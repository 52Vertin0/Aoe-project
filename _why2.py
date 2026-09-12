# -*- coding: utf-8 -*-
"""在射程内却不起手：发现帧 vs 抵达帧 vs 闸状态（用 [BEAT] 的 pr@ 精确算 sD0）"""
import re,glob,sys
WS={'map':(11,86),'map1':(93,11),'map2':(24,6),'map3':(82,20)}
BL=35.777
def tag_of(fn):
    for m in WS:
        if f'_{m}_' in fn: return m
    return None
CAND=sys.argv[1:] if len(sys.argv)>1 else None
for fn in sorted(glob.glob('fixI_*_r0_*.ait')):
    t=open(fn,encoding='utf-8',errors='replace').read()
    if t.count('[BEAT')<5: continue
    if 'converting Siege Workshop' in t: continue
    g=tag_of(fn); ws=WS[g]
    name=fn.replace('fixI_','').replace('.ait','')
    if CAND and name not in CAND: continue
    # 发现帧：从 ait 行取 frame 字段
    found=None
    for L in t.splitlines():
        if 'Enemy Siege Workshop found at' in L:
            m=re.search(r'\| (\d+) \|',L)
            if m: found=int(m.group(1)); break
    mca=re.search(r'Counterattack! Frame=(\d+)',t)
    caf=int(mca.group(1)) if mca else None
    # 逐桶 sD0（距 (ws+1)）
    ser=[]
    for L in t.splitlines():
        if '[BEAT' not in L: continue
        mf=re.search(r'\[BEAT f=(\d+) b=(\d+)\]',L)
        if not mf: continue
        f=int(mf.group(1))
        mp=re.search(r'pr@=\(([-\d.]+),([-\d.]+)\)',L)
        if not mp: continue
        x,y=float(mp.group(1)),float(mp.group(2))
        if x<=0 and y<=0: ser.append((f,None,None)); continue
        sD0=((x-(ws[0]+1))**2+(y-(ws[1]+1))**2)**.5
        mh=re.search(r'pr=\(sn-?\d+ st(-?\d+) hp(\d+)/\d+ ccd(-?\d+)\)',L)
        ser.append((f,sD0,(int(mh.group(2))/100.0 if mh else None)))
    valid=[s for s in ser if s[1] is not None]
    if not valid: continue
    best=min(valid,key=lambda s:s[1])
    inr=[s for s in valid if s[1]<=12.0]
    out=[]
    for tag in ['Priest ADVANCE','PRIEST-ESCAPE A','PRIEST-ESCAPE B','PRIEST-ESCAPE-BREAK','[SIEGE-WAIT]','[SIEGE-HOLD]']:
        fs=[int(m.group(1)) for m in re.finditer(re.escape(tag)+r'[^\n]*?f=(\d+)',t)]
        out.append(f'{tag.split()[-1]}={len(fs)}')
    print(f'--- {name} ({g}) ---')
    print(f'   发现武器厂帧={found}  反攻起点={caf}  最近 sD0={best[1]:.2f} @f={best[0]} (hp={best[2]})')
    f0=f'{inr[0][0]}(sD0={inr[0][1]:.2f},hp={inr[0][2]})' if inr else '-'
    print(f'   进入 12 格内的桶数={len(inr)}  首个={f0}  末个={inr[-1][0] if inr else "-"}')
    if inr:
        # 是否在发现之后才进圈
        print(f'   首个进圈 vs 发现: ' + ('发现之后' if found and inr[0][0]>=found else '发现之前'))
    print('   '+' '.join(out))
