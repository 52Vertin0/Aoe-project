# -*- coding: utf-8 -*-
"""木材早期提档 A/B 对比：基线(wbase) vs 处理(wearly)。
   口径与 _win_current.py 一致（W=祭司转换敌武器厂 / P=祭死 / T=TC毁 / U=超时未决）。
   机制量：升铜发起帧 / 第二仓库下单帧([STOCK-ORD]) / [WOOD] early 触发数。
   统计：Wilson 95%CI + Fisher 精确检验（超几何、双尾、概率 <= 观测）。
"""
import re, glob, os, math, statistics

TAG_A = 'wbase'    # 基线（改前）
TAG_B = 'wearly'   # 处理（木材早期提档）

def outcome(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    if 'DEFEAT: Town Center destroyed' in t: return 'T'
    return 'U'

def wilson(k, n):
    if n == 0: return (0.0, 0.0, 0.0)
    p = k / n; z = 1.96
    d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (p, max(0.0, c-h), min(1.0, c+h))

# ---- 正确的 Fisher 精确检验（超几何, 双尾, 概率 <= 观测） ----
def logcomb(n, k):
    if k < 0 or k > n: return float('-inf')
    return math.lgamma(n+1) - math.lgamma(k+1) - math.lgamma(n-k+1)

def fisher(a, b, c, d):
    """表 [[a,b],[c,d]]；双尾 p = (所有 P <= P_obs 的表概率之和) / (全体表概率之和)。
       ⚠ 必须除以 den（全体和）—— 只算分子会在 P 分布较宽时 >1 并被 clamp 成 1.0（曾误报 p=1.000）。"""
    N = a+b+c+d; R1 = a+b; R2 = c+d; C1 = a+c; C2 = b+d
    def logP(x):
        y = R1-x; z = C1-x; w = C2-y
        if z < 0 or w < 0: return float('-inf')
        return logcomb(R1, x) + logcomb(R2, z) - logcomb(N, C1)
    obs = logP(a)
    amin = max(0, R1-C2); amax = min(R1, C1)
    lps = [logP(x) for x in range(amin, amax+1)]
    mx = max(lps)
    den = sum(math.exp(l-mx) for l in lps)
    num = sum(math.exp(l-mx) for l in lps if l <= obs + 1e-9)
    return min(1.0, num / den)

def first_frame(t, pat):
    m = re.search(pat, t)
    return int(m.group(1)) if m else None

def collect(tag):
    res = {'W':0,'P':0,'T':0,'U':0}
    bronze = []; stock = []; early_hits = []; woodlines = []
    files = sorted(glob.glob(f'{tag}_map_r0_*.ait'))
    for fn in files:
        t = open(fn, encoding='utf-8', errors='replace').read()
        res[outcome(t)] += 1
        # 升铜代理：首个 [WOOD] boom=1（woodBoom 需铜器后 ⇒ 首现即铜器已达；分辨率 600 帧）
        bf = first_frame(t, r'\[WOOD f=(\d+)\] boom=1')
        sf = first_frame(t, r'\[STOCK-ORD f=(\d+)\]')
        e  = t.count('early=1')
        wl = t.count('[WOOD ')
        if bf is not None: bronze.append(bf)
        if sf is not None: stock.append(sf)
        early_hits.append(e); woodlines.append(wl)
    return res, bronze, stock, early_hits, woodlines, len(files)

def med(xs):
    return statistics.median(xs) if xs else float('nan')

A = collect(TAG_A)
B = collect(TAG_B)

def show(tag, pack):
    res, bronze, stock, early, woodl, n = pack
    w = res['W']; p = wilson(w, n)
    print(f'[{tag}] n={n}  W={res["W"]} P={res["P"]} T={res["T"]} U={res["U"]}'
          f'   胜率={p[0]*100:.1f}% (95%CI {p[1]*100:.1f}~{p[2]*100:.1f})')
    print(f'        升铜发起帧 中位={med(bronze)} (n={len(bronze)})   第二仓库下单帧 中位={med(stock)} (n={len(stock)})')
    ne = sum(1 for x in early if x > 0)
    print(f'        [WOOD] 行数 中位={med(woodl)}   early 触发局数={ne}/{n}  early=1 总行数={sum(early)}')

# Fisher 自测（防止再报错的 p）：identical→1.0 / 强差异→极小
_t1 = fisher(13, 35, 13, 35); _t2 = fisher(19, 29, 24, 24); _t3 = fisher(30, 18, 10, 38)
print(f'[Fisher 自测] identical(13v13)={_t1:.3f} (应=1.0) | 19v24={_t2:.3f} (应≈0.41) | 30v10={_t3:.5f} (应<0.001)')

print('=' * 104)
show(TAG_A, A)
show(TAG_B, B)
print('=' * 104)

resA, nA = A[0], A[5]
resB, nB = B[0], B[5]
p = fisher(resB['W'], nB-resB['W'], resA['W'], nA-resA['W'])
print(f'Fisher 精确检验 (W: {TAG_A} {resA["W"]}/{nA} vs {TAG_B} {resB["W"]}/{nB}): p={p:.3f}')
print('  (p<0.05 显著；n=48/臂 噪声带 ~±14pp，单批不显著属常态，符合"需~180局/臂"铁律)')
print('=' * 104)
print('解读：early 触发局数>0 = 提档确实生效；第二仓库下单帧提前 = 木材瓶颈被打开；')
print('      升铜发起帧不显著变晚 = 没抽空升铜食物；胜率升 = 改法命中。')
