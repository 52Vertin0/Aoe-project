# -*- coding: utf-8 -*-
"""全臂排行（四图合计）：统一 outcome 口径 + 伪U 过滤 + Wilson CI + 按图分层。
用法: python _allarms4.py [MIN_N]
"""
import glob, re, math, os, sys

MIN_N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
FR = re.compile(r'^\d\d:\d\d:\d\d+\s*\|\s*(\d+)\s*\|')
MAPS = ['map', 'map1', 'map2', 'map3']

def outcome(s):
    if '被祭司转换,归属阵营1->0' in s: return 'W'
    if 'DEFEAT: Priest killed' in s: return 'P'
    if 'DEFEAT: Town Center destroyed' in s: return 'T'
    if '敌方 摧毁主营' in s: return 'T'
    return 'U'

def wilson(k, n):
    if n == 0: return (0.0, 0.0, 0.0)
    p = k/n; z = 1.96
    d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return (p, c-h, c+h)

arms = {}
for fn in glob.glob('*_r0_*.ait'):
    parts = fn.split('_')
    # 形如 TAG_<map>_r0_N.ait 或 TAG_r0_N.ait（后者跳过，无法归图）
    m = re.match(r'^(.+?)_(map1|map2|map3|map)_r0_(\d+)\.ait$', fn)
    if not m: continue
    tag, mp = m.group(1), m.group(2)
    s = open(fn, encoding='utf-8', errors='replace').read()
    fr = [int(x.group(1)) for x in (FR.match(l) for l in s.splitlines()) if x]
    mx = max(fr) if fr else 0
    r = outcome(s)
    trunc = (r == 'U' and mx < 44000)
    d = arms.setdefault(tag, dict(W=0, n=0, trunc=0, per={k: [0, 0] for k in MAPS}))
    d['n'] += 1; d['per'][mp][1] += 1
    if trunc:
        d['trunc'] += 1
    else:
        if r == 'W':
            d['W'] += 1; d['per'][mp][0] += 1

rows = []
for tag, d in arms.items():
    nn = d['n'] - d['trunc']
    if nn < MIN_N: continue
    p, lo, hi = wilson(d['W'], nn)
    rows.append((p, tag, d, nn, lo, hi))
rows.sort(reverse=True)

print('=' * 118)
print(f'全臂排行 · 四图合计 rot0 · 有效局数 ≥{MIN_N}（伪U 已剔除）')
print('=' * 118)
hdr = f'{"#":<3}{"臂":<12}{"n":>4}{"截断":>5}{"W":>4}{"总胜率":>8}{"95%CI":>16}'
for k in MAPS:
    hdr += f'{k:>13}'
print(hdr)
print('-' * 118)
for i, (p, tag, d, nn, lo, hi) in enumerate(rows, 1):
    line = f'{i:<3}{tag:<12}{d["n"]:>4}{d["trunc"]:>5}{d["W"]:>4}{p*100:>7.1f}%  {lo*100:>5.1f}~{hi*100:<5.1f}  '
    for k in MAPS:
        w, n = d['per'][k]
        line += f'{f"{w}/{n} {w/n*100:.0f}%" if n else "-":>13}'
    print(line)
print('=' * 118)
print('⚠ 跨批不可严格比：不同日期/并行度存在批次效应。四图各图难度不同（map 最难）。')
