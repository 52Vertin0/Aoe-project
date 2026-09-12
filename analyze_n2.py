# -*- coding: utf-8 -*-
# map2 探路半径 100→40（n2 批 12 局）vs 敌情闸（n1 12 局）vs 改动前（z2 3 局）
import glob, re, os, sys, math

def fr_of(line):
    m = re.match(r'[^|]*\|\s*(\d+)\s*\|', line)
    return int(m.group(1)) if m else None

def first_frame(path, needle):
    for l in open(path, errors='replace'):
        if needle in l:
            f = fr_of(l)
            if f is not None:
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
    last = None; nst = 0; adv = 0; conv = 0
    moves = []
    for l in open(b + '.ait', errors='replace'):
        f = fr_of(l)
        if f is not None: last = f
        if 'Priest st=' in l: nst += 1
        if 'Priest ADVANCE to Siege' in l: adv += 1
        if 'Priest converting Siege Workshop' in l: conv += 1
        if 'HumanMove:祭司' in l:
            mm = re.search(r'移动至 \(([\d.]+),([\d.]+)\)', l)
            if mm: moves.append((f, float(mm.group(1)), float(mm.group(2))))
    res = 'WIN' if win else ('LOSS' if death is not None else 'UND')
    w1 = first_frame(b + '.ait', 'WAVE 1 INCOMING')
    lock = first_frame(b + '.ait', 'PRIEST GUARD] LOCKED-ON')
    mil = None
    for l in open(b + '.ait', errors='replace'):
        mm = re.search(r'Mil:\s*(\d+)', l)
        if mm and int(mm.group(1)) > 0:
            mil = fr_of(l); break
    # 探路最远点：取第一次"探路期"(<scoutPhase结束)的移动令中距 TC 最远者。TC 用首个 BUILD-ISSUE at= 附近估计不可靠，
    # 改用"祭司移动目标的最大跨度"（相对首条移动令坐标）作为探路幅度指标。
    maxreach = 0.0
    if moves:
        ox, oy = moves[0][1], moves[0][2]
        for f, x, y in moves:
            d = math.hypot(x - ox, y - oy) / 35.777
            if d > maxreach: maxreach = d
    return dict(tag=b, res=res, death=death, last=last, w1=w1, lock=lock, mil=mil,
                nst=nst, adv=adv, conv=conv, nlast=len(moves), reach=maxreach)

def show(rows, title):
    print('=== %s ===' % title)
    print('%-6s %-5s %8s %8s %8s %9s %8s %5s %4s %4s %8s' % (
        'game','res','death','last','WAVE1','1stLOCK','1stMil','ADV','CONV','st行','探路跨度(格)'))
    for r in rows:
        f = lambda v: v if v is not None else '-'
        print('%-6s %-5s %8s %8s %8s %9s %8s %5d %4d %4d %8.1f' % (
            r['tag'], r['res'], f(r['death']), f(r['last']), f(r['w1']), f(r['lock']), f(r['mil']),
            r['adv'], r['conv'], r['nst'], r['reach']))
    n = len(rows)
    w = sum(1 for r in rows if r['res'] == 'WIN')
    l = sum(1 for r in rows if r['res'] == 'LOSS')
    u = sum(1 for r in rows if r['res'] == 'UND')
    dead = sum(1 for r in rows if r['death'] is not None)
    early = [r['death'] for r in rows if r['death'] is not None and r['death'] < 5000]
    print('  n=%d  胜/负/未决=%d/%d/%d  胜率=%.1f%%  祭司死亡=%d  早死(<5000)=%d %s\n' % (
        n, w, l, u, 100.0*w/n, dead, len(early), early if early else ''))

for pre, title in [('z2', 'z2 批（改动前 map2, 3局, 探路100格）'),
                   ('n1', 'n1 批（敌情闸, map2, 12局）'),
                   ('n2', 'n2 批（探路40格, map2, 12局）'),
                   ('n3', 'n3 批（探路40格, map3 回归, 12局）'),
                   ('n4', 'n4 批（探路50格, map2, 12局）'),
                   ('n5', 'n5 批（探路45格, map2, 12局）'),
                   ('g1', 'g1 批（改动前 map3, 24局, 探路100格 = 已知最优基线）')]:
    fs = sorted(glob.glob(pre + '[0-9][0-9].ait'))
    if fs:
        show([analyze(f[:-4]) for f in fs], title)
    else:
        print('(%s 无文件)' % pre)
