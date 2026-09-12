import re,glob,bisect,statistics as st
CONV=340
def load(fn):
    beats,convs=[],[]
    for L in open(fn,encoding='utf-8',errors='replace'):
        if '[BEAT' in L:
            m=re.search(r'\[BEAT f=(\d+) b=(\d+)\]',L)
            if not m: continue
            pr=re.search(r'pr@=\(([-\d.]+),([-\d.]+)\)',L)
            if not pr: continue
            hp=re.search(r'pr=\(sn(-?\d+) st(-?\d+) hp(\d+)/(\d+) ccd(-?\d+)\)',L)
            pm=re.search(r'pm f(\d+) ca(\d+) h(\d+) cnt(\d+) o(\d+)',L)
            beats.append(dict(f=int(m.group(1)),x=float(pr.group(1)),y=float(pr.group(2)),
                              hp=int(hp.group(3)) if hp else None,
                              ccd=int(hp.group(5)) if hp else None,
                              pm=[int(pm.group(i)) for i in range(1,6)] if pm else None))
        if 'converting Siege Workshop' in L:
            m=re.search(r'converting Siege Workshop! f=(\d+)',L)
            if m: convs.append(int(m.group(1)))
    return beats,convs
def oc(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    return 'T'
detail=[]
for fn in sorted(glob.glob('fixI_*_r0_*.ait')):
    t=open(fn,encoding='utf-8',errors='replace').read()
    beats,convs=load(fn)
    if not beats or not convs: continue
    bmap={b['f']:b for b in beats}; fk=sorted(bmap)
    F=convs[0]; i=bisect.bisect_left(fk,F)
    seg=[bmap[k] for k in fk[i:i+60] if k<=F+CONV]
    if not seg: continue
    x0,y0=seg[0]['x'],seg[0]['y']
    mv=max(((b['x']-x0)**2+(b['y']-y0)**2)**0.5 for b in seg)
    cnt=sum((b['pm'][3] if b['pm'] else 0) for b in seg)
    hp0=seg[0]['hp']; hpm=min([b['hp'] for b in seg if b['hp'] is not None] or [99])
    detail.append((fn,oc(t),F,mv,cnt,hp0,hpm,seg[-1]['ccd'],len(convs)))
print('=== 阈值扫描：首起手窗口位移 分档 × 结局 ===')
for th in (2,5,10,20,40,60):
    big=[d for d in detail if d[3]>th]
    print(f'  位移>{th:>3}格: n={len(big):<3} 胜={sum(1 for d in big if d[1]=="W"):<3} 祭死={sum(1 for d in big if d[1]=="P"):<3} 超时={sum(1 for d in big if d[1]=="T")}')
print()
print('=== 逐结局：首起手窗口位移 ===')
for k in ['W','P','T']:
    v=sorted([d[3] for d in detail if d[1]==k])
    if not v: continue
    print(f'  {k}: n={len(v):<3} 中位={st.median(v):5.1f}  P75={v[int(len(v)*0.75)]:6.1f}  P90={v[int(len(v)*0.9)]:6.1f}  max={v[-1]:6.1f}')
print()
print('=== 起手后失败的局全部明细 ===')
for d in sorted([d for d in detail if d[1]!='W'],key=lambda x:-x[3]):
    print(f'  {d[0]:<24} {"祭死" if d[1]=="P" else "超时"} 首起手f={d[2]:<6} 位移={d[3]:>5.1f} cnt={d[4]:<3} hp {d[5]}->{d[6]:<3} 起手次数={d[8]}')
