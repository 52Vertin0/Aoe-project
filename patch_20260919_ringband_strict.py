# -*- coding: utf-8 -*-
"""
2026-09-19 环带收紧：ringOf 的 `n = 2*r + 3` -> `2*r + 1`，只留真 Chebyshev 紧邻环。
证据：fc 批 87 次落位里 4 次（4.8%）、ff4 里 1/12 落在 r=5/6 —— 坐标形如 (24,14)/(25,14)/(24,22)/(23,23)，
      相对锚点 Δ=(r+1, r) 或 (r+2, r)，正是"轴向多伸 2 格"越过角点的产物。
     这些格子仍满足"离建筑 ≥1 格"，但不在紧邻环上，与用户选定的「只许紧邻环」不符。
独立性：只改环带宽度，不碰锚点集合（与 granary-only 补丁可分别回滚）。
用法：python patch_...py [--dry]
"""
import sys

P = r'C:\new-aoe3.0.7g\UsrAI.cpp'
DRY = '--dry' in sys.argv


def rep(text, old, new, tag):
    o = old.replace('\r\n', '\n').replace('\n', '\r\n')
    n = new.replace('\r\n', '\n').replace('\n', '\r\n')
    c = text.count(o)
    if c != 1:
        raise SystemExit('[FAIL] %s 命中 %d 次（期望 1）' % (tag, c))
    return text.replace(o, n)


raw = open(P, 'rb').read().decode('utf-8')

old = '''    // 锚点外 r 环的 4 条带（上/下/左/右）；几何与旧 findFarmRingSite 一致（3x3 + 隔 1 格 ⇒ r>=4）
    auto ringOf = [&](int ax, int ay, int r, bool useBlack, int base) {
        const int n = 2 * r + 3;'''
new = '''    // 锚点外 r 环的 4 条带（上/下/左/右）—— 真 Chebyshev 环（3x3 + 隔 1 格 ⇒ r>=4）
    //   ★ 2026-09-19 收紧：原 `n = 2*r + 3` 让每条带在轴向【多伸 2 格】⇒ 越过角点、溢出到
    //     Chebyshev r+1 / r+2 的格子。实测：fc 批 87 次落位里 4 次（4.8%）、ff4 里 1/12 落在
    //     r=5/6，坐标 (24,14)/(25,14)/(24,22)/(23,23) = 相对锚点 Δ=(r+1,r) / (r+2,r)。
    //     这些格子虽然也满足"离建筑 ≥1 格"，但**不在紧邻环上**，与用户选定的「只许紧邻环」不符。
    //   改为 `n = 2*r + 1` ⇒ k∈[0,2r] ⇒ 轴向偏移 ∈ [-r,+r] ⇒ Chebyshev 距离恰为 r。
    //   ⚠ 四角会被相邻两条带各枚举一次（重复无害：consider 只做评估，不落位）。
    auto ringOf = [&](int ax, int ay, int r, bool useBlack, int base) {
        const int n = 2 * r + 1;'''
raw = rep(raw, old, new, 'R1 环带宽度')

if DRY:
    print('[DRY] R1 命中 1 次，未落盘')
else:
    open(P, 'wb').write(raw.encode('utf-8'))
    print('[OK] 已落盘，bytes=%d lines=%d' % (len(raw.encode('utf-8')), raw.count('\n')))
