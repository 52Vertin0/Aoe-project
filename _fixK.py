# -*- coding: utf-8 -*-
"""fixK（落点可达性分级退化）验证：三臂对照 + 退化触发 + ★静止局检测 + 护栏。
口径：[BEAT] 桶号免疫跳号；负 = 'DEFEAT: Priest killed'（禁裸 DEFEAT）；pr@=(0,0) 为死后哨兵，必须剔除。"""
import re, glob, collections, statistics as st, os

BL = 35.777

def load(tag):
    out = {}
    for fn in sorted(glob.glob(f'{tag}_*_r*_*.ait')):
        t = open(fn, encoding='utf-8', errors='replace').read()
        b = os.path.basename(fn)
        if t.count('[BEAT') < 5:
            out[b] = None; continue
        conv = '被祭司转换,归属阵营1->0' in t
        pdeath = 'DEFEAT: Priest killed' in t
        oc = 'W' if conv else ('P' if pdeath else 'T')
        mils = [int(x) for x in re.findall(r'Mil=(\d+)', t)]
        # [BEAT] 桶：帧 / Mil / pm五列 / pr@
        be = []
        for L in t.splitlines():
            if '[BEAT f=' not in L: continue
            m = re.search(r'\[BEAT f=(\d+)', L)
            if not m: continue
            f = int(m.group(1))
            mp = re.search(r'pr@=\(([-\d.]+),([-\d.]+)\)', L)
            mc = re.search(r'pm f(\d+) ca(\d+) h(\d+) cnt(\d+) o(\d+)', L)
            mm = re.search(r'Mil=(\d+)', L)
            pos = None
            if mp:
                x, y = float(mp.group(1)), float(mp.group(2))
                if not (abs(x) < 1e-6 and abs(y) < 1e-6):   # ★ 剔除死后哨兵 (0,0)
                    pos = (x, y)
            be.append(dict(f=f, pos=pos, pm=tuple(int(z) for z in mc.groups()) if mc else None,
                           mil=int(mm.group(1)) if mm else -1))
        endf = be[-1]['f'] if be else 0
        # ★ 静止局：局末 3000 帧内，祭司【有位置记录】但坐标极差 < 2 格，且 pm 全零
        tail = [x for x in be if x['f'] > endf - 3000 and x['pos']]
        still = False; spread = -1
        if len(tail) >= 6:
            xs = [p['pos'][0] for p in tail]; ys = [p['pos'][1] for p in tail]
            spread = max(max(xs) - min(xs), max(ys) - min(ys))
            pmz = all((p['pm'] == (0, 0, 0, 0, 0)) for p in tail if p['pm'])
            still = (spread < 2.0 and pmz and endf > 20000)   # ⚠ endf 下限：排除开局探路期/未结算短局（探路不计 g_pm*，易误判）
        # dS 序列（[LC-DBG]）
        ds = [(int(m.group(1)), float(m.group(2))) for m in
              re.finditer(r'\| (\d+) \|[^\n]*?dS=([-\d.]+)', t)]
        degs = [int(m.group(1)) for m in re.finditer(r'\[PRIEST-ADV-DEGRADE f=(\d+)\]', t)]
        advs = [int(m.group(1)) for m in re.finditer(r'Priest ADVANCE to Siege f=(\d+)', t)]
        out[b] = dict(_k=b, oc=oc, endf=endf, mil_max=max(mils) if mils else 0, mil_end=mils[-1] if mils else -1,
                      escA=len(re.findall(r'\[PRIEST-ESCAPE A f=', t)),
                      escB=len(re.findall(r'\[PRIEST-ESCAPE B f=', t)),
                      escBR=len(re.findall(r'\[PRIEST-ESCAPE-BREAK f=', t)),
                      deg=len(degs), degf=degs[0] if degs else -1,
                      adv=len(advs), nconv=len(re.findall(r'Priest converting Siege Workshop', t)),
                      still=still, spread=spread, ds=ds, tail=tail,
                      ca=next((int(m.group(1)) for m in re.finditer(r'Counterattack! Frame=(\d+)', t)), -1))
    return out

TAGS = ['fixI', 'fixJ', 'fixK']
D = {t: load(t) for t in TAGS}

def agg(rows):
    v = [r for r in rows if r]
    n = len(v); w = sum(1 for r in v if r['oc'] == 'W')
    return n, w, 100 * w / max(1, n)

print('=' * 112)
print('§1 三臂总览')
print('=' * 112)
for t in TAGS:
    n, w, r = agg(D[t].values())
    v = [x for x in D[t].values() if x]
    stl = sum(1 for x in v if x['still'])
    print(f'  {t:<6} 有效局={n:>3}  胜={w:>3}({r:>4.1f}%)  祭死={sum(1 for x in v if x["oc"]=="P") :>3}  超时={sum(1 for x in v if x["oc"]=="T"):>3}'
          f'    ★静止局={stl:>2}   退化触发局={sum(1 for x in v if x["deg"]>0):>2}')

print()
print('=' * 112)
print('§2 ★ fixK 生效判据：[PRIEST-ADV-DEGRADE] 触发')
print('=' * 112)
vk = [x for x in D['fixK'].values() if x]
dg = sorted([x for x in vk if x['deg'] > 0], key=lambda x: x['degf'])
print(f'  触发局数 = {len(dg)}/{len(vk)}   总触发次数 = {sum(x["deg"] for x in vk)}')
if dg:
    print(f'  {"局":<24}{"结局":>5}{"退化次数":>9}{"首帧":>8}{"escA+B":>8}{"adv":>5}{"nconv":>6}{"静止":>5}')
    for x in dg:
        print(f'  {x["_k"]:<24}{x["oc"]:>5}{x["deg"]:>9}{x["degf"]:>8}{x["escA"]+x["escB"]:>8}{x["adv"]:>5}{x["nconv"]:>6}{str(x["still"]):>5}')

print()
print('=' * 112)
print('§3 ★★ 核心：静止局（活锁）三臂对照 —— 这是 fixK 要消灭的靶子')
print('=' * 112)
for t in TAGS:
    v = [x for x in D[t].values() if x]
    s = [x for x in v if x['still']]
    print(f'  {t:<6} 静止局 n={len(s):>2}  ' + str(dict(collections.Counter(x['oc'] for x in s))))
    for x in sorted(s, key=lambda z: z['_k']):
        print(f'          {x["_k"]:<24} {x["oc"]}  escA+B={x["escA"]+x["escB"]:>3} adv={x["adv"]:>3} deg={x["deg"]:>3} 末帧={x["endf"]}')

print()
print('=' * 112)
print('§4 分图胜率（fixI → fixJ → fixK）')
print('=' * 112)
def mp(k): return k.split('_')[1]
for g in ['map', 'map1', 'map2', 'map3']:
    line = f'  {g:<6}'
    for t in TAGS:
        n, w, r = agg([x for k, x in D[t].items() if mp(k) == g])
        line += f'  {t} {w:>2}/{n:<2}({r:>4.0f}%)'
    print(line)

print()
print('=' * 112)
print('§5 护栏：前期节律（应三臂持平）')
print('=' * 112)
for t in TAGS:
    f5, f12, mx = [], [], []
    for k, x in D[t].items():
        if not x: continue
        t2 = open(k, encoding='utf-8', errors='replace').read()
        ser = [(int(m.group(1)), int(m.group(2))) for m in re.finditer(r'\[BEAT f=(\d+)[^\n]*?Mil=(\d+)', t2)]
        a = next((f for f, m in ser if m > 4), None)
        b2 = next((f for f, m in ser if m >= 12), None)
        if a: f5.append(a)
        if b2: f12.append(b2)
        mx.append(max((m for _, m in ser), default=0))
    med = lambda v: st.median(v) if v else float('nan')
    print(f'  {t:<6} Mil首>4 中位={med(f5):>7.0f}({med(f5)/1500:>4.1f}分)  首>=12 中位={med(f12):>7.0f}  mil_max中位={med(mx):>4.0f}')

print()
print('=' * 112)
print('§6 退化局的 dS 轨迹：退化后是否产生【真进展】？')
print('=' * 112)
for x in dg[:6]:
    print(f'--- {x["_k"]}  结局={x["oc"]}  首退化@f={x["degf"]}  共{x["deg"]}次  escA+B={x["escA"]+x["escB"]} ---')
    seg = [d for d in x['ds'] if d[0] >= x['degf']]
    pre = [d for d in x['ds'] if d[0] < x['degf']][-1:]
    for f, d in pre:
        print(f'    f={f:>6} dS={d:>6.1f}   ←退化前')
    for f, d in seg[:16]:
        print(f'    f={f:>6} dS={d:>6.1f}')
    if len(seg) > 16:
        for f, d in seg[-4:]:
            print(f'    f={f:>6} dS={d:>6.1f}   ←末')
    print()

print('=' * 112)
print('§7 规模：adv=0 的局（= 整届反攻期一条"正常推进"都没发出去 ⇒ 理想落点从未可达）')
print('=' * 112)
for t in TAGS:
    v = [x for x in D[t].values() if x]
    z = [x for x in v if x['adv'] == 0]
    z2 = [x for x in z if x['escA'] + x['escB'] > 0]
    print(f'  {t:<6} adv=0 局 n={len(z):>2}/{len(v)}（其中 escA+B>0（纯侧移）={len(z2):>2}）  '
          f'结局 {dict(collections.Counter(x["oc"] for x in z))}')
