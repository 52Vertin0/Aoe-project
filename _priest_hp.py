# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
g = r"C:\new-aoe3.0.7g"
B  = re.compile(r'\[BEAT f=(\d+) b=\d+\] st=(\w+)\*? .*? pr=\(sn(\d+) st(\d+) hp(\d+)/(\d+) ccd(-?\d+)\)')
def outcome(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    if 'DEFEAT: Town Center destroyed' in t: return 'T'
    return 'U'
def med(v): return st.median(v) if v else None
rows=[]
for fn in sorted(glob.glob(g+"\\pe2_map_r0_*.ait")):
    t=io.open(fn,encoding="utf-8",errors="replace").read()
    s=[(int(m.group(1)), m.group(2), int(m.group(4)), int(m.group(5)), int(m.group(6))) for m in B.finditer(t)]  # f, state, prSt, hp, max
    o=outcome(t)
    atk=[r for r in s if r[1]=="ATK"]
    if not atk: continue
    rows.append((fn.split("\\")[-1], o, atk))
print("=== 祭司在【反攻期】的 HP 轨迹（pe2, 47 局有反攻采样）===")
P=[r for r in rows if r[1]=="P"]; W=[r for r in rows if r[1]=="W"]; U=[r for r in rows if r[1]=="U"]
for label,grp in (("祭司死(P)",P),("胜(W)",W),("超时(U)",U)):
    if not grp: continue
    below60=[]; minHP=[]; lastHP=[]; firstTime=[]; diesInCast=[]
    for name,o,atk in grp:
        mx=atk[0][4]
        b=[r for r in atk if r[3] <= 0.6*mx]
        below60.append(len(b))
        minHP.append(min(r[3] for r in atk))
        lastHP.append(atk[-1][3])
        if b: firstTime.append(atk.index(b[0]))
        if atk[-1][2]==2: diesInCast.append(name)   # prSt==2 = WORKING
    print("%-10s n=%2d | HP≤60%%采样数 中位=%.0f | 最低HP 中位=%.0f | 末采样HP 中位=%.0f | 末采样处于WORKING(st2) 的局=%d" % (
        label, len(grp), med(below60), med(minHP), med(lastHP), len(diesInCast)))
print()
print("=== 祭司死局：反攻期 HP 由满血掉到 ≤60%% 用了几次采样（BEAT 周期≈150帧）===")
for name,o,atk in P:
    mx=atk[0][4]
    idx=[i for i,r in enumerate(atk) if r[3] <= 0.6*mx]
    full=[i for i,r in enumerate(atk) if r[3] >= mx]
    print("  %-20s 采样数=%3d  首次≤60%%: 采样#%s  最后满血: 采样#%s  ⇒ 落差采样数≈%s  末HP=%d  ccd=%d" % (
        name, len(atk), (idx[0] if idx else "-"), (full[-1] if full else "-"),
        (idx[0]-full[-1]) if (idx and full) else "-", atk[-1][3], atk[-1][4]))