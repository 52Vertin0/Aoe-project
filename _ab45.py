# -*- coding: utf-8 -*-
import io, re, glob, os
g = r"C:\new-aoe3.0.7g"
def outc(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    if 'DEFEAT: Town Center destroyed' in t: return 'T'
    return 'U'
for tag in ("ab4","ab5"):
    print("== %s ==" % tag)
    for fn in sorted(glob.glob(g+"\\"+tag+"_*_r0_*.ait")):
        t=io.open(fn,encoding="utf-8",errors="replace").read()
        beats=t.count("[BEAT")
        print("   %-24s %s  (BEAT=%d, %.1f MB)" % (os.path.basename(fn), outc(t), beats, len(t)/1048576.0))