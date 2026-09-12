# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
from collections import Counter
g = r"C:\new-aoe3.0.7g"
LINE=re.compile(r'^(\d+):(\d+):(\d+) \| (\d+) \| (\w+) \| (-?\d+) \| (.*)$')
OK=re.compile(r'玩家 转换(高级敌人|一般敌人)')
CMD=re.compile(r'HumanAction:祭司 \d+ 设置转换目标为')
ATK=re.compile(r'\[BEAT f=\d+ b=\d+\] st=ATK')
CONVD=re.compile(r'Priest CONVERT\(defense\)')
def med(v): return st.median(v) if v else 0
for tag in ("ab0","ab1"):
    rows=[]
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        txt=io.open(fn,encoding="utf-8",errors="replace").read()
        win='被祭司转换,归属阵营1->0' in txt
        atk=None; last=None; ok=0; cmd=0; convd=0; allok=0
        for line in txt.splitlines():
            m=LINE.match(line)
            if not m: continue
            f=int(m.group(4)); b=m.group(7); last=f
            if ATK.search(b) and atk is None: atk=f
            if OK.search(b):
                allok+=1
                if atk is not None and f>=atk: ok+=1
            if atk is not None and f>=atk:
                if CMD.search(b): cmd+=1
                if CONVD.search(b): convd+=1
        if atk is None: continue
        rows.append((fn.split("\\")[-1], win, ok, cmd, convd, allok, (last-atk)/25.0/60.0))
    W=[r for r in rows if r[1]]
    n=len(rows)
    P=[]
    P.append("=== %s (n=%d, 胜=%d=%.0f%%) ===" % (tag, n, len(W), 100.0*len(W)/n))
    for idx,lab in ((2,"反攻期感化【成功】单位"),(3,"反攻期感化【起手】"),(4,"反攻期 CONVERT(defense) 打印"),(5,"全局感化成功")):
        v=[r[idx] for r in rows]
        P.append("   %-28s 均值=%.2f  中位=%.1f  最大=%d" % (lab, sum(v)/n, med(v), max(v)))
    P.append("   反攻期时长(分钟)             均值=%.2f" % (sum(r[6] for r in rows)/n))
    P.append("   反攻期感化成功率(成功/起手)  = %.0f%%" % (100.0*sum(r[2] for r in rows)/max(1,sum(r[3] for r in rows))))
    P.append("   反攻期感化分布: " + "  ".join("%d个:%d局"%kv for kv in sorted(Counter(r[2] for r in rows).items())))
    P.append("   胜局反攻期感化均值=%.2f / 负局=%.2f" % (
        (sum(r[2] for r in W)/len(W)) if W else 0,
        (sum(r[2] for r in rows if not r[1])/max(1,len(rows)-len(W)))))
    print("\n".join(P)); print()