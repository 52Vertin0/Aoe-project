# -*- coding: utf-8 -*-
"""A2b：manageBuildings 第二轮 —— 农场需求额/农夫计数收口、聚类覆盖判据收口、
远距瞪羚判据收口、删 nearBushFood 死块。全部行为中性（纯抽提 / 纯删死代码）。
"""
P = 'UsrAI.cpp'
s = open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')
before = s

REPL = []

# ---------- 1) 删 nearBushFood 死块（结果从不被读取，原块只做一次无用的资源全表扫描）----------
NB = """            // ★ 检测基地附近浆果是否耗尽（耗尽则提前建市场+农场）
            int nearBushFood = 0;
            {
                double bBL = (double)BLOCKSIDELENGTH;
                auto bCenter = findBuilding(BUILDING_CENTER);
                double btcDR = bCenter ? (bCenter->BlockDR + 1) * bBL : 0;
                double btcUR = bCenter ? (bCenter->BlockUR + 1) * bBL : 0;
                for (auto &r : info.resources)
                    if (r.Type == RESOURCE_BUSH && r.Cnt > 0)
                        if (calDistance(btcDR, btcUR, r.DR, r.UR) < 30 * bBL) nearBushFood += r.Cnt;
            }

"""
REPL.append(('删 nearBushFood 死块', NB, '', 1))

# ---------- 2) postW1 农场块：需求额 + 目标农场数 ----------
F1 = """        bool cbSkillPending = (!compositeBowResearched && !compositeBowQueued && frame < FARM_WAIT_CB_FRAME);
        int farmWoodNeed2 = FARM_WOOD_NEED(storageNearGazelleBuilt == 1)
                          + (cbSkillPending ? COMPOSITE_BOW_WOOD_RESERVE : 0);
"""
REPL.append(('postW1 农场木材额', F1, "        int farmWoodNeed2 = farmWoodNeedNow();\n", 1))

F2 = """            int currentFarms = countFarmsForCap();
                int farmerCount = 0;
                for (auto &f : info.farmers)
                    if (f.FarmerSort == FARMERTYPE_FARMER) farmerCount++;
                int targetFarms = std::max(0, farmerCount - 2);
                targetFarms = std::min(targetFarms, MAX_FARMS);
                if (currentFarms < targetFarms) {
                    builtThisFrame = tryBuild(BUILDING_FARM, 3);
                }
            }
"""
REPL.append(('postW1 农场目标数', F2,
             "            int currentFarms = countFarmsForCap();\n"
             "                int targetFarms = std::min(std::max(0, farmerCountNow() - 2), MAX_FARMS);\n"
             "                if (currentFarms < targetFarms) {\n"
             "                    builtThisFrame = tryBuild(BUILDING_FARM, 3);\n"
             "                }\n"
             "            }\n", 1))

# ---------- 3) postW2 农场块：需求额 ----------
F3 = """        bool cbSkillPending2 = (!compositeBowResearched && !compositeBowQueued && frame < FARM_WAIT_CB_FRAME);
        int farmWoodNeed = FARM_WOOD_NEED(storageNearGazelleBuilt == 1)
                         + (cbSkillPending2 ? COMPOSITE_BOW_WOOD_RESERVE : 0);
"""
REPL.append(('postW2 农场木材额', F3, "        int farmWoodNeed = farmWoodNeedNow();\n", 1))

# ---------- 4) 聚类"是否已被现成仓库覆盖"：两处合一的 lambda + 调用点 ----------
CL_DEF_OLD = "                int existingStocks = countBuildingsExisting(BUILDING_STOCK);\n"
CL_DEF_NEW = """                // ★ 2026-09-15 收口：同一"本簇是否已被现成仓库覆盖"判据原先在本块内写了两遍
                //   （建造循环 1 次 + allCovered 判定 1 次）——判据写两遍即等于只剩一遍生效。
                auto clusterCovered = [&](double cdr, double cur) {
                    for (auto &b : info.buildings)
                        if (b.Type == BUILDING_STOCK && b.Percent == 100 &&
                            calDistance(cdr, cur, (b.BlockDR + 1) * gBL, (b.BlockUR + 1) * gBL)
                                < GAZELLE_HUNT_RANGE * gBL)
                            return true;
                    return false;
                };
                int existingStocks = countBuildingsExisting(BUILDING_STOCK);
"""
REPL.append(('clusterCovered 定义', CL_DEF_OLD, CL_DEF_NEW, 1))

CL1_OLD = """                    // ★ 该聚类是否已被现成仓库（任何已有者均视为前置库存，含初始化遗留）
                    bool covered = false;
                    for (auto &b : info.buildings)
                        if (b.Type == BUILDING_STOCK && b.Percent == 100 &&
                            calDistance(cl.dr, cl.ur, (b.BlockDR + 1) * gBL, (b.BlockUR + 1) * gBL)
                                < GAZELLE_HUNT_RANGE * gBL) {
                            covered = true; break;
                        }
                    if (covered) continue;   // 已覆盖则跳过本簇、继续下一簇（多重覆盖无意义）
"""
REPL.append(('clusterCovered 调用1', CL1_OLD,
             "                    // 该聚类已被现成仓库覆盖（任何已有者均视为前置库存，含初始化遗留）→ 跳过本簇\n"
             "                    if (clusterCovered(cl.dr, cl.ur)) continue;\n", 1))

CL2_OLD = """                    bool allCovered = true;
                    for (auto &cl : clusters) {
                        bool cov = false;
                        for (auto &b : info.buildings)
                            if (b.Type == BUILDING_STOCK && b.Percent == 100 &&
                                calDistance(cl.dr, cl.ur, (b.BlockDR + 1) * gBL, (b.BlockUR + 1) * gBL)
                                    < GAZELLE_HUNT_RANGE * gBL) {
                                cov = true; break;
                            }
                        if (!cov) { allCovered = false; break; }
                    }
                    if (allCovered) storageNearGazelleBuilt = 1;
"""
REPL.append(('clusterCovered 调用2', CL2_OLD,
             "                    bool allCovered = true;\n"
             "                    for (auto &cl : clusters)\n"
             "                        if (!clusterCovered(cl.dr, cl.ur)) { allCovered = false; break; }\n"
             "                    if (allCovered) storageNearGazelleBuilt = 1;\n", 1))

# ---------- 5) "远距瞪羚"判据：两处合一的 lambda + 调用点 ----------
FG_DEF_OLD = "        int gazelleAlive = 0;\n"
FG_DEF_NEW = """        // ★ 2026-09-15 收口："远距瞪羚"判据（距 TC > 20 格 且 距所有已建成仓库 > 20 格）原先在
        //   【needSecondStock 预判定】与【实际建造第二仓库】两处各写一遍 —— 两处口径必须完全一致，
        //   否则会出现"预判定说该建、建造块却不建"（或反之）的空转。
        auto isFarGazelle = [&](const tagResource &r, double tcDRx, double tcURx, double blx) -> bool {
            if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) return false;
            if (calDistance(tcDRx, tcURx, r.DR, r.UR) < 20 * blx) return false;
            for (auto &b : info.buildings)
                if (b.Type == BUILDING_STOCK && b.Percent == 100) {
                    double gDR = (b.BlockDR + 1) * blx, gUR = (b.BlockUR + 1) * blx;
                    if (calDistance(r.DR, r.UR, gDR, gUR) < 20 * blx) return false;
                }
            return true;
        };
        int gazelleAlive = 0;
"""
REPL.append(('isFarGazelle 定义', FG_DEF_OLD, FG_DEF_NEW, 1))

FG1_OLD = """                for (auto &r : info.resources) {
                    if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) continue;
                    if (calDistance(tcDRp, tcURp, r.DR, r.UR) < 20 * BLp) continue;
                    bool nearAnyStock = false;
                    for (auto &b : info.buildings) {
                        if (b.Type == BUILDING_STOCK && b.Percent == 100) {
                            double gDR = (b.BlockDR + 1) * BLp;
                            double gUR = (b.BlockUR + 1) * BLp;
                            if (calDistance(r.DR, r.UR, gDR, gUR) < 20 * BLp) {
                                nearAnyStock = true; break;
                            }
                        }
                    }
                    if (!nearAnyStock) {
                        farGazCnt++;
                        if (farGazCnt >= MIN_GAZELLE_FOR_SECOND_STOCK) { needSecondStock = true; break; }
                    }
                }
"""
REPL.append(('isFarGazelle 调用1', FG1_OLD,
             "                for (auto &r : info.resources) {\n"
             "                    if (!isFarGazelle(r, tcDRp, tcURp, BLp)) continue;\n"
             "                    farGazCnt++;\n"
             "                    if (farGazCnt >= MIN_GAZELLE_FOR_SECOND_STOCK) { needSecondStock = true; break; }\n"
             "                }\n", 1))

FG2_OLD = """            for (auto &r : info.resources) {
                if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) continue;
                if (calDistance(tcDR, tcUR, r.DR, r.UR) < 20 * BL) continue;
                bool farFromStock = true;
                for (auto &b : info.buildings) {
                    if (b.Type == BUILDING_STOCK && b.Percent == 100) {
                        double gDR = (b.BlockDR + 1) * BL;
                        double gUR = (b.BlockUR + 1) * BL;
                        if (calDistance(r.DR, r.UR, gDR, gUR) < 20 * BL) {
                            farFromStock = false; break;
                        }
                    }
                }
                if (farFromStock) farGaz.emplace_back(r.DR, r.UR);
            }
"""
REPL.append(('isFarGazelle 调用2', FG2_OLD,
             "            for (auto &r : info.resources)\n"
             "                if (isFarGazelle(r, tcDR, tcUR, BL))\n"
             "                    farGaz.emplace_back(r.DR, r.UR);\n", 1))

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
print('A2b done, 行数 %d → %d' % (before.count('\n'), s.count('\n')))
