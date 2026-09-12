# -*- coding: utf-8 -*-
"""map 图新旧版归因对比：扫描两个 TAG 前缀的 <tag>_map_r0_*.ait。
用法: python _map_cmp.py [TAG_A] [TAG_B]
  TAG_A 默认 'current'（基线 fixM 等价版，2/24）
  TAG_B 默认 'earlyclub8'（EARLY_CLUBMAN_TARGET 4→8）
输出：胜率/Wilson CI、前期崩盘率、反攻期祭死率、超时率、军队峰值分布。
"""
import re, glob, os, collections, math, sys

TAG_A = sys.argv[1] if len(sys.argv) > 1 else 'current'
TAG_B = sys.argv[2] if len(sys.argv) > 2 else 'earlyclub8'


def wilson(w, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * (c - h), 100 * (c + h))


def analyze(tag):
    files = sorted(glob.glob(f'{tag}_map_r0_*.ait'))
    rows = []
    for fn in files:
        t = open(fn, encoding='utf-8', errors='replace').read()
        if t.count('[BEAT') < 5:
            continue
        if '被祭司转换,归属阵营1->0' in t:
            res = 'W'
        elif 'DEFEAT: Priest killed' in t:
            res = 'P'
        elif 'DEFEAT: Town Center destroyed' in t:
            res = 'T'
        else:
            res = 'U'
        mpeak = 0
        for m in re.finditer(r'\[BEAT[^\n]*\bMil=(\d+)', t):
            mpeak = max(mpeak, int(m.group(1)))
        adv = re.search(r'Priest ADVANCE to Siege f=(\d+)', t)
        has_start = (adv is not None) or ('设置转换目标为 攻城武器厂' in t) or ('被祭司转换,归属阵营1->0' in t)
        ca = re.search(r'Counterattack! Frame=(\d+)', t)
        ca_f = int(ca.group(1)) if ca else 33001
        last = max([int(x) for x in re.findall(r'\[BEAT f=(\d+)', t)] or [0])
        rows.append(dict(res=res, mpeak=mpeak, has_start=has_start, last=last, ca_f=ca_f))
    return rows


def summarize(tag):
    rows = analyze(tag)
    n = len(rows)
    cnt = collections.Counter(r['res'] for r in rows)
    w = cnt['W']
    # 败因细分（仅在败局/未决里看机制）
    early = [r for r in rows if r['res'] == 'P' and not r['has_start'] and r['last'] < 33001]
    lateP = [r for r in rows if r['res'] == 'P' and r['has_start']]
    timeout = [r for r in rows if r['res'] == 'U']
    tc = [r for r in rows if r['res'] == 'T']
    mil_by_res = collections.defaultdict(list)
    for r in rows:
        mil_by_res[r['res']].append(r['mpeak'])
    return dict(tag=tag, n=n, cnt=cnt, w=w, early=early, lateP=lateP, timeout=timeout,
                tc=tc, mil_by_res=mil_by_res, rows=rows)


def med(xs):
    xs = sorted(xs)
    m = len(xs)
    if m == 0:
        return 0
    return xs[m // 2] if m % 2 else (xs[m // 2 - 1] + xs[m // 2]) / 2


A = summarize(TAG_A)
B = summarize(TAG_B)

print('=' * 104)
print(f'map 图新旧版对比：基线 {TAG_A} vs 新版 {TAG_B}（EARLY_CLUBMAN_TARGET 4→8）')
print('=' * 104)
print(f'{"指标":<22}{TAG_A:>16}{"":<2}{TAG_B:>16}')
print('-' * 104)

def line(name, va, vb):
    print(f'{name:<22}{va:>16}{"":<2}{vb:>16}')

loA, hiA = wilson(A['w'], A['n'])
loB, hiB = wilson(B['w'], B['n'])
line(f'胜率', f'{100*A["w"]/A["n"]:.1f}% [{loA:.0f},{hiA:.0f}]', f'{100*B["w"]/B["n"]:.1f}% [{loB:.0f},{hiB:.0f}]')
line(f'胜局数 W', A['cnt']['W'], B['cnt']['W'])
line(f'祭死 P', A['cnt']['P'], B['cnt']['P'])
line(f'TC毁 T', A['cnt']['T'], B['cnt']['T'])
line(f'超时 U', A['cnt']['U'], B['cnt']['U'])
print('-' * 104)
line(f'前期崩盘(早死无起手)', len(A['early']), len(B['early']))
line(f'反攻期祭死(有起手)', len(A['lateP']), len(B['lateP']))
line(f'超时未决', len(A['timeout']), len(B['timeout']))
print('-' * 104)
line(f'前期崩盘率', f'{100*len(A["early"])/A["n"]:.0f}%', f'{100*len(B["early"])/B["n"]:.0f}%')
line(f'反攻期祭死率', f'{100*len(A["lateP"])/A["n"]:.0f}%', f'{100*len(B["lateP"])/B["n"]:.0f}%')
print('-' * 104)
for res in ['W', 'P', 'U']:
    ma = med(A['mil_by_res'][res]) if A['mil_by_res'][res] else 0
    mb = med(B['mil_by_res'][res]) if B['mil_by_res'][res] else 0
    line(f'Mil峰中位({res})', ma, mb)
print('=' * 104)

# Fisher 精确检验（胜率）：用 log 空间避免 exp 下溢
def logfact(k):
    return sum(math.log(i) for i in range(1, k + 1)) if k > 0 else 0.0

a, b = A['w'], (A['n'] - A['w'])
c, d = B['w'], (B['n'] - B['w'])
n = a + b + c + d
row1, row2, col1, col2 = a + c, b + d, a + b, c + d

def table_lp(k):
    c2 = row1 - k; c3 = col1 - k; c4 = row2 - c3
    if k < 0 or c2 < 0 or c3 < 0 or c4 < 0:
        return None
    return (logfact(row1) + logfact(row2) + logfact(col1) + logfact(col2)
            - logfact(n) - logfact(k) - logfact(c2) - logfact(c3) - logfact(c4))

obs = table_lp(a)
lo, hi = max(0, a - d), min(row1, col1)
all_lp = [lp for k in range(lo, hi + 1) if (lp := table_lp(k)) is not None]
max_lp = max(all_lp)
p_two = sum(math.exp(lp - max_lp) for lp in all_lp if lp <= obs + 1e-9)
p_two = min(1.0, p_two * math.exp(max_lp))
print(f'Fisher 精确检验（胜率，双尾）：p={p_two:.3f}  （A胜{a}/{A["n"]}  vs  B胜{c}/{B["n"]}）')
print('=' * 104)
