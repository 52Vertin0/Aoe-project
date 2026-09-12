# -*- coding: utf-8 -*-
"""
验证假设：撤退落点 `距敌 R*1.4` 在 dK≈R 时几乎等于原地 ⇒ 拉扯幅度≈0。
  落点 = kEX + u * R*MULT，self 距敌 dK ⇒ 落点距 self ≈ |R*MULT - dK|
  复合弓兵 R=7、MULT=1.4 ⇒ R*MULT=9.8。进入接敌带时 dK ≤ 9 ⇒ 落点距 self ≤ 0.8~2.8 格。
  分桶看：落点距 self 越近，位移越小 ⇒ 证实"拉扯变形式失效"，而非"引擎不执行"。
"""
import re, glob, collections, statistics

RE_KIT = re.compile(
    r"\[KIT-R f=(\d+)\] SN=(\d+) dK=([\d.]+) R=([\d.]+) stage=(\d+) stuck=(\d+) aged=(\d+) self=\(([\d.-]+),([\d.-]+)\) tgt=\(([\d.-]+),([\d.-]+)\)")

FILES = sorted(glob.glob("gi*.ait"), key=lambda f: int(re.search(r"(\d+)", f).group(1)))
kit = collections.defaultdict(list)
for f in FILES:
    for line in open(f, encoding="utf-8", errors="replace"):
        p = line.split(" | ", 3)
        if len(p) < 4:
            continue
        m = RE_KIT.search(p[3])
        if m:
            g = m.groups()
            kit[int(g[1])].append(dict(fr=int(g[0]), dK=float(g[2]), R=float(g[3]), st=int(g[4]),
                                       stuck=int(g[5]), aged=int(g[6]),
                                       sx=float(g[7]), sy=float(g[8]),
                                       tx=float(g[9]), ty=float(g[10])))

print("=" * 84)
print("【1】撤退落点距【自身】的距离分布（= 这一步「应该走多远」）")
buckets = [(0, 0.5), (0.5, 1), (1, 2), (2, 4), (4, 8), (8, 15), (15, 999)]
step_cnt = collections.Counter()
steps_by_sn_win = []
for sn, evs in kit.items():
    evs.sort(key=lambda e: e["fr"])
    for e in evs:
        d = ((e["tx"] - e["sx"]) ** 2 + (e["ty"] - e["sy"]) ** 2) ** 0.5
        for lo, hi in buckets:
            if lo <= d < hi:
                step_cnt[(lo, hi)] += 1
                break
tot = sum(step_cnt.values())
for lo, hi in buckets:
    n = step_cnt[(lo, hi)]
    print("   落点距自身 %5.1f~%-5.1f 格 : %5d (%.1f%%)" % (lo, min(hi, 99), n, 100.0 * n / tot))

print()
print("=" * 84)
print("【2】★核心★ 按「应该走的距离」分桶，看「实际走了多少」")
print("   判据：相邻窗口(间隔≤90帧) 的 self 位移 vs 上一窗口落点距 self 的距离")
stat = collections.defaultdict(lambda: [0, 0, 0.0])   # bucket -> [窗口数, 空转数, 位移和]
for sn, evs in kit.items():
    evs.sort(key=lambda e: e["fr"])
    for i in range(1, len(evs)):
        a, b = evs[i - 1], evs[i]
        if not (0 < b["fr"] - a["fr"] <= 90):
            continue
        need = ((a["tx"] - a["sx"]) ** 2 + (a["ty"] - a["sy"]) ** 2) ** 0.5
        got = ((b["sx"] - a["sx"]) ** 2 + (b["sy"] - a["sy"]) ** 2) ** 0.5
        for lo, hi in buckets:
            if lo <= need < hi:
                s = stat[(lo, hi)]
                s[0] += 1
                if got < 0.5:
                    s[1] += 1
                s[2] += got
                break
print("   %-18s %7s %9s %9s %12s" % ("应走距离(格)", "窗口数", "空转数", "空转率", "实走/应走"))
for lo, hi in buckets:
    s = stat[(lo, hi)]
    if s[0] == 0:
        continue
    print("   %5.1f~%-5.1f      %7d %9d %8.1f%% %11.0f%%"
          % (lo, min(hi, 99), s[0], s[1], 100.0 * s[1] / s[0],
             100.0 * (s[2] / s[0]) / max(0.01, (lo + min(hi, 99)) / 2)))

print()
print("=" * 84)
print("【3】拉扯「视觉幅度」：每 10 秒(250帧)内，单位与最近敌的距离变化")
# 取窗口密集的 SN，看 dK 轨迹：若拉扯有效，dK 应呈锯齿(升→降→升)；若无效，dK 单调下降
samples = []
for sn, evs in kit.items():
    if len(evs) < 40:
        continue
    evs.sort(key=lambda e: e["fr"])
    first, last = evs[0], evs[-1]
    span = last["fr"] - first["fr"]
    if span < 2000:
        continue
    # 统计 dK 的锯齿：数值上升的窗口占比
    up = sum(1 for i in range(1, len(evs)) if evs[i]["dK"] > evs[i - 1]["dK"] + 0.2)
    down = sum(1 for i in range(1, len(evs)) if evs[i]["dK"] < evs[i - 1]["dK"] - 0.2)
    samples.append((sn, len(evs), span / 25.0, first["dK"], last["dK"], up, down))
samples.sort(key=lambda x: -x[1])
print("   %-8s %6s %8s %8s %8s %7s %7s" % ("SN", "窗口", "时长(秒)", "首dK", "末dK", "dK升", "dK降"))
for sn, n, sec, d0, d1, up, dn in samples[:16]:
    print("   %-8d %6d %8.1f %8.1f %8.1f %7d %7d" % (sn, n, sec, d0, d1, up, dn))
print()
print("   注：升=dK变大(拉开距离,撤退生效) 降=dK变小(被逼近)"
      "\n       若某单位 升≈0 而 降 很大 ⇒ 该单位全程只被逼近，拉扯从未生效")
