# -*- coding: utf-8 -*-
"""A2a：把 manageBuildings 里 8 类"重复建造块"替换为 A1 的 lambda 调用。
每处替换断言命中次数，任何不匹配立即报错退出（不写文件）。
"""
P = 'UsrAI.cpp'
s = open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')
before = s

REPL = []   # (name, old, new, count)

# ---------- 房屋块（4 处：preW1 8格 / rushMilitary 12格 / postW1 12格 / postW2 8格）----------
H8 = """        bool popHeadroomLow = (info.Human_MaxNum - humanPop <= POP_HEADROOM_BUILD);
        if (!builtThisFrame && houseCount < MAX_HOUSES && !houseBuildingInProgress && popHeadroomLow &&
            info.Wood >= BUILD_HOUSE_WOOD) {
            builtThisFrame = tryBuild(BUILDING_HOME, 2);
        }
"""
H12 = """            bool popHeadroomLow = (info.Human_MaxNum - humanPop <= POP_HEADROOM_BUILD);
            if (!builtThisFrame && houseCount < MAX_HOUSES && !houseBuildingInProgress && popHeadroomLow &&
                info.Wood >= BUILD_HOUSE_WOOD) {
                builtThisFrame = tryBuild(BUILDING_HOME, 2);
            }
"""
REPL.append(('房屋(8格缩进) x2', H8, '        tryBuildHouse();\n', 2))
REPL.append(('房屋(12格缩进) x2', H12, '            tryBuildHouse();\n', 2))

# ---------- 兵营块（3 处）----------
C8 = """        if (!builtThisFrame && countBuildingsExisting(BUILDING_ARMYCAMP) == 0 &&
            houseCount >= 1 && info.Wood >= BUILD_ARMYCAMP_WOOD) {
            builtThisFrame = tryBuild(BUILDING_ARMYCAMP, 3);
        }
"""
C12 = """            if (!builtThisFrame && countBuildingsExisting(BUILDING_ARMYCAMP) == 0 &&
                info.Wood >= BUILD_ARMYCAMP_WOOD) {
                builtThisFrame = tryBuild(BUILDING_ARMYCAMP, 3);
            }
"""
C8P = """        if (!builtThisFrame && upgradeStarted && countBuildingsExisting(BUILDING_ARMYCAMP) == 0 &&
            info.Wood >= BUILD_ARMYCAMP_WOOD) {
            builtThisFrame = tryBuild(BUILDING_ARMYCAMP, 3);
        }
"""
REPL.append(('兵营(preW1,house闸)', C8, '        tryBuildArmyCamp(true);\n', 1))
REPL.append(('兵营(rush,12)', C12, '            tryBuildArmyCamp(false);\n', 1))
REPL.append(('兵营(postW2,upgrade闸)', C8P, '        if (!builtThisFrame && upgradeStarted) tryBuildArmyCamp(false);\n', 1))

# ---------- 靶场块（3 处）----------
R8 = """        if (!builtThisFrame && countBuildingsExisting(BUILDING_RANGE) == 0 &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_RANGE_WOOD) {
            builtThisFrame = tryBuild(BUILDING_RANGE, 3);
        }
"""
R12 = """            if (!builtThisFrame && countBuildingsExisting(BUILDING_RANGE) == 0 &&
                countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_RANGE_WOOD) {
                builtThisFrame = tryBuild(BUILDING_RANGE, 3);
            }
"""
R12W = """            if (!builtThisFrame && countBuildingsExisting(BUILDING_RANGE) == 0 &&
                countBuildings(BUILDING_ARMYCAMP) >= 1 &&
                info.Wood >= BUILD_RANGE_WOOD) {
                builtThisFrame = tryBuild(BUILDING_RANGE, 3);
            }
"""
R8L = """        if (!builtThisFrame && !(needSecondStock && frame < WAVE3_TIME) &&
            countBuildingsExisting(BUILDING_RANGE) == 0 &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_RANGE_WOOD) {
            builtThisFrame = tryBuild(BUILDING_RANGE, 3);
            if (builtThisFrame) DebugText(QString("[RANGE f=%1] 下令建造首座靶场 wood=%2").arg(frame).arg((int)info.Wood));
        }
"""
REPL.append(('靶场(preW1,8)', R8, '        tryBuildRange(nullptr);\n', 1))
REPL.append(('靶场(rush,12)', R12, '            tryBuildRange(nullptr);\n', 1))
REPL.append(('靶场(postW1,12换行)', R12W, '            tryBuildRange(nullptr);\n', 1))
REPL.append(('靶场(postW2,让位+日志)', R8L,
             '        if (!builtThisFrame && !(needSecondStock && frame < WAVE3_TIME))\n'
             '            tryBuildRange("下令建造首座靶场");\n', 1))

# ---------- 箭塔块（2 处）----------
T12 = """            if (!builtThisFrame && towerCount < MAX_TOWERS && frame < WAVE3_TIME &&
                info.Stone >= 150) {
                builtThisFrame = tryBuild(BUILDING_ARROWTOWER, 2);
                if (builtThisFrame) towerCount++;
            }
"""
T8 = """        if (!builtThisFrame && towerCount < MAX_TOWERS && frame < WAVE3_TIME &&
            info.Stone >= 150) {
            builtThisFrame = tryBuild(BUILDING_ARROWTOWER, 2);
            if (builtThisFrame) towerCount++;
        }
"""
REPL.append(('箭塔(postW1,12)', T12, '            tryBuildTower();\n', 1))
REPL.append(('箭塔(postW2,8)', T8, '        tryBuildTower();\n', 1))

# ---------- 马厩块（2 处）----------
S12 = """            if (!builtThisFrame && countBuildingsExisting(BUILDING_STABLE) == 0 &&
                info.civilizationStage >= CIVILIZATION_TOOLAGE &&
                countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_STABLE_WOOD && !DISABLE_STABLE_BUILD) {
                builtThisFrame = tryBuild(BUILDING_STABLE, 3);
                if (builtThisFrame)
                    DebugText(QString("[STABLE f=%1] postW1 建马厩(学院前置) wood=%2").arg(frame).arg((int)info.Wood));
            }
"""
S8 = """        if (!builtThisFrame && countBuildingsExisting(BUILDING_STABLE) == 0 &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_STABLE_WOOD && !DISABLE_STABLE_BUILD) {
            builtThisFrame = tryBuild(BUILDING_STABLE, 3);
            if (builtThisFrame)
                DebugText(QString("[STABLE f=%1] postW2 建马厩(学院前置) wood=%2").arg(frame).arg((int)info.Wood));
        }
"""
REPL.append(('马厩(postW1,时代闸)', S12, '            tryBuildStable(true, "postW1 建马厩(学院前置)");\n', 1))
REPL.append(('马厩(postW2)', S8, '        tryBuildStable(false, "postW2 建马厩(学院前置)");\n', 1))

# ---------- 谷仓块（3 处）----------
G12E = """            if (!builtThisFrame && canAffordEcon &&
                countBuildingsExisting(BUILDING_MARKET) == 0 && countBuildingsExisting(BUILDING_GRANARY) == 0 &&
                info.Wood >= BUILD_GRANARY_WOOD && !DISABLE_GRANARY_BUILD) {
                builtThisFrame = tryBuild(BUILDING_GRANARY, 3);
            }
"""
G12B = """            if (!builtThisFrame && canAffordBuilding &&
                countBuildingsExisting(BUILDING_MARKET) == 0 && countBuildingsExisting(BUILDING_GRANARY) == 0 &&
                info.Wood >= BUILD_GRANARY_WOOD && !DISABLE_GRANARY_BUILD) {
                builtThisFrame = tryBuild(BUILDING_GRANARY, 3);
            }
"""
G8 = """        if (!builtThisFrame && countBuildingsExisting(BUILDING_GRANARY) == 0 &&
            info.Wood >= BUILD_GRANARY_WOOD && !DISABLE_GRANARY_BUILD) {
            builtThisFrame = tryBuild(BUILDING_GRANARY, 3);
        }
"""
REPL.append(('谷仓(rush)', G12E, '            tryBuildGranary(true);\n', 1))
REPL.append(('谷仓(postW1)', G12B, '            tryBuildGranary(true);\n', 1))
REPL.append(('谷仓(postW2)', G8, '        tryBuildGranary(false);\n', 1))

# ---------- 市场块（3 处）----------
M12R = """            if (!builtThisFrame && canAffordEcon &&
                countBuildingsExisting(BUILDING_MARKET) == 0 &&
                countBuildingsExisting(BUILDING_GRANARY) >= 1 && info.Wood >= 150) {
                builtThisFrame = tryBuild(BUILDING_MARKET, 3);
                if (builtThisFrame)
                    DebugText(QString("[MARKET f=%1] rushMilitary 期放行市场 wood=%2").arg(frame).arg((int)info.Wood));
            }
"""
M12W = """            if (!builtThisFrame && canAffordBuilding &&
                countBuildingsExisting(BUILDING_MARKET) == 0 &&
                countBuildingsExisting(BUILDING_GRANARY) >= 1 && info.Wood >= 150) {  // 造市场
                // ★ 2026-09-13：去掉 `info.Meat >= 100` 前置（原为"已去掉所有限制条件"却仍留着肉闸）。
                //   铜器期肉常被优先喂军，100 肉门槛会让市场在肉低谷反复跳空；postW2 市场闸(1835段)
                //   本就没有肉闸，此处对齐，避免同一建筑两套门槛。
                builtThisFrame = tryBuild(BUILDING_MARKET, 3);
                if (builtThisFrame)
                    DebugText(QString("[MARKET f=%1] postW1 经济期建市场 wood=%2").arg(frame).arg((int)info.Wood));
            }
"""
M8 = """        if (!builtThisFrame && !(needSecondStock && frame < WAVE3_TIME) &&
            countBuildingsExisting(BUILDING_MARKET) == 0 &&
            countBuildingsExisting(BUILDING_GRANARY) >= 1 && info.Wood >= 150) {  // 造市场（已去掉11分钟时间限制）
            builtThisFrame = tryBuild(BUILDING_MARKET, 3);
            if (builtThisFrame) DebugText(QString("[MARKET f=%1] 下令建造市场 wood=%2").arg(frame).arg((int)info.Wood));
        }
"""
REPL.append(('市场(rush)', M12R,
             '            if (!builtThisFrame && canAffordEconNow) tryBuildMarket("rushMilitary 期放行市场");\n', 1))
REPL.append(('市场(postW1)', M12W,
             '            if (!builtThisFrame && canAffordEconNow) tryBuildMarket("postW1 经济期建市场");\n', 1))
REPL.append(('市场(postW2)', M8,
             '        if (!builtThisFrame && !(needSecondStock && frame < WAVE3_TIME)) tryBuildMarket("下令建造市场");\n', 1))

# ---------- 合并后的冗余局部定义（值已由 lambda 区统一提供）----------
REPL.append(('删 canAffordBuilding',
             "            // ★ 铜器前/11分钟后/W2结束后：正常市场→农场\n"
             "            bool canAffordBuilding = (info.Meat >= 80 && info.Wood >= 50);\n",
             "            // ★ 铜器前/11分钟后/W2结束后：正常市场→农场\n", 1))
REPL.append(('删 canAffordEcon',
             "            bool canAffordEcon = (info.Meat >= 80 && info.Wood >= 50);\n",
             "", 1))

# ---------- 执行 ----------
ok = True
for name, old, new, cnt in REPL:
    got = s.count(old)
    if got != cnt:
        print('!! %-22s 期望 %d 命中，实际 %d' % (name, cnt, got))
        ok = False
        continue
    s = s.replace(old, new, cnt)
    print('ok %-22s x%d' % (name, cnt))

if not ok:
    print('ABORT：有替换未命中，未写文件')
    raise SystemExit(1)

open(P, 'w', encoding='utf-8', newline='').write(s.replace('\n', '\r\n'))
print('A2a done, 行数 %d → %d' % (before.count('\n'), s.count('\n')))
