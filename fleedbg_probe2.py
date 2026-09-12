# -*- coding: utf-8 -*-
"""
FLEEDBG v2：反攻期祭司“站着挨打”根因定位
核心问题：hp 在 (0.6, 1.0] 区间时 mustFlee 恒 0（远程威胁不触发撤退），
          若同时 healOverFlee=1（有伤兵要治），祭司会被钉在敌射程内治疗。
"""
import re, os
from collections import Counter

PAT = re.compile(
    r"\[FLEEDBG f=(\d+)\]\s+hp=([\d.]+)\s+mode=(\d+)\s+mustF=(\d+)\s+melee=(\d+)\s+"
    r"healOver=(\d+)\s+fleeLag=(\d+)\s+thr=([\d.]+)\s+thrR=([\d.]+)\s+"
    r"inCounter=(\d+)\s+canAct=(\d+)\s+st=(\d+)\s+cd=(\d+)\s+pXY=\(([-\d.]+),([-\d.]+)\)"
)
SENT = 1e10

def load(p):
    out = []
    for line in open(p, encoding="utf-8", errors="replace"):
        m = PAT.search(line)
        if m:
            out.append(dict(f=int(m.group(1)), hp=float(m.group(2)), mode=int(m.group(3)),
                            mustF=int(m.group(4)), melee=int(m.group(5)), healOver=int(m.group(6)),
                            fleeLag=int(m.group(7)), thr=float(m.group(8)), thrR=float(m.group(9)),
                            inCounter=int(m.group(10)), canAct=int(m.group(11)),
                            st=int(m.group(12)), cd=int(m.group(13)),
                            x=float(m.group(14)), y=float(m.group(15))))
    return out

files = [f"fd{i}.ait" for i in range(1, 9)]
allc = []
for p in files:
    if not os.path.exists(p): continue
    allc += [(p, x) for x in load(p) if x["inCounter"] == 1]

print("=" * 106)
print("表1  ★★★ 反攻期“身处敌射程内( thr<=thrR ) 却不撤退”的样本 —— 按 hp 分档")
print("     判据 mustFlee = melee || (hp<=0.6 && thr<=thrR)")
print("     故 hp>0.6 时，无论威胁多大都不撤退 ⇒ 远程消耗期“无感”")
print("=" * 106)
inR = [(p, x) for p, x in allc if x["thr"] < SENT and x["thr"] <= x["thrR"] + 1e-9 and x["melee"] == 0]
print(f"  身处射程内且无近战贴身的样本: {len(inR)} 条")
b = Counter()
for p, x in inR:
    if x["hp"] > 0.6:   b["hp>0.6 ⇒ mustFlee=0，不撤退"] += 1
    else:               b["hp<=0.6 ⇒ mustFlee=1，撤退"] += 1
for k, v in b.most_common():
    print(f"    {k}: {v} 条 ({100.0*v/max(len(inR),1):.1f}%)")

print("\n" + "=" * 106)
print("表2  ★★★ 危险组合：反攻期 + 身处敌射程内 + hp>0.6 + healOverFlee=1")
print("     ⇒ 祭司被“治疗伤兵”钉在敌射程里，且撤退判据根本没武装")
print("=" * 106)
dang = [(p, x) for p, x in allc
        if x["thr"] < SENT and x["thr"] <= x["thrR"] + 1e-9
        and x["hp"] > 0.6 and x["healOver"] == 1]
print(f"  命中样本: {len(dang)} 条")
if dang:
    byfile = Counter(p for p, _ in dang)
    for p, c in sorted(byfile.items()):
        print(f"    {p}: {c} 条")
    hs = [x["hp"] for _, x in dang]
    ths = [x["thr"] for _, x in dang]
    print(f"    hp 范围 {min(hs):.2f}~{max(hs):.2f}   thr 范围 {min(ths):.1f}~{max(ths):.1f}")
    # 最长连续段
    print("\n  最长连续段（同一坐标 + 同一状态）:")
    for p in sorted(byfile):
        s = [(pp, x) for pp, x in allc if pp == p]
        run, curxy, best, bestxy = 0, None, 0, None
        for _, x in s:
            xy = (round(x["x"], 2), round(x["y"], 2))
            if xy == curxy and x["healOver"] == 1 and x["hp"] > 0.6:
                run += 1
            else:
                if run > best: best, bestxy = run, curxy
                run = 1 if (x["healOver"] == 1 and x["hp"] > 0.6) else 0
            curxy = xy
        if run > best: best, bestxy = run, curxy
        if best >= 3:
            print(f"    {p}: {best} 采样 @ {bestxy} ≈ {best*5} 帧 ({best*5/25:.1f}s)")

print("\n" + "=" * 106)
print("表3  反攻期 hp 分布（看祭司通常在什么血量区间活动）")
print("=" * 106)
hs = sorted(x["hp"] for _, x in allc)
if hs:
    n = len(hs)
    print(f"  n={n}  min={hs[0]:.2f}  p25={hs[n//4]:.2f}  中位={hs[n//2]:.2f}  "
          f"p75={hs[3*n//4]:.2f}  max={hs[-1]:.2f}")
    for lo, hi in [(0.0,0.25),(0.25,0.5),(0.5,0.6),(0.6,0.75),(0.75,0.9),(0.9,1.01)]:
        c = sum(1 for h in hs if lo <= h < hi)
        print(f"    hp [{lo:.2f},{hi:.2f}): {c:5d} ({100.0*c/n:5.1f}%)")

print("\n" + "=" * 106)
print("表4  反攻期 thr 有效性（哨兵=完全无威胁记录）")
print("=" * 106)
c = Counter("哨兵(无威胁)" if x["thr"] >= SENT else "有效威胁" for _, x in allc)
for k, v in c.most_common():
    print(f"    {k}: {v} ({100.0*v/max(len(allc),1):.1f}%)")
print()
