# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
from collections import Counter
g = r"C:\new-aoe3.0.7g"
LINE=re.compile(r'^(\d+):(\d+):(\d+) \| (\d+) \| (\w+) \| (-?\d+) \| (.*)$')
ECO=re.compile(r'ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+) \|\| goldRich:(\d)')
for tag,lab in (("ab8","基线 pe2"),("ab9","最终版")):
    ph=0; ca=0; n=0; G=[];W=[];conv=0;ds=[]
    for fn in sorted(glob.glob(g+"\\"+tag+"_*_r0_*.ait")):
        t=io.open(fn,encoding="utf-8",errors="replace").read(); n+=1
        ph+=len(re.findall(r'\[HOPLITE-(?:LATE|ATK) ',t))
        ca+=len(re.findall(r'产生了新的战车弓兵',t))
        conv+=len(re.findall(r'玩家 转换(?:高级|一般)敌人',t))
        for line in t.splitlines():
            m=LINE.match(line)
            if not m: continue
            e=ECO.search(m.group(7))
            if e: W.append(int(e.group(6))); G.append(int(e.group(7)))
        ds += [float(x) for x in re.findall(r'siegeSN=-?\d+ mem=\([-\d.]+,[-\d.]+\) dS=([\d.]+)', t)]
    print("=== %s (n=%d) ===" % (lab,n))
    print("   方阵兵产量  %.1f/局    战车弓兵产量 %.1f/局" % (ph/n, ca/n))
    print("   全局感化成功(单位) %.1f/局" % (conv/n))
    print("   全场工人: 伐木 均值=%.2f   采金 均值=%.2f" % (st.mean(W), st.mean(G)))
    print()