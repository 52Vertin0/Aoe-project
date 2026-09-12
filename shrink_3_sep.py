# -*- coding: utf-8 -*-
"""
shrink_3_sep.py —— 第三轮：剥离"装饰线包裹"注释块的首/尾分隔线（纯注释，行为零变化）
规则：连续注释块，长度>=3，首行与末行皆为纯分隔线（// ===== / ----- 等），
      中间行全部为注释 ⇒ 删除首尾两行，仅保留内容行。
纪律：只动注释块；断言块内每行都是注释行。
"""
import io, re, sys

SRC = 'UsrAI.cpp'
raw = io.open(SRC, encoding='utf-8', newline='').read()
lines = raw.split('\r\n')
N = len(lines)

SEP = re.compile(r'^\s*//\s*[=\-*~+]{6,}\s*$')

targets = []
i = 0
while i < N:
    if lines[i].lstrip().startswith('//'):
        j = i
        while j < N and lines[j].lstrip().startswith('//'):
            j += 1
        blk = lines[i:j]
        if len(blk) >= 3 and SEP.match(blk[0]) and SEP.match(blk[-1]):
            targets.append((i + 1, j))      # 1-based, 含两端
        i = j
    else:
        i += 1

# 校验
errs = []
for (s, e) in targets:
    for k in range(s - 1, e):
        if not lines[k].lstrip().startswith('//'):
            errs.append('块 %d-%d 内第 %d 行非注释' % (s, e, k + 1))
if errs:
    print('ABORT：'); [print('  ', x) for x in errs]; sys.exit(1)

before = len(lines)
out = list(lines)
for (s, e) in sorted(targets, key=lambda t: -t[0]):
    # 删除首行(索引 s-1) 与末行(索引 e-1)
    del out[e - 1]
    del out[s - 1]

print('剥离装饰线块数 %d ｜ 行 %d → %d （−%d）' % (len(targets), before, len(out), before - len(out)))
io.open(SRC, 'w', encoding='utf-8', newline='').write('\r\n'.join(out))
d = io.open(SRC, 'rb').read()
print('CRLF %d / LF %d（应相等）' % (d.count(b'\r\n'), d.count(b'\n')))
print('WROTE OK')
