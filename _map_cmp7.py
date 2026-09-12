# -*- coding: utf-8 -*-
"""多臂对比（map 单图）：结局分布 + 人口闸触发 + 反攻帧 + 祭司反攻前早死。
用法: python _map_cmp7.py wbase club6n club8n
口径：
  W = 祭司转换敌武器厂；P = DEFEAT: Priest killed；T = TC毁(含 '敌方 摧毁主营')；U = 超时/未结算
  伪U = 结局为 U 且最大帧 < 44000（被 TMO kill 的截断局）⇒ 单独列示，默认从分母剔除。
"""
import glob, re, math, os, statistics, sys

FRAME_RE = re.compile(r'^\d\d:\d\d:\d\d+\s*\|\s*(\d+)\s*\|')
POPFULL_RE = re.compile(r'POP-FULL COUNTERATTACK! Frame=(\d+)')

def logcomb(n, k):
    if k < 0 or k > n: return float('-inf')
    return math.lgamma(n+1) - math.lgamma(k+1) - math.lgamma(n-k+1)

def fisher(a, b, c, d):
    N = a+b+c+d
    if N == 0: return 1.0
    R1 = a+b; R2 = c+d; C1 = a+c; C2 = b+d
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
    res = {'W':0,'P':0,'T':0,'U':0}
    n = 0; trunc = 0; early = 0
    ca = []; pf = []; pf_arms = 0
    early_list = []
    for fn in sorted(glob.glob(f'{tag}_*_r0_*.ait')):
        s = open(fn, encoding='utf-8', errors='replace').read(); n += 1
        fr = [int(x.group(1)) for x in (FRAME_RE.match(l) for l in s.splitlines()) if x]
        mx = max(fr) if fr else 0
        r = outcome(s)
        # 伪U判定：无结局且未跑到点
        is_trunc = (r == 'U' and mx < 44000)
        if is_trunc: trunc += 1
        res[r] += 1
        m = re.search(r'ALL WAVES DEFEATED! Counterattack! Frame=(\d+)', s)
        cafr = int(m.group(1)) if m else None
        if cafr is not None: ca.append(cafr)
        mp = POPFULL_RE.search(s)
        if mp:
            pf_arms += 1
            pf.append(int(mp.group(1)))
        if r == 'P':
            death = mx
            # ★ 反攻时点：闸帧优先（触发局不会再打印 ALL WAVES）
            atk = min([x for x in (cafr, (int(mp.group(1)) if mp else None)) if x] or [None])
            if atk is None or death < atk:
                early += 1
                early_list.append(os.path.basename(fn))
    return dict(res=res, n=n, trunc=trunc, ca=ca, pf=pf, pf_arms=pf_arms,
                early=early, early_list=early_list)

tags = sys.argv[1:] or ['wbase', 'club6n', 'club8n']
data = {t: collect(t) for t in tags}

print('=' * 108)
print('多臂对比（map 单图）  ' + '   '.join(f'{t}' for t in tags))
print('=' * 108)
hdr = f'{"臂":<10}{"n":>4}{"截断":>5}{"W":>4}{"P":>4}{"T":>4}{"U":>4}{"胜率":>8}{"95%CI":>18}{"祭死":>6}{"反攻前早死":>10}{"反攻帧中位":>11}{"闸触发":>7}{"闸均帧":>9}'
print(hdr)
print('-' * 108)
for t in tags:
    d = data[t]
    nn = d['n'] - d['trunc']          # 剔除截断后的有效分母
    p, lo, hi = wilson(d['res']['W'], nn)
    mc = statistics.median(d['ca']) if d['ca'] else float('nan')
    mpf = statistics.mean(d['pf']) if d['pf'] else float('nan')
    print(f'{t:<10}{d["n"]:>4}{d["trunc"]:>5}{d["res"]["W"]:>4}{d["res"]["P"]:>4}{d["res"]["T"]:>4}{d["res"]["U"]:>4}'
          f'{p*100:>7.1f}%  {lo*100:>5.1f}~{hi*100:<5.1f}   {d["res"]["P"]:>4}  {d["early"]:>8}'
          f'{(mc if mc==mc else 0):>11.0f}{d["pf_arms"]:>5}/{d["n"]:<2}{(mpf if mpf==mpf else 0):>9.0f}')
print('-' * 108)
print('Fisher 精确检验（双尾·超几何，分母已剔截断）：')
for i in range(len(tags)):
    for j in range(i+1, len(tags)):
        A, B = data[tags[i]], data[tags[j]]
        nA, nB = A['n']-A['trunc'], B['n']-B['trunc']
        pw = fisher(A['res']['W'], nA-A['res']['W'], B['res']['W'], nB-B['res']['W'])
        pp = fisher(A['res']['P'], nA-A['res']['P'], B['res']['P'], nB-B['res']['P'])
        print(f'  {tags[i]:<9} vs {tags[j]:<9}  胜 {A["res"]["W"]}/{nA} vs {B["res"]["W"]}/{nB}  p={pw:.4f}   |   祭死 {A["res"]["P"]}/{nA} vs {B["res"]["P"]}/{nB}  p={pp:.4f}')
print('=' * 108)
for t in tags:
    d = data[t]
    if d['early_list']:
        print(f'[{t}] 祭司反攻前早死局：{", ".join(x.replace(f"{t}_","").replace("_r0_"," r0/") for x in d["early_list"])}')
print(f"说明：n=48/臂 噪声带 ≈ ±14pp，可判读 ≥15pp；单图抽检（n≤12）不足以下结论。")
