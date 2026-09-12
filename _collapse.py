# -*- coding: utf-8 -*-
"""前期崩盘桶：mil_max<16 的局 vs 其余局，在 f=12000/14000 的人口/村民/资源/科技对照"""
import re,glob,statistics as st,collections
def tag_of(fn):
    for m in ['map','map1','map2','map3']:
        if f'_{m}_' in fn: return m
    return None
def snap(t,ftarget):
    """取最接近 ftarget 的 [BEAT] 桶"""
    best=None
    for L in t.splitlines():
        if '[BEAT' not in L: continue
        m=re.search(r'\[BEAT f=(\d+)',L)
        if not m: continue
        f=int(m.group(1))
        if f>ftarget: break
        best=L
    return best
def grab(L,pat):
    m=re.search(pat,L) if L else None
    return int(m.group(1)) if m else None
rows=[]
for fn in sorted(glob.glob('fixI_*_r0_*.ait')):
    t=open(fn,encoding='utf-8',errors='replace').read()
    if t.count('[BEAT')<5: continue
    mils=[int(m.group(1)) for m in re.finditer(r'Mil=(\d+)',t)]
    if not mils: continue
    mmax=max(mils)
    if '被祭司转换,归属阵营1->0' in t: k='W'
    elif 'DEFEAT: Priest killed' in t: k='P'
    else: k='T'
    s14=snap(t,14000); s10=snap(t,10000)
    rows.append(dict(f=fn.replace('fixI_','').replace('.ait',''),g=tag_of(fn),k=k,mmax=mmax,
        frm14=grab(s14,r'Frm=(\d+)'),mil14=grab(s14,r'Mil=(\d+)'),my14=grab(s14,r'nMy=(\d+)'),
        fd14=grab(s14,r'Fd=(\d+)'),wd14=grab(s14,r'Wd=(\d+)'),gd14=grab(s14,r'Gd=(\d+)'),
        st14=grab(s14,r' pr=\(sn-?\d+ st(-?\d+)'),
        frm10=grab(s10,r'Frm=(\d+)'),mil10=grab(s10,r'Mil=(\d+)'),st10=grab(s10,r' pr=\(sn-?\d+ st(-?\d+)'),
        era14=(s14 or '')[:0],))
def M(v): return st.median(v) if v else float('nan')
coll=[r for r in rows if r['mmax']<16]
rest=[r for r in rows if r['mmax']>=16]
print(f'崩盘桶(mil_max<16): n={len(coll)}  '+str(collections.Counter(x['k'] for x in coll))+'  分图'+str(collections.Counter(x['g'] for x in coll)))
print(f'其余              : n={len(rest)}  '+str(collections.Counter(x['k'] for x in rest)))
print()
for key in ['frm10','mil10','st10','frm14','mil14','my14','fd14','wd14','gd14']:
    a=[r[key] for r in coll if r[key] is not None]
    b=[r[key] for r in rest if r[key] is not None]
    print(f'  {key:<7} 崩盘桶中位={M(a):>7.1f}  其余中位={M(b):>7.1f}   Δ={M(a)-M(b):>+7.1f}')
print()
print('=== 崩盘桶逐局（f≈14000 快照；st: 0=IDLE 1=WALK 2=WORK 3=ATK）===')
print(f'{"局":<14}{"图":<6}{"端":<3}{"milmax":>7}{"Frm10":>6}{"Mil10":>6}{"st10":>5}{"Frm14":>6}{"Mil14":>6}{"nMy14":>6}{"Fd14":>6}{"Wd14":>6}{"Gd14":>6}')
for r in sorted(coll,key=lambda r:r['g']):
    print(f'{r["f"]:<14}{r["g"]:<6}{r["k"]:<3}{r["mmax"]:>7}{str(r["frm10"]):>6}{str(r["mil10"]):>6}{str(r["st10"]):>5}'
          f'{str(r["frm14"]):>6}{str(r["mil14"]):>6}{str(r["my14"]):>6}{str(r["fd14"]):>6}{str(r["wd14"]):>6}{str(r["gd14"]):>6}')
