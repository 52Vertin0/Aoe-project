# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
g = r"C:\new-aoe3.0.7g"
def med(v):
    v=[x for x in v if x is not None]
    return st.median(v) if v else None
for tag in ("pe2","ca1"):
    bronze=[]; firstCA=[]; firstTower=[]
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        t=io.open(fn,encoding="utf-8",errors="replace").read()
        # first BRONZE marker frame
        m=re.search(r'\| (\d+) \| \w+ \| \d+ \|.*BRONZE', t)
        bronze.append(int(m.group(1)) if m else None)
        # first chariot archer produced (frame>0)
        m2=re.search(r'\| (\d+) \| \w+ \| \d+ \|  产生了新的战车弓兵', t)
        firstCA.append(int(m2.group(1)) if m2 else None)
        # first tower
        m3=re.search(r'\| (\d+) \| \w+ \| \d+ \|  产生了新的箭塔', t)
        firstTower.append(int(m3.group(1)) if m3 else None)
    print("%s: bronze marker n=%d median=%.0f | first chariot-archer n=%d median=%.0f | first tower n=%d median=%.0f" % (
        tag, len([x for x in bronze if x]), med(bronze) or -1,
        len([x for x in firstCA if x]), med(firstCA) or -1,
        len([x for x in firstTower if x]), med(firstTower) or -1))