# -*- coding: utf-8 -*-
"""_priest_land.py —— 反攻期祭司「令下发后有没有真的走过去」

判据（[BEAT] 桶级）：
  pr@  = 祭司实际块坐标；last=(x,y) = 祭司最近一次移动令的落点（g_pmLast*，单位 0.1 块）
  ① gap = 桶内 |pr@ - last|   —— 持续很大 ⇒ 令发了但走不到（被引擎拒 / 被别的令覆盖）
  ② step = 相邻桶 pr@ 位移     —— 持续 ≈0 ⇒ 站桩
用法： python _priest_land.py <TAG> [TAG2 ...]
"""
import glob
import os
import re
import statistics as st
import sys

POP = re.compile(r'POP-FULL COUNTERATTACK! Frame=(\d+)')
CA = re.compile(r'ALL WAVES DEFEATED! Counterattack! Frame=(\d+)')
PR = re.compile(r'pr@=\(([-0-9.]+),([-0-9.]+)\)')
LAST = re.compile(r'last=\(([-0-9.]+),([-0-9.]+)\)')
MIL = re.compile(r'\bMil=(\d+)')
NEA = re.compile(r'nEB=(\d+) nEA=(\d+)')
HP = re.compile(r'pr=\(sn(-?\d+) st(-?\d+) hp(-?\d+)/(\d+) ccd(-?\d+)\)')


def outcome(t):
    if '被祭司转换,归属阵营1->0' in t:
        return '胜'
    if 'DEFEAT: Priest killed' in t:
        return '祭死'
    if 'DEFEAT: Town Center destroyed' in t or '敌方 摧毁主营' in t:
        return 'TC毁'
    return '超时'


def main(tags):
    print('=' * 100)
    print('反攻期祭司「令→到位」分析（[BEAT] 桶级）')
    print('=' * 100)
    for tag in tags:
        recs = []
        for f in sorted(glob.glob('%s_*_r0_*.ait' % tag)):
            t = open(f, encoding='utf-8', errors='replace').read()
            cand = [int(x.group(1)) for x in (POP.search(t), CA.search(t)) if x]
            atk = min(cand) if cand else 33000
            res = outcome(t)
            prev = None
            for L in t.splitlines():
                if '[BEAT' not in L:
                    continue
                p = L.split(' | ', 3)
                try:
                    fr = int(p[1])
                except (IndexError, ValueError):
                    continue
                if fr < atk:
                    continue
                m = PR.search(L); l = LAST.search(L); h = HP.search(L)
                if not (m and l and h):
                    continue
                px, py = float(m.group(1)), float(m.group(2))
                lx, ly = float(l.group(1)), float(l.group(2))   # 打印时已是块坐标（勿再 ÷10）
                hp, mx = int(h.group(3)), int(h.group(4))
                if hp <= 0 or mx <= 0 or (px == 0.0 and py == 0.0):
                    continue
                if lx < -900:      # 从未发过移动令
                    continue
                gap = ((px - lx) ** 2 + (py - ly) ** 2) ** 0.5
                step = None if prev is None else ((px - prev[0]) ** 2 + (py - prev[1]) ** 2) ** 0.5
                recs.append(dict(gap=gap, step=step, res=res, fr=fr,
                                 mil=int(MIL.search(L).group(1)) if MIL.search(L) else -1,
                                 nea=int(NEA.search(L).group(2)) if NEA.search(L) else -1))
                prev = (px, py)
        if not recs:
            print('[%s] 无数据' % tag)
            continue
        N = len(recs)
        gaps = [r['gap'] for r in recs]
        steps = [r['step'] for r in recs if r['step'] is not None]
        print()
        print('### %s  反攻期桶=%d' % (tag, N))
        print('  gap(|实际-落点|): 中位=%.1f 均=%.1f  p90=%.1f  |  >3格占%.1f%%  >10格占%.1f%%'
              % (st.median(gaps), st.mean(gaps),
                 sorted(gaps)[int(0.9 * len(gaps))],
                 100.0 * sum(1 for g in gaps if g > 3) / N,
                 100.0 * sum(1 for g in gaps if g > 10) / N))
        print('  step(相邻桶位移): 中位=%.1f 均=%.1f  |  =0占%.1f%%  <0.5格占%.1f%%'
              % (st.median(steps), st.mean(steps),
                 100.0 * sum(1 for s in steps if s == 0) / len(steps),
                 100.0 * sum(1 for s in steps if s < 0.5) / len(steps)))
        print()
        print('  %-8s %6s %9s %9s %9s %9s' % ('结局', '桶数', 'gap中位', 'step中位', 'gap>3%', 'step=0%'))
        for res in ('胜', '祭死', '超时', 'TC毁'):
            g = [r for r in recs if r['res'] == res]
            if not g:
                continue
            gg = [r['gap'] for r in g]
            ss = [r['step'] for r in g if r['step'] is not None]
            print('  %-8s %6d %9.1f %9.1f %8.1f%% %8.1f%%' % (
                res, len(g), st.median(gg), st.median(ss) if ss else -1,
                100.0 * sum(1 for x in gg if x > 3) / len(g),
                100.0 * sum(1 for x in ss if x == 0) / len(ss) if ss else -1))


if __name__ == '__main__':
    main(sys.argv[1:] or ['club8n'])
