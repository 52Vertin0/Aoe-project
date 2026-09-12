# -*- coding: utf-8 -*-
"""
决定性一问：撤退令到底走的哪一档？(stage 1=远离敌 / 2=朝TC / 3=朝祭司)
再由 stage 分布 + aged 分布 判断"退不出去"的真实机制。
"""
import re, glob, collections, statistics

RE_KIT = re.compile(
    r"\[KIT-R f=(\d+)\] SN=(\d+) dK=([\d.]+) R=([\d.]+) stage=(\d+) stuck=(\d+) aged=(\d+) self=\(([\d.-]+),([\d.-]+)\) tgt=\(([\d.-]+),([\d.-]+)\)")
BL = 35.777


def run(prefix, label):
    files = sorted(glob.glob(prefix + "*.ait"),
                   key=lambda f: int(re.search(r"(\d+)", f).group(1)))
    stg = collections.Counter()
    aged = collections.Counter()
    stuckc = collections.Counter()
    dk_by_stage = collections.defaultdict(list)
    dk_all = []
    # 同 SN 相邻窗口 dK 走向，按 stage 分开
    seq = collections.defaultdict(list)
    for f in files:
        for line in open(f, encoding="utf-8", errors="replace"):
            m = RE_KIT.search(line)
            if not m:
                continue
            g = m.groups()
            fr, sn, dK, R, s, sk, ag = int(g[0]), int(g[1]), float(g[2]), float(g[3]), int(g[4]), int(g[5]), int(g[6])
            stg[s] += 1
            dk_by_stage[s].append(dK)
            dk_all.append(dK)
            aged[min(ag // 15 * 15, 90)] += 1
            stuckc[min(sk, 8)] += 1
            seq[sn].append((fr, dK, s))

    tot = sum(stg.values())
    print("=" * 88)
    print("【%s】撤退窗口 %d 个" % (label, tot))
    for s in (1, 2, 3, 0):
        if stg[s]:
            d = dk_by_stage[s]
            print("  stage=%d (%-6s) : %5d (%5.1f%%)  dK 中位 %5.1f 格" %
                  (s, {1: "远离敌", 2: "朝TC", 3: "朝祭司", 0: "失败"}[s],
                   stg[s], 100.0 * stg[s] / tot, statistics.median(d)))
    print("  dK 全体: 中位 %.1f ｜ <8.5 格占 %.0f%% ｜ 8.5~11 占 %.0f%% ｜ >=11 占 %.0f%%" %
          (statistics.median(dk_all),
           100.0 * sum(1 for x in dk_all if x < 8.5) / len(dk_all),
           100.0 * sum(1 for x in dk_all if 8.5 <= x < 11) / len(dk_all),
           100.0 * sum(1 for x in dk_all if x >= 11) / len(dk_all)))
    print("  phaseAged 分布(15帧桶): " + " ".join("%d:%d" % (k, v) for k, v in sorted(aged.items())))
    print("  stuck 计数分布          : " + " ".join("%d:%d" % (k, v) for k, v in sorted(stuckc.items())))
    print()
    print("  —— 按 stage 分：相邻窗口(>=25帧)的 dK 走向 ——")
    for s in (1, 2, 3):
        up = dn = 0
        for sn, ev in seq.items():
            ev.sort()
            for i in range(1, len(ev)):
                if ev[i][2] != s or ev[i][0] - ev[i - 1][0] < 25:
                    continue
                if ev[i][1] > ev[i - 1][1] + 0.3:
                    up += 1
                elif ev[i][1] < ev[i - 1][1] - 0.3:
                    dn += 1
        t = up + dn
        print("    stage=%d: 拉大 %4d ｜ 缩小 %4d ｜ 拉开比 %s" %
              (s, up, dn, ("%.0f%%" % (100.0 * up / t)) if t else "n/a"))


if __name__ == "__main__":
    run("gi", "基线 gi（BREATH=1.5 阈值 8.5）")
    run("kb", "修正 kb（M1+M2+M3，BREATH=4.0 阈值 11）")
    run("kc", "修正 kc（M1+M2+M3+M4 窗口首帧清 prevDK）")
    run("kd", "修正 kd（M1~M5 拉扯撤退锁）")
