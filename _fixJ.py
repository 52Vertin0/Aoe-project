# -*- coding: utf-8 -*-
"""fixJ（脱困总预算）专项验证：生效判据 + 机制量 + 护栏 + 与 fixI 逐局对照。
口径：一律用 [BEAT] 桶号免疫 frame 跳号；负 = 'DEFEAT: Priest killed'（禁裸 DEFEAT）。"""
import re, glob, collections, statistics as st, os, sys, csv

def load(tag):
    out = {}
    for fn in sorted(glob.glob(f'{tag}_*_r*_*.ait')):
        t = open(fn, encoding='utf-8', errors='replace').read()
        base = os.path.basename(fn)
        # 空壳剔除：至少 5 条 [BEAT]
        if t.count('[BEAT') < 5:
            out[base] = None
            continue
        conv = '被祭司转换,归属阵营1->0' in t
        pdeath = 'DEFEAT: Priest killed' in t
        tclost = 'DEFEAT: Town Center destroyed' in t
        oc = 'W' if conv else ('P' if pdeath else ('T' if tclost else 'T'))
        beats = re.findall(r'\[BEAT f=(\d+)', t)
        mils = [int(x) for x in re.findall(r'Mil=(\d+)', t)]
        def cnt(tagpat):
            return len(re.findall(re.escape(tagpat), t))
        escapes = [int(m.group(1)) for m in re.finditer(r'\[PRIEST-ESCAPE [AB] f=(\d+)\]', t)]
        giveups = [int(m.group(1)) for m in re.finditer(r'\[PRIEST-ESCAPE-GIVEUP f=(\d+)\]', t)]
        resumes = [int(m.group(1)) for m in re.finditer(r'\[PRIEST-ESCAPE-RESUME f=(\d+)\]', t)]
        advs = [int(m.group(1)) for m in re.finditer(r'Priest ADVANCE to Siege f=(\d+)', t)]
        # GIVEUP 之后（到下一个 RESUME 之前）是否仍有脱困 ⇒ 应在 0
        leak = 0
        for g in giveups:
            nxt = [r for r in resumes if r > g]
            hi = min(nxt) if nxt else 10 ** 9
            leak += sum(1 for e in escapes if g < e < hi)
        hit = [f for f in (int(m.group(1)) for m in re.finditer(r'Counterattack! Frame=(\d+)', t))]
        out[base] = dict(
            _k=base,
            oc=oc, nbeat=len(beats), endf=max(int(x) for x in beats) if beats else 0,
            mil_max=max(mils) if mils else 0, mil_end=mils[-1] if mils else 0,
            escA=cnt('[PRIEST-ESCAPE A f='), escB=cnt('[PRIEST-ESCAPE B f='),
            escBR=cnt('[PRIEST-ESCAPE-BREAK f='),
            giveup=len(giveups), gupf=giveups[0] if giveups else -1,
            resume=len(resumes), leak=leak,
            adv=len(advs), caf=hit[0] if hit else -1,
            fws=len(re.findall(r'Enemy Siege Workshop found at', t)),
            nconv=len(re.findall(r'Priest converting Siege Workshop', t)),
        )
    return out

A = load('fixI'); B = load('fixJ')

def s(rows, k):
    return [r[k] for r in rows if r]

def rate(rows):
    v = [r for r in rows if r]
    if not v: return (0, 0, 0, 0)
    w = sum(1 for r in v if r['oc'] == 'W'); p = sum(1 for r in v if r['oc'] == 'P'); t = sum(1 for r in v if r['oc'] == 'T')
    return (len(v), w, p, t)

print('=' * 104)
print('§1 总量与胜率（口径：有效局 = 至少 5 条 [BEAT]）')
print('=' * 104)
for nm, D in [('fixI(基线)', A), ('fixJ(本轮)', B)]:
    v = [r for r in D.values() if r]
    n, w, p, t = rate(D.values())
    print(f'  {nm:<12} 有效局={n:>3}  胜={w:>3}({100*w/max(1,n):>4.1f}%)  祭死={p:>3}  超时={t:>3}  空壳/无效={sum(1 for x in D.values() if x is None):>3}')

print()
print('§2 ★ 生效判据：GIVEUP / RESUME 触发情况（fixJ）')
vJ = [r for r in B.values() if r]
gun = [r for r in vJ if r['giveup'] > 0]
print(f'  GIVEUP 触发局数 = {len(gun)}/{len(vJ)}    总触发次数 = {sum(r["giveup"] for r in vJ)}')
print(f'  RESUME 触发局数 = {sum(1 for r in vJ if r["resume"] > 0)}    总触发次数 = {sum(r["resume"] for r in vJ)}')
print(f'  ★ 闸泄漏（GIVEUP 后到 RESUME 前仍有脱困）= {sum(r["leak"] for r in vJ)}   ← 期望 0')
if gun:
    print()
    print(f'  {"局":<26}{"结局":<4}{"GIVEUP首帧":>10}{"次数":>5}{"RESUME":>7}{"escA":>5}{"escB":>5}{"escBR":>6}{"adv":>5}{"nconv":>6}{"mil末":>6}{"泄漏":>5}')
    for r in sorted(gun, key=lambda x: x['gupf']):
        print(f'  {r["_k"]:<26}{r["oc"]:<4}{r["gupf"]:>10}{r["giveup"]:>5}{r["resume"]:>7}{r["escA"]:>5}{r["escB"]:>5}{r["escBR"]:>6}{r["adv"]:>5}{r["nconv"]:>6}{r["mil_end"]:>6}{r["leak"]:>5}')

print()
print('§3 关键对照：fixI 中 escA+escB>=12 的 6 个活锁局，在 fixJ 里变成什么')
print('-' * 104)
lock = [k for k, r in A.items() if r and r['escA'] + r['escB'] >= 12]
print(f'  {"局":<26}{"fixI结局":>9}{"fixI脱困":>9}{"fixI_adv":>9}   {"fixJ结局":>9}{"fixJ脱困":>9}{"fixJ_adv":>9}{"GIVEUP":>7}{"RESUME":>7}')
for k in sorted(lock):
    a = A[k]; b = B.get(k)
    if not b:
        print(f'  {k:<26}  [fixJ 缺失]'); continue
    print(f'  {k:<26}{a["oc"]:>9}{a["escA"]+a["escB"]:>9}{a["adv"]:>9}   {b["oc"]:>9}{b["escA"]+b["escB"]:>9}{b["adv"]:>9}{b["giveup"]:>7}{b["resume"]:>7}')

print()
print('§4 分图胜率（fixI → fixJ）')
print('-' * 104)
def mp(k):
    m = k.split('_')[1]
    return m
for g in ['map', 'map1', 'map2', 'map3']:
    ra = [r for k, r in A.items() if r and mp(k) == g]
    rb = [r for k, r in B.items() if r and mp(k) == g]
    na, wa, _, _ = rate(ra); nb, wb, _, _ = rate(rb)
    print(f'  {g:<6} fixI {wa:>2}/{na:<2}({100*wa/max(1,na):>4.0f}%)   →   fixJ {wb:>2}/{nb:<2}({100*wb/max(1,nb):>4.0f}%)   Δ={100*wb/max(1,nb)-100*wa/max(1,na):>+5.1f}pp')

print()
print('§5 护栏：前期经济/军队节律（应与 fixI 持平）')
print('-' * 104)
for nm, D in [('fixI', A), ('fixJ', B)]:
    f5, f12, f25, mx = [], [], [], []
    for k, r in D.items():
        if not r: continue
        t = open(k, encoding='utf-8', errors='replace').read()
        ser = [(int(m.group(1)), int(m.group(2))) for m in re.finditer(r'\[BEAT f=(\d+)[^\n]*?Mil=(\d+)', t)]
        a = next((f for f, m in ser if m > 4), None)
        b2 = next((f for f, m in ser if m >= 12), None)
        c = next((f for f, m in ser if m >= 25), None)
        if a: f5.append(a)
        if b2: f12.append(b2)
        if c: f25.append(c)
        mx.append(max((m for _, m in ser), default=0))
    med = lambda v: st.median(v) if v else float('nan')
    print(f'  {nm}  Mil首>4 中位={med(f5):>7.0f}({med(f5)/1500:>4.1f}分) 首>=12={med(f12):>7.0f}({med(f12)/1500:>4.1f}分) 首>=25={med(f25):>7.0f}  mil_max中位={med(mx):>4.0f}')

print()
print('§6 结局分布对照（逐局配对，仅两臂都有效的局）')
print('-' * 104)
both = [(k, A[k], B[k]) for k in A if A.get(k) and B.get(k)]
trans = collections.Counter((a['oc'], b['oc']) for _, a, b in both)
print(f'  配对局数 = {len(both)}')
for (o1, o2), n in sorted(trans.items(), key=lambda x: -x[1]):
    print(f'    fixI {o1} → fixJ {o2} : {n:>3}')
