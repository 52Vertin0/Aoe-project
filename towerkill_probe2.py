# -*- coding: utf-8 -*-
"""修正版拆塔统计：按【建筑编号区间】判定归属，而非按"摧毁"事件文本。
口径依据：
  - 日志 '玩家/敌方 摧毁X' = Score::addScore 的计分广播（只是计分，不含编号）。
  - 真正的归属事件 = `XX(编号:N)被摧毁`，第4列 = playerID（0=我方，1=敌方）。
  - 但我方/敌方建筑编号区间不同：我方建的全部落在 11.3k~11.4k（本图固定），敌方在 11.1k 段。
  ⇒ 最可靠判据 = 该编号是否出现过 `建造完毕`（=我方建的）。敌方建筑我方看不到建造事件。
"""
import os, re, glob

BASE = r"C:\new-aoe3.0.7g"
TAGS = ["sg", "sz", "th", "mc", "md", "dm", "sb", "sba", "ps", "ts"]

def analyze(tag):
    files = sorted(glob.glob(os.path.join(BASE, tag + "[0-9]*.ait")))
    if not files:
        return None
    ours_towers = set()        # 我方建造完毕的箭塔编号
    destroyed_towers = []      # (file, frame, num, playerID)
    destroyed_by_us = 0        # 被我方摧毁的敌方建筑（编号不在 ours 里）
    for fp in files:
        raw = open(fp, "rb").read().decode("utf-8", "replace")
        my_bld = set()
        for m in re.finditer(r"(\d+):(\d+):(\d+)\s*\|\s*(\d+)\s*\|\s*\w+\s*\|\s*(\d+)\s*\|\s+(\S+)\(编号:(\d+)\)建造完毕", raw):
            my_bld.add(int(m.group(7)))
        for m in re.finditer(r"(\d+):(\d+):(\d+)\s*\|\s*(\d+)\s*\|\s*\w+\s*\|\s*(-?\d+)\s*\|\s+(\S+)\(编号:(\d+)\)被摧毁", raw):
            kind, num, pid, frame = m.group(6), int(m.group(7)), int(m.group(5)), int(m.group(4))
            destroyed_towers.append((os.path.basename(fp), frame, kind, num, pid, num in my_bld))
        ours_towers |= {n for n in my_bld}
    return files, ours_towers, destroyed_towers

print("=" * 104)
print("修正版：按【建筑归属】统计被摧毁的箭塔")
print("=" * 104)
for tag in TAGS:
    r = analyze(tag)
    if not r:
        continue
    files, ours, dest = r
    enemy_towers_destroyed = [d for d in dest if d[2] == "箭塔" and not d[5]]
    my_towers_destroyed    = [d for d in dest if d[2] == "箭塔" and d[5]]
    print(f"{tag:<6} 局={len(files):<3} 我方建的建筑编号数={len(ours):<4} "
          f"| 敌方箭塔被摧毁={len(enemy_towers_destroyed):<4} 我方箭塔被摧毁={len(my_towers_destroyed)}")
    for d in enemy_towers_destroyed[:6]:
        print(f"        敌方塔 {d[3]} @f={d[1]} (playerID={d[4]})")
print("=" * 104)
