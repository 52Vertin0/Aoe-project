# -*- coding: utf-8 -*-
"""反攻探路最简化：删除步进/绕路，改为直达敌方基地附近目标点。"""
import sys

P = r'C:\new-aoe3.0.7g\UsrAI.cpp'
raw = open(P, 'r', encoding='utf-8', newline='').read()
NL = '\r\n'
if raw.replace(NL, '').find('\n') >= 0:
    print('MIXED EOL - abort'); sys.exit(1)
L = raw.split(NL)


def chk(n, key):
    if key not in L[n - 1]:
        print('MISMATCH at line %d, expect %r, got %r' % (n, key, L[n - 1][:90]))
        sys.exit(1)


# ---- 断言：6 处锚点必须精确命中 ----
chk(4440, '绕路兜底')
chk(4473, 'bestCX*BL + BL*0.5')
chk(4480, 'axisAlignedTry')
chk(4501, 'nextVisibleStep')
chk(4537, 'return findDetourWaypoint(fx, fy, tx, ty, wx, wy);')
chk(4538, '};')
chk(4540, 'isRanged')
chk(4693, '脱困航点')
chk(4696, 'auto marchWaypoint')
chk(4738, 'return findDetourWaypoint(fx, fy, targetDR, targetUR, wx, wy);')
chk(4739, '};')
chk(4741, '统一推进出口')
chk(4748, 'auto issueMarch')
chk(4770, '};')
chk(4808, 'AT_CHARIOT_ARCHER')
chk(4819, 'SCOUT STUCK')
chk(4825, '}')
chk(5266, 'if (canReissue) {')
chk(5276, 'MARCH STUCK] catapult')
chk(5280, '}')

new3 = [
    '    // 统一推进出口：直达敌方基地附近的目标点，交给引擎 7e 全图寻路（可穿越未探索区）。',
    '    //   ★ 2026-09-15 用户要求「反攻时探路不用步进或绕路，直接以敌方基地附近为目标点，实现尽量最简」：',
    '    //     已删除 marchWaypoint 扇形脱困 / nextVisibleStep 小步 / axisAlignedTry 轴向绕行 / findDetourWaypoint BFS 绕路。',
    '    //   canReissue（30 帧节流）必须保留：每帧重发同一目标会刷新 marchCmdFrame ⇒ stuckTry 永不涨 ⇒ 卡死打转。',
    '    auto issueMarch = [&](double fx, double fy, int sn, int sort, int stuckTry, bool canReissue) {',
    '        (void)fx; (void)fy; (void)sort; (void)stuckTry;',
    '        if (!canReissue) return;                 // 未到节流窗口：本帧静默，不重复下发',
    '        HumanMove(sn, targetDR, targetUR);       // 引擎完整寻路：直奔敌方基地附近目标点',
    '        marchCmdFrame[sn] = frame;',
    '    };',
]

new4 = [
    '            if ((a.Sort == AT_CHARIOT_ARCHER || a.Sort == AT_CAVALRY) &&',
    '                !enemyBaseScouted && enemySiegeSN == -1) {',
    '                issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);   // 先锋直插敌方基地方位',
    '                marchCmds++;',
    '                continue;',
    '            }',
]

new5 = [
    '                if (canReissue) {',
    '                    HumanMove(a.SN, targetDR, targetUR);   // 投石车：直达敌方基地附近目标点',
    '                    marchCmdFrame[a.SN] = frame;',
    '                }',
]

new6 = [
    '    // ★ 2026-09-15 直达推进的前提：目标点必须落在可走格上（非海/非林/非矿）。',
    '    //   敌建筑的块坐标可能压在资源堆或海格上，HumanMove 直达会被引擎拒 ⇒ 全军原地不动。',
    '    //   故就近（半径 ≤4 格，由内向外）吸附到最近可走格——一次性静态修正，不引入步进/绕路。',
    '    auto snapWalkable = [&](double &x, double &y) {',
    '        if (isPassableAt(x, y)) return;',
    '        for (int r = 1; r <= 4; ++r)',
    '            for (int dx = -r; dx <= r; ++dx)',
    '                for (int dy = -r; dy <= r; ++dy) {',
    '                    if (dx > -r && dx < r && dy > -r && dy < r) continue;   // 只扫该半径的外环',
    '                    double cx = x + dx * BL, cy = y + dy * BL;',
    '                    if (isPassableAt(cx, cy)) { x = cx; y = cy; return; }',
    '                }',
    '    };',
    '    snapWalkable(targetDR, targetUR);',
]

before = len(L)

# ---- 从后往前应用（行号 1-based；删除区间 [a,b] → L[a-1:b]）----
L[5265:5280] = new5          # 投石车推进分支
L[4807:4825] = new4          # 先锋探路分支
L[4740:4770] = new3          # issueMarch 重写
del L[4692:4740]             # marchWaypoint 整块（含注释与尾随空行）
L[4648:4648] = new6          # 段1 之后插入 snapWalkable
del L[4439:4539]             # findDetourWaypoint + axisAlignedTry + nextVisibleStep 整块

out = NL.join(L)
open(P, 'w', encoding='utf-8', newline='').write(out)
print('lines %d -> %d (%+d)' % (before, len(L), len(L) - before))
print('bytes %d' % len(out.encode('utf-8')))
