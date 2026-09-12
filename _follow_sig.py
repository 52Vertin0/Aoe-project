# -*- coding: utf-8 -*-
import io, re, glob, statistics as st, random, math
from collections import Counter
g = r"C:\new-aoe3.0.7g"
LINE=re.compile(r'^(\d+):(\d+):(\d+) \| (\d+) \| (\w+) \| (-?\d+) \| (.*)$')
OK=re.compile(r'玩家 转换(高级敌人|一般敌人)')
ATK=re.compile(r'\[BEAT f=\d+ b=\d+\] st=ATK')
def load(tag):
    wins=[]; conv=[]; pd=[]; ds=[]
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        txt=io.open(fn,encoding="utf-8",errors="replace").read()
        w = '被祭司转换,归属阵营1->0' in txt
        p = 'DEFEAT: Priest killed' in txt
        atk=None; ok=0
        for line in txt.splitlines():
            m=LINE.match(line)
            if not m: continue
            f=int(m.group(4)); b=m.group(7)
            if ATK.search(b) and atk is None: atk=f
            if atk is not None and f>=atk and OK.search(b): ok+=1
        wins.append(1 if w else 0); conv.append(ok); pd.append(1 if p else 0)
    return wins, conv, pd
def fisher(a,b,c,d):
    # 2x2 exact (two-sided) via scipy-free hypergeometric
    from math import comb
    n=a+b+c+d; r1=a+b; c1=a+c
    def prob(x): return comb(r1,x)*comb(n-r1,c1-x)/comb(n,c1)
    p0=prob(a); tot=0
    for x in range(max(0,c1-(n-r1)), min(r1,c1)+1):
        if prob(x) <= p0+1e-12: tot+=prob(x)
    return tot
for tag in ("ab2","ab3"):
    w,c,p=load(tag)
    print("%s: 胜=%d/%d (%.1f%%)  祭死=%d  反攻感化=%.2f/局 (总%d)  局均分布=%s" % (
        tag, sum(w),len(w),100.0*sum(w)/len(w), sum(p), sum(c)/len(c), sum(c),
        dict(sorted(Counter(c).items()))))
A=load("ab2"); B=load("ab3")
print()
print("胜率 8/24 vs 10/24 → Fisher p = %.3f" % fisher(8,16,10,14))
print("祭死 10/24 vs 7/24 → Fisher p = %.3f" % fisher(10,14,7,17))
# 置换检验：每局反攻感化数
a=A[1]; b=B[1]; obs=st.mean(b)-st.mean(a); pool=a+b; random.seed(1); cnt=0; N=40000
for _ in range(N):
    random.shuffle(pool); cnt += 1 if abs(st.mean(pool[len(a):])-st.mean(pool[:len(a)]))>=abs(obs) else 0
print("反攻期感化 %.2f→%.2f (每局) → 置换检验 p = %.3f" % (st.mean(a), st.mean(b), cnt/N))