# -*- coding: utf-8 -*-
"""各地图胜率统计（复用 _winall.py 的 outcome 口径）。
用法: python _win_current.py [TAG]
  TAG 默认 'current'，扫描 '<TAG>_*_r0_*.ait'
  胜 = ait 含 '被祭司转换,归属阵营1->0'
  祭死 = 'DEFEAT: Priest killed'；TC毁 = 'DEFEAT: Town Center destroyed'；其余 = 超时/未结算
"""
import re, glob, os, collections, math, sys

TAG = sys.argv[1] if len(sys.argv) > 1 else 'current'
MAPS = ['map', 'map1', 'map2', 'map3']
NEED_BEAT = 5  # 空壳 .ait 稀释分母保护


def outcome(t):
    if '被祭司转换,归属阵营1->0' in t:
        return 'W'
    if 'DEFEAT: Priest killed' in t:
        return 'P'
    if 'DEFEAT: Town Center destroyed' in t:
        return 'T'
    return 'U'  # 超时 / 未结算


def wilson(w, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * (c - h), 100 * (c + h))


rows = []
for fn in sorted(glob.glob(f'{TAG}_*_r0_*.ait')):
    t = open(fn, encoding='utf-8', errors='replace').read()
    if t.count('[BEAT') < NEED_BEAT:
        continue
    mp = os.path.basename(fn).replace(TAG + '_', '').split('_r0_')[0]
    rows.append((mp, outcome(t)))

if not rows:
    print(f'未找到 {TAG}_*_r0_*.ait（至少需 {NEED_BEAT} 条 [BEAT]）。')
    sys.exit(0)

print('=' * 96)
print(f'各地图胜率（TAG={TAG}，有效局 {len(rows)}，胜率口径=祭司转换敌攻城武器厂）')
print('=' * 96)
print(f'{"地图":<8}{"局数":>5}{"胜":>4}{"胜率":>9}{"95%CI":>20}{"祭死":>5}{"TC毁":>5}{"超时":>5}')
print('-' * 96)

tot = collections.Counter()
totW = totP = totT = totU = 0
per = collections.Counter()
perW = collections.Counter()
for m in MAPS:
    sub = [(mp, k) for mp, k in rows if mp == m]
    n = len(sub)
    if n == 0:
        print(f'{m:<8}{0:>5}{"-":>4}{"-":>9}{"-":>20}{"-":>5}{"-":>5}{"-":>5}')
        continue
    cnt = collections.Counter(k for _, k in sub)
    w = cnt['W']; p = cnt['P']; tc = cnt['T']; u = cnt['U']
    lo, hi = wilson(w, n)
    print(f'{m:<8}{n:>5}{w:>4}{100*w/n:>8.1f}%{f"[{lo:.0f},{hi:.0f}]":>20}{p:>5}{tc:>5}{u:>5}')
    per[m] = n; perW[m] = w
    totW += w; totP += p; totT += tc; totU += u
    tot[m] += 1

n_all = len(rows)
lo, hi = wilson(totW, n_all)
print('-' * 96)
print(f'{"总体":<8}{n_all:>5}{totW:>4}{100*totW/n_all:>8.1f}%{f"[{lo:.0f},{hi:.0f}]":>20}{totP:>5}{totT:>5}{totU:>5}')
print('=' * 96)

# 各图胜率排名（按胜率降序）
print('分图胜率（降序）:')
ranked = sorted(MAPS, key=lambda m: (perW[m] / per[m]) if per[m] else -1, reverse=True)
for m in ranked:
    if per[m]:
        print(f'  {m:<8} {perW[m]:>2}/{per[m]:<3} = {100*perW[m]/per[m]:.1f}%')
print('=' * 96)
