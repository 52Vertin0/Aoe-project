# -*- coding: utf-8 -*-
"""找出各局 type=3(仓库/STOCK) 与 type=1(谷仓/GRANARY) 的落点，并算它们到 TC 的距离。"""
import re, os, math, statistics as st

BATCHES = ['pu', 'ez', 'tb', 'tl', 'tm', 'tn', 'lc', 'll', 'lm', 'ln', 'lj', 'pg']
RE = re.compile(r'\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) .* at=\((\d+),(\d+)\)')
TC = (20, 19)          # TC 中心（左下角 19,18 → 中心 +1）

NAMES = {0: 'HOME', 1: 'GRANARY', 2: 'CENTER', 3: 'STOCK', 4: 'FARM', 5: 'MARKET',
         6: 'ARROWTOWER', 7: 'ARMYCAMP', 8: 'STABLE', 9: 'RANGE', 10: 'DOCK',
         11: 'SIEGE', 12: 'COLLAGE', 13: 'TEMPLE', 14: 'WALL'}

cnt = {}
rows = []
for b in BATCHES:
    for i in range(1, 9):
        p = '%s%d.ait' % (b, i)
        if not os.path.exists(p):
            continue
        per = {}
        for line in open(p, encoding='utf-8', errors='replace'):
            m = RE.search(line)
            if not m:
                continue
            t = int(m.group(2)); x = int(m.group(4)); y = int(m.group(5)); fr = int(m.group(1))
            per.setdefault(t, []).append((fr, x, y))
            cnt[t] = cnt.get(t, 0) + 1
        st3 = [(x, y) for _, x, y in per.get(3, [])]
        g1 = [(x, y) for _, x, y in per.get(1, [])]
        d3 = [math.hypot(x + 1 - TC[0], y + 1 - TC[1]) for x, y in st3]
        d1 = [math.hypot(x + 1 - TC[0], y + 1 - TC[1]) for x, y in g1]
        rows.append((p, st3[:3], min(d3) if d3 else -1, g1[:2], min(d1) if d1 else -1))

print('== 各建筑类型的 BUILD-ISSUE 次数（96 局累计）==')
for t in sorted(cnt):
    print('   type=%-3d %-12s %d' % (t, NAMES.get(t, '?'), cnt[t]))
print()
print('%-9s %-26s %-8s %-22s %-8s' % ('局', '仓库STOCK(前3)', '最近仓库', '谷仓GRANARY(前2)', '最近谷仓'))
for p, s3, m3, g1, m1 in rows[:24]:
    print('%-9s %-26s %-8.1f %-22s %-8.1f' % (p, str(s3), m3, str(g1), m1))
d3a = [r[2] for r in rows if r[2] >= 0]
d1a = [r[4] for r in rows if r[4] >= 0]
print()
if d3a:
    print('仓库→TC 距离: 中位 %.1f  最小 %.1f  最大 %.1f  (有仓库的局 %d/%d)' %
          (st.median(d3a), min(d3a), max(d3a), len(d3a), len(rows)))
if d1a:
    print('谷仓→TC 距离: 中位 %.1f  最小 %.1f  最大 %.1f  (有谷仓的局 %d/%d)' %
          (st.median(d1a), min(d1a), max(d1a), len(d1a), len(rows)))
