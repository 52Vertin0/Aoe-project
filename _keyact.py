#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_keyact.py —— 【关键动作 × 关键前置量 × 结局】二维表。
  本工程「唯一胜利条件」的可观测等价物 = 引擎日志 `>> Priest converting Siege Workshop!`（起手），
  其几何前提 = 祭司距武器厂最近距离 `dmin`。
  用途：**任何改动之前先跑它**，判定力气该往哪儿投（见技能 aoe3-ai-behavior-attribution §2.38）。

用法: python _keyact.py base0 fix1 fix4          # 按 tag 前缀，自动扫 ${tag}_*_r0_*.ait
      python _keyact.py fix4_map_r0_1.ait ...    # 也可直接给文件
输出: ① 结局 × 是否起手 × 起手时各态势量中位数
      ② 起手 × dmin 四分桶的胜率（找出"必败"的那一格）
      ③ 未起手局明细（dmin 从小到大）
"""
import re, sys, glob, os, statistics as st

BL = 35.777
# 四图敌武器厂块坐标（来源：_maprev.py / OJ 反推；⚠ 换地图必须重跑 _maprev.py）
MAP_WS = {'map': (11, 86), 'map1': (93, 11), 'map2': (24, 6), 'map3': (82, 20)}


def which_map(basename):
    for k in ('map1', 'map2', 'map3'):
        if ('_' + k + '_') in basename:
            return k
    return 'map'


def parse(f):
    t = open(f, encoding='utf-8', errors='replace').read()
    b = os.path.basename(f)
    win = bool(re.search(r'攻城武器厂\(编号:\d+\)被祭司转换', t)) or \
        'VICTORY! Siege Workshop converted' in t
    pd = 'DEFEAT: Priest killed' in t
    tcl = bool(re.search(r'市镇中心\(编号:\d+\)被摧毁', t))
    fs = [int(x) for x in re.findall(r'\|\s*(\d+)\s*\|\s*(?:red|green|blue|black)', t)]
    endf = max(fs) if fs else 0
    res = '胜' if win else ('祭死' if pd else ('TC毁' if tcl else '超时'))

    # ★ 关键动作：起手（含三条下发点 path 标记）
    starts = []
    for m in re.finditer(
            r'>> Priest converting Siege Workshop! f=(\d+) d=([\d.]+) hp=([\d.]+) nearT=(-?[\d.]+) towers=(\d+)', t):
        starts.append(dict(f=int(m.group(1)), d=float(m.group(2)), hp=float(m.group(3)),
                           nearT=float(m.group(4)), towers=int(m.group(5))))

    ws = MAP_WS[which_map(b)]
    pr = [(float(x), float(y)) for x, y in re.findall(r'pr@=\(([\d.]+),([\d.]+)\)', t)
          if (float(x), float(y)) != (0.0, 0.0)]   # ⚠ 死亡后引擎清零 ⇒ 剔除 (0,0) 哨兵
    dmin = min(((x - ws[0]) ** 2 + (y - ws[1]) ** 2) ** 0.5 for x, y in pr) if pr else 999.0

    return dict(f=b, res=res, nst=len(starts), starts=starts, dmin=dmin, endf=endf)


def main(args):
    files = []
    for a in args:
        if '*' in a or os.path.isfile(a):
            files += glob.glob(a)
        else:
            files += sorted(glob.glob(a + '_*_r0_*.ait'))
    rows = [r for r in (parse(f) for f in sorted(set(files))) if r]
    if not rows:
        print('无样本'); return

    print('=== ① 结局 × 关键动作 ===')
    print('%-5s %5s %8s %12s %13s %12s %12s' % (
        '结局', 'n', '有起手比例', '起手次数中位', '起手时hp中位', '起手nearT中位', '距WS中位'))
    for r_ in ('胜', '祭死', '超时', 'TC毁'):
        s = [x for x in rows if x['res'] == r_]
        if not s:
            continue
        hps = [a['hp'] for x in s for a in x['starts']]
        nts = [a['nearT'] for x in s for a in x['starts'] if a['nearT'] >= 0]
        print('%-5s %5d %7.0f%% %12.1f %13s %13s %12.1f' % (
            r_, len(s), 100 * sum(1 for x in s if x['nst'] > 0) / len(s),
            st.median([x['nst'] for x in s]),
            ('%.2f' % st.median(hps)) if hps else '—',
            ('%.1f' % st.median(nts)) if nts else '—',
            st.median([x['dmin'] for x in s])))

    print()
    print('=== ② 关键动作 × 前置量（★ 找"必败"格） ===')
    print('%-22s %5s %5s %7s' % ('桶', 'n', '胜', '胜率'))
    for lbl, sel in (('起手 & dmin<12', lambda x: x['nst'] > 0 and x['dmin'] < 12),
                     ('起手 & dmin>=12', lambda x: x['nst'] > 0 and x['dmin'] >= 12),
                     ('无起手 & dmin<12', lambda x: x['nst'] == 0 and x['dmin'] < 12),
                     ('无起手 & dmin>=12', lambda x: x['nst'] == 0 and x['dmin'] >= 12)):
        s = [x for x in rows if sel(x)]
        w = sum(1 for x in s if x['res'] == '胜')
        print('%-22s %5d %5d %6.0f%%' % (lbl, len(s), w, 100 * w / len(s) if s else 0))

    print()
    print('=== ③ 未起手局明细（按 dmin 升序；这些局按 ② 必败） ===')
    bad = sorted([x for x in rows if x['nst'] == 0], key=lambda x: x['dmin'])
    for x in bad:
        print('  %-26s %-4s dmin=%6.1f endf=%d' % (x['f'], x['res'], x['dmin'], x['endf']))
    print('  n=%d' % len(bad))


if __name__ == '__main__':
    main(sys.argv[1:] or ['base0', 'fix1'])
