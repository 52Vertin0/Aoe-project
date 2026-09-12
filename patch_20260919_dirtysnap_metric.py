# -*- coding: utf-8 -*-
"""
把「脏快照降级」从静默变成【可观测机制量】。

P3  GlobalVariate.cpp：加全局计数 + 版本串（供 exe 内容验证）
P4  UsrAI.cpp：每分钟打印一次计数 ⇒ OJ 的 ait 里可见 [DIRTY-SNAP]

意义：如果 OJ 上 [DIRTY-SNAP] count > 0，即**直接证明** Info buffer 的
vector 元数据确被破坏、而崩溃已被预检拦下 —— 把偶发崩溃变成可量化指标。
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
    bb = s.encode('utf-8')
    return bb.replace(CRLF, bytes([LF])).replace(bytes([LF]), CRLF)


def rep(b, old, new, tag):
    o, n = _norm(old), _norm(new)
    c = b.count(o)
    assert c == 1, '[FAIL] %s: 命中 %d 次（应为 1）' % (tag, c)
    return b.replace(o, n)


# ============================================================
# P3: 全局计数 + 版本串
# ============================================================
gv = os.path.join(D, 'GlobalVariate.cpp')
b = load(gv)
old3 = 'tagInfo &tagInfo::operator=(const tagInfo &other) {'
new3 = '''// ★★★ 2026-09-19：脏快照计数（机制量）★★★
//   getInfo() 的预检每拦下一次"元数据已被破坏的快照"就 +1。
//   若在 OJ 上 > 0，即直接证明 Info 指向的 buffer 的 vector 元数据被破坏，
//   而进程崩溃已被预检降级为"丢一帧"。值由 UsrAI 每分钟打进 ait（[DIRTY-SNAP]）。
int g_dirtySnapCount = 0;
const char* g_dirtySnapTag = "DIRTY-SNAPSHOT";   // 非 static ⇒ 保证进 exe，供版本验证
tagInfo &tagInfo::operator=(const tagInfo &other) {'''
b2 = rep(b, old3, new3, 'P3 全局计数')
print('[OK ] P3 GlobalVariate.cpp  g_dirtySnapCount + 版本串')

old4 = '    if (dirtySnap) return tagInfo();'
new4 = '    if (dirtySnap) { g_dirtySnapCount++; return tagInfo(); }'
b2 = rep(b2, old4, new4, 'P3b 计数递增')
print('[OK ] P3b getInfo 脏快照分支计数递增')
if not DRY:
    save(gv, b2)

# ============================================================
# P4: UsrAI 每分钟打印计数
# ============================================================
ua = os.path.join(D, 'UsrAI.cpp')
b = load(ua)
old5 = '''void UsrAI::processData() {
    info = getInfo();
    frame = info.GameFrame;
'''
new5 = '''void UsrAI::processData() {
    info = getInfo();
    frame = info.GameFrame;

    // ★★★ 2026-09-19 诊断（可观测机制量）：引擎侧 getInfo() 预检拦下的脏快照次数。
    //   崩溃场景：OJ(Linux/gcc13) 上 AI 线程读快照的深拷贝 SIGSEGV（源内存不可访问）。
    //   加固后该场景被降级为"丢一帧"，此计数即其发生频率。
    //   ⇒ 若 OJ 的 ait 里出现 [DIRTY-SNAP] count>0，根因（buffer 元数据被破坏）即被证实。
    {
        extern int g_dirtySnapCount;
        static int lastDirtySnapFrame = -1;
        if (frame % 1500 < 2 && frame != lastDirtySnapFrame) {
            lastDirtySnapFrame = frame;
            DebugText(QString("[DIRTY-SNAP f=%1] 累计脏快照拦截=%2")
                      .arg(frame).arg(g_dirtySnapCount));
        }
    }
'''
b2 = rep(b, old5, new5, 'P4 UsrAI 诊断日志')
print('[OK ] P4 UsrAI.cpp  [DIRTY-SNAP] 分钟级日志')
if not DRY:
    save(ua, b2)

if not DRY:
    print()
    print('--- 复检 ---')
    g, u = load(gv), load(ua)
    print('  GlobalVariate.cpp g_dirtySnapCount :', g.count(b'g_dirtySnapCount'))
    print('  GlobalVariate.cpp g_dirtySnapTag   :', g.count(b'g_dirtySnapTag'))
    print('  UsrAI.cpp         DIRTY-SNAP       :', u.count(b'DIRTY-SNAP'))
    for f in (gv, ua):
        raw = load(f)
        ok = raw.count(CRLF) == raw.count(bytes([CR])) == raw.count(bytes([LF]))
        print('  换行符 %-22s %s' % (os.path.basename(f), 'OK(CRLF)' if ok else 'BAD'))
else:
    print('（--dry 模式：未落盘）')
