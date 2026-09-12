# -*- coding: utf-8 -*-
"""
祭司感化「投石车」机会量测  (2026-09-20)

回答：感化投石车少，是因为【档位压制（投石车在 28 格内却被别的目标挤掉）】
      还是因为【机会本来就少（投石车不在附近 / 祭司已死）】？

方法：坐标全部来自引擎移动令 `HumanMove:<兵种> <SN> 移动至 (x,y)`（不受采样影响），
      取"查询帧之前最近一次"的落点当该单位位置，超过 STALE 帧则判为未知（避免用陈旧坐标冒充）。

用法： python priest_stone_opp_probe.py [前缀...]
"""
import re, glob, sys, collections

BL = 35.777
STALE = 2400         # 帧：位置样本超过此值则视为未知（96 秒；投石车多为静止单位，放宽以免漏判）
R_SEE = 28.0         # 感化发现半径（格）PRIEST_CONVERT_RANGE
R_FIRE = 12.0        # 点火半径（格）

RE_CONV = re.compile(r'HumanAction:祭司\s+(\d+)\s+设置转换目标为\s+(\S+)\s+(\d+)')
RE_MOVE = re.compile(r'HumanMove:(\S+)\s+(\d+)\s+移动至\s+\(([\d.]+),([\d.]+)\)')
RE_SPAWN = re.compile(r'产生了新的(\S+)\(编号:?(\d+)\)')
RE_DEATH = re.compile(r'(\S+)\(编号:?(\d+)\)死亡')


def last_pos(track, fr, stale=STALE):
    """track = [(frame,x,y)] 升序；返回查询帧之前最近一次落点，过旧返回 None"""
    lo, hi, best = 0, len(track) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if track[mid][0] <= fr:
            best = track[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    if best is None or fr - best[0] > stale:
        return None
    return best


def main():
    pats = sys.argv[1:] or ['']
    files = sorted({f for p in pats for f in glob.glob(p + '*.ait')})
    games = 0
    ord_total = collections.Counter()          # 目标类型 -> 条数
    ord_stone_near = collections.Counter()     # 目标类型 -> 该令下发时"有投石车在 28 格内"的条数
    ord_stone_fire = collections.Counter()     # 同上但 12 格内
    dist_hist = collections.Counter()          # 投石车最近距离分桶（仅非投石车令）
    opp_frames = 0                             # 有投石车 ≤28 格的（祭司存活）帧数
    opp_games = 0                              # 至少有一帧机会的局数
    priest_dead_before_wave3 = 0
    games_no_opp = 0
    selfcheck = [0, 0]                         # [到位数, 可比数] —— 位置重建自检
    for f in files:
        priest_sn, conv = None, []
        moves = collections.defaultdict(list)
        stone = {}
        dead = {}
        last = 0
        for ln in open(f, encoding='utf-8', errors='replace'):
            p = ln.split(' | ', 3)
            if len(p) < 4:
                continue
            try:
                fr = int(p[1])
            except ValueError:
                continue
            last = max(last, fr)
            h = p[3].split(' | ', 1)
            fl = h[0].strip()
            m = h[1].strip() if len(h) > 1 else ''
            mc = RE_CONV.match(m)
            if mc:
                priest_sn = int(mc.group(1))
                conv.append((fr, mc.group(2), int(mc.group(3))))
                continue
            mm = RE_MOVE.match(m)
            if mm:
                moves[int(mm.group(2))].append(
                    (fr, float(mm.group(3)) / BL, float(mm.group(4)) / BL))
                continue
            ms = RE_SPAWN.search(m)
            if ms:
                sn, nm = int(ms.group(2)), ms.group(1)
                if nm == '投石车' and fl == '1' and sn not in stone:
                    stone[sn] = True
                continue
            md = RE_DEATH.match(m)
            if md:
                dead.setdefault(int(md.group(2)), fr)
        if priest_sn is None:
            continue
        games += 1
        for sn in list(moves):
            moves[sn].sort()
        ptrack = moves.get(priest_sn, [])
        if not ptrack:
            games_no_opp += 1
            continue
        if priest_sn in dead and dead[priest_sn] < 21001:
            priest_dead_before_wave3 += 1

        stone_sns = [s for s in stone if moves.get(s)]
        if not stone_sns:
            games_no_opp += 1
        got_opp = False
        target_ok = target_all = 0
        for fr, name, tsn in conv:
            ord_total[name] += 1
            pp = last_pos(ptrack, fr)
            if pp is None:
                continue
            # 自检：对"感化投石车"的令，算到【目标自己】的距离（构造上必 ≤12 格）
            if name == '投石车' and moves.get(tsn):
                tp = last_pos(moves[tsn], fr)
                if tp is not None:
                    target_all += 1
                    d = ((tp[1] - pp[1]) ** 2 + (tp[2] - pp[2]) ** 2) ** 0.5
                    if d <= R_FIRE + 2:
                        target_ok += 1
            best = 1e9
            for s in stone_sns:
                if dead.get(s, 1 << 60) <= fr:
                    continue
                sp = last_pos(moves[s], fr)
                if sp is None:
                    continue
                d = ((sp[1] - pp[1]) ** 2 + (sp[2] - pp[2]) ** 2) ** 0.5
                best = min(best, d)
            if best < 1e8:
                if name != '投石车':
                    if best <= R_SEE:
                        dist_hist['<=28'] += 1
                    elif best <= 45:
                        dist_hist['28~45'] += 1
                    else:
                        dist_hist['>45'] += 1
                if best <= R_SEE:
                    ord_stone_near[name] += 1
                    got_opp = True
                if best <= R_FIRE:
                    ord_stone_fire[name] += 1
        selfcheck[0] += target_ok
        selfcheck[1] += target_all
        # 机会帧总量（每 100 帧采样一次，省时）
        for fr in range(0, last + 1, 100):
            pp = last_pos(ptrack, fr)
            if pp is None:
                continue
            for s in stone_sns:
                if dead.get(s, 1 << 60) <= fr:
                    continue
                sp = last_pos(moves[s], fr)
                if sp is None:
                    continue
                if ((sp[1] - pp[1]) ** 2 + (sp[2] - pp[2]) ** 2) ** 0.5 <= R_SEE:
                    opp_frames += 1
                    break
        if got_opp:
            opp_games += 1
    print('局数 %d ｜ 无机会局 %d ｜ 祭司在波3前即阵亡的局 %d' %
          (games, games_no_opp, priest_dead_before_wave3))
    print('有"投石车≤28格"机会的局数 %d ｜ 机会帧（每百帧采样累计）%d' % (opp_games, opp_frames))
    print()
    print('%-10s %6s %8s %8s' % ('目标类型', '令数', '同帧28内有石', '12内'))
    for k, v in ord_total.most_common():
        print('%-10s %6d %8d %8d' % (k, v, ord_stone_near[k], ord_stone_fire[k]))
    print()
    print('非投石车令在当前时刻「到最近投石车」的距离分布：', dict(dist_hist))
    if selfcheck[1]:
        print('★ 位置重建自检：感化投石车的令中，重建距离 ≤14 格的比例 = %d/%d = %.1f%%'
              % (selfcheck[0], selfcheck[1], 100.0 * selfcheck[0] / selfcheck[1]))


if __name__ == '__main__':
    main()
