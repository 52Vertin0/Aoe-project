# -*- coding: utf-8 -*-
r"""_p3_cmp.py -- P3 (priest advance vs siege-workshop-known) before/after metrics.

Usage:
    python _p3_cmp.py <TAG_A> [TAG_B ...]

Per tag (reads <TAG>_map_r0_*.ait):
    n / W / P / T      outcome counts (same rule as _winall.py)
    found%             share of games that ever logged "Enemy Siege Workshop found at"
    start%             share of games that issued >=1 "Priest converting Siege Workshop"
    dEnd               median distance (blocks) from the priest's last [BEAT] pr@ to the
                       workshop block coord, over games that found the workshop
    T<20               over TIMEOUT games only: share with dEnd < 20 blocks
    adv/esc/wait       total [PRIEST-WITH-ARMY] / [PRIEST-ESCORT] / [SIEGE-WAIT] lines

P3 intent: the advance used to be gated on clearOk (towers cleared), so when the
workshop was known but towers were not cleared the priest stayed home while the
army pushed. After the fix we expect dEnd to fall and T<20 to rise.

ASCII-only source on purpose (GBK console on this box).
"""
import glob
import os
import re
import statistics
import sys

D = r'C:\new-aoe3.0.7g'
WIN = '\u88ab\u796d\u53f8\u8f6c\u6362,\u5f52\u5c5e\u9635\u84251->0'   # win sentinel
PD = 'DEFEAT: Priest killed'
TC = 'DEFEAT: Town Center destroyed'
FOUND = re.compile(r'Enemy Siege Workshop found at \((\d+),(\d+)\)')
BEAT = re.compile(r'\[BEAT f=(\d+)[^\r\n]*?pr@=\(([\d.\-]+),([\d.\-]+)\)')
BL = 35.777


def outcome(t):
    if WIN in t:
        return 'W'
    if PD in t:
        return 'P'
    if TC in t:
        return 'TC'
    return 'T'


def analyze(path):
    t = open(path, encoding='utf-8', errors='replace').read()
    out = outcome(t)
    m = FOUND.search(t)
    wx = wy = None
    if m:
        wx, wy = float(m.group(1)) + 1.0, float(m.group(2)) + 1.0
    d_end = None
    if wx is not None:
        for b in BEAT.finditer(t):
            x, y = float(b.group(2)) / BL, float(b.group(3)) / BL
            if x == 0.0 and y == 0.0:
                continue
            d_end = ((x - wx) ** 2 + (y - wy) ** 2) ** 0.5
    return dict(g=os.path.basename(path), out=out, found=wx is not None, d=d_end,
                start=t.count('Priest converting Siege Workshop'),
                adv=t.count('[PRIEST-WITH-ARMY'), esc=t.count('[PRIEST-ESCORT'),
                wait=t.count('[SIEGE-WAIT'))


def main(tags):
    for tag in (tags or ['pe2']):
        files = sorted(glob.glob(os.path.join(D, tag + '_map_r0_*.ait')))
        if not files:
            print('%-8s : no files' % tag)
            continue
        rows = [analyze(f) for f in files]
        n = len(rows)
        cnt = {}
        for r in rows:
            cnt[r['out']] = cnt.get(r['out'], 0) + 1
        ds = [r['d'] for r in rows if r['d'] is not None]
        tds = [r['d'] for r in rows if r['d'] is not None and r['out'] == 'T']
        t20 = [d for d in tds if d < 20.0]
        print('%-8s n=%-3d W=%-3d P=%-3d T=%-3d | found%%=%-5.1f start%%=%-5.1f dEnd_med=%-6.1f '
              'T_dEnd_med=%-6.1f T<20=%-3d/%-3d | adv=%-6d esc=%-5d wait=%-5d'
              % (tag, n, cnt.get('W', 0), cnt.get('P', 0), cnt.get('T', 0) + cnt.get('TC', 0),
                 100.0 * sum(1 for r in rows if r['found']) / n,
                 100.0 * sum(1 for r in rows if r['start'] > 0) / n,
                 statistics.median(ds) if ds else float('nan'),
                 statistics.median(tds) if tds else float('nan'), len(t20), len(tds),
                 sum(r['adv'] for r in rows), sum(r['esc'] for r in rows), sum(r['wait'] for r in rows)))


if __name__ == '__main__':
    main(sys.argv[1:])
