# -*- coding: utf-8 -*-
"""P2（managePriest 治疗档去重）：
   ① 抽 healLandingOk   —— 落点合法性判据（原 healLandOk / healLandingOk 各写一份）
   ② 抽 pickHealTarget  —— 选"最该治的伤兵"（原两段筛选循环各写一份）
   ③ 抽 moveAdjacentToAlly —— 贴到伤兵身边 + 可选"全被否→选离敌最远"兜底
   行为红线：阈值(0.8/0.9/0.5/25格/2.5格/2.0格/0.6格/1.0格)、分支顺序、日志字段全部不变。
"""
P = 'UsrAI.cpp'
s = open(P, encoding='utf-8', newline='').read()
assert '\r\n' in s, 'CRLF 缺失'
s = s.replace('\r\n', '\n')
lines = s.split('\n')


def repl(name, first_sub, last_sub, new_text, keep_last=False, back=0):
    starts = [k for k, l in enumerate(lines) if first_sub in l]
    assert len(starts) == 1, '%s: 首行匹配 %d 次' % (name, len(starts))
    i = starts[0] - back
    ends = [k for k in range(i, len(lines)) if last_sub in lines[k]]
    assert ends, '%s: 末行未找到' % name
    j = ends[0]
    tail = lines[j]
    body = new_text.split('\n') + ([tail] if keep_last else [])
    old_n = j - i + 1
    lines[i:j + 1] = body
    print('ok %-22s 行 %d-%d (%d行) → %d行' % (name, i + 1, j + 1, old_n, len(body)))


# ---------------------------------------------------------------- ① 三个函数级 lambda
NEW_LAMBDAS = """    auto occupiedLanding = [&](double x, double y) {
        if (ownOccupied(x, y)) return true;
        for (auto &e : info.enemy_armies)
            if (calDistance(x, y, e.DR, e.UR) < 4.0 * BL) return true;
        for (auto &e : info.enemy_farmers)
            if (calDistance(x, y, e.DR, e.UR) < 4.0 * BL) return true;
        return false;
    };

    // ★ 2026-09-15 去重（铁律 21/26）：治疗落点合法性（地图边界 + 己方建筑 2.5 格 + 敌单位 2.0 格）。
    //   原先在【趋近治疗】与【闲时治疗】两档各写一份（后者注释还自称"同 healLandOk"）。
    //   ⚠ 2.0 格是 2026-09-12 从 4.0 格收紧后的值：伤兵几乎总在交火线上，4.0 格会把所有落点
    //     判否(实测 4013 帧 0 次治疗)；2.0 格仍在近战贴身(≈1 格)之外，允许靠近交火线救人。
    auto healLandingOk = [&](double x, double y) -> bool {
        if (x < 0 || y < 0 || x > MAP_L * BL || y > MAP_U * BL) return false;
        for (auto &b : info.buildings)
            if (calDistance(x, y, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL) < 2.5 * BL) return false;
        for (auto &e : info.enemy_armies)
            if (calDistance(x, y, e.DR, e.UR) < 2.0 * BL) return false;
        for (auto &e : info.enemy_farmers)
            if (calDistance(x, y, e.DR, e.UR) < 2.0 * BL) return false;
        return true;
    };

    // ★ 2026-09-15 去重：选"最该治的伤兵"= 血量比最低者，同血取近者；原先两档各写一份筛选循环。
    //   maxRatio    ：只治血量比低于该值的友军（趋近档 0.8=只救明显重伤，免为小伤跨图送命；
    //                 闲时档 0.9=本职治疗）。
    //   counterRule ：闲时档在反攻期只认重伤(<50%)，避免祭司回头追基地里的轻伤后方单位而滞留不推进；
    //                 趋近档不带此规则（保持原行为）。
    //   输出 outRatio = 命中伤兵的血量比（未命中时 1.0，与原文初值一致，供日志使用）。
    auto pickHealTarget = [&](double maxRatio, bool counterRule,
                              double &outDR, double &outUR, double &outRatio) -> int {
        int bestSN = -1; double worst = 1.0, bestD = 1e12;
        outDR = 0; outUR = 0;
        for (auto &a : info.armies) {
            if (a.SN == priestSN) continue;              // ★ 铁律：绝不把祭司自己当治疗目标(=自毁)
            if (a.MaxBlood <= 0 || a.Blood <= 0) continue;
            double r = (double)a.Blood / a.MaxBlood;
            if (r >= maxRatio) continue;
            if (counterRule && inCounter && r >= 0.5) continue;
            double d = calDistance(pDR, pUR, a.DR, a.UR);
            if (d > 25.0 * BL) continue;                 // 太远不追，防送命/离 TC 过远
            if (r < worst || (r == worst && d < bestD)) {
                worst = r; bestSN = a.SN; bestD = d; outDR = a.DR; outUR = a.UR;
            }
        }
        outRatio = worst;
        return bestSN;
    };

    // ★ 2026-09-15 去重：贴到伤兵身边。落点 = 伤兵身后 0.6 格，再沿垂直方向 0/±1/±2 格微调，
    //   取首个合法落点（治疗射程极短：引擎 Core_List.cpp 仅校验 isAttackable 标志，无距离判定，
    //   故必须贴到友军身边 ≈0.6 格才发得出治疗令）。
    //   allowFallback：5 档全被否时是否"强行贴近"（改选离最近敌人最远的那档）——
    //                  闲时档 true（伤兵总在交火线上，不贴上去就永远治不到，且此处已保证非濒死）；
    //                  趋近档 false（宁可不发令，保持原行为）。
    auto moveAdjacentToAlly = [&](double allyX, double allyY, double dist, bool allowFallback) -> bool {
        double ux = (allyX - pDR) / dist;
        double uy = (allyY - pUR) / dist;
        const double OFF[5] = {0.0, 1.0, -1.0, 2.0, -2.0};
        int bestO = 0; double bestClear = -1e18;
        for (int o = 0; o < 5; ++o) {
            double cx = allyX - ux * 0.6 * BL - uy * OFF[o] * BL;
            double cy = allyY - uy * 0.6 * BL + ux * OFF[o] * BL;
            cx = max(0.0, min((double)MAP_L * BL, cx));
            cy = max(0.0, min((double)MAP_U * BL, cy));
            if (healLandingOk(cx, cy)) { HumanMove(priestSN, cx, cy); return true; }
            if (!allowFallback) continue;
            double clear = 1e12;
            for (auto &e : info.enemy_armies)
                clear = std::min(clear, calDistance(cx, cy, e.DR, e.UR));
            for (auto &e : info.enemy_farmers)
                clear = std::min(clear, calDistance(cx, cy, e.DR, e.UR));
            if (clear > bestClear) { bestClear = clear; bestO = o; }
        }
        if (!allowFallback) return false;
        double cx = allyX - ux * 0.6 * BL - uy * OFF[bestO] * BL;
        double cy = allyY - uy * 0.6 * BL + ux * OFF[bestO] * BL;
        cx = max(0.0, min((double)MAP_L * BL, cx));
        cy = max(0.0, min((double)MAP_U * BL, cy));
        HumanMove(priestSN, cx, cy);
        return true;
    };"""

repl('① 三个函数级 lambda',
     '    auto occupiedLanding = [&](double x, double y) {',
     '    };',
     NEW_LAMBDAS)

# ---------------------------------------------------------------- ② 趋近治疗档
NEW_A = """            bool closeQuarters = false;
            for (auto &e : info.enemy_armies)
                if (calDistance(pDR, pUR, e.DR, e.UR) < 4.0 * BL) { closeQuarters = true; break; }
            if (priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0 && pBR > 0.25 && !closeQuarters) {
                double allyDR = 0, allyUR = 0, worstRatio = 1.0;
                int needAlly = pickHealTarget(0.8, false, allyDR, allyUR, worstRatio);
                if (needAlly >= 0) {
                    double bestAllyDist = calDistance(pDR, pUR, allyDR, allyUR);
                    if (bestAllyDist <= 1.0 * BL) {
                        HumanAction(priestSN, needAlly);
                        priestMoveCooldown = 30;
                        if (frame % 50 == 0)
                            DebugText(QString("Priest HEAL(approach) SN=%1 ratio=%2 hp=%3")
                                      .arg(needAlly).arg(worstRatio, 0, 'f', 2).arg(pBR, 0, 'f', 2));
                        return;
                    }
                    if (moveAdjacentToAlly(allyDR, allyUR, bestAllyDist, false)) {
                        priestMoveCooldown = 30;
                        if (frame % 50 == 0)
                            DebugText(QString("Priest MOVE->HEAL SN=%1 ratio=%2 hp=%3 d=%4")
                                      .arg(needAlly).arg(worstRatio, 0, 'f', 2).arg(pBR, 0, 'f', 2)
                                      .arg(bestAllyDist / BL, 0, 'f', 1));
                        return;
                    }
                }
            }"""

repl('② 趋近治疗档',
     '            bool closeQuarters = false;',
     '}   // ★ 闭合 cpp:818 新加的外层',
     NEW_A, keep_last=True)

# ---------------------------------------------------------------- ③ 闲时治疗档
NEW_C = """            double bestAllyDR = 0, bestAllyUR = 0, worstRatio = 1.0;
            int bestAlly = pickHealTarget(0.9, true, bestAllyDR, bestAllyUR, worstRatio);
            if (bestAlly >= 0) {
                double bestAllyDist = calDistance(pDR, pUR, bestAllyDR, bestAllyUR);
                bool issued = false;
                if (bestAllyDist > 1.0 * BL) {
                    // ★ 反攻期：不回头追后方轻伤单位——治疗移动令落空，本函数结束，推进交给 manageCounterAttack
                    if (!inCounter) issued = moveAdjacentToAlly(bestAllyDR, bestAllyUR, bestAllyDist, true);
                } else {
                    HumanAction(priestSN, bestAlly);
                    issued = true;
                }
                if (!issued) return;
                priestMoveCooldown = 30;
                if (frame % 50 == 0)
                    DebugText(QString("Priest HEAL (idle) SN=%1 ratio=%2")
                              .arg(bestAlly).arg(worstRatio, 0, 'f', 2));"""

repl('③ 闲时治疗档',
     '            int bestAlly = -1; double worstRatio = 1.0; double bestAllyDist = 1e12;',
     ".arg(bestAlly).arg(worstRatio, 0, 'f', 2));",
     NEW_C)

out = '\n'.join(lines)
open(P, 'w', encoding='utf-8', newline='').write(out.replace('\n', '\r\n'))
print('P2 done, 行数 %d → %d' % (s.count('\n') + 1, out.count('\n') + 1))
