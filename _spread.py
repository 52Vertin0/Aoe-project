# -*- coding: utf-8 -*-
"""[SPREAD] 反攻期军队空间分布分析（纵向 + 横向）
用法: python _spread.py <tag> [tag2 ...]

字段含义（单位=格）：
  纵向（沿 我方TC→敌方目标 轴）
    n    军队数(非祭司)      nH  还窝在 TC 25 格内(新兵/未参战)
    span p90-p10 队形跨度    gap 排序后相邻投影最大空档(纵向断层), gL=该空档左侧人数
    p50  主力投影  pmax 前锋投影
  横向（垂直推进轴）★ "被海分成左右两股" 的度量
    latSpan 横向展宽 p90-p10
    latGap  横向排序后最大空档  ← 两股之间的空隙
    latL    该空档左侧人数      ← latL/n 接近 0.5 = 两股人数相当 = 真两波
  祭司
    lead  祭司 - 主力(p50)      leadF 祭司 - 前锋(pmax)  >0 = 祭司独自暴露
"""
import re, glob, os, sys, statistics as st, collections

NUM = r'(-?[\d.]+)'
KEYS = ['n', 'nH', 'ax', 'span', 'gap', 'gL', 'gAt', 'latSpan', 'latGap', 'latL', 'latAt',
        'nM', 'nR', 'medM', 'medR', 'dmax', 'p50', 'pmax', 'lead', 'leadF']


def g1(s, k):
    m = re.search(k + r'=' + NUM, s)
    return float(m.group(1)) if m else None


def load(tag):
    games = []
    for fn in sorted(glob.glob(f'{tag}_*_r0_*.ait')):
        t = open(fn, encoding='utf-8', errors='replace').read()
        if t.count('[BEAT') < 5:
            continue
        mp = os.path.basename(fn).replace(tag + '_', '').split('_r0_')[0]
        win = '被祭司转换,归属阵营1->0' in t
        pd = 'DEFEAT: Priest killed' in t
        rows = []
        for L in t.splitlines():
            if '[SPREAD' not in L:
                continue
            r = {k: g1(L, k) for k in KEYS}
            if r['n'] is None or r['span'] is None:
                continue
            rows.append(r)
        if not rows:
            continue
        games.append(dict(mp=mp, win=win, pd=pd, rows=rows, fn=os.path.basename(fn)[:-4]))
    return games


def med(v):
    v = [x for x in v if x is not None]
    return st.median(v) if v else None


def gmed(g, key):
    """局内中位数"""
    return med([r[key] for r in g['rows']])


def arm_med(gs, key):
    """臂级中位数（先每局取中位数，再取中位数）"""
    return med([gmed(g, key) for g in gs])


def line(lab, n, extra=''):
    print(f'  {lab:<22} n={n:>3}{extra}')


def show(tag):
    gs = load(tag)
    if not gs:
        print(f'  {tag}: 无数据')
        return None
    print(f'===== {tag} =====  局={len(gs)}   胜={sum(1 for g in gs if g["win"])}'
          f' ({100*sum(1 for g in gs if g["win"])/len(gs):.1f}%)')
    print('  --- 臂级中位（每局先取中位）---')
    print(f'    n={arm_med(gs,"n"):.0f}  nH(在基地)={arm_med(gs,"nH") or 0:.0f}'
          f'   纵向 span={arm_med(gs,"span"):.1f}  gap={arm_med(gs,"gap"):.1f}')
    lat = arm_med(gs, 'latSpan')
    if lat is not None:
        print(f'   横向 latSpan={lat:.1f}  latGap={arm_med(gs,"latGap"):.1f}')
    print(f'   dmax={arm_med(gs,"dmax"):.1f}   lead={arm_med(gs,"lead"):+.1f}   leadF={arm_med(gs,"leadF"):+.1f}')

    # —— 两波判据：横向空档 ≥12 格 且 左侧占比 ∈[0.25,0.75] ——
    rows = [r for g in gs for r in g['rows'] if r.get('latGap') is not None and r['n']]
    if rows:
        two = [r for r in rows if r['latGap'] >= 12.0 and 0.25 <= r['latL'] / r['n'] <= 0.75]
        print(f'   ★【两波】判据(latGap>=12 且 0.25<=latL/n<=0.75): {len(two)}/{len(rows)} 采样行'
              f' ({100*len(two)/len(rows):.1f}%)')
        per = collections.Counter()
        for g in gs:
            rr = [r for r in g['rows'] if r.get('latGap') is not None and r['n']]
            if rr and any(r['latGap'] >= 12.0 and 0.25 <= r['latL'] / r['n'] <= 0.75 for r in rr):
                per[g['win']] += 1
        print(f'     局级：胜局 {per[True]} 局出现过 / 负局 {per[False]} 局出现过')
    print()
    return dict(tag=tag, gs=gs)


if __name__ == '__main__':
    tags = sys.argv[1:] or ['sprd2']
    res = {}
    for t in tags:
        r = show(t)
        if r:
            res[t] = r
    gs = res.get(tags[0], {}).get('gs') or []
    if not gs:
        sys.exit()

    print('=== 分图（纵向 / 横向 / 祭司）===')
    bym = collections.defaultdict(list)
    for g in gs:
        bym[g['mp']].append(g)
    print(f'  {"图":<6}{"n":>3}{"胜":>6}  {"span":>6}{"gap":>6}{"nH":>5}{"latSpan":>8}{"latGap":>7}{"dmax":>6}{"leadF":>7}')
    for mp in sorted(bym):
        s = bym[mp]
        w = sum(1 for g in s if g['win'])
        print(f'  {mp:<6}{len(s):>3}{w:>3}({100*w/len(s):3.0f}%)'
              f'  {arm_med(s,"span") or 0:6.1f}{arm_med(s,"gap") or 0:6.1f}{arm_med(s,"nH") or 0:5.0f}'
              f'{arm_med(s,"latSpan") or 0:8.1f}{arm_med(s,"latGap") or 0:7.1f}'
              f'{arm_med(s,"dmax") or 0:6.1f}{arm_med(s,"leadF") or 0:+7.1f}')
    print()

    print('=== 胜 / 负 分层（全局）===')
    for lab, cond in [('胜局', lambda g: g['win']), ('负-祭司死', lambda g: g['pd']),
                      ('负-其它', lambda g: (not g['win']) and (not g['pd']))]:
        s = [g for g in gs if cond(g)]
        if len(s) < 3:
            continue
        print(f'  {lab:<10} n={len(s):>3}  span={arm_med(s,"span"):5.1f}  gap={arm_med(s,"gap"):5.1f}'
              f'  latSpan={arm_med(s,"latSpan") or 0:5.1f}  latGap={arm_med(s,"latGap") or 0:5.1f}'
              f'  dmax={arm_med(s,"dmax"):5.1f}  leadF峰值={med([max([r["leadF"] for r in g["rows"] if r["leadF"] is not None and r["leadF"]>-900] or [0]) for g in s]):+6.1f}')
    print()

    print('=== 同图内部 胜 vs 负（最强对照：排除图间差异）===')
    for mp in sorted(bym):
        s = bym[mp]
        for lab, cond in [('胜', lambda g: g['win']), ('负', lambda g: not g['win'])]:
            ss = [g for g in s if cond(g)]
            if len(ss) < 3:
                continue
            print(f'  {mp:<5}{lab} n={len(ss):>2}  span={arm_med(ss,"span"):5.1f}  gap={arm_med(ss,"gap"):5.1f}'
                  f'  latSpan={arm_med(ss,"latSpan") or 0:5.1f}  latGap={arm_med(ss,"latGap") or 0:5.1f}'
                  f'  dmax={arm_med(ss,"dmax"):5.1f}  nH={arm_med(ss,"nH") or 0:4.0f}')
        print()
