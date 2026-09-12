# -*- coding: utf-8 -*-
import io, re, glob, statistics as st, random
from collections import Counter
g = r"C:\new-aoe3.0.7g"
LINE=re.compile(r'^(\d+):(\d+):(\d+) \| (\d+) \| (\w+) \| (-?\d+) \| (.*)$')
ECO=re.compile(r'ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+) \|\| goldRich:(\d)')
ATK=re.compile(r'\[BEAT f=\d+ b=\d+\] st=ATK')
def med(v): return st.median(v) if v else 0
res={}
for tag in ("ab6","ab7"):
    W=[];G=[];Fw=[];Wd=[];Gd=[];Rich=[];lowW=0;tot=0;ph=0;ca=0;n=0
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        n+=1
        txt=io.open(fn,encoding="utf-8",errors="replace").read()
        W.append(1 if '被祭司转换,归属阵营1->0' in txt else 0)
        ph += len(re.findall(r'\[HOPLITE-(?:LATE|ATK) ', txt))
        ca += len(re.findall(r'产生了新的战车弓兵', txt))
        atk=None; gs=[]
        for line in txt.splitlines():
            m=LINE.match(line)
            if not m: continue
            f=int(m.group(4)); b=m.group(7)
            if ATK.search(b) and atk is None: atk=f
            if atk is None or f<atk: continue
            e=ECO.search(b)
            if e:
                tot+=1
                gs.append((int(e.group(2)),int(e.group(4)),int(e.group(7)),int(e.group(8)),int(e.group(9))))
        for x in gs:
            G.append(x[2]); Fw.append(x[3]); Wd.append(x[0]); Gd.append(x[1]); Rich.append(x[4])
            if x[0]<70: lowW+=1
    res[tag]=dict(W=W,G=G,Fw=Fw,Wd=Wd,Gd=Gd,Rich=Rich,n=n,ph=ph,ca=ca,tot=tot,lowW=lowW)
def line(t,k,lab,fmt="%.1f"):
    v=res[t][k]
    if not v: return "   %-22s -" % lab
    return ("   %-22s 中位="+fmt+" 均值="+fmt+" p25="+fmt+" p75="+fmt) % (lab, med(v), sum(v)/len(v), sorted(v)[len(v)//4], sorted(v)[3*len(v)//4])
for t,lab in (("ab6","改动前(跟随距离版)"),("ab7","改动后(减金工→木材)")):
    d=res[t]
    print("=== %s (n=%d, 胜=%d=%.0f%%) ===" % (lab,d["n"],sum(d["W"]),100.0*sum(d["W"])/d["n"]))
    print(line(t,"G","反攻期金工人数"))
    print(line(t,"Fw","反攻期伐木工人数"))
    print(line(t,"Wd","反攻期木材存量"))
    print(line(t,"Gd","反攻期黄金存量"))
    print("   %-22s goldRich=1 占比=%.0f%%  木材<70 占比=%.0f%%" % ("", 100.0*sum(d["Rich"])/max(1,len(d["Rich"])), 100.0*d["lowW"]/max(1,d["tot"])))
    print("   方阵兵产量=%.1f个/局   战车弓兵产量=%.1f个/局" % (d["ph"]/d["n"], d["ca"]/d["n"]))
    print()
# 显著性：金工人数 / 木材
for k,lab in (("G","金工人数"),("Fw","伐木工人数"),("Wd","木材存量"),("Gd","黄金存量")):
    a=res["ab6"][k]; b=res["ab7"][k]
    if not a or not b: continue
    obs=abs(st.mean(a)-st.mean(b)); pool=a+b; random.seed(3); cnt=0
    for _ in range(20000):
        random.shuffle(pool); cnt += 1 if abs(st.mean(pool[len(a):])-st.mean(pool[:len(a)]))>=obs else 0
    print("置换检验 %-8s 改动前均值=%.1f → 改动后=%.1f  p=%.3f" % (lab, st.mean(a), st.mean(b), cnt/20000.0))