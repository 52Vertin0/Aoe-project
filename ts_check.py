# -*- coding: utf-8 -*-
"""towerstrict 验证批核对：对照 th（局部清场,旧）与 ts（敌塔全拆,新）。
主证据 = 机制量（感化起手次数），不是胜场（铁律 25/36）。"""
import os, re, glob

BASE = r"C:\new-aoe3.0.7g"
WIN = "VICTORY! Siege Workshop converted"
START = "设置转换目标为 攻城武器厂"

def analyze(tag):
    files = sorted(glob.glob(os.path.join(BASE, tag + "[0-9]*.ait")))
    if not files:
        return None
    d = dict(tag=tag, n=len(files), win=0, lose=0, to=0, start=0, wait=0, waitSamples=[])
    for fp in files:
        raw = open(fp, "rb").read().decode("utf-8", "replace")
        if WIN in raw:
            d["win"] += 1
        elif re.search(r"DEFEAT: (Priest killed|Town Center destroyed)", raw):
            d["lose"] += 1
        else:
            d["to"] += 1
        d["start"] += raw.count(START)
        d["wait"] += raw.count("[SIEGE-WAIT")
        for m in re.finditer(r"\[SIEGE-WAIT f=(\d+)\] hp=([\d.]+) towers=(\d+) seen=(\d+) dS=([\d.]+)", raw):
            d["waitSamples"].append((os.path.basename(fp),) + m.groups())
    return d

rows = [r for r in (analyze(t) for t in ["th", "ts"]) if r]
print("=" * 96)
print("towerstrict 验证批 vs th 基线")
print("=" * 96)
print(f"{'批次':<6}{'胜':<4}{'负':<4}{'无结局':<7}{'感化起手':<10}{'SIEGE-WAIT':<12}{'说明'}")
print("-" * 96)
notes = {"th": "局部清场（旧）", "ts": "敌塔全拆（新，唯一闸）"}
for r in rows:
    print(f"{r['tag']:<6}{r['win']:<4}{r['lose']:<4}{r['to']:<7}{r['start']:<10}{r['wait']:<12}{notes[r['tag']]}")
print("=" * 96)
print()
for r in rows:
    if r["waitSamples"]:
        print(f"★ {r['tag']} 的 [SIEGE-WAIT] 现场（file, frame, hp, towers, seen, dS）:")
        for s in r["waitSamples"][:12]:
            print("   ", s)
        print()
