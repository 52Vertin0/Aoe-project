# -*- coding: utf-8 -*-
"""深挖精简候选：长注释带清单 / 真重复块 / 可疑冗余写法。只读。"""
import io, re, collections

SRC = 'UsrAI.cpp'
raw = io.open(SRC, encoding='utf-8', newline='').read()
lines = raw.split('\r\n')
N = len(lines)

fn_re = re.compile(r'^[A-Za-z_][\w:<>,&*\s]*?\s+UsrAI::(\w+)\s*\(')
funcs = []
for i, ln in enumerate(lines):
    m = fn_re.match(ln.rstrip())
    if m:
        funcs.append((i + 1, m.group(1)))

def owner(ln):
    lo, hi = None, None
    for (fl, nm) in funcs:
        if fl <= ln:
            lo, hi = fl, nm
        else:
            break
    return hi or '?', ln - (lo or 0) + 1

# ---- 1. 长注释带（>=10 行） ----
print('=== 长注释带 >=10 行（行区间 / 所属函数 / 首句）===')
bands = []
i = 0
while i < N:
    s = lines[i].strip()
    if s.startswith('//'):
        j = i
        while j < N and (lines[j].strip().startswith('//') or not lines[j].strip()):
            j += 1
        if j - i >= 10:
            bands.append((i + 1, j, 0))
        i = j
    else:
        i += 1
tot = 0
for (a, b, _) in bands:
    tot += (b - a)
    fn, rel = owner(a)
    head = lines[a - 1].strip()[:60]
    print('  %5d-%-5d %3d行  %-22s +%-4d  %s' % (a, b, b - a, fn, rel, head))
print('  >> 合计 %d 行' % tot)
print()

# ---- 2. 真重复块（>=4 行有效代码） ----
def norm(s):
    s = re.sub(r'//.*$', '', s)
    return re.sub(r'\s+', ' ', s).strip()
W = 4
win = collections.defaultdict(list)
for i in range(N - W + 1):
    chunk = [norm(lines[j]) for j in range(i, i + W)]
    if any(not c for c in chunk):
        continue
    if sum(1 for c in chunk if c in ('}', '{', '};')) >= 2:
        continue
    if all(len(c) <= 2 for c in chunk):
        continue
    win['\n'.join(chunk)].append(i + 1)
dups = sorted([(v, k) for k, v in win.items() if len(v) > 1], key=lambda t: -len(t[1]))
print('=== 真重复代码块 >=%d 行（共 %d 组）===' % (W, len(dups)))
for v, k in dups[:16]:
    fns = sorted(set(owner(x)[0] for x in v))
    print('  x%d  行 %-28s 函数 %s' % (len(v), str(v[:5]), ','.join(fns)))
    for l in k.split('\n'):
        print('        ' + l[:100])
print()

# ---- 3. 可疑冗余写法 ----
print('=== 可疑冗余写法 ===')
pats = [
    (r'\breturn\s+(true|false);\s*\r\n\s*\}', 'if(cond){return true/false} 可写 return cond'),
    (r'\?\s*true\s*:\s*false', 'x = cond ? true : false'),
    (r'\?\s*false\s*:\s*true', 'x = cond ? false : true'),
    (r'^\s*else\s*\{?\s*$', 'else 分支（需人工看是否可去）'),
    (r'(\w+)\s*=\s*\1\s*[;)]', '自赋值'),
    (r';;', '双分号'),
    (r'\bcontinue;\s*\r\n\s*\}', 'trailing continue'),
]
for p, desc in pats:
    c = len(re.findall(p, raw, re.M))
    print('  %-42s %4d' % (desc, c))
print()

# ---- 4. DebugText 前缀分布（可抽辅助函数的候选） ----
print('=== DebugText 调用统计 ===')
dt = re.findall(r'DebugText\(\s*QString\(\s*"(\[?[A-Za-z0-9_\-\[\] ]*)', raw)
cnt = collections.Counter(re.match(r'(\[[A-Z0-9\-]+\]?)', d).group(1) if re.match(r'\[', d) else '(无标签)'
                          for d in dt)
print('  DebugText 总数:', len(re.findall(r'DebugText\(', raw)))
print('  带 [TAG] 的标签数:', len(cnt), ' top15:', cnt.most_common(15))
print()

# ---- 5. countBuildingsExisting 调用点 ----
cbe = re.findall(r'countBuildingsExisting\((\w+)\)', raw)
print('=== countBuildingsExisting 调用（共 %d）===' % len(cbe))
for k, v in collections.Counter(cbe).most_common():
    print('  %-32s %d' % (k, v))
print()

# ---- 6. 空行分布 ----
print('=== 空行总数: %d ===' % sum(1 for l in lines if not l.strip()))
