# -*- coding: utf-8 -*-
import io, re, glob, os, statistics as st, datetime
g = r"C:\new-aoe3.0.7g"
launch = datetime.datetime(2026,10,9,0,17,58).timestamp()
print("=== 提速（同批 12 局并发；帧/秒 = 末帧 / (完成-启动)）===")
for tag,lab in (("d2","debug "),("n2","nodebug")):
    v=[]
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        op=fn[:-4]+".out"
        if not os.path.exists(op): continue
        o=io.open(op,encoding="utf-8",errors="replace").read()
        ms=[int(x) for x in re.findall(r'\[OJ-HB\] f=(\d+)', o)]
        if not ms: continue
        dur=os.path.getmtime(fn)-launch
        if dur<=0: continue
        v.append((ms[-1], dur, ms[-1]/dur))
    if v:
        print("   %s 帧/秒: 中位=%.0f  " % (lab, st.median([x[2] for x in v])) + "  各局=" + ", ".join("%.0f(%.0fs)"%(x[2],x[1]) for x in sorted(v)))