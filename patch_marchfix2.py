# -*- coding: utf-8 -*-
"""反攻推进「卡死自救活锁」修复 · 方案 2（2026-09-28）

方案 1（marchToFinal 历史最优）实测有害：24 局批前 8 局仅 1 胜 6 负 1 未决。
根因：用「历史最优距离」当进展判据太严 —— 单位被推远一次后就再也无法"创新低"
⇒ 档位只涨不落 ⇒ 部队反复退让、无法推进。

方案 2（本脚本）：**不动判据结构，只把参照锚对**。两处实质改动：
  ① issueMarch 退让重锚口径：
     calDistance(单位当前点 → 退让点)   ⛔ 朝退让点走 = 假进展
     → calDistance(退让点 → 最终目标)   ✅ 退让后基准>当前值，不误清档
  ② 卡死判据参照：marchGoal*（本轮下发点，会被自救挪动）→ targetDR/UR（最终推进目标，跨帧稳定）

效果：退让不再被记成进展 ⇒ 档位单调升到 2/3…档 ⇒ 逐档加深直到绕开障碍；
      而绕过障碍真朝目标推进 >0.5 格累计时，仍照旧清零档位（保留原有累积刷新语义，不会"永不脱困"）。

只改 UsrAI.cpp（纯 LF），不动 UsrAI.h ⇒ 不触发头依赖全量重编。
"""
import os

CPP = r'C:\new-aoe3.0.7g\UsrAI.cpp'
CPP_H = r'C:\new-aoe3.0.7h\UsrAI.cpp'
LF = '\n'


def rd(p):
    with open(p, 'rb') as f:
        return f.read()


def wr(p, b):
    with open(p, 'wb') as f:
        f.write(b)


def S(txt):
    return txt.replace('\n', '\n').encode('utf-8')


def sub1(buf, old, new, tag):
    c = buf.count(old)
    if c != 1:
        raise SystemExit('[FAIL] %s: 命中 %d 次（要求 1）' % (tag, c))
    return buf.replace(old, new)


cpp = rd(CPP)

# ---------------- C1：新增常量
c1_old = S("""#define PRIEST_ADV_CLEAR_MAX    3     // B 档单次最多挪走的友军数（保命：留其余护卫）
""")
c1_new = S("""#define PRIEST_ADV_CLEAR_MAX    3     // B 档单次最多挪走的友军数（保命：留其余护卫）
// ★★★ 2026-09-28 反攻推进「卡死自救活锁」修复（manageCounterAttack / issueMarch）★★★
//   活锁：自救退让把【本轮下发点】挪向我方，而旧重锚口径是"单位当前点→退让点"
//   ⇒ 单位朝退让点走就被记成"在前进" ⇒ marchStuckTry 清零 ⇒ 每轮只退 1 格、"退完即成功"
//   ⇒ 永远升不到 2/3 档 ⇒ 卡死单位被永久焊在原地（铁律 9：脱困动作不得充数为进展）。
//   修：① 重锚口径改为"退让点→最终目标"；② 判据参照改为最终推进目标 targetDR/UR。
//   ⛔ 另记：曾试"距最终目标的历史最优值(marchToFinal)"作判据 —— 实测有害（推远一次即无法
//      再创新低 ⇒ 档位只涨不落 ⇒ 部队反复退让），已回滚。勿重犯。
#define MARCH_STUCK_FRAMES  90     // 距最终目标连续 N 帧无新低 ⇒ 判卡死（≈3.6 秒@25fps，原硬编码 90）
#define MARCH_MAX_BACK      8.0    // 自救退让距离上限(格)：档位单调升时防"一路退回 TC"
#define MARCH_STUCK_TRY_MAX 8      // 退让档位上限（8 档 × 1 格 = 8 格，与 MARCH_MAX_BACK 对应）
""")
cpp = sub1(cpp, c1_old, c1_new, 'C1 常量')

# ---------------- C2：(void)fx/fy
c2_old = S("""        (void)sort;
        if (!canReissue) return;                 // 未到节流窗口：本帧静默，不重复下发
""")
c2_new = S("""        (void)sort;
        (void)fx; (void)fy;   // ★ 2026-09-28：重锚口径改为"退让点→最终目标"后，单位当前点不再参与判据
        if (!canReissue) return;                 // 未到节流窗口：本帧静默，不重复下发
""")
cpp = sub1(cpp, c2_old, c2_new, 'C2 (void)fx/fy')

# ---------------- C3：退让距离上限 + 重锚口径修正
c3_old = S("""            double back = (d > BL) ? ((stuckTry * BL < d - BL) ? stuckTry * BL : d - BL) : 0.0;
            if (d > 1e-6) { mx -= dx / d * back; my -= dy / d * back; }
            snapWalkable(mx, my, forestGrid);                // 内缩后可能落进海/林/矿 → 再吸附一次
            // 退让点算一个【新目标】：基准与计时一起重锚，"能否走到退让点"成为新一轮判据；走到即复位，不累积。
            marchIssueDist[sn] = calDistance(fx, fy, mx, my);
            marchMoveFrame[sn] = frame;
""")
c3_new = S("""            double back = (d > BL) ? ((stuckTry * BL < d - BL) ? stuckTry * BL : d - BL) : 0.0;
            if (back > MARCH_MAX_BACK * BL) back = MARCH_MAX_BACK * BL;   // ★ 2026-09-28 退让上限：档位单调升时防"一路退回 TC"
            if (d > 1e-6) { mx -= dx / d * back; my -= dy / d * back; }
            snapWalkable(mx, my, forestGrid);                // 内缩后可能落进海/林/矿 → 再吸附一次
            // ★★★ 2026-09-28 重锚口径修正（修「自救活锁」根因）★★★
            //   旧口径 = calDistance(单位当前点 → 退让点)：退让点被挪向我方 ⇒ 单位朝它走即"距离变近"
            //   ⇒ 被下游判成"在前进" ⇒ 档位清零 ⇒ 每轮只退 1 格 ⇒ 活锁。
            //   新口径 = calDistance(退让点 → 【最终推进目标】)：退让点必然比单位更远离目标 ⇒
            //   基准 > 当前值 ⇒ 不触发清零 ⇒ 档位单调升；真绕过障碍朝目标推进 >0.5 格时才清零。
            marchIssueDist[sn] = calDistance(mx, my, targetDR, targetUR);
            marchMoveFrame[sn] = frame;
""")
cpp = sub1(cpp, c3_old, c3_new, 'C3 重锚口径+上限')

# ---------------- C4：判据参照改 targetDR/UR
c4_old = S("""            const double gDR = marchGoalDR.count(a.SN) ? marchGoalDR[a.SN] : targetDR;
            const double gUR = marchGoalUR.count(a.SN) ? marchGoalUR[a.SN] : targetUR;
            const double curDistToTgt = calDistance(a.DR, a.UR, gDR, gUR);   // ★ 参照 = 本轮实际下发点
""")
c4_new = S("""            // ★★★ 2026-09-28 判据参照改锚（修自救活锁）★★★
            //   参照一律用【最终推进目标 targetDR/UR】（跨帧稳定），**不再**用 marchGoal*（本轮下发点）：
            //   后者会被自救退让挪动，distance 变近 ⇒ 与"进展即清档"互相污染 ⇒ 活锁。
            const double gDR = targetDR;
            const double gUR = targetUR;
            const double curDistToTgt = calDistance(a.DR, a.UR, gDR, gUR);   // ★ 参照 = 最终推进目标
""")
cpp = sub1(cpp, c4_old, c4_new, 'C4 判据参照')

# ---------------- C5：stuckNow 用常量 + 升档上限 + 诊断累加
c5_old = S("""            bool stuckNow = (frame - marchMoveFrame[a.SN] > 90);        // 90帧无位移→判定卡死
            bool canReissue = !marchCmdFrame.count(a.SN) ||
                              (frame - marchCmdFrame[a.SN] >= 30);      // 30帧节流，防每帧换方向抖动
            if (stuckNow && canReissue) marchStuckTry[a.SN]++;          // 升档：换个方向试
""")
c5_new = S("""            bool stuckNow = (frame - marchMoveFrame[a.SN] > MARCH_STUCK_FRAMES);  // 距最终目标无新低→判卡死
            bool canReissue = !marchCmdFrame.count(a.SN) ||
                              (frame - marchCmdFrame[a.SN] >= 30);      // 30帧节流，防每帧换方向抖动
            if (stuckNow && canReissue && marchStuckTry[a.SN] < MARCH_STUCK_TRY_MAX) {
                marchStuckTry[a.SN]++;                                  // 升档：逐档加深退让（有上限，不退回 TC）
                ++marchRiseN;
                if (marchStuckTry[a.SN] >= 2) ++marchRiseGe2;           // ★ 活锁下此值恒 0（永久只到 1 档）
                if (marchStuckTry[a.SN] > marchStuckMax) marchStuckMax = marchStuckTry[a.SN];
            }
""")
cpp = sub1(cpp, c5_old, c5_new, 'C5 升档上限+诊断')

# ---------------- C6：清档计数
c6_old = S("""                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0; // 并清卡死档，回正常寻路
""")
c6_new = S("""                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0; // 并清卡死档，回正常寻路
                ++marchClearN;                                          // ★ 只读诊断：真进展清档次数
""")
cpp = sub1(cpp, c6_old, c6_new, 'C6 清档计数')

# ---------------- C7：诊断变量声明
c7_old = S("""    static long long twArmyFrames = 0, twChance12 = 0, twChance30 = 0, twBias = 0;
""")
c7_new = S("""    static long long twArmyFrames = 0, twChance12 = 0, twChance30 = 0, twBias = 0;
    // ★★★ 2026-09-28 只读诊断（验证「卡死自救活锁」修复）★★★
    //   活锁特征：档位永远只到 1（退 1 格 → 朝退让点走 → 被误判脱困 → 清零 → 再退 1 格）。
    //   修复后应出现 >=2 档。验收判据 A：跑局后「其中>=2档」必须 > 0。
    //   验收判据 B：胜负零回归（对拍基线 map2 24 局 = 17胜/4负/3未决 = 70.8%）。
    static long long marchRiseN = 0, marchRiseGe2 = 0, marchClearN = 0;
    static int marchStuckMax = 0;
    bool marchSelfReported = false;
""")
cpp = sub1(cpp, c7_old, c7_new, 'C7 诊断变量')

# ---------------- C8：诊断打印（pass 循环内，每 1500 帧一档）
c8_old = S("""    for (int pass = 0; pass < 2 && marchCmds < maxMarchCmds; ++pass) {
        for (auto &a : infoPtr->armies) {
            if (a.Sort == AT_PRIEST) { priest = &a; continue; }
""")
c8_new = S("""    for (int pass = 0; pass < 2 && marchCmds < maxMarchCmds; ++pass) {
        // ★ 2026-09-28 只读诊断：自救退让档位分布（不参与任何决策；每 1500 帧一档）
        if (pass == 0 && frame % 1500 == 0 && !marchSelfReported) {
            marchSelfReported = true;
            DebugText(QString("[MARCH-SELF f=%1] 升档=%2 其中>=2档=%3 最高档=%4 真进展清档=%5")
                      .arg(frame).arg(marchRiseN).arg(marchRiseGe2).arg(marchStuckMax).arg(marchClearN));
        }
        for (auto &a : infoPtr->armies) {
            if (a.Sort == AT_PRIEST) { priest = &a; continue; }
""")
cpp = sub1(cpp, c8_old, c8_new, 'C8 诊断打印')

# ---------------- C9：头部机理注释同步
c9_old = S("""// 唯一退路 = 卡死时朝集结 TC 内缩 stuckTry 格重发。canReissue(30帧节流) 必须保留：每帧重发会刷新 marchCmdFrame
// ⇒ stuckTry 永不涨 ⇒ 卡死打转。   ⚠ marchGoal* = 本轮【实际下发点】：卡死判据必须以它为参照，否则退让会被误判为"更卡死"一路退回 TC。
""")
c9_new = S("""// 唯一退路 = 卡死时朝集结 TC 内缩 stuckTry 格重发。canReissue(30帧节流) 必须保留：每帧重发会刷新 marchCmdFrame
// ⇒ stuckTry 永不涨 ⇒ 卡死打转。
// ★★★ 2026-09-28 判据参照改锚（修自救活锁）★★★
//   原注："marchGoal*(本轮下发点) 必须作参照，否则退让会被误判为更卡死一路退回 TC" —— 该两难已解：
//     用 marchGoal* ⇒ 退让把目标挪近 ⇒ 单位朝退让点走 = 假进展 ⇒ 档位清零 ⇒ 活锁；
//     用最终目标 ⇒ 旧顾虑是"一路退回 TC"，现由 MARCH_MAX_BACK(8 格) 硬上限兜住。
//   ⇒ 参照 = targetDR/UR（最终推进目标，跨帧稳定）；退让时由 issueMarch 重锚为"退让点→最终目标"。
""")
cpp = sub1(cpp, c9_old, c9_new, 'C9 头部注释')

wr(CPP, cpp)
wr(CPP_H, cpp)
print('[OK] 方案2：%d 处替换成功，已写入 7g/7h' % 9)
