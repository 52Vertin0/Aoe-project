# -*- coding: utf-8 -*-
"""交叉验证：撤退窗口帧 vs HumanMove 日志，排除帧对齐伪影。"""
import re, glob, collections

RE_KIT = re.compile(r"\[KIT-R f=(\d+)\] SN=(\d+) dK=([\d.]+).*?stage=(\d+) stuck=(\d+) aged=(\d+) self=\(([\d.-]+),([\d.-]+)\) tgt=\(([\d.-]+),([\d.-]+)\)")
RE_MOVE = re.compile(r"HumanMove:([\u4e00-\u9fa5A-Za-z.]+) (\d+) 移动至 \(([\d.]+),([\d.]+)\)")

FILES = sorted(glob.glob("gi*.ait"), key=lambda f: int(re.search(r"(\d+)", f).group(1)))

kit_all = []          # (file, frame, sn, stage, tgtx_gr, tgty_gr, selfx, selfy)
move_all = []         # (file, frame, sn, x, y)
move_cnt = 0
for f in FILES:
    for line in open(f, encoding="utf-8", errors="replace"):
        p = line.split(" | ", 3)
        if len(p) < 4:
            continue
        try:
            fr = int(p[1])          # ★ frame 在 ait 行的 p[1]（p[3] 里只有 flag|message）
        except ValueError:
            continue
        body = p[3]
        m = RE_KIT.search(body)
        if m:
            kit_all.append((f, int(m.group(1)), int(m.group(2)), int(m.group(4)),
                            float(m.group(9)), float(m.group(10)),
                            float(m.group(7)), float(m.group(8))))
            continue
        m = RE_MOVE.search(body)
        if m:
            move_cnt += 1
            move_all.append((f, fr, int(m.group(2)), float(m.group(3)), float(m.group(4))))

print("=" * 78)
print("【A】日志总量")
print("   KIT-R 撤退窗口        : %d" % len(kit_all))
print("   全局 HumanMove 日志行 : %d" % move_cnt)

# 按 (file, sn) 建索引
mv_idx = collections.defaultdict(list)
for f, fr, sn, x, y in move_all:
    mv_idx[(f, sn)].append((fr, x, y))

print()
print("=" * 78)
print("【B】多窗口容差匹配（同 SN、帧差 ≤TOL）")
for TOL in (0, 1, 3, 10, 30):
    hit = 0
    for f, fr, sn, st, tx, ty, sx, sy in kit_all:
        lst = mv_idx.get((f, sn))
        if lst and any(abs(m[0] - fr) <= TOL for m in lst):
            hit += 1
    print("   TOL=%-3d 帧 → 命中 %5d / %d  (%.1f%%)" % (TOL, hit, len(kit_all), 100.0 * hit / len(kit_all)))

print()
print("=" * 78)
print("【C】落点几何校验：KIT-R 的 tgt 是否落在 HumanMove 实际下发点上")
# ai 的 kitX/kitY 是像素坐标；日志 tgt=(x/BL, y/BL) ⇒ 还原为格
tol_hit = near_hit = far_hit = no_mv = 0
for f, fr, sn, st, tx, ty, sx, sy in kit_all:
    lst = mv_idx.get((f, sn))
    cand = [m for m in (lst or []) if abs(m[0] - fr) <= 3]
    if not cand:
        no_mv += 1
        continue
    # HumanMove 落点(像素) / BL 后与 tgt(格) 比对
    BL = 35.777
    best = min((( (m[1]/BL - tx)**2 + (m[2]/BL - ty)**2 ) ** 0.5) for m in cand)
    if best < 0.5:
        tol_hit += 1
    elif best < 3.0:
        near_hit += 1
    else:
        far_hit += 1
print("   ±3 帧内无任何 HumanMove       : %d (%.1f%%)" % (no_mv, 100.0 * no_mv / len(kit_all)))
print("   有且落点一致(<0.5 格)         : %d (%.1f%%)" % (tol_hit, 100.0 * tol_hit / len(kit_all)))
print("   有但落点接近(0.5~3 格)        : %d (%.1f%%)" % (near_hit, 100.0 * near_hit / len(kit_all)))
print("   有但落点完全不同(>3 格)       : %d (%.1f%%)" % (far_hit, 100.0 * far_hit / len(kit_all)))

print()
print("=" * 78)
print("【D】单兵时间线样本（窗口最多的复合弓兵）")
c = collections.Counter(k[2] for k in kit_all)
for sn, n in c.most_common(2):
    print("   --- SN=%d (%d 个窗口) ---" % (sn, n))
    f = [k[0] for k in kit_all if k[2] == sn][0]
    evs = []
    for line in open(f, encoding="utf-8", errors="replace"):
        p = line.split(" | ", 3)
        if len(p) < 4:
            continue
        body = p[3]
        m = RE_KIT.search(body)
        if m and int(m.group(2)) == sn:
            evs.append((int(m.group(1)), "KIT st=%s stuck=%s self=(%s,%s) tgt=(%s,%s)"
                        % (m.group(4), m.group(5), m.group(7), m.group(8), m.group(9), m.group(10))))
            continue
        m = RE_MOVE.search(body)
        if m and int(m.group(2)) == sn:
            evs.append((int(m.group(2)), "MOVE -> (%.1f,%.1f)格" % (float(m.group(4)) / 35.777, float(m.group(5)) / 35.777)))
    evs.sort()
    for fr, t in evs[:24]:
        print("      %-7d %s" % (fr, t))
