# -*- coding: utf-8 -*-
"""M1（manageMilitary 结构去重）：
   ① 删死代码 enemyNearTC（只被 (void) 引用，无实际调用点，铁律 27）
   ② 抽 priestAttackerSN —— "有无敌人以祭司为目标"（D-1 一处 + D0 每兵各扫一遍）
   ③ 抽 nearestGuardTarget —— 护驾取敌"优先非投石车，否则任意敌"（紧急/预警各一遍）
   ④ 抽 holdNearBase —— 回基地外围待命螺旋（W2/W3 前出拦截 + W1/非战时近搜，各一遍）
   行为红线：半径/档位/阈值/卡死窗口/分支顺序/日志字段全部不变。
"""
P = 'UsrAI.cpp'
s = open(P, encoding='utf-8', newline='').read()
assert '\r\n' in s, 'CRLF 缺失'
s = s.replace('\r\n', '\n')
lines = s.split('\n')


def repl(name, first_sub, last_sub, new_text, keep_last=False, min_hits=1):
    starts = [k for k, l in enumerate(lines) if first_sub in l]
    assert len(starts) >= min_hits, '%s: 首行匹配 %d 次(需≥%d)' % (name, len(starts), min_hits)
    i = starts[0]
    ends = [k for k in range(i, len(lines)) if last_sub in lines[k]]
    assert ends, '%s: 末行未找到' % name
    j = ends[0]
    body = new_text.split('\n') + ([lines[j]] if keep_last else [])
    old_n = j - i + 1
    lines[i:j + 1] = body
    print('ok %-20s 行 %d-%d (%d行) → %d行' % (name, i + 1, j + 1, old_n, len(body)))


# ---------------------------------------------------------------- ①删死代码 + ②③④ 三个 lambda
NEW_BLOCK = """    // ★ 2026-09-15 删死代码（铁律 27）：原 enemyNearTC lambda 只被紧随其后的 `(void)enemyNearTC;`
    //   显式引用，无任何实际调用点（护驾早已取消"敌须在 TC 25 格内"门槛），保留只会误导后续维护。
    // ★ 2026-09-15 去重（铁律 21/26）：以下三组在 D-1 / D0 内原本各写一遍。
    //   ①「有无敌人以祭司为目标」= 敌 WorkObjectSN == priestSN（D-1 扫一遍；D0 更每兵各扫一遍队列）
    int priestAttackerSN = -1;
    if (priestAlive)
        for (auto &e : info.enemy_armies)
            if (e.WorkObjectSN == priestSN) { priestAttackerSN = e.SN; break; }
    //   ② 护驾取敌 = "优先非投石车（留给祭司感化），没有再退化为任意敌(含投石车)"（紧急/预警两档各一遍）
    auto nearestGuardTarget = [&](double r) -> int {
        int t = findNearestEnemyNoStone(priestDR, priestUR, r);
        return (t >= 0) ? t : findNearestEnemySN(priestDR, priestUR, r);
    };
    //   ③ 回基地外围待命螺旋（W2/W3 前出拦截搜不到敌、W1/非战时就近搜敌搜不到敌，各一遍）
    //      落点 = 半径 8/11/14 格 × 8 角 = 24 档，全在 TC 建筑之外 → 杜绝"走进 TC 导致不可达失败"；
    //      8 帧内没挪窝(>1 格)就换下一档，24 档全失败则放弃移动、就地待命（防无限刷屏）。
    auto holdNearBase = [&](tagArmy &a) {
        double distTC = calDistance(a.DR, a.UR, centerDR, centerUR);
        if (distTC <= 16 * BL) { armyReturnTry[a.SN] = 0; return; }   // 已在外围待命区，清卡死计数
        if (armyReturnTry[a.SN] >= 24) return;                        // 24 档全失败 → 就地待命
        int atry = armyReturnTry[a.SN];
        int aang = atry % 8;
        int arad = atry / 8; if (arad > 2) arad = 2;
        const int ARADII[3] = {8, 11, 14};
        double ara = (double)aang * 3.141592653589793 / 4.0;
        double aR = ARADII[arad] * BL;
        double atx = centerDR + std::cos(ara) * aR;
        double aty = centerUR + std::sin(ara) * aR;
        atx = max(0.0, min((double)MAP_L * BL, atx));
        aty = max(0.0, min((double)MAP_U * BL, aty));
        HumanMove(a.SN, atx, aty);
        // 卡死检测：不可达/被堵时快速换档（8帧，避免同一不可达点失败刷屏）
        if (armyIssueFrame.count(a.SN) && a.NowState == HUMAN_STATE_IDLE &&
            frame - armyIssueFrame[a.SN] > 8 &&
            calDistance(a.DR, a.UR, armyIssueDR[a.SN], armyIssueUR[a.SN]) < 1.0 * BL) {
            armyReturnTry[a.SN]++;
        }
        armyIssueDR[a.SN] = a.DR; armyIssueUR[a.SN] = a.UR; armyIssueFrame[a.SN] = frame;
    };"""

repl('① 删死代码+抽三个',
     '    auto enemyNearTC = [&](int enemySN) -> bool {',
     '    (void)enemyNearTC;',
     NEW_BLOCK)

# ---------------------------------------------------------------- ④a W2/W3 前出拦截的螺旋
repl('④a W2/W3 回基地',
     '                // 没找到敌人→回基地外围待命（距TC 16格内为外围待命区，不再缩进TC中心→避免不可达失败刷屏）',
     '                // atry>=24：全部档失败→放弃移动，就地待命（防无限刷屏）',
     '                holdNearBase(a);')

# ---------------------------------------------------------------- ④b W1/非战时的螺旋
repl('④b W1/非战时回基地',
     '                    double distToTC = calDistance(a.DR, a.UR, centerDR, centerUR);',
     '                    // atry>=24：放弃移动，就地待命（防无限刷屏）',
     '                    holdNearBase(a);')

# ---------------------------------------------------------------- ②③ D-1：敌锁祭司扫描 + 护驾取敌双查（合并收口）
#   ⚠ `int attackingPriestSN = -1;` 在 manageCounterAttack(1.5 段) 也有一份，故这里 min_hits=2、取首个（D-1）。
repl('②③ D-1 收口',
     '        int attackingPriestSN = -1;',
     '        if (alertSN < 0) alertSN = findNearestEnemySN(priestDR, priestUR, PRIEST_GUARD_ALERT * BL);',
     """        const int attackingPriestSN = priestAttackerSN;   // 已在上方统一扫描（D0 亦复用）
        int urgentSN = nearestGuardTarget(PRIEST_GUARD_URGENT * BL);
        int alertSN  = nearestGuardTarget(PRIEST_GUARD_ALERT * BL);""",
     min_hits=2)

# ---------------------------------------------------------------- ② D0 复用变量（区间须含 for 的闭合 `}`）
repl('② D0 复用变量',
     '            int attackingPriest = -1;',
     '            if (attackingPriest >= 0) {',
     """            const int attackingPriest = priestAttackerSN;   // 已在上方统一扫描
            if (attackingPriest >= 0) {""")

out = '\n'.join(lines)
open(P, 'w', encoding='utf-8', newline='').write(out.replace('\n', '\r\n'))
print('M1 done, 行数 %d → %d' % (s.count('\n') + 1, out.count('\n') + 1))
