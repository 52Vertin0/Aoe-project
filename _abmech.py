#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_abmech.py —— A/B 的【低噪声机制端点】表（胜率噪声 ±17pp 不可作主判据，机制量才是）

用法: python _abmech.py base0 fix1 fixH
产出: 逐 tag × 图：反攻起点帧中位 / 发现WS帧中位 / 起手率 / 起手时塔数中位 / 祭司死亡帧中位

口径（与 _tagcmp.py / _wsfind.py 一致，勿改）：
  反攻起点  = `Counterattack! Frame=N`（含 "满编即出发!" 与 "ALL WAVES DEFEATED!" 两条路径）
  发现WS    = `Enemy Siege Workshop found at (x,y)` 首次出现行的第 2 段帧号
  起手      = `>> Priest converting Siege Workshop! f=N`（每次发令一条，统计【局数】而非条数）
  起手塔数  = 该行 `towers=N`
自查：fixG 的 map 应给出 反攻≈33002、发现中位≈39000、起手 6/16（见日 log §14）
"""
import re, sys, glob, os, collections, statistics as st

MAPS = ['map', 'map1', 'map2', 'map3']


def med(v):
    return st.median(v) if v else None


def fm(v, p='%.0f'):
    return (p % v) if v is not None else '—'


def parse(path):
    t = open(path, encoding='utf-8', errors='replace').read()
    d = {}
    mb = re.search(r'_(map\d?)_r(\d+)_(\d+)\.ait', os.path.basename(path))
    d['map'] = mb.group(1) if mb else '?'
    d['tag'] = os.path.basename(path).split('_map')[0]

    mc = re.search(r'Counterattack! Frame=(\d+)', t)
    d['caF'] = int(mc.group(1)) if mc else None
    d['caEarly'] = '满编即出发' in t          # 走的是新闸而非原定 22 分

    # 发现 WS（取行内第 2 段=帧号，避免把坐标当帧号）
    d['wsF'] = None
    m = re.search(r'^\s*\S+\s*\|\s*(\d+)\s*\|[^\n]*Enemy Siege Workshop found', t, re.M)
    if m:
        d['wsF'] = int(m.group(1))

    conv = re.findall(r'converting Siege Workshop! f=(\d+) d=([\d.]+) hp=([\d.]+) nearT=([-\d.]+) towers=(\d+)', t)
    d['nConv'] = len(conv)
    d['convT'] = [float(c[4]) for c in conv]
    d['convF'] = int(conv[0][0]) if conv else None
    d['convHp'] = float(conv[0][2]) if conv else None

    d['win'] = bool(re.search(r'攻城武器厂\(编号:\d+\)被祭司转换', t))
    md = re.search(r'\|\s*(\d+)\s*\|[^|]*\|[^|]*\|[^|]*DEFEAT: Priest killed', t)
    d['deathF'] = int(md.group(1)) if md else None
    fs = [int(x) for x in re.findall(r'\|\s*(\d+)\s*\|\s*(?:red|green|blue|black)', t)]
    d['endf'] = max(fs) if fs else 0
    return d


def main():
    tags = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not tags:
        print(__doc__); return
    data = {tg: [parse(f) for f in sorted(glob.glob(tg + '_*_r0_*.ait'))] for tg in tags}

    print('=== ① 逐 tag × 图：机制端点 ===')
    hdr = ('tag', 'map', 'n', '反攻帧', '分', '新闸', '发现WS', '分', '起手局', '起手率',
           '首起手帧', '起手塔', '祭死帧', '胜')
    print('%-7s %-5s %3s %7s %5s %4s %7s %5s %5s %6s %8s %6s %7s %3s' % hdr)
    for tg in tags:
        for mp in MAPS:
            R = [d for d in data[tg] if d['map'] == mp]
            if not R: continue
            ca = [d['caF'] for d in R if d['caF']]
            wsf = [d['wsF'] for d in R if d['wsF']]
            found = sum(1 for d in R if d['wsF'])
            fired = sum(1 for d in R if d['nConv'] > 0)
            ct = [x for d in R for x in d['convT']]
            df = [d['deathF'] for d in R if d['deathF']]
            w = sum(1 for d in R if d['win'])
            print('%-7s %-5s %3d %7s %5s %4d %7s %5s %3d/%-2d %5s%% %8s %6s %7s %3d' % (
                tg, mp, len(R), fm(med(ca)),
                fm(med(ca) / 1500 if med(ca) else None, '%.1f'),
                sum(1 for d in R if d['caEarly']),
                fm(med(wsf)), fm(med(wsf) / 1500 if med(wsf) else None, '%.1f'),
                fired, found,
                fm(100.0 * fired / found if found else 0, '%.0f'),
                fm(med([d['convF'] for d in R if d['convF']])),
                fm(med(ct)), fm(med(df)), w))

    print()
    print('=== ② 全图合计 ===')
    print('%-7s %4s %8s %8s %8s %9s %8s %6s' % (
        'tag', 'n', '反攻帧', '发现WS', '发现率', '起手局率', '首起手帧', '胜率'))
    for tg in tags:
        R = data[tg]
        ca = [d['caF'] for d in R if d['caF']]
        wsf = [d['wsF'] for d in R if d['wsF']]
        fired = sum(1 for d in R if d['nConv'] > 0)
        w = sum(1 for d in R if d['win'])
        print('%-7s %4d %8s %8s %7s%% %8s%% %8s %7s%%' % (
            tg, len(R), fm(med(ca)), fm(med(wsf)),
            fm(100.0 * len(wsf) / len(R)),
            fm(100.0 * fired / len(R)),
            fm(med([d['convF'] for d in R if d['convF']])),
            fm(100.0 * w / len(R))))


if __name__ == '__main__':
    main()
