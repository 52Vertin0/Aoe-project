# -*- coding: utf-8 -*-
"""回退漂移诊断：比较各批次移动令落点"离地图原点(左下=我方基地方向)的平均半径"随时间的走势。
若晚段半径显著小于中段 ⇒ 部队在往回缩（退回 TC）。"""
import re, os, sys

RE = re.compile(r'HumanMove[:：]\s*(\S+)\s+(\d+)\s+移动至\s*\(([\d.]+),([\d.]+)\)')


def series(p):
    pts = []
    for line in open(p, encoding='utf-8', errors='replace'):
        t = line.rstrip('\n').split('|')
        if len(t) < 5 or not t[1].strip().isdigit():
            continue
        m = RE.search(t[4])
        if m:
            pts.append((int(t[1]), float(m.group(3)), float(m.group(4))))
    return pts


def seg(pts):
    n = len(pts)
    if n < 30:
        return None
    out = []
    for k in range(3):
        s = pts[k * n // 3:(k + 1) * n // 3]
        r = sum((x * x + y * y) ** .5 for _, x, y in s) / len(s)
        out.append(r)
    return out


print('%-6s %8s %8s %8s   %s' % ('局', '早段R', '中段R', '晚段R', '走势'))
for b in (sys.argv[1:] or ['dm', 'sba', 'sb']):
    print('--- %s' % b)
    for i in range(1, 9):
        p = '%s%d.ait' % (b, i)
        if not os.path.exists(p) or os.path.getsize(p) < 10000:
            continue
        s = seg(series(p))
        if not s:
            print('%-6s (移动令过少)' % p); continue
        trend = '回退' if s[2] < s[1] * 0.9 else ('推进' if s[2] > s[1] * 1.1 else '持平')
        print('%-6s %8.0f %8.0f %8.0f   %s' % (p, s[0], s[1], s[2], trend))
