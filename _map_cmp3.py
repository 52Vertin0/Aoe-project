# -*- coding: utf-8 -*-
# 对比 witharmy12(基线) vs armypush24(军队推到武器厂) —— map 单图因果对比
# 指标：W/P/T/U 结局桶、胜率 Wilson CI、Fisher 精确检验、祭死局 dSmin(到武器厂)、TOWER-TGT 频率
import re, glob, os, math

TAG_A = 'witharmy12'
TAG_B = 'armypush24'

def outcome(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    if 'DEFEAT: Town Center destroyed' in t: return 'T'
    return 'U'

def dsmin(t):
    lcs = [float(m.group(1)) for m in re.finditer(r'\[LC-DBG f=\d+\].*?dS=([-\d.]+)', t)
           if float(m.group(1)) >= 0]
    return min(lcs) if lcs else None

def ttcount(t): return t.count('[TOWER-TGT')

def collect(tag):
    res = {'W':0,'P':0,'T':0,'U':0}; ds_w = []; ds_p = []; tts = []
    files = sorted(glob.glob(f'{tag}_map_r0_*.ait'))
    for fn in files:
        t = open(fn, encoding='utf-8', errors='replace').read()
        r = outcome(t); res[r] += 1
        d = dsmin(t)
        if r == 'W' and d is not None: ds_w.append(d)
        if r == 'P' and d is not None: ds_p.append(d)
        tts.append(ttcount(t))
    return res, ds_w, ds_p, tts

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
    # 2x2 表:
    #        A(基线)  B(实验)
    #   W      a        b
    #   非W    c        d
    # 双尾 Fisher (超几何, log 空间, 完整遍历 a' 保持边际)
    N = a + b + c + d
    R1, R2 = a + b, c + d
    C1, C2 = a + c, b + d
    def logp(x, y, z, w):
        return (logfact(x) + logfact(y) + logfact(z) + logfact(w)
                - logfact(x + y) - logfact(z + w) - logfact(x + z) - logfact(y + w)
                + logfact(N))
    obs_lp = logp(a, b, c, d)
    amin = max(0, R1 - C2)
    amax = min(R1, C1)
    lps = []
    for ap in range(amin, amax + 1):
        bp = R1 - ap
        cp = C1 - ap
        dp = C2 - bp
        lps.append(logp(ap, bp, cp, dp))
    max_lp = max(lps)
    p_two = sum(math.exp(lp - max_lp) for lp in lps if lp >= obs_lp - 1e-9)
    return min(1.0, p_two)

A = collect(TAG_A)
B = collect(TAG_B)

def median(xs):
    if not xs: return float('nan')
    s = sorted(xs); return s[len(s)//2]

def show(tag, res, ds_w, ds_p, tts):
    n = sum(res.values())
    w = res['W']
    p = wilson(w, n)
    medtt = median(tts) if tts else 0
    mw = median(ds_w); mp = median(ds_p)
    # 祭死局中 dSmin<=12 (到过武器厂感化射程内) 的比例
    p_near = sum(1 for d in ds_p if d <= 12) if ds_p else 0
    p_far  = len(ds_p) - p_near
    print(f'[{tag}] n={n}  W={res["W"]} P={res["P"]} T={res["T"]} U={res["U"]}'
          f'  胜率={p[0]*100:.1f}% (95%CI {p[1]*100:.1f}~{p[2]*100:.1f})')
    print(f'       胜局 dSmin(到武器厂,格) 中位={mw:.1f}')
    print(f'       祭死局 dSmin 中位={mp:.1f}  (其中<=12格到过感化射程={p_near}, >12格没到={p_far})')
    print(f'       TOWER-TGT 中位={medtt}')
    return n, w

print('='*100)
nA, wA = show(TAG_A, *A)
nB, wB = show(TAG_B, *B)
print('='*100)

# Fisher 双尾: 2x2 (W vs 非W) across A/B
# 表: 基线W=wA 非W=nA-wA ; 实验W=wB 非W=nB-wB
p = fisher_exact(wB, nB - wB, wA, nA - wA)
print(f'Fisher 精确检验 (W: {TAG_A} {wA}/{nA} vs {TAG_B} {wB}/{nB}): p={p:.3f}')
print('  (p<0.05 显著；n=48/臂 噪声带 ~14pp，单批不显著属常态，符合"需~180局/臂"铁律)')
print('='*100)
print('解读：胜局 dSmin 低 = 祭司进了感化射程(军队推到武器厂)；')
print('      祭死局 dSmin<=12 占比高 = 到了武器厂但感化时被集火死；')
print('      祭死局 dSmin>12 占比高 = 军队没推到武器厂、祭司到不了；')
print('      TOWER-TGT 仍高 = 到武器厂保护圈内正常打塔。')
