# -*- coding: utf-8 -*-
"""dump 所有 >=MINL 行的连续注释块（含行号），供人工写压缩版。只读。"""
import io, re, sys

MINL = int(sys.argv[1]) if len(sys.argv) > 1 else 8
SRC = 'UsrAI.cpp'
lines = io.open(SRC, encoding='utf-8', newline='').read().split('\r\n')
N = len(lines)

fn_re = re.compile(r'^[A-Za-z_][\w:<>,&*\s]*?\s+UsrAI::(\w+)\s*\(')
funcs = [(i + 1, m.group(1)) for i, l in enumerate(lines) if (m := fn_re.match(l.rstrip()))]
def owner(ln):
    cur = '?'
    for fl, nm in funcs:
        if fl <= ln: cur = nm
        else: break
    return cur

i = 0
idx = 0
tot = 0
while i < N:
    if lines[i].lstrip().startswith('//'):
        j = i
        while j < N and lines[j].lstrip().startswith('//'):
            j += 1
        n = j - i
        if n >= MINL:
            idx += 1
            tot += n
            print('##### B%03d  lines %d-%d  (%d 行)  @%s' % (idx, i + 1, j, n, owner(i + 1)))
            for k in range(i, j):
                print('%5d| %s' % (k + 1, lines[k]))
            print()
        i = j
    else:
        i += 1
print('===== 共 %d 块, %d 行 =====' % (idx, tot))
