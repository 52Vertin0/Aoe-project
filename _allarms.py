# -*- coding: utf-8 -*-
"""全臂排行（map 单图 rot0）：统一 outcome 口径 + 伪U 过滤 + Wilson CI。
用法: python _allarms.py [MIN_N]
"""
import glob, re, math, os, statistics, sys

MIN_N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
FR = re.compile(r'^\d\d:\d\d:\d\d+\s*\|\s*(\d+)\s*\|')

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
for fn in glob.glob('*_map_r0_*.ait'):
    tag = fn.split('_map_r0_')[0]
    s = open(fn, encoding='utf-8', errors='replace').read()
    fr = [int(x.group(1)) for x in (FR.match(l) for l in s.splitlines()) if x]
    mx = max(fr) if fr else 0
    r = outcome(s)
    trunc = (r == 'U' and mx < 44000)
    d = arms.setdefault(tag, dict(W=0, P=0, T=0, U=0, n=0, trunc=0))
    d['n'] += 1; d[r] += 1
    if trunc: d['trunc'] += 1

rows = []
for tag, d in arms.items():
    nn = d['n'] - d['trunc']
    if nn < MIN_N: continue
    p, lo, hi = wilson(d['W'], nn)
    rows.append((p, tag, d, nn, lo, hi))
rows.sort(reverse=True)

print('=' * 106)
print(f'全臂排行 · map 单图 rot0 · 有效局数 ≥{MIN_N}（伪U 已剔除）')
print('=' * 106)
print(f'{"#":<3}{"臂":<13}{"n":>4}{"截断":>5}{"W":>4}{"P":>4}{"T":>4}{"U":>4}{"胜率":>8}{"95%CI":>17}{"祭死率":>8}')
print('-' * 106)
for i, (p, tag, d, nn, lo, hi) in enumerate(rows, 1):
    print(f'{i:<3}{tag:<13}{d["n"]:>4}{d["trunc"]:>5}{d["W"]:>4}{d["P"]:>4}{d["T"]:>4}{d["U"]:>4}'
          f'{p*100:>7.1f}%  {lo*100:>5.1f}~{hi*100:<5.1f}   {d["P"]/nn*100 if nn else 0:>6.1f}%')
print('=' * 106)
print(f'⚠ 跨批不严格可比：不同日期/并行度的臂存在批次效应；n=48 带 ±14pp、n=24 带 ±14~20pp。')
