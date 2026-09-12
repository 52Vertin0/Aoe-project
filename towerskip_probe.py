# -*- coding: utf-8 -*-
"""
量化「复合弓兵为什么不打箭塔」——把命中塔与跳过塔的各自原因分类计数。

日志口径：
  [TOWER-TGT ...]  复合弓兵/远程 SN=x 攻击最近敌塔 y   → 打了
  [TOWER-SKIP ...] 复合弓兵/远程 SN=x 射程u<塔v → 不打塔 y → 没打
  [TOWER-SKIP-*] 若存在其它跳过原因

分类：
  A 打了                → TOWER-TGT
  B 射程不够            → TOWER-SKIP（canHitTower=false）
  C 视野里没塔（范围内无塔） → towerSN < 0，不产生任何日志 ⇒ 需额外诊断
"""
import re, sys, os, glob
from collections import Counter, defaultdict

LOG_DIR = r"C:\new-aoe3.0.7g"

pat_tgt  = re.compile(r"\[TOWER-TGT f=(\d+)\] (\S+) SN=(\d+) 攻击最近敌塔 (\d+)")
pat_skip = re.compile(r"\[TOWER-SKIP f=(\d+)\] (\S+) SN=(\d+) 射程([\d.]+)<塔([\d.]+) → 不打塔 SN=(\d+)")

def scan(files):
    out = {}
    for fp in files:
        name = os.path.basename(fp)[:-4]
        tgt, skip = [], []
        for line in open(fp, encoding="utf-8", errors="ignore"):
            m = pat_tgt.search(line)
            if m: tgt.append((int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(4))))
            m = pat_skip.search(line)
            if m: skip.append((int(m.group(1)), m.group(2), int(m.group(3)),
                               float(m.group(4)), float(m.group(5)), int(m.group(6))))
        out[name] = (tgt, skip)
    return out

files = sorted(glob.glob(os.path.join(LOG_DIR, "*.ait")))
if len(sys.argv) > 1:
    files = [f for f in files if any(p in os.path.basename(f) for p in sys.argv[1:])]

data = scan(files)
print("="*104)
print("复合弓兵打塔 / 跳塔 计数（按批次）")
print("="*104)
print(f"{'批次':10s} {'局':>4s} {'TOWER-TGT':>10s} {'TOWER-SKIP':>11s} {'涉及单位数':>10s} {'打过塔的单位':>12s} {'跳过的单位':>11s}")
print("-"*104)

g_tgt = g_skip = 0
skip_units_by_sort = defaultdict(set)
tgt_units_by_sort = defaultdict(set)
for name, (tgt, skip) in sorted(data.items()):
    if not tgt and not skip: continue
    tgt_u = set(x[2] for x in tgt)
    skip_u = set(x[2] for x in skip)
    for x in tgt: tgt_units_by_sort[x[1]].add(x[2])
    for x in skip: skip_units_by_sort[x[1]].add(x[2])
    print(f"{name:10s} {1:>4d} {len(tgt):>10d} {len(skip):>11d} {len(tgt_u|skip_u):>10d} {len(tgt_u):>12d} {len(skip_u):>11d}")
    g_tgt += len(tgt); g_skip += len(skip)

print("-"*104)
print(f"{'合计':10s} {'':>4s} {g_tgt:>10d} {g_skip:>11d}")
print()

print("="*104)
print("★ 按 who 标签拆分（谁是复合弓兵、谁只是远程）")
print("="*104)
for who in sorted(set(list(tgt_units_by_sort.keys()) + list(skip_units_by_sort.keys()))):
    t = len(tgt_units_by_sort.get(who, ()))
    s = len(skip_units_by_sort.get(who, ()))
    print(f"  {who:20s} 打过塔的单位 {t:>4d}  跳过的单位 {s:>4d}")

print()
print("="*104)
print("★ 关键问题：被跳过的塔，射程判据是什么？")
print("="*104)
allskip = []
for name, (tgt, skip) in data.items():
    allskip += skip
c = Counter((x[1], x[3], x[4]) for x in allskip)
for (who, r1, r2), n in c.most_common(10):
    print(f"  [{who}] 自身射程 {r1} 格 < 塔射程 {r2} 格   × {n}")
