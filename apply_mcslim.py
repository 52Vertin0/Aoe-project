# -*- coding: utf-8 -*-
"""mcslim 轮：manageCounterAttack 去重 + 删死变量（行为中性重构）。
每处替换断言命中唯一，避免"报成功但未落盘"。"""
import io, sys

PATH = "UsrAI.cpp"
raw = open(PATH, "rb").read()
crlf = raw.count(b"\r\n") > 0
text = raw.decode("utf-8")
text = text.replace("\r\n", "\n")

R = []  # (name, old, new)

# ---------- 1. 新增 lookupEnemySN（放在 rangedMaxRange 之后） ----------
R.append(("lambda-lookupEnemySN", """            default:                 return 5.0 * BL;
        }
    };

    // ====== 1. 侦察阶段：寻找敌方武器厂 ======""", """            default:                 return 5.0 * BL;
        }
    };

    // ★ 2026-09-15 去重（铁律 21/26）：按 SN 在【敌军队→敌农民→敌建筑】中定位坐标。
    //   原代码在 3 处（拉扯粘滞目标 / 投石车粘滞目标 / 投石车威胁点）各抄一份同样的三层循环，语义完全一致。
    //   命中敌军队时顺带回填 isMelee（供拉扯对近战敌更早撤）；三类都没有则返回 false。
    //   ⚠ SN 全图唯一 ⇒ 多查一类（建筑）不会改变任何原有分支的结果。
    auto lookupEnemySN = [&](int sn, double &x, double &y, bool *pMelee = nullptr) -> bool {
        for (auto &e : info.enemy_armies)
            if (e.SN == sn) { x = e.DR; y = e.UR; if (pMelee) *pMelee = isMeleeSort(e.Sort); return true; }
        for (auto &e : info.enemy_farmers)
            if (e.SN == sn) { x = e.DR; y = e.UR; return true; }
        for (auto &b : info.enemy_buildings)
            if (b.SN == sn) { x = (b.BlockDR + 1.0) * BL; y = (b.BlockUR + 1.0) * BL; return true; }
        return false;
    };

    // ====== 1. 侦察阶段：寻找敌方武器厂 ======"""))

# ---------- 2. 新增 attackBuildingOrMarch（放在 issueMarch 之后） ----------
R.append(("lambda-attackBuildingOrMarch", """        marchGoalDR[sn] = mx; marchGoalUR[sn] = my;   // 判据参照 = 本轮实际下发点
        HumanMove(sn, mx, my);                   // 引擎完整寻路：直奔敌方基地附近目标点
        marchCmdFrame[sn] = frame;
    };

    for (int pass = 0; pass < 2 && marchCmds < 8; ++pass) {""", """        marchGoalDR[sn] = mx; marchGoalUR[sn] = my;   // 判据参照 = 本轮实际下发点
        HumanMove(sn, mx, my);                   // 引擎完整寻路：直奔敌方基地附近目标点
        marchCmdFrame[sn] = frame;
    };

    // ★ 2026-09-15 去重（铁律 21/26）：单位无「敌方兵」可打时的统一出口 = 最近敌塔 → 最近敌建筑 → 推进。
    //   原远程分支与近战分支各自抄了一份完全相同的 25 行（连 ARMY_IGNORE_SIEGE_WORKSHOP 分支都一样）。
    //   who 仅用于 [TOWER-TGT] 日志标签（"复合弓兵/远程" / "近战"），不改任何决策。
    //   ★ 语义保持原样：打塔后不再推进；打建筑时若"已在打它"则退回推进；否则推进兜底。
    auto attackBuildingOrMarch = [&](tagArmy &a, const char *who, int stuckTry, bool canReissue) {
        int towerSN = findNearestEnemyTower(a.DR, a.UR, TOWER_TARGET_RANGE * BL);
        if (towerSN >= 0) {
            if (a.WorkObjectSN != towerSN) {
                HumanAction(a.SN, towerSN);
                DebugText(QString("[TOWER-TGT f=%1] %2 SN=%3 攻击最近敌塔 %4 (R<=%5格)")
                          .arg(frame).arg(who).arg(a.SN).arg(towerSN).arg(TOWER_TARGET_RANGE));
            }
            return;
        }
        if (directMarch && calDistance(a.DR, a.UR, targetDR, targetUR) <= 12 * BL) {
            // 军队不打武器厂（留给祭司感化）：ARMY_IGNORE_SIEGE_WORKSHOP 时跳过最近的武器厂。
            int ebSN;
            if (ARMY_IGNORE_SIEGE_WORKSHOP) {
                int nb = findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
                ebSN = (nb >= 0 && siege != nullptr && nb == siege->SN) ? -1 : nb;
            } else {
                ebSN = siege ? siege->SN : findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
            }
            if (ebSN >= 0 && a.WorkObjectSN != ebSN) { HumanAction(a.SN, ebSN); return; }   // 有建筑可打→拆
        }
        issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);   // 无建筑/已在打→继续推进
    };

    for (int pass = 0; pass < 2 && marchCmds < 8; ++pass) {"""))

# ---------- 3. 拉扯粘滞目标查找去重 ----------
R.append(("kiting-sticky-lookup", """                if (kitingTargetSN.count(a.SN)) {
                    int cur = kitingTargetSN[a.SN];
                    for (auto &e : info.enemy_armies) if (e.SN == cur) {
                        kEX = e.DR; kEY = e.UR; kMelee = isMeleeSort(e.Sort); kGot = true; break;
                    }
                    if (!kGot)
                        for (auto &e : info.enemy_farmers) if (e.SN == cur) { kEX = e.DR; kEY = e.UR; kGot = true; break; }
                    if (kGot && calDistance(a.DR, a.UR, kEX, kEY) > 20 * BL) kGot = false;  // 目标跑远→放手
                    if (kGot) kEnemy = cur;
                }
                if (!kGot) {
                    kEnemy = findNearestEnemyNoStone(a.DR, a.UR, 20 * BL);
                    if (kEnemy >= 0) {
                        for (auto &e : info.enemy_armies) if (e.SN == kEnemy) {
                            kEX = e.DR; kEY = e.UR; kMelee = isMeleeSort(e.Sort); kGot = true; break;
                        }
                        if (!kGot)
                            for (auto &e : info.enemy_farmers) if (e.SN == kEnemy) { kEX = e.DR; kEY = e.UR; kGot = true; break; }
                    }
                }""", """                if (kitingTargetSN.count(a.SN)) {
                    int cur = kitingTargetSN[a.SN];
                    kGot = lookupEnemySN(cur, kEX, kEY, &kMelee);          // 粘滞目标仍存活?
                    if (kGot && calDistance(a.DR, a.UR, kEX, kEY) > 20 * BL) kGot = false;  // 目标跑远→放手
                    if (kGot) kEnemy = cur;
                }
                if (!kGot) {
                    kEnemy = findNearestEnemyNoStone(a.DR, a.UR, 20 * BL);
                    if (kEnemy >= 0) kGot = lookupEnemySN(kEnemy, kEX, kEY, &kMelee);
                }"""))

# ---------- 4. 投石车粘滞目标查找去重 ----------
R.append(("catapult-target-lookup", """                if (catTargetSN.count(a.SN)) {
                    int cur = catTargetSN[a.SN];
                    double cx = 0, cy = 0; bool alive = false;
                    for (auto &e : info.enemy_armies) if (e.SN == cur) { cx = e.DR; cy = e.UR; alive = true; break; }
                    if (!alive) for (auto &e : info.enemy_farmers) if (e.SN == cur) { cx = e.DR; cy = e.UR; alive = true; break; }
                    if (!alive) for (auto &b : info.enemy_buildings) if (b.SN == cur) {
                        cx = (b.BlockDR + 1.0) * (double)BLOCKSIDELENGTH;
                        cy = (b.BlockUR + 1.0) * (double)BLOCKSIDELENGTH; alive = true; break;
                    }
                    if (alive) {
                        atkD = calDistance(a.DR, a.UR, cx, cy);
                        if (atkD > 15 * BL) alive = false;      // 目标跑出选取范围→放手
                        else atkSN = cur;
                    }
                }
                bool catReEval = !catTargetFrame.count(a.SN) || (frame - catTargetFrame[a.SN] >= 30);
                if (catReEval) {
                    int cand = findCatapultTarget(a.DR, a.UR, 15 * BL);
                    if (cand >= 0 && cand != atkSN) {
                        double cx = 0, cy = 0; bool found = false;
                        for (auto &e : info.enemy_armies) if (e.SN == cand) { cx = e.DR; cy = e.UR; found = true; break; }
                        if (!found) for (auto &e : info.enemy_farmers) if (e.SN == cand) { cx = e.DR; cy = e.UR; found = true; break; }
                        if (!found) for (auto &b : info.enemy_buildings) if (b.SN == cand) {
                            cx = (b.BlockDR + 1.0) * (double)BLOCKSIDELENGTH;
                            cy = (b.BlockUR + 1.0) * (double)BLOCKSIDELENGTH; found = true; break;
                        }
                        double cd = found ? calDistance(a.DR, a.UR, cx, cy) : 1e12;
                        if (atkSN < 0 || cd + 2.0 * BL < atkD) { atkSN = cand; atkD = cd; }  // 只有明显更近才换目标
                    }
                    catTargetFrame[a.SN] = frame;
                }""", """                if (catTargetSN.count(a.SN)) {
                    int cur = catTargetSN[a.SN];
                    double cx = 0, cy = 0;
                    bool alive = lookupEnemySN(cur, cx, cy);
                    if (alive) {
                        atkD = calDistance(a.DR, a.UR, cx, cy);
                        if (atkD > 15 * BL) alive = false;      // 目标跑出选取范围→放手
                        else atkSN = cur;
                    }
                }
                bool catReEval = !catTargetFrame.count(a.SN) || (frame - catTargetFrame[a.SN] >= 30);
                if (catReEval) {
                    int cand = findCatapultTarget(a.DR, a.UR, 15 * BL);
                    if (cand >= 0 && cand != atkSN) {
                        double cx = 0, cy = 0;
                        bool found = lookupEnemySN(cand, cx, cy);
                        double cd = found ? calDistance(a.DR, a.UR, cx, cy) : 1e12;
                        if (atkSN < 0 || cd + 2.0 * BL < atkD) { atkSN = cand; atkD = cd; }  // 只有明显更近才换目标
                    }
                    catTargetFrame[a.SN] = frame;
                }"""))

# ---------- 5. 投石车威胁点查找去重 ----------
R.append(("catapult-threat-lookup", """                double ex = 0, ey = 0; bool gotThreat = false;
                if (threatSN >= 0) {
                    for (auto &e : info.enemy_armies) if (e.SN == threatSN) { ex = e.DR; ey = e.UR; gotThreat = true; break; }
                    if (!gotThreat) for (auto &e : info.enemy_farmers) if (e.SN == threatSN) { ex = e.DR; ey = e.UR; gotThreat = true; break; }
                }""", """                double ex = 0, ey = 0;
                bool gotThreat = (threatSN >= 0) && lookupEnemySN(threatSN, ex, ey);"""))

# ---------- 6. 远程分支：塔/建筑攻击块 → lambda ----------
R.append(("ranged-attack-block", """            if (ranged) {
                // ★ 2026-09-13「士兵攻击箭塔 → 选距离自己最近的箭塔」：
                //   先查【最近敌方箭塔】(TOWER_TARGET_RANGE 格内)。命中则打塔，且【优先于武器厂/任意敌建筑】——
                //   旧逻辑里武器厂(siege)必然覆盖一切，更近的房屋/农场也会顶掉箭塔 ⇒ 挨塔射不还手。
                //   仍保留去重：已在打这座塔就不重发，避免每帧 HumanAction 打断上方拉扯 HumanMove。
                int towerSN = findNearestEnemyTower(a.DR, a.UR, TOWER_TARGET_RANGE * BL);
                if (towerSN >= 0) {
                    if (a.WorkObjectSN != towerSN) {
                        HumanAction(a.SN, towerSN);
                        DebugText(QString("[TOWER-TGT f=%1] 复合弓兵/远程 SN=%2 攻击最近敌塔 %3 (R<=%4格)")
                                  .arg(frame).arg(a.SN).arg(towerSN).arg(TOWER_TARGET_RANGE));
                    }
                } else if (directMarch && calDistance(a.DR, a.UR, targetDR, targetUR) <= 12 * BL) {
                    // ★ 2026-09-13 用户要求「军队不要攻击敌方武器厂」：不再优先选武器厂(ARMY_IGNORE_SIEGE_WORKSHOP)，
                    //   改打【最近任意敌建筑】（箭塔已在上面 towerSN 分支优先命中）。
                    int ebSN;
                    if (ARMY_IGNORE_SIEGE_WORKSHOP) {
                        int nb = findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
                        // ★ 武器厂专留给祭司感化——军队即使最近建筑是武器厂也跳过它(不打武器厂)
                        ebSN = (nb >= 0 && siege != nullptr && nb == siege->SN) ? -1 : nb;
                    } else {
                        ebSN = siege ? siege->SN : findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
                    }
                    if (ebSN >= 0 && a.WorkObjectSN != ebSN) HumanAction(a.SN, ebSN);
                    else issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);
                } else {
                    issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);
                }
                marchCmds++;
                continue;
            }""", """            if (ranged) {
                // ★ 2026-09-13「士兵攻击箭塔 → 选距离自己最近的箭塔」+「军队不要攻击敌方武器厂」：
                //   打最近敌塔(TOWER_TARGET_RANGE 格内) → 打最近任意敌建筑(12 格内，武器厂跳过留给祭司) → 推进。
                //   与近战分支共用同一实现（原两处各抄一份 25 行，铁律 21/26）。
                attackBuildingOrMarch(a, "复合弓兵/远程", stuckTry, canReissue);
                marchCmds++;
                continue;
            }"""))

# ---------- 7. 近战分支：塔/建筑攻击块 → lambda ----------
R.append(("melee-attack-block", """            if (enemySN >= 0) {
                // 有敌【单位】可打 → 单位永远优先于建筑（保持原语义，含去重）
                if (a.WorkObjectSN != enemySN) HumanAction(a.SN, enemySN);
            } else {
                // ★ 2026-09-13「士兵攻击箭塔 → 选距离自己最近的箭塔」：
                //   15 格内无敌方单位时，先查【最近敌方箭塔】(TOWER_TARGET_RANGE 格内)并打它，
                //   优先于武器厂(siege)与任意其它敌建筑。近战打塔需要走过去，故给 12 格窗口。
                int towerSN = findNearestEnemyTower(a.DR, a.UR, TOWER_TARGET_RANGE * BL);
                if (towerSN >= 0) {
                    if (a.WorkObjectSN != towerSN) {
                        HumanAction(a.SN, towerSN);
                        DebugText(QString("[TOWER-TGT f=%1] 近战 SN=%2 攻击最近敌塔 %3 (R<=%4格)")
                                  .arg(frame).arg(a.SN).arg(towerSN).arg(TOWER_TARGET_RANGE));
                    }
                } else if (directMarch && calDistance(a.DR, a.UR, targetDR, targetUR) <= 12 * BL) {
                    // ★ 2026-09-13 用户要求「军队不要攻击敌方武器厂」：不再优先选武器厂(ARMY_IGNORE_SIEGE_WORKSHOP)，
                    //   改拆【最近任意敌建筑】（箭塔已在上方 towerSN 分支优先命中）。武器厂留给祭司感化。
                    int ebSN;
                    if (ARMY_IGNORE_SIEGE_WORKSHOP) {
                        int nb = findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
                        // ★ 武器厂专留给祭司感化——军队即使最近建筑是武器厂也跳过它(不打武器厂)
                        ebSN = (nb >= 0 && siege != nullptr && nb == siege->SN) ? -1 : nb;
                    } else {
                        ebSN = siege ? siege->SN : findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
                    }
                    // ★ 拆建筑攻击令去重（同 4117）
                    if (ebSN >= 0 && a.WorkObjectSN != ebSN) HumanAction(a.SN, ebSN);   // 有建筑可打→拆基地
                    else issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);  // 无建筑→继续推进
                } else {
                    // 向目标推进：已知敌基地→引擎全图寻路直奔；未知→逐格摸索已探索区
                    issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);
                }
            }""", """            if (enemySN >= 0) {
                // 有敌【单位】可打 → 单位永远优先于建筑（保持原语义，含去重）
                if (a.WorkObjectSN != enemySN) HumanAction(a.SN, enemySN);
            } else {
                // 15 格内无敌方单位：打最近敌塔 → 最近敌建筑 → 推进（与远程分支共用实现）。
                attackBuildingOrMarch(a, "近战", stuckTry, canReissue);
            }"""))

# ---------- 8. 删死变量 enemyMil / enemyTowers ----------
R.append(("dead-enemyMil-Towers", """        int enemyMil = 0;
        for (auto &e : info.enemy_armies) if (e.Blood > 0) enemyMil++;
        int enemyTowers = 0;
        for (auto &b : info.enemy_buildings) if (b.Type == BUILDING_ARROWTOWER) enemyTowers++;
        // 局部清场：祭司周边无敌【活敌军队】、无【箭塔】""", """        // 局部清场：祭司周边无敌【活敌军队】、无【箭塔】"""))

R.append(("stale-comment-enemyMil", """        // ★ 2026-09-13：敌方已清场(enemyMil==0 && enemyTowers==0)时，安全距离约束失效 ——""",
          """        // ★ 2026-09-13：局部清场(localClear)成立时，安全距离约束失效 ——"""))

# ---------- 9. 删死变量 priestEnemy ----------
R.append(("dead-priestEnemy", """        // ★【2026-09-08 二次修】原"扩到 28 格后 priestEnemy>=0 return"——WRONG-LAYER return 又踩坑:
        //   反攻期祭司前出后 28 格内**恒有敌** → return 几乎每帧触发 → 祭司段永远跑不到 → 停在 TC 不动。
        //   改为：只查询,不 return——managePriest 仍独立按"投石车→近战→远程→村民"优先级感化
        //   (原 12~28 格盲区已扩到 28 格),本段继续走感化武器厂 / HumanMove 推进(与 managePriest 并行)。
        int priestEnemy = findNearestEnemySN(priest->DR, priest->UR, PRIEST_CONVERT_RANGE * BL);
        // 注: priestEnemy 暂不直接使用——managePriest 已独立感化,本段只关心武器厂 + 推进""",
          """        // ★【2026-09-08 二次修 / 2026-09-15 清理】原"扩到 28 格后 priestEnemy>=0 return"是 WRONG-LAYER
        //   return：反攻期祭司前出后 28 格内**恒有敌** → return 几乎每帧触发 → 祭司段永远跑不到 → 停在 TC 不动。
        //   ⇒ 该查询已彻底删除（结果从不被使用）。managePriest 仍独立按"投石车→近战→远程→村民"感化，
        //     本段只负责感化武器厂 / HumanMove 推进（与 managePriest 并行）。"""))

ok = True
for name, old, new in R:
    c = text.count(old)
    if c != 1:
        print("FAIL %-28s hits=%d" % (name, c))
        ok = False
    else:
        text = text.replace(old, new, 1)
        print("ok   %-28s" % name)

if not ok:
    sys.exit(1)

out = text.replace("\n", "\r\n") if crlf else text
open(PATH, "wb").write(out.encode("utf-8"))
print("written")
