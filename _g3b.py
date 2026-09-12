import io, re, glob
g = r"C:\new-aoe3.0.7g"
pat = re.compile(r'\[HOPLITE-(?:LATE|ATK)')
n=0; ex=[]
for fn in sorted(glob.glob(g+"\\ab3_map_r0_*.ait")):
    for line in io.open(fn,encoding="utf-8",errors="replace"):
        if pat.search(line):
            n+=1
            if len(ex)<3: ex.append(line.strip()[-160:])
print("HOPLITE 行数 =", n)
for e in ex: print("  ", e)