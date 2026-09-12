# -*- coding: utf-8 -*-
"""_priest_pos.py —— 反攻期祭司"离太远"的空间解释

假设：反攻期祭司被两类约束钉在离敌军队很远的地方 ——
  (a) PRIEST_MIN_DIST_TARGET=18 > 感化射程 12 的 legacy 后撤锚（军后 8 格 + 距目标 ≥18 格）
  (b) 推进段只朝武器厂走，而敌军队主力可能根本不在那条线上
本脚本只用 [BEAT]（150 帧分桶，免疫 frame 跳号），输出：
  反攻期每桶：dS(距武器厂) / inBox(在我军包围盒内) / nEA(可见敌军队) / nEB / Mil / hp
  ⇒ 按 dS 分档看"祭司是否已在武器厂射程内"，按 nEA 看"附近到底有没有敌军"
用法： python _priest_pos.py <TAG> [TAG2 ...]
"""
import glob
import os
import re
import statistics as st
import sys

MAP_WS = {'map': (11, 86), 'map1': (93, 11), 'map2': (24, 6), 'map3': (82, 20)}
CA = re.compile(r'ALL WAVES DEFEATED! Counterattack! Frame=(\d+)')


def which_map(bn):
    for k in ('map1', 'map2', 'map3'):
        if ('_' + k + '_') in bn:
            return k
    return 'map'


def outcome(t):
    if '被祭司转换,归属阵营1->0' in t:
        return '胜'
    if 'DEFEAT: Priest killed' in t:
        return '祭死'
    if 'DEFEAT: Town Center destroyed' in t or '敌方 摧毁主营' in t:
        return 'TC毁'
    return '超时'


def rows(path):
    mp = which_map(os.path.basename(path))
    wx, wy = MAP_WS[mp]
    tx, ty = wx + 1.0, wy + 1.0
    out = []
    for L in open(path, encoding='utf-8', errors='replace'):
        if '[BEAT' not in L:
            continue
        p = L.split(' | ', 3)
        try:
            fr = int(p[1])
        except (IndexError, ValueError):
            continue
        mb = re.search(r'\bb=(\d+)\]', L)
        mp_ = re.search(r'pr@=\(([-0-9.]+),([-0-9.]+)\)', L)
        mh = re.search(r'pr=\(sn(-?\d+) st(-?\d+) hp(-?\d+)/(\d+) ccd(-?\d+)\)', L)
        bb = re.search(r'bbox=\(x([-0-9.]+)\.\.([-0-9.]+),y([-0-9.]+)\.\.([-0-9.]+)\)', L)
        mm = re.search(r'\bMil=(\d+)', L)
        ne = re.search(r'nEB=(\d+) nEA=(\d+)', L)
        if not (mb and mp_ and mh and bb):
            continue
        px, py = float(mp_.group(1)), float(mp_.group(2))
        hp, mx = int(mh.group(3)), int(mh.group(4))
        if hp <= 0 or mx <= 0 or (px == 0.0 and py == 0.0):
            continue
        x1, x2, y1, y2 = [float(g) for g in bb.groups()]
        dx = max(x1 - px, 0.0, px - x2)
        dy = max(y1 - py, 0.0, py - y2)
        out.append(dict(fr=fr, b=int(mb.group(1)),
                        dS=((px - tx) ** 2 + (py - ty) ** 2) ** 0.5,
                        inBox=(dx * dx + dy * dy) ** 0.5 <= 0.0,
                        hp=hp / mx, mil=int(mm.group(1)) if mm else -1,
                        nEB=int(ne.group(1)) if ne else -1, nEA=int(ne.group(2)) if ne else -1))
    return out


def main(tags):
    print('=' * 100)
    print('反攻期祭司空间位置解剖（[BEAT] 桶级，免疫 frame 跳号）')
    print('  dS = 祭司距敌方武器厂（块）；inBox = 是否在我军包围盒内；nEA = 可见敌军队数')
    print('=' * 100)
    for tag in tags:
        buckets = []
        nfile = 0
        for f in sorted(glob.glob('%s_*_r0_*.ait' % tag)):
            t = open(f, encoding='utf-8', errors='replace').read()
            m = CA.search(t)
            if not m:
                continue
            atk = int(m.group(1))
            rs = [r for r in rows(f) if r['fr'] >= atk]
            if not rs:
                continue
            nfile += 1
            for r in rs:
                r['res'] = outcome(t)
            buckets.extend(rs)
        if not buckets:
            print('[%s] 无反攻期数据' % tag)
            continue
        print()
        print('### %s  局数(有反攻点)=%d  反攻期桶数=%d' % (tag, nfile, len(buckets)))
        # dS 分档
        cuts = [(0, 12), (12, 18), (18, 28), (28, 50), (50, 1e9)]
        print('  %-14s %6s %7s %8s %9s %9s %9s' % ('dS 距武器厂', '占比', 'nEA中位', 'nEB中位', 'Mil中位', 'inBox%', 'hp中位'))
        for lo, hi in cuts:
            g = [r for r in buckets if lo <= r['dS'] < hi]
            if not g:
                continue
            print('  %-14s %5.1f%% %7.1f %8.1f %9.1f %8.0f%% %9.2f' % (
                '[%g,%g)' % (lo, hi) if hi < 1e8 else '>=%g' % lo,
                100.0 * len(g) / len(buckets),
                st.median([r['nEA'] for r in g]), st.median([r['nEB'] for r in g]),
                st.median([r['mil'] for r in g]),
                100.0 * sum(1 for r in g if r['inBox']) / len(g),
                st.median([r['hp'] for r in g])))
        # nEA 分档
        print()
        print('  %-16s %6s %9s %9s %9s' % ('nEA 可见敌军队', '占比', 'dS中位', 'Mil中位', 'inBox%'))
        for lo, hi in ((0, 1), (1, 5), (5, 11), (11, 1e9)):
            g = [r for r in buckets if lo <= r['nEA'] < hi]
            if not g:
                continue
            print('  %-16s %5.1f%% %9.1f %9.1f %8.0f%%' % (
                '=%g' % lo if hi - lo == 1 else '[%g,%g)' % (lo, hi),
                100.0 * len(g) / len(buckets),
                st.median([r['dS'] for r in g]), st.median([r['mil'] for r in g]),
                100.0 * sum(1 for r in g if r['inBox']) / len(g)))
        # 结局分组
        print()
        print('  %-8s %6s %8s %8s %8s %9s %9s' % ('结局', '桶数', 'dS中位', 'nEA中位', 'Mil中位', 'inBox%', 'dS<=12%'))
        for res in ('胜', '祭死', '超时', 'TC毁'):
            g = [r for r in buckets if r['res'] == res]
            if not g:
                continue
            print('  %-8s %6d %8.1f %8.1f %8.1f %8.0f%% %8.1f%%' % (
                res, len(g), st.median([r['dS'] for r in g]), st.median([r['nEA'] for r in g]),
                st.median([r['mil'] for r in g]),
                100.0 * sum(1 for r in g if r['inBox']) / len(g),
                100.0 * sum(1 for r in g if r['dS'] <= 12) / len(g)))


if __name__ == '__main__':
    main(sys.argv[1:] or ['club8n'])
