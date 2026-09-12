# -*- coding: utf-8 -*-
r"""mk_submit.py —— 生成"网站提交版"：把仓库源转成**纯 LF 行尾**，并做体检。

为什么要转 LF：
    评测网站的服务端在落盘时几乎一定会做一次"补 CR"（Python 的
    `content.replace("\n", "\r\n")`，或 Windows 上的 text-mode `open("w")`）。
    若提交的是 CRLF 源，这一步会把已有的 `\r\n` 再补一个 `\r` ⇒ `\r\r\n`：
      · GCC 把孤立 `\r` 也当换行 ⇒ 报错行号 = 真实行号×2-1；
      · 更要命的是 `#define X \` 的续行符被 `\r` 切断 ⇒ 宏体掉到文件作用域
        ⇒ error: expected ')' before '?' token。
    若提交的是 LF 源，则同一步只会补出**正确的 CRLF**；服务端若原样保存，
    得到纯 LF —— GCC 对 LF/CRLF 一视同仁。⇒ **两种服务端行为都免疫**。

用法：
    python mk_submit.py                    # 输出到 <工程>\_submit\
    python mk_submit.py --out D:\somewhere # 指定输出目录
    python mk_submit.py --src C:\new-aoe3.0.7g
"""
import io, os, re, sys

DEFAULT_SRC = r'C:\new-aoe3.0.7g'

# ============================================================================
# --nodebug：额外产出「去掉调试文本」的提交版
#
#   做什么：`DebugText` 是引擎 ai.h 里 AI 类的成员函数（5 个重载：
#           std::string / QString / char* / int / double），全项目 121 处调用，
#           唯一输出目的地是游戏内 DebugText 栏 + AIText.log。
#           nodebug 版**不删调用**，而是在**所有 #include 之后**加一行变参宏整体置空：
#               #define DebugText(...) ((void)0)
#
#   为什么不逐处删调用：
#     · 121 处里有大量多行链式 `.arg()`，逐处删容易破坏括号配对；
#     · 宏版是「一行的改动」，且能用「剥注释后逐字符比对」证明除该行外零差异。
#   为什么必须在所有 #include 之后：
#     · 放在 `#include "UsrAI.h"`（→ ai.h）之前，会把 ai.h 里 DebugText 的**声明**也
#       替换掉 ⇒ 编译错。放最后一个 #include 之后，只影响 UsrAI.cpp 体内的调用。
#   已知代价（有意为之）：
#     · 实参不再求值 ⇒ 只服务打印的表达式被一并省掉（本项目它们全是纯查询，无副作用）；
#     · 可能有局部变量变成 set-but-unused ⇒ 必须用 -Wall -Wextra 复验 warning 数。
#   保留不动：`fprintf(stdout/stderr, "[OJ-ENV]…")` 环境自证 与 `[OJ-HB]` 每 300 帧
#     崩溃定位心跳 —— 它们是 OJ 上定位崩点/核对引擎版本的唯一通道，与 DebugText 无关。
# ============================================================================
NODEBUG_TAG = 'NODEBUG'

# 插入到「最后一个 #include 行」之后的宏块（纯 LF、UTF-8）
NODEBUG_PATCH = '''// ============================================================================================
// [NODEBUG] 去调试文本版（本文件由 mk_submit.py --nodebug 自动生成，请勿手改）
//   把 ai.h 中 AI::DebugText 的 5 个重载整体屏蔽为无操作 —— 121 处调用全部静默。
//   · 本块必须位于**所有 #include 之后**：放前面会把 ai.h 里的声明一起替换掉 ⇒ 编译错。
//   · 宏体用 `if (0) { (void)(...); }` 而非裸 `((void)0)`：
//     裸写法会把 23 个「只服务打印」的变量变成 unused/-Wunused-but-set-variable 警告；
//     if(0) 在 -O2 下整块被删（零运行时开销），但语义上"引用"了实参 ⇒ 不触发 unused。
//   · 外面套 do{}while(0)：调用点存在「单语句 if」的无花括号写法。
//   · 实参不再求值 ⇒ 仅影响"只服务打印"的表达式（本文件均为纯查询，无副作用）。
//   · 保留 [OJ-ENV] 环境自证与 [OJ-HB] 崩溃定位心跳（fprintf，与 DebugText 无关）。
//   复现： python mk_submit.py --nodebug
// ============================================================================================
#define DebugText(...) do { if (0) { (void)(__VA_ARGS__); } } while (0)
'''


def make_nodebug(text):
    """把纯 LF 源码变成去 DebugText 版。text / 返回值都是 bytes。

    只做一件事：在**最后一个 `#include` 行之后**插入 NODEBUG_PATCH。
    用「最后一个 #include」而不是写死行号 —— 源码增删注释/常量时不会失效。
    返回 (新内容, 补丁起始行号, 补丁行数)，供打印核对。
    """
    assert b'\r' not in text, '必须先转成纯 LF 再打补丁'
    lines = text.split(b'\n')
    idx = [i for i, L in enumerate(lines) if L.startswith(b'#include')]
    if not idx:
        raise RuntimeError('源码里找不到 #include，拒绝打补丁')
    at = idx[-1] + 1
    patch = NODEBUG_PATCH.encode('utf-8').rstrip(b'\n').split(b'\n')
    out = lines[:at] + [b''] + patch + lines[at:]
    return b'\n'.join(out), at + 2, len(patch)


def check(path, expect_lines=None):
    b = open(path, 'rb').read()
    rr = b.count(b'\r\r\n')
    crlf = b.count(b'\r\n')
    lf = b.count(b'\n') - crlf
    lone_cr = b.count(b'\r') - crlf - rr
    tri = len(re.findall(rb'\?\?[=()<>/!\'-]', b))
    nl = b.count(b'\n')
    # 续行（行尾反斜杠）——这是 \r\r\n 唯一会炸的东西
    cont = [i + 1 for i, L in enumerate(b.split(b'\n'))
            if L.rstrip(b' \t\r').endswith(b'\\')]
    bad = []
    if rr:
        bad.append(r'\r\r\n x%d' % rr)
    if lf and crlf:
        bad.append('行尾混用 (CRLF=%d, LF=%d)' % (crlf, lf))
    if tri:
        bad.append('三元字 x%d' % tri)
    if lone_cr:
        bad.append('孤立 CR x%d' % lone_cr)
    if expect_lines is not None and nl != expect_lines:
        bad.append('行数 %d != %d' % (nl, expect_lines))
    print('  %s' % path)
    print('     %d 行 / %d B   CRLF=%d  纯LF=%d  \\r\\r\\n=%d  三元字=%d'
          % (nl, len(b), crlf, lf, rr, tri))
    print('     续行(行尾反斜杠) %d 处%s' % (len(cont), ('  第 ' + ','.join(map(str, cont[:6])) + ' 行') if cont else ''))
    print('     判定 : %s' % ('[X] ' + ' / '.join(bad) if bad else '[.] 干净'))
    return len(bad)


def main():
    src = DEFAULT_SRC
    out = None
    args = sys.argv[1:]
    i = 0
    nodebug = False
    nodebug_only = False
    while i < len(args):
        if args[i] == '--src':
            src = args[i + 1]; i += 2
        elif args[i] == '--out':
            out = args[i + 1]; i += 2
        elif args[i] == '--nodebug':
            nodebug = True; i += 1
        elif args[i] == '--nodebug-only':
            nodebug = nodebug_only = True; i += 1
        else:
            i += 1
    if out is None:
        out = os.path.join(src, '_submit')

    pairs = [('UsrAI.cpp', 'UsrAI.cpp'), ('UsrAI.h', 'UsrAI.h')]
    for s, d in pairs:
        sp = os.path.join(src, s)
        if not os.path.exists(sp):
            print('缺文件: %s' % sp)
            return 1
    os.makedirs(out, exist_ok=True)

    print('=' * 78)
    print('源（仓库，可含 CRLF）')
    nbad = 0
    for s, _ in pairs:
        nbad += check(os.path.join(src, s))

    if not nodebug_only:
        print('=' * 78)
        print('生成提交版（纯 LF）-> %s' % out)
        for s, d in pairs:
            b = open(os.path.join(src, s), 'rb').read()
            b = b.replace(b'\r\r\n', b'\r\n').replace(b'\r\n', b'\n')   # 先消双CR再统一成 LF
            assert b'\r' not in b, '仍有 CR 残留'
            open(os.path.join(out, d), 'wb').write(b)
        for _, d in pairs:
            nbad += check(os.path.join(out, d), None)
    else:
        print('=' * 78)
        print('--nodebug-only：跳过主提交件，%s\\UsrAI.cpp / UsrAI.h 保持原样不动' % out)

    if nodebug:
        print('=' * 78)
        nbdir = os.path.join(out, 'nodebug')
        os.makedirs(nbdir, exist_ok=True)
        print('生成去调试文本版（纯 LF + 屏蔽 DebugText）-> %s' % nbdir)
        for s, d in pairs:
            b = open(os.path.join(src, s), 'rb').read()
            b = b.replace(b'\r\r\n', b'\r\n').replace(b'\r\n', b'\n')   # 先消双CR再统一成 LF
            assert b'\r' not in b, '仍有 CR 残留'
            if s == 'UsrAI.cpp':
                plain = b                                   # 打补丁前的纯 LF 源，用作自检基线
                b, at, n = make_nodebug(b)
                print('    [补丁] 第 %d~%d 行（最后一个 #include 之后）' % (at, at + n - 1))
                n_src = sum(1 for L in plain.split(b'\n') if b'DebugText(' in L)
                n_nb = sum(1 for L in b.split(b'\n') if b'DebugText(' in L)
                print('    [校验] DebugText( 所在行数：源 %d → 产物 %d（+1 = 宏定义行；'
                      '相等即证「没误删任何调用点」）' % (n_src, n_nb))
                n_cut = len(plain.split(b'\n')) + n + 1 - len(b.split(b'\n'))
                print('    [校验] 行数 %d + %d(补丁+空行) = %d %s'
                      % (len(plain.split(b'\n')), n + 1, len(b.split(b'\n')),
                         'OK' if n_cut == 0 else '★异常'))
            open(os.path.join(nbdir, d), 'wb').write(b)
        for _, d in pairs:
            nbad += check(os.path.join(nbdir, d), None)

    print('=' * 78)
    if nbad:
        print('==> 源侧有损伤（%d 项）。注意：LF 版只消行尾，**不会**修复"中文变 ?"或行数缺失。' % nbad)
    else:
        if nodebug_only:
            print('==> 全部干净。去调试文本版：%s\\nodebug\\UsrAI.cpp + UsrAI.h（主提交件未动）' % out)
        elif nodebug:
            print('==> 全部干净。提交件两份：')
            print('    带调试文本 : %s\\UsrAI.cpp + UsrAI.h' % out)
            print('    去调试文本 : %s\\nodebug\\UsrAI.cpp + UsrAI.h' % out)
        else:
            print('==> 全部干净。把 %s 下的两个文件提交到网站即可。' % out)
        print('    提交后若仍有问题，用 chk_src.py / chk_src.sh 体检"网站传回来的那份"。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
