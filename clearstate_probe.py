# -*- coding: utf-8 -*-
"""探查：本图(tc/sz/th 共32局)里"敌方军队全灭 + 箭塔全拆"这一全局状态是否出现过、出现多晚。
判据来源：ait 日志中的引擎事件。
  - 敌方单位阵亡 -> "XX阵亡" / 引擎红色事件；用 DebugText 记录？
  - 更可靠：用 [SIEGE-HOLD]/[LC-DBG]/[TOWER-TGT] 里的 towers= 列看敌塔剩余。
先做粗粒度探查：统计每局的 towers 列最小值（=曾探明的敌塔数最小值）。
"""
import io, os, re, glob

TAG_LC = re.compile(r'\[LC-DBG f=(\d+)\].*?towers=(\d+) nearT=([-\d.]+)')
TAG_TGT = re.compile(r'\[TOWER-TGT f=(\d+)\]')
TAG_HOLD = re.compile(r'\[SIEGE-HOLD f=(\d+)\] hp=([\d.]+) nearT=([-\d.]+) towers=(\d+)')

rows = []
for batch in ('tc', 'sz', 'szb', 'th'):
    for i in range(1, 9):
        p = '%s%d.ait' % (batch, i)
        if not os.path.exists(p):
            continue
        lines = io.open(p, encoding='utf-8', errors='replace').read().splitlines()
        minTower = 999
        maxFrame = 0
        nHold = 0
        firstZeroTowerFrame = None
        for ln in lines:
            q = ln.split('|')
            if len(q) < 5:
                continue
            try:
                frame = int(q[1].strip())
            except Exception:
                continue
            maxFrame = max(maxFrame, frame)
            m = TAG_LC.search(q[4])
            if m:
                t = int(m.group(2))
                if t < minTower:
                    minTower = t
                if t == 0 and firstZeroTowerFrame is None:
                    firstZeroTowerFrame = frame
            m2 = TAG_HOLD.search(q[4])
            if m2:
                nHold += 1
                t = int(m2.group(4))
                if t < minTower:
                    minTower = t
        vic = any('VICTORY' in l for l in lines)
        de = any('DEFEAT:' in l for l in lines)
        rows.append((batch + str(i), maxFrame, minTower, nHold, firstZeroTowerFrame, vic, de))

print('%-7s %8s %9s %6s %12s %5s %5s' % ('局', '末帧', 'minTowers', 'HOLD数', '首见0塔帧', '胜', '负'))
print('-' * 62)
for r in rows:
    print('%-7s %8d %9s %6d %12s %5s %5s' % (
        r[0], r[1], ('-' if r[2] > 900 else r[2]), r[3],
        ('-' if r[4] is None else r[4]), 'Y' if r[5] else '', 'Y' if r[6] else ''))
