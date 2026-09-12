# -*- coding: utf-8 -*-
r"""_fleehold_cmp.py -- P1 (priest "convert vs flee" contention) before/after metrics.

Usage:
    python _fleehold_cmp.py <TAG_A> [TAG_B ...]

Reads <TAG>_map_r0_*.ait from the project dir and prints one row per tag:
    n / W / P / T                outcome counts (same rule as _winall.py)
    moves                        priest HumanMove orders (engine action log)
    gap_med                      median frame gap between consecutive orders
    dup%                         share of orders repeating the previous landing point
    conv                         unit-convert orders (HumanAction "set convert target")
    cut%                         share of those orders followed by a priest move <=400f
    net / rev                    net displacement and direction reversals ([BEAT] pr@,
                                 (0,0) samples excluded -- the death sentinel)

Metric intent (P1): before the fix the priest re-issued moves every ~1 frame, so
gap_med collapsed to 1 and cut% was near 100 (the 400f cast was reset every frame).
After the fix we expect gap_med >= 18 and a much lower cut%.

ASCII-only source on purpose: this box's PowerShell console is GBK and mangles
non-ASCII script sources (PS 5.1 reads BOM-less UTF-8 as ANSI).
"""
import glob
import os
import re
import statistics
import sys

D = r'C:\new-aoe3.0.7g'

# Chinese markers as escapes so the source stays pure ASCII.
PR = '\u796d\u53f8'                                                   # priest
MOVE_MARK = '\u79fb\u52a8\u81f3'                                      # "move to"
CONV_MARK = '\u8bbe\u7f6e\u8f6c\u6362\u76ee\u6807\u4e3a'              # "set convert target"
WIN = '\u88ab\u796d\u53f8\u8f6c\u6362,\u5f52\u5c5e\u9635\u84251->0'    # win sentinel
PD = 'DEFEAT: Priest killed'
TC = 'DEFEAT: Town Center destroyed'

RE_MOVE = re.compile(r'\|\s*(\d+)\s*\|[^\n]*?HumanMove:' + PR + r'\s+\d+\s+' + MOVE_MARK + r'\s*\(([-\d.]+)\s*,\s*([-\d.]+)\)')
RE_CONV = re.compile(r'\|\s*(\d+)\s*\|[^\n]*?HumanAction:' + PR + r'\s+\d+\s+' + CONV_MARK)
RE_BEAT = re.compile(r'\[BEAT f=(\d+)[^\r\n]*?pr@=\(([\d.\-]+),([\d.\-]+)\)')


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

    moves = [(int(m.group(1)), m.group(2), m.group(3)) for m in RE_MOVE.finditer(t)]
    frames = [m[0] for m in moves]
    gaps = [b - a for a, b in zip(frames, frames[1:])]
    late = [f for f in frames if frames and f > frames[-1] - 900]
    late_gaps = [b - a for a, b in zip(late, late[1:])]
    dup = 0
    for a, b in zip(moves, moves[1:]):
        if a[1] == b[1] and a[2] == b[2]:
            dup += 1

    convs = [int(m.group(1)) for m in RE_CONV.finditer(t)]
    cut = 0
    for c in convs:
        if any(c < f <= c + 400 for f in frames):
            cut += 1

    pts = []
    for m in RE_BEAT.finditer(t):
        x, y = float(m.group(2)), float(m.group(3))
        if x == 0.0 and y == 0.0:
            continue
        pts.append((x, y))
    net = 0.0
    rev = 0
    if len(pts) > 2:
        net = ((pts[-1][0] - pts[0][0]) ** 2 + (pts[-1][1] - pts[0][1]) ** 2) ** 0.5
        prev = None
        for a, b in zip(pts, pts[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            if (dx * dx + dy * dy) ** 0.5 <= 1.0:
                continue
            ang = __import__('math').atan2(dy, dx)
            if prev is not None:
                d = abs(ang - prev)
                if d > 3.141592653589793:
                    d = 6.283185307179586 - d
                if d > 2.0943951023931953:
                    rev += 1
            prev = ang
    return dict(g=os.path.basename(path), out=out, moves=len(moves), gap_med=statistics.median(gaps) if gaps else float('nan'),
                gap_last=statistics.median(late_gaps) if late_gaps else float('nan'),
                dup=(100.0 * dup / (len(moves) - 1)) if len(moves) > 1 else 0.0,
                conv=len(convs), cut=(100.0 * cut / len(convs)) if convs else 0.0,
                net=net, rev=rev)


def main(tags):
    if not tags:
        tags = ['pe2']
    for tag in tags:
        files = sorted(glob.glob(os.path.join(D, tag + '_map_r0_*.ait')))
        if not files:
            print('%-10s : no %s_map_r0_*.ait' % (tag, tag))
            continue
        rows = [analyze(f) for f in files]
        cnt = {}
        for r in rows:
            cnt[r['out']] = cnt.get(r['out'], 0) + 1
        med = lambda k: statistics.median([r[k] for r in rows])
        print('%-10s n=%-3d W=%-3d P=%-3d T=%-3d | moves_med=%-6.0f gap_med=%-6.1f gap_last900=%-6.1f dup%%=%-5.1f '
              'conv_med=%-6.0f cut%%=%-5.1f net_med=%-6.1f rev_med=%-5.1f'
              % (tag, len(rows), cnt.get('W', 0), cnt.get('P', 0), cnt.get('T', 0) + cnt.get('TC', 0),
                 med('moves'), med('gap_med'), med('gap_last'), med('dup'), med('conv'), med('cut'), med('net'), med('rev')))
        worst = sorted(rows, key=lambda r: (r['gap_last'] if r['gap_last'] == r['gap_last'] else 1e9))[:3]
        for r in worst:
            print('    worst gap_last900: %-24s %s moves=%-4d gap_med=%-5.1f gap_last900=%-5.1f dup%%=%-5.1f conv=%-4d cut%%=%-5.1f'
                  % (r['g'], r['out'], r['moves'], r['gap_med'], r['gap_last'], r['dup'], r['conv'], r['cut']))


if __name__ == '__main__':
    main(sys.argv[1:])
