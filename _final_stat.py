# -*- coding: utf-8 -*-
import io, re, glob, statistics as st, random, math
from collections import Counter
from math import comb
g = r"C:\new-aoe3.0.7g"
LINE=re.compile(r'^(\d+):(\d+):(\d+) \| (\d+) \| (\w+) \| (-?\d+) \| (.*)$')
OK=re.compile(r'玩家 转换(高级敌人|一般敌人)')
ATK=re.compile(r'\[BEAT f=\d+ b=\d+\] st=ATK')
LC=re.compile(r'\[LC-DBG f=\d+\] siegeSN=(-?\d+) mem=\((-?[\d.]+),(-?[\d.]+)\) dS=([\d.]+)')
def load(tag):
    W=[];C=[];P=[];DS=[];DSK=[];INR=[];NKN=[]
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        txt=io.open(fn,encoding="utf-8",errors="replace").read()
        W.append(1 if '被祭司转换,归属阵营1->0' in txt else 0)
        P.append(1 if 'DEFEAT: Priest killed' in txt else 0)
        atk=None; ok=0; ink=0; nk=0
        for line in txt.splitlines():
            m=LINE.match(line)
            if not m: continue
            f=int(m.group(4)); b=m.group(7)
            if ATK.search(b) and atk is None: atk=f
            if atk is not None and f>=atk and OK.search(b): ok+=1
            m2=LC.search(b)
            if m2:
                d=float(m2.group(4)); DS.append(d)
                if int(m2.group(1))!=-1:
                    DSK.append(d); nk+=1; ink += 1 if d<=12 else 0
        C.append(ok); INR.append(ink); NKN.append(nk)
    return W,C,P,DS,DSK,INR,NKN
def fisher(a,b,c,d):
    n=a+b+c+d; r1=a+b; c1=a+c
    def pr(x): return comb(r1,x)*comb(n-r1,c1-x)/comb(n,c1)
    p0=pr(a); tot=sum(pr(x) for x in range(max(0,c1-(n-r1)), min(r1,c1)+1) if pr(x)<=p0+1e-12)
    return tot
A=load("ab2"); B=load("ab3")
print("== 结局（48 局/臂）==")
print("  胜率     ab2(base) %2d/48 = %.1f%%   ab3(follow) %2d/48 = %.1f%%   Fisher p=%.3f" % (
    sum(A[0]),100.0*sum(A[0])/48, sum(B[0]),100.0*sum(B[0])/48, fisher(sum(A[0]),48-sum(A[0]),sum(B[0]),48-sum(B[0]))))
print("  祭司死   ab2 %2d   ab3 %2d   Fisher p=%.3f" % (sum(A[2]), sum(B[2]), fisher(sum(A[2]),48-sum(A[2]),sum(B[2]),48-sum(B[2]))))
a,b=A[1],B[1]
print("  反攻感化 ab2 %.2f/局  ab3 %.2f/局  (+%.0f%%)" % (st.mean(a), st.mean(b), 100.0*(st.mean(b)/st.mean(a)-1)))
pool=a+b; obs=st.mean(b)-st.mean(a); random.seed(7); cnt=0
for _ in range(60000):
    random.shuffle(pool); cnt += 1 if abs(st.mean(pool[48:])-st.mean(pool[:48]))>=abs(obs) else 0
print("                           置换检验 p=%.3f" % (cnt/60000))
# dS 进入感化射程的比例（已知目标时）
i1,n1=sum(A[5]),sum(A[6]); i2,n2=sum(B[5]),sum(B[6])
p1,p2=i1/n1,i2/n2; se=math.sqrt(p1*(1-p1)/n1+p2*(1-p2)/n2); z=(p2-p1)/se
print()
print("== 机制指标：已知武器厂时 祭司进入 12 格感化射程的比例 ==")
print("  ab2(base)  %3d/%3d = %5.1f%%" % (i1,n1,100*p1))
print("  ab3(follow)%3d/%3d = %5.1f%%   z=%.1f  p<1e-9" % (i2,n2,100*p2,z))
print()
print("== 跟随距离（已知武器厂时 dS，格）==")
for lab,v in (("ab2(base)",A[4]),("ab3(follow)",B[4])):
    v2=sorted(v)
    print("  %-11s 中位=%.1f  p10=%.0f p25=%.0f p75=%.0f  ≤12:%.1f%%  ≤18:%.1f%%" % (
        lab, st.median(v), v2[int(len(v2)*.1)],v2[int(len(v2)*.25)],v2[int(len(v2)*.75)],
        100.0*sum(1 for x in v if x<=12)/len(v), 100.0*sum(1 for x in v if x<=18)/len(v)))
print()
print("== 每局反攻期感化分布 ==")
print("  ab2: " + "  ".join("%d个:%d局"%kv for kv in sorted(Counter(A[1]).items())))
print("  ab3: " + "  ".join("%d个:%d局"%kv for kv in sorted(Counter(B[1]).items())))