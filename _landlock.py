#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_landlock.py —— 检测「不可达落点刷屏」（Locked Landing）：
  祭司连续下发【同一个】落点（块坐标四舍五入到 0.15 格内视为同一点）>= RUN 次，
  且在这段时间里祭司的桶级位置几乎没有位移（< MOVE 格）=> 判定为「落点被引擎拒收/路径不可达」的锁死段。
  病形样本：fix3smoke_map_r0_1，f=44249~44357 每 18 帧重发 (53.89,47.10)，祭司钉在 (23.4,73.0) 一步没动。

用法: python _landlock.py base0_*_r0_*.ait [fix1_*.ait ...]
输出: 每局一行「锁死段数 / 锁死帧数 / 最长锁死帧 / 锁死帧占祭司存活帧比」+ 结局
"""
import re, sys, glob, os, collections, statistics

BL = 35.777
RUN = 3        # 连续同点 >= RUN 次
MOVE = 1.0     # 期间祭司位移 < MOVE 格
SAME = 0.15    # 落点相同判据（格）


def parse(f):
    t = open(f, encoding='utf-8', errors='replace').read()
    win = bool(re.search(r'攻城武器厂\(编号:\d+\)被祭司转换', t)) or \
        'VICTORY! Siege Workshop converted' in t
    pd = 'DEFEAT: Priest killed' in t
    tcl = bool(re.search(r'市镇中心\(编号:\d+\)被摧毁', t))
    fs = [int(x) for x in re.findall(r'\|\s*(\d+)\s*\|\s*(?:red|green|blue|black)', t)]
    endf = max(fs) if fs else 0

    mv = []      # (frame, x块, y块)
    pr = []      # (frame, x块, y块)  桶级祭司位置
    for l in t.splitlines():
        mf = re.search(r'\|\s*(\d+)\s*\|', l)
        if not mf:
            continue
        fno = int(mf.group(1))
        if 'HumanMove:祭司 ' in l:
            m = re.search(r'移动至 \(([\d.]+),([\d.]+)\)', l)
            if m:
                mv.append((fno, float(m.group(1)) / BL, float(m.group(2)) / BL))
        if '[BEAT' in l and 'pr@=' in l:
            m = re.search(r'pr@=\(([\d.]+),([\d.]+)\)', l)
            if m:
                pr.append((fno, float(m.group(1)), float(m.group(2))))

    if len(mv) < 3:
        return None

    # 锁死段检测
    locks = []
    i = 0
    while i < len(mv):
        j = i + 1
        while j < len(mv) and abs(mv[j][1] - mv[i][1]) <= SAME and abs(mv[j][2] - mv[i][2]) <= SAME:
            j += 1
        if j - i >= RUN:
            f0, f1 = mv[i][0], mv[j - 1][0]
            # 该段内祭司位移
            seg = [p for p in pr if f0 - 150 <= p[0] <= f1 + 150]
            moved = 0.0
            if len(seg) >= 2:
                xs = [p[1] for p in seg]; ys = [p[2] for p in seg]
                moved = ((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2) ** 0.5
            if moved < MOVE:
                locks.append((f0, f1, j - i, moved))
        i = j

    lock_frames = sum(b - a for a, b, _, _ in locks)
    priest_span = (pr[-1][0] - pr[0][0]) if len(pr) >= 2 else 1
    return dict(f=os.path.basename(f), win=win, pd=pd, tcl=tcl, endf=endf,
                nmv=len(mv), npr=len(pr),
                nlock=len(locks), lock_frames=lock_frames,
                maxlock=max([b - a for a, b, _, _ in locks], default=0),
                maxrep=max([n for _, _, n, _ in locks], default=0),
                frac=(lock_frames / priest_span if priest_span > 0 else 0.0))


def main(files):
    rows = []
    for f in files:
        for g in (glob.glob(f) if ('*' in f) else [f]):
            r = parse(g)
            if r:
                rows.append(r)
    if not rows:
        print('无样本'); return
    print('%-26s %-5s %6s %5s %6s %6s %6s %6s %6s' % (
        'file', '结果', '令数', '锁段', '锁帧', '最长锁', '最多重', '锁占比', 'endf'))
    for r in sorted(rows, key=lambda r: -r['frac']):
        res = '胜' if r['win'] else ('祭死' if r['pd'] else ('TC毁' if r['tcl'] else '超时/未'))
        print('%-26s %-5s %6d %5d %6d %6d %6d %5.0f%% %6d' % (
            r['f'], res, r['nmv'], r['nlock'], r['lock_frames'],
            r['maxlock'], r['maxrep'], 100 * r['frac'], r['endf']))
    # 分组统计
    print()
    print('%-6s %5s %8s %8s %8s %8s' % ('组', 'n', '锁帧中位', '锁占比中位', '锁段中位', '有锁比例'))
    for name, sel in (('胜', lambda r: r['win']),
                      ('祭死', lambda r: r['pd'] and not r['win']),
                      ('其它', lambda r: not r['win'] and not r['pd'])):
        s = [r for r in rows if sel(r)]
        if not s:
            continue
        print('%-6s %5d %8.0f %7.0f%% %8.0f %7.0f%%' % (
            name, len(s),
            statistics.median([r['lock_frames'] for r in s]),
            statistics.median([100 * r['frac'] for r in s]),
            statistics.median([r['nlock'] for r in s]),
            100.0 * sum(1 for r in s if r['nlock'] > 0) / len(s)))


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        args = ['base0_*_r0_*.ait', 'fix1_*_r0_*.ait']
    main(args)
