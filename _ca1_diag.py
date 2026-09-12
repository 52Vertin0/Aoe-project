# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
g = r"C:\new-aoe3.0.7g"
NEW = re.compile(r'产生了新的(.+?)\(编号:\d+\)')
def stats(tag):
    rows = []
    for fn in sorted(glob.glob(g + "\\" + tag + "_map_r0_*.ait")):
        t = io.open(fn, encoding="utf-8", errors="replace").read()
        # frame>0 = real production
        prod = {}
        for m in re.finditer(r'\|\s*(\d+)\s*\|\s*\w+\s*\|\s*\d+\s*\|\s+产生了新的(.+?)\(编号:\d+\)', t):
            fr = int(m.group(1))
            if fr == 0: continue
            prod[m.group(2).strip()] = prod.get(m.group(2).strip(), 0) + 1
        # last ECO line
        ecos = re.findall(r'workers F(\d+) W(\d+) G(\d+) S(\d+)', t)
        lastEco = ecos[-1] if ecos else None
        # final army size: count [BEAT lines? use last "现役" style; fallback: none
        rows.append((fn.split("\\")[-1], prod, lastEco))
    def avg(key):
        vals = [r[1].get(key, 0) for r in rows]
        return (sum(vals)/len(vals)) if vals else 0
    return rows, avg
for tag in ("pe2", "ca1"):
    rows, avg = stats(tag)
    print("=== %s : %d games ===" % (tag, len(rows)))
    for k in ("战车弓兵", "复合弓兵", "方阵兵", "棍棒兵", "投石车", "村民", "祭司"):
        print("  %-8s avg produced = %.2f" % (k, avg(k)))
    eco = [r[2] for r in rows if r[2]]
    if eco:
        F = sum(int(e[0]) for e in eco)/len(eco); W = sum(int(e[1]) for e in eco)/len(eco)
        G = sum(int(e[2]) for e in eco)/len(eco); S = sum(int(e[3]) for e in eco)/len(eco)
        print("  last-ECO avg workers  F=%.1f W=%.1f G=%.1f S=%.1f" % (F, W, G, S))
    print()