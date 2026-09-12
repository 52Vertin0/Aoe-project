# -*- coding: utf-8 -*-
"""金工/木工分工轨迹：解析 'ECO | ... || workers F W G S || ...' 自检行（每 600 帧）。
用法: python _eco_workers.py <tag> [tag2...]
输出: 按时段（铜器后 13500+, 反攻期 33000+）统计金工/木工/存量 中位数，以及 goldRich 命中率。
"""
import re, glob, os, sys, statistics as st, collections

ECO = re.compile(
    r'\[BEAT[^\]]*\]?|ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+) '
    r'\|\| goldRich:(\d) woodStop:(\d) stoneStop:(\d) foodStop:(\d) woodTarget:(\d+)')
FR = re.compile(r'^\d\d:\d\d:\d\d+\s*\|\s*(\d+)\s*\|')

def med(xs):
    return st.median(xs) if xs else float('nan')

for tag in sys.argv[1:]:
    # 桶: [(phase, F,W,G, S, Gd,Wd,Fd, goldRich)]
    buckets = collections.defaultdict(list)  # phase -> list of dict
    ngames = 0
    for fn in sorted(glob.glob(f'{tag}_*_r0_*.ait')):
        t = open(fn, encoding='utf-8', errors='replace').read()
        if t.count('[BEAT') < 5:
            continue
        ngames += 1
        cur_f = 0
        for L in t.splitlines():
            mfr = FR.match(L)
            if mfr:
                cur_f = int(mfr.group(1))
            if '|| workers F' not in L:
                continue
            m = ECO.search(L)
            if not m:
                continue
            fd, wd, st_, gd, F, W, G, S, gr, ws, ss, fs, wt = map(int, m.groups())
            if cur_f < 13500:
                ph = 'W1-2(<13.5k)'
            elif cur_f < 21000:
                ph = 'W2-3(13.5-21k)'
            elif cur_f < 33000:
                ph = 'W3(21-33k)'
            else:
                ph = '反攻(33k+)'
            buckets[ph].append(dict(F=F, W=W, G=G, S=S, Gd=gd, Wd=wd, Fd=fd, gr=gr, fs=fs))
    print(f'==== {tag}  ({ngames} 局, 全图) ====')
    print(f'{"时段":<18}{"样本":>5}{"F食":>5}{"W木":>5}{"G金":>5}{"S石":>5}{"Gd中":>6}{"Wd中":>6}{"Fd中":>6}{"goldRich%":>10}{"foodStop%":>10}')
    for ph in ['W1-2(<13.5k)', 'W2-3(13.5-21k)', 'W3(21-33k)', '反攻(33k+)']:
        rows = buckets.get(ph, [])
        if not rows:
            continue
        print(f'{ph:<18}{len(rows):>5}{med([r["F"] for r in rows]):>5.1f}{med([r["W"] for r in rows]):>5.1f}'
              f'{med([r["G"] for r in rows]):>5.1f}{med([r["S"] for r in rows]):>5.1f}'
              f'{med([r["Gd"] for r in rows]):>6.0f}{med([r["Wd"] for r in rows]):>6.0f}{med([r["Fd"] for r in rows]):>6.0f}'
              f'{100*sum(r["gr"] for r in rows)/len(rows):>9.0f}%{100*sum(r["fs"] for r in rows)/len(rows):>9.0f}%')
    # 金工分布（W2 之后）
    late = buckets.get('W2-3(13.5-21k)', []) + buckets.get('W3(21-33k)', []) + buckets.get('反攻(33k+)', [])
    if late:
        dist = collections.Counter(r['G'] for r in late)
        print('  金工人数分布(13.5k+): ' + ' '.join(f'G{k}={v}' for k, v in sorted(dist.items())))
        distw = collections.Counter(r['W'] for r in late)
        print('  木工人数分布(13.5k+): ' + ' '.join(f'W{k}={v}' for k, v in sorted(distw.items())))
    print()
