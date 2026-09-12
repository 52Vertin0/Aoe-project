# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
from collections import Counter
g = r"C:\new-aoe3.0.7g"
BEAT = re.compile(r'\[BEAT f=(\d+) b=\d+\] st=(\w+)\*? .*? \| a=(\d+) hop=(\d+) arch=(\d+) oth=(\d+)')
def med(v): return st.median(v) if v else None
def run(tag):
    starts=[]; peaks=[]; lasts=[]; hops=[]; reached=0; tot=0
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        tot+=1
        t=io.open(fn,encoding="utf-8",errors="replace").read()
        seq=[(int(m.group(1)), m.group(2), int(m.group(4)), int(m.group(5))) for m in BEAT.finditer(t)]
        atk=[r for r in seq if r[1]=="ATK"]
        if not atk: continue
        reached+=1
        starts.append(atk[0][3]); peaks.append(max(r[3] for r in atk)); lasts.append(atk[-1][3]); hops.append(atk[0][2])
    print("=== %s : %d 局，进入反攻(ATK) %d 局 ===" % (tag, tot, reached))
    if not reached: return
    print("  反攻【开始时】战车弓兵 arch : 中位=%.0f  最小=%d  最大=%d" % (med(starts), min(starts), max(starts)))
    print("  反攻【进行中】战车弓兵峰值 : 中位=%.0f  最小=%d  最大=%d" % (med(peaks), min(peaks), max(peaks)))
    print("  反攻【最后采样】战车弓兵   : 中位=%.0f  最小=%d  最大=%d" % (med(lasts), min(lasts), max(lasts)))
    print("  反攻开始时方阵兵 hop       : 中位=%.0f" % med(hops))
    print("  反攻起点分布: " + "  ".join("%d个:%d局" % kv for kv in sorted(Counter(starts).items())))
    print("  峰值分布    : " + "  ".join("%d个:%d局" % kv for kv in sorted(Counter(peaks).items())))
    print()
run("pe2")
run("ca1")