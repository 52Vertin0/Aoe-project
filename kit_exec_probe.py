# -*- coding: utf-8 -*-
"""
拉扯有效性探针 —— 回答"撤退令到底执行了没有"。

核心判据：KIT-R 日志里 self=(DR/BL, UR/BL) 是【单位当前坐标】。
  相邻两个 KIT-R 窗口之间，若 self 位移 < 0.5 格 ⇒ 该窗口的撤退令【空转】(单位没走)。
  与 dK 交叉验证：如果 dK 同时在减小 ⇒ 单位被敌人逼近，撤退彻底失败（用户看到的画面）。

同时区分两类撤退窗口：
  stage=1 远离敌档 / stage=2 朝 TC 档 / stage=3 朝祭司档 / stage=0 三档全败（无落点）
"""
import re, glob, os, statistics, collections

RE_KIT = re.compile(
    r"\[KIT-R f=(\d+)\] SN=(\d+) dK=([\d.]+) R=([\d.]+) stage=(\d+) stuck=(\d+) aged=(\d+) self=\(([\d.-]+),([\d.-]+)\) tgt=\(([\d.-]+),([\d.-]+)\)")
RE_BORN = re.compile(r"产生了新的([\u4e00-\u9fa5A-Za-z.]+)\(编号:(\d+)\)")
RE_MOVE = re.compile(r"HumanMove:([\u4e00-\u9fa5A-Za-z.]+) (\d+) 移动至 \(([\d.]+),([\d.]+)\)")
RE_DEAD = re.compile(r"([\u4e00-\u9fa5A-Za-z.]+)\(编号:?(\d+)\)\s*(?:死亡|阵亡)")

FILES = sorted(glob.glob("gi*.ait"), key=lambda f: int(re.search(r"(\d+)", f).group(1)))

# ---------- 第一遍：SN -> 单位类型（"产生了新的" 行；flag 区分阵营见注释）----------
# ⚠ ait 真实格式 = time | frame | color | flag | message，flag 在 split(' | ',3) 后的 p[3] 头部。
#   感化来的敌方单位在"产生了新的"里 flag=1(敌方)，但被感化后归我方管理 ⇒ 不能按 flag 过滤。
sn_type = {}
for f in FILES:
    for line in open(f, encoding="utf-8", errors="replace"):
        p = line.split(" | ", 3)
        if len(p) < 4:
            continue
        m = RE_BORN.search(p[3])
        if m:
            sn_type[int(m.group(2))] = m.group(1)

print("=" * 78)
print("【0】我方单位类型映射（gi 批 24 局）")
cnt = collections.Counter(sn_type.values())
for t, c in cnt.most_common():
    print("   %-14s %d 个" % (t, c))

# ---------- 第二遍：KIT-R 按 SN 聚合 ----------
kit = collections.defaultdict(list)      # sn -> [(frame,dK,R,stage,stuck,aged,sx,sy,tx,ty)]
moves = collections.defaultdict(list)    # sn -> [(frame,x,y)]
deaths = {}
for f in FILES:
    local_dead = {}
    for line in open(f, encoding="utf-8", errors="replace"):
        p = line.split(" | ", 3)
        if len(p) < 4:
            continue
        try:
            fr = int(p[1])
        except ValueError:
            continue
        body = p[3]
        m = RE_KIT.search(body)
        if m:
            g = m.groups()
            kit[int(g[1])].append((int(g[0]), float(g[2]), float(g[3]), int(g[4]),
                                   int(g[5]), int(g[6]), float(g[7]), float(g[8]),
                                   float(g[9]), float(g[10])))
            continue
        if "KIT-R" in body:          # 正则没匹配上
            print("  [格式未匹配] %s" % body.strip()[:150])
            continue
        m = RE_MOVE.search(body)
        if m:
            moves[int(m.group(2))].append((fr, float(m.group(3)), float(m.group(4))))
            continue
        if "死亡" in body or "阵亡" in body:
            m = re.search(r"\(编号:?(\d+)\)", body)
            if m:
                local_dead[int(m.group(1))] = fr
    for k, v in local_dead.items():
        deaths[k] = v

print()
print("=" * 78)
print("【1】KIT-R 覆盖：有多少远程单位【一生中从未】进入撤退窗口")
ranged_sn = [sn for sn, t in sn_type.items()
             if t in ("复合弓兵", "战车弓兵", "弓兵", "投石兵")]
with_kit = [sn for sn in ranged_sn if sn in kit]
print("   我方远程单位总数        : %d" % len(ranged_sn))
print("   其中出现过 KIT-R 的     : %d (%.1f%%)" % (len(with_kit), 100.0 * len(with_kit) / max(1, len(ranged_sn))))
print("   从未进入撤退窗口的      : %d (%.1f%%)" % (len(ranged_sn) - len(with_kit),
                                                  100.0 * (len(ranged_sn) - len(with_kit)) / max(1, len(ranged_sn))))

# ---------- 核心：窗口内 self 位移 ----------
print()
print("=" * 78)
print("【2】★核心★ 每个撤退窗口内【单位是否真的移动了】(相邻 KIT-R 间隔)")
total_win = 0
idle_win = 0              # self 位移 < 0.5 格
approach_win = 0          # 没动 且 dK 反而减小
stage_cnt = collections.Counter()
stuck_lt = []
per_sn_stat = []

for sn, evs in kit.items():
    evs.sort()
    t = sn_type.get(sn, "?")
    n_idle = n_appr = 0
    for i in range(1, len(evs)):
        f0, dK0, R0, st0, sk0, ag0, sx0, sy0, tx0, ty0 = evs[i - 1]
        f1, dK1, R1, st1, sk1, ag1, sx1, sy1, tx1, ty1 = evs[i]
        dt = f1 - f0
        if dt <= 0 or dt > 90:
            continue
        total_win += 1
        stage_cnt[st0] += 1
        dist = ((sx1 - sx0) ** 2 + (sy1 - sy0) ** 2) ** 0.5
        if dist < 0.5:
            idle_win += 1
            n_idle += 1
            if dK1 < dK0 - 0.2:
                approach_win += 1
                n_appr += 1
    for e in evs:
        stuck_lt.append(e[4])
    if len(evs) >= 5:
        per_sn_stat.append((sn, t, len(evs), n_idle, n_appr, evs[-1][1], deaths.get(sn, -1)))

print("   统计窗口数(相邻 KIT-R 间隔 ≤90 帧): %d" % total_win)
print("   ★ 窗口内单位位移 < 0.5 格(空转)  : %d (%.1f%%)" % (idle_win, 100.0 * idle_win / max(1, total_win)))
print("   ★ 空转 且 dK 反而变小(被逼近)    : %d (%.1f%%)" % (approach_win, 100.0 * approach_win / max(1, total_win)))
print()
print("   窗口 stage 分布: " + "  ".join("%d=%d(%.0f%%)" % (k, v, 100.0 * v / max(1, total_win))
                                       for k, v in sorted(stage_cnt.items())))
print("   stuck 值分布  : " + "  ".join("%d=%d" % (k, v) for k, v in sorted(collections.Counter(stuck_lt).items())[:8]))

# ---------- 逐单位排行 ----------
print()
print("=" * 78)
print("【3】空转最严重的单位（KIT-R 窗口 ≥5 个）")
per_sn_stat.sort(key=lambda x: -x[3])
print("   %-8s %-12s %6s %7s %7s %8s %8s" % ("SN", "类型", "窗口数", "空转", "被逼近", "末次dK", "死亡帧"))
for sn, t, nk, ni, na, lastdk, df in per_sn_stat[:18]:
    print("   %-8d %-12s %6d %7d %7d %8.1f %8s" % (sn, t, nk, ni, na, lastdk, df if df > 0 else "-"))

# ---------- HumanMove 交叉验证 ----------
print()
print("=" * 78)
print("【4】交叉验证：撤退窗口帧是否有 HumanMove 记录")
sample_missing = 0
sample_total = 0
for sn in with_kit[:12]:
    ms = set(f for f, _, _ in moves.get(sn, []))
    hits = sum(1 for e in kit[sn] if e[0] in ms)
    sample_total += len(kit[sn])
    sample_missing += len(kit[sn]) - hits
print("   抽 12 个有撤退窗口的单位: 窗口 %d 个，其中同帧有 HumanMove 的 %d 个 (%.0f%%)"
      % (sample_total, sample_total - sample_missing,
         100.0 * (sample_total - sample_missing) / max(1, sample_total)))
print("   → 同帧有 HumanMove = AI 确实下发了移动令；若这些单位仍然不动，问题在引擎侧（落点被占/攻击中不可移动）")
