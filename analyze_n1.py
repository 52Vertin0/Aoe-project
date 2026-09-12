# -*- coding: utf-8 -*-
# map2 探路期敌情闸（n1 批 12 局）vs 改动前同图 z2 批（3 局）
import glob, re, os, sys

def fr_of(line):
    m = re.match(r'[^|]*\|\s*(\d+)\s*\|', line)
    return int(m.group(1)) if m else None

def first_frame(path, needle, start=0):
    for l in open(path, errors='replace'):
        if needle in l:
            f = fr_of(l)
            if f is not None and f >= start:
                return f
    return None

def analyze(tag):
    b = tag
    win = False
    if os.path.exists(b + '.jsonl'):
        for l in open(b + '.jsonl', errors='replace'):
            if '"win":true' in l:
                win = True; break
    death = first_frame(b + '.ait', 'DEFEAT: Priest killed')
    last = None
    with open(b + '.ait', errors='replace') as fh:
        for l in fh:
            f = fr_of(l)
            if f is not None: last = f
    res = 'WIN' if win else ('LOSS' if death is not None else 'UND')
    sbrk = first_frame(b + '.ait', 'SCOUT-BREAK')
    w1 = first_frame(b + '.ait', 'WAVE 1 INCOMING')
    lock = first_frame(b + '.ait', 'PRIEST GUARD] LOCKED-ON')
    mil = None
    for l in open(b + '.ait', errors='replace'):
        if 'Mil:' in l:
            mm = re.search(r'Mil:\s*(\d+)', l)
            if mm and int(mm.group(1)) > 0:
                mil = fr_of(l); break
    nst = sum(1 for l in open(b + '.ait', errors='replace') if 'Priest st=' in l)
    nadv = sum(1 for l in open(b + '.ait', errors='replace') if 'Priest ADVANCE to Siege' in l)
    nconv = sum(1 for l in open(b + '.ait', errors='replace') if 'Priest converting Siege Workshop' in l)
    return dict(tag=b, res=res, death=death, last=last, sbrk=sbrk, w1=w1,
                lock=lock, mil=mil, nst=nst, adv=nadv, conv=nconv)

def show(rows, title):
    print('=== %s ===' % title)
    print('%-6s %-5s %8s %8s %9s %8s %8s %8s %6s %5s %5s' % (
        'game','res','death','last','SCOUT-BRK','WAVE1','1stLOCK','1stMil','Priest st','ADV','CONV'))
    for r in rows:
        print('%-6s %-5s %8s %8s %9s %8s %8s %8s %6d %5d %5d' % (
            r['tag'], r['res'],
            r['death'] if r['death'] is not None else '-',
            r['last'] if r['last'] is not None else '-',
            r['sbrk'] if r['sbrk'] is not None else '-',
            r['w1'] if r['w1'] is not None else '-',
            r['lock'] if r['lock'] is not None else '-',
            r['mil'] if r['mil'] is not None else '-',
            r['nst'], r['adv'], r['conv']))
    n = len(rows)
    w = sum(1 for r in rows if r['res'] == 'WIN')
    l = sum(1 for r in rows if r['res'] == 'LOSS')
    u = sum(1 for r in rows if r['res'] == 'UND')
    dead = sum(1 for r in rows if r['death'] is not None)
    early = sum(1 for r in rows if r['death'] is not None and r['death'] < 5000)
    earlyall = sum(1 for r in rows if r['last'] is not None and r['last'] < 5000 and r['res'] != 'WIN')
    w1n = sum(1 for r in rows if r['w1'] is not None)
    print('  n=%d  胜/负/未决=%d/%d/%d  胜率=%.1f%%  祭司死亡=%d  早死(<5000)=%d  WAVE1出现=%d/%d\n' % (
        n, w, l, u, 100.0*w/n, dead, early, w1n, n))

n1 = sorted(glob.glob('n1[0-9][0-9].ait'))
rows_n1 = [analyze(f[:-4]) for f in n1]
show(rows_n1, 'n1 批（探路期敌情闸，map2, 12局）')

z2 = sorted(glob.glob('z2[0-9][0-9].ait'))
if z2:
    rows_z2 = [analyze(f[:-4]) for f in z2]
    show(rows_z2, 'z2 批（改动前同图 map2, 3局）')
else:
    print('(z2 批文件不存在)')
