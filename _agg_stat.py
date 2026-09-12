# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
from math import comb
g = r"C:\new-aoe3.0.7g"
def fisher(a,b,c,d):
    n=a+b+c+d; r1=a+b; c1=a+c
    def pr(x): return comb(r1,x)*comb(n-r1,c1-x)/comb(n,c1)
    p0=pr(a); return sum(pr(x) for x in range(max(0,c1-(n-r1)),min(r1,c1)+1) if pr(x)<=p0+1e-12)
def out(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    return 'U'
print("=== 机制指标：激进版 vs 最终版（map.njust，各 24 局）===")
for tag,lab in (("ab10","最终版"),("ab11","激进版")):
    n=0; die=0; conv=0; siegeshot=0; hold=0; waitp=0; escort=0; ok=0
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        t=io.open(fn,encoding="utf-8",errors="replace").read(); n+=1
        if re.search(r'祭司\(编号\d+\)死亡', t): die+=1
        if out(t)=='W': ok+=1
        conv+=len(re.findall(r'玩家 转换(?:高级|一般)敌人', t))
        siegeshot+=len(re.findall(r'>> Priest converting Siege Workshop', t))
        hold+=len(re.findall(r'\[SIEGE-HOLD', t))
        waitp+=len(re.findall(r'\[SIEGE-WAIT', t))
        escort+=len(re.findall(r'\[PRIEST-ESCORT', t))
    print("  %s: 胜=%2d/24  祭司死=%2d | 感化成功=%.2f/局 | 武器厂感化令=%.2f/局 | SIEGE-HOLD=%.2f/局 | PRIEST-ESCORT=%.2f/局" % (
        lab, ok, die, conv/n, siegeshot/n, hold/n, escort/n))