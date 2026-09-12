# -*- coding: utf-8 -*-
"""
量「同一局内两座仓库落点间距」——验证"附近同时建2个仓库"是否真的发生，
以及发生在哪个建造点（瞪羚群中心仓库 vs 第二仓库）。
口径：ait 日志 `[GAZELLE-STOCK ...] 群中心块(x,y)` -> 主建点落点；
      `XX(编号:N)建造完毕` 全部建筑 -> 用引擎事件补全（若日志够）。
"""
import re, sys, os, glob
from collections import defaultdict

LOG_DIR = r"C:\new-aoe3.0.7g"
pat_center = re.compile(r"\[GAZELLE-STOCK f=(\d+)\] 群中心块\((-?\d+),(-?\d+)\) 群内瞪羚=(\d+) 已建仓=(\d+)/(\d+) 木=(\d+)")
pat_gate   = re.compile(r"\[GATE f=(\d+)\] needStock=(\d+) gazAlive=(\d+) stock=(\d+) wood=(\d+)")

def scan(files):
    rows = []
    for fp in files:
        name = os.path.basename(fp)[:-4]
        centers = []
        gates = []
        for line in open(fp, encoding="utf-8", errors="ignore"):
            m = pat_center.search(line)
            if m:
                centers.append((int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                int(m.group(4)), int(m.group(5))))
            m = pat_gate.search(line)
            if m:
                gates.append((int(m.group(1)), int(m.group(2)), int(m.group(4)), int(m.group(5))))
        rows.append((name, centers, gates))
    return rows

def dist(x1,y1,x2,y2):
    return ((x1-x2)**2 + (y1-y2)**2) ** 0.5

files = sorted(glob.glob(os.path.join(LOG_DIR, "*.ait")))
if len(sys.argv) > 1:
    files = [f for f in files if any(p in os.path.basename(f) for p in sys.argv[1:])]

print("="*100)
print("仓库落点间距普查（块坐标，1 块 ≈ 1 格）")
print("="*100)
print(f"扫描 {len(files)} 个 .ait")
print()

grand = []
for name, centers, gates in scan(files):
    # 去重：同一落点每 60 帧打印一次，压成唯一点序列
    uniq = []
    for c in centers:
        if not uniq or (c[1], c[2]) != (uniq[-1][1], uniq[-1][2]):
            uniq.append(c)
    if not uniq:
        continue
    # 相邻落点间距
    gaps = []
    for i in range(1, len(uniq)):
        gaps.append(dist(uniq[i-1][1], uniq[i-1][2], uniq[i][1], uniq[i][2]))
    stockmax = max([g[2] for g in gates], default=0)
    print(f"{name:10s} 主建点落块序列 = " + " -> ".join(f"({c[1]},{c[2]})@f{c[0]}" for c in uniq))
    if gaps:
        print(f"{'':10s} 相邻间距 = " + ", ".join(f"{g:.1f}" for g in gaps)
              + f"   ★最近两仓 = {min(gaps):.1f} 格")
        grand.append((name, min(gaps), stockmax))
    print(f"{'':10s} GATE 记录的仓库峰值数 = {stockmax}")
    print()

if grand:
    bad = [g for g in grand if g[1] < 20]
    print("="*100)
    print(f"★ 最近两座仓库间距 < 20 格（= 第二仓库的 isFarGazelle 判据阈值）的局：{len(bad)}/{len(grand)}")
    for n, g, s in bad:
        print(f"   {n}: 间距 {g:.1f} 格, 仓库峰值 {s}")
    allg = [g[1] for g in grand]
    allg.sort()
    print(f"\n最近间距分布: min={allg[0]:.1f} 中位={allg[len(allg)//2]:.1f} max={allg[-1]:.1f}")
