# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
g = r"C:\new-aoe3.0.7g"
LC = re.compile(r'\[LC-DBG f=(\d+)\] siegeSN=(-?\d+) mem=\((-?[\d.]+),(-?[\d.]+)\) dS=([\d.]+) hp=([\d.]+) ccd=(-?\d+) st=(\d+) mvcd=(\d+) gT=(\d+) seen=(\d+) nearT=(-?[\d.]+) loc=(\d+)')
rows=[]
for fn in sorted(glob.glob(g+"\\pe2_map_r0_*.ait")):
    for line in io.open(fn,encoding="utf-8",errors="replace"):
        m=LC.search(line)
        if m: rows.append((int(m.group(2)), float(m.group(5)), int(m.group(4+7))))  # siegeSN, dS, seen
known=[r for r in rows if r[0]!=-1]; unknown=[r for r in rows if r[0]==-1]
def stats(v,lab):
    if not v: print("   %s: 无样本"%lab); return
    n=len(v); ds=[x[1] for x in v]
    print("   %-22s n=%4d (%4.1f%%)  dS中位=%5.1f  dS<=12:%5.1f%%  dS<=18:%5.1f%%  dS<=26:%5.1f%%" % (
        lab, n, 100.0*n/len(rows), st.median(ds), 100.0*sum(1 for x in ds if x<=12)/n,
        100.0*sum(1 for x in ds if x<=18)/n, 100.0*sum(1 for x in ds if x<=26)/n))
print("=== 反攻期：武器厂【已侦察到】vs【未侦察到】时的祭司距离 ===")
stats(rows,"全部")
stats(known,"siegeSN!=-1 已知目标")
stats(unknown,"siegeSN==-1 未侦察到")
print()
# 已知目标时，祭司是否最终进入 12 格？
k=sorted(known, key=lambda r:r[1])
print("=== 已知目标时 dS 的分位 ===")
ds=sorted(x[1] for x in known); n=len(ds)
print("   p10=%.0f p25=%.0f p50=%.0f p75=%.0f p90=%.0f 最小=%.1f" % (ds[int(n*.1)],ds[int(n*.25)],ds[int(n*.5)],ds[int(n*.75)],ds[int(n*.9)],ds[0]))
print()
# 每局：ATK 期内 已知目标的时间占比 & 最终是否进入 12 格
print("=== 逐局（前 16）：ATK 内 已知目标采样占比 / 己方最小 dS ===")
per={}
for fn in sorted(glob.glob(g+"\\pe2_map_r0_*.ait")):
    tot=0; kn=0; mind=1e9
    for line in io.open(fn,encoding="utf-8",errors="replace"):
        m=LC.search(line)
        if not m: continue
        tot+=1
        if int(m.group(2))!=-1:
            kn+=1; mind=min(mind, float(m.group(5)))
    if tot: per[fn.split("\\")[-1]]=(tot,kn,mind)
for k2,(tot,kn,mind) in list(per.items())[:16]:
    print("   %-20s 采样%3d  已知目标%3d(%5.1f%%)  最小dS=%s" % (k2,tot,kn,100.0*kn/tot, ("%.1f"%mind) if mind<1e8 else "-"))