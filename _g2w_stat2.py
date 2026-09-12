# -*- coding: utf-8 -*-
import io, re, glob, statistics as st, random
from collections import Counter
g = r"C:\new-aoe3.0.7g"
LINE=re.compile(r'^(\d+):(\d+):(\d+) \| (\d+) \| (\w+) \| (-?\d+) \| (.*)$')
ECO=re.compile(r'ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+) \|\| goldRich:(\d)')
ATK=re.compile(r'\[BEAT f=\d+ b=\d+\] st=ATK')
def med(v): return st.median(v) if v else 0
def show(v,fmt="%.1f"):
    v=sorted(v); return (("中位="+fmt+" 均值="+fmt+" p25="+fmt+" p75="+fmt+" 最大="+fmt) % (med(v),sum(v)/len(v),v[len(v)//4],v[3*len(v)//4],v[-1])) if v else "-"
for tag,lab in (("ab6","改动前"),("ab7","改动后")):
    # 全场 & 反攻期工人构成
    allF=[];allW=[];allG=[];allS=[]
    atkW=[];atkG=[];atkWd=[];atkGd=[];atkRich=[]
    goldRate=[]; woodRate=[]
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        seq=[]; atkf=None
        for line in io.open(fn,encoding="utf-8",errors="replace"):
            m=LINE.match(line.rstrip("\n"))
            if not m: continue
            f=int(m.group(4)); b=m.group(7)
            if ATK.search(b) and atkf is None: atkf=f
            e=ECO.search(b)
            if e: seq.append((f,int(e.group(2)),int(e.group(4)),int(e.group(5)),int(e.group(6)),int(e.group(7)),int(e.group(8)),int(e.group(9))))
        if not seq: continue
        for x in seq:
            allF.append(x[3]); allW.append(x[4]); allG.append(x[5]); allS.append(x[6])
            if atkf is not None and x[0]>=atkf:
                atkW.append(x[4]); atkG.append(x[5]); atkWd.append(x[1]); atkGd.append(x[2]); atkRich.append(x[7])
        # 收入速率（反攻期：Δ存量/Δ时间）
        a=[x for x in seq if atkf is not None and x[0]>=atkf]
        if len(a)>=2:
            dt=(a[-1][0]-a[0][0])/25.0
            if dt>30:
                goldRate.append((a[-1][2]-a[0][2])/dt*60)
                woodRate.append((a[-1][1]-a[0][1])/dt*60)
    print("=== %s (%s) ===" % (tag,lab))
    print("   【全场】工人 食物=%s" % show(allF,"%.1f"))
    print("          伐木=%s" % show(allW,"%.1f"))
    print("          采金=%s" % show(allG,"%.1f"))
    print("          采石=%s" % show(allS,"%.1f"))
    print("   【反攻期】伐木工=%s" % show(atkW,"%.1f"))
    print("             采金工=%s" % show(atkG,"%.1f"))
    print("             木材存量=%s" % show(atkWd,"%.0f"))
    print("             黄金存量=%s" % show(atkGd,"%.0f"))
    print("             黄金净收入/分钟=%s   木材净收入/分钟=%s" % (show(goldRate,"%.1f"), show(woodRate,"%.1f")))
    print("             goldRich=1 占比=%.0f%%" % (100.0*sum(atkRich)/max(1,len(atkRich))))
    print()
# 显著性别：全场工人构成
import collections
D={}
for tag in ("ab6","ab7"):
    F=[];W=[];G=[];S=[]
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        for line in io.open(fn,encoding="utf-8",errors="replace"):
            m=LINE.match(line.rstrip("\n"))
            if not m: continue
            e=ECO.search(m.group(7))
            if e: F.append(int(e.group(5)));W.append(int(e.group(6)));G.append(int(e.group(7)));S.append(int(e.group(8)))
    D[tag]=(F,W,G,S)
for i,lab in ((0,"食物工"),(1,"伐木工"),(2,"采金工"),(3,"采石工")):
    a,b=D["ab6"][i],D["ab7"][i]
    obs=abs(st.mean(a)-st.mean(b)); pool=a+b; random.seed(5); cnt=0
    for _ in range(8000):
        random.shuffle(pool); cnt += 1 if abs(st.mean(pool[len(a):])-st.mean(pool[:len(a)]))>=obs else 0
    print("全场 %-6s 均值 %.2f → %.2f   p=%.3f   (n=%d/%d)" % (lab, st.mean(a), st.mean(b), cnt/8000.0, len(a), len(b)))