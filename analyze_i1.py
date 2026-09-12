# -*- coding: utf-8 -*-
"""i1(LOCK-FLEE) vs g1(无闸基线) 祭司存活/胜负/触发频率对比。
判据：胜 = jsonl 任一行 "win":true ；负 = ait 含 "DEFEAT: Priest killed" ；其余=未决。
早死 = 死亡帧 < 23253（复合弓首产中位）。
"""
import os, re, glob

FIRST_BOW = 23253

def analyze(prefix):
    files = sorted(glob.glob('%s*.ait' % prefix))
    n = len(files)
    win = loss = und = 0
    priest_death = 0
    early_death = 0
    death_frames = []
    lockflee = 0
    lockflee_games = 0
    if not files:
        return None
    for ait in files:
        base = ait[:-4]
        jsonl = base + '.jsonl'
        w = False
        if os.path.exists(jsonl):
            with open(jsonl, 'r', errors='replace') as f:
                for line in f:
                    if '"win":true' in line:
                        w = True
                        break
        pk_frame = None
        lf = 0
        with open(ait, 'r', errors='replace') as f:
            for line in f:
                if 'DEFEAT: Priest killed' in line:
                    m = re.search(r'\|\s*(\d+)\s*\|', line)
                    if m:
                        fr = int(m.group(1))
                        if pk_frame is None or fr < pk_frame:
                            pk_frame = fr
                if 'PRIEST LOCK-FLEE' in line:
                    lf += 1
        if w:
            win += 1
        elif pk_frame is not None:
            loss += 1
        else:
            und += 1
        if pk_frame is not None:
            priest_death += 1
            death_frames.append(pk_frame)
            if pk_frame < FIRST_BOW:
                early_death += 1
        lockflee += lf
        if lf > 0:
            lockflee_games += 1
    return dict(prefix=prefix, n=n, win=win, loss=loss, und=und,
                priest_death=priest_death, early_death=early_death,
                death_frames=death_frames, lockflee=lockflee,
                lockflee_games=lockflee_games)

def report(r):
    if not r:
        print('(no files)')
        return
    print('=== %s 批 (n=%d) ===' % (r['prefix'], r['n']))
    print('  胜=%d  负=%d  未决=%d  胜率=%.1f%%' % (r['win'], r['loss'], r['und'], 100.0*r['win']/r['n']))
    print('  祭司死亡=%d/%d (%.1f%%)  早死(<23253)=%d' % (r['priest_death'], r['n'], 100.0*r['priest_death']/r['n'], r['early_death']))
    print('  [PRIEST LOCK-FLEE] 总触发=%d 次，命中局数=%d/%d，均值=%.1f 次/局' %
          (r['lockflee'], r['lockflee_games'], r['n'], r['lockflee']/r['n']))
    if r['death_frames']:
        print('  死亡帧: ' + ', '.join(str(x) for x in sorted(r['death_frames'])))
    print()

for p in ['g1', 'i1']:
    report(analyze(p))

def fisher(a,b,c,d):
    import math
    n=a+b+c+d; row1=a+b; row2=c+d; col1=a+c
    pcut=math.comb(row1,a)*math.comb(row2,c)/math.comb(n,col1)
    p=0.0
    for i in range(max(0,col1-row2), min(col1,row1)+1):
        pv=math.comb(row1,i)*math.comb(row2,col1-i)/math.comb(n,col1)
        if pv<=pcut+1e-15: p+=pv
    return p

g1 = analyze('g1'); i1 = analyze('i1')
if g1 and i1:
    print('Fisher p (g1 vs i1):')
    print('  胜率     %d/%d vs %d/%d : p=%.4f' % (g1['win'],g1['n'],i1['win'],i1['n'],
          fisher(g1['win'], g1['n']-g1['win'], i1['win'], i1['n']-i1['win'])))
    print('  祭司死亡 %d/%d vs %d/%d : p=%.4f' % (g1['priest_death'],g1['n'],i1['priest_death'],i1['n'],
          fisher(g1['priest_death'], g1['n']-g1['priest_death'], i1['priest_death'], i1['n']-i1['priest_death'])))
    print('  早死     %d/%d vs %d/%d : p=%.4f' % (g1['early_death'],g1['n'],i1['early_death'],i1['n'],
          fisher(g1['early_death'], g1['n']-g1['early_death'], i1['early_death'], i1['n']-i1['early_death'])))
