# -*- coding: utf-8 -*-
"""关键问题：敌方一共有几座塔？我军拆掉几座？"全拆"差多远？
口径：敌方塔 = 曾出现过的 111xx 段箭塔（被摧毁行的 playerID=1，或被我方攻击过的箭塔编号）。
      我方塔 = 被摧毁行 playerID=0，或"建造完毕"事件里的箭塔编号。
"""
import os, re, glob, collections

BASE = r"C:\new-aoe3.0.7g"

DEAD = re.compile(r"\|\s*(-?\d+)\s*\|\s+(\S+)\(编号:(\d+)\)被摧毁")
ATK  = re.compile(r"\|\s*(-?\d+)\s*\|\s+(\S+)\(编号:(\d+)\)开始向(\S+)\(编号：(\d+)\)攻击")
OWN  = re.compile(r"\|\s*(-?\d+)\s*\|\s+(\S+)\(编号:(\d+)\)建造完毕")

def dump(tag):
    files = sorted(glob.glob(os.path.join(BASE, tag + "[0-9]*.ait")))
    print("=" * 96)
    print(f"批次 {tag}")
    print("=" * 96)
    for fp in files[:4]:
        raw = open(fp, "rb").read().decode("utf-8", "replace")
        my_towers = set()
        for m in OWN.finditer(raw):
            if m.group(2) == "箭塔":
                my_towers.add(int(m.group(3)))
        enemy_towers = set()
        for m in DEAD.finditer(raw):
            if m.group(2) == "箭塔" and int(m.group(1)) == 1:
                enemy_towers.add(int(m.group(3)))
        # 被我方攻击过的箭塔（也是敌塔）
        attacked = set()
        for m in ATK.finditer(raw):
            if m.group(4) == "箭塔" and int(m.group(1)) == 0:   # 我方(flag=0)攻击的箭塔
                attacked.add(int(m.group(5)))
        # 被敌方攻击的箭塔（= 我方的塔）
        attacked_by_enemy = set()
        for m in ATK.finditer(raw):
            if m.group(4) == "箭塔" and int(m.group(1)) == 1:
                attacked_by_enemy.add(int(m.group(5)))
        all_enemy = enemy_towers | attacked
        print(f"  {os.path.basename(fp)}")
        print(f"    我方塔(建造)={sorted(my_towers)}")
        print(f"    敌方塔(被拆+被攻击)={sorted(all_enemy)}  共{len(all_enemy)}座")
        print(f"    其中被我方拆掉的={sorted(enemy_towers)} 共{len(enemy_towers)}座")
        remain = all_enemy - enemy_towers
        print(f"    ⇒ 未被拆的={sorted(remain)} 共{len(remain)}座")

for t in ["th", "ts"]:
    dump(t)
