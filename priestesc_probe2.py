# -*- coding: utf-8 -*-
"""
祭司反攻期被杀 —— 根因量化（v2）
核心疑点：enemyThreatRange 用 12 格算所有远程兵，但战车弓兵真实射程 7 格。
          同时 threatDist 只记录 d <= r+4 的目标 ⇒ 12 格兵种的记录门槛 = 16 格。
判据：mustFlee(inCounter) = meleeAdj || (pBRc <= 0.6 && threatDist <= nearestThreatR)
"""
import re, os
from collections import Counter

# config.h:577-594 枚举
SORT_NAME = {
    0:"棍兵", 1:"投石兵", 2:"弓兵", 3:"侦察", 4:"剑士", 5:"精锐剑士",
    6:"骑兵", 7:"船", 8:"投石车", 9:"祭司", 10:"方阵兵",
    11:"战车", 12:"战车弓兵", 13:"阔剑兵", 14:"复合弓兵",
}
REAL_RANGE = {0:2.5,1:4.0,2:5.0,3:5.0,4:2.5,5:2.5,6:5.0,7:5.0,
              8:10.0,9:5.0,10:5.0,11:5.0,12:7.0,13:2.5,14:7.0}
def threat_range(s):
    return 12.0 if s in (1,2,12,14) or s == 8 else 2.5

PAT = re.compile(
    r"\[PESC f=(\d+)\]\s+hp=([\d.]+)\s+mode=(\d+)\s+nearE=([\d.]+)\s+"
    r"threat=([\d.eE+-]+)\s+nRSort=(-?\d+)\s+nRD=([\d.]+)\s+threatR=([\d.]+)"
)
SENT = 1e10

def series(path):
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = PAT.search(line)
            if m:
                out.append(dict(f=int(m.group(1)), hp=float(m.group(2)), mode=int(m.group(3)),
                                nearE=float(m.group(4)), threat=float(m.group(5)),
                                nRSort=int(m.group(6)), nRD=float(m.group(7)),
                                threatR=float(m.group(8))))
    return out

print("=" * 108)
print("表1  观测到的 nRSort → 兵种解码（谁在打祭司）")
print("=" * 108)
print(f"{'nRSort':<8}{'兵种':<12}{'真实射程':<10}{'代码威胁半径':<14}{'误算倍数':<10}")
for s in sorted(SORT_NAME):
    print(f"{s:<8}{SORT_NAME[s]:<12}{REAL_RANGE[s]:<10.1f}{threat_range(s):<14.1f}"
          f"{threat_range(s)/max(REAL_RANGE[s],0.1):<10.1f}")

files = [f"pe{i}.ait" for i in range(1, 9)]
allS = []
print("\n" + "=" * 108)
print("表2  每局：祭司挨打→逃跑 预警链")
print("=" * 108)
print(f"{'局':<6}{'样本':<7}{'首挨打f':<10}{'首挨打hp':<10}{'首逃f':<10}{'首逃hp':<9}"
      f"{'延迟帧':<8}{'延迟s':<8}{'期间掉血pp':<11}{'min hp':<8}{'结局':<10}")
for p in files:
    if not os.path.exists(p):
        continue
    s = series(p)
    if not s:
        continue
    allS += [(p, x) for x in s]
    fb = next((x for x in s if x["hp"] < 0.995), None)
    ff = next((x for x in s if x["mode"] == 1), None)
    hpmin = min(x["hp"] for x in s)
    # 结局
    txt = open(p, encoding="utf-8", errors="replace").read()
    win = "VICTORY" in txt
    died = "Priest killed" in txt or "祭司阵亡" in txt
    end = "胜" if win else ("祭司亡" if died else "未决")
    delay = (ff["f"] - fb["f"]) if (fb and ff) else None
    dhp = (fb["hp"] - ff["hp"]) * 100 if (fb and ff) else None
    print(f"{p[:-4]:<6}{len(s):<7}"
          f"{fb['f'] if fb else '-':<10}{fb['hp'] if fb else '-':<10}"
          f"{ff['f'] if ff else '-':<10}{ff['hp'] if ff else '-':<9}"
          f"{delay if delay is not None else '∞':<8}"
          f"{delay/25.0 if delay is not None else '∞':<8}"
          f"{dhp if dhp is not None else 0:<11.1f}"
          f"{hpmin:<8}{end:<10}")

print("\n" + "=" * 108)
print("表3  ★ 谁在打祭司：全批次威胁兵种分布（按采样数）")
print("=" * 108)
cnt = Counter(x["nRSort"] for _, x in allS)
tot = sum(cnt.values())
print(f"{'兵种':<14}{'采样数':<10}{'占比':<10}{'真实射程':<10}{'代码威胁半径':<14}{'威胁半径误判':<14}")
for s, c in cnt.most_common():
    if s < 0: continue
    rr, tr = REAL_RANGE.get(s, 5.0), threat_range(s)
    flag = ""
    if tr > rr: flag = f"高估 +{tr-rr:.1f} 格"
    elif tr < rr: flag = f"低估 -{rr-tr:.1f} 格"
    print(f"{SORT_NAME.get(s,s):<14}{c:<10}{100.0*c/tot:<9.1f}%{rr:<10.1f}{tr:<14.1f}{flag:<14}")

print("\n" + "=" * 108)
print("表4  ★ 威胁半径错配的实际后果：祭司被'看不见的威胁'击杀")
print("=" * 108)
# 分类：对每个采样，判断其 nRD 与真实射程 / 代码威胁半径 的关系
buckets = Counter()
for _, x in allS:
    s = x["nRSort"]
    if s < 0: continue
    rr, tr = REAL_RANGE.get(s, 5.0), threat_range(s)
    d = x["nRD"]
    if d <= rr:
        buckets["① 在真实射程内（确实该挨打）"] += 1
    elif d <= tr:
        buckets["② 超出真实射程、但在代码威胁半径内（高估）"] += 1
    else:
        buckets["③ 超出代码威胁半径（根本不算威胁）"] += 1
for k, v in buckets.most_common():
    print(f"  {k}: {v} 条 ({100.0*v/tot:.1f}%)")

print("\n" + "=" * 108)
print("表5  ★★ 关键：threatDist 的记录门槛 = r + 4 格")
print("      12 格兵种 → 门槛 16 格；2.5 格兵种 → 门槛 6.5 格")
print("      mustFlee 要求 threatDist <= nearestThreatR")
print("=" * 108)
for _, x in allS:
    s = x["nRSort"]
    if s < 0: continue
    pass
# 统计最近的采样里，threatDist 是否 <= nearestThreatR
ok = sum(1 for _, x in allS if x["threat"] < SENT and x["threat"] <= x["threatR"])
no = sum(1 for _, x in allS if x["threat"] < SENT and x["threat"] > x["threatR"])
sent = sum(1 for _, x in allS if x["threat"] >= SENT)
print(f"  threatDist<=threatR（若 hp<=0.6 必逃）: {ok} 条")
print(f"  threatDist> threatR（即使 hp<=0.6 也不逃）: {no} 条")
print(f"  threat 为哨兵值 1e12（完全无威胁记录）: {sent} 条")
print(f"  合计 {ok+no+sent}")
print("\n  注意：threatDist 只记录 d<=r+4 的目标；一旦祭司逃到 r+4 之外，")
print("        threatDist 立刻回落到【次近】目标或退回 1e12 ⇒ 判据自动解除。")
print("        这就是 pe3/pe4 pe6 末段 threat=27950849718.9 (哨兵) 而 hp 仍低的原因。")

print("\n" + "=" * 108)
print("表6  ★★★ 掉血速率（反推集火强度与'来不及逃'的量化）")
print("=" * 108)
for p in files:
    s = series(p)
    if not s: continue
    fb = next((x for x in s if x["hp"] < 0.995), None)
    ff = next((x for x in s if x["mode"] == 1), None)
    if not fb: continue
    if ff:
        df = ff["f"] - fb["f"]; dhp = fb["hp"] - ff["hp"]
        rate = dhp / df if df > 0 else 0
        print(f"  {p[:-4]}: {df} 帧掉 {100*dhp:.0f}pp ⇒ {100*rate:.3f} pp/帧 "
              f"= {100*rate*25:.1f} pp/s  ⇒ 满血→0.6 需 {0.40/max(rate,1e-9):.0f} 帧 "
              f"({0.40/max(rate,1e-9)/25:.1f}s)")
    else:
        print(f"  {p[:-4]}: 从未逃跑，hp {fb['hp']:.2f} → {min(x['hp'] for x in s):.2f}")
print()
