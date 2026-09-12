# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
from collections import Counter, defaultdict
g = r"C:\new-aoe3.0.7g"
LC = re.compile(r'\[LC-DBG f=(\d+)\] siegeSN=(-?\d+) mem=\((-?[\d.]+),(-?[\d.]+)\) dS=([\d.]+) hp=([\d.]+) ccd=(-?\d+) st=(\d+) mvcd=(\d+) gT=(\d+) seen=(\d+) nearT=(-?[\d.]+) loc=(\d+)')
WAIT=re.compile(r'\[SIEGE-WAIT f=(\d+)\] hp=([\d.]+) towers=(\d+) seen=(\d+) alive=(\d+) dS=([\d.]+) lim=(\d+)')
HOLD=re.compile(r'\[SIEGE-HOLD f=(\d+)\]')
rows=[]; waits=0; holds=0
for fn in sorted(glob.glob(g+"\\pe2_map_r0_*.ait")):
    for line in io.open(fn,encoding="utf-8",errors="replace"):
        m=LC.search(line)
        if m: rows.append((int(m.group(1)), int(m.group(2)), float(m.group(5)), int(m.group(10)), int(m.group(11)), float(m.group(12))))
        if WAIT.search(line): waits+=1
        if HOLD.search(line): holds+=1
n=len(rows)
print("LC-DBG 采样 n=%d" % n)
gt=[r[3] for r in rows]
print("敌箭塔数 gT 分布: 中位=%.0f  p25=%.0f p75=%.0f 最大=%d" % (st.median(gt), sorted(gt)[n//4], sorted(gt)[3*n//4], max(gt)))
print("gT<=5(塔已清够,放行) 占比 = %.1f%% ; gT>5(被闸住) = %.1f%%" % (100.0*sum(1 for x in gt if x<=5)/n, 100.0*sum(1 for x in gt if x>5)/n))
seen=[r[4] for r in rows]
print("已探明敌建筑 seen 分布: 中位=%.0f 最小=%d  ; seen==0(视野丢失) 占比=%.1f%%" % (st.median(seen), min(seen), 100.0*sum(1 for x in seen if x==0)/n))
print("siegeSN==-1 (武器厂未知) 占比 = %.1f%%" % (100.0*sum(1 for r in rows if r[1]==-1)/n))
print()
print("=== 按 gT 分档看 dS（距离）===")
for lo,hi,lab in ((0,5,"gT<=5 放行"),(6,10,"gT 6-10"),(11,99,"gT>10")):
    v=[r[2] for r in rows if lo<=r[3]<=hi]
    if v: print("   %-12s n=%4d  dS 中位=%.0f 格   dS<=12 占比=%.1f%%" % (lab, len(v), st.median(v), 100.0*sum(1 for x in v if x<=12)/len(v)))
print()
print("SIEGE-WAIT 打印次数=%d (%.1f/局) ; SIEGE-HOLD=%d" % (waits, waits/48.0, holds))