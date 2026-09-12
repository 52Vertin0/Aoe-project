# -*- coding: utf-8 -*-
"""map2 图：军队衰减曲线（按结局分层）+ 祭司阵亡时与武器厂的距离。只读。"""
import glob, re, statistics, collections, math

BL = 35.777


def parse(fn):
    s = open(fn, encoding="utf-8", errors="replace").read()
    if "被祭司转换,归属阵营1->0" in s:
        out = "W"
    elif "DEFEAT: Priest killed" in s:
        out = "P"
    elif "DEFEAT: Town Center destroyed" in s or "敌方 摧毁主营" in s:
        out = "T"
    else:
        out = "U"
    dis = None
    sw = None
    for ln in s.splitlines():
        m = re.search(r"\|\s*(\d+)\s*\|\s*\w+\s*\|.*Enemy Siege Workshop found at \((\d+),(\d+)\)", ln)
        if m and dis is None:
            dis = int(m.group(1)); sw = (int(m.group(2)), int(m.group(3)))
    beats = []
    for ln in s.splitlines():
        m = re.search(r"\[BEAT f=(\d+) b=\d+\] st=(\S+) .*?Mil=(\d+).*?pr=\(sn(-?\d+) .*?pr@=\(([-\d.]+),([-\d.]+)\)", ln)
        if m:
            beats.append(dict(f=int(m.group(1)), st=m.group(2), mil=int(m.group(3)),
                              psn=m.group(4), px=float(m.group(5)), py=float(m.group(6))))
    if not beats:
        return None
    # 分分钟军队
    mil = {}
    for b in beats:
        mil.setdefault(b["f"] // 1500, b["mil"])
    # 祭司死亡帧 + 位置
    dth = px = py = None
    for i, b in enumerate(beats):
        if b["psn"] == "-1":
            dth = b["f"]
            if i > 0:
                px, py = beats[i - 1]["px"], beats[i - 1]["py"]
            break
    d2sw = None
    if dth and sw and px is not None and px > 0:
        d2sw = math.hypot(px - (sw[0] + 1), py - (sw[1] + 1))
    return dict(out=out, dis=dis, sw=sw, dth=dth, d2sw=d2sw, mil=mil, beats=beats)


files = []
for tag in ["club8pop2", "current", "fixM", "wb4", "pe4"]:
    files += glob.glob(f"{tag}_map2_r0_*.ait")
rows = [r for r in (parse(f) for f in files) if r]

print("=" * 100)
print(f"map2 图（n={len(rows)}，含 club8pop2/current/fixM/wb4/pe4）—— 军队 Mil 逐分钟（按结局均值）")
print("=" * 100)
mins = list(range(20, 31))
print(f"{'结局':<6} {'n':>4}  " + " ".join(f"{m:>5}分" for m in mins))
for out in ["W", "P", "U"]:
    g = [r for r in rows if r["out"] == out]
    if not g:
        continue
    line = []
    for m in mins:
        v = [r["mil"][m] for r in g if m in r["mil"]]
        line.append(f"{statistics.mean(v):>6.1f}" if v else "     -")
    print(f"{out:<6} {len(g):>4}  " + " ".join(line))

print()
print("=" * 100)
print("祭司阵亡时与武器厂的距离（格，只看已发现武器厂且祭司阵亡的局）")
print("=" * 100)
dd = [r["d2sw"] for r in rows if r["d2sw"] is not None]
if dd:
    print(f"  n={len(dd)}  中位={statistics.median(dd):.1f} 均={statistics.mean(dd):.1f} "
          f"min={min(dd):.1f} max={max(dd):.1f}")
    print(f"  感化射程 PRIEST_CONVERT_SIEGE_RANGE = 12.0 格 ⇒ 死亡时还在射程外的比例 = "
          f"{sum(1 for x in dd if x > 12)}/{len(dd)} = {sum(1 for x in dd if x>12)/len(dd)*100:.0f}%")
for r in sorted([r for r in rows if r["d2sw"] is not None], key=lambda r: r["d2sw"]):
    print(f"    {r['out']} 死@{r['dth']/1500:5.2f}分  距武器厂 {r['d2sw']:5.1f}格  发现@{r['dis']/1500:5.2f}分")

print()
print("=" * 100)
print("★ OJ 局（debug_16577，手工提取）")
print("=" * 100)
print("  图：map2（local 对齐值 Enemy base scouted at (751.319,572.433) = map2 专属）")
print("  22分军队=27（满编）｜武器厂 @(24,6) 发现于 24:06:32｜祭司起手前出 24:06:96 d=44.6格")
print("  祭司阵亡 25:17:84（f=37945）｜阵亡前最后位置 (38.5,25.5) ⇒ 距武器厂中心 "
      f"{math.hypot(38.5-25.0, 25.5-7.0):.1f} 格")
print("  24:00 时 near=0/24 gathered=0 expire=1（集结垮掉）｜结局 P（祭司被击杀）")
