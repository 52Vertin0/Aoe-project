# -*- coding: utf-8 -*-
from math import comb
def fisher(a,b,c,d):
    n=a+b+c+d; r1=a+b; c1=a+c
    def pr(x): return comb(r1,x)*comb(n-r1,c1-x)/comb(n,c1)
    p0=pr(a); return sum(pr(x) for x in range(max(0,c1-(n-r1)),min(r1,c1)+1) if pr(x)<=p0+1e-12)
print("map.njust  最终版 12/24 vs 激进版 14/24  → Fisher p=%.3f" % fisher(12,12,14,10))
print("四图×3     最终版  5/12 vs 激进版  6/12  → Fisher p=%.3f" % fisher(5,7,6,6))
print("合并(两测) 17/36 vs 20/36               → Fisher p=%.3f" % fisher(17,19,20,16))