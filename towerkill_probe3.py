# -*- coding: utf-8 -*-
"""最终版：判定"敌塔被摧毁"到底是我方干的还是敌方自己干的。
口径：找 `XX(编号:N)开始向箭塔(编号:M)攻击` 事件，看攻击者 XX 的 flag（第4列）。
  flag=0 → 我方单位（我方部队编号是 91xxx）
  flag=1 → 敌方单位（敌方部队编号也是 91xxx，但 flag=1）
关键：行为者和目标的归属都要判。本图我方建筑编号 113xx~114xx，敌方 111xx。
"""
import os, re, glob

BASE = r"C:\new-aoe3.0.7g"
TAGS = ["th", "sg", "ts"]

pat_attack = re.compile(r"(\d+):(\d+):(\d+)\s*\|\s*(\d+)\s*\|\s*(\w+)\s*\|\s*(-?\d+)\s*\|\s+(\S+)\(编号:(\d+)\)开始向(\S+)\(编号：(\d+)\)攻击")

for tag in TAGS:
    files = sorted(glob.glob(os.path.join(BASE, tag + "[0-9]*.ait")))
    print("=" * 92)
    print(f"批次 {tag}")
    print("=" * 92)
    for fp in files:
        raw = open(fp, "rb").read().decode("utf-8", "replace")
        # 谁在攻击"箭塔"
        by_us = by_enemy = 0
        attackers_us, attackers_enemy = set(), set()
        for m in pat_attack.finditer(raw):
            frame, flag, atk_kind, atk_num, tgt_kind, tgt_num = \
                int(m.group(4)), int(m.group(6)), m.group(7), m.group(8), m.group(9), int(m.group(10))
            if tgt_kind == "箭塔":
                if flag == 0:
                    by_us += 1; attackers_us.add(atk_kind)
                elif flag == 1:
                    by_enemy += 1; attackers_enemy.add(atk_kind)
        # 我方建造的箭塔编号
        my_towers = set(int(x) for x in re.findall(r"箭塔\(编号:(\d+)\)建造完毕", raw))
        # 被摧毁的箭塔编号
        dead = set(int(x) for x in re.findall(r"箭塔\(编号:(\d+)\)被摧毁", raw))
        print(f"  {os.path.basename(fp):<12} 攻击箭塔: 我方={by_us:<4}{sorted(attackers_us)}  "
              f"敌方={by_enemy:<4}{sorted(attackers_enemy)}")
        print(f"      我方塔编号={sorted(my_towers)}  被摧毁的塔={sorted(dead)}  "
              f"⇒ 敌方塔死在: {sorted(dead - my_towers)}")
