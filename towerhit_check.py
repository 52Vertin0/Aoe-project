# -*- coding: utf-8 -*-
"""towerhit 轮核对：仅复合弓兵应直接攻击箭塔；战车弓/弓兵/投石兵-slinger 应仍不打塔。
对比 th(仅复合弓可打塔) vs sz(全禁打塔的 shrink 版) 两批 ait 日志的 [TOWER-TGT]/[TOWER-SKIP] 标签 + 精确结局。
结局判定（依 MEMORY 铁律）：胜 = 'VICTORY!'；负 = 'DEFEAT:'（必须带冒号）。
"""
import io, re

TAG = re.compile(r'\[(TOWER-(?:TGT|SKIP))[^\]]*\]\s+(\S+)')

def parse(p):
    tgt, skip = {}, {}
    win = priest_dead = False
    for line in io.open(p, encoding='utf-8', errors='replace'):
        if 'VICTORY!' in line: win = True
        if 'DEFEAT:' in line and ('Priest' in line or '祭司' in line or 'killed' in line.lower()):
            priest_dead = True
        m = TAG.search(line)
        if m:
            tag, who = m.group(1), m.group(2)
            (tgt if tag == 'TOWER-TGT' else skip)[who] = (tgt if tag == 'TOWER-TGT' else skip).get(who, 0) + 1
    return tgt, skip, win, priest_dead

def batch(pre):
    return {i: (parse('%s%d.ait' % (pre, i)) if __import__('os').path.exists('%s%d.ait' % (pre, i)) else (None,)*4)
            for i in range(1, 9)}

def show(pre, b, label):
    print('=== %s (%s) ===' % (pre, label))
    for i in range(1, 9):
        tgt, skip, win, pd = b[i]
        if tgt is None:
            print('  %d MISSING' % i); continue
        t = ','.join('%s×%d' % (k, v) for k, v in sorted(tgt.items())) or '-'
        s = ','.join('%s×%d' % (k, v) for k, v in sorted(skip.items())) or '-'
        print('  %d  TGT[%-18s] SKIP[%-18s] 胜=%s 祭司死=%s' % (i, t, s, win, pd))
    print()

th = batch('th'); sz = batch('sz')
show('th', th, '仅复合弓可打塔')
show('sz', sz, '全禁打塔(shrink版)')

def tot(b, key):
    return sum((b[i][0] or {}).get(key, 0) for i in range(1, 9))
print('【汇总】复合弓兵/远程 打塔总次数:  th=%d  sz=%d' % (tot(th, '复合弓兵/远程'), tot(sz, '复合弓兵/远程')))
print('【汇总】近战 打塔总次数:          th=%d  sz=%d' % (tot(th, '近战'), tot(sz, '近战')))
print('【汇总】胜局数:                   th=%d/8  sz=%d/8' % (
    sum(1 for i in range(1,9) if th[i][2]), sum(1 for i in range(1,9) if sz[i][2])))
