# -*- coding: utf-8 -*-
r"""_sig_stat.py -- map-single-map outcome tally for the arms touched on 10-08.

Reads <TAG>_map_r0_*.ait, prints W/P/T/U per tag with Wilson 95% CI on W.
Outcome rule: same as _winall.py
    W  = converted win sentinel
    P  = priest killed
    T  = town center destroyed
    U  = timeout / truncated (anything else, incl. abort)
ASCII-only source (GBK console on this box).
"""
import glob
import io
import math
import os
import sys

D = r'C:\new-aoe3.0.7g'
WIN = '\u88ab\u796d\u53f8\u8f6c\u6362,\u5f52\u5c5e\u9635\u84251->0'
PD = 'DEFEAT: Priest killed'
TC = 'DEFEAT: Town Center destroyed'


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d * 100, (c + m) / d * 100)


def outcome(t):
    if WIN in t:
        return 'W'
    if PD in t:
        return 'P'
    if TC in t:
        return 'T'
    return 'U'


def main(tags):
    rows = []
    for tag in tags:
        files = sorted(glob.glob(os.path.join(D, tag + '_map_r0_*.ait')))
        cnt = {'W': 0, 'P': 0, 'T': 0, 'U': 0}
        for fn in files:
            try:
                t = io.open(fn, encoding='utf-8', errors='replace').read()
            except Exception:
                cnt['U'] += 1
                continue
            cnt[outcome(t)] += 1
        n = sum(cnt.values())
        lo, hi = wilson(cnt['W'], n)
        rows.append((tag, n, cnt, lo, hi))
    print('%-14s %4s %4s %4s %4s %4s   %6s  %s' % ('tag', 'n', 'W', 'P', 'T', 'U', 'win%', '95%CI'))
    for tag, n, c, lo, hi in rows:
        wr = (100.0 * c['W'] / n) if n else 0.0
        print('%-14s %4d %4d %4d %4d %4d   %5.1f%%  [%.1f, %.1f]' % (
            tag, n, c['W'], c['P'], c['T'], c['U'], wr, lo, hi))


if __name__ == '__main__':
    main(sys.argv[1:] if len(sys.argv) > 1 else [
        'wbase', 'sc1', 'wearly', 'er1', 'nc1', 'v1', 'gs1',
        'fh1', 'p3a', 'ca1', 'pe2', 'pe5', 'club8n', 'kb',
    ])
