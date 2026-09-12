# -*- coding: utf-8 -*-
"""h3(A') vs h2(方案A) 祭司存活/胜负对比分析。
判据：胜 = jsonl 任一行 "win":true ；负 = ait 含 "DEFEAT: Priest killed" ；其余=未决。
早死 = 死亡帧 < 23253（复合弓首产中位）。
"""
import os, re, glob

FIRST_BOW = 23253  # 复合弓首产中位帧

def analyze(prefix):
    files = sorted(glob.glob('%s*.ait' % prefix))
    n = len(files)
    win = loss = und = 0
    priest_death = 0
    early_death = 0
    death_frames = []
    noadv = 0
    for ait in files:
        base = ait[:-4]
        jsonl = base + '.jsonl'
        # win?
        w = False
        if os.path.exists(jsonl):
            with open(jsonl, 'r', errors='replace') as f:
                for line in f:
                    if '"win":true' in line:
                        w = True
                        break
        # priest killed?
        pk_frame = None
        with open(ait, 'r', errors='replace') as f:
            for line in f:
                if 'DEFEAT: Priest killed' in line:
                    m = re.search(r'\|\s*(\d+)\s*\|', line)
                    if m:
                        fr = int(m.group(1))
                        if pk_frame is None or fr < pk_frame:
                            pk_frame = fr
                if 'PRIEST-NOADV' in line:
                    noadv += 1
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
    return dict(prefix=prefix, n=n, win=win, loss=loss, und=und,
                priest_death=priest_death, early_death=early_death,
                death_frames=death_frames, noadv=noadv)

def report(r):
    print('=== %s 批 (n=%d) ===' % (r['prefix'], r['n']))
    print('  胜=%d  负=%d  未决=%d  胜率=%.1f%%' % (r['win'], r['loss'], r['und'], 100.0*r['win']/r['n']))
    print('  祭司死亡=%d/24 (%.1f%%)   其中早死(<23253帧)=%d' % (r['priest_death'], 100.0*r['priest_death']/r['n'], r['early_death']))
    print('  [PRIEST-NOADV] 触发=%d 次' % r['noadv'])
    if r['death_frames']:
        print('  死亡帧列表: ' + ', '.join(str(x) for x in sorted(r['death_frames'])))
    print()

for p in ['h2', 'h3']:
    report(analyze(p))

# 显著性粗判（Fisher 近似用 scipy 若可用）
try:
    from scipy import stats
    h2 = analyze('h2'); h3 = analyze('h3')
    # 早死：h2 vs h3 (早死数 / 死亡总数? 用 早死/24)
    _, p_early = stats.fisher_exact([[h2['early_death'], h2['n']-h2['early_death']],
                                      [h3['early_death'], h3['n']-h3['early_death']]])
    _, p_win = stats.fisher_exact([[h2['win'], h2['n']-h2['win']],
                                    [h3['win'], h3['n']-h3['win']]])
    print('Fisher p (早死 h2 vs h3) = %.4f' % p_early)
    print('Fisher p (胜率 h2 vs h3) = %.4f' % p_win)
except Exception as e:
    print('(scipy 不可用，跳过显著性: %s)' % e)
