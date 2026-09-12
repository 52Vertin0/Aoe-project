# -*- coding: utf-8 -*-
"""武器厂「发现时点」分布分析 v2：用日志时间前缀换算帧号。只读。"""
import glob, re, os, statistics, collections, sys

FOUND = re.compile(r"\|\s*(\d+)\s*\|\s*\w+\s*\|.*Enemy Siege Workshop found at \((\d+),(\d+)\)")
TIME = re.compile(r"^(\d\d):(\d\d):(\d\d)\b")
FR = re.compile(r"^\d\d:\d\d:\d\d\s+\|\s*(\d+)\s*\|")


def t2f(h, m, s):
    return int((int(h) * 60 + int(m) + int(s) / 100.0) * 25)   # 25 fps


def outcome(s):
    if "被祭司转换,归属阵营1->0" in s:
        return "W"
    if "DEFEAT: Priest killed" in s:
        return "P"
    if "DEFEAT: Town Center destroyed" in s or "敌方 摧毁主营" in s:
        return "T"
    return "U"


def tagmap(fn):
    b = os.path.basename(fn)[:-4]
    m = re.match(r"^(.+?)_(map[0-3]?)_r(\d+)_(\d+)$", b)
    return (m.group(1), m.group(2)) if m else (None, None)


TAGS = set(sys.argv[1:]) if len(sys.argv) > 1 else None
recs = []
for fn in glob.glob("*_map*_r*_*.ait"):
    tag, mp = tagmap(fn)
    if tag is None or (TAGS and tag not in TAGS):
        continue
    s = open(fn, encoding="utf-8", errors="replace").read()
    tf = None
    for ln in s.splitlines():
        m = FOUND.search(ln)
        if m:
            tf = int(m.group(1))
            break
    r = {"tag": tag, "mp": mp, "fn": os.path.basename(fn), "dis": tf, "out": outcome(s)}
    recs.append(r)

print("=" * 112)
print(f"样本：{len(recs)} 局；TAG 过滤={'全部' if not TAGS else sorted(TAGS)}")
print("=" * 112)
print(f"{'图':<8} {'局数':>5} {'发现局':>6} {'发现率':>7} {'发现中位(分)':>12} {'发现均值(分)':>12} {'最早':>7} {'最晚':>7} {'胜率':>7}")
for mp in sorted(set(r["mp"] for r in recs)):
    rows = [r for r in recs if r["mp"] == mp]
    d = [r["dis"] for r in rows if r["dis"] is not None]
    w = sum(1 for r in rows if r["out"] == "W")
    print(f"{mp:<8} {len(rows):>5} {len(d):>6} {len(d)/len(rows)*100:>6.1f}% "
          f"{(statistics.median(d)/1500 if d else 0):>12.1f} {(statistics.mean(d)/1500 if d else 0):>12.1f} "
          f"{(min(d)/1500 if d else 0):>7.1f} {(max(d)/1500 if d else 0):>7.1f} {w/len(rows)*100:>6.1f}%")

print()
print("=" * 112)
print("★ 分层：发现时点 → 结局（只看已发现的局）")
print("=" * 112)
bins = [(0, 9000), (9000, 13500), (13500, 21000), (21000, 27000), (27000, 33000), (33000, 10**9)]
labels = ["<6分", "6~9分", "9~14分", "14~18分", "18~22分", "≥22分"]
for mp in sorted(set(r["mp"] for r in recs)):
    rows = [r for r in recs if r["mp"] == mp and r["dis"] is not None]
    if not rows:
        continue
    print(f"  [{mp}] n={len(rows)}")
    for (lo, hi), lb in zip(bins, labels):
        g = [r for r in rows if lo <= r["dis"] < hi]
        if not g:
            continue
        w = sum(1 for r in g if r["out"] == "W")
        print(f"      {lb:<8} n={len(g):<4} 胜={w:<4} ({w/len(g)*100:5.1f}%)  结局={dict(collections.Counter(r['out'] for r in g))}")

print()
print("=" * 112)
print("★ 主判据：发现时点是否存在的两分（全场）")
print("=" * 112)
for mp in sorted(set(r["mp"] for r in recs)) + ["ALL"]:
    rows = recs if mp == "ALL" else [r for r in recs if r["mp"] == mp]
    d = [r for r in rows if r["dis"] is not None]
    n = [r for r in rows if r["dis"] is None]
    wd = sum(1 for r in d if r["out"] == "W")
    wn = sum(1 for r in n if r["out"] == "W")
    print(f"  {mp:<8} 已发现 {wd}/{len(d)}={wd/len(d)*100 if d else 0:5.1f}%   未发现 {wn}/{len(n)}={wn/len(n)*100 if n else 0:5.1f}%"
          f"   未发现占比 {len(n)/len(rows)*100:5.1f}%")

print()
print("=" * 112)
print("★ 分 TAG × 图：发现率（仅列已跑满四图的 TAG）")
print("=" * 112)
byt = collections.defaultdict(lambda: collections.defaultdict(list))
for r in recs:
    byt[r["tag"]][r["mp"]].append(r)
rows_out = []
for tag, d in byt.items():
    if len(d) < 4:
        continue
    fr = {mp: (sum(1 for r in v if r["dis"] is not None) / len(v)) for mp, v in d.items()}
    rows_out.append((tag, {mp: len(v) for mp, v in d.items()}, fr))
for tag, n, fr in sorted(rows_out, key=lambda x: x[2].get("map", 0)):
    print(f"  {tag:<14} " + "  ".join(f"{mp}:{fr[mp]*100:5.1f}%(n={n[mp]})" for mp in sorted(fr)))
