# -*- coding: utf-8 -*-
# A/B: 战车弓臂(chariot) vs 复合弓臂(composite) —— map 单图，验证「复合弓→战车弓」对胜率的影响
# 两臂仅在主远程兵种（unit + 解锁科技 + 木材提档）上不同，其余（随军闸/集结闸/先锋限量/MAX_FARMS）相同。
import re, glob, math

TAG_A = 'chariot'      # 战车弓
TAG_B = 'composite'    # 复合弓

def outcome(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    if 'DEFEAT: Town Center destroyed' in t: return 'T'
    return 'U'

def main_unit_peak(t):
    # ARMY 行里的 comp:N（MAIN_RANGED_SORT 计数）取峰值
    mx = 0
    for m in re.finditer(r'ARMY \| comp:(\d+)', t):
        mx = max(mx, int(m.group(1)))
    return mx

def collect(tag):
    res = {'W':0,'P':0,'T':0,'U':0}; peaks = []
    for fn in sorted(glob.glob(f'{tag}_map_r0_*.ait')):
        t = open(fn, encoding='utf-8', errors='replace').read()
        r = outcome(t); res[r] += 1
        peaks.append(main_unit_peak(t))
    return res, peaks

def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0, 0.0)
    p = k / n
    den = 1 + z*z/n
    c = (p + z*z/(2*n)) / den
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return (p, max(0, c-h), min(1, c+h))

def logfact(n):
    if n < 0: return float('-inf')
    return math.lgamma(n + 1)

def fisher_exact(a, b, c, d):
    N = a + b + c + d
    R1, C1, C2 = a + b, a + c, b + d
    def logp(x, y, z, w):
        return (logfact(x)+logfact(y)+logfact(z)+logfact(w)
                - logfact(x+y)-logfact(z+w)-logfact(x+z)-logfact(y+w) + logfact(N))
    obs = logp(a, b, c, d)
    lps = [logp(ap, R1-ap, C1-ap, C2-(R1-ap)) for ap in range(max(0, R1-C2), min(R1, C1)+1)]
    mx = max(lps)
    return min(1.0, sum(math.exp(lp-mx) for lp in lps if lp >= obs - 1e-9))

A, pA = collect(TAG_A)
B, pB = collect(TAG_B)

def show(tag, res, peaks):
    n = sum(res.values()); w = res['W']; p = wilson(w, n)
    pk = sorted(peaks); med = pk[len(pk)//2] if pk else 0
    print(f'[{tag}] n={n}  W={res["W"]} P={res["P"]} T={res["T"]} U={res["U"]}'
          f'  胜率={p[0]*100:.1f}% (95%CI {p[1]*100:.1f}~{p[2]*100:.1f})  主兵峰值中位={med}')

nA, wA = sum(A.values()), A['W']
nB, wB = sum(B.values()), B['W']
print('='*100)
show(TAG_A, A, pA)
show(TAG_B, B, pB)
print('='*100)
p = fisher_exact(wB, nB-wB, wA, nA-wA)
print(f'Fisher 精确检验 (W: {TAG_A} {wA}/{nA} vs {TAG_B} {wB}/{nB}): p={p:.3f}')
print(f'胜率差 = {(wB/nB - wA/nA)*100:+.1f}pp  (正值=复合弓更高，负值=战车弓更高)')
print('  注：n=48/臂 噪声带 ~±14pp；p<0.05 才显著。')
