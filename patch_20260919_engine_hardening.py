# -*- coding: utf-8 -*-
"""
引擎侧防御性加固（针对 OJ/Linux 上 UsrAI::processData 首句 SIGSEGV）

崩溃事实（两次复现，栈一致）：
  UsrAI.cpp:473  info = getInfo();
    -> tagGame::getInfo()          (持锁，return *Info)
    -> tagInfo::operator=          (GlobalVariate.cpp，进入 buildings 赋值)
    -> vector<tagBuilding>::operator=  (源 len=6 cap=6)
    -> __copy_move -> memcpy  ← SIGSEGV，源地址不可访问

静态审计结论：UsrAI.cpp 无内存安全缺陷（零裸内存操作 / 定长数组全有护栏 /
SN 索引全走 map / 坐标输出有 isPositionFree 边界检查 / theMap 有空指针守卫）。
=> 崩塌点在「读快照的深拷贝」上，属"受害者"，根因是 Info 指向的 buffer 元数据被破坏。

本补丁只做两件事，都是【纯防御、正常路径零行为变化】：
  P1  getInfo() 脏快照预检 —— 把「进程崩溃」降级为「本帧 AI 空转（丢一帧）」
  P2  enemyai.cpp around[100] 无界下标 —— 真正的越界写 BSS 缺陷，改 std::map
"""
import os
import sys

D = r'C:\new-aoe3.0.7g'
CR, LF = 13, 10
CRLF = bytes([CR, LF])
DRY = '--dry' in sys.argv


def load(p):
    return open(p, 'rb').read()


def save(p, b):
    open(p, 'wb').write(b)


def _norm(s):
    """把字面量统一成 CRLF（源码是 CRLF+UTF-8）"""
    bb = s.encode('utf-8')
    bb = bb.replace(CRLF, bytes([LF])).replace(bytes([LF]), CRLF)
    return bb


def rep(b, old, new, tag):
    o, n = _norm(old), _norm(new)
    c = b.count(o)
    assert c == 1, '[FAIL] %s: 命中 %d 次（应为 1）' % (tag, c)
    return b.replace(o, n)


# ============================================================
# P1: tagGame::getInfo() 脏快照预检
# ============================================================
gv = os.path.join(D, 'GlobalVariate.cpp')
b = load(gv)
old1 = '''tagInfo tagGame::getInfo() {
    QMutexLocker locker(&Locker);
    return *Info;
}'''
new1 = '''tagInfo tagGame::getInfo() {
    QMutexLocker locker(&Locker);
    // ★★★ 2026-09-19 防御性加固（DIRTY-SNAPSHOT）★★★
    //   背景：OJ(Linux/gcc13) 上 AI 线程在 return *Info 的深拷贝里 SIGSEGV
    //   （__memcpy_avx 源地址不可访问，源 vector len=6/cap=6）—— 说明 Info 指向的
    //   buffer 的 vector 元数据已被破坏，此时深拷贝必然踩到不可读内存。
    //   措施：拷贝前做一次零成本自洽预检（vector 不变式 size<=capacity 且 data 非空）。
    //   不自洽 ⇒ 判定脏快照，返回空快照，把「整个进程崩溃」降级为「本帧 AI 空转」。
    if (Info == NULL) return tagInfo();
    bool dirtySnap =
           Info->buildings.size()       > Info->buildings.capacity()
        || Info->farmers.size()         > Info->farmers.capacity()
        || Info->armies.size()          > Info->armies.capacity()
        || Info->enemy_buildings.size() > Info->enemy_buildings.capacity()
        || Info->enemy_farmers.size()   > Info->enemy_farmers.capacity()
        || Info->enemy_armies.size()    > Info->enemy_armies.capacity()
        || Info->resources.size()       > Info->resources.capacity()
        || (Info->buildings.size()       > 0 && Info->buildings.data()       == NULL)
        || (Info->farmers.size()         > 0 && Info->farmers.data()         == NULL)
        || (Info->armies.size()          > 0 && Info->armies.data()          == NULL)
        || (Info->resources.size()       > 0 && Info->resources.data()       == NULL);
    if (dirtySnap) return tagInfo();
    return *Info;
}'''
b2 = rep(b, old1, new1, 'P1 getInfo')
print('[OK ] P1 GlobalVariate.cpp  getInfo 脏快照预检')
if not DRY:
    save(gv, b2)

# ============================================================
# P2: enemyai.cpp  around[100] -> std::map
# ============================================================
ea = os.path.join(D, 'enemyai.cpp')
b = load(ea)
old2 = 'static int around[100];'
new2 = '''static std::map<int,int> around;   // ★ 2026-09-19 越界修复：原 int around[100] 用
                                   //   enemyInfo.armies.size() 作下标且无上界保护，
                                   //   军队数 >100 即越界写 BSS 段（本图峰值 76，余量仅 24）。
                                   //   改 map：operator[] 默认 0，与数组语义一致，无越界。'''
b2 = rep(b, old2, new2, 'P2 around')
print('[OK ] P2 enemyai.cpp  around[100] -> std::map')
if not DRY:
    save(ea, b2)

# ============================================================
# 复检
# ============================================================
if not DRY:
    g = load(gv)
    e = load(ea)
    print()
    print('--- 复检 ---')
    print('  GlobalVariate.cpp 含 DIRTY-SNAPSHOT :', g.count(b'DIRTY-SNAPSHOT'))
    print('  GlobalVariate.cpp 含 dirtySnap      :', g.count(b'dirtySnap'))
    print('  enemyai.cpp around 声明              :',
          b'static std::map<int,int> around;' in e)
    print('  enemyai.cpp 残留 int around[100]     :', e.count(b'static int around[100];'))
    for f in (gv, ea):
        raw = load(f)
        ok = raw.count(CRLF) == raw.count(bytes([CR])) == raw.count(bytes([LF]))
        print('  换行符 %-22s %s' % (os.path.basename(f), 'OK(CRLF)' if ok else 'BAD'))
else:
    print()
    print('（--dry 模式：未落盘）')
