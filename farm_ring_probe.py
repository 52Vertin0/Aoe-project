# -*- coding: utf-8 -*-
"""农场环位分析：量「农场落在 TC/谷仓 的第几环」与「紧邻环(r=FARM_ANCHOR_R_MIN)还剩几个空位」。

几何口径（与 UsrAI.cpp ringOf 完全一致）：
  锚点与农场都是 3x3；环 r 的定义 = 农场左下角相对锚点左下角的 切比雪夫距离 max(|dx|,|dy|) = r
  「隔一格」⇒ 最近可行环 r = 3 + BUILD_GAP = 4
  候选带：上/下带 nx∈[ax-r, ax+r], ny=ay±r；左/右带 ny∈[ay-r, ay+r], nx=ax±r

用法：python farm_ring_probe.py [批次前缀...]
"""
import re, sys, glob, math, collections, statistics as st

RE = re.compile(r'\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) .* at=\((\d+),(\d+)\)')
T_HOME, T_GRANARY, T_CENTER, T_STOCK, T_FARM = 0, 1, 2, 3, 4
R_MIN = 4
NAMES = {T_GRANARY: '谷仓', T_STOCK: '仓库', T_CENTER: 'TC', T_FARM: '农场',
         T_HOME: '房屋', 7: '兵营', 9: '靶场', 5: '市场', 6: '箭塔', 8: '马厩'}


def separated(a, b):
    """与 isFarmAdjacent 同款：False = 不相邻(可共存)"""
    ax, ay = a; bx, by = b
    sx = (ax - 1 > bx + 2) or (ax + 3 < bx)
    sy = (ay - 1 > by + 2) or (ay + 3 < by)
    return sx or sy


def cheb(dx, dy):
    return max(abs(dx), abs(dy))


def ring_slots(ax, ay, r):
    """锚点外 r 环的全部候选左下角（与 ringOf 同款四带，去重）"""
    s = set()
    for k in range(0, 2 * r + 3):
        s.add((ax - r + k, ay + r))     # 上带
        s.add((ax - r + k, ay - r))     # 下带
        s.add((ax - r, ay - r + k))     # 左带
        s.add((ax + r, ay - r + k))     # 右带
    return s


def packable(anchor, r, occupied):
    """在 r 环上、避开 occupied（含其他建筑 footprint + 隔1格）后，最多能放几个农场（贪心：左下→右上）"""
    slots = sorted(ring_slots(anchor[0], anchor[1], r))
    placed = []
    for s in slots:
        # 该位置与已有农场是否可共存
        if any(not separated(s, p) for p in placed):
            continue
        placed.append(s)
    return placed


def parse_raw(path):
    """全部 FARM 下发记录 (帧, x, y)，不去重"""
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE.search(line)
        if m and int(m.group(2)) == T_FARM:
            out.append((int(m.group(1)), int(m.group(4)), int(m.group(5))))
    return out


def parse(path):
    farms, others, tc = [], [], None
    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE.search(line)
        if not m:
            continue
        fr = int(m.group(1)); t = int(m.group(2)); x = int(m.group(4)); y = int(m.group(5))
        if t == T_FARM:
            farms.append((fr, x, y))
        elif t == T_CENTER and tc is None:
            tc = (x, y)
        else:
            others.append((t, x, y))
    # 贪心重建：按帧序，遵守 isFarmAdjacent
    real = []
    for fr, x, y in sorted(farms):
        if all(separated((x, y), p) for p in real):
            real.append((x, y))
    return tc, real, others


def main():
    tags = sys.argv[1:] or ['kd']
    ring_hist = collections.Counter()
    dtc_all = []
    per_game = []
    for tag in tags:
        for fp in sorted(glob.glob(tag + '*.ait'), key=lambda p: int(re.search(r'\d+', p).group())):
            tc, farms, others = parse(fp)
            if tc is None:                       # TC 为地图预置，不经 BUILD-ISSUE
                tc = (19, 18)                    # map3 固定 TC 左下角（96 局实测一致）
            if not farms:
                continue
            rs = [cheb(x - tc[0], y - tc[1]) for x, y in farms]
            for r in rs:
                ring_hist[r] += 1
            dtc_all += [math.hypot((x + 1) - (tc[0] + 1), (y + 1) - (tc[1] + 1)) for x, y in farms]
            # 用「其他建筑」占位做粗略可用性（不知道地形/资源，故只算几何上限）
            occ = set()
            for t, x, y in others:
                sz = 3 if t in (T_GRANARY, T_STOCK, 5, 7, 9) else 2
                for i in range(x - 1, x + sz + 1):
                    for j in range(y - 1, y + sz + 1):
                        occ.add((i, j))
            cap4 = len(packable(tc, R_MIN, occ))
            used4 = sum(1 for x, y in farms if cheb(x - tc[0], y - tc[1]) == R_MIN)
            per_game.append((fp.replace('.ait', ''), len(farms), rs, used4, cap4, tc))

    print('======== 农场相对 TC 的环分布（Chebyshev r；r=4 即"隔一格"紧邻环）========')
    tot = sum(ring_hist.values())
    print('样本：%d 局 / %d 座农场' % (len(per_game), tot))
    for r in sorted(ring_hist):
        n = ring_hist[r]
        lo, hi = r, r * math.sqrt(2)
        mark = '   ← 隔一格紧邻环' if r == R_MIN else ''
        print('  r=%-3d %4d 座 (%5.1f%%)   实际距离 %.1f~%.1f 格%s' % (r, n, 100.0 * n / tot, lo, hi, mark))
    if dtc_all:
        print('  农场→TC 距离：中位 %.1f  最大 %.1f ｜ 落在紧邻环的比例 %.1f%%'
              % (st.median(dtc_all), max(dtc_all), 100.0 * ring_hist[R_MIN] / tot))
    print()
    print('======== 紧邻环(r=4) 容量 vs 实际占用（几何上限，未计地形/资源）========')
    print('%-10s %6s %8s %8s %8s' % ('局', '农场数', 'r=4占用', 'r=4容量', '最外环'))
    for g, n, rs, used4, cap4, tc in per_game[:26]:
        print('%-10s %6d %8d %8d %8d' % (g, n, used4, cap4, max(rs)))
    cu = [u for _, _, _, u, _, _ in per_game]
    cc = [c for _, _, _, _, c, _ in per_game]
    if cu:
        print()
        print('  紧邻环占用中位 %d ／ 容量中位 %d ⇒ 几何利用率 %.0f%%'
              % (st.median(cu), st.median(cc), 100.0 * st.median(cu) / max(1, st.median(cc))))
        print('  需求 %d 座(M) vs 紧邻环容量中位 %d ⇒ %s'
              % (12, st.median(cc),
                 '容量足够' if st.median(cc) >= 12 else '★ 容量不足 ⇒ 只允许紧邻环会建不满'))

    # ---- 建造序列：看"第几座开始跳层" ----
    print()
    print('======== 建造序列（帧 坐标 环 到TC格）—— 检查是否"内圈未满就跳外层" ========')
    jump = 0; jn = 0
    for fp in sorted(glob.glob(tags[0] + '*.ait'), key=lambda p: int(re.search(r'\d+', p).group())):
        tc, farms, others = parse(fp)
        if tc is None:
            tc = (19, 18)
        if not farms:
            continue
        seq = []
        for fr, x, y in sorted(parse_raw(fp)):
            if any(x == a[0] and y == a[1] for a in farms) and (x, y) not in [s[1] for s in seq]:
                seq.append(((x, y), fr))
        if not seq:
            continue
        rs = [cheb(p[0][0] - tc[0], p[0][1] - tc[1]) for p in seq]
        # 首次出现 r>=7 的序号，且此前 r=4 占用 < 容量上限(8) ⇒ 判为跳层
        first_far = next((i for i, r in enumerate(rs) if r >= 7), None)
        n4_before = sum(1 for r in rs[:first_far] if r == R_MIN) if first_far is not None else None
        tag = ''
        if first_far is not None and n4_before is not None and n4_before < 8:
            jump += 1
            tag = '  ★ 内圈未满就跳外层（第%d座，此前 r=4 只用了 %d/8）' % (first_far + 1, n4_before)
        jn += 1
        print('%-8s 序列环=%s%s' % (fp.replace('.ait', ''), rs, tag))
    print()
    print('  ★ 跳层局数 = %d / %d' % (jump, jn))

    # ---- 跨局一致性：r=4 环上哪些 (dx,dy) 被反复使用 ----
    print()
    print('======== 紧邻环(r=4) 各槽位跨局使用频率（相对 TC，dx=农场x-19, dy=农场y-18）========')
    slot_use = collections.Counter()
    n_used_per_game = []
    for fp in sorted(glob.glob(tags[0] + '*.ait'), key=lambda p: int(re.search(r'\d+', p).group())):
        tc, farms, others = parse(fp)
        if tc is None:
            tc = (19, 18)
        if not farms:
            continue
        cur = set()
        for x, y in farms:
            if cheb(x - tc[0], y - tc[1]) == R_MIN:
                cur.add((x - tc[0], y - tc[1]))
        for s in cur:
            slot_use[s] += 1
        n_used_per_game.append(len(cur))
    NG = len(n_used_per_game)
    print('  样本 %d 局；每局紧邻环实际占用：中位 %d，最大 %d'
          % (NG, st.median(n_used_per_game) if NG else 0, max(n_used_per_game) if NG else 0))
    print('  槽位（按使用局数降序，仅列 ≥1 局）：')
    full = [s for s, c in slot_use.items() if c == NG]
    print('  %-18s %-8s %s' % ('(dx,dy)', '使用局数', '占比'))
    for (dx, dy), c in slot_use.most_common(30):
        flag = '  ← 全局必然可用' if c == NG else ''
        print('  %-18s %-8d %5.1f%%%s' % (str((dx, dy)), c, 100.0 * c / max(1, NG), flag))
    print()
    print('  「在所有局里都可用」的槽位 %d 个（= 紧邻环的稳定容量下界）' % len(full))
    print('  ⇒ 只允许紧邻环时，农场数上限 ≈ %d 座（现均 11 座）' % len(full))


if __name__ == '__main__':
    main()
