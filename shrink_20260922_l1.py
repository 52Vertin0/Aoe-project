# -*- coding: utf-8 -*-
"""shrink_20260922_l1.py —— L1 级（纯排版）注释块回流。

规则（与 skill §3.7a 一致）：
  · 只动【整块都是 // 注释】的最大连续段；不碰任何含代码的行。
  · 段内以 "★" 开头的行、以及纯横幅行（====/----）必须独占行首（导航标记）。
  · 其余续行按"显示宽度 <= MAXW"贪心合并到上一行末尾。
  · 自证：合并前后【归一化（去掉 // 与全部空白）后的文字多重集】必须全等；
    不等则 ABORT 不写文件。
  · 源文件 CRLF，写回保 CRLF。
"""
import io, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else 'UsrAI.cpp'
MAXW = int(sys.argv[2]) if len(sys.argv) > 2 else 148          # 显示宽度上限（CJK 记 2 列）

raw = io.open(SRC, 'rb').read()
text = raw.decode('utf-8')
crlf = '\r\n' in text
lines = text.split('\r\n') if crlf else text.split('\n')

def is_cmt(s):
    return s.strip().startswith('//')

def disp_w(s):
    w = 0
    for ch in s:
        w += 2 if ord(ch) > 0x2E7F else 1
    return w

def body_of(s):
    """去掉行首缩进与 // 标记，返回注释正文（不含换行）。"""
    t = s.lstrip()
    assert t.startswith('//')
    return t[2:]

BANNER = set('=-*_#')

def starts_segment(cmt_body):
    b = cmt_body.strip()
    if not b:
        return False
    if b[0] == '\u2605':            # ★ 导航标记：必须行首独立
        return True
    # 纯横幅行：===== ---- ***** 等（去掉首尾后只剩一种符号）
    core = b.strip()
    if len(core) >= 6 and len(set(core)) == 1 and core[0] in BANNER:
        return True
    return False

out = []
i = 0
N = len(lines)
stat = {'runs': 0, 'before': 0, 'after': 0}

while i < N:
    if not is_cmt(lines[i]):
        out.append(lines[i]); i += 1; continue
    # 收集最大连续注释段
    j = i
    while j < N and is_cmt(lines[j]):
        j += 1
    run = lines[i:j]
    stat['runs'] += 1
    stat['before'] += len(run)

    if len(run) == 1:
        out.extend(run); i = j; continue

    # 逐行归段：第一行必起新段；其余行按 starts_segment 判断
    segs = []            # 每段 = (indent, [body,...])
    for k, s in enumerate(run):
        b = body_of(s)
        if k == 0 or starts_segment(b):
            segs.append([s[:len(s) - len(s.lstrip())], [b]])
        else:
            segs[-1][1].append(b)

    # 贪心打包每段
    rebuilt = []
    for indent, bodies in segs:
        cur = ''
        for b in bodies:
            b = b.strip()
            if not b:
                continue
            if cur == '':
                cur = b
            elif disp_w(indent + '// ' + cur + ' ' + b) <= MAXW:
                cur = cur + ' ' + b
            else:
                rebuilt.append(indent + '// ' + cur)
                cur = b
        if cur != '':
            rebuilt.append(indent + '// ' + cur)

    # ---- 自证：归一化文字比较 ----
    def norm(ls):
        acc = []
        for s in ls:
            acc.append(''.join(body_of(s).split()))
        return ''.join(acc)
    a, b = norm(run), norm(rebuilt)
    if a != b:
        print('ABORT: 注释段文字不等 行%d..%d' % (i + 1, j))
        print('  before:', a[:200])
        print('  after :', b[:200])
        sys.exit(1)

    out.extend(rebuilt)
    stat['after'] += len(rebuilt)
    i = j

new_text = crlf and '\r\n'.join(out) or '\n'.join(out)
io.open(SRC, 'wb').write(new_text.encode('utf-8'))

print('注释段 %d 个：%d 行 -> %d 行  (省 %d 行)' % (
    stat['runs'], stat['before'], stat['after'], stat['before'] - stat['after']))
print('总行数：%d -> %d' % (N, len(out)))
