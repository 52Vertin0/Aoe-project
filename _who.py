# -*- coding: utf-8 -*-
"""谁在动祭司：引擎 HumanMove:祭司 条数 vs [BEAT] pm 五列之和 ⇒ 残差 = 未被计数的下令者"""
import re,glob,statistics as st
rows=[]
for fn in sorted(glob.glob('fixI_*_r0_*.ait')):
    t=open(fn,encoding='utf-8',errors='replace').read()
    if t.count('[BEAT')<5: continue
    hm=len(re.findall(r'HumanMove:祭司',t))
    tot=0; agg=[0]*5; nb=0
    for L in t.splitlines():
        if '[BEAT' not in L: continue
        nb+=1
        m=re.search(r'pm f(\d+) ca(\d+) h(\d+) cnt(\d+) o(\d+)',L)
        if m:
            v=[int(m.group(i+1)) for i in range(5)]
            for i in range(5): agg[i]+=v[i]
            tot+=sum(v)
    h='converting Siege Workshop' in t
    if '被祭司转换,归属阵营1->0' in t: k='W'
    elif 'DEFEAT: Priest killed' in t: k='P'
    else: k='T'
    rows.append(dict(f=fn.replace('fixI_','').replace('.ait',''),k=k,h=h,hm=hm,pm=tot,
                     ratio=(100*tot/hm if hm else 0),agg=agg,nb=nb))

print('=== 引擎 HumanMove:祭司 条数 vs [BEAT] pm 总和（残差 = 未计入 pm 的移动令）===')
print(f'{"局":<20}{"结局":<4}{"起手":<5}{"HM祭司":>7}{"pm总":>7}{"pm/HM%":>8}   pm构成 f/ca/h/cnt/o')
for r in sorted(rows,key=lambda r:r['ratio']):
    a=r['agg']
    print(f'{r["f"]:<20}{r["k"]:<4}{"Y" if r["h"] else "-":<5}{r["hm"]:>7}{r["pm"]:>7}{r["ratio"]:>8.1f}   {a[0]}/{a[1]}/{a[2]}/{a[3]}/{a[4]}')

print()
print('=== 汇总 ===')
for lbl,filt in [('起手局',True),('未起手局',False)]:
    sub=[r for r in rows if r['h']==filt]
    if not sub: continue
    rt=[r['ratio'] for r in sub]
    print(f'{lbl:<8} n={len(sub):>3}  pm/HM% 中位={st.median(rt):.1f}  范围 {min(rt):.1f}~{max(rt):.1f}')
    print(f'         平均 HM祭司={st.mean([r["hm"] for r in sub]):.0f} | pm总={st.mean([r["pm"] for r in sub]):.0f}')
