# -*- coding: utf-8 -*-
"""永久保留的农场落位机制量日志（替代临时诊断）。

为什么需要：只靠 [BUILD-ISSUE] 无法还原锚点集合 —— 实测本图存在 (13,34)/(23,32) 这类
**不经 tryBuild** 的谷仓/仓库(地图预置或初始建筑)，日志里没有它们的建造记录 ⇒
从外部反推锚点必然漏算，验收会误判「越界」。
直接在落位点打印「选中锚点 + 环号 + 相对 TC 环号」= 100% 精确的机制量。

格式（无节流，每落位一条，约 15~20 条/局）：
  [FARM-PICK f=%1] base=%2(%3,%4) r=%5 tcR=%6 -> (%7,%8)
    base = 锚点索引（0=TC，>=1=谷仓/仓库）
    r    = 相对该锚点的切比雪夫距离（设计上恒 = FARM_ANCHOR_R_MIN = 4）
    tcR  = 相对 TC 的切比雪夫距离（判断"是否外溢"用）
"""
import sys

P = r'C:\new-aoe3.0.7g\UsrAI.cpp'
raw = open(P, 'rb').read().decode('utf-8')
crlf = raw.count('\r\n') > 0
t = raw.replace('\r\n', '\n')

REV = '--reverse' in sys.argv


def rep(old, new, tag):
    n = t.count(old)
    assert n == 1, (tag, 'hits=%d' % n)
    return t.replace(old, new)


A_OLD = """    double bestD2 = 1e18;                    // 距离平方（避免 sqrt）
    int bx = -1, by = -1;
"""
A_NEW = """    double bestD2 = 1e18;                    // 距离平方（避免 sqrt）
    int bx = -1, by = -1;
    int bestBase = -1;                       // 最优候选所属锚点索引（0=TC）—— 供落位日志使用
"""

B_OLD = """        if (d2 < bestD2) { bestD2 = d2; bx = nx; by = ny; }
"""
B_NEW = """        if (d2 < bestD2) { bestD2 = d2; bx = nx; by = ny; bestBase = base; }
"""

C_OLD = """    if (bx < 0) return false;
    x = bx; y = by;
    return true;
}
"""
C_NEW = """    if (bx < 0) return false;
    // ★ 2026-09-19 农场落位机制量（不受采样影响，最可靠）：选中锚点索引 / 环号 / 相对 TC 环号
    //   r 设计上恒 = FARM_ANCHOR_R_MIN = 4（紧邻环）；tcR 用于判定是否外溢（谷仓环天然很大）。
    {
        int bbx = anchors[bestBase].first, bby = anchors[bestBase].second;
        int rr  = std::max(std::abs(bx - bbx), std::abs(by - bby));
        int tcR = std::max(std::abs(bx - anchors[0].first), std::abs(by - anchors[0].second));
        DebugText(QString("[FARM-PICK f=%1] base=%2(%3,%4) r=%5 tcR=%6 -> (%7,%8)")
                  .arg(frame).arg(bestBase).arg(bbx).arg(bby).arg(rr).arg(tcR).arg(bx).arg(by));
    }
    x = bx; y = by;
    return true;
}
"""

if REV:
    t = rep(C_NEW, C_OLD, 'C')
    t = rep(B_NEW, B_OLD, 'B')
    t = rep(A_NEW, A_OLD, 'A')
    print('REVERSED ok')
else:
    t = rep(A_OLD, A_NEW, 'A')
    t = rep(B_OLD, B_NEW, 'B')
    t = rep(C_OLD, C_NEW, 'C')
    print('PATCHED ok')

out = t.replace('\n', '\r\n') if crlf else t
open(P, 'wb').write(out.encode('utf-8'))
print('bytes=', len(out.encode('utf-8')))
