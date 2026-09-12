# -*- coding: utf-8 -*-
"""农场布局探针：从 ait 日志的 [BUILD-ISSUE] 里挖出所有 type=1(谷仓)/type=4(农场) 的落点，
   反推 TC 坐标，量化每个农场到"最近锚点(TC 或谷仓)"的距离分布。"""
import re, os, sys, math, statistics as st

BATCHES = ['pu', 'ez', 'tb', 'tl', 'tm', 'tn', 'lc', 'll', 'lm', 'ln', 'lj', 'pg']
RE = re.compile(r'\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) .* at=\((\d+),(\d+)\)')


def parse(path):
    """返回 (TC候选计数, 谷仓列表, 农场列表[(f,x,y)])"""
    gran, farms, tcs = [], [], []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE.search(line)
        if not m:
            continue
        t = int(m.group(2)); x = int(m.group(4)); y = int(m.group(5)); fr = int(m.group(1))
        if t == 1:
            gran.append((x, y))
        elif t == 4:
            farms.append((fr, x, y))
        elif t == 2:
            tcs.append((x, y))
    return tcs, gran, farms


def infer_tc(farms):
    """由农场落点反推 TC 左下角：农场环几何决定 cx±4 / cy±4 是最内圈。
       稳健做法：找出现频率最高的 (x mod 4) 与 (y mod 4) 并取众数组合上的最小值。"""
    if not farms:
        return None
    # 内圈(r=4)：y = cy+4 或 cy-4；x = cx+4 或 cx-4
    # 取所有农场 y 值，最小 y 与最大 y 的差应为 2r 的倍数；用众数法：
    ys = sorted(set(y for _, _, y in farms))
    xs = sorted(set(x for _, _, x in farms))
    # cy 使 min(|y-(cy±4)|) 最小 -> 枚举候选 cy 在 [miny-10, maxy+10]
    best, bestCost = None, 1e18
    for cy in range(min(ys) - 12, max(ys) + 13):
        for cx in range(min(xs) - 12, max(xs) + 13):
            cost = 0.0
            for _, x, y in farms:
                # 农场必在 TC 环上：min over {cx±r, cy±r} 的一致性
                d1 = min(abs(x - (cx + 4)), abs(x - (cx - 4)))
                d2 = min(abs(y - (cy + 4)), abs(y - (cy - 4)))
                cost += min(d1, d2)          # 至少一个维度贴 r=4 环
            if cost < bestCost:
                bestCost, best = cost, (cx, cy)
    return best


def main():
    rows = []
    for b in BATCHES:
        for i in range(1, 9):
            p = '%s%d.ait' % (b, i)
            if not os.path.exists(p):
                continue
            tcs, gran, farms = parse(p)
            if not farms:
                continue
            tc = infer_tc(farms)
            if not tc:
                continue
            cx, cy = tc
            # 锚点集合 = TC 中心 + 各谷仓中心（用中心坐标，块格）
            anchors = [(cx + 1, cy + 1)]
            for gx, gy in gran:
                anchors.append((gx + 1, gy + 1))
            ds, d_tc, d_gr = [], [], []
            for fr, x, y in farms:
                fxc, fyc = x + 1, y + 1
                dt = math.hypot(fxc - (cx + 1), fyc - (cy + 1))
                d_tc.append(dt)
                if gran:
                    dg = min(math.hypot(fxc - (gx + 1), fyc - (gy + 1)) for gx, gy in gran)
                    d_gr.append(dg)
                dmin = min(math.hypot(fxc - ax, fyc - ay) for ax, ay in anchors)
                ds.append(dmin)
            rows.append(dict(g=p, tc=(cx, cy), n=len(farms), ng=len(gran),
                             dmin=ds, dtc=d_tc, dgr=d_gr,
                             farms=[(x, y) for _, x, y in farms]))
    if not rows:
        print('no data'); return
    # 汇总
    allmin = [d for r in rows for d in r['dmin']]
    alltc = [d for r in rows for d in r['dtc']]
    print('== 全部 %d 局、%d 座农场 ==' % (len(rows), len(allmin)))
    print('  到最近锚点(TC或谷仓) 距离(格): 中位 %.1f  均值 %.1f  最大 %.1f' %
          (st.median(allmin), sum(allmin) / len(allmin), max(allmin)))
    print('  到 TC 距离(格):            中位 %.1f  均值 %.1f  最大 %.1f' %
          (st.median(alltc), sum(alltc) / len(alltc), max(alltc)))
    for thr in (6, 10, 14, 20, 30):
        k = sum(1 for d in allmin if d > thr)
        print('   > %2d 格的农场: %3d 座 (%.1f%%)' % (thr, k, 100.0 * k / len(allmin)))
    print()
    print('%-8s %-9s %-5s %-5s %-8s %-8s %-8s %s' %
          ('局', 'TC(推)', '农场', '谷仓', '锚点中位', 'TC中位', '最远', '超14格'))
    for r in rows:
        over = sum(1 for d in r['dmin'] if d > 14)
        print('%-8s (%2d,%2d)  %-5d %-5d %-8.1f %-8.1f %-8.1f %d' %
              (r['g'], r['tc'][0], r['tc'][1], r['n'], r['ng'],
               st.median(r['dmin']), st.median(r['dtc']), max(r['dmin']), over))
    # 打印一局的落点散点（ASCII）
    r = rows[0]
    print()
    print('== 示例局 %s 落点图（# 农场  T=TC  G=谷仓  . 空）==' % r['g'])
    xs = [x for x, y in r['farms']] + [r['tc'][0]]
    ys = [y for x, y in r['farms']] + [r['tc'][1]]
    x0, x1 = min(xs) - 2, max(xs) + 5
    y0, y1 = min(ys) - 2, max(ys) + 5
    for y in range(y1, y0 - 1, -1):
        line = ''
        for x in range(x0, x1):
            ch = '.'
            if r['tc'][0] <= x <= r['tc'][0] + 2 and r['tc'][1] <= y <= r['tc'][1] + 2:
                ch = 'T'
            for fx, fy in r['farms']:
                if fx <= x <= fx + 2 and fy <= y <= fy + 2:
                    ch = '#'
            line += ch
        print('  %s y=%2d' % (line, y))
    print('  ' + ''.join(str(x // 10 % 10) for x in range(x0, x1)) + '  x十位')
    print('  ' + ''.join(str(x % 10) for x in range(x0, x1)) + '  x个位')


if __name__ == '__main__':
    main()
