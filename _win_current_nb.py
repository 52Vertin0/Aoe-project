# -*- coding: utf-8 -*-
"""各地图胜率统计 —— nodebug 版口径（只吃引擎事件，不吃 DebugText）
用法: python _win_current_nb.py [TAG]
  胜 = ait 含 '被祭司转换,归属阵营1->0'        （引擎行）
  祭死 = 引擎行 '祭司(编号N)死亡'
  有效局 = 含 >=5 条引擎 '开始向' 事件（debug 版的 [BEAT 有效性判据在 nodebug 版不存在）
"""
import re, glob, os, collections, math, sys
TAG = sys.argv[1] if len(sys.argv) > 1 else 'current'
MAPS = ['map','map1','map2','map3']
NEED_EV = 5
def outcome(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if re.search(r'祭司\(编号\d+\)死亡', t): return 'P'
    return 'U'
def wilson(w,n,z=1.96):
    if n==0: return (0.0,0.0)
    p=w/n; d=1+z*z/n; c=(p+z*z/(2*n))/d
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return (100*(c-h),100*(c+h))
rows=[]
for fn in sorted(glob.glob(f'{TAG}_*_r0_*.ait')):
    t=open(fn,encoding='utf-8',errors='replace').read()
    if t.count('开始向') < NEED_EV: continue
    mp=os.path.basename(fn).replace(TAG+'_','').split('_r0_')[0]
    rows.append((mp,outcome(t)))
if not rows:
    print(f'未找到 {TAG}_*_r0_*.ait（至少需 {NEED_EV} 条引擎事件）。'); sys.exit(0)
print('='*92)
print(f'各地图胜率（TAG={TAG}，引擎口径/nodebug 兼容，有效局 {len(rows)}）')
print('='*92)
totW=0
for m in MAPS:
    sub=[k for mp,k in rows if mp==m]; n=len(sub)
    if n==0:
        print(f'{m:<8}{0:>5}{"-":>5}{"-":>10}{"-":>18}'); continue
    cnt=collections.Counter(sub); w=cnt['W']; p=cnt['P']; lo,hi=wilson(w,n)
    totW+=w
    print(f'{m:<8}{n:>5}{w:>5}{100*w/n:>9.1f}%{f"[{lo:.0f},{hi:.0f}]":>18}   祭死={p}')
n=len(rows); lo,hi=wilson(totW,n)
print('-'*92)
print(f'{"总体":<8}{n:>5}{totW:>5}{100*totW/n:>9.1f}%{f"[{lo:.0f},{hi:.0f}]":>18}')
print('='*92)