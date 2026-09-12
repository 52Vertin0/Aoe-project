# -*- coding: utf-8 -*-
import io, re, glob
from math import comb
g = r"C:\new-aoe3.0.7g"
def fisher(a,b,c,d):
    n=a+b+c+d; r1=a+b; c1=a+c
    def pr(x): return comb(r1,x)*comb(n-r1,c1-x)/comb(n,c1)
    p0=pr(a); return sum(pr(x) for x in range(max(0,c1-(n-r1)),min(r1,c1)+1) if pr(x)<=p0+1e-12)
def cnt(tag,pat):
    n=0
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        t=io.open(fn,encoding="utf-8",errors="replace").read()
        n += 1 if re.search(pat,t) else 0
    return n
W6=cnt("ab6",r'被祭司转换'); W7=cnt("ab7",r'被祭司转换')
P6=cnt("ab6",r'祭司\(编号\d+\)死亡'); P7=cnt("ab7",r'祭司\(编号\d+\)死亡')
print("胜率   ab6 %2d/24 = %.1f%%   ab7 %2d/24 = %.1f%%   Fisher p=%.3f" % (W6,100.0*W6/24,W7,100.0*W7/24, fisher(W6,24-W6,W7,24-W7)))
print("祭司死 ab6 %2d      ab7 %2d      Fisher p=%.3f" % (P6,P7, fisher(P6,24-P6,P7,24-P7)))
# 方阵兵产量
for tag in ("ab6","ab7"):
    tot=0; n=0; ca=0
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        t=io.open(fn,encoding="utf-8",errors="replace").read()
        tot+=len(re.findall(r'\[HOPLITE-(?:LATE|ATK) ',t)); ca+=len(re.findall(r'产生了新的战车弓兵',t)); n+=1
    print("%s: 方阵兵 %.1f/局   战车弓兵 %.1f/局" % (tag, tot/n, ca/n))