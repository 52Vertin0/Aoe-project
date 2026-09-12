# -*- coding: utf-8 -*-
"""检查某臂的 U 局是否为『被截断的伪 U』（最大帧 < 44000 且无结局标记）。"""
import glob, re, sys

FR = re.compile(r'^\d\d:\d\d:\d\d+\s*\|\s*(\d+)\s*\|')

def outcome(s):
    if '被祭司转换,归属阵营1->0' in s: return 'W'
    if 'DEFEAT: Priest killed' in s: return 'P'
    if 'DEFEAT: Town Center destroyed' in s: return 'T'
    if '敌方 摧毁主营' in s: return 'T'
    return 'U'

tags = sys.argv[1:] or ['wbase', 'club6b']
for tag in tags:
    U = []; comp = 0; n = 0
    for fn in sorted(glob.glob(f'{tag}_*_r0_*.ait')):
        s = open(fn, encoding='utf-8', errors='replace').read(); n += 1
        fr = [int(m.group(1)) for m in (FR.match(l) for l in s.splitlines()) if m]
        mx = max(fr) if fr else 0
        r = outcome(s)
        if r == 'U':
            U.append((fn.split('/')[-1].split('\\')[-1], mx))
        if r != 'U' or mx >= 44000:
            comp += 1
    print(f'[{tag}] n={n}  完整局(有结局 或 到点>=44000)={comp}  伪U(截断)={sum(1 for _, m in U if m < 44000)}')
    for fn, mx in U:
        flag = '  <== 伪U(截断)' if mx < 44000 else ''
        print(f'      {fn:<30} maxf={mx} ({mx/1500:.1f}分){flag}')
