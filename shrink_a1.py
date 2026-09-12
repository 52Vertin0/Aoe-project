# -*- coding: utf-8 -*-
"""A1：manageBuildings 精简第一步 —— 插入 9 个"建造块收口" lambda + 合并重复的局部判据。
纯结构抽提：lambda 内判据与原块逐字等价，调用点后续步骤再替换。
"""
import io
import sys

P = 'UsrAI.cpp'
s = open(P, encoding='utf-8', newline='').read()
assert '\r\n' in s, 'expect CRLF'
s = s.replace('\r\n', '\n')

# ---------- 1) 插入 lambda 定义（紧跟 postW2 定义之后）----------
anchor = "    bool postW2 = (frame >= WAVE2_TIME);\n"
assert s.count(anchor) == 1, s.count(anchor)

NEW = """
    // ====== ★ 2026-09-15 精简：建造块收口（铁律 21/26）======
    //   同一建筑的"该不该建 / 建不建得起"判据此前在 preW1 / postW1 / postW2 三个分支里各写一遍
    //   （房屋 4 处、谷仓 3 处、市场 3 处、靶场 3 处、兵营 3 处、箭塔 2 处、马厩 2 处、农场 2 处）——
    //   任一改动漏改一处就会让"阶段之间的行为悄悄分叉"，且看代码的人无法确认哪一份才是真源。
    //   此处收口为 9 个 lambda：判据与原块【逐字等价】，调用点保持原位置 + 原阶段守卫 ⇒ 行为不变。
    //   ⚠ 条件求值顺序一律保持原样：短路顺序决定 countBuildingsExisting() 的被调用次数
    //     （该函数带"90 帧防重窗口"副作用），重排即可能改行为。
    //   ⚠ 各阶段条件确有差异（如 preW1 的兵营多一道 houseCount 闸、postW2 的市场要避让第二仓库），
    //     差异一律做成显式参数，不做"想当然的合并"。
    const bool popHeadroomLowNow = (info.Human_MaxNum - humanPop <= POP_HEADROOM_BUILD);
    const bool canAffordEconNow  = (info.Meat >= 80 && info.Wood >= 50);
    auto tryBuildHouse = [&]() {
        if (!builtThisFrame && houseCount < MAX_HOUSES && !houseBuildingInProgress && popHeadroomLowNow &&
            info.Wood >= BUILD_HOUSE_WOOD)
            builtThisFrame = tryBuild(BUILDING_HOME, 2);
    };
    auto tryBuildGranary = [&](bool requireAfford) {
        if (!builtThisFrame && (!requireAfford || canAffordEconNow) &&
            countBuildingsExisting(BUILDING_MARKET) == 0 && countBuildingsExisting(BUILDING_GRANARY) == 0 &&
            info.Wood >= BUILD_GRANARY_WOOD && !DISABLE_GRANARY_BUILD)
            builtThisFrame = tryBuild(BUILDING_GRANARY, 3);
    };
    auto tryBuildMarket = [&](const char *tag) {
        if (!builtThisFrame &&
            countBuildingsExisting(BUILDING_MARKET) == 0 &&
            countBuildingsExisting(BUILDING_GRANARY) >= 1 && info.Wood >= 150) {
            builtThisFrame = tryBuild(BUILDING_MARKET, 3);
            if (builtThisFrame)
                DebugText(QString("[MARKET f=%1] %2 wood=%3").arg(frame).arg(tag).arg((int)info.Wood));
        }
    };
    auto tryBuildArmyCamp = [&](bool requireHouse) {
        if (!builtThisFrame && countBuildingsExisting(BUILDING_ARMYCAMP) == 0 &&
            (!requireHouse || houseCount >= 1) && info.Wood >= BUILD_ARMYCAMP_WOOD)
            builtThisFrame = tryBuild(BUILDING_ARMYCAMP, 3);
    };
    auto tryBuildRange = [&](const char *tag) {
        if (!builtThisFrame && countBuildingsExisting(BUILDING_RANGE) == 0 &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_RANGE_WOOD) {
            builtThisFrame = tryBuild(BUILDING_RANGE, 3);
            if (builtThisFrame && tag)
                DebugText(QString("[RANGE f=%1] %2 wood=%3").arg(frame).arg(tag).arg((int)info.Wood));
        }
    };
    auto tryBuildTower = [&]() {
        if (!builtThisFrame && towerCount < MAX_TOWERS && frame < WAVE3_TIME && info.Stone >= 150) {
            builtThisFrame = tryBuild(BUILDING_ARROWTOWER, 2);
            if (builtThisFrame) towerCount++;
        }
    };
    auto tryBuildStable = [&](bool requireToolAge, const char *tag) {
        if (!builtThisFrame && countBuildingsExisting(BUILDING_STABLE) == 0 &&
            (!requireToolAge || info.civilizationStage >= CIVILIZATION_TOOLAGE) &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_STABLE_WOOD && !DISABLE_STABLE_BUILD) {
            builtThisFrame = tryBuild(BUILDING_STABLE, 3);
            if (builtThisFrame)
                DebugText(QString("[STABLE f=%1] %2 wood=%3").arg(frame).arg(tag).arg((int)info.Wood));
        }
    };
    // 农场"木材需求额"：两处（postW1 / postW2）此前各算一遍同样的 6 行，口径必须同源。
    auto farmWoodNeedNow = [&]() {
        bool cbPending = (!compositeBowResearched && !compositeBowQueued && frame < FARM_WAIT_CB_FRAME);
        return FARM_WOOD_NEED(storageNearGazelleBuilt == 1) + (cbPending ? COMPOSITE_BOW_WOOD_RESERVE : 0);
    };
    auto farmerCountNow = [&]() {
        int n = 0;
        for (auto &f : info.farmers) if (f.FarmerSort == FARMERTYPE_FARMER) n++;
        return n;
    };
"""
s = s.replace(anchor, anchor + NEW, 1)

open(P, 'w', encoding='utf-8', newline='').write(s.replace('\n', '\r\n'))
print('A1 done')
