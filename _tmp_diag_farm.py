# -*- coding: utf-8 -*-
"""临时诊断补丁：在 findFarmSiteBest 里打印 TC 坐标 / 锚点集合 / 选中锚点与环号。
   验证完必须用 reverse() 还原。"""
import sys, io

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
    int bestBase = -1;                       // [DIAG-FF] 最优候选所属锚点索引
"""

B_OLD = """        if (d2 < bestD2) { bestD2 = d2; bx = nx; by = ny; }
"""
B_NEW = """        if (d2 < bestD2) { bestD2 = d2; bx = nx; by = ny; bestBase = base; }   // [DIAG-FF]
"""

C_OLD = """    if (bx < 0) return false;
    x = bx; y = by;
    return true;
}
"""
C_NEW = """    if (bx < 0) {
        // [DIAG-FF] 全候选被拒：打印锚点集合规模
        static int lastFF0 = -99999;
        if (frame - lastFF0 >= 60) {
            lastFF0 = frame;
            QString s0 = QString("[FARM-PICK-FAIL f=%1] tc=(%2,%3) NA=%4")
                         .arg(frame).arg(center->BlockDR).arg(center->BlockUR).arg(NA);
            for (int i = 0; i < NA && i < 10; ++i)
                s0 += QString(" (%1,%2)").arg(anchors[i].first).arg(anchors[i].second);
            DebugText(s0);
        }
        return false;
    }
    {
        // [DIAG-FF] 临时诊断：选中的锚点 / 环号 / 相对 TC 的环号
        int bbx = anchors[bestBase].first, bby = anchors[bestBase].second;
        int rr  = std::max(std::abs(bx - bbx), std::abs(by - bby));
        int tcR = std::max(std::abs(bx - anchors[0].first), std::abs(by - anchors[0].second));
        static int lastFF1 = -99999;
        if (frame - lastFF1 >= 60) {
            lastFF1 = frame;
            QString s1 = QString("[FARM-PICK f=%1] tc=(%2,%3) NA=%4")
                         .arg(frame).arg(center->BlockDR).arg(center->BlockUR).arg(NA);
            s1 += QString(" a0=(%1,%2) base=%3(%4,%5) r=%6 tcR=%7 -> (%8,%9)")
                  .arg(anchors[0].first).arg(anchors[0].second)
                  .arg(bestBase).arg(bbx).arg(bby).arg(rr).arg(tcR).arg(bx).arg(by);
            for (int i = 0; i < NA && i < 10; ++i)
                s1 += QString(" (%1,%2)").arg(anchors[i].first).arg(anchors[i].second);
            DebugText(s1);
        }
    }
    x = bx; y = by;
    return true;
}
"""

if REV:
    t = rep(A_NEW, A_OLD, 'A')
    t = rep(B_NEW, B_OLD, 'B')
    t = rep(C_NEW, C_OLD, 'C')
    print('REVERSED ok')
else:
    t = rep(A_OLD, A_NEW, 'A')
    t = rep(B_OLD, B_NEW, 'B')
    t = rep(C_OLD, C_NEW, 'C')
    print('PATCHED ok')

out = t.replace('\n', '\r\n') if crlf else t
open(P, 'wb').write(out.encode('utf-8'))
print('bytes=', len(out.encode('utf-8')))
