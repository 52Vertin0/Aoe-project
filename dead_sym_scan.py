# -*- coding: utf-8 -*-
"""
dead_sym_scan.py —— 零消费点符号扫描（只读，不修改任何文件）

原理：一个 #define / 类成员 / 函数，若在【全项目 .cpp/.h + Qt 侧】里
      除声明处外再无任何引用，则删除它**可证明不改行为**。
口径与铁律一致：删前必须 grep 反查消费点，只有"零消费点"才算真无用。

输出：dead_defines.txt / dead_members.txt
"""
import io, os, re, glob, collections

ROOT = '.'
SRC_CPP = 'UsrAI.cpp'
SRC_H   = 'UsrAI.h'

# ---------- 1. 收集全项目可搜索文本 ----------
files = []
for pat in ('*.cpp', '*.h', '*.hpp', '*.cc'):
    files += glob.glob(os.path.join(ROOT, pat))
files = sorted(set(files))
blobs = {}
for f in files:
    try:
        blobs[f] = io.open(f, encoding='utf-8', errors='replace').read()
    except Exception:
        pass

def count_all(tok, exclude_file=None, exclude_line_nos=()):
    """全项目计数，可排除某文件的若干行（声明处）。"""
    n = 0
    for f, t in blobs.items():
        for i, l in enumerate(t.split('\n'), 1):
            if f == exclude_file and i in exclude_line_nos:
                continue
            n += len(re.findall(r'\b' + re.escape(tok) + r'\b', l))
    return n

# ---------- 2. #define 扫描 ----------
cpp = io.open(SRC_CPP, encoding='utf-8', errors='replace').read()
h   = io.open(SRC_H,   encoding='utf-8', errors='replace').read()

out = []
seen = {}
for fname in (SRC_CPP, SRC_H):
    for i, l in enumerate(io.open(fname, encoding='utf-8', errors='replace').read().split('\n'), 1):
        m = re.match(r'\s*#define\s+([A-Za-z_]\w*)\s*(.*)$', l)
        if not m:
            continue
        name, body = m.group(1), m.group(2)
        if name in seen:            # 同名重复定义（含 #undef 后再定义）
            seen[name].append((fname, i))
            continue
        seen[name] = [(fname, i)]
for name, locs in sorted(seen.items()):
    ex_f = {f for f, _ in locs}
    # 声明行全部排除
    n = 0
    for f, t in blobs.items():
        if f in ex_f:
            lines = t.split('\n')
            excl = {i for ff, i in locs if ff == f}
            for i, l in enumerate(lines, 1):
                if i in excl:
                    continue
                n += len(re.findall(r'\b' + re.escape(name) + r'\b', l))
        else:
            n += len(re.findall(r'\b' + re.escape(name) + r'\b', t))
    ndef = len(locs)
    if n == 0 or (n == ndef and ndef > 1):
        out.append((n, name, locs, blobs.get(SRC_CPP, '')))

with io.open('dead_defines.txt', 'w', encoding='utf-8', newline='\r\n') as fh:
    fh.write('=== 零消费 #define（全项目除声明外 0 引用）===\n')
    for n, name, locs, _ in out:
        fh.write('%-46s 引用=%d  声明: %s\n' % (name, n, ', '.join('%s:%d' % x for x in locs)))
    fh.write('\n共 %d 条；总 #define 数 %d\n' % (len(out), len(seen)))
print('零消费 #define: %d / %d  -> dead_defines.txt' % (len(out), len(seen)))

# ---------- 3. UsrAI.h 成员扫描 ----------
MEM = re.compile(r'^\s{4}(?!//|/\*)(?:static\s+|const\s+|mutable\s+|volatile\s+)*'
                 r'([A-Za-z_][\w:<>,\s\*&\[\]]*?)\s+([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*(?:=[^;]*)?;\s*$')
mems = []
for i, l in enumerate(h.split('\n'), 1):
    m = MEM.match(l)
    if not m:
        continue
    typ, name = m.group(1).strip(), m.group(2)
    if typ in ('return', 'typedef', 'using', 'struct', 'class', 'enum'):
        continue
    mems.append((name, typ, i))

rows = []
for name, typ, i in mems:
    refs = 0
    for f, t in blobs.items():
        if f == SRC_H:
            for k, l in enumerate(t.split('\n'), 1):
                if k == i:
                    continue
                refs += len(re.findall(r'\b' + re.escape(name) + r'\b', l))
        else:
            refs += len(re.findall(r'\b' + re.escape(name) + r'\b', t))
    rows.append((refs, name, typ, i))

rows.sort()
with io.open('dead_members.txt', 'w', encoding='utf-8', newline='\r\n') as fh:
    fh.write('=== UsrAI.h 成员（按引用数升序；refs==0 = 只声明未使用）===\n')
    for refs, name, typ, i in rows:
        fh.write('refs=%-5d h:%-5d %-26s %s\n' % (refs, i, name, typ))
    fh.write('\n成员总数 %d；refs==0 共 %d\n' % (len(rows), sum(1 for r in rows if r[0] == 0)))
print('成员 %d；refs==0 共 %d  -> dead_members.txt' % (len(rows), sum(1 for r in rows if r[0] == 0)))
