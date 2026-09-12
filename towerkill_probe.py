# -*- coding: utf-8 -*-
"""加闸前量化（铁律 24/35）：先看"我方拆敌塔"到底发生过没有。
关键口径：`玩家 摧毁箭塔` = 我方拆掉敌塔；`敌方 摧毁箭塔` = 我方塔被拆。
若前者在全部历史局里恒为 0，则"塔全拆"结构性不可达 ⇒ 这道闸 = 永久关闭唯一胜路。
"""
import os, re, glob

BASE = r"C:\new-aoe3.0.7g"
TAGS = ["sg", "sz", "th", "mc", "md", "dm", "sb", "sba", "ps", "hc3", "hc4", "rb_smoke"]

print("=" * 100)
print("「我方拆敌塔」vs「敌方拆我塔」逐批统计")
print("=" * 100)
print(f"{'批次':<10}{'局数':<6}{'我方拆敌塔':<12}{'敌方拆我塔':<12}{'我方拆敌其他建筑':<18}")
print("-" * 100)

grand_ours = 0
for tag in TAGS:
    files = sorted(glob.glob(os.path.join(BASE, tag + "*.ait")))
    if not files:
        continue
    ours = theirs = other = 0
    for fp in files:
        raw = open(fp, "rb").read().decode("utf-8", "replace")
        for ln in raw.splitlines():
            # 只统计引擎的"摧毁"事件行（HumanAction 之外的引擎动作）
            if "摧毁" not in ln:
                continue
            if "箭塔" in ln:
                if "玩家 摧毁箭塔" in ln or ("玩家" in ln and "摧毁" in ln and "箭塔" in ln):
                    ours += 1
                elif "敌方" in ln:
                    theirs += 1
            else:
                # 我方拆敌方的其他建筑（武器厂/房屋等）
                if "玩家 摧毁" in ln and "敌方" not in ln:
                    other += 1
    grand_ours += ours
    print(f"{tag:<10}{len(files):<6}{ours:<12}{theirs:<12}{other:<18}")

print("=" * 100)
print(f"★ 全部历史局中「我方拆敌塔」总计 = {grand_ours}")
if grand_ours == 0:
    print("★ 结论：结构性为 0 ⇒ 「敌塔全拆」在当前军队行为下【不可达】。")
    print("  这道闸 = 永久关闭感化武器厂 = 永久关闭 exam 唯一胜路。")
    print("  ⇒ 必须先让军队有能力拆塔，否则闸必然死锁（与 2026-09-16 prieststrict 轮结论一致）。")
else:
    print("★ 结论：确有拆塔行为发生 ⇒ 该闸有可达性，需要具体看是哪几局、什么兵种完成的。")
