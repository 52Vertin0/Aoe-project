# -*- coding: utf-8 -*-
"""GIVEUP 现场解剖：GIVEUP 之后祭司到底有没有在动？为什么还是推不进去？"""
import re, glob, os

BL = 35.777
WS = {'map': (11, 86), 'map1': (93, 11), 'map2': (24, 6), 'map3': (82, 20)}

def hdrmove(fn):
    t = open(fn, encoding='utf-8', errors='replace').read()
    g = re.search(r'\[PRIEST-ESCAPE-GIVEUP f=(\d+)\]', t)
    gup = int(g.group(1)) if g else -1
    ca = re.search(r'Counterattack! Frame=(\d+)', t)
    caf = int(ca.group(1)) if ca else -1
    # 局末（最后一条 [BEAT] 帧）
    bfs = [int(m.group(1)) for m in re.finditer(r'\[BEAT f=(\d+)', t)]
    endf = max(bfs) if bfs else -1
    # 祭司移动令
    mv = [int(m.group(1)) for m in re.finditer(r'\| (\d+) \|.*HumanMove:祭司', t)]
    mv_after = [f for f in mv if f > gup]
    # [LC-DBG] 序列
    lc = []
    for L in t.splitlines():
        if 'LC-DBG' not in L: continue
        m = re.search(r'\| (\d+) \|', L)
        m2 = re.search(r'dS=([-\d.]+)', L)
        m3 = re.search(r'gT=(\d+)', L)
        m4 = re.search(r'hp=([-\d.]+)', L)
        m5 = re.search(r'seen=(\d+)', L)
        if m and m2:
            lc.append((int(m.group(1)), float(m2.group(1)), int(m3.group(1)) if m3 else -1,
                       float(m4.group(1)) if m4 else -1, int(m5.group(1)) if m5 else -1))
    lc_after = [x for x in lc if x[0] > gup]
    # [BEAT] 的 pm cnt / pr@ 序列（GIVEUP 之后）
    be = []
    for L in t.splitlines():
        if '[BEAT f=' not in L: continue
        m = re.search(r'\[BEAT f=(\d+)', L)
        mc = re.search(r'pm f(\d+) ca(\d+) h(\d+) cnt(\d+) o(\d+)', L)
        mp = re.search(r'pr@=\(([-\d.]+),([-\d.]+)\)', L)
        mm = re.search(r'Mil=(\d+)', L)
        if m:
            be.append((int(m.group(1)),
                       tuple(int(x) for x in mc.groups()) if mc else None,
                       (float(mp.group(1)), float(mp.group(2))) if mp else None,
                       int(mm.group(1)) if mm else -1))
    be_after = [x for x in be if x[0] > gup]
    return dict(fn=os.path.basename(fn), gup=gup, caf=caf, endf=endf, mv=len(mv), mv_after=len(mv_after),
                lc=lc, lc_after=lc_after, be_after=be_after, t=t)

print('=' * 112)
print('§A GIVEUP 之后：还有多少时间 / 还有没有移动令 / dS 有没有变化')
print('=' * 112)
print(f'{"局":<24}{"CA":>7}{"GIVEUP":>8}{"局末":>7}{"剩余帧":>7}{"剩分钟":>7}{"移动令总":>9}{"GIVEUP后":>9}')
rows = []
for fn in sorted(glob.glob('fixJ_*.ait')):
    r = hdrmove(fn)
    if r['gup'] < 0: continue
    rows.append(r)
    rem = r['endf'] - r['gup']
    print(f'{r["fn"]:<24}{r["caf"]:>7}{r["gup"]:>8}{r["endf"]:>7}{rem:>7}{rem/1500:>7.1f}{r["mv"]:>9}{r["mv_after"]:>9}')

print()
print('=' * 112)
print('§B 逐局：GIVEUP 之后的 [LC-DBG]（dS=距武器厂格数 / gT=全局敌塔 / hp / seen）')
print('=' * 112)
for r in rows:
    print(f'--- {r["fn"]}  GIVEUP@{r["gup"]}  （GIVEUP 前最后 2 条 / 后全部 {len(r["lc_after"])} 条）---')
    pre = [x for x in r['lc'] if x[0] <= r['gup']][-2:]
    for f, ds, gt, hp, sn in pre:
        print(f'    f={f:>6} dS={ds:>6.1f} gT={gt:>2} hp={hp:>5.2f} seen={sn:>2}   ←pre')
    for f, ds, gt, hp, sn in r['lc_after'][:12]:
        print(f'    f={f:>6} dS={ds:>6.1f} gT={gt:>2} hp={hp:>5.2f} seen={sn:>2}')
    if len(r['lc_after']) > 12:
        print(f'    ...（略 {len(r["lc_after"])-12} 条）')
        for f, ds, gt, hp, sn in r['lc_after'][-4:]:
            print(f'    f={f:>6} dS={ds:>6.1f} gT={gt:>2} hp={hp:>5.2f} seen={sn:>2}   ←末')
    print()

print('=' * 112)
print('§C GIVEUP 之后的 [BEAT] 序列（pm 五列 + 祭司位置 + Mil）')
print('=' * 112)
for r in rows:
    print(f'--- {r["fn"]} ---')
    for f, pm, pos, mil in r['be_after'][:14]:
        p = '' if not pos else (f'({pos[0]:5.1f},{pos[1]:5.1f})')
        print(f'    f={f:>6} Mil={mil:>3} pm={pm if pm else "-"}  pr@{p}')
    if len(r['be_after']) > 14:
        print(f'    ...（略 {len(r["be_after"])-14} 条）')
    print()
