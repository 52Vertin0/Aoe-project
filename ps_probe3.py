# -*- coding: utf-8 -*-
"""量化 ps 批里 alive(=敌活军队) 与 towers(=敌塔) 的分布：
回答"敌方士兵全灭"是否真可达、「箭塔全拆」是否不可达。
口径：SIEGE-WAIT 行直接带 alive=/towers=；另外用引擎事件独立算敌塔被拆数。
"""
import io, os, re

# SIEGE-WAIT 行: alive=0 towers=4
PAT_WAIT = re.compile(r'\[SIEGE-WAIT f=\d+\] hp=([\d.]+) clearOk=\d+ alive=(\d+) towers=(\d+) dS=([\d.]+)')

print('=== ps 批 [SIEGE-WAIT] 明细（每局最多列 6 条）===')
for i in range(1, 9):
    p = 'ps%d.ait' % i
    if not os.path.exists(p):
        continue
    waits = []
    for ln in io.open(p, encoding='utf-8', errors='replace'):
        q = ln.split('|')
        if len(q) < 5:
            continue
        m = PAT_WAIT.search(q[4])
        if m:
            f = q[1].strip()
            waits.append((f, m.group(2), m.group(3), m.group(4)))
    print('ps%d: WAIT %d 条' % (i, len(waits)))
    for w in waits[:6]:
        print('    f=%-6s alive=%-3s towers=%-3s dS=%s' % w)

print()
print('=== 各批次 敌塔被【我方】拆掉 的次数（引擎事件）===')
# "玩家 摧毁箭塔" = 我方拆敌塔；"敌方 摧毁箭塔" = 我方塔被拆
for batch in ('th', 'ps'):
    tot_p = tot_e = 0
    print('--- %s ---' % batch)
    for i in range(1, 9):
        p = '%s%d.ait' % (batch, i)
        if not os.path.exists(p):
            continue
        txt = io.open(p, encoding='utf-8', errors='replace').read()
        mp = txt.count('玩家 摧毁箭塔')
        me = txt.count('敌方 摧毁箭塔')
        tot_p += mp; tot_e += me
        print('  %s%d: 我方拆敌塔=%d  我方塔被拆=%d' % (batch, i, mp, me))
    print('  >> 合计 我方拆敌塔=%d, 我方塔被拆=%d' % (tot_p, tot_e))
