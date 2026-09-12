# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
g = r"C:\new-aoe3.0.7g"
BEAT = re.compile(r'\[BEAT f=(\d+) b=(\d+)\] (\w+)(\*?) \| .*? \| a=(\d+) hop=(\d+) arch=(\d+) oth=(\d+)')
def med(v): return st.median(v) if v else None
def run(tag):
    rows=[]
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        t=io.open(fn,encoding="utf-8",errors="replace").read()
        seq=[]
        for m in BEAT.finditer(t):
            seq.append((int(m.group(1)), m.group(3), m.group(4)=='*', int(m.group(6)), int(m.group(7))))
        atk=[r for r in seq if r[1]=="ATK"]
        if not atk:
            rows.append((fn.split("\\")[-1], None)); continue
        first=atk[0]; peak=max(r[4] for r in atk)
        rows.append((fn.split("\\")[-1], dict(start=first[4], peak=peak, startF=first[0], nAtk=len(atk), hopStart=first[3], lastArch=seq[-1][4], lastSt=seq[-1][1])))
    ok=[r for r in rows if r[1]]
    print("=== %s : %d games, %d reached ATK ===" % (tag, len(rows), len(ok)))
    if not ok: return
    starts=[r[1]['start'] for r in ok]; peaks=[r[1]['peak'] for r in ok]
    hops=[r[1]['hopStart'] for r in ok]
    print("  反攻起点 arch : median=%.0f  min=%d  max=%d" % (med(starts), min(starts), max(starts)))
    print("  反攻期峰值 arch: median=%.0f  min=%d  max=%d" % (med(peaks), min(peaks), max(peaks)))
    print("  反攻起点 hop  : median=%.0f" % med(hops))
    from collections import Counter
    c=Counter(starts)
    print("  反攻起点分布 : " + "  ".join("%d个:%d局" % (k,v) for k,v in sorted(c.items())))
    c2=Counter(peaks)
    print("  峰值分布     : " + "  ".join("%d个:%d局" % (k,v) for k,v in sorted(c2.items())))
    print()
run("pe2")
run("ca1")