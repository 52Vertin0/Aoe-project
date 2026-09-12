# -*- coding: utf-8 -*-
"""
_convwin.py —— 量化「起手后施法窗口」被移动令打断的程度。

口径（全部来自 [BEAT] 桶采样，免疫 frame 跳号）：
  起手时刻 = 日志 "Priest converting Siege Workshop! f=F"（early / front 两条路径都打这条）
  施法窗口 = [F, F+CONV_FRAMES]（默认 340，转化实测 ~310 帧）
  打断判据 = 窗口内祭司【位置位移 > MOVE_BL】且【窗口末仍未收编】
  收编判据 = 游戏含 '被祭司转换,归属阵营1->0'

用法: python _convwin.py fixI [CONV_FRAMES] [MOVE_BL]
"""
import re, sys, glob, statistics as st, collections

CONV_FRAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 340
MOVE_BL = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0


def load(fn):
    beats, convs = [], []
    for L in open(fn, encoding='utf-8', errors='replace'):
        if '[BEAT' in L:
            m = re.search(r'\[BEAT f=(\d+) b=(\d+)\]', L)
            if not m:
                continue
            pr = re.search(r'pr@=\(([-\d.]+),([-\d.]+)\)', L)
            hp = re.search(r'pr=\(sn(-?\d+) st(-?\d+) hp(\d+)/(\d+)', L)
            pm = re.search(r'pm f(\d+) ca(\d+) h(\d+) cnt(\d+) o(\d+)', L)
            if not pr:
                continue
            beats.append(dict(
                f=int(m.group(1)), b=int(m.group(2)),
                x=float(pr.group(1)), y=float(pr.group(2)),
                hp=int(hp.group(3)) if hp else None,
                st=int(hp.group(2)) if hp else None,
                ccd=int(hp.group(4)) if hp else None,
                pm=[int(pm.group(i)) for i in range(1, 6)] if pm else None))
        if 'converting Siege Workshop' in L:
            m = re.search(r'converting Siege Workshop! f=(\d+)', L)
            if m:
                convs.append(int(m.group(1)))
    return beats, convs


def outcome(t):
    if '被祭司转换,归属阵营1->0' in t:
        return 'W'
    if 'DEFEAT: Priest killed' in t:
        return 'P'
    return 'T'


rows = []
for fn in sorted(glob.glob(f'{sys.argv[1]}_*_r0_*.ait')):
    t = open(fn, encoding='utf-8', errors='replace').read()
    beats, convs = load(fn)
    if not beats:
        continue
    oc = outcome(t)
    bmap = {b['f']: b for b in beats}
    fkeys = sorted(bmap)
    import bisect
    ev = []
    for F in convs:
        i = bisect.bisect_left(fkeys, F)
        seg = [bmap[k] for k in fkeys[i:i + 60] if k <= F + CONV_FRAMES]
        if not seg:
            continue
        x0, y0 = seg[0]['x'], seg[0]['y']
        dx = max(abs(b['x'] - x0) for b in seg)
        dy = max(abs(b['y'] - y0) for b in seg)
        move = (dx * dx + dy * dy) ** 0.5
        cnt = sum((b['pm'][3] if b['pm'] else 0) for b in seg)
        hp0 = seg[0]['hp']
        hpm = min([b['hp'] for b in seg if b['hp'] is not None] or [99])
        ev.append(dict(F=F, move=move, cnt=cnt, hp0=hp0, hpm=hpm, n=len(seg)))
    rows.append((fn, oc, ev))

print(f'{"局":<24}{"结局":<4}{"起手数":>6}{"窗口位移中位":>12}{"cnt令中位":>10}  窗口 hp 起点->最低')
tot_int = 0        # 有起手且被判"位移打断"的窗口数
tot_win_after = 0  # 起手后收编（=胜）的窗口数
for fn, oc, ev in rows:
    if not ev:
        print(f'{fn:<24}{oc:<4}{0:>6}{"—":>12}{"—":>10}')
        continue
    mv = st.median([e["move"] for e in ev])
    ct = st.median([e["cnt"] for e in ev])
    detail = ' '.join(f'{e["hp0"]}->{e["hpm"]}(d{e["move"]:.0f})' for e in ev[:4])
    print(f'{fn:<24}{oc:<4}{len(ev):>6}{mv:>12.1f}{ct:>10.0f}  {detail}')
    for e in ev:
        if e['move'] > MOVE_BL:
            tot_int += 1

w = [r for r in rows if r[1] == 'W']
cons_w = sum(len(r[2]) for r in w)
print()
print(f'=== 汇总（{sys.argv[1]}）===')
print(f'  局数={len(rows)}  胜={len(w)}  有起手的局={sum(1 for r in rows if r[2])}  起手窗口总数={sum(len(r[2]) for r in rows)}')
print(f'  窗口内位移 > {MOVE_BL} 格的窗口数 = {tot_int}')
print(f'  胜局起手窗口数 = {cons_w}  ⇒ 平均每胜局起手 {cons_w/max(1,len(w)):.2f} 次')
for oc in ['W', 'P', 'T']:
    sub = [r for r in rows if r[1] == oc]
    ne = [len(r[2]) for r in sub]
    print(f'  {oc}: n={len(sub):<3} 有起手的局={sum(1 for x in ne if x>0):<3} 起手总次数={sum(ne):<3} 局均={sum(ne)/max(1,len(sub)):.2f}')
