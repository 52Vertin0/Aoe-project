# -*- coding: utf-8 -*-
"""从未起手的局：祭司在反攻段的状态剖面（hp / dS / pm 构成 / 反攻段时长）"""
import re,glob,statistics as st
WS={'map':(11,86),'map1':(93,11),'map2':(24,6),'map3':(82,20)}
def tag_of(fn):
    for m in WS:
        if f'_{m}_' in fn: return m
    return None
rows=[]
for fn in sorted(glob.glob('fixI_*_r0_*.ait')):
    t=open(fn,encoding='utf-8',errors='replace').read()
    mc=re.search(r'Counterattack! Frame=(\d+)',t)
    if not mc: continue
    if 'converting Siege Workshop' in t: continue        # 只看从未起手
    caB=int(mc.group(1))//150
    ccd=[int(x) for x in re.findall(r'pr=\(sn-?\d+ st-?\d+ hp\d+/\d+ ccd(-?\d+)\)',t)]
    hps=[];ds=[];agg=[0]*5;nb=0;stset=set()
    st4=[]
    for L in t.splitlines():
        if '[BEAT' not in L: continue
        mb=re.search(r'\[BEAT f=\d+ b=(\d+)\]',L)
        if not mb or int(mb.group(1))<caB: continue
        nb+=1
        h=re.search(r'pr=\(sn-?\d+ st(-?\d+) hp(\d+)/\d+ ccd',L)
        if h:
            stset.add(h.group(1)); hps.append(int(h.group(2))); st4.append(int(h.group(1)))
        pa=re.search(r'pr@=\(([-\d.]+),([-\d.]+)\)',L)
        m=tag_of(fn)
        if pa and m:
            x,y=float(pa.group(1)),float(pa.group(2))
            if x>0 or y>0:
                w=WS[m]; ds.append(((x-w[0])**2+(y-w[1])**2)**0.5)
        pmm=re.search(r'pm f(\d+) ca(\d+) h(\d+) cnt(\d+) o(\d+)',L)
        if pmm:
            for i in range(5): agg[i]+=int(pmm.group(i+1))
    s=sum(agg)
    # 结局
    if '被祭司转换,归属阵营1->0' in t: k='W'
    elif 'DEFEAT: Priest killed' in t: k='P'
    else: k='T'
    md=re.search(r'\|[^|]*(\d+)[^|]*\|[^|]*DEFEAT: Priest killed',t)
    rows.append(dict(f=fn,k=k,hp_end=(hps[-1] if hps else None),hp_min=(min(hps) if hps else None),
                     hp_max=(max(hps) if hps else None),dmin=(min(ds) if ds else None),dmed=(st.median(ds) if ds else None),
                     pm=[100*x/s for x in agg] if s else None,nb=nb,
                     st=st4, ccdmin=(min(ccd) if ccd else None), ccdmax=(max(ccd) if ccd else None)))
print(f'{"局":<24}{"结局":<4}{"hp末":>5}{"hp低":>5}{"hp高":>5}{"dS最小":>8}{"dS中位":>8}{"flee%":>7}{"cnt%":>6}{"ca%":>6}')
for r in rows:
    pm=r['pm']
    print(f'{r["f"]:<24}{r["k"]:<4}{str(r["hp_end"]):>5}{str(r["hp_min"]):>5}{str(r["hp_max"]):>5}'
          f'{("%.1f"%r["dmin"]) if r["dmin"] is not None else "-":>8}'
          f'{("%.1f"%r["dmed"]) if r["dmed"] is not None else "-":>8}'
          f'{(("%.1f"%pm[0]) if pm else "-"):>7}{(("%.1f"%pm[3]) if pm else "-"):>6}{(("%.1f"%pm[1]) if pm else "-"):>6}')
print()
print('=== 汇总（从未起手的局）===')
for k in ['P','T']:
    sub=[r for r in rows if r['k']==k]
    if not sub: continue
    he=[r['hp_end'] for r in sub if r['hp_end'] is not None]
    dm=[r['dmin'] for r in sub if r['dmin'] is not None]
    fl=[r['pm'][0] for r in sub if r['pm']]
    ct=[r['pm'][3] for r in sub if r['pm']]
    print(f'  {k}: n={len(sub)}  hp末中位={st.median(he) if he else "-"}  dS最小中位={st.median(dm) if dm else "-":.1f}'
          f'  flee%中位={st.median(fl) if fl else "-":.1f}  cnt%中位={st.median(ct) if ct else "-":.1f}')
    print(f'     hp末分布: ' + ' '.join(str(x) for x in sorted(he)))
