# -*- coding: utf-8 -*-
"""精简前体检：注释占比 / 函数体量 / 重复行块 / 长注释带。只读，不改文件。"""
import io, re, sys, collections

SRC = 'UsrAI.cpp'
raw = io.open(SRC, encoding='utf-8', newline='').read()
lines = raw.split('\r\n')
N = len(lines)

blank = 0
comment_only = 0
code = 0
inline_cmt = 0
in_block = False
for ln in lines:
    s = ln.strip()
    if in_block:
        comment_only += 1
        if '*/' in s:
            in_block = False
        continue
    if not s:
        blank += 1
        continue
    if s.startswith('/*'):
        comment_only += 1
        if '*/' not in s:
            in_block = True
        continue
    if s.startswith('//'):
        comment_only += 1
        continue
    code += 1
    if '//' in ln and not re.search(r'"[^"]*//', ln):
        inline_cmt += 1

print('=== 体量构成 (%s, N=%d) ===' % (SRC, N))
print('  纯注释行 : %5d  (%.1f%%)' % (comment_only, 100.0*comment_only/N))
print('  空行     : %5d  (%.1f%%)' % (blank, 100.0*blank/N))
print('  含代码行 : %5d  (%.1f%%)   其中带行尾注释 %d' % (code, 100.0*code/N, inline_cmt))
print()

# 注释块长度分布（连续的注释/空行视为一带）
bands = []
cur = 0
for ln in lines:
    s = ln.strip()
    if s.startswith('//') or s.startswith('*') or s.startswith('/*') or (not s and cur):
        cur += 1
    else:
        if cur >= 8:
            bands.append(cur)
        cur = 0
if cur >= 8:
    bands.append(cur)
bands.sort(reverse=True)
print('=== 长注释带（>=8 行连续注释/空行）共 %d 段，合计 %d 行 ===' % (len(bands), sum(bands)))
print('  最长 15 段:', bands[:15])
print()

# 连续空行 >=3
runs = re.findall(r'(?:\r\n){4,}', raw)
print('=== 连续空行 >=3 的段落: %d 处，合计可省 %d 行 ===' % (len(runs), sum(len(r)//2-2 for r in runs)))
print()

# 函数体量（UsrAI::xxx 定义）
fn_re = re.compile(r'^[A-Za-z_][\w:<>,&*\s]*\s+UsrAI::(\w+)\s*\(', re.M)
marks = [(m.start(), m.group(1), raw[:m.start()].count('\n')) for m in fn_re.finditer(raw)]
sizes = []
for i, (pos, name, ln0) in enumerate(marks):
    end = raw.find('\n}\n', pos)
    endln = raw[:end].count('\n') if end > 0 else N
    sizes.append((endln - ln0 + 1, name, ln0+1))
sizes.sort(reverse=True)
print('=== 函数体量 top 20 (共 %d 个 UsrAI:: 定义) ===' % len(sizes))
for s, nm, ln in sizes[:20]:
    print('  %5d 行  %-32s  @%d' % (s, nm, ln))
print()

# 重复行块（连续 6 行窗口，规范化后比对）
def norm(s):
    s = re.sub(r'//.*$', '', s)
    return re.sub(r'\s+', ' ', s).strip()
W = 6
win = collections.defaultdict(list)
for i in range(N-W+1):
    chunk = [norm(lines[j]) for j in range(i, i+W)]
    if sum(1 for c in chunk if c) < W-1:      # 允许 1 行空
        continue
    key = '\n'.join(chunk)
    win[key].append(i+1)
dups = [(v, k) for k, v in win.items() if len(v) > 1]
dups.sort(key=lambda t: -len(t[0]))
print('=== 重复代码窗口 (连续 %d 行，去注释后相同) 共 %d 组 ===' % (W, len(dups)))
for v, k in dups[:12]:
    print('  x%d 行号 %s' % (len(v), v[:6]))
    print('      | ' + k.split('\n')[0][:96])
print()

# 大括号/分号密度
print('=== 简单信号 ===')
print('  if 语句总数      :', len(re.findall(r'\bif\s*\(', raw)))
print('  } else if        :', raw.count('} else if'))
print('  for 循环         :', len(re.findall(r'\bfor\s*\(', raw)))
print('  单行 if 无大括号 :', len(re.findall(r'^\s*if\s*\(.*\)\s*[^;{/]*;', raw, re.M)))
