# -*- coding: utf-8 -*-
"""农场布局 A/B 对比：基线 vs 新选址。
   · 真实落点 = BUILD-ISSUE 日志经 isFarmAdjacent 同款几何【贪心重建】后的集合
     （BUILD-ISSUE 也包含失败重试位，直接统计会虚增密集度）。
   · 锚点 = TC + 各谷仓(GRANARY)/仓库(STOCK) 的建筑中心（块格）。
"""
import re, os, sys, math, statistics as st

RE = re.compile(r'\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) .* at=\((\d+),(\d+)\)')
TC_BL = (19, 18)                 # map3 + rotate90 固定：96 局反推一致
TC_C = (TC_BL[0] + 1, TC_BL[1] + 1)


def adjacent(a, b):
    """与 UsrAI::isFarmAdjacent 同款：3x3 各外扩 1 格后仍有交集 = 相邻（不可共存）"""
    ax, ay = a; bx, by = b
    sx = (ax - 1 > bx + 2) or (ax + 3 < bx)
    sy = (ay - 1 > by + 2) or (ay + 3 < by)
    return not sx and not sy


def parse(path):
    gran, stock, seq = [], [], []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE.search(line)
        if not m:
            continue
        t = int(m.group(2)); x = int(m.group(4)); y = int(m.group(5)); fr = int(m.group(1))
        if t == 1:
            gran.append((x, y))
        elif t == 3:
            stock.append((x, y))
        elif t == 4:
            seq.append((fr, x, y))
    return gran, stock, seq


def rebuild(seq):
    acc, seen = [], set()
    for fr, x, y in seq:
        if (x, y) in seen:
            continue
        seen.add((x, y))
        if any(adjacent((x, y), a) for a in acc):
            continue
        acc.append((x, y))
    return acc


def group(batch_list):
    rows = []
    for b in batch_list:
        for i in range(1, 9):
            p = '%s%d.ait' % (b, i)
            if not os.path.exists(p):
                continue
            gran, stock, seq = parse(p)
            if not seq:
                continue
            farms = rebuild(seq)
            other = gran + stock
            anchors = [TC_C] + [(x + 1, y + 1) for x, y in other]
            dmin, dtc, near = [], [], 0
            for x, y in farms:
                fc = (x + 1, y + 1)
                dm = min(math.hypot(fc[0] - a[0], fc[1] - a[1]) for a in anchors)
                dt = math.hypot(fc[0] - TC_C[0], fc[1] - TC_C[1])
                dmin.append(dm); dtc.append(dt)
                if other:
                    dg = min(math.hypot(fc[0] - (x2 + 1), fc[1] - (y2 + 1)) for x2, y2 in other)
                    if dg <= 15 and dg < dt:
                        near += 1
            rows.append(dict(nf=len(farms), dmin=dmin, dtc=dtc, near=near, nanc=len(anchors)))
    return rows


def pct(vals, thr):
    return 100.0 * sum(1 for v in vals if v > thr) / max(1, len(vals))


def report(name, rows):
    dmin = [d for r in rows for d in r['dmin']]
    dtc = [d for r in rows for d in r['dtc']]
    near = sum(r['near'] for r in rows)
    nf = sum(r['nf'] for r in rows)
    if not dmin:
        print('%-16s 无数据' % name); print(); return
    ds = sorted(dmin)
    q90 = ds[min(len(ds) - 1, int(len(ds) * 0.9))]
    print('%-16s 局=%-3d 农场=%-5d 农/局=%.1f  锚点/局≈%.1f' %
          (name, len(rows), nf, nf / len(rows),
           sum(r['nanc'] for r in rows) / len(rows)))
    print('   到最近锚点  中位 %5.1f  均值 %5.1f  P90 %5.1f  最大 %5.1f' %
          (st.median(dmin), sum(dmin) / len(dmin), q90, max(dmin)))
    print('   到 TC       中位 %5.1f  均值 %5.1f  最大 %5.1f' %
          (st.median(dtc), sum(dtc) / len(dtc), max(dtc)))
    print('   紧凑度  <=6格 %5.1f%%  <=8格 %5.1f%%   |   外扩  >6格 %5.1f%%  >8格 %5.1f%%  >10格 %5.1f%%' %
          (100 - pct(dmin, 6), 100 - pct(dmin, 8), pct(dmin, 6), pct(dmin, 8), pct(dmin, 10)))
    print('   谷仓/仓库旁(<=15格且近于TC): %d 座 (%.1f%%)' % (near, 100.0 * near / max(1, nf)))
    print()


if __name__ == '__main__':
    ARMS = [('基线(pu+ez+tb)', ['pu', 'ez', 'tb']),
            ('v1 最近锚点评分(fl)', ['fl']),
            ('v2 到TC距离评分(fm)', ['fm']),
            ('v3 R_MAX=18(fn)', ['fn'])]
    print('==== 农场布局 A/B 对比（真实落点 = BUILD-ISSUE 经 isFarmAdjacent 贪心重建）====')
    print()
    for name, bs in ARMS:
        if not any(os.path.exists('%s1.ait' % b) for b in bs):
            print('%-16s (批次不存在，跳过)' % name); print(); continue
        report(name, group(bs))
