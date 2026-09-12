# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
from collections import Counter
g = r"C:\new-aoe3.0.7g"
BEAT = re.compile(r'\[BEAT f=(\d+) b=\d+\] st=(\w+)\*? .*? \| a=(\d+) hop=(\d+) arch=(\d+) oth=(\d+)')
def med(v): return st.median(v) if v else None
def outcome(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    if 'DEFEAT: Town Center destroyed' in t: return 'T'
    return 'U'
for tag in ("pe2","ca1"):
    grp={'W':[], 'P':[], 'U':[]}
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        t=io.open(fn,encoding="utf-8",errors="replace").read()
        atk=[(int(m.group(1)), int(m.group(3)), int(m.group(4))) for m in BEAT.finditer(t) if m.group(2)=="ATK"]
        if not atk: continue
        grp[outcome(t)].append(atk[0][2])
    print("=== %s 反攻开始时战车弓兵 arch（按结局分组）===" % tag)
    for k in ("W","P","U"):
        v=grp[k]
        if v: print("  %s (n=%2d) : 中位=%.0f  均值=%.1f  范围=%d~%d" % (k, len(v), med(v), sum(v)/len(v), min(v), max(v)))
    print()