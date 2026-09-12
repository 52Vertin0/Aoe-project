# -*- coding: utf-8 -*-
"""gT（全局已探明敌箭塔数）分布 + 是否曾降到 0 —— 决定「塔拆完才起手」这道闸是否可行"""
import re,glob,statistics as st,collections
def oc(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    return 'T'
rows=[]
allg=collections.Counter()
for fn in sorted(glob.glob('fixI_*_r0_*.ait')):
    t=open(fn,encoding='utf-8',errors='replace').read()
    seq=[(int(a),int(b),int(c)) for a,b,c in re.findall(r'\[LC-DBG f=(\d+)\][^\n]*?gT=(\d+) seen=(\d+)',t)]
    if not seq: 
        rows.append((fn,oc(t),None,None,None,None,None,0)); continue
    gs=[g for _,g,_ in seq]
    k=oc(t)
    # 反攻帧
    mc=re.search(r'Counterattack! Frame=(\d+)',t); caf=int(mc.group(1)) if mc else None
    # 反攻后是否曾 gT=0
    after=[(f,g) for f,g,_ in seq if caf and f>=caf]
    z=[f for f,g in after if g==0]
    # 死亡帧
    md=re.search(r'\|\s*(\d+)\s*\|[^|]*\|[^|]*\|[^|]*DEFEAT: Priest killed',t)
    dth=int(md.group(1)) if md else None
    rows.append((fn,k,min(gs),max(gs),st.median(gs),len(z),(z[0] if z else None),len(seq)))
    allg.update(gs)
print(f'{"局":<24}{"结局":<4}{"gT_min":>7}{"gT_max":>7}{"gT中位":>7}{"反攻后gT=0次数":>14}{"首个f":>8}{"LC采样":>7}')
for r in rows:
    print(f'{r[0]:<24}{r[1]:<4}{str(r[2]):>7}{str(r[3]):>7}{(("%.1f"%r[4]) if r[4] is not None else "-"):>7}{r[5]:>14}{str(r[6]):>8}{r[7]:>7}')
print()
print('=== fixI 全臂 gT 取值分布 ===')
for g,c in sorted(allg.items()): print(f'  gT={g}: {c}')
print()
print('=== 汇总 ===')
n=len(rows); w=[r for r in rows if r[1]=='W']
print(f'  总局数={n}  胜={len(w)}')
print(f'  反攻后曾出现 gT=0 的局 = {sum(1 for r in rows if r[5]>0)}/{n}')
for k in ['W','P','T']:
    sub=[r for r in rows if r[1]==k]
    print(f'  {k}: n={len(sub)}  反攻后 gT=0 出现过的局={sum(1 for r in sub if r[5]>0)}')
print()
print('=== 分图：gT 中位 ===')
for m in ['map','map1','map2','map3']:
    sub=[r for r in rows if f'_{m}_' in r[0] and r[4] is not None]
    if sub: print(f'  {m}: n={len(sub)}  gT中位中位={st.median([r[4] for r in sub]):.1f}  gT_max最大={max(r[3] for r in sub)}')
