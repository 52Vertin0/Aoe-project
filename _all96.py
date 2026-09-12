# -*- coding: utf-8 -*-
"""全量 96 局特征表 → _all96.tsv（后续查询基座）。所有距离量剔除死亡哨兵 (0,0)。"""
import re,glob,csv,sys
WS={'map':(11,86),'map1':(93,11),'map2':(24,6),'map3':(82,20)}
BASE={'map':(80.4,12.1),'map1':(22.4,75.0),'map2':(73.8,87.2),'map3':(28.9,81.0)}
def tag_of(fn):
    for m in WS:
        if f'_{m}_' in fn: return m
    return None
def dist(a,b): return ((a[0]-b[0])**2+(a[1]-b[1])**2)**0.5

out=[]
for fn in sorted(glob.glob('fixI_*_r0_*.ait')):
    t=open(fn,encoding='utf-8',errors='replace').read()
    if t.count('[BEAT')<5: continue
    g=tag_of(fn); ws=WS[g]; bs=BASE[g]
    CA=re.search(r'Counterattack! Frame=(\d+)',t)
    caf=int(CA.group(1)) if CA else None
    convs=[(int(m.group(1)),m.group(2)) for m in
           re.finditer(r'converting Siege Workshop! f=(\d+) d=([\d.]+)',t)]
    if '被祭司转换,归属阵营1->0' in t: k='W'
    elif 'DEFEAT: Priest killed' in t: k='P'
    elif 'DEFEAT: Town Center destroyed' in t: k='TC'
    else: k='T'
    # 死亡帧
    dth=None
    m=re.search(r'\|(\d+)\|[^|]*DEFEAT: Priest killed',t)
    if m: dth=int(m.group(1))
    # 发现武器厂
    mw=re.search(r'Enemy Siege Workshop found at[^\d]*\((\d+),(\d+)\)',t)
    fws=None
    mfw=re.search(r'Enemy Siege Workshop found at.*?(\d{4,6})',t)
    # [BEAT] 序列
    beats=[]
    for L in t.splitlines():
        if '[BEAT' not in L: continue
        mb=re.search(r'\[BEAT f=(\d+) b=(\d+)\]',L)
        if not mb: continue
        b=int(mb.group(2)); f=int(mb.group(1))
        mm=re.search(r'Mil=(\d+)',L); mil=int(mm.group(1)) if mm else None
        mh=re.search(r'pr=\(sn-?\d+ st(-?\d+) hp(\d+)/\d+ ccd(-?\d+)\)',L)
        st=int(mh.group(1)) if mh else None
        hp=int(mh.group(2)) if mh else None
        ccd=int(mh.group(3)) if mh else None
        mp=re.search(r'pr@=\(([-\d.]+),([-\d.]+)\)',L)
        pos=None
        if mp:
            x,y=float(mp.group(1)),float(mp.group(2))
            if x>0 or y>0: pos=(x,y)
        pm=re.search(r'pm f(\d+) ca(\d+) h(\d+) cnt(\d+) o(\d+)',L)
        pmv=[int(pm.group(i+1)) for i in range(5)] if pm else None
        beats.append(dict(f=f,b=b,mil=mil,st=st,hp=hp,ccd=ccd,pos=pos,pm=pmv))
    convB = int(convs[0][0])//150 if convs else None
    # 分段统计
    def seg(lo,hi):
        return [x for x in beats if x['b']>=lo and (hi is None or x['b']<hi)]
    post = seg(convB, None) if convB is not None else []
    ca_seg = seg(caf//150 if caf else 10**9, None)
    amb_seg = seg(0, caf//150 if caf else 10**9)
    def dmin(s,anchor):
        v=[dist(x['pos'],anchor) for x in s if x['pos']]
        return min(v) if v else None
    def dlast(s,anchor):
        v=[dist(x['pos'],anchor) for x in s if x['pos']]
        return v[-1] if v else None
    agg=[0]*5
    for x in beats:
        if x['pm']:
            for i in range(5): agg[i]+=x['pm'][i]
    caagg=[0]*5
    for x in ca_seg:
        if x['pm']:
            for i in range(5): caagg[i]+=x['pm'][i]
    postagg=[0]*5
    for x in post:
        if x['pm']:
            for i in range(5): postagg[i]+=x['pm'][i]
    out.append(dict(
        game=fn.replace('fixI_','').replace('.ait',''), map=g, outcome=k,
        caf=caf or -1, nconv=len(convs), convf=convs[0][0] if convs else -1,
        dth=dth if dth is not None else -1,
        hp_end=beats[-1]['hp'] if beats else -1,
        mil_end=beats[-1]['mil'] if beats else -1,
        hp_at_ca=(ca_seg[0]['hp'] if ca_seg else -1),
        dmin_ws=dmin(beats,ws) if dmin(beats,ws) is not None else -1,
        dmin_ws_ca=dmin(ca_seg,ws) if dmin(ca_seg,ws) is not None else -1,
        dmin_base=dmin(beats,bs) if dmin(beats,bs) is not None else -1,
        dmin_base_ca=dmin(ca_seg,bs) if dmin(ca_seg,bs) is not None else -1,
        mil_at_ca=(ca_seg[0]['mil'] if ca_seg and ca_seg[0]['mil'] is not None else -1),
        mil_max=(max(x['mil'] for x in beats) if any(x['mil'] is not None for x in beats) else -1),
        mil23=(sum(1 for x in beats if x['mil'] is not None and x['mil']>=23)),
        mil_at_conv=(post[0]['mil'] if post and post[0]['mil'] is not None else -1),
        hpf=beats[-1]['f'] if beats else -1,
        d_at_conv=(float(convs[0][1]) if convs else -1),
        hp_at_conv=(post[0]['hp'] if post else -1),
        flee=agg[0],convapp=agg[1],heal=agg[2],cnt=agg[3],other=agg[4],
        ca_flee=caagg[0],ca_cnt=caagg[3],ca_convapp=caagg[1],
        po_flee=postagg[0],po_cnt=postagg[3],po_convapp=postagg[1],
        HM=len(re.findall(r'HumanMove:祭司',t)),
        escA=t.count('PRIEST-ESCAPE A'),escB=t.count('PRIEST-ESCAPE B'),
        escBR=t.count('PRIEST-ESCAPE-BREAK'),adv=t.count('Priest ADVANCE to Siege'),
        wait=t.count('[SIEGE-WAIT]'),hold=t.count('[SIEGE-HOLD]'),
        noarmy=t.count('[PRST-NOARMY]'),rear=t.count('[PRST-REAR]'),
        guard=t.count('[PRIEST GUARD]'),nbeat=len(beats),
        fws=1 if mw else 0))
cols=list(out[0].keys())
w=csv.DictWriter(sys.stdout,fieldnames=cols,delimiter='\t',lineterminator='\n')
w.writeheader()
for r in out: w.writerow(r)
sys.stderr.write(f'{len(out)} games\n')
