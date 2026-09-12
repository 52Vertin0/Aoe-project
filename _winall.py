# -*- coding: utf-8 -*-
"""
胜率总账 v2（各臂对照 + 正确显著性 + 噪声标定 + 分图 CI）
用法: python _winall.py
口径: 胜 = ait 内出现 '被祭司转换,归属阵营1->0'（与 _fixM.py / _all96.py 一致）
      负 = 'DEFEAT: Priest killed' / 'DEFEAT: Town Center destroyed'（精确匹配，禁用裸 'DEFEAT'）
      其余 = 超时/未结算
"""
import re, glob, os, collections, math

ARMS = ['base0', 'fix1', 'base1', 'fix2', 'fixH', 'fixI', 'fixJ', 'fixK', 'fixL', 'fixM',
        'fixN3', 'fixK2', 'fixG', 'fix5']
MAPS = ['map', 'map1', 'map2', 'map3']


def outcome(t):
    if '被祭司转换,归属阵营1->0' in t:
        return 'W'
    if 'DEFEAT: Priest killed' in t:
        return 'P'
    if 'DEFEAT: Town Center destroyed' in t:
        return 'TC'
    return 'T'


def load(tag, need_beat=5):
    rows = []
    for fn in sorted(glob.glob(f'{tag}_*_r0_*.ait')):
        t = open(fn, encoding='utf-8', errors='replace').read()
        if t.count('[BEAT') < need_beat:
            continue
        mp = os.path.basename(fn).replace(tag + '_', '').split('_r0_')[0]
        rows.append((mp, outcome(t)))
    return rows


L = math.lgamma


def fisher(a, b, c, d):
    """双尾 Fisher 精确检验（对数空间 + 减最大值，避免下溢）"""
    N = a + b + c + d
    r1, r2, c1, c2 = a + b, c + d, a + c, b + d
    if 0 in (r1, r2, c1, c2):
        return 1.0
    logs = {}
    for x in range(max(0, c1 - r2), min(r1, c1) + 1):
        logs[x] = (L(r1 + 1) + L(r2 + 1) + L(c1 + 1) + L(c2 + 1) - L(N + 1)
                   - L(x + 1) - L(r1 - x + 1) - L(c1 - x + 1) - L(c2 - r1 + x + 1))
    mx = max(logs.values())
    ps = {x: math.exp(v - mx) for x, v in logs.items()}
    tot = sum(ps.values())
    obs = ps[a]
    return sum(v for v in ps.values() if v <= obs + 1e-12) / tot


def wilson(w, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * (c - h), 100 * (c + h))


def fmt(rows):
    kc = collections.Counter(k for _, k in rows)
    n = len(rows)
    return dict(n=n, W=kc['W'], P=kc['P'], TC=kc['TC'], T=kc['T'], rate=kc['W'] / n,
                per=collections.Counter(m for m, _ in rows),
                perW=collections.Counter(m for m, k in rows if k == 'W'))


print('=' * 122)
print('§ 1  各臂胜率总账')
print('=' * 122)
print(f'{"臂":<7}{"局数":>5}{"胜":>5}{"胜率":>9}{"95%CI(Wilson)":>18}{"祭死":>6}{"超时":>6}   '
      + ''.join(f'{m:>8}' for m in MAPS))
print('-' * 122)
store = {}
for tg in ARMS:
    r0 = load(tg)
    if not r0:
        continue
    r = fmt(r0); store[tg] = r
    lo, hi = wilson(r['W'], r['n'])
    cell = [f'{r["perW"][m]}/{r["per"][m]}' if r['per'][m] else '—' for m in MAPS]
    print(f'{tg:<7}{r["n"]:>5}{r["W"]:>5}{100*r["rate"]:>8.1f}%{f"[{lo:.0f},{hi:.0f}]":>18}'
          f'{r["P"]:>6}{r["T"]:>6}   ' + ''.join(f'{c:>8}' for c in cell))

print()
print('=' * 122)
print('§ 2  fixM 对照检验（双尾 Fisher 精确检验）')
print('=' * 122)
M = store['fixM']
for tg in ['base1', 'fix2', 'fixH', 'fixI', 'fixJ', 'fixK', 'fixL']:
    A = store.get(tg)
    if not A:
        continue
    p = fisher(M['W'], M['n'] - M['W'], A['W'], A['n'] - A['W'])
    flag = '  ← p<0.05' if p < 0.05 else ('  ← p<0.10' if p < 0.10 else '')
    print(f'  总体  fixM {M["W"]:>2}/{M["n"]} ({100*M["rate"]:.1f}%)  vs  {tg:<5} '
          f'{A["W"]:>2}/{A["n"]} ({100*A["rate"]:.1f}%)   Δ={100*(M["rate"]-A["rate"]):+5.1f}pp   p={p:.4f}{flag}')

print()
print('  分图对照（每格 12~24 局 ⇒ 单格噪声极大，只看方向）')
for m in MAPS:
    parts = []
    for tg in ['fixI', 'fixK', 'fixL', 'fixM']:
        A = store.get(tg)
        if A and A['per'].get(m):
            parts.append(f'{tg} {A["perW"][m]:>2}/{A["per"][m]}')
    A = store['fixI']
    if A['per'].get(m) and M['per'].get(m):
        p = fisher(M['perW'][m], M['per'][m] - M['perW'][m],
                   A['perW'][m], A['per'][m] - A['perW'][m])
        d = 100 * (M['perW'][m] / M['per'][m] - A['perW'][m] / A['per'][m])
        parts.append(f'| I→M Δ={d:+5.1f}pp  p={p:.3f}')
    print(f'    {m:<6} ' + '   '.join(parts))

print()
print('=' * 122)
print('§ 3  ★★★ 噪声标定（本回答的核心：噪声到底多大？）')
print('=' * 122)
print('  【A】同一份二进制的批间复跑（fixK vs fixK2，仅 map 24 局）')
K, K2 = store['fixK'], store['fixK2']
w1, n1 = K['perW']['map'], K['per']['map']
print(f'       批1 {w1}/{n1} = {100*w1/n1:.1f}%   批2 {K2["W"]}/{K2["n"]} = {100*K2["rate"]:.1f}%   '
      f'Δ = {100*(K2["rate"]-w1/n1):+.1f}pp  （n=24 时 95%CI 宽 ≈ ±{wilson(w1,n1)[1]-wilson(w1,n1)[0]:.0f}pp）')

print()
print('  【B】行为等价/近等价的 96 局臂两两之差')
print('      —— 判别组（这些代码改动此前都判"胜率无变化"，用于标定噪声）')
pairs = [('fixI', 'fixJ', 'fixJ 的 GIVEUP 只在 7/96 局触发'),
         ('fixI', 'fixL', 'fixL 只改 W3 护驾目标筛选'),
         ('fixK', 'fixL', '同上，叠在 fixK 上'),
         ('fixI', 'fixK', 'fixK 纯新增 26 行、落点可达时逐位不变')]
null_diffs = []
for x, y, why in pairs:
    A, B = store[x], store[y]
    d = abs(A['W'] - B['W'])
    null_diffs.append(d)
    print(f'          {x:<5} {A["W"]:>2}/96  ↔  {y:<5} {B["W"]:>2}/96   差 {d} 局 ({100*d/96:>4.1f}pp)   <{why}>')
rms = math.sqrt(sum(d * d for d in null_diffs) / len(null_diffs))
print(f'          ⇒ 判别组的臂间差 = {null_diffs} 局  ⇒ 极差 {max(null_diffs)} 局 = {100*max(null_diffs)/96:.1f}pp，RMS {rms:.1f} 局')
print('      —— 检验组（待判效果，不参与噪声标定）')
for x, y, why in [('fixK', 'fixM', 'fixM 只改祭司目标排序'), ('fixI', 'fixM', '本轮要判的差')]:
    A, B = store[x], store[y]
    d = B['W'] - A['W']
    print(f'          {x:<5} {A["W"]:>2}/96  →  {y:<5} {B["W"]:>2}/96   差 {d:+d} 局 ({100*d/96:+.1f}pp)   <{why}>'
          f'   = {abs(d)/rms:.1f}× 判别组 RMS')
print(f'          ⚠ 判别组 n 仅 {len(null_diffs)}，RMS 是下界估计；独立二项模型给出更保守的 6.9 局（见 §3 说明）。')

print()
print('  【C】逐局结局一致率（说明"局级是混沌的、但总量稳定"）')
def rd(tag):
    d = {}
    for fn in sorted(glob.glob(f'{tag}_*_r0_*.ait')):
        t = open(fn, encoding='utf-8', errors='replace').read()
        if t.count('[BEAT') < 5:
            continue
        b = os.path.basename(fn).replace(tag + '_', '').replace('.ait', '')
        d[b] = outcome(t)
    return d

for x, y in [('fixI', 'fixJ'), ('fixK', 'fixK2'), ('fixK', 'fixM'), ('fixI', 'fixM')]:
    da, db = rd(x), rd(y)
    com = set(da) & set(db)
    if not com:
        continue
    same = sum(1 for k in com if da[k] == db[k])
    print(f'       {x:<5} ↔ {y:<5}  可比局 {len(com):>3}   一致率 {100*same/len(com):>5.1f}%')
print('       ⇒ 逐局一致率仅 4~5 成（局级完全混沌），但【总胜局数】在不同臂间只差 0~4 局')
print('          ⇒ 结论：n=96 的总量比单局稳定得多；单图 n=12~24 的格子才是噪声重灾区。')

print()
print('  【D】单图 n=12 vs n=24 的 CI 宽度对比（解释"±17pp"从哪来）')
for w, n in [(4, 12), (4, 24), (7, 24), (12, 24)]:
    lo, hi = wilson(w, n)
    print(f'       {w:>2}/{n:<3} = {100*w/n:>5.1f}%   95%CI [{lo:.0f}%, {hi:.0f}%]   宽 {hi-lo:.0f}pp')

print()
print('=' * 122)
print('§ 4  §3 结论对 §0「噪声铁律」的影响')
print('=' * 122)
print(f'  旧记录：「24 局/臂胜率噪声带 ≈ ±17pp（同代码空转臂实测 16.7% vs 33%）」')
print(f'  ⇒ 该 16.7% 与 33% 实为 fixG map 4/24 与 fix1 map 4/12（n=12！）⇒ 后者 CI 宽 ≈ '
      f'{wilson(4,12)[1]-wilson(4,12)[0]:.0f}pp ⇒ 属小样本伪噪声，不能外推到 n=96。')
print(f'  ⇒ 修正：n=96 总量层面，"同行为"臂间差实测 ≤4 局（≤4.2pp）；噪声带应记为 ≈±4~5pp。')
print(f'     单图 n=24 层面：同二进制批间差 4.2pp，但 CI 宽 {wilson(3,24)[1]-wilson(3,24)[0]:.0f}pp。')
