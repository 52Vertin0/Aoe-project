# -*- coding: utf-8 -*-
"""农场布局精查：
   ① 用 isFarmAdjacent 同款几何约束做贪心重建，还原【真实建成】的农场集合（去掉失败重试位）；
   ② 打印每局谷仓坐标 + 谷仓到 TC 距离；
   ③ 统计农场到 TC / 到谷仓 / 到最近锚点 的距离分布，并给出「谷仓旁可容纳但未使用」的量化。
"""
import re, os, sys, math, statistics as st

# 用法：python farm_layout_probe2.py [批次前缀...]   例：python farm_layout_probe2.py fl
#       不带参数 = 全部历史批次
BATCHES = sys.argv[1:] if len(sys.argv) > 1 else \
    ['pu', 'ez', 'tb', 'tl', 'tm', 'tn', 'lc', 'll', 'lm', 'ln', 'lj', 'pg']
RE = re.compile(r'\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) .* at=\((\d+),(\d+)\)')


def adjacent(a, b):
    """a=(x,y) b=(x,y) 均为 3x3 左下角；返回 True = 相邻(不可共存)，与 isFarmAdjacent 同款"""
    ax, ay = a; bx, by = b
    separatedX = (ax - 1 > bx + 2) or (ax + 3 < bx)
    separatedY = (ay - 1 > by + 2) or (ay + 3 < by)
    return not separatedX and not separatedY


def parse(path):
    gran, seq = [], []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE.search(line)
        if not m:
            continue
        t = int(m.group(2)); x = int(m.group(4)); y = int(m.group(5)); fr = int(m.group(1))
        if t == 1:
            gran.append((x, y))
        elif t == 4:
            seq.append((fr, x, y))
    return gran, seq


def rebuild(seq):
    """按时间贪心：与已接受集合冲突(相邻/重叠)的候选视为未建成，丢弃。
       同一位置重复出现(失败重试)算一次。"""
    accepted = []
    seen = set()
    for fr, x, y in seq:
        if (x, y) in seen:
            continue
        if any(adjacent((x, y), a) for a in accepted):
            seen.add((x, y))
            continue
        accepted.append((x, y))
        seen.add((x, y))
    return accepted


def main():
    tot = dict(farm=0, dtc=[], dgr=[], dmin=[], ngr=[], gdtc=[], over6=0, over10=0)
    rows = []
    for b in BATCHES:
        for i in range(1, 9):
            p = '%s%d.ait' % (b, i)
            if not os.path.exists(p):
                continue
            gran, seq = parse(p)
            if not seq:
                continue
            fa = rebuild(seq)
            cx, cy = 19, 18                      # map3 固定 TC 左下角（96 局推断一致）
            tcc = (cx + 1, cy + 1)
            gcen = [(gx + 1, gy + 1) for gx, gy in gran]
            anchors = [tcc] + gcen
            dtc, dgr, dmin = [], [], []
            for x, y in fa:
                fc = (x + 1, y + 1)
                d1 = math.hypot(fc[0] - tcc[0], fc[1] - tcc[1])
                dtc.append(d1)
                if gcen:
                    d2 = min(math.hypot(fc[0] - g[0], fc[1] - g[1]) for g in gcen)
                    dgr.append(d2)
                dm = min(math.hypot(fc[0] - a[0], fc[1] - a[1]) for a in anchors)
                dmin.append(dm)
                tot['farm'] += 1
                if dm > 6: tot['over6'] += 1
                if dm > 10: tot['over10'] += 1
            tot['dtc'] += dtc; tot['dgr'] += dgr; tot['dmin'] += dmin
            tot['ngr'].append(len(gran))
            for g in gcen:
                tot['gdtc'].append(math.hypot(g[0] - tcc[0], g[1] - tcc[1]))
            rows.append(dict(g=p, n=len(fa), ng=len(gran), gran=gran,
                             dtc=st.median(dtc) if dtc else 0,
                             dmin=st.median(dmin) if dmin else 0,
                             mx=max(dmin) if dmin else 0))
    print('======== 真实农场（贪心重建，已剔除失败重试位） ========')
    print('局数 %d   农场总数 %d' % (len(rows), tot['farm']))
    print('谷仓/局: 均值 %.2f   谷仓到TC距离 中位 %.1f  最大 %.1f' %
          (sum(tot['ngr']) / max(1, len(tot['ngr'])),
           st.median(tot['gdtc']) if tot['gdtc'] else -1,
           max(tot['gdtc']) if tot['gdtc'] else -1))
    print()
    f = tot
    print('农场→TC      中位 %.1f  均值 %.1f  最大 %.1f' %
          (st.median(f['dtc']), sum(f['dtc']) / len(f['dtc']), max(f['dtc'])))
    if f['dgr']:
        print('农场→最近谷仓 中位 %.1f  均值 %.1f  最小 %.1f  (仅 %d 座有谷仓可算)' %
              (st.median(f['dgr']), sum(f['dgr']) / len(f['dgr']), min(f['dgr']), len(f['dgr'])))
    print('农场→最近锚点 中位 %.1f  均值 %.1f  最大 %.1f' %
          (st.median(f['dmin']), sum(f['dmin']) / len(f['dmin']), max(f['dmin'])))
    print('  >6 格: %d (%.1f%%)   >10 格: %d (%.1f%%)' %
          (f['over6'], 100.0 * f['over6'] / f['farm'], f['over10'], 100.0 * f['over10'] / f['farm']))
    # 关键量化：农场离 TC 比离谷仓更近的有多少 / 谷仓旁(<=8格)一座都没有的局数
    if f['dgr']:
        closer_gran = sum(1 for a, b in zip(f['dtc'], f['dgr']) if b < a)
        print('  「离谷仓更近」的农场: %d (%.1f%%)  ← 用于衡量"谷仓周围"被利用的程度'
              % (closer_gran, 100.0 * closer_gran / len(f['dtc'])))
    print()
    print('%-8s %-6s %-5s %-14s %-9s %-9s %-7s' %
          ('局', '农场', '谷仓', '谷仓坐标', '→TC中位', '→锚中位', '最远'))
    for r in rows:
        print('%-8s %-6d %-5d %-14s %-9.1f %-9.1f %-7.1f' %
              (r['g'], r['n'], r['ng'], str(r['gran'][:1]), r['dtc'], r['dmin'], r['mx']))


if __name__ == '__main__':
    main()
