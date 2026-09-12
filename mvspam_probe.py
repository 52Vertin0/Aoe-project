# -*- coding: utf-8 -*-
"""
移动令刷屏 / 待命点重合 普查
口径:
  ① 刷屏 = 同一 (单位, 坐标) 在连续帧(间隔<=2)内重复 >=20 次的段
  ② 重合 = 同一坐标被 >=3 个不同单位下发过
用法: python mvspam_probe.py <files...>
"""
import re
import sys
from collections import defaultdict, Counter

MOVE_RE = re.compile(r'HumanMove:(\S+?) (\d+) 移动至 \(([\d.]+),([\d.]+)\)')


def scan(fn):
    seq = []
    total = 0
    for line in open(fn, encoding='utf-8', errors='replace'):
        m = re.search(r'\|\s*(\d+)\s*\|', line)
        if not m:
            continue
        fr = int(m.group(1))
        m2 = MOVE_RE.search(line)
        if m2:
            total += 1
            seq.append((fr, (m2.group(1), m2.group(2), m2.group(3), m2.group(4))))
    # ① 连续重复段
    runs = []
    i = 0
    while i < len(seq):
        j = i
        while j + 1 < len(seq) and seq[j + 1][1] == seq[i][1] and seq[j + 1][0] - seq[j][0] <= 2:
            j += 1
        n = j - i + 1
        if n >= 20:
            runs.append((n, seq[i][0], seq[j][0], seq[i][1]))
        i = j + 1
    # ② 同坐标多单位
    bycoord = defaultdict(set)
    coordcnt = Counter()
    for fr, key in seq:
        bycoord[(key[2], key[3])].add((key[0], key[1]))
        coordcnt[(key[2], key[3])] += 1
    shared = [(c, len(u), coordcnt[c]) for c, u in bycoord.items() if len(u) >= 3]
    shared.sort(key=lambda t: -t[1])
    return total, runs, shared


def main():
    files = sys.argv[1:]
    print('%-12s %-12s %-14s %-10s %s' % ('file', 'HumanMove', '重复段>=20', '最长段', '同点>=3单位'))
    print('-' * 78)
    for fn in files:
        try:
            total, runs, shared = scan(fn)
        except FileNotFoundError:
            continue
        mx = max((r[0] for r in runs), default=0)
        print('%-12s %-12d %-14d %-10d %d' % (fn, total, len(runs), mx, len(shared)))
        for n, f0, f1, key in sorted(runs, reverse=True)[:3]:
            print('      ★最长 %-4s %-18s (%s,%s) f=%d..%d 连发 %d 帧'
                  % (key[0], 'SN=' + key[1], key[2], key[3], f0, f1, n))
        for c, nu, cnt in shared[:3]:
            print('      ★重合 (%s,%s) 被 %d 个单位下发 %d 次' % (c[0], c[1], nu, cnt))


if __name__ == '__main__':
    main()
