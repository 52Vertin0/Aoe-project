# -*- coding: utf-8 -*-
"""P1：managePriest 精简 —— 兵种/射程口径收口 + findConvertTarget 五段合一的 pickByBlood。"""
P = 'UsrAI.cpp'
s = open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')
before = s
lines = s.split('\n')


def repl(name, first_sub, last_sub, new_text, back=0):
    starts = [k for k, l in enumerate(lines) if first_sub in l]
    assert len(starts) == 1, '%s: 首行匹配 %d 次' % (name, len(starts))
    i = starts[0] - back
    ends = [k for k in range(i, len(lines)) if last_sub in lines[k]]
    assert ends, '%s: 末行未找到' % name
    j = ends[0]
    old_n = j - i + 1
    lines[i:j + 1] = new_text.split('\n')
    print('ok %-20s 行 %d-%d (%d行) → %d行' % (name, i + 1, j + 1, old_n, new_text.count('\n') + 1))


def ins_before(name, anchor_sub, new_text):
    starts = [k for k, l in enumerate(lines) if anchor_sub in l]
    assert len(starts) == 1, '%s: 锚点匹配 %d 次' % (name, len(starts))
    i = starts[0]
    lines[i:i] = new_text.split('\n')
    print('ok %-20s 插入于行 %d 前 (%d行)' % (name, i + 1, new_text.count('\n') + 1))


# ---------- 1) 兵种/射程口径收口（原先在 感化选择 / 威胁扫描 / 逃跑 三处各写一遍）----------
ins_before('兵种射程口径',
           '    // ★ 2026-09-15 去重：落点的【己方】占用判据',
           """    // ★ 2026-09-15 去重（铁律 21/26）：远程兵种判定 + "该敌对我的威胁半径"原先在
    //   【感化目标选择】/【威胁扫描 chkThreat】/【逃跑 priestFlee 的威胁收集】三处各写一遍，
    //   改一处漏一处即口径分叉。此处收口为两个 lambda。
    //   ⚠ 威胁半径口径：远程(弓/战车弓/复合弓/投石兵/投石车)≈12 格；近战≈2.5 格（贴身）。
    auto isRangedSort = [&](int s) -> bool {
        return s == AT_BOWMAN || s == AT_CHARIOT_ARCHER ||
               s == AT_COMPOSITE_BOWMAN || s == AT_SLINGER;
    };
    auto enemyThreatRange = [&](int s) -> double {
        return (isRangedSort(s) || s == AT_STONE_THROWER) ? 12.0 * BL : 2.5 * BL;
    };""")

# ---------- 2) findConvertTarget：五段重复循环 → pickByBlood ----------
repl('findConvertTarget',
     '        // ★ 转化优先级（2026-09-12 用户连续需求：先"投石车不再最优先"，再"方阵兵为感化最优先"）：',
     '        return bestVilSN;',
     """        // ★ 转化优先级（2026-09-12 用户连续需求）：① 方阵兵(AT_HOPLITE，克骑兵、转来即反骑主力)
        //   → ② 其余近战(贴身 2.5 格，威胁祭司性命) → ③ 远程军队(削输出) → ④ 投石车(慢，不直接威胁祭司)
        //   → 兜底：最近敌方村民。
        //   ⚠ 前四档的循环体完全相同（"同型里选血量最高者，同血取近者"），原先各写一份共 ~50 行；
        //     收口为 pickByBlood(mode)，筛选条件用显式 mode 区分（不改变任何一档的判定与顺序）。
        auto pickByBlood = [&](int mode) -> int {
            int bSN = -1, bBlood = -1; double bD = 1e12;
            for (auto &e : info.enemy_armies) {
                if (e.Blood <= 0) continue;
                bool want;
                switch (mode) {
                    case 0:  want = (e.Sort == AT_HOPLITE); break;                        // 方阵兵
                    case 1:  want = (e.Sort != AT_HOPLITE && e.Sort != AT_STONE_THROWER &&
                                     !isRangedSort(e.Sort)); break;                       // 其余近战
                    case 2:  want = (e.Sort != AT_HOPLITE && e.Sort != AT_STONE_THROWER &&
                                     isRangedSort(e.Sort)); break;                        // 远程军队
                    default: want = (e.Sort == AT_STONE_THROWER); break;                  // 投石车
                }
                if (!want) continue;
                double d = calDistance(dr, ur, e.DR, e.UR);
                if (d > range) continue;
                if (e.Blood > bBlood || (e.Blood == bBlood && d < bD)) {
                    bBlood = e.Blood; bSN = e.SN; bD = d;
                }
            }
            return bSN;
        };
        int t;
        if ((t = pickByBlood(0)) >= 0) return t;   // 0) 方阵兵最高优先
        if ((t = pickByBlood(1)) >= 0) return t;   // 1) 其余近战（保命）
        if ((t = pickByBlood(2)) >= 0) return t;   // 2) 远程军队
        if ((t = pickByBlood(3)) >= 0) return t;   // 3) 投石车降为第四
        // 兜底：无敌方军队时，最近敌方村民（保留原行为）
        int bestVilSN = -1; double bestVilDist = 1e12;
        for (auto &e : info.enemy_farmers) {
            double d = calDistance(dr, ur, e.DR, e.UR);
            if (d > range) continue;
            if (d < bestVilDist) { bestVilDist = d; bestVilSN = e.SN; }
        }
        return bestVilSN;""")

# ---------- 3) chkThreat 段的射程表达式（往上 3 行，即三行 r 计算）----------
# 末行锚点必须是【被替换行本身】：以 back=3 回退到 `double r = (` 首行，
# 区间 [i..j] 才覆盖 4 行（含 chkThreat 调用行）。若末行子串取成上一行会漏删调用行。
repl('chkThreat 射程',
     '            chkThreat(e.DR, e.UR, r);',
     '            chkThreat(e.DR, e.UR, r);',
     '            chkThreat(e.DR, e.UR, enemyThreatRange(e.Sort));',
     back=3)

# ---------- 4) priestFlee 威胁收集的射程表达式 ----------
repl('priestFlee 射程',
     '            double r = (e.Sort == AT_BOWMAN || e.Sort == AT_CHARIOT_ARCHER ||',
     '                        e.Sort == AT_STONE_THROWER) ? 12.0 * BL : 2.5 * BL;',
     '            double r = enemyThreatRange(e.Sort);')

out = '\n'.join(lines)
open(P, 'w', encoding='utf-8', newline='').write(out.replace('\n', '\r\n'))
print('P1 done, 行数 %d → %d' % (before.count('\n'), out.count('\n')))
