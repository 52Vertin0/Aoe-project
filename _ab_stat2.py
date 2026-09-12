# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
from collections import Counter
g = r"C:\new-aoe3.0.7g"
LINE=re.compile(r'^(\d+):(\d+):(\d+) \| (\d+) \| (\w+) \| (-?\d+) \| (.*)$')
OK=re.compile(r'玩家 转换(高级敌人|一般敌人)')
ATK=re.compile(r'\[BEAT f=\d+ b=\d+\] st=ATK')
def med(v): return st.median(v) if v else 0
res={}
for tag in ("ab0","ab1"):
    rows=[]
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        txt=io.open(fn,encoding="utf-8",errors="replace").read()
        win='被祭司转换,归属阵营1->0' in txt
        atk=None; ok=0
        for line in txt.splitlines():
            m=LINE.match(line)
            if not m: continue
            f=int(m.group(4)); b=m.group(7)
            if ATK.search(b) and atk is None: atk=f
            if atk is not None and f>=atk and OK.search(b): ok+=1
        rows.append((win, ok, atk is not None))
    res[tag]=rows
    n=len(rows); v=[r[1] for r in rows]
    print("%s: n=%d 胜=%d(%.0f%%) ATK局=%d | 反攻期感化 均值=%.2f 中位=%.0f 最大=%d" % (
        tag, n, sum(1 for r in rows if r[0]), 100.0*sum(1 for r in rows if r[0])/n,
        sum(1 for r in rows if r[2]), sum(v)/n, med(v), max(v)))
print()
print("  分布 ab0: " + "  ".join("%d个:%d局"%kv for kv in sorted(Counter(r[1] for r in res["ab0"]).items())))
print("  分布 ab1: " + "  ".join("%d个:%d局"%kv for kv in sorted(Counter(r[1] for r in res["ab1"]).items())))