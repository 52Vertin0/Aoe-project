# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
from collections import Counter
g = r"C:\new-aoe3.0.7g"
LC = re.compile(r'\[LC-DBG f=(\d+)\] siegeSN=(-?\d+) mem=\((-?[\d.]+),(-?[\d.]+)\) dS=([\d.]+) hp=([\d.]+) ccd=(-?\d+) st=(\d+) mvcd=(\d+)')
ADV= re.compile(r'>> Priest ADVANCE to Siege f=(\d+) d=([\d.]+)')
BEAT=re.compile(r'\[BEAT f=(\d+) b=\d+\] st=(\w+)\*?')
CNT =re.compile(r'PRIEST-WITH-ARMY f=(\d+) ')
PR_ST=re.compile(r'Priest st=\d+ hp=[\d.]+ nearE=([\d.]+) threat=[\d.]+ mode=-?\d+ \| ally=(\d+) wound25=(\d+) nearAlly=([\d.]+)BL cd=(\d+)')
ds=[]; advd=[]; clamp=0; nearE=[]; nearAlly=[]; ally=[]
for fn in sorted(glob.glob(g+"\\pe2_map_r0_*.ait")):
    for line in io.open(fn,encoding="utf-8",errors="replace"):
        m=LC.search(line)
        if m and float(m.group(5))<1e4: ds.append(float(m.group(5)))
        m=ADV.search(line)
        if m: advd.append(float(m.group(2)))
        if CNT.search(line): clamp+=1
        m=PR_ST.search(line)
        if m:
            ne=float(m.group(1)); na=float(m.group(4))
            if ne<1e6: nearE.append(ne)
            nearAlly.append(na); ally.append(int(m.group(2)))
def pct(v,p): 
    v=sorted(v); return v[int(len(v)*p)] if v else 0
n=len(ds)
print("=== 反攻期祭司→敌【武器厂】距离 dS（LC-DBG 采样，n=%d，约每 12 秒 1 个）===" % n)
print("   中位=%.1f 格   均值=%.1f   最小=%.1f   最大=%.1f" % (st.median(ds), sum(ds)/n, min(ds), max(ds)))
print("   分位: p10=%.0f p25=%.0f p50=%.0f p75=%.0f p90=%.0f" % (pct(ds,.1),pct(ds,.25),pct(ds,.5),pct(ds,.75),pct(ds,.9)))
print("   dS<=12(感化射程内)=%.1f%%   dS<=18=%.1f%%   18<dS<=30=%.1f%%   dS>30=%.1f%%" % (
    100.0*sum(1 for x in ds if x<=12)/n, 100.0*sum(1 for x in ds if x<=18)/n,
    100.0*sum(1 for x in ds if 18<x<=30)/n, 100.0*sum(1 for x in ds if x>30)/n))
print()
print("=== ADVANCE 打印里的 d（每次推进令时的 dSiege，n=%d）===" % len(advd))
print("   中位=%.1f  均值=%.1f  p25=%.0f  p75=%.0f" % (st.median(advd), sum(advd)/len(advd), pct(advd,.25), pct(advd,.75)))
print()
print("=== 祭司与【最近友军】距离 nearAlly ===  中位=%.1f格  均值=%.1f  ; 周边友军数 ally 中位=%.0f" % (
    st.median(nearAlly), sum(nearAlly)/len(nearAlly), st.median(ally)))
print("=== 祭司与【最近敌军】距离 nearE === 中位=%.1f格 (有敌兵时, n=%d)" % (st.median(nearE), len(nearE)))
print()
print("PRIEST-WITH-ARMY 随军钉回 次数/48局 = %d  (%.1f 次/局)" % (clamp, clamp/48.0))