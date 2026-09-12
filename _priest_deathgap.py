# -*- coding: utf-8 -*-
r"""_priest_deathgap.py -- priest "silence before death" per arm (map single map).

For games where the priest dies, compute  deathFrame - lastPriestMoveOrderFrame,
i.e. how long the priest issued no move order before it died.

debug_19485: last move order 25:03.96, death 25:36.16 -> 1930 frames (32.2 s),
during which it started a conversion at 25:10 and took fire from six units.

ASCII-only source (GBK console).
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

RE_PR_MOVE = re.compile(r'\|\s*(\d+)\s*\|[^\n]*?HumanMove:' + PR + r'\s+\d+\s+' + MOVE)
RE_PR_DEATH = re.compile(r'\|\s*(\d+)\s*\|[^\n]*?' + PR + r'\(\u7f16\u53f7:?(\d+)\)\u6b7b\u4ea1')
# windows of interest: how many orders in the last 2000 / 1000 frames before death
def q(v, p):
    if not v:
        return None
    v = sorted(v)
    k = (len(v) - 1) * p
    f = int(k)
    c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def main(tags):
    print('%-12s %4s %8s %8s %8s %8s %8s' % ('tag', 'P_n', 'gap_med', 'gap_p90', 'gap_max', 'n<600f', '%<600f'))
    for tag in tags:
        gaps = []
        short = 0
        files = sorted(glob.glob(os.path.join(D, tag + '_map_r0_*.ait')))
        for fn in files:
            t = io.open(fn, encoding='utf-8', errors='replace').read()
            d = RE_PR_DEATH.search(t)
            if not d:
                continue
            death = int(d.group(1))
            fr = [int(m.group(1)) for m in RE_PR_MOVE.finditer(t) if int(m.group(1)) <= death]
            if not fr:
                continue
            gap = death - max(fr)
            gaps.append(gap)
            if gap < 600:
                short += 1
        if not gaps:
            print('%-12s %4d  (no data)' % (tag, 0))
            continue
        print('%-12s %4d %8.0f %8.0f %8d %8d %7.1f%%' % (
            tag, len(gaps), statistics.median(gaps), q(gaps, 0.9), max(gaps),
            short, 100.0 * short / len(gaps)))


if __name__ == '__main__':
    main(sys.argv[1:] if len(sys.argv) > 1 else ['wbase', 'sc1', 'p3a', 'fh1', 'pe2', 'pe5', 'club8n'])
