# -*- coding: utf-8 -*-
import io, re, glob, os, collections
from math import comb
g = r"C:\new-aoe3.0.7g"
def fisher(a,b,c,d):
    n=a+b+c+d; r1=a+b; c1=a+c
    def pr(x): return comb(r1,x)*comb(n-r1,c1-x)/comb(n,c1)
    p0=pr(a); return sum(pr(x) for x in range(max(0,c1-(n-r1)),min(r1,c1)+1) if pr(x)<=p0+1e-12)
def out(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    if 'DEFEAT: Town Center destroyed' in t: return 'T'
    return 'U'
for tag,lab in (("ab8","基线 pe2"),("ab9","最终版")):
    per=collections.defaultdict(lambda:[0,0,0,0])  # W n P U
    for fn in sorted(glob.glob(g+"\\"+tag+"_*_r0_*.ait")):
        t=io.open(fn,encoding="utf-8",errors="replace").read()
        mp=os.path.basename(fn).replace(tag+"_","").split("_r0_")[0]
        o=out(t); per[mp][1]+=1
        per[mp][{"W":0,"P":2,"T":3,"U":3}[o]]+=1
    tw=tn=tp=0
    parts=[]
    for m in ("map","map1","map2","map3"):
        w,n,p,u=per[m]; tw+=w; tn+=n; tp+=p
        if n: parts.append("%s %d/%d" % (m,w,n))
    print("%-10s 总计 %2d/%2d = %5.1f%%  | 祭司死=%d | 分图: %s" % (lab, tw,tn,100.0*tw/tn,tp,"  ".join(parts)))
W8=[]; W9=[]
for tag,box in (("ab8",W8),("ab9",W9)):
    for fn in sorted(glob.glob(g+"\\"+tag+"_*_r0_*.ait")):
        t=io.open(fn,encoding="utf-8",errors="replace").read()
        box.append(1 if out(t)=="W" else 0)
print()
print("Fisher 检验：%d/24 vs %d/24 → p=%.3f" % (sum(W8),sum(W9), fisher(sum(W8),24-sum(W8),sum(W9),24-sum(W9))))