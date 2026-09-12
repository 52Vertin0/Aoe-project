# -*- coding: utf-8 -*-
"""起手现场全表：hp / nearT / towers / d / path × 结局"""
import re,glob,statistics as st,collections
def oc(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    return 'T'
def tag_of(fn):
    for m in ('map1','map2','map3','map'):
        if f'_{m}_' in fn: return m
W={(11,86):'map',(93,11):'map1',(24,6):'map2',(82,20):'map3'}
rows=[]
for fn in sorted(glob.glob('fixI_*_r0_*.ait')):
    t=open(fn,encoding='utf-8',errors='replace').read()
    sites=re.findall(r'converting Siege Workshop! f=(\d+) d=([\d.]+) hp=([\d.]+) nearT=([-\d.]+) towers=(\d+) path=(\w+)',t)
    if not sites: continue
    rows.append((fn,oc(t),sites))
print(f'{"局":<24}{"结局":<4}{"起手#":>6}   现场（f/d/hp/nearT/towers/path）')
for fn,k,ss in rows:
    s=' | '.join(f'{a[0]}/{a[1]}/{a[2]}/{a[3]}/{a[4]}/{a[5]}' for a in ss[:3])
    print(f'{fn:<24}{k:<4}{len(ss):>6}   {s}')
print()
first=[(fn,k,ss[0]) for fn,k,ss in rows]
print('=== 首起手现场 × 结局 ===')
for k in ['W','P','T']:
    sub=[r for r in first if r[1]==k]
    if not sub: continue
    hp=[float(r[2][2]) for r in sub]; nt=[float(r[2][3]) for r in sub]; tw=[int(r[2][4]) for r in sub]
    print(f'  {k}: n={len(sub)}')
    print(f'     hp    中位={st.median(hp):.2f}  min={min(hp):.2f}  max={max(hp):.2f}  分档{ {"<0.4":sum(1 for x in hp if x<0.4),"0.4-0.6":sum(1 for x in hp if 0.4<=x<0.6),"0.6-0.8":sum(1 for x in hp if 0.6<=x<0.8),">=0.8":sum(1 for x in hp if x>=0.8)} }')
    print(f'     nearT 中位={st.median(nt):.1f}  min={min(nt):.1f}  max={max(nt):.1f}  分档{ {"<=7":sum(1 for x in nt if x<=7),"7-14":sum(1 for x in nt if 7<x<=14),">14":sum(1 for x in nt if x>14)} }')
    print(f'     towers 分布 {dict(sorted(collections.Counter(tw).items()))}')
print()
print('=== 二维：hp × nearT（首起手）→ 胜/总 ===')
bins=[(0,0.4),(0.4,0.6),(0.6,0.8),(0.8,1.01)]
for hlo,hhi in bins:
    line=[]
    for tlo,thi in [(0,7),(7,14),(14,999)]:
        sub=[r for r in first if hlo<=float(r[2][2])<hhi and tlo<=float(r[2][3])<thi]
        w=sum(1 for r in sub if r[1]=='W')
        line.append(f'{w}/{len(sub)}'.rjust(7))
    print(f'  hp[{hlo},{hhi})  nearT<=7|7-14|>14 :' + ''.join(line))
