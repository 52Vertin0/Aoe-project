# -*- coding: utf-8 -*-
"""_all96.tsv 快速查询"""
import csv,statistics as st,sys,collections
R=list(csv.DictReader(open('_all96.tsv',encoding='utf-8'),delimiter='\t'))
def I(r,k):
    v=r[k]
    return int(float(v)) if v not in ('','None') else -999
def F(r,k):
    v=r[k]
    return float(v) if v not in ('','None') else -999.0
def med(v): return st.median(v) if v else float('nan')
OUT=['W','P','T','TC']

def show(title,rows,keys):
    print(f'--- {title} (n={len(rows)}) ---')
    for k in keys:
        v=[I(r,k) for r in rows]
        if not v: continue
        print(f'   {k:<14} 中位={med(v):>8.1f}  P25={sorted(v)[len(v)//4]:>7} P75={sorted(v)[len(v)*3//4]:>7} min={min(v)} max={max(v)}')
    print()

print('=== 1. 起手局（nconv>0）按结局的 hp 轨迹 ===')
con=[r for r in R if I(r,'nconv')>0]
nocon=[r for r in R if I(r,'nconv')==0]
print(f'起手 {len(con)}  未起手 {len(nocon)}   (W={sum(1 for r in R if r["outcome"]=="W")} P={sum(1 for r in R if r["outcome"]=="P")} T={sum(1 for r in R if r["outcome"]=="T")})')
print()
show('起手局·胜 W',[r for r in con if r['outcome']=='W'],['hp_at_ca','hp_at_conv','hp_end','d_at_conv','mil_end','caf','convf','flee','cnt','escA'])
show('起手局·祭死 P',[r for r in con if r['outcome']=='P'],['hp_at_ca','hp_at_conv','hp_end','d_at_conv','mil_end','caf','convf','flee','cnt','escA'])
show('起手局·超时 T',[r for r in con if r['outcome']=='T'],['hp_at_ca','hp_at_conv','hp_end','d_at_conv','mil_end','caf','convf','flee','cnt','escA'])
print()
print('=== 2. 未起手局：反攻段离武器厂最近距离 dmin_ws_ca ===')
show('未起手·全部',nocon,['dmin_ws','dmin_ws_ca','hp_at_ca','hp_end','mil_end','escA','escB','escBR','adv','cnt','flee'])
buckets=[(0,12),(12,14),(14,18),(18,25),(25,40),(40,999)]
print('   dmin_ws_ca 分档:')
for lo,hi in buckets:
    s=[r for r in nocon if lo<=F(r,'dmin_ws_ca')<hi]
    if s: print(f'     [{lo},{hi})  n={len(s):>3}  结局 ' + str(collections.Counter(x["outcome"] for x in s)) +
                f'   hp末中位={med([I(x,"hp_end") for x in s]):.0f}  escA中位={med([I(x,"escA") for x in s]):.0f}')
print()
print('=== 3. 全部 96 局：hp_at_ca 分档 × 结局 ===')
for lo,hi in [(0,26),(26,46),(46,66),(66,86),(86,101)]:
    s=[r for r in R if lo<=I(r,'hp_at_ca')<hi]
    if s: print(f'   hp@反攻起点 [{lo},{hi})  n={len(s):>3}  ' + str(collections.Counter(x["outcome"] for x in s)) +
                f'  胜率={100*sum(1 for x in s if x["outcome"]=="W")/len(s):.0f}%')
print()
print('=== 4. 全部 96 局：mil_end（反攻期军队规模）分档 × 结局 ===')
for lo,hi in [(0,1),(1,6),(6,11),(11,16),(16,27),(27,99)]:
    s=[r for r in R if lo<=I(r,'mil_end')<hi]
    if s: print(f'   mil_end [{lo},{hi})  n={len(s):>3}  ' + str(collections.Counter(x["outcome"] for x in s)) +
                f'  胜率={100*sum(1 for x in s if x["outcome"]=="W")/len(s):.0f}%')
print()
print('=== 5. 分图 × 结局 ===')
for g in ['map','map1','map2','map3']:
    s=[r for r in R if r['map']==g]
    print(f'   {g:<6} n={len(s):>3} ' + str(collections.Counter(x["outcome"] for x in s)) +
          f'  胜率={100*sum(1 for x in s if x["outcome"]=="W")/len(s):.0f}%'
          f'  hp@CA中位={med([I(x,"hp_at_ca") for x in s]):.0f}'
          f'  mil_end中位={med([I(x,"mil_end") for x in s]):.0f}'
          f'  起手率={100*sum(1 for x in s if I(x,"nconv")>0)/len(s):.0f}%'
          f'  fws={sum(1 for x in s if I(x,"fws"))}/{len(s)}')
