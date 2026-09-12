# -*- coding: utf-8 -*-
import io, re, glob, statistics as st, random
g = r"C:\new-aoe3.0.7g"
LINE=re.compile(r'^(\d+):(\d+):(\d+) \| (\d+) \| (\w+) \| (-?\d+) \| (.*)$')
OK=re.compile(r'玩家 转换(高级敌人|一般敌人)')
ATK=re.compile(r'\[BEAT f=\d+ b=\d+\] st=ATK')
def vals(tag):
    out=[]
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        txt=io.open(fn,encoding="utf-8",errors="replace").read()
        atk=None; ok=0
        for line in txt.splitlines():
            m=LINE.match(line)
            if not m: continue
            f=int(m.group(4)); b=m.group(7)
            if ATK.search(b) and atk is None: atk=f
            if atk is not None and f>=atk and OK.search(b): ok+=1
        out.append(ok)
    return out
A=vals("ab0"); B=vals("ab1")
print("ab0: mean=%.2f sd=%.2f  n=%d" % (st.mean(A), st.pstdev(A), len(A)))
print("ab1: mean=%.2f sd=%.2f  n=%d" % (st.mean(B), st.pstdev(B), len(B)))
# Welch t
import math
sa,sb=st.variance(A),st.variance(B)
se=math.sqrt(sa/len(A)+sb/len(B)); t=(st.mean(A)-st.mean(B))/se
print("Welch t=%.2f  (df≈%.1f)" % (t, se**4/((sa/len(A))**2/(len(A)-1)+(sb/len(B))**2/(len(B)-1))))
# permutation test on mean difference
random.seed(0); obs=st.mean(A)-st.mean(B); pool=A+B; cnt=0; N=20000
for _ in range(N):
    random.shuffle(pool); cnt += 1 if abs(st.mean(pool[:len(A)])-st.mean(pool[len(A):]))>=abs(obs) else 0
print("置换检验 p = %.3f" % (cnt/N))