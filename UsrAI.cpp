#include "UsrAI.h"

tagGame tagUsrGame;
ins UsrIns;
/*##########DO NOT MODIFY THE CODE ABOVE##########*/

// 波次时间（帧）- 来自任务文档
#define WAVE1_TIME 5000
#define WAVE2_TIME 13500
#define WAVE3_TIME 21000

// ★★★ 完整版：PPT策略——房→市→兵营→靶场→马厩→箭塔 ★★★
#define MAX_FARMERS 22          // 目标村民数量（PPT建议20-28）
#define MAX_HOUSES 10           // PPT：50人口=10房
#define MAX_FARMS 12            // 20+农民一半种田
#define MAX_TOWERS 3            // 箭塔数量
#define HUNT_GROUP_SIZE 2       // 羚羊狩猎组大小
#define ELEPHANT_HUNT_SIZE 4    // 大象狩猎组大小
#define MIN_FOOD_FOR_FARM 500   // 野生食物<500开始建农场
#define ASSIGN_PER_FRAME 30     // 一帧内全部分配
#define MIN_FOOD_WORKERS 6      // 铜器前冲食物：至少6人采食物
#define MIN_WOOD_WORKERS 1      // 降低木材保底，释放人手采食物
#define MIN_GOLD_WORKERS 1      // 至少1人挖金！铜器兵种+科技都需要黄金
#define FOOD_CRISIS_THRESHOLD 5 // 几乎不暂停产农
#define FOOD_PAUSE_TECH_TRAIN 60 // 食物<60暂停科技/训练
#define FOOD_CRITICAL 60
#define STUCK_GATHER_TIMEOUT 1500     // 空手且非空闲超时(帧)→判定寻路卡死(60秒)
#define STUCK_BLACKLIST_FRAMES 15000  // 不可达资源拉黑时长(10分钟,到期可重试)
// ============================================================
// processData - 主循环（每帧调用）
// 规则：祭司保命 > 失败检查 > 阶段切换 > 打猎 > 经济 > 军事 > 反攻
// ============================================================
void UsrAI::processData() {
    info = getInfo();
    frame = info.GameFrame;

    // 0. 处理上一帧建造指令结果：失败则释放建造者并换位置重试
    handleBuildResults();

    // 1. 失败检查（第一时间检查）
    checkDefeat();
    if (state == VICTORY || state == DEFEAT) return;

    // 2. 初始化关键 SN
    if (townCenterSN == -1) {
        for (auto &b : info.buildings) {
            if (b.Type == BUILDING_CENTER) { townCenterSN = b.SN; break; }
        }
    }
    if (priestSN == -1) {
        for (auto &a : info.armies) {
            if (a.Sort == AT_PRIEST) { priestSN = a.SN; break; }
        }
    }
    if (state == INIT) {
        if (townCenterSN != -1 && priestSN != -1) {
            state = EARLY_ECONOMY;
            DebugText("AI started — Tool Age. Target: Bronze Age + survive 3 waves.");
        }
        return;
    }

    // ---- 每帧更新祭司SN（防止祭司被重新编号） ----
    {
        bool found = false;
        for (auto &a : info.armies) {
            if (a.Sort == AT_PRIEST) { priestSN = a.SN; found = true; break; }
        }
        if (!found) priestSN = -1;
    }

    // 3. 祭司保命（最高优先级，每帧都要检查！）
    managePriest();

    // 4. 递减冷却
    if (buildCooldown > 0) buildCooldown--;
    if (techCooldown  > 0) techCooldown--;
    if (trainCooldown > 0) trainCooldown--;

    // 5. 阶段切换
    updateState();

    manageCarriedResources();

    manageFirstWaveDefense();

    // 6. 打猎管理（必须在经济管理之前！否则空闲农民已被分配完）
    manageHunting();

    // 6.5 检测寻路卡死的采集村民（先拉黑不可达资源再分配，避免反复派去）
    detectStuckGatherers();

    // 7. 经济管理（始终运行）
    manageEconomy();

    // 8. 军事管理（始终运行）
    manageMilitary();

    // 9. 反攻
    if (state == COUNTERATTACK) {
        manageCounterAttack();
    }

    // 10. 调试输出
    doDebugOutput();
}

// ============================================================
// 阶段切换（改进版：更稳健的状态转换）
// ============================================================
void UsrAI::updateState() {
    switch (state) {
    case EARLY_ECONOMY: {
        // ★ 食物够800立刻升铜器（一满足条件就升级，无建筑前置）
        if (info.Meat >= BUILDING_CENTER_UPGRADE_BRONZEAGE_FOOD) {
            auto tc = findBuilding(BUILDING_CENTER);
            if (tc && tc->Project == ACT_NULL) {
                BuildingAction(tc->SN, BUILDING_CENTER_UPGRADE);
                hasUpgraded = true;
                state = UPGRADING;
                DebugText(QString(">> Upgrading to Bronze Age! Frame=%1, Meat=%2, Farmers=%3")
                    .arg(frame).arg((int)info.Meat).arg((int)info.farmers.size()));
            }
        }
        // 超时保护：frame > WAVE1_TIME → 进入第一波防御准备
        if (frame > WAVE1_TIME && state == EARLY_ECONOMY) {
            state = DEFENSE_PREP;
            DebugText("!! Force DEFENSE_PREP (timeout from ECONOMY)");
        }
        break;
    }
    case UPGRADING:
        if (info.civilizationStage >= CIVILIZATION_BRONZEAGE) {
            state = DEFENSE_PREP;
            DebugText(">> Bronze Age reached!");
        }
        // 升级完成前保持 UPGRADING 状态，自然等待 civilizationStage 变化
        break;

    case DEFENSE_WAVE1:
        // ★ 食物够800立刻升铜器
        if (info.civilizationStage < CIVILIZATION_BRONZEAGE && !hasUpgraded) {
            if (info.Meat >= BUILDING_CENTER_UPGRADE_BRONZEAGE_FOOD) {
                auto tc = findBuilding(BUILDING_CENTER);
                if (tc && tc->Project == ACT_NULL) {
                    BuildingAction(tc->SN, BUILDING_CENTER_UPGRADE);
                    hasUpgraded = true;
                    state = UPGRADING;
                    DebugText(QString(">> WAVE1 Bronze Age! Frame=%1, Meat=%2")
                        .arg(frame).arg((int)info.Meat));
                    break;
                }
            }
        }
        // 第一波结束条件：敌人稀少 或 超时强制结束
        if (frame > WAVE1_TIME + 3500) {
            int eCount = info.enemy_armies.size() + info.enemy_farmers.size();
            if (eCount < 3 || frame > WAVE1_TIME + 6000) {
                wave1Defeated = true;
                state = DEFENSE_PREP;
                DebugText(QString(">> Wave 1 defeated at frame %1").arg(frame));
            }
        }
        // 第二波时间到了直接切换
        if (frame >= WAVE2_TIME && !wave2Started) {
            wave2Started = true;
            state = DEFENSE_WAVE2;
            DebugText("!! WAVE 2 INCOMING!");
        }
        break;

    case DEFENSE_PREP:
        // ★ 食物够800立刻升铜器
        if (info.civilizationStage < CIVILIZATION_BRONZEAGE && !hasUpgraded) {
            if (info.Meat >= BUILDING_CENTER_UPGRADE_BRONZEAGE_FOOD) {
                auto tc = findBuilding(BUILDING_CENTER);
                if (tc && tc->Project == ACT_NULL) {
                    BuildingAction(tc->SN, BUILDING_CENTER_UPGRADE);
                    hasUpgraded = true;
                    state = UPGRADING;
                    DebugText(QString(">> LATE Bronze Age! Frame=%1, Meat=%2")
                        .arg(frame).arg((int)info.Meat));
                }
            }
        }
        // 检测波次开始
        if (frame >= WAVE1_TIME && !wave1Started) {
            wave1Started = true;
            state = DEFENSE_WAVE1;
            DebugText("!! WAVE 1 INCOMING!");
            break;
        }
        if (frame >= WAVE2_TIME && !wave2Started) {
            wave2Started = true;
            state = DEFENSE_WAVE2;
            DebugText("!! WAVE 2 INCOMING!");
            break;
        }
        if (frame >= WAVE3_TIME && !wave3Started) {
            wave3Started = true;
            state = DEFENSE_WAVE3;
            DebugText("!! WAVE 3 INCOMING (no retreat)!");
            break;
        }
        break;

    case DEFENSE_WAVE2:
        // 铜器升级
        if (info.civilizationStage < CIVILIZATION_BRONZEAGE && !hasUpgraded) {
            if (info.Meat >= BUILDING_CENTER_UPGRADE_BRONZEAGE_FOOD) {
                auto tc = findBuilding(BUILDING_CENTER);
                if (tc && tc->Project == ACT_NULL) {
                    BuildingAction(tc->SN, BUILDING_CENTER_UPGRADE);
                    hasUpgraded = true;
                    state = UPGRADING;
                    DebugText(QString(">> W2 Bronze Age! Frame=%1, Meat=%2")
                        .arg(frame).arg((int)info.Meat));
                    break;
                }
            }
        }
        if (frame > WAVE2_TIME + 4500) {
            int eCount = info.enemy_armies.size() + info.enemy_farmers.size();
            if (eCount < 5 || frame > WAVE2_TIME + 7000) {
                wave2Defeated = true;
                state = DEFENSE_PREP;
                DebugText(QString(">> Wave 2 defeated at frame %1").arg(frame));
            }
        }
        if (frame >= WAVE3_TIME && !wave3Started) {
            wave3Started = true;
            state = DEFENSE_WAVE3;
            DebugText("!! WAVE 3 INCOMING (no retreat)!");
        }
        break;

    case DEFENSE_WAVE3:
        // 第三波必须全部消灭
        if (frame > WAVE3_TIME + 6000) {
            int eCount = info.enemy_armies.size() + info.enemy_farmers.size();
            if (eCount < 3 || frame > WAVE3_TIME + 10000) {
                wave3Defeated = true;
                state = COUNTERATTACK;
                DebugText(QString(">> ALL WAVES DEFEATED! Counterattack! Frame=%1").arg(frame));
            }
        }
        // 超时强制反击：frame > 27000
        if (frame > 27000 && state == DEFENSE_WAVE3) {
            state = COUNTERATTACK;
            DebugText("!! Force COUNTERATTACK (timeout)");
        }
        break;

    default: break;
    }
}

// ============================================================
// 祭司管理（W1感化刀斧兵 > 反攻感化 > 逃跑保命 > 治疗）
// ============================================================
void UsrAI::managePriest() {
    if (priestSN == -1) return;

    // ★ 祭司正在探路→跳过常规逻辑（由探路模块接管）
    if (scoutPhase < 20) return;

    tagArmy* priest = nullptr;
    for (auto &a : info.armies) {
        if (a.SN == priestSN) { priest = &a; break; }
    }
    if (!priest) return;

    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return;
    double BL = (double)BLOCKSIDELENGTH;
    double pDR = priest->DR, pUR = priest->UR;
    double tcDR = (center->BlockDR + 1) * BL;
    double tcUR = (center->BlockUR + 1) * BL;
    bool canAct = (priest->NowState == HUMAN_STATE_IDLE || priest->NowState == HUMAN_STATE_WALKING);

    if (priestMoveCooldown > 0) priestMoveCooldown--;

    auto convertPriority = [](int sort) -> int {
        if (sort == AT_CHARIOT_ARCHER) return 0;
        if (sort == AT_COMPOSITE_BOWMAN) return 1;
        if (sort == AT_STONE_THROWER) return 2;
        return 3;
    };

    auto findConvertTarget = [&](double dr, double ur, double range) -> int {
        int bestSN = -1;
        int bestPriority = 999;
        double bestDist = 1e12;
        for (auto &e : info.enemy_armies) {
            double d = calDistance(dr, ur, e.DR, e.UR);
            if (d > range) continue;
            int p = convertPriority(e.Sort);
            if (p < bestPriority || (p == bestPriority && d < bestDist)) {
                bestPriority = p;
                bestDist = d;
                bestSN = e.SN;
            }
        }
        for (auto &e : info.enemy_farmers) {
            double d = calDistance(dr, ur, e.DR, e.UR);
            if (d > range) continue;
            int p = 4;
            if (p < bestPriority || (p == bestPriority && d < bestDist)) {
                bestPriority = p;
                bestDist = d;
                bestSN = e.SN;
            }
        }
        return bestSN;
    };

    // ========== 优先级1：W1 感化（迎上去！15格发现→走近到12格感化）==========
    if (state == DEFENSE_WAVE1) {
        if (priest->NowState == HUMAN_STATE_ATTACKING || priest->NowState == HUMAN_STATE_WORKING) {
            return;  // 感化进行中，静等完成
        }

        int targetSN = findConvertTarget(pDR, pUR, 20 * BL);
        if (targetSN >= 0 && priest->ConvertCooldown <= 0 && priestMoveCooldown <= 0) {
            double eDR = 0, eUR = 0;
            for (auto &e : info.enemy_armies) {
                if (e.SN == targetSN) { eDR = e.DR; eUR = e.UR; break; }
            }
            if (eDR == 0 && eUR == 0) {
                for (auto &e : info.enemy_farmers) {
                    if (e.SN == targetSN) { eDR = e.DR; eUR = e.UR; break; }
                }
            }
            double dist = calDistance(pDR, pUR, eDR, eUR);
            if (dist <= 14 * BL) {
                HumanAction(priestSN, targetSN);
                priestMoveCooldown = 120;
                if (frame % 50 == 0)
                    DebugText(QString("Priest CONVERT W1! SN=%1").arg(targetSN));
                return;
            } else {
                // 14~20格→提前锁定目标，主动靠近
                double dx = eDR - pDR, dy = eUR - pUR;
                double len = std::sqrt(dx*dx + dy*dy);
                if (len > 0.01) {
                    HumanMove(priestSN, pDR + dx/len * (dist - 13 * BL), pUR + dy/len * (dist - 13 * BL));
                    priestMoveCooldown = 20;
                    return;
                }
            }
        }
    }

    // ========== 优先级2：反攻感化武器厂 ==========
    if (state == COUNTERATTACK) {
        if (enemySiegeSN == -1) {
            auto s = findEnemyBuilding(BUILDING_SIEGE);
            if (s) enemySiegeSN = s->SN;
        }
        auto siege = findEnemyBuilding(BUILDING_SIEGE);
        if (siege && priest->ConvertCooldown <= 0) {
            double sDR = siege->BlockDR * BL, sUR = siege->BlockUR * BL;
            if (calDistance(pDR, pUR, sDR, sUR) < 14 * BL) {
                HumanAction(priestSN, siege->SN); return;
            }
        } else if (!siege) { enemySiegeSN = -1; }
    }

    // ========== 优先级3：W2/W3 感化（迎上去！15格发现→走近到12格感化）==========
    if (state >= DEFENSE_WAVE2 && state <= DEFENSE_WAVE3) {
        if (priest->NowState == HUMAN_STATE_ATTACKING || priest->NowState == HUMAN_STATE_WORKING) {
            return;
        }
        int targetSN = findConvertTarget(pDR, pUR, 20 * BL);
        if (targetSN >= 0 && priest->ConvertCooldown <= 0 && priestMoveCooldown <= 0) {
            double eDR = 0, eUR = 0;
            for (auto &e : info.enemy_armies) {
                if (e.SN == targetSN) { eDR = e.DR; eUR = e.UR; break; }
            }
            if (eDR == 0 && eUR == 0) {
                for (auto &e : info.enemy_farmers) {
                    if (e.SN == targetSN) { eDR = e.DR; eUR = e.UR; break; }
                }
            }
            double dist = calDistance(pDR, pUR, eDR, eUR);
            if (dist <= 14 * BL) {
                HumanAction(priestSN, targetSN);
                priestMoveCooldown = 120;
                if (frame % 50 == 0)
                    DebugText(QString("Priest CONVERT W2/W3! SN=%1").arg(targetSN));
                return;
            } else {
                // 14~20格→提前锁定目标，主动靠近
                double dx = eDR - pDR, dy = eUR - pUR;
                double len = std::sqrt(dx*dx + dy*dy);
                if (len > 0.01) {
                    HumanMove(priestSN, pDR + dx/len * (dist - 13 * BL), pUR + dy/len * (dist - 13 * BL));
                    priestMoveCooldown = 20;
                    return;
                }
            }
        }
    }

    // ========== 优先级4：敌人靠近→迎上去感化，冷却中才逃跑 ==========
    int closeEnemy = findConvertTarget(pDR, pUR, 20 * BL);
    if (closeEnemy >= 0 && priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0) {
        // 感化冷却好了→迎上去感化
        if (priest->ConvertCooldown <= 0) {
            double eDR = 0, eUR = 0;
            for (auto &e : info.enemy_armies) {
                if (e.SN == closeEnemy) { eDR = e.DR; eUR = e.UR; break; }
            }
            if (eDR == 0 && eUR == 0) {
                for (auto &e : info.enemy_farmers) {
                    if (e.SN == closeEnemy) { eDR = e.DR; eUR = e.UR; break; }
                }
            }
            double dist = calDistance(pDR, pUR, eDR, eUR);
            if (dist <= 14 * BL) {
                HumanAction(priestSN, closeEnemy);
                priestMoveCooldown = 120;
                return;
            } else {
                // 14~20格→迎上去
                double dx = eDR - pDR, dy = eUR - pUR;
                double len = std::sqrt(dx*dx + dy*dy);
                if (len > 0.01) {
                    HumanMove(priestSN, pDR + dx/len * (dist - 13 * BL), pUR + dy/len * (dist - 13 * BL));
                    priestMoveCooldown = 20;
                    return;
                }
            }
        }
        // 感化冷却中→逃跑：远离敌人12格
        double eDR = 0, eUR = 0;
        for (auto &e : info.enemy_armies) {
            if (e.SN == closeEnemy) { eDR = e.DR; eUR = e.UR; break; }
        }
        if (eDR == 0 && eUR == 0) {
            for (auto &e : info.enemy_farmers) {
                if (e.SN == closeEnemy) { eDR = e.DR; eUR = e.UR; break; }
            }
        }
        double dx = pDR - eDR, dy = pUR - eUR;
        double len = std::sqrt(dx*dx + dy*dy);
        if (len > 0.01) {
            HumanMove(priestSN, pDR + dx/len * 12 * BL, pUR + dy/len * 12 * BL);
            priestMoveCooldown = 40;
            return;
        }
    }

    // ========== 优先级5：待机时守在TC旁（探完路后应待在TC附近）==========
    // ★ 目标用 TC 旁"空地"而非 TC 建筑中心（中心不可达→原逻辑放弃强回、祭司永远待在远处）。
    //   改用多半径×多角度螺旋找可走点，被石头/其他建筑堵住时逐级放大半径重试，确保真回到TC旁。
    {
        double dTC = calDistance(pDR, pUR, tcDR, tcUR);
        if (priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0) {
            if (dTC <= 6 * BL) {
                // 已在TC旁(≤6格)→无需移动，重置绕路计数
                priestNearTCTry = 0;
            } else {
                // 卡死检测：上次下指令后没挪窝→换下一档角度/半径重试（不无限重发同一点）
                double pIssueMoved = calDistance(pDR, pUR, priestIssueDR, priestIssueUR);
                bool pStuck = (priestIssueFrame > -999999) && (frame - priestIssueFrame > 45) && (pIssueMoved < 1.0 * BL);
                if (pStuck && priestNearTCTry + 1 < 24) priestNearTCTry++;
                // 多半径×多角度找TC旁可走点（{4,7,10}×BL × 8角度 = 24次）
                const double R[3] = {4.0, 7.0, 10.0};
                const int NA = 8;
                int idx = priestNearTCTry;
                int ri = idx / NA; if (ri > 2) ri = 2;
                int ai = idx % NA;
                double ang = (double)ai * 3.141592653589793 / 4.0;
                double rad = R[ri] * BL;
                double tx = tcDR + std::cos(ang) * rad;
                double ty = tcUR + std::sin(ang) * rad;
                tx = max(0.0, min((double)MAP_L * BL, tx));
                ty = max(0.0, min((double)MAP_U * BL, ty));
                HumanMove(priestSN, tx, ty);
                priestIssueDR = pDR; priestIssueUR = pUR; priestIssueFrame = frame;
                priestMoveCooldown = 15;
                return;
            }
        }
    }

    // ========== 优先级6：治疗（感化冷却中→治疗友军；空闲→治疗自己）==========
    if (priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0) {
        // 感化冷却中：优先治疗附近受伤友军（不浪费冷却时间）
        if (priest->ConvertCooldown > 0) {
            for (auto &a : info.armies) {
                if (a.SN == priestSN) continue;
                if (a.Blood < a.MaxBlood * 0.6 &&
                    calDistance(pDR, pUR, a.DR, a.UR) < 8 * BL) {
                    HumanAction(priestSN, a.SN);
                    priestMoveCooldown = 30;
                    if (frame % 50 == 0)
                        DebugText(QString("Priest HEAL ally (convert cooldown) SN=%1").arg(a.SN));
                    return;
                }
            }
        }
        // 空闲且自己掉血→治疗自己
        if (priest->Blood < priest->MaxBlood * 0.95) {
            HumanAction(priestSN, priestSN);
            priestMoveCooldown = 30;
            if (frame % 50 == 0)
                DebugText(QString("Priest HEAL SELF blood=%1/%2").arg((int)priest->Blood).arg((int)priest->MaxBlood));
            return;
        }
        // 自己满血→顺手治疗附近受伤友军（原逻辑保留）
        for (auto &a : info.armies) {
            if (a.SN == priestSN) continue;
            if (a.Blood < a.MaxBlood * 0.6) {
                if (calDistance(pDR, pUR, a.DR, a.UR) < 8 * BL) {
                    HumanAction(priestSN, a.SN); break;
                }
            }
        }
    }
}

// ============================================================
// 经济管理（农民生产 + 建筑 + 分配 + 科技）
// ============================================================
void UsrAI::manageEconomy() {
    // 1. 村民生产：有50食物就造人，冲到目标数量
    //    ★ 铜器升级条件已满足时优先升级：暂停造村民，把TC和食物留给升级指令
    auto center = findBuilding(BUILDING_CENTER);
    bool bronzeUpgradeReady = (info.civilizationStage < CIVILIZATION_BRONZEAGE && !hasUpgraded &&
                               info.Meat >= BUILDING_CENTER_UPGRADE_BRONZEAGE_FOOD &&
                               (state == EARLY_ECONOMY || state == DEFENSE_PREP ||
                                state == DEFENSE_WAVE1 || state == DEFENSE_WAVE2));
    if (center && center->Project == ACT_NULL && !bronzeUpgradeReady) {
        int farmerCount = 0;
        for (auto &f : info.farmers)
            if (f.FarmerSort == FARMERTYPE_FARMER) farmerCount++;

        int totalPop = info.farmers.size() + info.armies.size();
        int currentMaxFarmers = (frame < 13500) ? 16 : MAX_FARMERS;  // W2前限16农，优先升级
        if (farmerCount < currentMaxFarmers && totalPop < info.Human_MaxNum) {
            // ★ 铜器后：检查军事科技是否真的在研究中（已扣资源），而非乐观布尔值 ★
            // 乐观布尔值在 BuildingAction 发出时就设为 true，但资源尚未扣除
            // 必须查建筑的实际 Project 状态，确认科技已经"付款"正在执行
            bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
            int minFood = 50;
            if (postBronze) {
                // 检查阔剑/复合弓是否真的已启动（建筑 Project 非空）
                bool broadswordRunning = false;
                auto ac = findBuildingIncludingUnderConstruction(BUILDING_ARMYCAMP);
                if (ac && ac->Project == BUILDING_ARMYCAMP_UPGRADE_BROADSWORD)
                    broadswordRunning = true;

                bool compositeBowRunning = false;
                auto rng = findBuildingIncludingUnderConstruction(BUILDING_RANGE);
                if (rng && rng->Project == BUILDING_RANGE_UPGRADE_COMPOSITE_BOW)
                    compositeBowRunning = true;

                // 只有当真在研究中（已扣资源）才解锁农民生产
                bool militaryTechPaid = broadswordRunning || compositeBowRunning
                    || broadswordResearched || compositeBowResearched;

                if (!militaryTechPaid)
                    minFood = 190;  // 保留140给阔剑 + 50缓冲

                if (frame % 50 == 0) {
                    DebugText(QString("[FARMER f=%1] postBr=%2 paid=%3(brRun=%4 cbRun=%5 brd=%6 cmp=%7) minFd=%8 meat=%9 fCnt=%10")
                        .arg(frame).arg((int)postBronze).arg((int)militaryTechPaid)
                        .arg((int)broadswordRunning).arg((int)compositeBowRunning)
                        .arg((int)broadswordResearched).arg((int)compositeBowResearched)
                        .arg(minFood).arg((int)info.Meat).arg(farmerCount));
                }
            }

            if (info.Meat >= minFood) {
                DebugText(QString("!! PRODUCE FARMER f=%1 meat=%2 minFood=%3").arg(frame).arg((int)info.Meat).arg(minFood));
                BuildingAction(center->SN, BUILDING_CENTER_CREATEFARMER);
            }
        }
    }

    // 2. 建造管理
    manageBuildings();

    // 3. 分配空闲村民
    assignIdleFarmers();
    assignIdleSimple();

    // 4. 科技升级
    manageTechUpgrade();
}

// ============================================================
// 建造管理（PPT顺序：房屋→谷仓→市场→兵营→靶场→马厩→箭塔→学院）
// ============================================================
void UsrAI::manageBuildings() {
    releasedBuilders.clear();

    // ---- 废弃地基标记清理：已开始建造(Percent>0)或已不存在的建筑恢复有效 ----
    for (auto it = deadBuildings.begin(); it != deadBuildings.end(); ) {
        bool stillDead = false;
        for (auto &b : info.buildings) {
            if (b.SN == *it && b.Percent == 0) { stillDead = true; break; }
        }
        if (!stillDead) it = deadBuildings.erase(it); else ++it;
    }

    // ---- 建造者清理 ----
    // ★ 释放建造者：清空登记并标记本帧可重新分配
    auto releaseBuilder = [&](int sn) {
        releasedBuilders.insert(sn);
        buildStartFrame.erase(sn);
        builderIdleFrame.erase(sn);
    };
    for (auto it = buildingFarmerType.begin(); it != buildingFarmerType.end(); ) {
        int sn = it->first;
        int buildType = it->second;
        tagFarmer* f = nullptr;
        for (auto &x : info.farmers) {
            if (x.SN == sn) { f = &x; break; }
        }
        if (!f) {
            buildStartFrame.erase(sn);
            builderIdleFrame.erase(sn);
            buildRedispatchFrame.erase(sn);
            it = buildingFarmerType.erase(it);
            continue;
        }

        // ★ 定位该建造者正在建的建筑：优先按 WorkObjectSN 精确匹配，其次退化为该类型第一处在建
        tagBuilding* myB = nullptr;
        for (auto &b : info.buildings)
            if (b.SN == f->WorkObjectSN && b.Type == buildType) { myB = &b; break; }
        if (!myB)
            for (auto &b : info.buildings)
                if (b.Type == buildType && b.Percent < 100) { myB = &b; break; }

        if (!myB || myB->Percent >= 100) {
            // 建筑已建成或已不存在 → 真正"建完才释放"
            releaseBuilder(sn);
            it = buildingFarmerType.erase(it);
            continue;
        }

        // 建造者正在施工（WORKING 且目标就是该建筑）→ 正常推进，保持登记
        bool working = (f->NowState == HUMAN_STATE_WORKING && f->WorkObjectSN == myB->SN);
        if (working) {
            builderIdleFrame.erase(sn);
            buildRedispatchFrame.erase(sn);
            ++it; continue;
        }

        // 建筑仍在进行：建造者若空闲（走到一半/被打断/卡顿），重新派它回去继续建，绝不中途释放去采集
        if (f->NowState == HUMAN_STATE_IDLE && f->Resource <= 0) {
            if (builderIdleFrame.find(sn) == builderIdleFrame.end())
                builderIdleFrame[sn] = frame;   // 首次空闲起累计（重派不重置）
            // 节流：每60帧重新下发建造指令，把它送回地基继续施工
            if (buildRedispatchFrame.find(sn) == buildRedispatchFrame.end() || frame - buildRedispatchFrame[sn] >= 60) {
                HumanBuild(sn, buildType, (int)myB->BlockDR, (int)myB->BlockUR);
                buildRedispatchFrame[sn] = frame;
            }
            // 累计空闲>15秒仍建不成 → 判定地基不可达/废弃，放弃并拉黑（避免死等浪费村民）
            if (frame - builderIdleFrame[sn] > 900) {
                deadBuildings.insert(myB->SN);
                releaseBuilder(sn);
                it = buildingFarmerType.erase(it);
                continue;
            }
            ++it; continue;
        }

        // 其他状态（WALKING/ATTACKING 等）：保持登记等待；不清除 builderIdleFrame，让其继续累计空闲时间
        ++it;
    }
    bool builtThisFrame = false;
    int humanPop = info.farmers.size() + info.armies.size();
    int houseCount = countBuildingsAll(BUILDING_HOME);
    bool houseBuildingInProgress = false;
    for (auto &b : info.buildings) {
        if (b.Type == BUILDING_HOME && b.Percent < 100 && !deadBuildings.count(b.SN)) { houseBuildingInProgress = true; break; }
    }
    bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
    bool upgradeStarted = (state == UPGRADING || postBronze);
    bool rangeUnlocked = upgradeStarted;
    bool hasArmyCamp = (countBuildingsAll(BUILDING_ARMYCAMP) >= 1);
    bool hasRange = (countBuildingsAll(BUILDING_RANGE) >= 1);
    bool hasStable = (countBuildingsAll(BUILDING_STABLE) >= 1);

    bool preW1 = (frame < WAVE1_TIME);
    bool postW1 = (frame >= WAVE1_TIME && frame < WAVE2_TIME);
    bool postW2 = (frame >= WAVE2_TIME);

    // ====== 第一波前：房屋→兵营（工具时代就能建），不建其他 ======
    if (preW1) {
        // 人口≤2余量时补房屋
        bool popHeadroomLow = (info.Human_MaxNum <= humanPop + 2);
        if (!builtThisFrame && houseCount < MAX_HOUSES && !houseBuildingInProgress && popHeadroomLow &&
            info.Wood >= BUILD_HOUSE_WOOD) {
            builtThisFrame = tryBuild(BUILDING_HOME, 2);
        }
        // 有房屋后尽早造兵营（木材够就建，不等人满）
        if (!builtThisFrame && countBuildingsAll(BUILDING_ARMYCAMP) == 0 &&
            houseCount >= 1 && info.Wood >= BUILD_ARMYCAMP_WOOD) {
            builtThisFrame = tryBuild(BUILDING_ARMYCAMP, 3);
        }
    }

    // ====== 第一波后~第二波前：铜器启动即优先军事（工具时代就能建兵营） ======
    if (postW1) {
        bool rushMilitary = (upgradeStarted && frame < 16500 && !wave2Defeated);  // 升级已启动即可建兵营

        if (rushMilitary) {
            // ★ 铜器后军事优先：兵营→靶场→阔剑科技，不建市场农场
            if (!builtThisFrame && countBuildingsAll(BUILDING_ARMYCAMP) == 0 &&
                info.Wood >= BUILD_ARMYCAMP_WOOD) {
                builtThisFrame = tryBuild(BUILDING_ARMYCAMP, 3);
            }
            if (!builtThisFrame && countBuildingsAll(BUILDING_RANGE) == 0 &&
                countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_RANGE_WOOD) {
                builtThisFrame = tryBuild(BUILDING_RANGE, 3);
            }
            // 人口上限→补房屋
            bool popHeadroomLow = (info.Human_MaxNum <= humanPop + 2);
            if (!builtThisFrame && houseCount < MAX_HOUSES && !houseBuildingInProgress && popHeadroomLow &&
                info.Wood >= BUILD_HOUSE_WOOD) {
                builtThisFrame = tryBuild(BUILDING_HOME, 2);
            }
        } else {
            // ★ 铜器前/11分钟后/W2结束后：正常市场→农场
            bool canAffordBuilding = (info.Meat >= 80 && info.Wood >= 50);

            // ★ 检测基地附近浆果是否耗尽（耗尽则提前建市场+农场）
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

            if (!builtThisFrame && canAffordBuilding &&
                countBuildingsAll(BUILDING_MARKET) == 0 && countBuildingsAll(BUILDING_GRANARY) == 0 &&
                info.Wood >= BUILD_GRANARY_WOOD) {
                builtThisFrame = tryBuild(BUILDING_GRANARY, 3);
            }
            if (!builtThisFrame && canAffordBuilding &&
                countBuildingsAll(BUILDING_MARKET) == 0 &&
                countBuildingsAll(BUILDING_GRANARY) >= 1 && info.Wood >= 150 && info.Meat >= 100) {  // 造市场（已去掉所有限制条件）
                builtThisFrame = tryBuild(BUILDING_MARKET, 3);
            }

            // ★ 箭塔优先于农场：石头够就造（数量上限 MAX_TOWERS）
            if (!builtThisFrame && towerCount < MAX_TOWERS &&
                info.Stone >= 150) {
                builtThisFrame = tryBuild(BUILDING_ARROWTOWER, 2);
                if (builtThisFrame) towerCount++;
            }

            bool marketReady = (countBuildings(BUILDING_MARKET) >= 1);
            if (!builtThisFrame && marketReady && info.Wood >= 75 && info.Meat >= 100) {
                int currentFarms = countBuildingsAll(BUILDING_FARM);
                int farmerCount = 0;
                for (auto &f : info.farmers)
                    if (f.FarmerSort == FARMERTYPE_FARMER) farmerCount++;
                int targetFarms = std::max(0, farmerCount - 2);
                targetFarms = std::min(targetFarms, 20);
                if (currentFarms < targetFarms) {
                    builtThisFrame = tryBuild(BUILDING_FARM, 3);
                }
            }

            bool popHeadroomLow = (info.Human_MaxNum <= humanPop + 2);
            if (!builtThisFrame && houseCount < MAX_HOUSES && !houseBuildingInProgress && popHeadroomLow &&
                info.Wood >= BUILD_HOUSE_WOOD) {
                builtThisFrame = tryBuild(BUILDING_HOME, 2);
            }
        }
    }

    // ====== 第二波后：正常军事建筑 ======
    if (postW2) {
        // 为未建的军事建筑保留木材
        int woodForMilitary = 0;
        if (upgradeStarted && !hasArmyCamp) woodForMilitary = BUILD_ARMYCAMP_WOOD;
        else if (rangeUnlocked && !hasRange)  woodForMilitary = BUILD_RANGE_WOOD;

        // 房屋
        bool popHeadroomLow = (info.Human_MaxNum <= humanPop + 2);
        if (!builtThisFrame && houseCount < MAX_HOUSES && !houseBuildingInProgress && popHeadroomLow &&
            info.Wood >= BUILD_HOUSE_WOOD + woodForMilitary) {
            builtThisFrame = tryBuild(BUILDING_HOME, 2);
        }

        // 谷仓
        if (!builtThisFrame && countBuildingsAll(BUILDING_GRANARY) == 0 &&
            info.Wood >= BUILD_GRANARY_WOOD) {
            builtThisFrame = tryBuild(BUILDING_GRANARY, 3);
        }

        // ★ 第二仓库：瞪羚群距现有交付点>20格时建造（减少运输时间）
        if (!builtThisFrame && countBuildingsAll(BUILDING_GRANARY) == 1 &&
            wave2Defeated && info.Wood >= BUILD_GRANARY_WOOD + 30) {
            auto center = findBuilding(BUILDING_CENTER);
            double BL = (double)BLOCKSIDELENGTH;
            double tcDR = center ? (center->BlockDR + 1) * BL : 0;
            double tcUR = center ? (center->BlockUR + 1) * BL : 0;
            bool needSecondGranary = false;
            for (auto &r : info.resources) {
                if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) continue;
                if (calDistance(tcDR, tcUR, r.DR, r.UR) < 20 * BL) continue;
                bool farFromGranary = true;
                for (auto &b : info.buildings) {
                    if (b.Type == BUILDING_GRANARY && b.Percent == 100) {
                        double gDR = (b.BlockDR + 1) * BL;
                        double gUR = (b.BlockUR + 1) * BL;
                        if (calDistance(r.DR, r.UR, gDR, gUR) < 20 * BL) {
                            farFromGranary = false; break;
                        }
                    }
                }
                if (farFromGranary) { needSecondGranary = true; break; }
            }
            if (needSecondGranary)
                builtThisFrame = tryBuild(BUILDING_GRANARY, 3);
        }

        // 市场
        if (!builtThisFrame && countBuildingsAll(BUILDING_MARKET) == 0 &&
            countBuildingsAll(BUILDING_GRANARY) >= 1 && info.Wood >= 150) {  // 造市场（已去掉11分钟时间限制）
            builtThisFrame = tryBuild(BUILDING_MARKET, 3);
        }

        // 兵营
        if (!builtThisFrame && upgradeStarted && countBuildingsAll(BUILDING_ARMYCAMP) == 0 &&
            info.Wood >= BUILD_ARMYCAMP_WOOD) {
            builtThisFrame = tryBuild(BUILDING_ARMYCAMP, 3);
        }

        // 靶场
        if (!builtThisFrame && rangeUnlocked && countBuildingsAll(BUILDING_RANGE) == 0 &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_RANGE_WOOD) {
            builtThisFrame = tryBuild(BUILDING_RANGE, 3);
        }

        // 箭塔：石头够就造（已解除 铜器/箭塔科技/兵营/靶场 前置；数量上限 MAX_TOWERS 保留）
        if (!builtThisFrame && towerCount < MAX_TOWERS &&
            info.Stone >= 150) {
            builtThisFrame = tryBuild(BUILDING_ARROWTOWER, 2);
            if (builtThisFrame) towerCount++;
        }

        // 农场
        if (!builtThisFrame) {
            int currentFarms = countBuildings(BUILDING_FARM);
            if (currentFarms < farmTarget && info.Wood >= 75) {
                builtThisFrame = tryBuild(BUILDING_FARM, 3);
            }
        }
    }
}

// ============================================================
// 分配空闲村民采集（改进版：每帧2个 + 金矿 + 自动调整农场目标）
// ============================================================
void UsrAI::assignIdleFarmers() {
    frameFoodTargets.clear();  // ★ 每帧重置：防同帧多农民分配到同一目标
    frameBushCount.clear();    // ★ 每帧重置浆果每丛分配计数
    frameWoodCount.clear();  // ★ 每帧重置木材分配计数
    frameGazelleCount.clear(); // ★ 每帧重置瞪羚每只分配计数
    for (auto it = pendingWoodAssigns.begin(); it != pendingWoodAssigns.end(); ) {
        bool stillIdle = false;
        for (auto &f : info.farmers) {
            if (f.SN == *it && f.NowState == HUMAN_STATE_IDLE && f.Resource <= 0) {
                stillIdle = true; break;
            }
        }
        if (!stillIdle) it = pendingWoodAssigns.erase(it); else ++it;
    }
    std::set<int> frameAssigned;  // ★ 本帧已分配村民SN（safetyNet 跳过，防同帧二次分配把食物覆盖成木头）
    for (auto sn : huntingGroup) frameAssigned.insert(sn);  // ★ 打猎中的村民（本帧刚派/仍在攻击）不被覆盖
    const int woodFloor = std::max(MIN_WOOD_WORKERS, 2);    // 木工保底人数：无论哪个阶段至少保留2人

    // ---- 动态计算农场目标 ----
    int bushFood = 0, huntFood = 0, nearBushFood = 0;
    {
        double bBL = (double)BLOCKSIDELENGTH;
        auto bCenter = findBuilding(BUILDING_CENTER);
        double btcDR = bCenter ? (bCenter->BlockDR + 1) * bBL : 0;
        double btcUR = bCenter ? (bCenter->BlockUR + 1) * bBL : 0;
        for (auto &r : info.resources) {
            if (r.Type == RESOURCE_BUSH) {
                bushFood += r.Cnt;
                if (calDistance(btcDR, btcUR, r.DR, r.UR) < 30 * bBL) nearBushFood += r.Cnt;
            }
            else if (r.Type == RESOURCE_GAZELLE || r.Type == RESOURCE_ELEPHANT)
                huntFood += r.Cnt;
        }
    }
    int totalWildFood = bushFood + huntFood;
    bool marketBuilt = (countBuildings(BUILDING_MARKET) >= 1);
    bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);

    // ★ 农场策略：基地附近浆果耗尽时转农场；远处浆果不算
    if (nearBushFood > 0) {
        // 基地附近还有浆果，继续采野果
        farmTarget = 0;
    } else if (!marketBuilt) {
        farmTarget = 0;
    } else if (frame < 7500 && totalWildFood > 300) {
        // 5分钟前野生食物充足：不建农场
        farmTarget = 0;
    } else {
        // 青铜后保底4农场（军事需要稳定食物）
        int baseFarms = postBronze ? 4 : 0;

        if (totalWildFood < 300 || info.Meat < 200) {
            farmTarget = MAX_FARMS;           // 12 — 野生食物枯竭，全上农场
        } else if (totalWildFood < 500) {
            farmTarget = std::max(8, baseFarms);  // 8
        } else if (totalWildFood < 1000) {
            farmTarget = std::max(6, baseFarms);  // 6
        } else {
            farmTarget = std::max(4, baseFarms);  // 4 — 充足的野生食物+保底
        }
    }

    // ---- 统计各资源采集人数（含走路中的工人） ----
    int foodWorkers = 0, woodWorkers = 0, goldWorkers = 0;
    int idleCount = 0;
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (f.NowState == HUMAN_STATE_IDLE) {
            if (f.Resource > 0) continue;
            idleCount++; continue;
        }
        int rs = f.ResourceSort;
        if (rs == HUMAN_GRANARYFOOD || rs == HUMAN_STOCKFOOD) foodWorkers++;
        else if (rs == HUMAN_WOOD)  woodWorkers++;
        else if (rs == HUMAN_GOLD)  goldWorkers++;
        // ★ ResourceSort为空但WorkObjectSN指向资源：走路中，按目标类型计数
        else if (f.WorkObjectSN > 0) {
            for (auto &r : info.resources) {
                if (r.SN == f.WorkObjectSN && r.Cnt > 0) {
                    if (r.Type == RESOURCE_BUSH || r.Type == RESOURCE_GAZELLE || r.Type == RESOURCE_ELEPHANT)
                        foodWorkers++;
                    else if (r.Type == RESOURCE_TREE) woodWorkers++;
                    else if (r.Type == RESOURCE_GOLD) goldWorkers++;
                    break;
                }
            }
        }
    }

    int farmerCount = 0;
    for (auto &f : info.farmers)
        if (f.FarmerSort == FARMERTYPE_FARMER) farmerCount++;
    int effectiveWoodWorkers = woodWorkers + (int)pendingWoodAssigns.size();

    int maxAssignThisFrame = ASSIGN_PER_FRAME;
    int assigned = 0;

    // ★ 安全网：兜底分配，确保任何仍空闲的村民都被派去伐木/采集（树始终存在，杜绝空闲）★
    auto safetyNetAssign = [&]() {
        for (auto &f : info.farmers) {
            if (f.FarmerSort != FARMERTYPE_FARMER) continue;
            if (frameAssigned.count(f.SN)) continue;  // ★ 主循环已分配过，跳过（防同帧二次分配覆盖）
            if (waveBlockers.count(f.SN) || buildingFarmerType.count(f.SN) || f.SN == scoutFarmerSN) continue;
            if (f.Resource > 0) continue;
            if (f.NowState != HUMAN_STATE_IDLE && !releasedBuilders.count(f.SN)) continue;
            if (tryAssignFood(&f)) continue;  // ★ 兜底也遵循食物优先
            if ((frame >= WAVE1_TIME || effectiveWoodWorkers < woodFloor) && tryAssignWood(&f)) {
                pendingWoodAssigns.insert(f.SN);
                effectiveWoodWorkers++;
                continue;
            }

            // ★ 最终兜底：前两者均失败时，直接派到任意可见资源，绝不让村民停在TC旁。
            std::vector<int> anyTypes = { RESOURCE_BUSH, RESOURCE_TREE, RESOURCE_GOLD, RESOURCE_GAZELLE, RESOURCE_ELEPHANT };
            tagResource* anyRes = findNearestResourceAny(anyTypes, f.DR, f.UR);
            if (anyRes) HumanAction(f.SN, anyRes->SN);
        }
    };

    // 最后机会：所有普通分配后仍然 IDLE 的村民，直接派到任意最近资源。
    auto lastChanceAssign = [&]() {
        for (auto &f : info.farmers) {
            if (f.FarmerSort != FARMERTYPE_FARMER) continue;
            if (waveBlockers.count(f.SN) || f.SN == scoutFarmerSN) continue;
            if (f.Resource > 0) continue;
            if (f.NowState != HUMAN_STATE_IDLE) continue;

            std::vector<int> anyTypes = { RESOURCE_BUSH, RESOURCE_TREE, RESOURCE_GOLD, RESOURCE_GAZELLE, RESOURCE_ELEPHANT };
            tagResource* anyRes = findNearestResourceAny(anyTypes, f.DR, f.UR);
            if (anyRes) {
                HumanAction(f.SN, anyRes->SN);
                if (anyRes->Type == RESOURCE_TREE) {
                    pendingWoodAssigns.insert(f.SN);
                    effectiveWoodWorkers++;
                }
            }
        }
    };

    // 木工不足时从低优先级的食物工中抢人，先抢猎人，再抢第二人以上的浆果工。
    auto pullWoodWorkers = [&](int need) {
        for (int pass = 0; pass < 2 && need > 0; ++pass) {
            for (auto &f : info.farmers) {
                if (need <= 0) break;
                if (f.FarmerSort != FARMERTYPE_FARMER) continue;
                if (waveBlockers.count(f.SN) || buildingFarmerType.count(f.SN) || f.SN == scoutFarmerSN) continue;
                if (f.NowState != HUMAN_STATE_WORKING || f.WorkObjectSN <= 0) continue;

                bool isHunt = false, isBush = false;
                for (auto &r : info.resources) {
                    if (r.SN == f.WorkObjectSN && r.Cnt > 0) {
                        if (r.Type == RESOURCE_GAZELLE || r.Type == RESOURCE_ELEPHANT) isHunt = true;
                        else if (r.Type == RESOURCE_BUSH) isBush = true;
                        break;
                    }
                }
                if (pass == 0 && !isHunt) continue;
                if (pass == 1 && !isBush) continue;
                if (pass == 1) {
                    int onBush = 0;
                    for (auto &other : info.farmers)
                        if (other.WorkObjectSN == f.WorkObjectSN) onBush++;
                    if (onBush <= 1) continue; // 每丛至少保留1人
                }
                if (tryAssignWood(&f)) {
                    woodWorkers++;
                    need--;
                }
            }
        }
    };

    bool preW1 = (frame < WAVE1_TIME);                        // 第一波前：全员食物
    bool postW1 = (frame >= WAVE1_TIME && frame < WAVE2_TIME); // 第一波后：市场→农场
    bool postW2 = (frame >= WAVE2_TIME);                       // 第二波后：正常策略

    // ====== 祭司探路：8方向放射状，祭司视野远，覆盖更广 ======
    bool isWar = (state >= DEFENSE_WAVE1 && state <= DEFENSE_WAVE3);
    if (!isWar && state != COUNTERATTACK && scoutPhase < 16) {
        double BL = (double)BLOCKSIDELENGTH;

        // ★ 返回绕路：多半径×多角度螺旋（被石头/障碍堵住时逐级放大半径重试，降低死循环）★
        const int SCOUT_RETURN_RADII[3] = {4, 7, 10};   // 单位 BL
        const int SCOUT_RETURN_ANGLES = 8;
        const int SCOUT_RETURN_MAX = SCOUT_RETURN_ANGLES * 3;  // 共 24 次尝试
        auto scoutReturnPoint = [&](int tryN, double bDR, double bUR, double& wx, double& wy) {
            int a = tryN % SCOUT_RETURN_ANGLES;
            int r = tryN / SCOUT_RETURN_ANGLES; if (r > 2) r = 2;
            double ra = (double)a * 3.141592653589793 / 4.0;
            double R = SCOUT_RETURN_RADII[r] * BL;
            wx = bDR + std::cos(ra) * R;
            wy = bUR + std::sin(ra) * R;
            wx = max(0.0, min((double)MAP_L * BL, wx));
            wy = max(0.0, min((double)MAP_U * BL, wy));
        };

        if (scoutCooldown > 0) scoutCooldown--;

        // ★ 检查是否金矿+瞪羚+树已发现（树必探！否则 tryAssignWood 恒失败→无人伐木→无木建农场/兵营）
        bool hasGold = false, hasGazelle = false, hasTree = false;
        for (auto &r : info.resources) {
            if (r.Cnt <= 0) continue;
            if (r.Type == RESOURCE_GOLD) hasGold = true;
            if (r.Type == RESOURCE_GAZELLE) hasGazelle = true;
            if (r.Type == RESOURCE_TREE) hasTree = true;
        }
        if ((hasGold && hasGazelle && hasTree) || scoutDirsDone >= 4) {
            scoutPhase = 20;  // 三资源找齐 或 已探完4个外向方向 → 结束探路，回TC待命
        }

        // 验证祭司是否还活着
        if (priestSN != -1) {
            bool alive = false;
            for (auto &a : info.armies) {
                if (a.SN == priestSN && a.Sort == AT_PRIEST) {
                    alive = true; break;
                }
            }
            if (!alive) { priestSN = -1; scoutWalkTimer = 0; }
        }

        // 祭司不存在→无法探路
        if (priestSN == -1) {
            scoutPhase = 20;  // 释放探路状态
        }

        // 发探路移动指令
        if (priestSN != -1 && scoutPhase < 16) {
            tagArmy* scout = nullptr;
            for (auto &a : info.armies) {
                if (a.SN == priestSN) { scout = &a; break; }
            }

            // ★ 每帧检测：敌方军队→回TC换方向；野兽/敌村民→逃12格（禁止感化！）
            bool fledThisFrame = false;
            if (scout) {
                auto center = findBuilding(BUILDING_CENTER);
                double tcDR = center ? (center->BlockDR + 1) * BL : scout->DR;
                double tcUR = center ? (center->BlockUR + 1) * BL : scout->UR;

                double beastDist = 12 * BL, beastX = scout->DR, beastY = scout->UR;
                bool beastNearby = false;
                double enemyDist = 12 * BL, enemyX = scout->DR, enemyY = scout->UR;
                bool enemyNearby = false;

                // 野兽
                for (auto &r : info.resources) {
                    if (r.Cnt <= 0) continue;
                    if (r.Type != RESOURCE_LION && r.Type != RESOURCE_ELEPHANT) continue;
                    double d = calDistance(scout->DR, scout->UR, r.DR, r.UR);
                    if (d < beastDist) { beastDist = d; beastX = r.DR; beastY = r.UR; beastNearby = true; }
                }
                // 敌方军队
                for (auto &e : info.enemy_armies) {
                    if (e.Blood <= 0) continue;
                    double d = calDistance(scout->DR, scout->UR, e.DR, e.UR);
                    if (d < enemyDist) { enemyDist = d; enemyX = e.DR; enemyY = e.UR; enemyNearby = true; }
                }
                // 敌方村民
                for (auto &e : info.enemy_farmers) {
                    if (e.Blood <= 0) continue;
                    double d = calDistance(scout->DR, scout->UR, e.DR, e.UR);
                    if (d < beastDist) { beastDist = d; beastX = e.DR; beastY = e.UR; beastNearby = true; }
                }

                if (scout->NowState != HUMAN_STATE_WALKING) {
                    if (enemyNearby) {
                        // ★ 发现敌军→立刻回TC，跳过此方向（下一轮探另一方向）
                        // 遇敌返回：移到TC旁空地（避开建筑中心/石头），用多半径螺旋绕路
                        double rx = 0, ry = 0;
                        scoutReturnPoint(scoutReturnTry, tcDR, tcUR, rx, ry);
                        HumanMove(scout->SN, rx, ry);
                        scoutIssueDR = scout->DR; scoutIssueUR = scout->UR; scoutIssueFrame = frame;
                        scoutPhase++;
                        if (scoutPhase >= 16) scoutPhase = 20;  // 探完→结束探路回TC待命
                        scoutReturnTry = 0;
                        scoutCooldown = 20;
                        scoutWalkTimer = 0;
                        fledThisFrame = true;
                    } else if (beastNearby) {
                        // ★ 野兽→远离12格，继续当前方向
                        double awayDX = scout->DR - beastX;
                        double awayDY = scout->UR - beastY;
                        double awayLen = std::sqrt(awayDX*awayDX + awayDY*awayDY);
                        if (awayLen < 0.01) { awayDX = 1; awayDY = 0; awayLen = 1; }
                        double tx = scout->DR + (awayDX / awayLen) * 12 * BL;
                        double ty = scout->UR + (awayDY / awayLen) * 12 * BL;
                        tx = max(0.0, min((double)MAP_L * BL, tx));
                        ty = max(0.0, min((double)MAP_U * BL, ty));
                        HumanMove(scout->SN, tx, ty);
                        scoutIssueDR = scout->DR; scoutIssueUR = scout->UR; scoutIssueFrame = frame;
                        scoutCooldown = 30;
                        scoutWalkTimer = 0;
                        fledThisFrame = true;
                    }
                }
            }

            if (!fledThisFrame) {
            if (scoutCooldown > 0) { /* 冷却中且无威胁→等待 */ }
            else {
            // 走路计时：走路+1，空闲清零。超1200帧(48秒)=不可达→跳过
            if (scout) {
                if (scout->NowState == HUMAN_STATE_WALKING) scoutWalkTimer++;
                else scoutWalkTimer = 0;
            }
            // ★ 关键修复：目标不可达时祭司保持 IDLE（不进入 WALKING），
            //   原 scoutWalkTimer 永远为0、scoutLegStartFrame 又被每帧重发重置，
            //   卡死检测失效→scoutReturnTry 不前进→同一不可达点无限重发。
            //   改用"下发移动指令后祭司实际没挪窝"的位置进度检测，即使 IDLE 也能识别卡死。
            double scoutIssueMoved = calDistance(scout->DR, scout->UR, scoutIssueDR, scoutIssueUR);
            bool noProgress = (scoutIssueFrame > -999999) && (frame - scoutIssueFrame > 20) && (scoutIssueMoved < 1.0 * BL);
            bool scoutStuck = (scoutWalkTimer > 1200 || noProgress ||
                               (scoutLegStartFrame > 0 && frame - scoutLegStartFrame > 2000));

            if (scoutStuck) {
                bool stuckInReturn = (scoutPhase % 2 == 1);  // 奇数=返回阶段
                if (stuckInReturn && scoutReturnTry + 1 < SCOUT_RETURN_MAX) {
                    // ★ 返回被石头堵→多半径×多角度螺旋重试绕路（逐级放大半径），不放弃返回
                    scoutReturnTry++;
                    scoutWalkTimer = 0;
                    scoutLegStartFrame = frame;
                    scoutCooldown = 5;
                } else if (stuckInReturn) {
                    // 返回8个角度都失败→放弃返回，交给 managePriest 回TC旁（多半径螺旋绕路，避免卡在建筑中心）
                    scoutPhase = 20;
                    scoutReturnTry = 0;
                    priestNearTCTry = 0;  // 重置守TC旁绕路计数，从角度0重新尝试
                    scoutWalkTimer = 0;
                    scoutIssueFrame = -999999;  // 重置，避免 managePriest 误判卡死
                    scoutCooldown = 10;
                } else {
                    // 外出探路卡住→放弃此方向，推进下一阶段（换下一个外向方向继续探）
                    scoutPhase++;
                    if (scoutPhase >= 16) scoutPhase = 20;  // 探完→结束探路回TC待命
                    scoutReturnTry = 0;
                    scoutWalkTimer = 0;
                    scoutLegStartFrame = frame;
                    scoutCooldown = 10;
                }
            } else if (scout && (scout->NowState == HUMAN_STATE_ATTACKING || scout->NowState == HUMAN_STATE_WORKING)) {
                // ★ 探路中被野兽/敌人纠缠→远离最近的威胁（禁止感化！保命+继续探路优先）
                double fleeX = scout->DR, fleeY = scout->UR;
                double nearestDist = 1e12;
                // 检查野兽威胁
                for (auto &r : info.resources) {
                    if (r.Cnt <= 0) continue;
                    if (r.Type != RESOURCE_LION && r.Type != RESOURCE_ELEPHANT) continue;
                    double d = calDistance(scout->DR, scout->UR, r.DR, r.UR);
                    if (d < nearestDist) { nearestDist = d; fleeX = r.DR; fleeY = r.UR; }
                }
                // 检查敌方军队威胁（包括正在被感化的敌人）
                for (auto &e : info.enemy_armies) {
                    if (e.Blood <= 0) continue;
                    double d = calDistance(scout->DR, scout->UR, e.DR, e.UR);
                    if (d < nearestDist) { nearestDist = d; fleeX = e.DR; fleeY = e.UR; }
                }
                // 检查敌方村民威胁
                for (auto &e : info.enemy_farmers) {
                    if (e.Blood <= 0) continue;
                    double d = calDistance(scout->DR, scout->UR, e.DR, e.UR);
                    if (d < nearestDist) { nearestDist = d; fleeX = e.DR; fleeY = e.UR; }
                }
                // 远离最近威胁，跑12格
                double awayDX = scout->DR - fleeX;
                double awayDY = scout->UR - fleeY;
                double awayLen = std::sqrt(awayDX*awayDX + awayDY*awayDY);
                if (awayLen < 0.01) { awayDX = 1; awayDY = 0; awayLen = 1; }
                double tx = scout->DR + (awayDX / awayLen) * 12 * BL;
                double ty = scout->UR + (awayDY / awayLen) * 12 * BL;
                tx = max(0.0, min((double)MAP_L * BL, tx));
                ty = max(0.0, min((double)MAP_U * BL, ty));
                HumanMove(scout->SN, tx, ty);
                scoutIssueDR = scout->DR; scoutIssueUR = scout->UR; scoutIssueFrame = frame;
                scoutCooldown = 30;
                scoutWalkTimer = 0;
            } else if (scout && scout->NowState == HUMAN_STATE_IDLE) {
                auto center = findBuilding(BUILDING_CENTER);
                if (center) {
                    double baseDR = (center->BlockDR + 1) * BL;
                    double baseUR = (center->BlockUR + 1) * BL;
                    double sDR = scout->DR, sUR = scout->UR;

                    // 地图四边边缘坐标
                    double edgeWest  = 0;
                    double edgeEast  = MAP_L * BL;
                    double edgeSouth = 0;
                    double edgeNorth = MAP_U * BL;

                    bool nearTarget = false;
                    const double SCOUT_DIST = 55.0;  // 探索半径由40格扩大到55格，覆盖更远资源

                    // ★ 根据TC象限决定探索方向和顺序
                    double distWest  = baseDR / BL;
                    double distEast  = (MAP_L * BL - baseDR) / BL;
                    double distSouth = baseUR / BL;
                    double distNorth = (MAP_U * BL - baseUR) / BL;
                    double tcBlockX = baseDR / BL;
                    double tcBlockY = baseUR / BL;
                    double mapCX = MAP_L / 2.0;
                    double mapCY = MAP_U / 2.0;
                    bool nearWest  = (tcBlockX < mapCX * 0.5);
                    bool nearEast  = (tcBlockX > mapCX * 1.5);
                    bool nearSouth = (tcBlockY < mapCY * 0.5);
                    bool nearNorth = (tcBlockY > mapCY * 1.5);

                    // 计算8方向范围(格数)
                    double range[8];
                    range[0] = distWest;
                    range[1] = (distWest  < distSouth ? distWest  : distSouth) * 1.414;
                    range[2] = distSouth;
                    range[3] = (distEast  < distSouth ? distEast  : distSouth) * 1.414;
                    range[4] = distEast;
                    range[5] = (distEast  < distNorth ? distEast  : distNorth) * 1.414;
                    range[6] = distNorth;
                    range[7] = (distWest  < distNorth ? distWest  : distNorth) * 1.414;

                    // 按象限构建dirOrder：优先方向→其余按范围填充
                    int dirOrder[8];
                    bool used[8] = {false};
                    int di = 0;
                    auto addDir = [&](int d) { if (!used[d]) { dirOrder[di++] = d; used[d] = true; } };
                    if (nearWest && nearNorth) {
                        addDir(4); addDir(3);  // E优先, SE次之（NW角→向E/SE最远）
                    } else if (nearWest && nearSouth) {
                        addDir(6); addDir(4);  // N优先, E次之（SW角→N最远）
                    } else if (nearEast && nearSouth) {
                        addDir(6); addDir(0);  // N优先, W次之（SE角→N最远）
                    } else if (nearEast && nearNorth) {
                        addDir(0); addDir(1);  // W→SW（NE角远离东和北边缘）
                    }
                    // 其余方向按范围降序填充
                    while (di < 8) {
                        int best = -1; double bestR = -1;
                        for (int j = 0; j < 8; j++) {
                            if (!used[j] && range[j] > bestR) { bestR = range[j]; best = j; }
                        }
                        dirOrder[di++] = best; used[best] = true;
                    }

                    int dir = dirOrder[scoutPhase / 2];
                    bool ret = (scoutPhase % 2 == 1);

                    if (!ret) {
                            // 8方向单位向量 (dx=东, dy=北)
                            double dirX[8] = {-1, -1,  0,  1, 1, 1, 0, -1};
                            double dirY[8] = { 0, -1, -1, -1, 0, 1, 1,  1};
                            bool isDiag = (dir % 2 == 1);
                            double dist = SCOUT_DIST * BL;
                            if (isDiag) dist *= 0.707;  // 对角线保持实际距离≈40格

                            double dx = dirX[dir], dy = dirY[dir];
                            // 探索终点：TC 沿该方向 40 格（钳制到地图边缘）
                            double gx = baseDR + dx * dist;
                            double gy = baseUR + dy * dist;
                            gx = max(edgeWest, min(edgeEast, gx));
                            gy = max(edgeSouth, min(edgeNorth, gy));
                            // ★ 关键：每步只朝终点走 ~9 格（< 祭司 12 格视野），
                            //   保证目标始终在已探索范围内可达；到达后再走下一步，逐步推进
                            double gdx = gx - sDR, gdy = gy - sUR;
                            double goalLen = std::sqrt(gdx*gdx + gdy*gdy);
                            const double SCOUT_STEP = 9.0;
                            double wx, wy;
                            if (goalLen <= SCOUT_STEP * BL) {
                                wx = gx; wy = gy;
                            } else {
                                wx = sDR + gdx / goalLen * SCOUT_STEP * BL;
                                wy = sUR + gdy / goalLen * SCOUT_STEP * BL;
                            }
                            nearTarget = (goalLen < 3.0 * BL);

                            // ★ 危险检测：目标12格+路径前8格避开狮/象
                            bool dangerNearby = false;
                            double pathDX = wx - sDR, pathDY = wy - sUR;
                            double pathLen = std::sqrt(pathDX*pathDX + pathDY*pathDY);
                            for (auto &r : info.resources) {
                                if (r.Cnt <= 0) continue;
                                if (r.Type != RESOURCE_LION && r.Type != RESOURCE_ELEPHANT) continue;
                                double lx = r.DR, ly = r.UR;
                                if (calDistance(wx, wy, lx, ly) < 12 * BL) {
                                    dangerNearby = true; break;
                                }
                                if (pathLen > 0.01) {
                                    double t = ((lx - sDR)*pathDX + (ly - sUR)*pathDY) / (pathLen*pathLen);
                                    if (t < 0 || t * pathLen > 8 * BL) continue;  // 只检查前8格，远端不管
                                    if (t > 1) t = 1;
                                    double nearX = sDR + t * pathDX;
                                    double nearY = sUR + t * pathDY;
                                    if (calDistance(lx, ly, nearX, nearY) < 1.5 * BL) {
                                        dangerNearby = true; break;
                                    }
                                }
                            }

                            if (nearTarget || dangerNearby) {
                                if (nearTarget) scoutDirsDone++;
                                scoutReturnTry = 0;  // 开始返回阶段，重置绕路计数
                                scoutPhase++;  // 到达或遇险→进入返回阶段
                                scoutCooldown = 10;
                            } else {
                                HumanMove(scout->SN, wx, wy);
                                scoutIssueDR = scout->DR; scoutIssueUR = scout->UR; scoutIssueFrame = frame;
                                scoutCooldown = 15;
                                scoutWalkTimer = 0;
                                scoutLegStartFrame = frame;
                            }
                    } else {
                        // 返回：回TC旁空地（多半径×多角度螺旋绕路，被石头堵时逐级放大半径重试）
                        double wx = 0, wy = 0;
                        scoutReturnPoint(scoutReturnTry, baseDR, baseUR, wx, wy);
                        nearTarget = (calDistance(sDR, sUR, wx, wy) < 7 * BL) ||
                                     (calDistance(sDR, sUR, baseDR, baseUR) < 8 * BL);

                        // ★ 返程也要检测路径前8格是否有狮/象
                        bool dangerNearby = false;
                        double pathDX = wx - sDR, pathDY = wy - sUR;
                        double pathLen = std::sqrt(pathDX*pathDX + pathDY*pathDY);
                        for (auto &r : info.resources) {
                            if (r.Cnt <= 0) continue;
                            if (r.Type != RESOURCE_LION && r.Type != RESOURCE_ELEPHANT) continue;
                            double lx = r.DR, ly = r.UR;
                            if (pathLen > 0.01) {
                                double t = ((lx - sDR)*pathDX + (ly - sUR)*pathDY) / (pathLen*pathLen);
                                if (t < 0 || t * pathLen > 8 * BL) continue;  // 只检查前8格
                                if (t > 1) t = 1;
                                double nearX = sDR + t * pathDX;
                                double nearY = sUR + t * pathDY;
                                if (calDistance(lx, ly, nearX, nearY) < 1.5 * BL) {
                                    dangerNearby = true; break;
                                }
                            }
                        }

                        if (nearTarget || dangerNearby) {
                            scoutReturnTry = 0;  // 成功回到TC旁→重置绕路计数
                            scoutPhase++;  // 回到TC或遇险→下一个外向方向
                            if (scoutPhase >= 16) scoutPhase = 20;  // 全部探完→结束探路回TC待命
                            scoutCooldown = 10;
                        } else {
                            HumanMove(scout->SN, wx, wy);
                            scoutIssueDR = scout->DR; scoutIssueUR = scout->UR; scoutIssueFrame = frame;
                            scoutCooldown = 15;
                            scoutWalkTimer = 0;
                            scoutLegStartFrame = frame;
                        }
                    }
                }
            }
            } // if(!fledThisFrame)
            }
        }

    // 探路完成（phase>=16或祭司死亡/不存在）后释放标记
    if (scoutPhase >= 16) {
        // 祭司探路完成，managePriest恢复常规逻辑
    }

    // 旧分配逻辑全部禁用：探路完成后直接返回，村民分配由 assignIdleSimple() 单独负责。
    return;

    // ====== 第一波前：全采浆果（固定1人采金，其余全员采食物，完全不伐木）======
    if (preW1) {
        for (auto &f : info.farmers) {
            if (f.FarmerSort != FARMERTYPE_FARMER) continue;
            if (frameAssigned.count(f.SN) || waveBlockers.count(f.SN) || buildingFarmerType.count(f.SN) || f.SN == scoutFarmerSN) continue;
            if (f.Resource > 0) continue;
            if (f.NowState != HUMAN_STATE_IDLE && !releasedBuilders.count(f.SN)) continue;
            if (assigned >= maxAssignThisFrame) break;

            // 固定1人采金（为铜器兵种+科技攒黄金）
            if (goldWorkers < 1) {
                if (tryAssignGold(&f)) {
                    frameAssigned.insert(f.SN);
                    goldWorkers++; assigned++; continue;
                }
            }

            // ★ 浆果优先（tryAssignFood内部：浆果→大象→农场→瞪羚，浆果满3人/丛才打瞪羚）★
            if (tryAssignFood(&f)) {
                frameAssigned.insert(f.SN);
                foodWorkers++; assigned++; continue;
            }
            // ★ 保底木工：食物/金矿无法分配时，才补足最低木工数量
            if (woodWorkers < woodFloor) {
                if (tryAssignWood(&f)) {
                    frameAssigned.insert(f.SN);
                    woodWorkers++; assigned++; continue;
                }
            }
            if (woodWorkers < woodFloor && tryAssignWood(&f)) {
                frameAssigned.insert(f.SN);
                woodWorkers++; assigned++; continue;
            }
        }

        // 木工保底：所有空闲已处理后仍不足，则从第二人以上的浆果工或猎人补足。
        if (woodWorkers < woodFloor) {
            pullWoodWorkers(woodFloor - woodWorkers);
        }

        // ★ 安全网：兜底分配（第一波前不伐木）★
        safetyNetAssign();
        lastChanceAssign();
        releasedBuilders.clear();
        return; // 第一波前不执行下面的再平衡
    }

    // ====== 第一波后~第二波前：铜器启动即军事优先（工具时代就能建兵营） ======
    if (postW1) {
        bool upgradeStarted = (state == UPGRADING || postBronze);
        bool rushMilitary = (upgradeStarted && frame < 16500 && !wave2Defeated);

        // ★ 第一波后伐木目标：提高伐木工人数（浆果耗尽加木建房种田）★
        int woodTarget = rushMilitary ? 6 : (postBronze ? 5 : 4);
        if (nearBushFood == 0) woodTarget = std::max(woodTarget, 6);
        woodTarget = std::max(woodTarget, woodFloor);
        woodTarget = std::min(woodTarget, 8);

        // ★ 调试：周期性输出伐木人数与可用树数量（定位"无人伐木"根因）★
        if (frame % 300 == 0) {
            int treeCnt = 0;
            for (auto &r : info.resources) if (r.Type == RESOURCE_TREE && r.Cnt > 0) treeCnt++;
            DebugText(QString("[WOOD f=%1] target=%2 cur=%3 idle=%4 trees=%5")
                .arg(frame).arg(woodTarget).arg(woodWorkers).arg(idleCount).arg(treeCnt));
        }

        for (auto &f : info.farmers) {
            if (f.FarmerSort != FARMERTYPE_FARMER) continue;
            if (frameAssigned.count(f.SN) || waveBlockers.count(f.SN) || buildingFarmerType.count(f.SN) || f.SN == scoutFarmerSN) continue;
            if (f.Resource > 0) continue;
            if (f.NowState != HUMAN_STATE_IDLE && !releasedBuilders.count(f.SN)) continue;
            if (assigned >= maxAssignThisFrame) break;

            // 伐木（2~5人）
            if (woodWorkers < woodTarget) {
                if (tryAssignWood(&f)) {
                    frameAssigned.insert(f.SN);
                    woodWorkers++; assigned++; continue;
                }
            }
            // 固定1人采金
            if (goldWorkers < 1) {
                if (tryAssignGold(&f)) {
                    frameAssigned.insert(f.SN);
                    goldWorkers++; assigned++; continue;
                }
            }
            // 食物（军事冲刺不种田）
            if (rushMilitary) {
                if (tryAssignFood(&f)) {
                    frameAssigned.insert(f.SN);
                    assigned++; continue;
                }
            } else {
                // 农场（1人1块）
                bool hasFarm = false;
                for (auto &b : info.buildings) {
                    if (b.Type != BUILDING_FARM || b.Percent < 100) continue;
                    if (frameFoodTargets.count(b.SN)) continue;
                    int onFarm = 0;
                    for (auto &other : info.farmers)
                        if (other.WorkObjectSN == b.SN) onFarm++;
                    if (onFarm >= 1) continue;
                    HumanAction(f.SN, b.SN);
                    frameFoodTargets.insert(b.SN);
                    frameAssigned.insert(f.SN);
                    assigned++;
                    hasFarm = true;
                    break;
                }
                if (hasFarm) continue;
                if (tryAssignFood(&f)) {
                    frameAssigned.insert(f.SN);
                    assigned++; continue;
                }
            }
            // 兜底：木头未满才继续伐木（保持≤5，不无限伐木）
            if (woodWorkers < woodTarget) {
                if (tryAssignWood(&f)) {
                    frameAssigned.insert(f.SN);
                    woodWorkers++; assigned++; continue;
                }
            }
        }

        // ★ 主动再平衡：空闲村民已分配完，但伐木人数仍不足目标（≥2）→ 直接从食物工抢人 ★
        if (woodWorkers < woodTarget) {
            int need = woodTarget - woodWorkers;
            // 第一遍：抢打猎的（瞪羚/大象，优先级最低，抢走损失小）
            for (auto &f : info.farmers) {
                if (need <= 0) break;
                if (f.FarmerSort != FARMERTYPE_FARMER) continue;
                if (waveBlockers.count(f.SN) || buildingFarmerType.count(f.SN) || f.SN == scoutFarmerSN) continue;
                if (f.NowState != HUMAN_STATE_WORKING || f.WorkObjectSN <= 0) continue;
                bool isHunt = false;
                for (auto &r : info.resources)
                    if (r.SN == f.WorkObjectSN && (r.Type == RESOURCE_GAZELLE || r.Type == RESOURCE_ELEPHANT)) { isHunt = true; break; }
                if (!isHunt) continue;
                if (tryAssignWood(&f)) { woodWorkers++; need--; }
            }
            // 第二遍：仍不够 → 抢采浆果的（每丛至少保留1人，避免浆果断供）
            if (need > 0) {
                for (auto &f : info.farmers) {
                    if (need <= 0) break;
                    if (f.FarmerSort != FARMERTYPE_FARMER) continue;
                    if (waveBlockers.count(f.SN) || buildingFarmerType.count(f.SN) || f.SN == scoutFarmerSN) continue;
                    if (f.NowState != HUMAN_STATE_WORKING || f.WorkObjectSN <= 0) continue;
                    bool isBush = false;
                    for (auto &r : info.resources)
                        if (r.SN == f.WorkObjectSN && r.Type == RESOURCE_BUSH) { isBush = true; break; }
                    if (!isBush) continue;
                    int onBush = 0;
                    for (auto &other : info.farmers)
                        if (other.WorkObjectSN == f.WorkObjectSN) onBush++;
                    if (onBush <= 1) continue;  // 每丛保留至少1人
                    if (tryAssignWood(&f)) { woodWorkers++; need--; }
                }
            }
        }

        // ★ 安全网：兜底分配，杜绝任何村民空闲 ★
        safetyNetAssign();
        lastChanceAssign();
        releasedBuilders.clear();
        return;
    }

    // ====== 第二波后：正常策略（铜器→军事） ======
    bool foodEmergency = (foodWorkers < farmerCount * 0.55 || info.Meat < 300);
    double woodRatio = (nearBushFood == 0) ? 0.55 : 0.15;
    int woodTarget = std::max(woodFloor, (int)(farmerCount * woodRatio));

    // ---- 前期：空闲农民自动帮忙建造未完成的建筑 ----
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (frameAssigned.count(f.SN) || waveBlockers.count(f.SN) || buildingFarmerType.count(f.SN) || f.SN == scoutFarmerSN) continue;
        if (f.Resource > 0) continue;
        if (f.NowState != HUMAN_STATE_IDLE && !releasedBuilders.count(f.SN)) continue;
        if (assigned >= maxAssignThisFrame) break;

        bool ok = false;

        // ★★★ 第一硬底线：食物最少 4 人（4+4=8，适配8农开局）★★★
        if (!ok && goldWorkers < MIN_GOLD_WORKERS) {
            ok = tryAssignGold(&f);
            if (ok) { frameAssigned.insert(f.SN); goldWorkers++; assigned++; continue; }
        }

        if (!ok && foodWorkers < MIN_FOOD_WORKERS) {
            ok = tryAssignFood(&f);
            if (ok) { frameAssigned.insert(f.SN); foodWorkers++; assigned++; continue; }
        }

        if (!ok && woodWorkers < woodTarget) {
            ok = tryAssignWood(&f);
            if (ok) { frameAssigned.insert(f.SN); woodWorkers++; assigned++; continue; }
        }

        if (foodEmergency) {
            ok = tryAssignFood(&f);
            if (ok) { frameAssigned.insert(f.SN); foodWorkers++; assigned++; continue; }
        }

        // ---- 木头：保底2人；浆果耗尽时提高到50%建房+种田 ----
        if (!ok && woodWorkers < woodTarget) {
            ok = tryAssignWood(&f);
            if (ok) { frameAssigned.insert(f.SN); woodWorkers++; assigned++; continue; }
        }

        // ---- 食物：60%（冲800升级费） ----
        if (!ok && foodWorkers < farmerCount * 0.60) {
            ok = tryAssignFood(&f);
            if (ok) { frameAssigned.insert(f.SN); foodWorkers++; assigned++; continue; }
        }
        // ---- 兜底：木头 > 食物 ----
        if (!ok) ok = tryAssignWood(&f);
        if (!ok) ok = tryAssignFood(&f);

        if (ok) {
            frameAssigned.insert(f.SN);
            assigned++;
        }
    }

    // ★★★ 强制再平衡：只在工人目标已消失时才转移（避免打断正在走路的工人导致卡死） ★★★
    bool buildingInProgress = false;
    for (auto &b : info.buildings) {
        if (b.Percent > 0 && b.Percent < 100) { buildingInProgress = true; break; }
    }
    if (idleCount == 0 && frame % 30 == 0 && !buildingInProgress && waveBlockers.empty() && buildingFarmerType.empty()) {
        // 辅助：检查工人当前目标是否仍有效（资源存在且未枯竭）
        auto targetValid = [&](tagFarmer& f) -> bool {
            if (f.WorkObjectSN <= 0) return false;
            if (f.NowState != HUMAN_STATE_WORKING && f.NowState != HUMAN_STATE_WALKING) return false;
            for (auto &r : info.resources)
                if (r.SN == f.WorkObjectSN && r.Cnt > 0) return true;
            for (auto &b : info.buildings)
                if (b.SN == f.WorkObjectSN) return true;
            return false;
        };
        // 1) 木头不足：从目标已失效的采石/采金工转移
        if (woodWorkers < MIN_WOOD_WORKERS) {
            for (auto &f : info.farmers) {
                if (f.FarmerSort != FARMERTYPE_FARMER) continue;
                if (f.Resource > 0) continue;
                if (f.NowState == HUMAN_STATE_WORKING &&
                    (f.ResourceSort == HUMAN_STONE || f.ResourceSort == HUMAN_GOLD) &&
                    !targetValid(f)) {
                    tryAssignWood(&f); break;
                }
            }
        }
        // 2) 食物不足或危机：从目标已失效的非食物工转移
        if (foodWorkers < MIN_FOOD_WORKERS || info.Meat < FOOD_CRITICAL) {
            for (auto &f : info.farmers) {
                if (f.FarmerSort != FARMERTYPE_FARMER) continue;
                if (f.Resource > 0) continue;
                if (f.NowState == HUMAN_STATE_WORKING &&
                    (f.ResourceSort == HUMAN_STONE || f.ResourceSort == HUMAN_GOLD) &&
                    !targetValid(f)) {
                    tryAssignFood(&f); break;
                }
            }
            if ((foodWorkers < MIN_FOOD_WORKERS || info.Meat < FOOD_CRITICAL)
                && woodWorkers > MIN_WOOD_WORKERS) {
                for (auto &f : info.farmers) {
                    if (f.FarmerSort != FARMERTYPE_FARMER) continue;
                    if (f.Resource > 0) continue;
                    if (f.NowState == HUMAN_STATE_WORKING && f.ResourceSort == HUMAN_WOOD &&
                        !targetValid(f)) {
                        tryAssignFood(&f); break;
                    }
                }
            }
        }
    }

    // ★ 木工保底：空闲已分配完仍不足目标，则从猎人/第二人以上的浆果工补足。
    if (woodWorkers < woodTarget) {
        pullWoodWorkers(woodTarget - woodWorkers);
    }

    // ★ 安全网：兜底分配，杜绝任何村民空闲（树始终存在）★
    safetyNetAssign();
    lastChanceAssign();
    releasedBuilders.clear();
}
}

void UsrAI::assignIdleSimple() {
    std::map<int,int> assignedBush;
    std::map<int,int> assignedGazelle;
    double BL = (double)BLOCKSIDELENGTH;
    const int woodTarget = 6;  // ★ 伐木工目标人数（提高以加快建房/箭塔/科技）
    auto center = findBuilding(BUILDING_CENTER);
    double tcDR = center ? (center->BlockDR + 1) * BL : 0;
    double tcUR = center ? (center->BlockUR + 1) * BL : 0;

    int goldWorkers = 0;
    int woodWorkers = 0;
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (f.ResourceSort == HUMAN_GOLD) goldWorkers++;
        if (f.ResourceSort == HUMAN_WOOD) woodWorkers++;
        if (f.WorkObjectSN > 0) {
            for (auto &r : info.resources)
                if (r.SN == f.WorkObjectSN) {
                    if (r.Type == RESOURCE_GOLD) goldWorkers++;
                    else if (r.Type == RESOURCE_TREE) woodWorkers++;
                    break;
                }
        }
    }

    if (info.Gold >= 200) {
        for (auto &f : info.farmers) {
            if (f.FarmerSort != FARMERTYPE_FARMER) continue;
            bool onGold = (f.ResourceSort == HUMAN_GOLD);
            if (!onGold && f.WorkObjectSN > 0) {
                for (auto &r : info.resources)
                    if (r.SN == f.WorkObjectSN && r.Type == RESOURCE_GOLD) { onGold = true; break; }
            }
            if (!onGold) continue;
            auto stone = findNearestResource(RESOURCE_STONE, f.DR, f.UR);
            if (stone) HumanAction(f.SN, stone->SN);
        }
    }

    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (f.Resource > 0) continue;
        if (f.NowState != HUMAN_STATE_IDLE) continue;
        if (waveBlockers.count(f.SN) || f.SN == scoutFarmerSN) continue;

        if (woodWorkers < woodTarget) {
            auto treeFirst = findNearestResource(RESOURCE_TREE, f.DR, f.UR);
            if (treeFirst) {
                HumanAction(f.SN, treeFirst->SN);
                woodWorkers++;
                continue;
            }
        }

        if (info.Gold < 200 && goldWorkers < 1) {
            auto gold = findNearestResource(RESOURCE_GOLD, f.DR, f.UR);
            if (gold) {
                HumanAction(f.SN, gold->SN);
                goldWorkers++;
                continue;
            }
        }

        tagResource* bestBush = nullptr;
        double bestBushScore = 1e12;
        for (auto &r : info.resources) {
            if (r.Type != RESOURCE_BUSH || r.Cnt <= 0) continue;
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > 20 * BL) continue;
            int onBush = 0;
            for (auto &other : info.farmers)
                if (other.WorkObjectSN == r.SN) onBush++;
            int totalOnBush = onBush + assignedBush[r.SN];
            if (totalOnBush >= 3) continue;
            double d = (r.DR - f.DR)*(r.DR - f.DR) + (r.UR - f.UR)*(r.UR - f.UR);
            double score = d * (1.0 + totalOnBush * 0.8);
            if (score < bestBushScore) { bestBushScore = score; bestBush = &r; }
        }
        if (bestBush) {
            HumanAction(f.SN, bestBush->SN);
            assignedBush[bestBush->SN]++;
            continue;
        }

        tagResource* bestGazelle = nullptr;
        double bestGazelleDist = 1e12;
        for (auto &r : info.resources) {
            if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) continue;
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > 40 * BL) continue;
            int onGazelle = 0;
            for (auto &other : info.farmers)
                if (other.WorkObjectSN == r.SN) onGazelle++;
            if (onGazelle + assignedGazelle[r.SN] >= 2) continue;
            double d = (r.DR - f.DR)*(r.DR - f.DR) + (r.UR - f.UR)*(r.UR - f.UR);
            if (d < bestGazelleDist) { bestGazelleDist = d; bestGazelle = &r; }
        }
        if (bestGazelle) {
            HumanAction(f.SN, bestGazelle->SN);
            assignedGazelle[bestGazelle->SN]++;
            continue;
        }

        auto elephant = findNearestResource(RESOURCE_ELEPHANT, f.DR, f.UR);
        if (elephant) {
            HumanAction(f.SN, elephant->SN);
            continue;
        }

        tagBuilding* farm = nullptr;
        for (auto &b : info.buildings) {
            if (b.Type != BUILDING_FARM || b.Percent < 100) continue;
            bool occupied = false;
            for (auto &other : info.farmers)
                if (other.WorkObjectSN == b.SN) { occupied = true; break; }
            if (!occupied) { farm = &b; break; }
        }
        if (farm) {
            HumanAction(f.SN, farm->SN);
            continue;
        }

        if (woodWorkers < woodTarget) {
            auto tree = findNearestResource(RESOURCE_TREE, f.DR, f.UR);
            if (tree) {
                HumanAction(f.SN, tree->SN);
                woodWorkers++;
            }
        }
    }
}

void UsrAI::manageHunting() {
    if (state >= DEFENSE_WAVE1 && state <= DEFENSE_WAVE3) return;
    if (state == COUNTERATTACK) return;

    double BL = (double)BLOCKSIDELENGTH;
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return;
    double tcDR = (center->BlockDR + 1) * BL;
    double tcUR = (center->BlockUR + 1) * BL;

    // 统计TC附近浆果总食物量（不用丛数，避免多丛快枯的浆果误判为"充足"）
    int bushFood = 0;
    for (auto &r : info.resources)
        if (r.Type == RESOURCE_BUSH && r.Cnt > 0)
            if (calDistance(tcDR, tcUR, r.DR, r.UR) < 30 * BL) bushFood += r.Cnt;
    // 清理狩猎组（农民不在攻击状态→已完成狩猎）★ 每帧都清，避免浆果>400时 stale 条目让村民被跳过
    for (auto it = huntingGroup.begin(); it != huntingGroup.end(); ) {
        bool still = false;
        for (auto &f : info.farmers)
            if (f.SN == *it && f.NowState == HUMAN_STATE_ATTACKING) { still = true; break; }
        if (!still) it = huntingGroup.erase(it); else ++it;
    }

    if (bushFood > 400) return;  // 浆果还够吃（>400食物），暂不主动打猎

    // 找TC附近最近的瞪羚（每只≤2人）
    tagResource* bestGazelle = nullptr;
    double bestDist = 1e12;
    for (auto &r : info.resources) {
        if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) continue;
        double d = calDistance(tcDR, tcUR, r.DR, r.UR);
        if (d >= 30 * BL) continue;
        int realCount = 0;
        for (auto &other : info.farmers)
            if (other.WorkObjectSN == r.SN) realCount++;
        if (realCount >= 2) continue;  // 每只≤2人
        if (d < bestDist) { bestDist = d; bestGazelle = &r; }
    }
    if (!bestGazelle) return;

    // ★ 只用空闲农民，不抢采浆果的 ★
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN) || waveBlockers.count(f.SN)) continue;
        if (huntingGroup.count(f.SN)) continue;  // 已分配过，不重复设
        if (f.Resource > 0) continue;
        if (f.NowState != HUMAN_STATE_IDLE) continue;  // 只等空闲

        HumanAction(f.SN, bestGazelle->SN);
        huntingGroup.insert(f.SN);
        return;  // 每帧最多分配1个猎人
    }
}

// ============================================================
// 科技升级（铜器后三级制：军事解锁 > 军事强化 > 经济）
// ============================================================
void UsrAI::manageTechUpgrade() {
    if (techCooldown > 0) return;
    if (info.Meat < FOOD_PAUSE_TECH_TRAIN) return;

    bool done = false;
    bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);

    // ★★★ 第一波前：除阔剑外禁止其他科技；所有食物优先爆农民 ★★★
    bool preW1 = (frame < WAVE1_TIME);
    // ★ 开局即研究箭塔科技（不等铜器/第3波/军事解锁）：有谷仓+50食物就研究，解锁箭塔建造 ★
    if (!towerTechResearched) {
        auto g = findBuilding(BUILDING_GRANARY);
        if (g && g->Project == BUILDING_GRANARY_ARROWTOWER) {
            towerTechResearched = true;  // 引擎已在研究中（已扣资源）
        } else if (g && g->Project == ACT_NULL && info.Meat >= 50) {
            BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWER);
            towerTechResearched = true;
            techCooldown = 25;
            return;
        }
    }

    // ★★★ 铜器前：除箭塔科技外禁止其他科技！每一粒食物都留给800升级费 ★★★
    if (!postBronze) return;

    // ★ 从游戏状态同步布尔值（检查建筑是否真在研究中，已扣资源）★
    // 不使用乐观标记！必须确认科技已经"付款"正在执行
    if (!broadswordResearched) {
        auto ac = findBuildingIncludingUnderConstruction(BUILDING_ARMYCAMP);
        if (ac && ac->Project == BUILDING_ARMYCAMP_UPGRADE_BROADSWORD) {
            broadswordResearched = true;  // 真的在研究了！
        } else if (broadswordQueued && ac && ac->Project == ACT_NULL) {
            // 已排队 → 建筑空闲 → 科技已完成
            broadswordResearched = true;
        }
    }
    if (!compositeBowResearched) {
        auto rng = findBuildingIncludingUnderConstruction(BUILDING_RANGE);
        if (rng && rng->Project == BUILDING_RANGE_UPGRADE_COMPOSITE_BOW) {
            compositeBowResearched = true;
        } else if (compositeBowQueued && rng && rng->Project == ACT_NULL) {
            compositeBowResearched = true;
        }
    }

    // ==================================================================
    // ★ TIER 1：军事解锁（阔剑优先→复合弓）★
    // ==================================================================

    // --- Army camp: broadsword first ---
    if (!done && !broadswordResearched && !broadswordQueued) {
        auto ac = findBuilding(BUILDING_ARMYCAMP);
        if (ac && ac->Project == ACT_NULL && info.Meat >= 140 && info.Gold >= 50) {
            BuildingAction(ac->SN, BUILDING_ARMYCAMP_UPGRADE_BROADSWORD);
            broadswordQueued = true;
            done = true;
        }
    }

    // --- Range: composite bow after broadsword (DEFENSE_PREP和W2期间跳过，省食物训兵) ---
    if (!preW1 && !done && !compositeBowResearched && !compositeBowQueued &&
        state != DEFENSE_PREP && state != DEFENSE_WAVE2) {
        auto r = findBuilding(BUILDING_RANGE);
        if (r && r->Project == ACT_NULL &&
            info.Meat >= 180 && info.Wood >= 100 && info.Gold >= 40) {
            BuildingAction(r->SN, BUILDING_RANGE_UPGRADE_COMPOSITE_BOW);
            compositeBowQueued = true;
            done = true;
        }
    }

    // ==================================================================
    // ★ 箭塔科技提前（已解除门槛）：铜器后立即可研究，不等第3波、不要求军事解锁 ★
    // ==================================================================
    if (!done && !towerTechResearched) {
        auto g = findBuilding(BUILDING_GRANARY);
        if (g && g->Project == ACT_NULL && info.Meat >= 50) {
            BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWER);
            towerTechResearched = true; done = true;
        }
    }
    if (!done && !bronzeTowerUpgraded && towerTechResearched) {
        auto g = findBuilding(BUILDING_GRANARY);
        if (g && g->Project == ACT_NULL && info.Meat >= 120 && info.Stone >= 50) {
            BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWE_UPGRADE);
            bronzeTowerUpgraded = true; done = true;
        }
    }

    // ==================================================================
    // ★ TIER 2+3 前置锁：军事解锁前不研究任何其他科技 ★
    // ==================================================================
    // Before wave 3, only military unlock techs may be researched.
    if (frame < WAVE3_TIME) {
        if (done) techCooldown = 25;
        return;
    }

    bool milUnlocked = (broadswordResearched || compositeBowResearched);
    if (!milUnlocked) {
        if (!done && !towerTechResearched) {
            auto g = findBuilding(BUILDING_GRANARY);
            if (g && g->Project == ACT_NULL && info.Meat >= 50) {
                BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWER);
                towerTechResearched = true; done = true;
            }
        }
        if (done) techCooldown = 25;
        return;
    }

    // ==================================================================
    // ★ TIER 2：军事强化 ★
    // ==================================================================

    // --- 仓库：工具使用（近战+2） ---
    if (!done && !useToolDone && info.Meat >= 100) {
        auto s = findBuilding(BUILDING_STOCK);
        if (s && s->Project == ACT_NULL) {
            BuildingAction(s->SN, BUILDING_STOCK_UPGRADE_USETOOL);
            useToolDone = true; done = true;
        }
    }

    // --- 仓库：步兵护甲（近战防御+2） ---
    if (!done && !infantryArmorDone && info.Meat >= 75) {
        auto s = findBuilding(BUILDING_STOCK);
        if (s && s->Project == ACT_NULL) {
            BuildingAction(s->SN, BUILDING_STOCK_UPGRADE_DEFENSE_INFANTRY);
            infantryArmorDone = true; done = true;
        }
    }

    // --- 仓库：弓兵护甲（远程防御+2） ---
    if (!done && !archerArmorDone && info.Meat >= 100) {
        auto s = findBuilding(BUILDING_STOCK);
        if (s && s->Project == ACT_NULL) {
            BuildingAction(s->SN, BUILDING_STOCK_UPGRADE_DEFENSE_ARCHER);
            archerArmorDone = true; done = true;
        }
    }

    // --- 谷仓：箭塔科技（解锁箭塔） ---
    if (!done && !towerTechResearched && info.Meat >= 50) {
        auto g = findBuilding(BUILDING_GRANARY);
        if (g && g->Project == ACT_NULL) {
            BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWER);
            towerTechResearched = true; done = true;
        }
    }

    // --- 谷仓：铜器箭塔升级 ---
    if (!done && !bronzeTowerUpgraded && towerTechResearched) {
        auto g = findBuilding(BUILDING_GRANARY);
        if (g && g->Project == ACT_NULL && info.Meat >= 120 && info.Stone >= 50) {
            BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWE_UPGRADE);
            bronzeTowerUpgraded = true; done = true;
        }
    }

    // ==================================================================
    // ★ TIER 3：经济科技 — 成本价即研究 ★
    // ==================================================================

    // --- 市场：木材加工（120食物+75木材） ---
    if (!done) {
        auto m = findBuilding(BUILDING_MARKET);
        if (m && m->Project == ACT_NULL && info.Meat >= 120 && info.Wood >= 75) {
            BuildingAction(m->SN, BUILDING_MARKET_WOOD_UPGRADE);
            done = true;
        }
    }

    // --- 市场：驯养动物（200食物+50木材） ---
    if (!done && !marketFarmUpgraded) {
        auto m = findBuilding(BUILDING_MARKET);
        if (m && m->Project == ACT_NULL && info.Meat >= 200 && info.Wood >= 50) {
            BuildingAction(m->SN, BUILDING_MARKET_FARM_UPGRADE);
            marketFarmUpgraded = true; done = true;
        }
    }

    // --- 市场：车轮（150食物+100木材） ---
    if (!done && !wheelResearched) {
        auto m = findBuilding(BUILDING_MARKET);
        if (m && m->Project == ACT_NULL && info.Meat >= 150 && info.Wood >= 100) {
            BuildingAction(m->SN, BUILDING_MARKET_WHEEL_UPGRADE);
            wheelResearched = true; done = true;
        }
    }

    // --- 市场：犁（250食物+75木材） ---
    if (!done && !marketPlowUpgraded) {
        auto m = findBuilding(BUILDING_MARKET);
        if (m && m->Project == ACT_NULL && info.Meat >= 250 && info.Wood >= 75) {
            BuildingAction(m->SN, BUILDING_MARKET_PLOW_UPGRADE);
            marketPlowUpgraded = true; done = true;
        }
    }

    // --- 市场：工艺（170食物+150木材） ---
    if (!done && !craftResearched) {
        auto m = findBuilding(BUILDING_MARKET);
        if (m && m->Project == ACT_NULL && info.Meat >= 170 && info.Wood >= 150) {
            BuildingAction(m->SN, BUILDING_MARKET_CRAFT_UPGRADE);
            craftResearched = true; done = true;
        }
    }

    if (done) techCooldown = 25;  // 铜器后加长冷却，1秒1科技
}

// ============================================================
// 军事管理（训练 + 箭塔防御 + 护祭司 + 自动作战）
// ============================================================
void UsrAI::manageMilitary() {
    bool isWarTime = (state >= DEFENSE_WAVE1 && state <= DEFENSE_WAVE3);
    bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
    int humanPop = info.farmers.size() + info.armies.size();
    double BL = (double)BLOCKSIDELENGTH;

    // ====== A. 军事训练 ======
    if (trainCooldown > 0) trainCooldown--;
    if (info.Meat >= FOOD_PAUSE_TECH_TRAIN && trainCooldown <= 0 && humanPop < info.Human_MaxNum) {
        bool trained = false;

        // --- 工具时代：不训练军队（攒食物升铜器） ---
        // (pre-Bronze: no training, save food)

        // --- 铜器时代：训练军事单位 ---
        if (postBronze) {
            // 优先级1：复合弓兵（远程DPS，PPT重点）
            if (!trained && compositeBowResearched) {
                auto r = findBuilding(BUILDING_RANGE);
                if (r && r->Project == ACT_NULL &&
                    info.Meat >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_FOOD &&
                    info.Gold >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_GOLD) {
                    BuildingAction(r->SN, BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN);
                    trained = true;
                }
            }

            // 优先级2：阔剑兵（近战肉盾）
            if (!trained && broadswordResearched) {
                auto ac = findBuilding(BUILDING_ARMYCAMP);
                if (ac && ac->Project == ACT_NULL &&
                    info.Meat >= BUILDING_ARMYCAMP_CREATE_BROADSWORD_FOOD &&
                    info.Gold >= BUILDING_ARMYCAMP_CREATE_BROADSWORD_GOLD) {
                    BuildingAction(ac->SN, BUILDING_ARMYCAMP_CREATE_BROADSWORD);
                    trained = true;
                }
            }

            // 优先级2.5：PREP/W1/W2/W3期间训练廉价兵种（弓兵→投石兵→棍棒兵）
            bool canTrainCheap = (isWarTime || state == DEFENSE_PREP);
            if (!trained && canTrainCheap && info.Meat >= 60) {
                // 投石兵（兵营）：40食物+10石头，24秒
                if (!trained) {
                    auto ac = findBuilding(BUILDING_ARMYCAMP);
                    if (ac && ac->Project == ACT_NULL &&
                        info.Meat >= BUILDING_ARMYCAMP_CREATE_SLINGER_FOOD &&
                        info.Stone >= BUILDING_ARMYCAMP_CREATE_SLINGER_STONE) {
                        BuildingAction(ac->SN, BUILDING_ARMYCAMP_CREATE_SLINGER);
                        trained = true;
                    }
                }
                // 棍棒兵（兵营）：50食物，27秒
                if (!trained) {
                    auto ac = findBuilding(BUILDING_ARMYCAMP);
                    if (ac && ac->Project == ACT_NULL &&
                        info.Meat >= BUILDING_ARMYCAMP_CREATE_CLUBMAN_FOOD) {
                        BuildingAction(ac->SN, BUILDING_ARMYCAMP_CREATE_CLUBMAN);
                        trained = true;
                    }
                }
            }

            // 优先级3：方阵兵（强力近战，学院）
            if (!trained && academyBuilt) {
                auto col = findBuilding(BUILDING_COLLAGE);
                if (col && col->Project == ACT_NULL &&
                    info.Meat >= BUILDING_COLLAGE_CREATE_HOPLITE_FOOD &&
                    info.Gold >= BUILDING_COLLAGE_CREATE_HOPLITE_GOLD) {
                    BuildingAction(col->SN, BUILDING_COLLAGE_CREATE_HOPLITE);
                    trained = true;
                }
            }

            // 优先级4：骑兵（冲击远程部队）
            if (!trained) {
                auto st = findBuilding(BUILDING_STABLE);
                if (st && st->Project == ACT_NULL &&
                    info.Meat >= BUILDING_STABLE_CREATE_CAVALRY_FOOD &&
                    info.Gold >= BUILDING_STABLE_CREATE_CAVALRY_GOLD) {
                    BuildingAction(st->SN, BUILDING_STABLE_CREATE_CAVALRY);
                    trained = true;
                }
            }

            // 侦察骑兵（反攻阶段需要探路，只造1个）
            if (!trained && !scoutBuilt && state >= COUNTERATTACK) {
                auto st = findBuilding(BUILDING_STABLE);
                if (st && st->Project == ACT_NULL &&
                    info.Meat >= BUILDING_STABLE_CREATE_SCOUT_FOOD) {
                    BuildingAction(st->SN, BUILDING_STABLE_CREATE_SCOUT);
                    scoutBuilt = true; trained = true;
                }
            }
        }

        if (trained) trainCooldown = 15;
    }

    // ====== B. 箭塔防御：所有波次手动指挥箭塔攻击进入射程的敌人 ======
    if (isWarTime) {
        for (auto &tower : info.buildings) {
            if (tower.Type != BUILDING_ARROWTOWER || tower.Percent < 100) continue;
            if (tower.Project != ACT_NULL) continue; // 已在攻击
            // 找箭塔射程内的最近敌人
            double tDR = (tower.BlockDR + 1) * BL;
            double tUR = (tower.BlockUR + 1) * BL;
            int target = findNearestEnemySN(tDR, tUR, 8 * BL); // 箭塔射程约8格
            if (target >= 0) {
                BuildingAction(tower.SN, target);
            }
        }
    }

    // ====== C. 获取祭司和TC位置 ======
    double priestDR = 0, priestUR = 0;
    double priestBlood = 0, priestMaxBlood = 0;
    bool priestAlive = false;
    for (auto &a : info.armies) {
        if (a.SN == priestSN) {
            priestDR = a.DR; priestUR = a.UR;
            priestBlood = a.Blood; priestMaxBlood = a.MaxBlood;
            priestAlive = true; break;
        }
    }

    auto center = findBuilding(BUILDING_CENTER);
    double centerDR = 0, centerUR = 0;
    if (center) {
        centerDR = (center->BlockDR + 1) * BL;
        centerUR = (center->BlockUR + 1) * BL;
    }

    auto enemyNearTC = [&](int enemySN) -> bool {
        if (!center) return false;
        for (auto &e : info.enemy_armies)
            if (e.SN == enemySN)
                return calDistance(centerDR, centerUR, e.DR, e.UR) <= 25 * BL;
        for (auto &e : info.enemy_farmers)
            if (e.SN == enemySN)
                return calDistance(centerDR, centerUR, e.DR, e.UR) <= 25 * BL;
        return false;
    };

    // ====== D. 空闲士兵分配攻击指令 ======
    int maxAttackCmds = isWarTime ? 8 : 4;
    int attackCmds = 0;

    // 检测祭司是否受威胁
    bool priestThreatened = false;
    int priestEnemySN2 = -1;
    if (priestAlive) {
        priestEnemySN2 = findNearestEnemySN(priestDR, priestUR, 15 * BL);
        priestThreatened = (priestEnemySN2 >= 0);
    }

    // --- D0: 士兵——祭司危险优先保护 / W2+主动前出拦截 ---
    if (priestAlive && center) {
        for (auto &a : info.armies) {
            if (a.NowState != HUMAN_STATE_IDLE) continue;
            if (a.Sort == AT_PRIEST) continue;
            if (attackCmds >= maxAttackCmds) break;

            // 祭司受威胁→最高优先保护
            if (priestThreatened) {
                if (enemyNearTC(priestEnemySN2)) {
                    HumanAction(a.SN, priestEnemySN2);
                    attackCmds++;
                }
                continue;
            }

            // 找正在攻击祭司的敌人
            int attackingPriest = -1;
            for (auto &e : info.enemy_armies) {
                if (e.WorkObjectSN == priestSN) { attackingPriest = e.SN; break; }
            }
            if (attackingPriest >= 0) {
                if (enemyNearTC(attackingPriest)) {
                    HumanAction(a.SN, attackingPriest);
                    attackCmds++;
                }
                continue;
            }

            // W2/W3：主动前出拦截远处敌人
            if (state >= DEFENSE_WAVE2) {
                int farEnemy = findNearestEnemySN(centerDR, centerUR, 25 * BL);
                if (farEnemy >= 0) {
                    HumanAction(a.SN, farEnemy);
                    attackCmds++;
                    continue;
                }
                // 没找到敌人→回TC
                double distTC = calDistance(a.DR, a.UR, centerDR, centerUR);
                if (distTC > 6 * BL) {
                    // ★ 回TC旁可达空地（不再用TC建筑中心centerDR/centerUR——中心被建筑占着不可达，
                    //   单位永远走不到→距离恒>阈值→每帧重发同一坐标刷屏、单位原地不动。刀斧兵/弓箭手等通用）
                    {
                        int atry = armyReturnTry[a.SN];
                        int aang = atry % 8;
                        int arad = atry / 8; if (arad > 2) arad = 2;
                        const int ARADII[3] = {4, 7, 10};
                        double ara = (double)aang * 3.141592653589793 / 4.0;
                        double aR = ARADII[arad] * BL;
                        double atx = centerDR + std::cos(ara) * aR;
                        double aty = centerUR + std::sin(ara) * aR;
                        atx = max(0.0, min((double)MAP_L * BL, atx));
                        aty = max(0.0, min((double)MAP_U * BL, aty));
                        HumanMove(a.SN, atx, aty);
                        // 卡死检测：idle 且上次下发后几乎没动→换下一角度/半径重试，避免同一不可达点死循环
                        if (armyIssueFrame.count(a.SN) && a.NowState == HUMAN_STATE_IDLE &&
                            frame - armyIssueFrame[a.SN] > 45 &&
                            calDistance(a.DR, a.UR, armyIssueDR[a.SN], armyIssueUR[a.SN]) < 1.0 * BL) {
                            armyReturnTry[a.SN]++;
                        }
                        armyIssueDR[a.SN] = a.DR; armyIssueUR[a.SN] = a.UR; armyIssueFrame[a.SN] = frame;
                    }
                }
                attackCmds++;
                continue;
            }

            // W1/非战时：就近搜敌攻击
            int nearbyEnemy = findNearestEnemySN(centerDR, centerUR, 25 * BL);
            if (nearbyEnemy >= 0) {
                HumanAction(a.SN, nearbyEnemy);
            } else {
                double distToTC = calDistance(a.DR, a.UR, centerDR, centerUR);
                if (distToTC > 8 * BL) {
                    // ★ 回TC旁可达空地（不再用TC建筑中心centerDR/centerUR——中心被建筑占着不可达，
                    //   单位永远走不到→距离恒>阈值→每帧重发同一坐标刷屏、单位原地不动。刀斧兵/弓箭手等通用）
                    {
                        int atry = armyReturnTry[a.SN];
                        int aang = atry % 8;
                        int arad = atry / 8; if (arad > 2) arad = 2;
                        const int ARADII[3] = {4, 7, 10};
                        double ara = (double)aang * 3.141592653589793 / 4.0;
                        double aR = ARADII[arad] * BL;
                        double atx = centerDR + std::cos(ara) * aR;
                        double aty = centerUR + std::sin(ara) * aR;
                        atx = max(0.0, min((double)MAP_L * BL, atx));
                        aty = max(0.0, min((double)MAP_U * BL, aty));
                        HumanMove(a.SN, atx, aty);
                        // 卡死检测：idle 且上次下发后几乎没动→换下一角度/半径重试，避免同一不可达点死循环
                        if (armyIssueFrame.count(a.SN) && a.NowState == HUMAN_STATE_IDLE &&
                            frame - armyIssueFrame[a.SN] > 45 &&
                            calDistance(a.DR, a.UR, armyIssueDR[a.SN], armyIssueUR[a.SN]) < 1.0 * BL) {
                            armyReturnTry[a.SN]++;
                        }
                        armyIssueDR[a.SN] = a.DR; armyIssueUR[a.SN] = a.UR; armyIssueFrame[a.SN] = frame;
                    }
                }
            }
            attackCmds++;
        }
    }

    // --- D1: 波次期间TC附近有敌人时优先清除 ---
    if (isWarTime && center && attackCmds < maxAttackCmds) {
        int tcEnemy = findNearestEnemySN(centerDR, centerUR, 25 * BL);
        if (tcEnemy >= 0) {
            for (auto &a : info.armies) {
                if (a.Sort == AT_PRIEST) continue;
                if (a.NowState != HUMAN_STATE_IDLE) continue;
                if (attackCmds >= maxAttackCmds) break;
                HumanAction(a.SN, tcEnemy);
                attackCmds++;
            }
        }
    }

    // --- D2: 每个空闲士兵搜敌攻击 ---
    for (auto &a : info.armies) {
        if (a.Sort == AT_PRIEST) continue;
        if (a.NowState != HUMAN_STATE_IDLE) continue;
        if (attackCmds >= maxAttackCmds) break;

        bool isRanged = (a.Sort == AT_BOWMAN || a.Sort == AT_COMPOSITE_BOWMAN ||
                         a.Sort == AT_CHARIOT_ARCHER || a.Sort == AT_SLINGER);
        double searchRange = isRanged ? 10 : 6;
        searchRange *= BL;

        int enemySN = findNearestEnemySN(a.DR, a.UR, searchRange);
        if (enemySN < 0) continue;

        // 校验：敌人目标必须在防御圈内
        double eDR = 0, eUR = 0;
        bool foundEnemy = false;
        for (auto &e : info.enemy_armies) {
            if (e.SN == enemySN) { eDR = e.DR; eUR = e.UR; foundEnemy = true; break; }
        }
        if (!foundEnemy) {
            for (auto &e : info.enemy_farmers) {
                if (e.SN == enemySN) { eDR = e.DR; eUR = e.UR; foundEnemy = true; break; }
            }
        }
        if (!foundEnemy) continue;

        bool inDefenseZone = false;
        if (priestAlive && calDistance(priestDR, priestUR, eDR, eUR) <= 25 * BL)
            inDefenseZone = true;
        if (!inDefenseZone && center && calDistance(centerDR, centerUR, eDR, eUR) <= 25 * BL)
            inDefenseZone = true;
        if (!inDefenseZone) continue;

        HumanAction(a.SN, enemySN);
        attackCmds++;
    }
}

// ============================================================
// 反攻管理（PPT策略：侦察→集结→推进→祭司转化武器厂）
// ============================================================
void UsrAI::manageCarriedResources() {
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (f.Resource <= 0) {
            depositFarmers.erase(f.SN);
            depositStartFrame.erase(f.SN);
            continue;
        }
        if (f.NowState != HUMAN_STATE_IDLE) {
            depositFarmers.erase(f.SN);
            depositStartFrame.erase(f.SN);
            continue;
        }
        if (depositFarmers.count(f.SN)) {
            if (frame - depositStartFrame[f.SN] < 30) continue;
            depositStartFrame[f.SN] = frame;
        }

        tagBuilding* depot = nullptr;
        for (auto &b : info.buildings) {
            if (b.Percent != 100) continue;
            if (b.Type == BUILDING_CENTER) { depot = &b; break; }
            if (f.ResourceSort == HUMAN_GRANARYFOOD && b.Type == BUILDING_GRANARY) { depot = &b; break; }
            if (f.ResourceSort != HUMAN_GRANARYFOOD && f.ResourceSort != HUMAN_DOCKFOOD &&
                b.Type == BUILDING_STOCK) { depot = &b; break; }
        }
        if (depot) {
            HumanAction(f.SN, depot->SN);
            depositFarmers.insert(f.SN);
            depositStartFrame[f.SN] = frame;
        }
    }
}

void UsrAI::manageFirstWaveDefense() {
    if (state < DEFENSE_WAVE1 || state > DEFENSE_WAVE3) {
        waveBlockers.clear();
        return;
    }
    if (countAllMilitary() >= 6) {
        waveBlockers.clear();
        return;
    }

    tagArmy* priest = nullptr;
    for (auto &a : info.armies) {
        if (a.Sort == AT_PRIEST) { priest = &a; break; }
    }
    if (!priest) {
        waveBlockers.clear();
        return;
    }

    double BL = (double)BLOCKSIDELENGTH;
    double refDR = priest->DR, refUR = priest->UR;
    double targetRange = 25 * BL;
    int axeSN = -1, archerSN = -1;
    double axeBest = 1e18, archerBest = 1e18;
    for (auto &e : info.enemy_armies) {
        double d = calDistance(refDR, refUR, e.DR, e.UR);
        if (d > targetRange) continue;
        if (e.Sort == AT_SWORDSMAN) {
            if (d < axeBest) { axeBest = d; axeSN = e.SN; }
        } else if (e.Sort == AT_BOWMAN || e.Sort == AT_COMPOSITE_BOWMAN ||
                   e.Sort == AT_SLINGER) {
            if (d < archerBest) { archerBest = d; archerSN = e.SN; }
        }
    }

    // Only defend enemies already near the priest/base.
    if (axeSN < 0 && archerSN < 0) {
        int fallback = findNearestEnemySN(refDR, refUR, 25 * BL);
        if (fallback < 0) {
            waveBlockers.clear();
            return;
        }
        for (auto &e : info.enemy_armies) {
            if (e.SN != fallback) continue;
            if (e.Sort == AT_CHARIOT_ARCHER) {
                waveBlockers.clear();
                return;
            }
            axeSN = fallback;
            break;
        }
        if (axeSN < 0) {
            waveBlockers.clear();
            return;
        }
    }

    int axeSlots = (axeSN >= 0) ? 4 : 0;
    int archerSlots = (archerSN >= 0) ? 2 : 0;
    std::set<int> stillAlive;

    for (int sn : waveBlockers) {
        if (axeSlots + archerSlots == 0) break;
        tagFarmer* f = nullptr;
        for (auto &x : info.farmers) {
            if (x.SN == sn) { f = &x; break; }
        }
        if (!f || f->Blood <= 0) continue;
        if (buildingFarmerType.count(sn)) continue;
        if (f->Resource > 0) continue;
        if (axeSlots > 0 && axeSN >= 0) {
            HumanAction(sn, axeSN);
            axeSlots--;
            stillAlive.insert(sn);
        } else if (archerSlots > 0 && archerSN >= 0) {
            HumanAction(sn, archerSN);
            archerSlots--;
            stillAlive.insert(sn);
        }
    }

    for (int pass = 0; pass < 2 && axeSlots + archerSlots > 0; ++pass) {
        for (auto &f : info.farmers) {
            if (axeSlots + archerSlots == 0) break;
            if (f.FarmerSort != FARMERTYPE_FARMER) continue;
            if (stillAlive.count(f.SN)) continue;
            if (buildingFarmerType.count(f.SN)) continue;
            if (f.Resource > 0) continue;
            double d = calDistance(f.DR, f.UR, refDR, refUR);
            if (pass == 0 && d > 15 * BL) continue;
            if (pass == 1 && d > 30 * BL) continue;
            if (axeSlots > 0 && axeSN >= 0) {
                HumanAction(f.SN, axeSN);
                axeSlots--;
                stillAlive.insert(f.SN);
            } else if (archerSlots > 0 && archerSN >= 0) {
                HumanAction(f.SN, archerSN);
                archerSlots--;
                stillAlive.insert(f.SN);
            }
        }
    }

    waveBlockers = stillAlive;
}
void UsrAI::manageCounterAttack() {
    double BL = (double)BLOCKSIDELENGTH;

    // ====== 1. 侦察阶段：寻找敌方武器厂 ======
    if (enemySiegeSN == -1) {
        auto siege = findEnemyBuilding(BUILDING_SIEGE);
        if (siege) {
            enemySiegeSN = siege->SN;
            rallyDR = siege->BlockDR;
            rallyUR = siege->BlockUR;
            DebugText(QString(">> Enemy Siege Workshop found at (%1,%2)!").arg(rallyDR).arg(rallyUR));
        }
    }

    // 如果还没发现武器厂，用侦察骑兵探索
    if (enemySiegeSN == -1) {
        // 尝试用已有军队向地图未知区域探索
        for (auto &a : info.armies) {
            if (a.Sort == AT_SCOUT && a.NowState == HUMAN_STATE_IDLE) {
                // 侦察骑兵向地图中部探索
                HumanMove(a.SN, 128 * BL, 128 * BL);
                break;
            }
        }
        // 还没有侦察骑兵就造一个
        if (!scoutBuilt) {
            auto st = findBuilding(BUILDING_STABLE);
            if (st && st->Project == ACT_NULL && info.Meat >= BUILDING_STABLE_CREATE_SCOUT_FOOD) {
                BuildingAction(st->SN, BUILDING_STABLE_CREATE_SCOUT);
                scoutBuilt = true;
            }
        }
        // 没找到就继续找
        return;
    }

    auto siege = findEnemyBuilding(BUILDING_SIEGE);
    if (!siege) {
        // 检查是否已经胜利
        bool foundEnemySiege = false;
        for (auto &b : info.enemy_buildings) {
            if (b.Type == BUILDING_SIEGE) { foundEnemySiege = true; break; }
        }
        if (!foundEnemySiege) {
            for (auto &b : info.buildings) {
                if (b.Type == BUILDING_SIEGE) {
                    state = VICTORY;
                    DebugText("!!! VICTORY! Siege Workshop converted !!!");
                    return;
                }
            }
        }
        return;
    }

    double sDR = (siege->BlockDR + 1) * BL;
    double sUR = (siege->BlockUR + 1) * BL;
    auto center = findBuilding(BUILDING_CENTER);

    // ====== 2. 集结与推进 ======
    int marchCmds = 0;
    tagArmy* priest = nullptr;
    for (auto &a : info.armies) {
        if (a.Sort == AT_PRIEST) { priest = &a; continue; }
        if (a.NowState != HUMAN_STATE_IDLE) continue;
        if (marchCmds >= 8) break;

        // 优先攻击路径上的敌人
        int enemySN = findNearestEnemySN(a.DR, a.UR, 15 * BL);
        if (enemySN >= 0) {
            HumanAction(a.SN, enemySN);
        } else {
            // 向武器厂推进
            HumanMove(a.SN, sDR, sUR);
        }
        marchCmds++;
    }

    // ====== 3. 祭司安全推进 ======
    if (priest && priest->NowState != HUMAN_STATE_ATTACKING && priest->NowState != HUMAN_STATE_WORKING) {
        double pDist = calDistance(priest->DR, priest->UR, sDR, sUR);

        // 检查祭司周围是否有敌人
        int priestEnemy = findNearestEnemySN(priest->DR, priest->UR, 12 * BL);

        if (priestEnemy >= 0) {
            // 有敌人！撤退
            if (center && priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0) {
                double retreatDR = (center->BlockDR + 1) * BL;
                double retreatUR = (center->BlockUR + 1) * BL;
                HumanMove(priestSN, retreatDR, retreatUR);
                priestMoveCooldown = 40;
            }
        } else if (pDist < 12 * BL && priest->ConvertCooldown <= 0 && priestMoveCooldown <= 0) {
            // 在感化范围内→感化武器厂！
            HumanAction(priestSN, siege->SN);
            priestMoveCooldown = 120;
            DebugText(">> Priest converting Siege Workshop!");
        } else if (priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0) {
            // 安全，向武器厂后方推进（保持距离）
            double targetDR = sDR - 5 * BL;
            double targetUR = sUR - 5 * BL;
            HumanMove(priestSN, targetDR, targetUR);
            priestMoveCooldown = 30;
        }
    }

    // ====== 4. 后方支援：继续造兵补充伤亡 ======
    // (已在manageMilitary中持续进行)
}

// ============================================================
// 失败检查
// ============================================================
void UsrAI::checkDefeat() {
    // 检查祭司
    bool priestAlive = false;
    for (auto &a : info.armies) {
        if (a.Sort == AT_PRIEST) { priestAlive = true; break; }
    }
    if (!priestAlive && priestSN != -1) {
        state = DEFEAT;
        DebugText("!!! DEFEAT: Priest killed !!!");
        return;
    }

    // 检查市镇中心
    bool tcAlive = false;
    for (auto &b : info.buildings) {
        if (b.Type == BUILDING_CENTER) { tcAlive = true; break; }
    }
    if (!tcAlive) {
        state = DEFEAT;
        DebugText("!!! DEFEAT: Town Center destroyed !!!");
        return;
    }
}

// ============================================================
// 调试输出（每150帧输出一次）
// ============================================================
void UsrAI::doDebugOutput() {
    debugTimer++;
    if (debugTimer % 150 != 0) return;

    QString s;
    switch (state) {
    case INIT: s="INIT"; break;
    case EARLY_ECONOMY: s="ECO"; break;
    case UPGRADING: s="UPG"; break;
    case DEFENSE_PREP: s="PREP"; break;
    case DEFENSE_WAVE1: s="W1"; break;
    case DEFENSE_WAVE2: s="W2"; break;
    case DEFENSE_WAVE3: s="W3"; break;
    case COUNTERATTACK: s="ATK"; break;
    case VICTORY: s="WIN"; break;
    case DEFEAT: s="LOSE"; break;
    }

    int fCount = 0, idleF = 0, idleCarry = 0, walkingF = 0;
    int workingF = 0, attackingF = 0;
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        fCount++;
        if (f.NowState == HUMAN_STATE_IDLE) {
            idleF++;
            if (f.Resource > 0) idleCarry++;
        } else if (f.NowState == HUMAN_STATE_WALKING) {
            walkingF++;
        } else if (f.NowState == HUMAN_STATE_WORKING) {
            workingF++;
        } else if (f.NowState == HUMAN_STATE_ATTACKING) {
            attackingF++;
        }
    }

    int mil = countAllMilitary();
    int eCount = info.enemy_armies.size() + info.enemy_farmers.size();

    DebugText(QString("[%1] %2 | Fd:%3 Wd:%4 St:%5 Gd:%6 | Frm:%7 Idle:%8(Carry:%9) Walk:%10 Work:%11 Atk:%12 | Mil:%13 E:%14")
        .arg(frame).arg(s)
        .arg((int)info.Meat).arg((int)info.Wood).arg((int)info.Stone).arg((int)info.Gold)
        .arg(fCount).arg(idleF).arg(idleCarry).arg(walkingF).arg(workingF).arg(attackingF)
        .arg(mil).arg(eCount));
}

// ============================================================
// 辅助函数实现
// ============================================================

tagFarmer* UsrAI::findIdleFarmer() {
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN) || f.SN == scoutFarmerSN) continue;
        if (f.NowState == HUMAN_STATE_IDLE && f.Resource <= 0) return &f;
    }
    return nullptr;
}

tagFarmer* UsrAI::findAnyFarmer() {
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN) || waveBlockers.count(f.SN)) continue;
        if (f.Resource > 0) continue;
        if (f.NowState == HUMAN_STATE_WORKING && f.ResourceSort == HUMAN_STONE) return &f;
    }
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN) || waveBlockers.count(f.SN)) continue;
        if (f.Resource > 0) continue;
        if (f.NowState == HUMAN_STATE_WORKING && f.ResourceSort == HUMAN_GOLD) return &f;
    }
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN) || waveBlockers.count(f.SN)) continue;
        if (f.Resource > 0) continue;
        if (f.NowState == HUMAN_STATE_WORKING && f.ResourceSort == HUMAN_WOOD) return &f;
    }
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN) || waveBlockers.count(f.SN)) continue;
        if (f.Resource > 0) continue;
        if (f.NowState != HUMAN_STATE_IDLE && f.NowState != HUMAN_STATE_ATTACKING) return &f;
    }
    return nullptr;
}
tagBuilding* UsrAI::findBuilding(int type) {
    for (auto &b : info.buildings)
        if (b.Type == type && b.Percent == 100) return &b;
    return nullptr;
}

tagBuilding* UsrAI::findBuildingIncludingUnderConstruction(int type) {
    for (auto &b : info.buildings)
        if (b.Type == type) return &b;
    return nullptr;
}

tagBuilding* UsrAI::findEnemyBuilding(int type) {
    for (auto &b : info.enemy_buildings)
        if (b.Type == type) return &b;
    return nullptr;
}

tagResource* UsrAI::findNearestResource(int type, double dr, double ur) {
    tagResource* best = nullptr;
    double bestDist = 1e12;
    for (auto &r : info.resources) {
        if (r.Type == type && r.Cnt > 0) {
            double d = (r.DR - dr) * (r.DR - dr) + (r.UR - ur) * (r.UR - ur);
            if (d < bestDist) { bestDist = d; best = &r; }
        }
    }
    return best;
}

tagResource* UsrAI::findNearestResourceAny(const std::vector<int>& types, double dr, double ur) {
    tagResource* best = nullptr;
    double bestDist = 1e12;
    for (auto &r : info.resources) {
        for (int t : types) {
            if (r.Type == t && r.Cnt > 0) {
                double d = (r.DR - dr) * (r.DR - dr) + (r.UR - ur) * (r.UR - ur);
                if (d < bestDist) { bestDist = d; best = &r; }
            }
        }
    }
    return best;
}

tagArmy* UsrAI::findMyArmy(int sort, bool idleOnly) {
    for (auto &a : info.armies)
        if (a.Sort == sort && (!idleOnly || a.NowState == HUMAN_STATE_IDLE)) return &a;
    return nullptr;
}

int UsrAI::findNearestEnemySN(double dr, double ur, double range) {
    int bestSN = -1;
    double bestDist = range * range;
    for (const auto &e : info.enemy_armies) {
        double d = (e.DR - dr) * (e.DR - dr) + (e.UR - ur) * (e.UR - ur);
        if (d < bestDist) { bestDist = d; bestSN = e.SN; }
    }
    for (const auto &e : info.enemy_farmers) {
        double d = (e.DR - dr) * (e.DR - dr) + (e.UR - ur) * (e.UR - ur);
        if (d < bestDist) { bestDist = d; bestSN = e.SN; }
    }
    return bestSN;
}

int UsrAI::countBuildings(int type) {
    int cnt = 0;
    for (auto &b : info.buildings) if (b.Type == type && b.Percent == 100) cnt++;
    return cnt;
}

int UsrAI::countBuildingsAll(int type) {
    int cnt = 0;
    for (auto &b : info.buildings) if (b.Type == type && !deadBuildings.count(b.SN)) cnt++;
    return cnt;
}

int UsrAI::countUnits(int sort) {
    int cnt = 0;
    for (auto &a : info.armies) if (a.Sort == sort) cnt++;
    return cnt;
}

int UsrAI::countAllMilitary() {
    int cnt = 0;
    for (auto &a : info.armies) if (a.Sort != AT_PRIEST) cnt++;
    return cnt;
}

int UsrAI::countFarmersByState(int state) {
    int cnt = 0;
    for (auto &f : info.farmers) if (f.NowState == state) cnt++;
    return cnt;
}

bool UsrAI::isPositionFree(int blockDR, int blockUR, int size) {
    if (blockDR < 0 || blockUR < 0 || blockDR + size > MAP_L || blockUR + size > MAP_U)
        return false;
    if (info.theMap == nullptr) return false;

    // 地形检查：草地 + 高度一致
    int firstHeight = (*info.theMap)[blockDR][blockUR].height;
    for (int i = blockDR; i < blockDR + size; ++i) {
        for (int j = blockUR; j < blockUR + size; ++j) {
            auto &t = (*info.theMap)[i][j];
            if (t.type != MAPPATTERN_GRASS) return false;
            if (t.height < 0) return false;
            if (t.height != firstHeight) return false;
        }
    }

    // 我方建筑重叠检查
    for (auto &b : info.buildings) {
        int bSize = (b.Type == BUILDING_HOME || b.Type == BUILDING_ARROWTOWER) ? 2 : 3;
        for (int i = blockDR; i < blockDR + size; ++i)
            for (int j = blockUR; j < blockUR + size; ++j)
                if (i >= b.BlockDR && i < b.BlockDR + bSize &&
                    j >= b.BlockUR && j < b.BlockUR + bSize) return false;
    }

    // 敌方建筑重叠检查（已探索区域内的敌方建筑也会阻挡建造）
    for (auto &b : info.enemy_buildings) {
        int bSize = (b.Type == BUILDING_HOME || b.Type == BUILDING_ARROWTOWER) ? 2 : 3;
        for (int i = blockDR; i < blockDR + size; ++i)
            for (int j = blockUR; j < blockUR + size; ++j)
                if (i >= b.BlockDR && i < b.BlockDR + bSize &&
                    j >= b.BlockUR && j < b.BlockUR + bSize) return false;
    }

    // 资源重叠检查
    for (auto &r : info.resources) {
        if (r.Cnt <= 0) continue;
        for (int i = blockDR; i < blockDR + size; ++i)
            for (int j = blockUR; j < blockUR + size; ++j)
                if (i == r.BlockDR && j == r.BlockUR) return false;
    }

    // ★ 单位重叠检查（村民/士兵站在建造位置上也导致失败）★
    for (auto &f : info.farmers) {
        int fbDR = (int)(f.DR / (double)BLOCKSIDELENGTH);
        int fbUR = (int)(f.UR / (double)BLOCKSIDELENGTH);
        if (fbDR >= blockDR && fbDR < blockDR + size &&
            fbUR >= blockUR && fbUR < blockUR + size) return false;
    }
    for (auto &a : info.armies) {
        int abDR = (int)(a.DR / (double)BLOCKSIDELENGTH);
        int abUR = (int)(a.UR / (double)BLOCKSIDELENGTH);
        if (abDR >= blockDR && abDR < blockDR + size &&
            abUR >= blockUR && abUR < blockUR + size) return false;
    }

    return true;
}

bool UsrAI::findBuildSite(int &x, int &y, int size) {
    if (townCenterSN == -1) return false;
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return false;
    int cx = center->BlockDR, cy = center->BlockUR;

    // 从TC向外螺旋搜索（扩大范围到50，适应密集地图；r=8 避开农场6格保护区）
    for (int r = 8; r < 50; ++r) {
        for (int dx = -r; dx <= r; ++dx) {
            for (int dy = -r; dy <= r; ++dy) {
                if (std::abs(dx) != r && std::abs(dy) != r) continue;
                int nx = cx + dx, ny = cy + dy;
                int key = nx * 1000 + ny;
                if (triedBuildPositions.count(key)) continue;
                if (isPositionFree(nx, ny, size)) {
                    x = nx; y = ny;
                    return true;
                }
            }
        }
    }

    // 清空黑名单重试
    if (!triedBuildPositions.empty()) {
        triedBuildPositions.clear();
        DebugText("Cleared build blacklist, retrying...");
    }
    return false;
}

bool UsrAI::findDefenseBuildSite(int &x, int &y, int size) {
    if (townCenterSN == -1) return false;
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return false;
    int cx = center->BlockDR, cy = center->BlockUR;
    // 四对角方向螺旋搜索，分散箭塔覆盖范围
    static int diagOffsets[4][2] = {{1,1},{1,-1},{-1,1},{-1,-1}};
    for (int r = 4; r < 12; ++r) {
        for (int d = 0; d < 4; ++d) {
            int nx = cx + diagOffsets[d][0] * r;
            int ny = cy + diagOffsets[d][1] * r;
            if (nx < 0 || ny < 0 || nx >= MAP_L || ny >= MAP_U) continue;
            int key = nx * 1000 + ny;
            if (triedBuildPositions.count(key)) continue;
            if (isPositionFree(nx, ny, size)) {
                x = nx; y = ny;
                return true;
            }
        }
    }
    return false;
}
// 谷仓选址：靠近浆果丛最密集处，减少村民往返时间
bool UsrAI::findGranarySite(int &x, int &y) {
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return false;
    double BL = (double)BLOCKSIDELENGTH;
    double tcDR = (center->BlockDR + 1) * BL;
    double tcUR = (center->BlockUR + 1) * BL;

    // ★ 收集已有仓库位置（斥力：避免重复在同一集群旁建仓库）
    std::vector<std::pair<double,double>> existingGranaries;
    for (auto &b : info.buildings) {
        if (b.Type == BUILDING_GRANARY && b.Percent == 100) {
            existingGranaries.push_back({(b.BlockDR + 1.0) * BL, (b.BlockUR + 1.0) * BL});
        }
    }
    bool hasGranary = !existingGranaries.empty();

    // 统计聚类密度
    // ★ 第一座仓库：只考虑浆果（保证主食物来源效率，瞪羚距离远不打紧）
    // ★ 第二座仓库：也考虑瞪羚（2x加权，已有仓库排斥会让它自然选在瞪羚旁）
    int bestScore = -1;
    int bestBX = 0, bestBY = 0;
    for (auto &r : info.resources) {
        if (r.Cnt <= 0) continue;
        bool isBush = (r.Type == RESOURCE_BUSH);
        bool isGazelle = (r.Type == RESOURCE_GAZELLE);
        if (!isBush && !isGazelle) continue;
        // 第一座仓库不选瞪羚——必须保证浆果采集效率！
        if (isGazelle && !hasGranary) continue;
        if (calDistance(tcDR, tcUR, r.DR, r.UR) > 30 * BL) continue;

        int cluster = 0;
        for (auto &r2 : info.resources) {
            if (r2.Cnt <= 0) continue;
            if ((isBush && r2.Type == RESOURCE_BUSH) ||
                (isGazelle && r2.Type == RESOURCE_GAZELLE))
                if (calDistance(r.DR, r.UR, r2.DR, r2.UR) < 5 * BL) cluster++;
        }
        if (cluster <= 0) continue;

        // 第二座及以后：瞪羚2x加权（减少猎人运输时间）
        if (hasGranary && isGazelle) cluster *= 2;

        // 已有仓库排斥：12格内有仓库则大幅降分
        for (auto &gd : existingGranaries) {
            if (calDistance(r.DR, r.UR, gd.first, gd.second) < 12 * BL) {
                cluster /= 4;
                break;
            }
        }

        if (cluster > bestScore) {
            bestScore = cluster;
            bestBX = r.BlockDR;
            bestBY = r.BlockUR;
        }
    }
    if (bestScore <= 0) return false;

    // 在最佳浆果丛四侧尝试放置3x3谷仓
    int offsets[4][2] = {{1,0}, {-1,0}, {0,1}, {0,-1}};
    for (int d = 0; d < 4; d++) {
        int nx = bestBX + offsets[d][0] * 3;
        int ny = bestBY + offsets[d][1] * 3;
        if (triedBuildPositions.count(nx * 1000 + ny)) continue;
        if (isPositionFree(nx, ny, 3)) {
            x = nx; y = ny;
            return true;
        }
    }
    // 四侧都被占→扩大搜索范围
    for (int r = 4; r < 10; r++) {
        for (int dx = -r; dx <= r; dx++) {
            for (int dy = -r; dy <= r; dy++) {
                if (std::abs(dx) != r && std::abs(dy) != r) continue;
                int nx = bestBX + dx, ny = bestBY + dy;
                if (nx < 0 || ny < 0) continue;
                if (triedBuildPositions.count(nx * 1000 + ny)) continue;
                if (isPositionFree(nx, ny, 3)) {
                    x = nx; y = ny;
                    return true;
                }
            }
        }
    }
    return false;
}

// 房屋选址：TC 8格外（避开TC周围6格，留给农场）
bool UsrAI::findHouseSite(int &x, int &y) {
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return false;
    int cx = center->BlockDR, cy = center->BlockUR;
    for (int r = 8; r < 50; ++r) {
        for (int dx = -r; dx <= r; ++dx) {
            for (int dy = -r; dy <= r; ++dy) {
                if (std::abs(dx) != r && std::abs(dy) != r) continue;
                int nx = cx + dx, ny = cy + dy;
                if (nx < 0 || ny < 0) continue;
                if (triedBuildPositions.count(nx * 1000 + ny)) continue;
                if (isPositionFree(nx, ny, 2)) {
                    x = nx; y = ny;
                    return true;
                }
            }
        }
    }
    return false;
}

// 市场选址：TC 8格外（避开TC周围6格，留给农场）
bool UsrAI::findMarketSite(int &x, int &y) {
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return false;
    int cx = center->BlockDR, cy = center->BlockUR;

    // 从TC外8格开始螺旋搜索
    for (int r = 8; r < 50; ++r) {
        for (int dx = -r; dx <= r; ++dx) {
            for (int dy = -r; dy <= r; ++dy) {
                if (std::abs(dx) != r && std::abs(dy) != r) continue;
                int nx = cx + dx, ny = cy + dy;
                if (nx < 0 || ny < 0) continue;
                if (triedBuildPositions.count(nx * 1000 + ny)) continue;
                if (isPositionFree(nx, ny, 3)) {
                    x = nx; y = ny;
                    return true;
                }
            }
        }
    }
    return false;
}

// ============================================================
// 农场环形选址：TC周围隔1格，从紧贴TC的环向外扩展
// ============================================================
bool UsrAI::findFarmRingSite(int &x, int &y) {
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return findBuildSite(x, y, 3);
    int cx = center->BlockDR, cy = center->BlockUR;
    // TC 3x3 占据 [cx, cx+2] x [cy, cy+2]
    // 隔1格：农场3x3从 cx+4 / cx-4 / cy+4 / cy-4 开始（gap = 1 block）

    // 从内圈向外搜索（r=4 = 隔1格后最内圈）
    for (int r = 4; r < 30; ++r) {
        // 上下两行
        for (int dx = -r; dx <= r + 2; ++dx) {
            int nx = cx + dx;
            // 上行：farm bottom = cy+r, farm occupies [cy+r, cy+r+2]
            int key = nx * 1000 + (cy + r);
            if (!triedBuildPositions.count(key) && isPositionFree(nx, cy + r, 3)) {
                x = nx; y = cy + r; return true;
            }
            // 下行：farm bottom = cy-r, farm occupies [cy-r, cy-r+2]（隔1格）
            key = nx * 1000 + (cy - r);
            if (!triedBuildPositions.count(key) && isPositionFree(nx, cy - r, 3)) {
                x = nx; y = cy - r; return true;
            }
        }
        // 左右两列（不含四角，避免重复）
        for (int dy = -r + 1; dy <= r + 1; ++dy) {
            int ny = cy + dy;
            // 右列：farm left = cx+r
            int key = (cx + r) * 1000 + ny;
            if (!triedBuildPositions.count(key) && isPositionFree(cx + r, ny, 3)) {
                x = cx + r; y = ny; return true;
            }
            // 左列：farm left = cx-r, farm occupies [cx-r, cx-r+2]（隔1格）
            key = (cx - r) * 1000 + ny;
            if (!triedBuildPositions.count(key) && isPositionFree(cx - r, ny, 3)) {
                x = cx - r; y = ny; return true;
            }
        }
    }
    // 环形找不到→回退到默认选址
    return findBuildSite(x, y, 3);
}

bool UsrAI::tryBuild(int buildingType, int size, bool ignoreCooldown) {
    if (buildCooldown > 0 && !ignoreCooldown) return false;

    auto f = findIdleFarmer();
    if (!f) f = findAnyFarmer();
    if (!f) return false;

    int x, y;
    bool placed = false;
    // 谷仓：优先建在浆果密集处
    if (buildingType == BUILDING_GRANARY)
        placed = findGranarySite(x, y);
    // 市场：建在TC 8格外（避开农场6格保护区）
    if (!placed && buildingType == BUILDING_MARKET)
        placed = findMarketSite(x, y);
    // 房屋：TC 8格外（避开农场6格保护区）
    if (!placed && buildingType == BUILDING_HOME)
        placed = findHouseSite(x, y);
    if (!placed && buildingType == BUILDING_FARM)
        placed = findFarmRingSite(x, y);
    if (!placed && buildingType == BUILDING_ARROWTOWER)
        placed = findDefenseBuildSite(x, y, size);
    if (!placed) placed = findBuildSite(x, y, size);
    if (!placed) return false;

    buildingFarmerType[f->SN] = buildingType;
    int buildInsId = HumanBuild(f->SN, buildingType, x, y);
    pendingBuildIns[buildInsId] = {f->SN, buildingType};

    // 记录尝试过的位置，防止反复在同一位置建造失败
    int key = x * 1000 + y;
    triedBuildPositions.insert(key);

    buildCooldown = 5;   // 5帧冷却（单位碰撞检测已防止重复失败）
    return true;
}

// ============================================================
// 处理建造指令执行结果：失败则释放建造者并换位置重试
// ============================================================
void UsrAI::handleBuildResults() {
    // 极端安全：待定建造指令异常堆积则清空，避免无限增长
    if (pendingBuildIns.size() > 64) pendingBuildIns.clear();

    for (auto it = pendingBuildIns.begin(); it != pendingBuildIns.end(); ) {
        int insId = it->first;
        int farmerSN = it->second.first;
        if (!info.ins_ret.count(insId)) { ++it; continue; }

        int ret = info.ins_ret[insId];
        if (ret == ACTION_SUCCESS) {
            // 内核已接受并放下地基
            it = pendingBuildIns.erase(it);
            continue;
        }

        // 建造失败：释放建造者，让下一帧重新选址
        buildingFarmerType.erase(farmerSN);
        buildStartFrame.erase(farmerSN);

        // 位置类错误才立即换位置重试（该位置已在 tryBuild 中加入黑名单）
        // 资源不足/未解锁类错误则等 manageBuildings 的条件恢复后再自然重试
        if (ret == ACTION_INVALID_HUMANBUILD_DIFFERENTHIGH ||
            ret == ACTION_INVALID_HUMANBUILD_OVERBORDER ||
            ret == ACTION_INVALID_HUMANBUILD_UNEXPLORE ||
            ret == ACTION_INVALID_HUMANBUILD_OVERLAP ||
            ret == ACTION_INVALID_POSITION_NOT_FIT) {
            buildCooldown = 0;   // 解除冷却，允许下一帧立即重试
        }
        it = pendingBuildIns.erase(it);
    }
}

// ---- 资源采集分配 ----

// ============================================================
// 检测寻路卡死的采集村民：空手且长时间非空闲 → 判定目标不可达，强制打断 + 拉黑
// ============================================================
void UsrAI::detectStuckGatherers() {
    // 到期解禁（临时拉黑，避免永久丢失只是暂时被堵的资源）
    for (auto it = stuckResourceUntil.begin(); it != stuckResourceUntil.end(); ) {
        if (it->second <= frame) it = stuckResourceUntil.erase(it);
        else ++it;
    }

    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return;

    for (auto &f : info.farmers) {
        // 跳过：建造者 / 引诱者 / 探路者（本就非空闲+空手，不是采集卡死）
        if (buildingFarmerType.count(f.SN) || f.SN == scoutFarmerSN) {
            gatherStuckFrame.erase(f.SN);
            continue;
        }
        // 已采到东西(Resource>0) 或 空闲(IDLE) → 正常，清空计时
        if (f.Resource > 0 || f.NowState == HUMAN_STATE_IDLE) {
            gatherStuckFrame.erase(f.SN);
            continue;
        }
        // 空手 + 非空闲：累计时长，超时判定寻路卡死
        if (gatherStuckFrame.find(f.SN) == gatherStuckFrame.end()) {
            gatherStuckFrame[f.SN] = frame;
        } else if (frame - gatherStuckFrame[f.SN] > STUCK_GATHER_TIMEOUT) {
            int targetSN = f.WorkObjectSN;
            if (targetSN > 0) stuckResourceUntil[targetSN] = frame + STUCK_BLACKLIST_FRAMES;
            HumanAction(f.SN, center->SN);  // 打断卡死关系，回TC重新待命
            gatherStuckFrame.erase(f.SN);
            DebugText(QString("[STUCK f=%1] 村民SN=%2 寻路卡死, 目标资源SN=%3 已拉黑").arg(frame).arg(f.SN).arg(targetSN));
        }
    }
}

bool UsrAI::tryAssignFood(tagFarmer* f) {
    if (!f) return false;

    // ★ 每帧清理：已完成狩猎的农民移出狩猎组（防止卡死在组内无法再次狩猎）
    for (auto it = huntingGroup.begin(); it != huntingGroup.end(); ) {
        bool still = false;
        for (auto &x : info.farmers)
            if (x.SN == *it && x.NowState == HUMAN_STATE_ATTACKING) { still = true; break; }
        if (!still) it = huntingGroup.erase(it); else ++it;
    }

    bool isWarTime = (state >= DEFENSE_WAVE1 && state <= DEFENSE_WAVE3);

    double BL = (double)BLOCKSIDELENGTH;
    auto center = findBuilding(BUILDING_CENTER);
    double tcDR = center ? (center->BlockDR + 1) * BL : f->DR;
    double tcUR = center ? (center->BlockUR + 1) * BL : f->UR;

    // ★ 优先级1：浆果丛（TC 30格内，每丛≤2人，满2人后按优先级转大象/农场/瞪羚）★
    tagResource* bestBush = nullptr;
    double bestBDist = 1e12;
    for (auto &r : info.resources) {
        if (r.Type != RESOURCE_BUSH || r.Cnt <= 0) continue;
        if (stuckResourceUntil.count(r.SN)) continue;  // 不可达的浆果，跳过
        if (calDistance(tcDR, tcUR, r.DR, r.UR) > 30 * BL) continue;
        int realCount = 0;
        for (auto &other : info.farmers)
            if (other.WorkObjectSN == r.SN) realCount++;
        if (realCount + frameBushCount[r.SN] >= 2) continue;  // 每丛≤2人（含本帧已分，满2人转其他事）
        double d = (r.DR - f->DR)*(r.DR - f->DR) + (r.UR - f->UR)*(r.UR - f->UR);
        if (d < bestBDist) { bestBDist = d; bestBush = &r; }
    }
    if (bestBush) {
        HumanAction(f->SN, bestBush->SN);
        frameBushCount[bestBush->SN]++;  // 本帧标记该丛已分1人
        return true;
    }

    // ★ 优先级2：狩猎大象（优先于瞪羚！每头200~300食物，波次期间禁止）★
    if (!isWarTime) {
        auto elephant = findNearestResource(RESOURCE_ELEPHANT, f->DR, f->UR);
        if (elephant && elephant->Cnt > 0 && !frameFoodTargets.count(elephant->SN) && !stuckResourceUntil.count(elephant->SN)) {
            HumanAction(f->SN, elephant->SN);
            frameFoodTargets.insert(elephant->SN);
            return true;
        }
    }

    // ★ 优先级3：农场（每块≤1人，实时扫描+同帧去重）★
    for (auto &b : info.buildings) {
        if (b.Type != BUILDING_FARM || b.Percent < 100) continue;
        if (frameFoodTargets.count(b.SN)) continue;  // 本帧已分配
        int realCount = 0;
        for (auto &other : info.farmers)
            if (other.WorkObjectSN == b.SN) realCount++;
        if (realCount >= 1) continue;
        HumanAction(f->SN, b.SN);
        frameFoodTargets.insert(b.SN);  // 本帧标记
        return true;
    }

    // ★ 优先级4：狩猎瞪羚（波次期间禁止！每只≤2人，WorkObjectSN实时统计）★
    if (!isWarTime && !huntingGroup.count(f->SN)) {
        // 找最近的瞪羚（每只≤2人，含本帧已分）
        tagResource* bestGazelle = nullptr;
        double bestGDist = 1e12;
        for (auto &r : info.resources) {
            if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) continue;
            if (stuckResourceUntil.count(r.SN)) continue;  // 不可达的瞪羚，跳过
            int realCount = 0;
            for (auto &other : info.farmers)
                if (other.WorkObjectSN == r.SN) realCount++;
            if (realCount + frameGazelleCount[r.SN] >= 2) continue;  // 每只≤2人（含本帧已分）
            double d = (r.DR - f->DR)*(r.DR - f->DR) + (r.UR - f->UR)*(r.UR - f->UR);
            if (d < bestGDist) { bestGDist = d; bestGazelle = &r; }
        }
        if (bestGazelle) {
            HumanAction(f->SN, bestGazelle->SN);
            huntingGroup.insert(f->SN);
            frameGazelleCount[bestGazelle->SN]++;
            return true;
        }
    }

    return false;
}

bool UsrAI::tryAssignWood(tagFarmer* f) {
    if (!f) return false;
    // ★ 找最近且工人<2的树，每帧每树最多分2人（减少木头过渡期空闲）
    tagResource* bestTree = nullptr;
    double bestScore = 1e12;
    for (auto &r : info.resources) {
        if (r.Type != RESOURCE_TREE || r.Cnt <= 0) continue;
        if (stuckResourceUntil.count(r.SN)) continue;  // 不可达的树，跳过
        int workerCount = 0;
        for (auto &other : info.farmers)
            if (other.WorkObjectSN == r.SN) workerCount++;
        if (workerCount + frameWoodCount[r.SN] >= 2) continue;  // 单树≤2人（含本帧已分）
        double dist = (r.DR - f->DR)*(r.DR - f->DR) + (r.UR - f->UR)*(r.UR - f->UR);
        double score = dist * (1.0 + workerCount * 0.5);
        if (score < bestScore) { bestScore = score; bestTree = &r; }
    }
    if (bestTree) {
        HumanAction(f->SN, bestTree->SN);
        frameWoodCount[bestTree->SN]++;
        return true;
    }
    // 树少或同帧分配较多时，也要保证能派出去：选择当前工人最少的可达树。
    tagResource* fallbackTree = nullptr;
    int minWorkerCount = 9999;
    double bestFallbackDist = 1e12;
    for (auto &r : info.resources) {
        if (r.Type != RESOURCE_TREE || r.Cnt <= 0) continue;
        if (stuckResourceUntil.count(r.SN)) continue;
        int workerCount = 0;
        for (auto &other : info.farmers)
            if (other.WorkObjectSN == r.SN) workerCount++;
        double dist = (r.DR - f->DR)*(r.DR - f->DR) + (r.UR - f->UR)*(r.UR - f->UR);
        if (workerCount < minWorkerCount ||
            (workerCount == minWorkerCount && dist < bestFallbackDist)) {
            minWorkerCount = workerCount;
            bestFallbackDist = dist;
            fallbackTree = &r;
        }
    }
    if (fallbackTree) {
        HumanAction(f->SN, fallbackTree->SN);
        frameWoodCount[fallbackTree->SN]++;
        return true;
    }
    return false;
}

bool UsrAI::tryAssignGold(tagFarmer* f) {
    if (!f) return false;
    auto res = findNearestResource(RESOURCE_GOLD, f->DR, f->UR);
    if (res && !stuckResourceUntil.count(res->SN)) { HumanAction(f->SN, res->SN); return true; }
    return false;
}
