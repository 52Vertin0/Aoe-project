# -*- coding: utf-8 -*-
"""反攻期 Mil / Frm / 资源 的时间曲线（按图分组，取中位）"""
import re,glob,statistics as st,collections
WS={'map':(11,86),'map1':(93,11),'map2':(24,6),'map3':(82,20)}
def tag_of(fn):
    for m in WS:
        if f'_{m}_' in fn: return m
    return None
GRID=[0,1500,3000,4500,6000,7500,9000,10500,12000]
data=collections.defaultdict(lambda: collections.defaultdict(list))
kinds=collections.defaultdict(lambda: collections.Counter())
for fn in sorted(glob.glob('fixI_*_r0_*.ait')):
    t=open(fn,encoding='utf-8',errors='replace').read()
    if t.count('[BEAT')<5: continue
    g=tag_of(fn)
    mca=re.search(r'Counterattack! Frame=(\d+)',t)
    if not mca: continue
    caf=int(mca.group(1))
    if '被祭司转换,归属阵营1->0' in t: k='W'
    elif 'DEFEAT: Priest killed' in t: k='P'
    else: k='T'
    kinds[g][k]+=1
    series=[]
    for L in t.splitlines():
        if '[BEAT' not in L: continue
        mf=re.search(r'\[BEAT f=(\d+)',L)
        if not mf: continue
        f=int(mf.group(1))
        if f<caf: continue
        mm=re.search(r'Mil=(\d+)',L); mfr=re.search(r'Frm=(\d+)',L)
        mr=re.search(r'Fd=(\d+) Wd=(\d+) St=(\d+) Gd=(\d+)',L)
        mh=re.search(r'pr=\(sn-?\d+ st(-?\d+) hp(\d+)/\d+',L)
        series.append((f-caf, int(mm.group(1)) if mm else None,
                       int(mfr.group(1)) if mfr else None,
                       tuple(int(x) for x in mr.groups()) if mr else None,
                       int(mh.group(1)) if mh else None, int(mh.group(2)) if mh else None))
    for off in GRID:
        cand=[x for x in series if off<=x[0]<off+1500]
        if not cand: continue
        def M(v): return st.median(v) if v else float('nan')
        data[g][off].append((M([x[1] for x in cand if x[1] is not None]),
                             M([x[2] for x in cand if x[2] is not None]),
                             M([x[3][3] for x in cand if x[3]]),
                             M([x[5] for x in cand if x[5] is not None and x[5]>=0])))
print('=== 反攻起点后的中位轨迹（Mil / Frm / Gold / hp）===') 
print(f'{"图":<6}{"结局":<22}' + ''.join(f'{("+%d"%o):>21}' for o in GRID))
for g in ['map','map1','map2','map3']:
    print(f'{g:<6}{str(dict(kinds[g])):<22}')
    row=[]
    for off in GRID:
        v=data[g][off]
        if not v: row.append('-'); continue
        row.append(f'{st.median([x[0] for x in v]):.0f}/{st.median([x[1] for x in v]):.0f}/{st.median([x[2] for x in v]):.0f}/{st.median([x[3] for x in v]):.0f}')
    print(f'{"":<28}' + ''.join(f'{r:>21}' for r in row))
    print()
print('(格式 Mil/Frm/Gold/hp，每列 = 该 1500 帧窗口内的中位)')
