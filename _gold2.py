# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
from collections import Counter
g = r"C:\new-aoe3.0.7g"
LINE=re.compile(r'^(\d+):(\d+):(\d+) \| (\d+) \| (\w+) \| (-?\d+) \| (.*)$')
ECO=re.compile(r'ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+) \|\| goldRich:(\d)')
ATK=re.compile(r'\[BEAT f=\d+ b=\d+\] st=ATK')
def pct(v,p):
    v=sorted(v); return v[int(len(v)*p)] if v else 0
for tag in ("ab3","ab2"):
    fin=[]; mx=[]; richfrac=[]; gwork=[]; n=0
    atk_g_start=[]; atk_g_end=[]; atk_g_delta=[]; wood_atk=[]
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        n+=1; seq=[]; atkf=None
        for line in io.open(fn,encoding="utf-8",errors="replace"):
            m=LINE.match(line.rstrip("\n"))
            if not m: continue
            f=int(m.group(4)); b=m.group(7)
            if ATK.search(b) and atkf is None: atkf=f
            e=ECO.search(b)
            if e: seq.append((f,int(e.group(4)),int(e.group(7)),int(e.group(9)),int(e.group(5))))
        if not seq: continue
        golds=[x[1] for x in seq]
        fin.append(golds[-1]); mx.append(max(golds)); gwork += [x[2] for x in seq]
        if atkf is not None:
            a=[x for x in seq if x[0]>=atkf]
            if len(a)>=2:
                atk_g_start.append(a[0][1]); atk_g_end.append(a[-1][1])
                atk_g_delta.append(a[-1][1]-a[0][1])
                richfrac.append(sum(x[3] for x in a)/len(a))
                wood_atk.append(sum(x[4] for x in a)/len(a))
    print("=== %s (n=%d) ===" % (tag,n))
    print("   终局黄金 中位=%.0f p75=%.0f 最大=%d   |  峰值 中位=%.0f" % (st.median(fin),pct(fin,.75),max(fin),st.median(mx)))
    print("   反攻开始黄金 中位=%.0f  →  结束时 中位=%.0f   Δ中位=%+.0f" % (
        st.median(atk_g_start), st.median(atk_g_end), st.median(atk_g_delta)))
    up=sum(1 for d in atk_g_delta if d>0); dn=sum(1 for d in atk_g_delta if d<0)
    print("   反攻期黄金【上涨】的局=%d / 下降=%d  ⇒ %s" % (up,dn, "反攻期还在净进账" if up>dn else "反攻期基本在消耗"))
    print("   金工人数分布: " + "  ".join("%d人:%.0f%%"%(k,100.0*v/len(gwork)) for k,v in sorted(Counter(gwork).items())))
    print("   反攻期 goldRich=1 占比 中位=%.0f%%   |   反攻期木材 中位=%.0f" % (100*st.median(richfrac), st.median(wood_atk)))
    print()
# 金矿消耗侧：一局造了多少方阵兵(=40金/个)
print("=== 黄金去向（ab3 48局）===")
tot=0; n=0
for fn in sorted(glob.glob(g+"\\ab3_map_r0_*.ait")):
    t=io.open(fn,encoding="utf-8",errors="replace").read()
    ph=len(re.findall(r'产生了新的方阵兵', t))
    tot+=ph; n+=1
print("   方阵兵产量 均值=%.2f 个/局  ⇒ 黄金消耗 ≈%.0f/局（40金/个）" % (tot/n, 40.0*tot/n))
print("   另加护甲二级科技 50+50=100 金（若研究）")
print("   而终局剩余黄金 中位=244 ⇒ 单看存量不算爆仓，但反攻期若净进账即为纯浪费")