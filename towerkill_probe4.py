# -*- coding: utf-8 -*-
"""★ 正确版拆塔统计（2026-09-16 修正）
前两次都错了：
  ① 错法一：grep 文本 `玩家 摧毁箭塔` —— 该字符串【从未出现】，等于什么都没量。
  ② 错法二：按"建筑编号区间"猜归属 —— 区间重叠、且正则漏匹配 `开始向...(编号：N)攻击`（注意是【全角冒号】）。
正确口径（已由 Core.cpp:262 源码 + th7 实证确认）：
  `XX(编号:N)被摧毁` 行的【第4列 = playerID】= 该建筑的所有者（0=我方 / 1=敌方）。
  引擎按 player 逐个遍历自己的建筑并打日志（Core.cpp:105 `for playerIndx...`），
  所以同一行既是"这个建筑死了"，也直接告诉你"它是谁的"。
"""
import os, re, glob, collections

BASE = r"C:\new-aoe3.0.7g"
TAGS = ["sg", "sz", "th", "mc", "md", "dm", "sb", "sba", "ps", "ts", "hc3", "hc4"]

DEAD = re.compile(r"(\d+):(\d+):(\d+)\s*\|\s*(\d+)\s*\|\s*\w+\s*\|\s*(-?\d+)\s*\|\s+(\S+)\(编号:(\d+)\)被摧毁")

total_enemy_tower_dead = 0
total_my_tower_dead = 0

print("=" * 92)
print("敌我箭塔阵亡统计（第4列 playerID = 所有者；0=我方 1=敌方）")
print("=" * 92)
print(f"{'批次':<7}{'局':<4}{'敌塔被拆':<10}{'我塔被拆':<10}{'有拆塔的局数':<12}{'说明'}")
print("-" * 92)

for tag in TAGS:
    files = sorted(glob.glob(os.path.join(BASE, tag + "[0-9]*.ait")))
    if not files:
        continue
    et = mt = 0
    rounds_with_kill = 0
    for fp in files:
        raw = open(fp, "rb").read().decode("utf-8", "replace")
        e = m = 0
        for mm in DEAD.finditer(raw):
            kind, pid = mm.group(6), int(mm.group(5))
            if kind != "箭塔":
                continue
            if pid == 1:
                e += 1          # 敌方拥有的塔死了 = 我方拆的（本图我方是进攻方）
            elif pid == 0:
                m += 1          # 我方的塔死了
        et += e; mt += m
        if e > 0:
            rounds_with_kill += 1
    total_enemy_tower_dead += et
    total_my_tower_dead += mt
    print(f"{tag:<7}{len(files):<4}{et:<10}{mt:<10}{rounds_with_kill}/{len(files):<10}")

print("=" * 92)
print(f"总计：敌方箭塔被拆 = {total_enemy_tower_dead} 座   我方箭塔被拆 = {total_my_tower_dead} 座")
print()
if total_enemy_tower_dead > 0:
    print("★ 结论：我军【确实具备】拆敌塔能力 —— 前两次统计（0 次）是我的口径错误，不是引擎事实。")
    print("  ⇒ 「敌塔全拆」并非结构性不可达；真正的问题是【拆得够不够快/够不够全】。")
