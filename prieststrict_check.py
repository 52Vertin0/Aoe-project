# -*- coding: utf-8 -*-
"""prieststrict 核对：全局清场闸（敌全灭+塔全拆）对感化武器厂的影响。
对照 ps1-8（全局闸）vs th1-8（局部清场）。
指标：
  - 感化令次数 path=early / path=front / path=legacy
  - [SIEGE-WAIT] 计数（新闸挡下的次数）—— 只在全局版有
  - [SIEGE-HOLD] 计数（旧的残血+塔近保护）
  - 结局 VICTORY / DEFEAT / timeout
  - 活敌军队数 & 敌塔数的全局最小值（看闸是否曾满足）
"""
import io, os, re

PAT_CONV = re.compile(r'Priest converting Siege Workshop')
PAT_PATH = re.compile(r'path=(early|front|legacy)')
PAT_WAIT = re.compile(r'\[SIEGE-WAIT')
PAT_HOLD = re.compile(r'\[SIEGE-HOLD')
PAT_LC = re.compile(r'\[LC-DBG f=(\d+)\].*?towers=(\d+)')

def analyze(p):
    lines = io.open(p, encoding='utf-8', errors='replace').read().splitlines()
    conv = 0; pe = pf = pl = 0; wait = 0; hold = 0
    maxf = 0
    for ln in lines:
        q = ln.split('|')
        if len(q) < 5:
            continue
        try:
            f = int(q[1].strip())
        except Exception:
            continue
        if f > maxf: maxf = f
        msg = q[4]
        if PAT_CONV.search(msg):
            conv += 1
            m = PAT_PATH.search(msg)
            if m:
                if m.group(1) == 'early': pe += 1
                elif m.group(1) == 'front': pf += 1
                else: pl += 1
        if PAT_WAIT.search(msg): wait += 1
        if PAT_HOLD.search(msg): hold += 1
    vic = any('VICTORY' in l for l in lines)
    de = any('DEFEAT:' in l for l in lines)
    out = 'VICTORY' if vic else ('DEFEAT' if de else 'timeout')
    return maxf, conv, pe, pf, pl, wait, hold, out

for batch, label in (('th', '局部清场(旧)'), ('ps', '全局清场(新)')):
    print('=== %s ===' % label)
    print('%-6s %8s %6s %6s %6s %6s %6s %6s %9s' % ('局', '末帧', '感化', 'early', 'front', 'legacy', 'WAIT', 'HOLD', '结局'))
    tv = tc = tw = 0
    for i in range(1, 9):
        p = '%s%d.ait' % (batch, i)
        if not os.path.exists(p):
            print('%-6s (缺)' % (batch + str(i)))
            continue
        r = analyze(p)
        print('%-6s %8d %6d %6d %6d %6d %6d %6d %9s' % (batch + str(i), r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]))
        tc += r[1]; tw += r[5]
        if r[7] == 'VICTORY': tv += 1
    print('  >> 合计: 感化 %d 次, WAIT %d 次, 胜 %d/8' % (tc, tw, tv))
    print()
