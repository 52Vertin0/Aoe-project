# -*- coding: utf-8 -*-
"""
量化「撤退令被反向指令抵消」。
判据：撤退窗口帧 fr 的落点 R_pt，与该 SN 在 (fr, fr+N] 内实际下发的 HumanMove 落点 M_pt 比较：
  • M_pt ≈ R_pt            → 撤退令生效(同一目标)
  • M_pt 显著不同          → 被别的指令覆盖(推进/集结)
另外单独统计：撤退窗口后 60 帧内是否出现 HumanAction 攻击令（引擎会逼近敌人 ⇒ 抵消撤退）。
"""
import re, glob, collections

RE_KIT = re.compile(r"\[KIT-R f=(\d+)\] SN=(\d+) dK=([\d.]+).*?stage=(\d+) stuck=(\d+) aged=(\d+) self=\(([\d.-]+),([\d.-]+)\) tgt=\(([\d.-]+),([\d.-]+)\)")
RE_MOVE = re.compile(r"HumanMove:[\u4e00-\u9fa5A-Za-z.]+ (\d+) 移动至 \(([\d.]+),([\d.]+)\)")
RE_ATK = re.compile(r"HumanAction:[\u4e00-\u9fa5A-Za-z.]+ (\d+) 设置攻击目标为 ")
BL = 35.777

FILES = sorted(glob.glob("gi*.ait"), key=lambda f: int(re.search(r"(\d+)", f).group(1)))

tot = dict(kit=0, over_mv=0, over_atk=0, same_mv=0, no_follow=0, after_over=0)
cover_dist = []
# 额外：按 SN 聚合「撤退落点集」与「全部移动落点集」的规模比
per_sn = collections.defaultdict(lambda: dict(kitp=set(), allp=set()))

for f in FILES:
    kit_ev, mv_ev, atk_ev = [], [], []
    for line in open(f, encoding="utf-8", errors="replace"):
        p = line.split(" | ", 3)
        if len(p) < 4:
            continue
        try:
            fr = int(p[1])
        except ValueError:
            continue
        m = RE_KIT.search(p[3])
        if m:
            kit_ev.append((int(m.group(1)), int(m.group(2)), float(m.group(9)), float(m.group(10))))
            continue
        m = RE_MOVE.search(p[3])
        if m:
            mv_ev.append((fr, int(m.group(1)), float(m.group(2)) / BL, float(m.group(3)) / BL))
            continue
        m = RE_ATK.search(p[3])
        if m:
            atk_ev.append((fr, int(m.group(1))))

    mv_idx = collections.defaultdict(list)
    for fr, sn, x, y in mv_ev:
        mv_idx[sn].append((fr, x, y))
    atk_idx = collections.defaultdict(list)
    for fr, sn in atk_ev:
        atk_idx[sn].append(fr)

    for fr, sn, tx, ty in kit_ev:
        tot["kit"] += 1
        per_sn[sn]["kitp"].add((round(tx, 1), round(ty, 1)))
        # ★ 窗口后 90 帧内的【全部】移动令（不只第一条）—— 第一条必然是本窗口撤退令，
        #   真正的抵消发生在【其后】。旧口径只看第一条 ⇒ 恒 99.8%，漏掉全部推进令。
        follows = [m for m in mv_idx.get(sn, []) if 0 < m[0] - fr <= 90]
        if not follows:
            tot["no_follow"] += 1
        else:
            follows.sort()
            f0 = follows[0]
            d0 = ((f0[1] - tx) ** 2 + (f0[2] - ty) ** 2) ** 0.5
            cover_dist.append(d0)
            if d0 < 3.0:
                tot["same_mv"] += 1
            else:
                tot["over_mv"] += 1
            # 之后是否还有【不同落点】的移动令
            rest = [m for m in follows[1:]
                    if ((m[1] - tx) ** 2 + (m[2] - ty) ** 2) ** 0.5 > 3.0]
            if rest:
                tot["after_over"] += 1
        if any(0 < a - fr <= 60 for a in atk_idx.get(sn, [])):
            tot["over_atk"] += 1

    for fr, sn, x, y in mv_ev:
        per_sn[sn]["allp"].add((round(x, 1), round(y, 1)))

print("=" * 86)
print("【1】撤退窗口之后到底发生了什么")
print("   撤退窗口总数                     : %d" % tot["kit"])
print("   后续 90 帧内该兵【没有】任何移动令 : %d (%.1f%%)" % (tot["no_follow"], 100.0 * tot["no_follow"] / tot["kit"]))
print("   后续移动令 = 同一撤退落点(<3格)   : %d (%.1f%%)  ← 撤退令是最后一手" % (tot["same_mv"], 100.0 * tot["same_mv"] / tot["kit"]))
print("   ★后续移动令 = 完全不同落点(>3格) : %d (%.1f%%)  ← 被别的指令覆盖(推进/集结)" % (tot["over_mv"], 100.0 * tot["over_mv"] / tot["kit"]))
print("   ★★撤退令之后【又冒出】不同落点   : %d (%.1f%%)  ← 撤退刚发完就被反向指令顶掉" % (tot["after_over"], 100.0 * tot["after_over"] / tot["kit"]))
print("   ★后续 60 帧内出现攻击令          : %d (%.1f%%)  ← 引擎会自行逼近敌人，抵消撤退" % (tot["over_atk"], 100.0 * tot["over_atk"] / tot["kit"]))
if cover_dist:
    import statistics
    print("   覆盖落点距撤退落点: 中位 %.1f 格 / 均值 %.1f 格 / 最大 %.1f 格"
          % (statistics.median(cover_dist), statistics.mean(cover_dist), max(cover_dist)))

print()
print("=" * 86)
print("【2】每个远程兵「落点集合」规模 —— 撤退落点只占其全部移动落点的一小部分？")
print("   %-8s %10s %12s %8s" % ("SN", "全部落点数", "撤退落点数", "占比"))
rows = []
for sn, d in per_sn.items():
    if len(d["kitp"]) >= 3 and len(d["allp"]) >= 5:
        rows.append((sn, len(d["allp"]), len(d["kitp"]), 100.0 * len(d["kitp"]) / len(d["allp"])))
rows.sort(key=lambda r: r[3])
for sn, a, k, r in rows[:14]:
    print("   %-8d %10d %12d %7.0f%%" % (sn, a, k, r))
