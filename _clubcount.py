# -*- coding: utf-8 -*-
"""机制量验证：每局我方(flag=0)新产生的棍棒兵数量 + 祭司死亡/早死 Fisher 检验。
用法: python _clubcount.py wbase club6n
"""
import glob, re, math, statistics, sys

# | frame | side | flag |  message   —— 两侧有空格，必须 split('|')
def rows(fn):
    out = []
    for l in open(fn, encoding='utf-8', errors='replace'):
        p = l.split('|')
        if len(p) < 5: continue
        out.append(p)
    return out

NEWCLUB = re.compile(r'产生了新的棍棒兵\(编号:(\d+)\)')

def clubcount(fn):
    sns = set()
    for p in rows(fn):
        if p[3].strip() != '0':      # flag 0 = 我方
            continue
        m = NEWCLUB.search(p[4])
        if m:
            sns.add(m.group(1))
    return len(sns)

def outcome(s):
    if '被祭司转换,归属阵营1->0' in s: return 'W'
    if 'DEFEAT: Priest killed' in s: return 'P'
    if 'DEFEAT: Town Center destroyed' in s or '敌方 摧毁主营' in s: return 'T'
    return 'U'

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

tags = sys.argv[1:] or ['wbase', 'club6n']
data = {}
for tag in tags:
    cnts = []; P = T = W = U = 0; n = 0; early = 0
    for fn in sorted(glob.glob(f'{tag}_map_r0_*.ait')):
        s = open(fn, encoding='utf-8', errors='replace').read(); n += 1
        cnts.append(clubcount(fn))
        r = outcome(s)
        if r == 'W': W += 1
        elif r == 'P': P += 1
        elif r == 'T': T += 1
        else: U += 1
        m = re.search(r'ALL WAVES DEFEATED! Counterattack! Frame=(\d+)', s)
        cafr = int(m.group(1)) if m else None
        if r == 'P':
            fr = [int(x.split('|')[1]) for x in s.splitlines() if len(x.split('|')) > 2 and x.split('|')[1].strip().isdigit()]
            death = max(fr) if fr else 0
            if cafr is None or death < cafr: early += 1
    data[tag] = dict(cnts=cnts, W=W, P=P, T=T, U=U, n=n, early=early)

print('=' * 96)
for tag in tags:
    d = data[tag]
    c = d['cnts']
    print(f'[{tag}] n={d["n"]}  棍棒兵产量: 均值={statistics.mean(c):.1f} 中位={statistics.median(c):.0f} '
          f'min={min(c)} max={max(c)}  (>=6 的局: {sum(1 for x in c if x>=6)}/{d["n"]})')
    print(f'        结局 W={d["W"]} P={d["P"]} T={d["T"]} U={d["U"]}   祭司反攻前早死={d["early"]}')
print('-' * 96)
if len(tags) == 2:
    A, B = data[tags[0]], data[tags[1]]
    print(f'Fisher  W(胜)   : {A["W"]}/{A["n"]} vs {B["W"]}/{B["n"]}  p={fisher(A["W"],A["n"]-A["W"],B["W"],B["n"]-B["W"]):.4f}')
    print(f'Fisher  P(祭死) : {A["P"]}/{A["n"]} vs {B["P"]}/{B["n"]}  p={fisher(A["P"],A["n"]-A["P"],B["P"],B["n"]-B["P"]):.4f}')
    print(f'Fisher  P+早死  : {A["early"]}/{A["n"]} vs {B["early"]}/{B["n"]}  p={fisher(A["early"],A["n"]-A["early"],B["early"],B["n"]-B["early"]):.4f}')
print('=' * 96)
