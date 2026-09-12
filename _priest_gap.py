# -*- coding: utf-8 -*-
r"""_priest_gap.py -- priest order-gap profile per arm (map single map).

For each game: frames of every "HumanMove: priest" order (field 1 = frame),
then the largest gap between consecutive orders. Grouped by outcome.

Why: debug_19485 shows the priest issued its LAST move order at 25:03.96 and died
at 25:36.16 -- a 1930-frame (32.2 s) silence while six enemy units shot at it.
This script measures how common such long silences are locally, and whether the
longest gap separates wins from priest-killed games.

ASCII-only source (this box's console is GBK).
"""
import glob
import io
import os
import re
import statistics
import sys

D = r'C:\new-aoe3.0.7g'
PR = '\u796d\u53f8'
MOVE = '\u79fb\u52a8\u81f3'
WIN = '\u88ab\u796d\u53f8\u8f6c\u6362,\u5f52\u5c5e\u9635\u84251->0'
PD = 'DEFEAT: Priest killed'
TC = 'DEFEAT: Town Center destroyed'

# field 1 of the 5-column engine line is the frame number
RE_PR_MOVE = re.compile(r'\|\s*(\d+)\s*\|[^\n]*?HumanMove:' + PR + r'\s+\d+\s+' + MOVE)


def outcome(t):
    if WIN in t:
        return 'W'
    if PD in t:
        return 'P'
    if TC in t:
        return 'T'
    return 'U'


def q(v, p):
    if not v:
        return None
    v = sorted(v)
    k = (len(v) - 1) * p
    f = int(k)
    c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def main(tags):
    print('%-12s %4s %6s %6s %6s %6s %6s' % ('tag', 'n', 'gm_med', 'gm_p90', 'gm_max', 'W_med', 'P_med'))
    for tag in tags:
        gmax, gm = [], []
        by = {'W': [], 'P': [], 'T': [], 'U': []}
        files = sorted(glob.glob(os.path.join(D, tag + '_map_r0_*.ait')))
        for fn in files:
            t = io.open(fn, encoding='utf-8', errors='replace').read()
            fr = sorted(int(m.group(1)) for m in RE_PR_MOVE.finditer(t))
            if len(fr) < 2:
                continue
            gaps = [b - a for a, b in zip(fr, fr[1:])]
            g = max(gaps)
            gmax.append(g)
            gm.append(statistics.median(gaps))
            by[outcome(t)].append(g)
        if not gmax:
            print('%-12s %4d  (no data)' % (tag, len(files)))
            continue
        print('%-12s %4d %6.0f %6.0f %6.0f %6.0f %6.0f' % (
            tag, len(gmax),
            statistics.median(gm), q(gm, 0.9), max(gmax),
            statistics.median(by['W']) if by['W'] else -1,
            statistics.median(by['P']) if by['P'] else -1))


if __name__ == '__main__':
    main(sys.argv[1:] if len(sys.argv) > 1 else ['wbase', 'sc1', 'p3a', 'fh1', 'pe2', 'pe5', 'club8n'])
