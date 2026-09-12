# -*- coding: utf-8 -*-
import io, re, glob, os, statistics as st
g = r"C:\new-aoe3.0.7g"
def outc(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    if 'DEFEAT: Town Center destroyed' in t: return 'T'
    return 'U'
print("%-14s %6s %8s %10s %10s %s" % ("arm/index","大小MB","行数","结局","用时(分)","引擎事件(开始向/死亡)"))
res={}
for tag in ("d2","d3","n2"):
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait"), key=lambda p:int(re.search(r'_r0_(\d+)',p).group(1))):
        idx=int(re.search(r'_r0_(\d+)',fn).group(1))
        t=io.open(fn,encoding="utf-8",errors="replace").read()
        o=outc(t)
        mt=os.path.getmtime(fn)
        res[(tag,idx)]=(o, mt)
        print("%-14s %6.2f %8d %10s %10s %s" % (tag+"#"+str(idx), len(t)/1048576.0, t.count("\n"),
              o, "", "%d/%d" % (t.count("开始向"), len(re.findall(r'\)死亡', t)))))
print()
print("=== 1) 确定性检验：同一 exe 同下标跑两次（d2 vs d3）===")
same=diff=0
for i in (1,2,3,4):
    a=res[("d2",i)][0]; b=res[("d3",i)][0]
    ok = (a==b)
    same += ok; diff += (not ok)
    print("   index %d : d2=%s  d3=%s   %s" % (i,a,b,"一致" if ok else "★不一致"))
print("   ⇒ 一致 %d / 不一致 %d" % (same,diff))
print()
print("=== 2) 行为等价检验：debug(d2) vs nodebug(n2) 同下标 ===")
same=diff=0
for i in (1,2,3,4):
    a=res[("d2",i)][0]; b=res[("n2",i)][0]
    ok=(a==b); same+=ok; diff+=(not ok)
    print("   index %d : debug=%s  nodebug=%s   %s" % (i,a,b,"一致" if ok else "★不一致"))
print("   ⇒ 一致 %d / 不一致 %d" % (same,diff))
print()
import statistics
d2t=[res[("d2",i)][1] for i in (1,2,3,4)]; n2t=[res[("n2",i)][1] for i in (1,2,3,4)]
print("=== 3) 用时（同批并发，可横向比）===")
print("   debug  d2 完成时刻: " + ", ".join("%.1fs"%((t-min(min(d2t),min(n2t)))) for t in sorted(d2t)))
print("   nodebug n2 完成时刻: " + ", ".join("%.1fs"%((t-min(min(d2t),min(n2t)))) for t in sorted(n2t)))