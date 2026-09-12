# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
from collections import Counter
g = r"C:\new-aoe3.0.7g"
LINE=re.compile(r'^(\d+):(\d+):(\d+) \| (\d+) \| (\w+) \| (-?\d+) \| (.*)$')
ECO=re.compile(r'ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+) \|\| goldRich:(\d)')
ATK=re.compile(r'\[BEAT f=\d+ b=\d+\] st=ATK')
def pct(v,p):
    v=sorted(v); return v[int(len(v)*p)] if v else 0
for tag in ("ab3","ab2"):
    fin=[]; mx=[]; atkstart=[]; richfrac=[]; gwork=[]; n=0; over300=over500=over800=0
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        n+=1
        seq=[]; atkf=None
        for line in io.open(fn,encoding="utf-8",errors="replace"):
            m=LINE.match(line.rstrip("\n"))
            if not m: continue
            f=int(m.group(4)); b=m.group(7)
            if ATK.search(b) and atkf is None: atkf=f
            e=ECO.search(b)
            if e: seq.append((f,int(e.group(4)),int(e.group(7)),int(e.group(9))))
        if not seq: continue
        golds=[x[1] for x in seq]
        fin.append(golds[-1]); mx.append(max(golds))
        if atkf is not None:
            a=[x for x in seq if x[0]>=atkf]
            if a:
                atkstart.append(a[0][1]); richfrac.append(sum(x[3] for x in a)/len(a))
        gwork += [x[2] for x in seq]
        if golds[-1]>300: over300+=1
        if golds[-1]>500: over500+=1
        if golds[-1]>800: over800+=1
    print("=== %s (n=%d) ===" % (tag,n))
    print("   终局黄金  中位=%.0f 均值=%.0f p25=%.0f p75=%.0f 最大=%d" % (st.median(fin),sum(fin)/len(fin),pct(fin,.25),pct(fin,.75),max(fin)))
    print("   全程峰值黄金 中位=%.0f 最大=%d" % (st.median(mx),max(mx)))
    print("   终局>300 的局=%d(%.0f%%)  >500=%d  >800=%d" % (over300,100.0*over300/n,over500,over800))
    print("   全场金工人数分布: " + "  ".join("%d人:%d次(%.0f%%)"%kv for kv in sorted(Counter(gwork).items())))
    if richfrac: print("   反攻期 goldRich=1 的采样占比 中位=%.0f%%" % (100*st.median(richfrac)))
    if atkstart: print("   反攻开始时黄金 中位=%.0f" % st.median(atkstart))
    print()