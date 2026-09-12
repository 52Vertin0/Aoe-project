# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
g = r"C:\new-aoe3.0.7g"
HOP = re.compile(r'\[HOPLITE-(?:LATE|ATK) .*?gold=(\d+)\(kept(\d+)\)')
ECO = re.compile(r'ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+)')
LINE= re.compile(r'^(\d+):(\d+):(\d+) \| (\d+) \| (\w+) \| (-?\d+) \| (.*)$')
ATK = re.compile(r'\[BEAT f=\d+ b=\d+\] st=ATK')
gh=[]
for fn in sorted(glob.glob(g+"\\ab3_map_r0_*.ait")):
    for line in io.open(fn,encoding="utf-8",errors="replace"):
        m=HOP.search(line)
        if m: gh.append(int(m.group(1)))
if gh:
    v=sorted(gh)
    print("[1] 产方阵兵时的黄金余额: n=%d  中位=%d  p10=%d  最小=%d   (成本 40 金)" % (len(v), st.median(v), v[int(len(v)*0.1)], v[0]))
for tag in ("ab3","ab2"):
    wd=[]; gd=[]; tot=0; low=0; atkmin=0
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        atk=None
        for line in io.open(fn,encoding="utf-8",errors="replace"):
            m=LINE.match(line.rstrip("\n"))
            if not m: continue
            f=int(m.group(4)); b=m.group(7)
            if ATK.search(b) and atk is None: atk=f
            if atk is None or f<atk: continue
            e=ECO.search(b)
            if e:
                tot+=1; w=int(e.group(2)); gg=int(e.group(4))
                wd.append(w); gd.append(gg)
                if w<70: low+=1
    if wd:
        print("[2] %s 反攻期 ECO 采样 %d 个: 木材中位=%d  黄金中位=%d  木材<70(1个战车弓兵钱)占 %.0f%%" % (tag,tot,st.median(wd),st.median(gd),100.0*low/tot))