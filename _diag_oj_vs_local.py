# -*- coding: utf-8 -*-
"""把 OJ 这一局（debug_16577）与本地 map2 同源局做同口径对比。只读。"""
import glob, re, os, statistics, collections, sys

def parse(fn):
    s = open(fn, encoding="utf-8", errors="replace").read()
    L = s.splitlines()
    # 结局
    if "被祭司转换,归属阵营1->0" in s:
        out = "W"
    elif "DEFEAT: Priest killed" in s:
        out = "P"
    elif "DEFEAT: Town Center destroyed" in s or "敌方 摧毁主营" in s:
        out = "T"
    else:
        out = "U"
    # 武器厂发现帧
    dis = None
    for ln in L:
        m = re.search(r"\|\s*(\d+)\s*\|\s*\w+\s*\|.*Enemy Siege Workshop found at \((\d+),(\d+)\)", ln)
        if m:
            dis = int(m.group(1)); break
    # 强制反攻帧
    ca = None
    for ln in L:
        m = re.search(r"ALL WAVES DEFEATED! Counterattack! Frame=(\d+)", ln)
        if m:
            ca = int(m.group(1)); break
    # BEAT 序列
    beats = []
    for ln in L:
        m = re.search(r"\[BEAT f=(\d+) b=(\d+)\] st=(\S+) .*?Mil=(\d+).*?pr=\(sn(-?\d+)", ln)
        if m:
            beats.append((int(m.group(1)), m.group(3), int(m.group(4)), m.group(5)))
    if not beats:
        return None
    mx = beats[-1][0]
    mil_at = {}
    for f, st, mil, psn in beats:
        mil_at.setdefault(f // 1500, mil)
    # 祭司死亡帧（首个 pr=sn-1）
    dth = None
    for f, st, mil, psn in beats:
        if psn == "-1":
            dth = f; break
    # 最大军队
    milmax = max(b[2] for b in beats)
    return dict(out=out, dis=dis, ca=ca, mx=mx, dth=dth, milmax=milmax,
                beats=beats, mil=mil_at)


def show(tag, rows, tag_name):
    print(f"  [{tag_name}] n={len(rows)}")
    outs = collections.Counter(r["out"] for r in rows)
    print(f"      结局 {dict(outs)}  胜率={outs['W']/len(rows)*100:.1f}%")
    dis = [r["dis"] for r in rows if r["dis"]]
    print(f"      发现武器厂 {len(dis)}/{len(rows)}  中位={statistics.median(dis)/1500 if dis else 0:.1f}分")
    mm = [r["milmax"] for r in rows]
    print(f"      峰值军队 Mil 中位={statistics.median(mm):.0f} 均={statistics.mean(mm):.1f}")
    # 22 分时军队（找 f>=33000 的首条）
    at22 = []
    for r in rows:
        for f, st, mil, psn in r["beats"]:
            if f >= 33000:
                at22.append(mil); break
    if at22:
        print(f"      22分军队 中位={statistics.median(at22):.0f} 均={statistics.mean(at22):.1f} min={min(at22)}")
    dth = [r["dth"] for r in rows if r["dth"]]
    if dth:
        print(f"      祭司死亡帧 中位={statistics.median(dth)/1500:.1f}分 (n={len(dth)})")


print("=" * 96)
print("本地 map2 局（按 TAG，近期臂）")
print("=" * 96)
for tag in ["club8pop2", "arb1", "fixM", "wb4", "pe4", "current"]:
    rows = []
    for fn in glob.glob(f"{tag}_map2_r0_*.ait"):
        r = parse(fn)
        if r:
            rows.append(r)
    if rows:
        show(tag, rows, tag)

print()
print("=" * 96)
print("本地 map / 其他图对照（近期臂）")
print("=" * 96)
for tag, mp in [("club8n", "map"), ("wbase", "map"), ("club6n", "map"),
                ("arb1", "map1"), ("arb1", "map3")]:
    rows = []
    for fn in glob.glob(f"{tag}_{mp}_r0_*.ait"):
        r = parse(fn)
        if r:
            rows.append(r)
    if rows:
        show(tag, rows, f"{tag}/{mp}")
