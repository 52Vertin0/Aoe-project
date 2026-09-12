# -*- coding: utf-8 -*-
"""g2w0q (改动前) vs g2w2q (减金工伐木) —— 4图×3局 A/B 统计"""
import glob, re
from math import comb


def outcome(fn):
    s = open(fn, encoding='utf-8', errors='replace').read()
    if '被祭司转换' in s:
        return 'W'
    if 'DEFEAT: Priest killed' in s:
        return 'P'
    if 'DEFEAT: Town Center destroyed' in s or '敌方 摧毁主营' in s:
        return 'T'
    return 'U'


def fisher(a, b, c, d):
    n = a + b + c + d
    if n == 0:
        return 1.0
    r1, c1 = a + b, a + c
    def p(k):
        return comb(c1, k) * comb(n - c1, r1 - k) / comb(n, r1)
    lo, hi = max(0, r1 - (n - c1)), min(r1, c1)
    obs = p(a)
    tot = sum(p(k) for k in range(lo, hi + 1) if p(k) <= obs * (1 + 1e-12))
    return min(1.0, tot)


def peak_mil(fn):
    s = open(fn, encoding='utf-8', errors='replace').read()
    v = [int(x) for x in re.findall(r'Mil=(\d+)', s)]
    return max(v) if v else None


def gold_last(fn):
    s = open(fn, encoding='utf-8', errors='replace').read()
    v = re.findall(r'G=(\d+)', s)
    return int(v[-1]) if v else None


def wood_last(fn):
    s = open(fn, encoding='utf-8', errors='replace').read()
    v = re.findall(r'W=(\d+)', s)
    return int(v[-1]) if v else None


for tag, label in (('g2w0q', '改动前 aggpriest'), ('g2w2q', '改动后 减金工伐木')):
    files = sorted(glob.glob(tag + '_*_r0_*.ait'))
    res = {'W': 0, 'P': 0, 'T': 0, 'U': 0}
    permap = {}
    mils, gv, wv = [], [], []
    for f in files:
        o = outcome(f)
        res[o] += 1
        m = re.search(r'_(map\d*)_r0_', f)
        mp = m.group(1) if m else '?'
        d = permap.setdefault(mp, {'W': 0, 'n': 0})
        d['n'] += 1
        d['W'] += (o == 'W')
        pm = peak_mil(f)
        if pm is not None:
            mils.append(pm)
        gl = gold_last(f)
        if gl is not None:
            gv.append(gl)
        wl = wood_last(f)
        if wl is not None:
            wv.append(wl)
    n = len(files)
    print('=== %s   %s ===' % (tag, label))
    print('  局数 %d   胜 %d (%.1f%%)   祭死 %d   主城毁 %d   超时/未决 %d'
          % (n, res['W'], 100.0 * res['W'] / n if n else 0, res['P'], res['T'], res['U']))
    print('  分图: ' + '  '.join('%s %d/%d' % (k, v['W'], v['n']) for k, v in sorted(permap.items())))
    if mils:
        mils.sort(); print('  军队峰值 中位 %d  最大 %d' % (mils[len(mils) // 2], mils[-1]))
    if gv:
        gv.sort(); print('  黄金存量末值 中位 %d' % gv[len(gv) // 2])
    if wv:
        wv.sort(); print('  木材存量末值 中位 %d' % wv[len(wv) // 2])
    print()


def collect(tag):
    files = sorted(glob.glob(tag + '_*_r0_*.ait'))
    w = sum(1 for f in files if outcome(f) == 'W')
    return w, len(files) - w

w0, l0 = collect('g2w0q')
w1, l1 = collect('g2w2q')
print('Fisher 双尾 p = %.3f    (%d/%d  vs  %d/%d)' % (fisher(w0, l0, w1, l1), w0, w0 + l0, w1, w1 + l1))
