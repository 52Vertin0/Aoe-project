# -*- coding: utf-8 -*-
r"""chk_src.py —— 源码"字节级"体检：专抓会让 GCC 报怪错、却肉眼看不出问题的那些损伤。

用法：
    python chk_src.py <文件> [...] [--expect-lines N]
    （--expect-lines 只作用于第一个文件）
    python chk_src.py --scan <根目录> [...] [--maxdepth N] [--name 通配]
    （--scan：递归找出所有 UsrAI*.cpp/.h 并逐个体检；默认深度 6。
      用于回答"我手上到底哪份是干净源"这类问题。）

检查项（任一为真 => 该文件不能直接提交/编译）：
  1. \r\r\n（双 CR）      —— Windows 文本模式 + 手工拼 CRLF 的二次翻译产物。
                            GCC 把孤立 \r 也当换行 ⇒ 行号变 2N-1；更致命的是
                            `#define X \` 的续行会被 \r 切断 ⇒ 宏体掉到文件作用域。
  2. 孤立 \n / 孤立 \r     —— 行尾混用，同上类风险。
  3. ??X 三元字           —— 中文被有损转码成 '?' 后的残留（??= ??( ??< ??/ ??- ??! …）。
  4. 非 UTF-8 字节        —— 编码被换过（GBK/UTF-16/…）。
  5. UTF-8 BOM            —— 某些工具链路不接受。
  6. 行数快照比对          —— 传 --expect-lines 时校验，防"悄悄少了几百行"。
"""
import sys, os, re, collections

TRI = re.compile(rb'\?\?[=()<>/!\'-]')


def check(path, expect_lines=None, quiet=False):
    b = open(path, 'rb').read()
    name = os.path.basename(path)
    bad = []

    rr = b.count(b'\r\r\n')
    crlf = b.count(b'\r\n')
    lf = b.count(b'\n')
    cr = b.count(b'\r')
    lone_lf = lf - crlf
    lone_cr = cr - crlf - rr        # rr 单独报，不再重复计入孤立 CR

    tri = TRI.findall(b)
    tri_lines = collections.Counter()
    for m in TRI.finditer(b):
        tri_lines[b.count(b'\n', 0, m.start()) + 1] += 1

    bom = b[:3] == b'\xef\xbb\xbf'
    try:
        b[len(b'\xef\xbb\xbf') if bom else 0:].decode('utf-8')
        utf8_ok = True
    except Exception as e:
        utf8_ok = False
        err = e

    if rr:
        bad.append('\\r\\r\\n x%d —— 每行会被 GCC 当两行（行号 2N-1），且断掉 \\ 续行' % rr)
    # ★ 2026-09-23：统一 LF 是"提交形态"（mk_submit.py 产出），本身无损伤；
    #   只有 LF 与 CRLF 混用才是损伤（历史误报：把 _submit/ 的纯 LF 判成"孤立 LF/混用"）。
    if lone_lf and crlf:
        bad.append('孤立 LF x%d —— 行尾混用（与 CRLF 并存）' % lone_lf)
    if lone_cr:
        bad.append('孤立 CR x%d —— GCC 会当换行' % lone_cr)
    if tri:
        head = ', '.join('第%d行' % k for k, _ in tri_lines.most_common(8))
        bad.append('三元字 ??X x%d —— 中文已被有损转码成 \'?\'（首见：%s）'
                   % (len(tri), head))
    if not utf8_ok:
        bad.append('非 UTF-8 —— 编码被换过')
    if bom:
        bad.append('带 UTF-8 BOM')
    if expect_lines is not None and lf != expect_lines:
        bad.append('行数 %d != 期望 %d —— 文件被动过' % (lf, expect_lines))

    if quiet:
        if bad:
            print('  [X] %-62s %s' % (path, ' / '.join(x.split(' ')[0] for x in bad)))
            for x in bad:
                print('        - %s' % x)
        else:
            print('  [.] %-62s OK  (%d 行, CRLF=%d)' % (path, lf, crlf))
        return len(bad)

    print('=' * 74)
    print('文件 : %s' % path)
    print('字节 : %d   行(\\n) : %d' % (len(b), lf))
    print('行尾 : CRLF=%d  孤立LF=%d  孤立CR=%d  \\r\\r\\n=%d' % (crlf, lone_lf, lone_cr, rr))
    print('编码 : %s%s' % ('UTF-8' if utf8_ok else '不是合法 UTF-8 -> ' + str(err)[:60],
                           '  +BOM' if bom else ''))
    print('三元字: %d 处' % len(tri))

    if bad:
        print('判定 : ✗ 有损伤')
        for x in bad:
            print('   - %s' % x)
    else:
        form = '统一 CRLF' if crlf else ('统一 LF（提交形态）' if lone_lf else '无行尾')
        print('判定 : ✓ 干净（UTF-8 / %s / 无三元字 / 行数符合）' % form)
    return len(bad)


SKIP_DIRS = {'release', '.git', '__pycache__', 'node_modules', 'appdata',
             'windows', '$recycle.bin', 'program files', 'program files (x86)',
             'programdata', 'system volume information', 'tmpbuild'}


def scan(roots, names, maxdepth):
    """递归找出匹配的文件名并逐个（安静模式）体检。返回有损伤的文件数。"""
    import fnmatch
    hits = []
    for r in roots:
        if not os.path.isdir(r):
            print('  跳过（不存在）: %s' % r)
            continue
        base = os.path.abspath(r).rstrip(os.sep).count(os.sep)
        for dp, dn, fn in os.walk(r):
            if dp.count(os.sep) - base >= maxdepth:
                dn[:] = []
            dn[:] = [d for d in dn if d.lower() not in SKIP_DIRS]
            for f in fn:
                if any(fnmatch.fnmatch(f.lower(), pat.lower()) for pat in names):
                    hits.append(os.path.join(dp, f))
    uniq = sorted(set(hits))
    print('扫描根 : %s' % ', '.join(roots))
    print('匹配   : %d 个文件（%s, 深度<=%d）' % (len(uniq), '/'.join(names), maxdepth))
    print('-' * 74)
    bad = 0
    for p in uniq:
        try:
            bad += check(p, None, quiet=True)
        except Exception as e:
            print('  [X] %-62s 读失败 %s' % (p, str(e)[:40]))
            bad += 1
    print('-' * 74)
    print('汇总   : %d 个文件，%d 个有损伤' % (len(uniq), bad))
    if len(uniq):
        print('         （[.] = 干净可直接编译；[X] = 有损伤，勿用于编译/提交）')
    return bad


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)

    if args[0] == '--scan':
        rest = args[1:]
        roots, depth, names = [], 6, ['UsrAI*.cpp', 'UsrAI*.h']
        k = 0
        while k < len(rest):
            a = rest[k]
            if a == '--maxdepth':
                depth = int(rest[k + 1]); k += 2
            elif a == '--name':
                names = [rest[k + 1]]; k += 2
            else:
                roots.append(a); k += 1
        if not roots:
            roots = [os.getcwd()]
        sys.exit(1 if scan(roots, names, depth) else 0)

    exp = None
    if '--expect-lines' in args:
        i = args.index('--expect-lines')
        exp = int(args[i + 1])
        del args[i:i + 2]
    n = 0
    for i, p in enumerate(args):
        if os.path.exists(p):
            n += check(p, exp if i == 0 else None)
        else:
            print('缺文件: %s' % p)
            n += 1
    sys.exit(1 if n else 0)
