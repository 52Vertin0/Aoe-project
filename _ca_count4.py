# -*- coding: utf-8 -*-
import io, re, glob, statistics as st
g = r"C:\new-aoe3.0.7g"
BEAT = re.compile(r'\[BEAT f=(\d+) b=\d+\] st=(\w+)\*? .*? \| a=(\d+) hop=(\d+) arch=(\d+) oth=(\d+)')
def med(v): return st.median(v) if v else None
def outcome(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    if 'DEFEAT: Town Center destroyed' in t: return 'T'
    return 'U'
for tag in ("pe2","ca1"):
    gW={'W':[], 'P':[], 'U':[]}; gH={'W':[], 'P':[], 'U':[]}; gPk={'W':[], 'P':[], 'U':[]}
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        t=io.open(fn,encoding="utf-8",errors="replace").read()
        rows=[(int(m.group(5)), int(m.group(4))) for m in BEAT.finditer(t) if m.group(2)=="ATK"]  # (arch, hop)
        if not rows: continue
        o=outcome(t)
        gW[o].append(rows[0][0]); gH[o].append(rows[0][1]); gPk[o].append(max(r[0] for r in rows))
    print("=== %s ===" % tag)
    for k in ("W","P","U"):
        v=gW[k]
        if v: print("  %s n=%2d | 反攻起点 arch: 中位=%.0f 均值=%.1f 范围=%d~%d | 起点 hop 中位=%.0f | 反攻峰值 arch 中位=%.0f" % (
            k, len(v), med(v), sum(v)/len(v), min(v), max(v), med(gH[k]), med(gPk[k])))
    print()