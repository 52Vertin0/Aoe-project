# -*- coding: utf-8 -*-
import io, re, glob, os
g = r"C:\new-aoe3.0.7g"
def clf_dbg(t):   # 旧口径（依赖 DebugText）
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    if 'DEFEAT: Town Center destroyed' in t: return 'T'
    return 'U'
def clf_eng(t):   # 新口径（只用引擎事件，nodebug 也适用）
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if re.search(r'祭司\(编号\d+\)死亡', t): return 'P'
    return 'U'
print("=== 1) 引擎口径 vs 旧口径：在 debug 日志上是否等价（ab2/ab3 各 48 局）===")
for tag in ("ab2","ab3"):
    a=b=0; mism=[]
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        t=io.open(fn,encoding="utf-8",errors="replace").read()
        x=clf_dbg(t); y=clf_eng(t); a+=1
        if x!=y: mism.append((os.path.basename(fn),x,y))
    from collections import Counter
    print("   %s: 旧口径=%s" % (tag, dict(Counter(clf_dbg(io.open(f,encoding='utf-8',errors='replace').read()) for f in sorted(glob.glob(g+'\\'+tag+'_map_r0_*.ait'))))))
    print("   %s: 新口径=%s" % (tag, dict(Counter(clf_eng(io.open(f,encoding='utf-8',errors='replace').read()) for f in sorted(glob.glob(g+'\\'+tag+'_map_r0_*.ait'))))))
    print("   %s: 不一致 %d 局 %s" % (tag, len(mism), mism[:5]))
print()
print("=== 2) nodebug 版本能否被判分（用 n2/nb1 日志验证）===")
for tag in ("n2","nb1"):
    fs=sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait"))
    if not fs: continue
    print("   %s: %s" % (tag, [clf_eng(io.open(f,encoding="utf-8",errors="replace").read()) for f in fs]))
    t=io.open(fs[0],encoding="utf-8",errors="replace").read()
    print("      有效性判据(旧=需5条[BEAT): [BEAT=%d  → 会被丢弃；新判据'开始向'=%d 可作有效标志" % (t.count("[BEAT"), t.count("开始向")))
print()
print("=== 3) 提速：帧/秒（同批 12 局并发，d2/debug vs n2/nodebug）===")
import statistics as st
def speed(tag, t_end):
    out=[]
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        base=fn[:-4]
        op=base+".out"
        if not os.path.exists(op): continue
        o=io.open(op,encoding="utf-8",errors="replace").read()
        ms=[int(x) for x in re.findall(r'\[OJ-HB\] f=(\d+)', o)]
        if not ms: continue
        dur=t_end-os.path.getmtime(base+".ait")
        out.append(ms[-1]/dur)
    return out
t_end=os.path.getmtime(g+r"\n2_map_r0_1.ait")
for tag in ("d2","n2"):
    v=speed(tag, max(os.path.getmtime(f) for f in glob.glob(g+"\\"+tag+"_map_r0_*.ait")))
    if v: print("   %-4s 帧/秒: 中位=%.0f  各局=%s" % (tag, st.median(v), ",".join("%.0f"%x for x in sorted(v))))