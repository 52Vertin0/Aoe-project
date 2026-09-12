# -*- coding: utf-8 -*-
# 下一瓶颈诊断：把各局按 胜/负/未决 分组，比较 Mil 峰值 / 黄金供给 / 经济规模 / 反攻时机
import glob, re, os, sys

def fr(line):
    m = re.match(r'[^|]*\|\s*(\d+)\s*\|', line)
    return int(m.group(1)) if m else None

def analyze(tag):
    p = tag + '.ait'
    win = False
    j = tag + '.jsonl'
    if os.path.exists(j):
        for l in open(j, errors='replace'):
            if '"win":true' in l: win = True; break
    death = None; last = 0
    milMax = 0; gdMax = 0; gdN = 0; upgN = 0
    frmMax = 0
    aw = None; adv1 = None; conv1 = None
    ecoWood = 0
    for l in open(p, errors='replace'):
        f = fr(l)
        if f is None: continue
        if f > last: last = f
        if 'DEFEAT: Priest killed' in l and death is None: death = f
        if 'Mil:' in l:
            m = re.search(r'Mil:\s*(\d+)', l)
            if m: milMax = max(milMax, int(m.group(1)))
        if 'UPG' in l and 'Fd:' in l:
            upgN += 1
            m = re.search(r'Gd:\s*(\d+)', l)
            if m:
                g = int(m.group(1))
                if g > 0: gdN += 1
                gdMax = max(gdMax, g)
            m2 = re.search(r'Frm:\s*(\d+)', l)
            if m2: frmMax = max(frmMax, int(m2.group(1)))
        if 'ALL WAVES DEFEATED' in l and aw is None: aw = f
        if 'Priest ADVANCE to Siege' in l and adv1 is None: adv1 = f
        if 'Priest converting Siege Workshop' in l and conv1 is None: conv1 = f
    res = 'WIN' if win else ('LOSS' if death is not None else 'UND')
    return dict(tag=tag, res=res, last=last, death=death, milMax=milMax,
                gdMax=gdMax, gdRate=(100.0*gdN/upgN if upgN else 0), frmMax=frmMax,
                aw=aw, adv1=adv1, conv1=conv1)

def group(rows, name):
    print('=== %s ===' % name)
    print('%-6s %-5s %8s %8s %7s %7s %8s %9s %8s' % (
        'game','res','Mil峰值','Gd峰值','Gd非零%','Frm峰值','反攻起','首前出','首感化'))
    for r in rows:
        g = lambda v: v if v is not None else '-'
        print('%-6s %-5s %8d %8d %6.0f%% %7d %8s %9s %8s' % (
            r['tag'], r['res'], r['milMax'], r['gdMax'], r['gdRate'], r['frmMax'],
            g(r['aw']), g(r['adv1']), g(r['conv1'])))
    for grp in ['WIN','LOSS','UND']:
        sel = [r for r in rows if r['res'] == grp]
        if not sel: continue
        n = len(sel)
        mil = sum(r['milMax'] for r in sel)/n
        gd = sum(r['gdMax'] for r in sel)/n
        gdr = sum(r['gdRate'] for r in sel)/n
        frm = sum(r['frmMax'] for r in sel)/n
        print('  %-4s n=%-3d Mil峰值均值=%5.1f  Gd峰值均值=%5.1f  Gd非零率均值=%4.0f%%  村民峰值均值=%5.1f' % (
            grp, n, mil, gd, gdr, frm))
    print()

allrows = []
for pre in ['n2','n4','n5','g1']:
    fs = sorted(glob.glob(pre + '[0-9][0-9].ait'))
    if fs:
        rows = [analyze(f[:-4]) for f in fs]
        group(rows, '%s 批（%d 局）' % (pre, len(rows)))
        allrows += rows
group(allrows, '全部合并（%d 局）' % len(allrows))
