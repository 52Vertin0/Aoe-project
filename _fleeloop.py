#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_fleeloop.py —— 量化「反攻期祭司逃跑档把人送回基地 / 横穿全图往返」

用法: python _fleeloop.py fix1 fixG fixH
产出: 逐 tag（全图合计）：逃跑令占比 / 末尾落点仍在【我方半场】的局数比例 / 反攻段往返次数中位

口径：
  逃跑令 = [BEAT] 的 pm 第 1 段 `f`；总令 = f+ca+h+cnt+o（同桶累加）
  反攻段 = 桶号 b >= Counterattack帧/150
  末段落点 = 反攻段最后 10 桶的 pm last=(x,y) 均值；与【我方基地中心】(§3.5) 比与【敌武器厂】比，近者胜
  往返次数 = 反攻段内「到敌武器厂距离」的方向翻转次数
自查：fixH_map_r0_20 末段应出现大量 pm f 且落点 ≈(77.1,12.4)
"""
import re, sys, glob, os, statistics as st

WSXY  = {'map': (11, 86), 'map1': (93, 11), 'map2': (24, 6), 'map3': (82, 20)}
BASEC = {'map': (80.4, 12.1), 'map1': (22.4, 75.0), 'map2': (73.8, 87.2), 'map3': (28.9, 81.0)}


def main():
    tags = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not tags:
        print(__doc__); return
    print('%-7s %5s %10s %12s %12s %10s' % ('tag', 'n', '逃跑令占比', '末落点近基地局', '末落点近基地比例', '往返次数中位'))
    for tg in tags:
        F = sorted(glob.glob(tg + '_*_r0_*.ait'))
        if not F: continue
        allf = alltot = 0
        basecnt = 0
        trips = []
        for f in F:
            t = open(f, encoding='utf-8', errors='replace').read()
            mc = re.search(r'Counterattack! Frame=(\d+)', t)
            caB = (int(mc.group(1)) // 150) if mc else 0
            mpn = (re.search(r'_(map\d?)_', os.path.basename(f)) or [None, 'map'])[1]
            wxy, bxy = WSXY[mpn], BASEC[mpn]
            tot = fl = 0
            tail, dists = [], []
            for L in t.splitlines():
                mb = re.search(r'\[BEAT f=(\d+) b=(\d+)\]', L)
                if not mb: continue
                b = int(mb.group(2))
                m = re.search(r'pm f(\d+) ca(\d+) h(\d+) cnt(\d+) o(\d+) last=\(([-\d.]+),([-\d.]+)\)', L)
                if not m or b < caB: continue
                vals = [int(m.group(i)) for i in range(1, 6)]
                tot += sum(vals); fl += vals[0]
                tx, ty = float(m.group(6)), float(m.group(7))
                tail.append((tx, ty))
                dists.append(((tx - wxy[0]) ** 2 + (ty - wxy[1]) ** 2) ** 0.5)
            allf += fl; alltot += tot
            if tail:
                t10 = tail[-min(10, len(tail)):]
                dbase = sum(((x - bxy[0]) ** 2 + (y - bxy[1]) ** 2) ** 0.5 for x, y in t10) / len(t10)
                dws = sum(((x - wxy[0]) ** 2 + (y - wxy[1]) ** 2) ** 0.5 for x, y in t10) / len(t10)
                if dbase < dws: basecnt += 1
            trips.append(sum(1 for i in range(2, len(dists))
                             if (dists[i] - dists[i - 1]) * (dists[i - 1] - dists[i - 2]) < 0))
        n = len(F)
        print('%-7s %5d %9.1f%% %12d %11.0f%% %10.1f' % (
            tg, n, 100.0 * allf / alltot if alltot else 0,
            basecnt, 100.0 * basecnt / n if n else 0, st.median(trips) if trips else 0))


if __name__ == '__main__':
    main()
