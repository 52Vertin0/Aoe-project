# -*- coding: utf-8 -*-
"""
fa 批修正：农民总攻目标选取永远 -1（功能静默失效）
根因：本图敌方【没有 TC】，基地结构只有 箭塔 + 武器厂；
      原兜底循环把 BUILDING_ARROWTOWER 与 BUILDING_SIEGE 一起排除 ⇒ 目标恒 -1。
修法：目标选取改三级 + 无目标时行军到记忆方位。
"""
import io
import sys

PATH = 'UsrAI.cpp'
raw = open(PATH, 'rb').read()
assert raw.count(b'\r\n') > 6000, 'CRLF 行尾数异常'
L = raw.decode('utf-8').split('\r\n')
print('原行数 =', len(L) - 1)

# ---- 用内容锚点定位待替换段（避免行号漂移） ----
a = None
for i, l in enumerate(L):
    if l == '    if (COUNTER_FARMER_ATTACK && frame >= COUNTER_FARMER_ATTACK_FRAME) {':
        a = i
        break
assert a is not None, '找不到农民总攻段起始行'
# 段尾 = 该段末尾的 DebugText 调用后的闭合 '    }'
b = None
for j in range(a, a + 60):
    if L[j] == '    }':
        b = j
        break
assert b is not None, '找不到农民总攻段结束行'
print('段范围 = %d ~ %d (%d 行)' % (a + 1, b + 1, b - a + 1))
print('--- 段首 ---')
print('|%s|' % L[a])
print('--- 段尾 3 行 ---')
for k in range(b - 2, b + 1):
    print('|%s|' % L[k])

NEW = [
    '    if (COUNTER_FARMER_ATTACK && frame >= COUNTER_FARMER_ATTACK_FRAME) {',
    '        static std::map<int, int> farmerAtkFrame;   // 农民 SN → 上次下发帧（节流）',
    '        // ★ 目标选取三级 + 兜底行军（2026-09-19 fa 批修正）：',
    '        //   ① 敌方 TC（"基地"本体）',
    '        //   ② 最近的【软目标】敌建筑（非箭塔、非武器厂）',
    '        //   ③ 最近的【箭塔】—— 必须保留：本图敌方【没有 TC】，其基地结构只有 箭塔 + 武器厂，',
    '        //      若把箭塔也排除则目标恒为 -1、整个功能静默失效（fa 批实证：14 局触发、0 条指令下发）。',
    '        //   ④ ①②③ 全空（敌建筑全部失去视野）→ 行军到 enemyBaseScouted 的记忆方位，抵达后自然重新发现。',
    '        //   ⚠ ①②③ 一律不含武器厂：exam 胜条件唯一 = 祭司感化敌方武器厂（与 ARMY_IGNORE_SIEGE_WORKSHOP 同源）。',
    '        int farmerTgtSN = -1;',
    '        int tgtKind = 0;                        // 0=无 1=TC 2=软目标 3=箭塔 4=行军',
    '        double bestSoft = 1e18, bestTower = 1e18;',
    '        int softSN = -1, towerSN = -1;',
    '        tagBuilding* foeTC = findEnemyBuilding(BUILDING_CENTER);',
    '        if (foeTC) { farmerTgtSN = foeTC->SN; tgtKind = 1; }',
    '        for (auto &b : info.enemy_buildings) {',
    '            if (b.Type == BUILDING_SIEGE) continue;              // 永不打武器厂',
    '            double d = calDistance((b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL, targetDR, targetUR);',
    '            if (b.Type == BUILDING_ARROWTOWER) {',
    '                if (d < bestTower) { bestTower = d; towerSN = b.SN; }',
    '            } else if (d < bestSoft) { bestSoft = d; softSN = b.SN; }',
    '        }',
    '        if (farmerTgtSN < 0) {',
    '            if (softSN >= 0)      { farmerTgtSN = softSN;  tgtKind = 2; }',
    '            else if (towerSN >= 0) { farmerTgtSN = towerSN; tgtKind = 3; }',
    '        }',
    '        int nFarmer = 0;',
    '        for (auto &f : info.farmers) if (f.FarmerSort == FARMERTYPE_FARMER) nFarmer++;',
    '        int nEngaged = 0, nSent = 0;',
    '        if (farmerTgtSN >= 0) {',
    '            for (auto &f : info.farmers) {',
    '                if (f.FarmerSort != FARMERTYPE_FARMER) continue;',
    '                if (f.WorkObjectSN == farmerTgtSN) { nEngaged++; continue; }',
    '                if (farmerAtkFrame.count(f.SN) && frame - farmerAtkFrame[f.SN] < COUNTER_FARMER_ATTACK_GAP) continue;',
    '                HumanAction(f.SN, farmerTgtSN);',
    '                farmerAtkFrame[f.SN] = frame;',
    '                nSent++;',
    '            }',
    '        } else if (enemyBaseScouted) {',
    '            tgtKind = 4;',
    '            for (auto &f : info.farmers) {',
    '                if (f.FarmerSort != FARMERTYPE_FARMER) continue;',
    '                if (farmerAtkFrame.count(f.SN) && frame - farmerAtkFrame[f.SN] < COUNTER_FARMER_ATTACK_GAP) continue;',
    '                HumanMove(f.SN, enemyBaseDR, enemyBaseUR);',
    '                farmerAtkFrame[f.SN] = frame;',
    '                nSent++;',
    '            }',
    '        }',
    '        if (frame % 300 == 0)',
    '            DebugText(QString("[FARMER-ATK f=%1] 农民=%2 已投入=%3 本帧下发=%4 tgtSN=%5 kind=%6 敌建筑=%7")',
    '                      .arg(frame).arg(nFarmer).arg(nEngaged).arg(nSent).arg(farmerTgtSN).arg(tgtKind)',
    '                      .arg((int)info.enemy_buildings.size()));',
    '    }',
]

L2 = L[:a] + NEW + L[b + 1:]
print('新行数 =', len(L2) - 1, '(+%d)' % (len(NEW) - (b - a + 1)))

# ---- 同步常量块注释（铁律 44：注释与代码同轮更新） ----
IDX = None
for i, l in enumerate(L2):
    if l.startswith('//   目标 = 敌方 TC(真正的"基地") > 最近的【非箭塔、非武器厂】敌建筑 > 无目标则不动。'):
        IDX = i
        break
assert IDX is not None, '找不到常量块目标说明行'
print('常量块说明行 = %d' % (IDX + 1))
L2[IDX] = ('//   目标三级：① 敌方 TC > ② 最近的【软目标】敌建筑(非箭塔/非武器厂) > ③ 最近的【箭塔】'
           '（本图敌方无 TC，仅靠 ③ 才可达）')
L2.insert(IDX + 1,
          '//   全部不可见 → 行军到 enemyBaseScouted 记忆方位；仍无则不动。')

if '--dry' in sys.argv:
    print('=== DRY RUN：未写盘 ===')
    for k in range(max(0, a - 3), a + 4):
        print('  %4d |%s' % (k + 1, L2[k]))
    print('  ...')
    for k in range(a + len(NEW) - 3, a + len(NEW) + 3):
        print('  %4d |%s' % (k + 1, L2[k]))
    sys.exit(0)

out = '\r\n'.join(L2).encode('utf-8')
open(PATH, 'wb').write(out)
print('已写入 %d 字节' % len(out))
