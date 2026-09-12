# -*- coding: utf-8 -*-
"""反攻起点 → 发现武器厂【之前】的窗口：祭司净位移方向 + 移动令条数"""
import re,glob,statistics as st
WS={'map':(11,86),'map1':(93,11),'map2':(24,6),'map3':(82,20)}
ENEMY={'map':(11,86),'map1':(93,11),'map2':(24,6),'map3':(82,20)}
BL=35.777
def tag_of(fn):
    for m in WS:
        if f'_{m}_' in fn: return m
    return None
rows=[]
for fn in sorted(glob.glob('fixI_*_r0_*.ait')):
    t=open(fn,encoding='utf-8',errors='replace').read()
    if t.count('[BEAT')<5: continue
    mca=re.search(r'Counterattack! Frame=(\d+)',t)
    if not mca: continue
    caf=int(mca.group(1)); g=tag_of(fn); ws=WS[g]
    mf=re.search(r'\| (\d+) \| black \| 0 \| .*Enemy Siege Workshop found at',t)
    fws=int(mf.group(1)) if mf else None
    # 窗口 = [caf, fws) ；若未发现则到 BEAT 末尾
    fs=[int(m.group(1)) for m in re.finditer(r'\[BEAT f=(\d+)',t)]
    hi=fws if fws else max(fs)
    if hi<=caf: continue
    # 祭司轨迹（用 [BEAT] pr@）
    pts=[]
    for L in t.splitlines():
        if '[BEAT' not in L: continue
        m=re.search(r'\[BEAT f=(\d+)',L)
        if not m: continue
        f=int(m.group(1))
        if f<caf or f>=hi: continue
        mp=re.search(r'pr@=\(([-\d.]+),([-\d.]+)\)',L)
        if not mp: continue
        x,y=float(mp.group(1)),float(mp.group(2))
        if x<=0 and y<=0: continue
        pts.append((f,x,y))
    if len(pts)<2: continue
    d0=((pts[0][1]-ws[0])**2+(pts[0][2]-ws[1])**2)**.5
    d1=((pts[-1][1]-ws[0])**2+(pts[-1][2]-ws[1])**2)**.5
    # 移动令
    mv=0
    for L in t.splitlines():
        m=re.search(r'\| (\d+) \|.*HumanMove:祭司',L)
        if m and caf<=int(m.group(1))<hi: mv+=1
    if '被祭司转换,归属阵营1->0' in t: k='W'
    elif 'DEFEAT: Priest killed' in t: k='P'
    else: k='T'
    rows.append(dict(f=fn.replace('fixI_','').replace('.ait',''),g=g,k=k,caf=caf,fws=fws if fws else -1,
                     win=hi-caf,d0=d0,d1=d1,prog=d0-d1,mv=mv,nb=len(pts),
                     hp0=None))
print('=== 反攻起点→发现武器厂之前：祭司净位移（正=朝武器厂靠近）===')
print(f'{"局":<14}{"图":<6}{"结局":<3}{"窗口帧":>7}{"起点dWS":>8}{"末dWS":>7}{"净位移":>7}{"移动令":>7}{"桶数":>5}')
for r in sorted(rows,key=lambda r:r['k']+r['f']):
    print(f'{r["f"]:<14}{r["g"]:<6}{r["k"]:<3}{r["win"]:>7}{r["d0"]:>8.1f}{r["d1"]:>7.1f}{r["prog"]:>+7.1f}{r["mv"]:>7}{r["nb"]:>5}')
print()
print('=== 汇总：按结局 ===')
for k in ['W','P','T']:
    s=[r for r in rows if r['k']==k]
    if not s: continue
    print(f'  {k}: n={len(s):>2}  净位移中位={st.median([r["prog"] for r in s]):>+6.1f} 格  移动令中位={st.median([r["mv"] for r in s]):>5.0f}  窗口中位={st.median([r["win"] for r in s]):>6.0f} 帧')
print()
print('=== 净位移分档 × 结局（全 %d 局）==='%len(rows))
import collections
for lo,hi in [(-999,-20),(-20,-2),(-2,2),(2,20),(20,999)]:
    s=[r for r in rows if lo<=r['prog']<hi]
    if s: print(f'  净位移[{lo},{hi}) n={len(s):>2} '+str(collections.Counter(x["k"] for x in s)))
