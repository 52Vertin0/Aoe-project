# -*- coding: utf-8 -*-
"""量化「敌方士兵全灭 + 箭塔全拆」这一全局状态：
死亡事件的累计数(玩家击杀=敌方减员) vs 敌方单位产出事件(敌方可补充)。
敌方可补充的证据：敌方"产生了新的XX" 行（若存在）。
核心问题：本图敌方是【持续产兵】还是【固定波次】？若是持续产兵，"敌全灭"永不成立 -> 死锁。
"""
import io, os, re

KILL_P = re.compile(r'(?<!敌方 )玩家 击杀')
KILL_E = re.compile(r'敌方 击杀')
# 敌方生产事件（类似 "产生了新的复合弓兵" 但属于敌方 -> 观察格式）
SPAWN_ANY = re.compile(r'产生了新的')
# 敌方攻击我方建筑
ENEMY_ATK = re.compile(r'敌方.*(攻击|摧毁)')

print('%-7s %8s %7s %7s %8s %9s %9s' % ('局', '末帧', '玩家击杀', '敌方击杀', '敌方生产', '敌攻我建筑', '结局'))
print('-' * 66)

tot_enemy_spawn = 0
for batch in ('tc', 'sz', 'szb', 'th'):
    for i in range(1, 9):
        p = '%s%d.ait' % (batch, i)
        if not os.path.exists(p):
            continue
        lines = io.open(p, encoding='utf-8', errors='replace').read().splitlines()
        maxf = 0; kp = 0; ke = 0; spawn = 0; eatk = 0
        for ln in lines:
            q = ln.split('|')
            if len(q) < 5:
                continue
            try:
                f = int(q[1].strip())
            except Exception:
                continue
            maxf = max(maxf, f)
            msg = q[4]
            if KILL_P.search(msg): kp += 1
            if KILL_E.search(msg): ke += 1
            if SPAWN_ANY.search(msg): spawn += 1
            if ENEMY_ATK.search(msg): eatk += 1
        tot_enemy_spawn += spawn
        vic = any('VICTORY' in l for l in lines)
        de = any('DEFEAT:' in l for l in lines)
        out = 'VICTORY' if vic else ('DEFEAT' if de else 'timeout')
        print('%-7s %8d %7d %7d %8d %9d %9s' % (batch + str(i), maxf, kp, ke, spawn, eatk, out))

print()
print('总"产生了新的"事件 =', tot_enemy_spawn)
