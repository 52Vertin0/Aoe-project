# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
from collections import Counter
g = r"C:\new-aoe3.0.7g"
LINE=re.compile(r'^(\d+):(\d+):(\d+) \| (\d+) \| (\w+) \| (-?\d+) \| (.*)$')
LC = re.compile(r'\[LC-DBG f=\d+\] siegeSN=(-?\d+) mem=\((-?[\d.]+),(-?[\d.]+)\) dS=([\d.]+)')
OK=re.compile(r'玩家 转换(高级敌人|一般敌人)')
ATK=re.compile(r'\[BEAT f=\d+ b=\d+\] st=ATK')
ADV=re.compile(r'>> Priest ADVANCE to Siege f=\d+ d=([\d.]+)')
CLAMP=re.compile(r'PRIEST-WITH-ARMY')
def pct(v,p):
    v=sorted(v); return v[int(len(v)*p)] if v else 0
for tag in ("ab2","ab3"):
    ds_all=[]; ds_known=[]; adv=[]; conv=0; clamp=0; n=0; wins=0
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        n+=1
        txt=io.open(fn,encoding="utf-8",errors="replace").read()
        if '被祭司转换,归属阵营1->0' in txt: wins+=1
        atk=None; ok=0
        for line in txt.splitlines():
            m=LINE.match(line)
            if not m: continue
            f=int(m.group(4)); b=m.group(7)
            if ATK.search(b) and atk is None: atk=f
            if atk is not None and f>=atk and OK.search(b): ok+=1
            m2=LC.search(b)
            if m2:
                d=float(m2.group(4)); ds_all.append(d)
                if int(m2.group(1))!=-1: ds_known.append(d)
            m3=ADV.search(b)
            if m3: adv.append(float(m3.group(1)))
            if CLAMP.search(b): clamp+=1
        conv+=ok
    def line(lab,v):
        if not v: return "   %-16s -" % lab
        return "   %-16s n=%4d 中位=%5.1f 均值=%5.1f p10=%4.0f p25=%4.0f p75=%4.0f  <=12:%5.1f%%  <=18:%5.1f%%" % (
            lab, len(v), st.median(v), sum(v)/len(v), pct(v,.1),pct(v,.25),pct(v,.75),
            100.0*sum(1 for x in v if x<=12)/len(v), 100.0*sum(1 for x in v if x<=18)/len(v))
    print("=== %s (n=%d, 胜=%d=%.0f%%) ===" % (tag,n,wins,100.0*wins/n))
    print(line("dS 全部",ds_all))
    print(line("dS 已知武器厂",ds_known))
    print(line("ADVANCE 时 d",adv))
    print("   反攻期感化单位总数=%d (%.2f/局)   PRIEST-WITH-ARMY 钉回=%d" % (conv, conv/n, clamp))
    print()