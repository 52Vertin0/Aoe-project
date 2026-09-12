# -*- coding: utf-8 -*-
"""A/B：wbase(clubman8, 0565ef20) vs club6b(clubman6)。map 单图各 48 局。
口径：W=祭司转换敌武器厂；P=DEFEAT: Priest killed；T=TC毁(含 '敌方 摧毁主营')；U=超时/未结算。
Fisher：双尾超几何（已验证：identical→1.0 / 19v24→0.412 / 30v10→0.00007）。
另报：反攻触发帧中位、反攻前早死局数。
"""
import glob, re, math, statistics, sys

TAG_A = sys.argv[1] if len(sys.argv) > 1 else 'wbase'    # clubman 8
TAG_B = sys.argv[2] if len(sys.argv) > 2 else 'club6b'   # clubman 6
FRAME_RE = re.compile(r'^\d\d:\d\d:\d\d+\s*\|\s*(\d+)\s*\|')

def logcomb(n, k):
    if k < 0 or k > n: return float('-inf')
    return math.lgamma(n+1) - math.lgamma(k+1) - math.lgamma(n-k+1)

def fisher(a, b, c, d):
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
    return min(1.0, num/den)

def wilson(k, n):
    if n == 0: return (0.0, 0.0, 0.0)
    p = k/n; z = 1.96
    d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return (p, c-h, c+h)

def outcome(s):
    if '被祭司转换,归属阵营1->0' in s: return 'W'
    if 'DEFEAT: Priest killed' in s: return 'P'
    if 'DEFEAT: Town Center destroyed' in s: return 'T'
    if '敌方 摧毁主营' in s: return 'T'
    return 'U'

def collect(tag):
    res = {'W':0,'P':0,'T':0,'U':0}; ca = []; early = 0; n = 0
    for fn in sorted(glob.glob(f'{tag}_*_r0_*.ait')):
        s = open(fn, encoding='utf-8', errors='replace').read(); n += 1
        r = outcome(s); res[r] += 1
        m = re.search(r'ALL WAVES DEFEATED! Counterattack! Frame=(\d+)', s)
        cafr = int(m.group(1)) if m else None
        if cafr is not None: ca.append(cafr)
        if r == 'P':
            fr = [int(x.group(1)) for x in (FRAME_RE.match(l) for l in s.splitlines()) if x]
            death = max(fr) if fr else 0
            if cafr is None or death < cafr: early += 1
    return res, ca, early, n

resA, caA, earlyA, nA = collect(TAG_A)
resB, caB, earlyB, nB = collect(TAG_B)

print('=' * 100)
print(f'A = {TAG_A}   B = {TAG_B}   （map 单图）')
print('=' * 100)
for tag, res, ca, early, n in ((TAG_A, resA, caA, earlyA, nA), (TAG_B, resB, caB, earlyB, nB)):
    p, lo, hi = wilson(res['W'], n)
    mc = statistics.median(ca) if ca else float('nan')
    print(f'[{tag}] n={n}  W={res["W"]} P={res["P"]} T={res["T"]} U={res["U"]}  '
          f'胜率={p*100:.1f}% (95%CI {lo*100:.1f}~{hi*100:.1f})   反攻帧中位={mc:.0f}  反攻前早死={early}')
print('-' * 100)
p = fisher(resA['W'], nA-resA['W'], resB['W'], nB-resB['W'])
print(f'Fisher 精确检验 (W: {TAG_A} {resA["W"]}/{nA} vs {TAG_B} {resB["W"]}/{nB}): p={p:.3f}')
print('  (n=48/臂 噪声带 ~±14pp；p<0.05 才显著)')
print('=' * 100)
