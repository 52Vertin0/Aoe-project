# -*- coding: utf-8 -*-
"""
FLEEDBG 分析：反攻期祭司的 mustFlee / mode 判定链
口径字段：hp mode mustF melee healOver fleeLag thr thrR inCounter canAct st cd pXY
"""
import re, os, sys
from collections import Counter

PAT = re.compile(
    r"\[FLEEDBG f=(\d+)\]\s+hp=([\d.]+)\s+mode=(\d+)\s+mustF=(\d+)\s+melee=(\d+)\s+"
    r"healOver=(\d+)\s+fleeLag=(\d+)\s+thr=([\d.]+)\s+thrR=([\d.]+)\s+"
    r"inCounter=(\d+)\s+canAct=(\d+)\s+st=(\d+)\s+cd=(\d+)\s+pXY=\(([-\d.]+),([-\d.]+)\)"
)

def load(path):
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = PAT.search(line)
            if m:
                out.append(dict(
                    f=int(m.group(1)), hp=float(m.group(2)), mode=int(m.group(3)),
                    mustF=int(m.group(4)), melee=int(m.group(5)), healOver=int(m.group(6)),
                    fleeLag=int(m.group(7)), thr=float(m.group(8)), thrR=float(m.group(9)),
                    inCounter=int(m.group(10)), canAct=int(m.group(11)),
                    st=int(m.group(12)), cd=int(m.group(13)),
                    x=float(m.group(14)), y=float(m.group(15)),
                ))
    return out

files = [f"fd{i}.ait" for i in range(1, 9)]
allc = []   # 反攻期样本
for p in files:
    if not os.path.exists(p): continue
    s = load(p)
    c = [x for x in s if x["inCounter"] == 1]
    if c:
        allc += [(p, x) for x in c]
    if s:
        print(f"{p}: 总 {len(s)}  反攻期 {len(c)}")

print("\n" + "=" * 104)
print("表A  【反攻期】mustFlee 判据四要素的一致性检查")
print("     mustFlee = melee || (hp<=0.6 && thr<=thrR)")
print("=" * 104)
bad = []
for p, x in allc:
    expect = 1 if (x["melee"] == 1 or (x["hp"] <= 0.6 and x["thr"] <= x["thrR"] + 1e-9)) else 0
    if expect != x["mustF"]:
        bad.append((p, x, expect))
print(f"  样本 {len(allc)} 条，mustF 与公式【不一致】{len(bad)} 条")
for p, x, e in bad[:5]:
    print(f"    {p} f={x['f']} hp={x['hp']} melee={x['melee']} thr={x['thr']} thrR={x['thrR']} "
          f"-> 实测 mustF={x['mustF']} 期望{e}")

print("\n" + "=" * 104)
print("表B  ★★ 反攻期：hp<=0.6 且 thr<=thrR（mustFlee 必为真）时，mode 是否为 1？")
print("     —— 若不是 1，说明 priestFlee 未被调用 或 调用后 priestMode 又被复位")
print("=" * 104)
sub = [(p, x) for p, x in allc if x["hp"] <= 0.6 and x["thr"] <= x["thrR"] + 1e-9]
cnt = Counter(x["mode"] for _, x in sub)
print(f"  命中样本 {len(sub)} 条，mode 分布: {dict(cnt)}")
print()
# 按局细分
for p in files:
    ps = [(pp, x) for pp, x in sub if pp == p]
    if not ps: continue
    c = Counter(x["mode"] for _, x in ps)
    m0 = c.get(0, 0)
    print(f"  {p}: 命中 {len(ps)} 条 → mode {dict(c)}"
          + ("   ★★ mode=0 占比 %.0f%%（该逃未逃！）" % (100.0*m0/len(ps)) if m0 else ""))

print("\n" + "=" * 104)
print("表C  ★★★ 反攻期不应逃的原因判定（mustF=1 但 mode=0 的样本）")
print("=" * 104)
badCases = [(p, x) for p, x in allc if x["mustF"] == 1 and x["mode"] == 0]
print(f"  mustF=1 却 mode=0 的样本: {len(badCases)} 条 / mustF=1 共 "
      f"{sum(1 for _, x in allc if x['mustF']==1)} 条")
if badCases:
    c = Counter()
    for p, x in badCases:
        if x["healOver"] == 1: c["healOverFlee=1（压制治疗档）"] += 1
        elif x["cd"] > 0:      c["cd>0（冷却期内 priestFlee 直接 return）"] += 1
        elif x["fleeLag"] == 1: c["fleeLag=1 但走的是 L1290 迟滞分支"] += 1
        else:                  c["其它"] += 1
    for k, v in c.most_common():
        print(f"    {k}: {v} 条")
    # 细看 healOver 情况
    ho = [(p, x) for p, x in badCases if x["healOver"] == 1]
    print(f"\n  其中 healOverFlee=1 (healOver 压制): {len(ho)} 条")
    for p, x in ho[:6]:
        print(f"    {p} f={x['f']} hp={x['hp']} mode={x['mode']} mustF={x['mustF']} "
              f"healOver={x['healOver']} melee={x['melee']} thr={x['thr']} thrR={x['thrR']} cd={x['cd']}")

print("\n" + "=" * 104)
print("表D  ★★★ 祭司坐标冻结检测（同坐标连续采样 = 站着挨打）")
print("=" * 104)
for p in files:
    if not os.path.exists(p): continue
    s = [x for x in load(p) if x["inCounter"] == 1]
    if not s: continue
    # 找最长同坐标连续段
    best_run, best_xy, cur, curxy = 0, None, 0, None
    for x in s:
        xy = (round(x["x"], 2), round(x["y"], 2))
        if xy == curxy: cur += 1
        else:
            if cur > best_run: best_run, best_xy = cur, curxy
            cur, curxy = 1, xy
    if cur > best_run: best_run, best_xy = cur, curxy
    if best_xy and best_run >= 3:
        print(f"  {p}: 最长坐标冻结 {best_run} 个连续采样 @ {best_xy} (每采样 5 帧 ⇒ 约 {best_run*5} 帧)")
    else:
        print(f"  {p}: 无长冻结（最长 {best_run}）")
print()
