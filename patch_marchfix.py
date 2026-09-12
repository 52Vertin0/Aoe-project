# -*- coding: utf-8 -*-
"""反攻推进「卡死自救活锁」修复补丁（2026-09-28）

缺陷（活锁）：
  issueMarch 退让时把 marchIssueDist 重锚成"距【退让点】的距离"（语义=新一轮指令基准），
  而主判据只要"距下发点变近 >0.5BL"就 marchStuckTry=0。
  退让点本身被挪向我方 ⇒ 单位朝它走必然触发清零 ⇒
  每轮只从 0 升到 1、退完即"成功" ⇒ 永远升不到 2/3 档 ⇒ 单位被永久焊在卡死点。
  （铁律 9：脱困动作不得充数为进展。）

修法：
  ① 把卡死档位(marchStuckTry)清零的条件，从"距【下发点】变近"改为
     "距【最终推进目标】的净距离创新低"（新成员 marchToFinal）。
     退让必然远离最终目标 ⇒ 档位单调升 ⇒ 逐档加深退让直到绕开障碍；
     一旦真绕开、距离创新低 ⇒ 判脱困、清档。
  ② 退让距离加硬上限 MARCH_MAX_BACK（格），防止档位单调升时"一路退回 TC"。
  ③ 退让档位加上限 MARCH_STUCK_TRY_MAX。

换行：UsrAI.cpp 纯 LF、UsrAI.h CRLF（不可混）。
"""
import io, sys

CPP = r'C:\new-aoe3.0.7g\UsrAI.cpp'
HDR = r'C:\new-aoe3.0.7g\UsrAI.h'
CPP_H = r'C:\new-aoe3.0.7h\UsrAI.cpp'
HDR_H = r'C:\new-aoe3.0.7h\UsrAI.h'


def rd(p):
    with open(p, 'rb') as f:
        return f.read()


def wr(p, b):
    with open(p, 'wb') as f:
        f.write(b)


def S(txt, nl):
    """LF 文本 → 指定换行的 bytes"""
    if nl == b'\r\n':
        txt = txt.replace('\n', '\r\n')
    return txt.encode('utf-8')


def sub1(buf, old_b, new_b, tag):
    c = buf.count(old_b)
    if c != 1:
        raise SystemExit('[FAIL] %s: 命中 %d 次（要求 1）' % (tag, c))
    return buf.replace(old_b, new_b)


LF = b'\n'
CRLF = b'\r\n'

# ---------------------------------------------------------------- .cpp
cpp = rd(CPP)

# C1 常量：新增 march 卡死自救三项
c1_old = S("""#define PRIEST_ADV_CLEAR_MAX    3     // B 档单次最多挪走的友军数（保命：留其余护卫）
""", LF)
c1_new = S("""#define PRIEST_ADV_CLEAR_MAX    3     // B 档单次最多挪走的友军数（保命：留其余护卫）
// ★★★ 2026-09-28 反攻推进「卡死自救活锁」修复（manageCounterAttack / issueMarch）★★★
//   旧实现活锁：退让把【本轮下发点】挪向我方，而主判据只按"距下发点变近 >0.5 格"就
//   marchStuckTry=0 ⇒ 单位朝退让点走必然清零档位 ⇒ 每轮只退 1 格、"退完即成功"
//   ⇒ 永远升不到 2/3 档 ⇒ 卡死单位被永久焊在原地（铁律 9：脱困动作不得充数为进展）。
//   现改为：只有"距【最终推进目标】的净距离创新低"才算进展、才清零档位。
#define MARCH_STUCK_FRAMES  90     // 距最终目标连续 N 帧无新低 ⇒ 判卡死（≈3.6 秒@25fps，原硬编码 90）
#define MARCH_MAX_BACK      8.0    // 自救退让距离上限(格)：档位单调升时防"一路退回 TC"
#define MARCH_STUCK_TRY_MAX 8      // 退让档位上限（8 档 × 1 格 = 8 格，与 MARCH_MAX_BACK 对应）
""", LF)
cpp = sub1(cpp, c1_old, c1_new, 'C1 常量')

# C2 issueMarch：退让距离加硬上限
c2_old = S("""            double back = (d > BL) ? ((stuckTry * BL < d - BL) ? stuckTry * BL : d - BL) : 0.0;
            if (d > 1e-6) { mx -= dx / d * back; my -= dy / d * back; }
""", LF)
c2_new = S("""            double back = (d > BL) ? ((stuckTry * BL < d - BL) ? stuckTry * BL : d - BL) : 0.0;
            if (back > MARCH_MAX_BACK * BL) back = MARCH_MAX_BACK * BL;   // ★ 2026-09-28 退让上限：档位单调升时防"一路退回 TC"
            if (d > 1e-6) { mx -= dx / d * back; my -= dy / d * back; }
""", LF)
cpp = sub1(cpp, c2_old, c2_new, 'C2 issueMarch 退让上限')

# C3+C4 主判据拆两路（含 ATTACKING 分支）
c3_old = S("""            const double gDR = marchGoalDR.count(a.SN) ? marchGoalDR[a.SN] : targetDR;
            const double gUR = marchGoalUR.count(a.SN) ? marchGoalUR[a.SN] : targetUR;
            const double curDistToTgt = calDistance(a.DR, a.UR, gDR, gUR);   // ★ 参照 = 本轮实际下发点
            if (!marchIssueDist.count(a.SN)) {          // 首次见到→建立基准
                marchIssueDist[a.SN] = curDistToTgt;
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
            } else if (marchIssueDist[a.SN] - curDistToTgt > 0.5 * BL) {
                marchIssueDist[a.SN] = curDistToTgt;    // 朝目标靠近了→刷新基准
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0; // 并清卡死档，回正常寻路
            }
            // ⚠ ATTACKING(正在开火)绝不算卡死：投石车/弓兵按最大射程站桩输出时本就不位移，   若计入卡死，90帧后会被拽走去移动，直接破坏投石车的 standoff 输出。
            // 这里同时刷新基准，使其停火后重新计时而非立刻被判卡死。
            if (a.NowState == HUMAN_STATE_ATTACKING) {
                marchIssueDist[a.SN] = curDistToTgt;
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
            }
""", LF)
c3_new = S("""            // ★★★ 2026-09-28 卡死判据拆两路（修「自救活锁」，铁律 9）★★★
            //   ① marchIssueDist = 距【本轮下发点】：只判"这条指令走完没有"（逼近即重锚该基准）。
            //      ⛔ 绝不用它清零档位 —— 自救退让把下发点挪向我方后，"朝退让点走"会被记成脱困。
            //   ② marchToFinal   = 距【最终推进目标 targetDR/UR】的历史最优值：只有它被刷新才算真进展，
            //      也只有它清零 marchStuckTry。退让必然远离最终目标 ⇒ 档位单调升 ⇒ 逐档加深直到绕开障碍。
            //      （旧实现在此用 marchIssueDist 清零 ⇒ 每轮从 0 退到 1、退完即"成功" ⇒ 永久焊死。）
            const double curToFinal = calDistance(a.DR, a.UR, targetDR, targetUR);
            bool realProgress = false;
            if (!marchToFinal.count(a.SN)) {
                marchToFinal[a.SN] = curToFinal;                        // 首次见到→建立最优基准
            } else if (marchToFinal[a.SN] - curToFinal > 0.5 * BL) {
                marchToFinal[a.SN] = curToFinal;                        // 距最终目标创新低 = 真的在推进
                realProgress = true;
            }
            const double gDR = marchGoalDR.count(a.SN) ? marchGoalDR[a.SN] : targetDR;
            const double gUR = marchGoalUR.count(a.SN) ? marchGoalUR[a.SN] : targetUR;
            const double curDistToTgt = calDistance(a.DR, a.UR, gDR, gUR);   // ★ 参照 = 本轮实际下发点
            if (!marchIssueDist.count(a.SN)) {          // 首次见到→建立基准
                marchIssueDist[a.SN] = curDistToTgt;
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
            } else if (marchIssueDist[a.SN] - curDistToTgt > 0.5 * BL) {
                marchIssueDist[a.SN] = curDistToTgt;    // 逼近本轮下发点→重锚"指令"基准
                if (realProgress) {                     // ★ 仅当真朝最终目标推进，才算脱困成功、清档
                    marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
                }
            }
            // ⚠ ATTACKING(正在开火)绝不算卡死：投石车/弓兵按最大射程站桩输出时本就不位移，   若计入卡死，90帧后会被拽走去移动，直接破坏投石车的 standoff 输出。
            // 这里同时刷新基准，使其停火后重新计时而非立刻被判卡死。
            if (a.NowState == HUMAN_STATE_ATTACKING) {
                marchIssueDist[a.SN] = curDistToTgt;
                marchToFinal[a.SN] = curToFinal;        // ★ 同步最优基准：停火后从当前位置重新起算，避免被当"远离"而误升档
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
            }
""", LF)
cpp = sub1(cpp, c3_old, c3_new, 'C3 主判据拆两路')

# C5 stuckNow 用常量 + 升档加上限
c5_old = S("""            bool stuckNow = (frame - marchMoveFrame[a.SN] > 90);        // 90帧无位移→判定卡死
            bool canReissue = !marchCmdFrame.count(a.SN) ||
                              (frame - marchCmdFrame[a.SN] >= 30);      // 30帧节流，防每帧换方向抖动
            if (stuckNow && canReissue) marchStuckTry[a.SN]++;          // 升档：换个方向试
""", LF)
c5_new = S("""            bool stuckNow = (frame - marchMoveFrame[a.SN] > MARCH_STUCK_FRAMES);  // 距最终目标无新低→判卡死
            bool canReissue = !marchCmdFrame.count(a.SN) ||
                              (frame - marchCmdFrame[a.SN] >= 30);      // 30帧节流，防每帧换方向抖动
            if (stuckNow && canReissue && marchStuckTry[a.SN] < MARCH_STUCK_TRY_MAX)
                marchStuckTry[a.SN]++;                                  // 升档：逐档加深退让（有上限，不退回 TC）
""", LF)
cpp = sub1(cpp, c5_old, c5_new, 'C5 stuckNow/升档')

# C6 头部机理注释同步（5052-5055 那段"唯一退路/参照"说明）
c6_old = S("""// 统一推进出口：直达敌方基地附近目标点，交给引擎全图寻路（可穿越未探索区）。
// ★ 2026-09-15 用户要求「不用步进或绕路」：已删 marchWaypoint/nextVisibleStep/axisAlignedTry/findDetourWaypoint。
// 唯一退路 = 卡死时朝集结 TC 内缩 stuckTry 格重发。canReissue(30帧节流) 必须保留：每帧重发会刷新 marchCmdFrame
// ⇒ stuckTry 永不涨 ⇒ 卡死打转。   ⚠ marchGoal* = 本轮【实际下发点】：卡死判据必须以它为参照，否则退让会被误判为"更卡死"一路退回 TC。
""", LF)
c6_new = S("""// 统一推进出口：直达敌方基地附近目标点，交给引擎全图寻路（可穿越未探索区）。
// ★ 2026-09-15 用户要求「不用步进或绕路」：已删 marchWaypoint/nextVisibleStep/axisAlignedTry/findDetourWaypoint。
// 唯一退路 = 卡死时朝集结 TC 内缩 stuckTry 格重发。canReissue(30帧节流) 必须保留：每帧重发会刷新 marchCmdFrame
// ⇒ stuckTry 永不涨 ⇒ 卡死打转。
// ★★★ 2026-09-28 判据参照改锚（修自救活锁）★★★
//   修订：marchGoal*（本轮【实际下发点】）只用于【下发指令】，**不再**作卡死判据参照。
//   旧两难：用 marchGoal* ⇒ 退让把自己目标挪近 ⇒ 单位朝退让点走被记成"前进" ⇒ 档位清零 ⇒ 活锁；
//            用最终目标 ⇒ 退让被记成"更卡死" ⇒ 一路退回 TC。
//   现解：① 进展判据 = 距【最终目标】的历史最优值(marchToFinal)，退让远离目标 ⇒ 档位单调升；
//         ② 退让距离硬上限 MARCH_MAX_BACK ⇒ 不会"一路退回 TC"。两难同时解除。
""", LF)
cpp = sub1(cpp, c6_old, c6_new, 'C6 头部注释')

# ---------------------------------------------------------------- .h
hdr = rd(HDR)
h_old = S("""    std::map<int,double> marchIssueDist;
""", CRLF)
h_new = S("""    std::map<int,double> marchIssueDist;
    // ★★★ 2026-09-28 反攻推进「卡死自救活锁」修复：距【最终推进目标 targetDR/UR】的历史最优距离。
    //   marchStuckTry 现在只由本字段刷新来清零 —— 不能用 marchIssueDist 清零：
    //   自救退让会把【本轮下发点】挪向我方，单位"朝退让点走"就会被记成"在前进"
    //   ⇒ 档位每轮清零 ⇒ 永远只退 1 格 ⇒ 单位被永久焊在卡死点（铁律 9：脱困动作不得充数为进展）。
    std::map<int,double> marchToFinal;
""", CRLF)
hdr = sub1(hdr, h_old, h_new, 'H1 marchToFinal 声明')

# ---------------------------------------------------------------- 写出（7g + 7h）
wr(CPP, cpp)
wr(CPP_H, cpp)
wr(HDR, hdr)
wr(HDR_H, hdr)
print('[OK] 全部 %d 处替换成功，已写入 7g/7h 两份副本' % 7)
