# -*- coding: utf-8 -*-
"""对比 two TAGs (earlyclub8 vs witharmy12) on map.njust：
结局分布(W/P/T/U) + 胜率 + Fisher + 祭死局机制(dSmin 距武器厂 / 死时距军心 / 军盒内外)。
用法：python _map_cmp2.py <TAG_A> <TAG_B>
"""
import re, glob, os, math, sys, collections

def outcome(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    if 'DEFEAT: Town Center destroyed' in t: return 'T'
    return 'U'

def dSmin(t):
    m = 1e9
    for line in t.splitlines():
        if '[LC-DBG' in line:
            mm = re.search(r'dS=([-\d.]+)', line)
            if mm:
                v = float(mm.group(1))
                if v >= 0: m = min(m, v)
    return m

def last_beat_dist(t):
    bx0=bx1=by0=by1=None; px=py=None
    for line in t.splitlines():
        if '[BEAT' in line:
            pr = re.search(r'pr@=\(([\d.]+),([\d.]+)\)', line)
            bb = re.search(r'bbox=\(x([\d.]+)\.\.([\d.]+),y([\d.]+)\.\.([\d.]+)\)', line)
            if pr: px, py = float(pr.group(1)), float(pr.group(2))
            if bb: bx0,bx1,by0,by1 = map(float, bb.groups())
    if px is None or bx0 is None: return None, None
    cx, cy = (bx0+bx1)/2, (by0+by1)/2
    d = math.hypot(px-cx, py-cy)
    inside = (bx0 <= px <= bx1 and by0 <= py <= by1)
    return d/35.777, inside

def fisher_exact(a_w, a_n, b_w, b_n):
    # two-sided Fisher (log-space hypergeometric, max_lp normalized) — 与 _map_cmp.py 同口径
    from math import log, exp, lgamma
    a_l, a_r = a_w, a_n-a_w
    b_l, b_r = b_w, b_n-b_w
    def lfact(x): return lgamma(x+1)
    def table_lp(k):
        c1=a_l+b_l-k; c2=a_r+k; c3=b_l-k; c4=b_r-k
        if min(c1,c2,c3,c4) < 0: return -1e18
        return (lfact(a_l)+lfact(a_r)+lfact(b_l)+lfact(b_r)
                - lfact(a_n)-lfact(b_n)-lfact(k)-lfact(c2)-lfact(c3)-lfact(c4))
    ks = list(range(max(0, a_l+b_l-a_n), min(a_l, a_l+b_l)+1))
    lps = [table_lp(k) for k in ks]
    max_lp = max(lps)
    p_obs = sum(exp(lp-max_lp) for lp in lps if lp <= lps[ks.index(a_l)]+1e-12)
    p_two = sum(exp(lp-max_lp) for lp in lps if lp <= max_lp - (max_lp - lps[ks.index(a_l)]))
    # 简化双尾：取观测行概率 + 更极端行概率
    return p_two if p_two > 0 else p_obs

TA, TB = (sys.argv[1], sys.argv[2]) if len(sys.argv) >= 3 else ('earlyclub8', 'witharmy12')
def gather(tag):
    res = collections.defaultdict(int); ds=[]; dd=[]; di=[]
    for fn in sorted(glob.glob(f'{tag}_map_r0_*.ait')):
        t = open(fn, encoding='utf-8', errors='replace').read()
        o = outcome(t); res[o]+=1
        if o == 'P':
            ds.append(dSmin(t)); d,ins = last_beat_dist(t)
            if d is not None: dd.append(d); di.append(ins)
    n = sum(res.values())
    w = res['W']
    return res, n, w, ds, dd, di

ra,na,wa,dsa,dda,dia = gather(TA)
rb,nb,wb,dsb,ddb,dib = gather(TB)
def wr(w,n): return f'{w}/{n} = {100*w/n:.1f}%' if n else '-'
print('='*92)
print(f'对比 {TA}(n={na}) vs {TB}(n={nb})  on map.njust')
print('='*92)
print(f'{"":10} {TA:>16} {TB:>16}')
print(f'{"胜 W":10} {wr(wa,na):>16} {wr(wb,nb):>16}')
print(f'{"祭死 P":10} {ra["P"]:>16} {rb["P"]:>16}')
print(f'{"TC毁 T":10} {ra["T"]:>16} {rb["T"]:>16}')
print(f'{"超时 U":10} {ra["U"]:>16} {rb["U"]:>16}')
# Fisher on winrate
p = fisher_exact(wa, na, wb, nb)
print(f'\n胜率 {TA}={100*wa/na:.1f}%  {TB}={100*wb/nb:.1f}%  双尾 Fisher p={p:.3f}')
# 祭死局机制
def med(x):
    if not x: return -1
    s=sorted(x); m=len(s); return s[m//2] if m%2 else (s[m//2-1]+s[m//2])/2
print(f'\n祭死局(P)机制：')
print(f'  {TA}: dSmin中位={med(dsa):.1f}  死时距军心中位={med(dda):.1f}格  军盒外={sum(1 for x in dia if not x)}/{len(dia)}')
print(f'  {TB}: dSmin中位={med(dsb):.1f}  死时距军心中位={med(ddb):.1f}格  军盒外={sum(1 for x in dib if not x)}/{len(dib)}')
print('='*92)
