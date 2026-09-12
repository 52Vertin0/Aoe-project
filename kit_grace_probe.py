# -*- coding: utf-8 -*-
"""
决定性一问：下了 stage=1「远离敌」这条令之后，给足时间 dK 到底拉不拉得开？

若「30/60 帧后 dK 明显上升」 ⇒ 单位有能力撤，问题纯粹是"第 2 帧就判 stuck 改走 stage=2"
                              ⇒ 修法 = 给一段宽限期（M5），不要在 1 帧内审判结果。
若「给足时间也不上升」       ⇒ 落点/通行性有问题，宽限期无用，得去动 tryRetreatLanding。

口径：同一 SN 的相邻 KIT-R 事件，gap 落在窗口内(25~45 帧 = canReissue 30 帧节流)，
      按【前一条】的 stage 分组，统计 dK 变化量（后 − 前）。
"""
import re, glob, collections, statistics

RE_KIT = re.compile(
    r"\[KIT-R f=(\d+)\] SN=(\d+) dK=([\d.]+) R=([\d.]+) stage=(\d+) stuck=(\d+) aged=(\d+) self=\(([\d.-]+),([\d.-]+)\) tgt=\(([\d.-]+),([\d.-]+)\)")
BL = 35.777


def load(prefix):
    return sorted(glob.glob(prefix + "*.ait"),
                  key=lambda f: int(re.search(r"(\d+)", f).group(1)))


def window_sizes(prefix):
    """窗口长度分布：同 SN 连续 KIT-R 的 gap<45帧 视为同一窗口内的反复重发。"""
    hist = collections.Counter()
    for f in load(prefix):
        per = collections.defaultdict(list)
        for line in open(f, encoding="utf-8", errors="replace"):
            m = RE_KIT.search(line)
            if not m:
                continue
            per[int(m.group(2))].append((int(m.group(1)), int(m.group(5))))
        for sn, ev in per.items():
            ev.sort()
            n = 1
            for i in range(1, len(ev)):
                if ev[i][0] - ev[i - 1][0] < 45:
                    n += 1
                else:
                    hist[min(n, 8)] += 1
                    n = 1
            hist[min(n, 8)] += 1
    return hist


def run(prefix, label):
    delta = collections.defaultdict(list)     # 前一事件 stage -> [dK 变化(格)]
    moved = collections.defaultdict(lambda: [0, 0])   # 前一 stage -> [位移>1格, 总数]
    for f in load(prefix):
        per = collections.defaultdict(list)
        for line in open(f, encoding="utf-8", errors="replace"):
            m = RE_KIT.search(line)
            if not m:
                continue
            g = m.groups()
            per[int(g[1])].append((int(g[0]), float(g[2]), int(g[4]),
                                   float(g[7]), float(g[8])))
        for sn, ev in per.items():
            ev.sort()
            for i in range(1, len(ev)):
                f0, d0, s0, x0, y0 = ev[i - 1]
                f1, d1, s1, x1, y1 = ev[i]
                gap = f1 - f0
                if not (25 <= gap <= 45):
                    continue
                delta[s0].append(d1 - d0)
                step = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
                moved[s0][1] += 1
                if step > 1.0:
                    moved[s0][0] += 1

    tot = sum(len(v) for v in delta.values())
    print("=" * 88)
    print("【%s】相邻窗口事件对（gap 25~45 帧）共 %d 对" % (label, tot))
    for s in (1, 2, 3):
        v = delta.get(s)
        if not v or len(v) < 20:
            continue
        up = sum(1 for x in v if x > 0.3)
        dn = sum(1 for x in v if x < -0.3)
        flat = len(v) - up - dn
        print("  前一条 stage=%d : n=%5d ｜ 中位变化 %+5.1f 格 ｜ 均值 %+5.1f 格" %
              (s, len(v), statistics.median(v), statistics.mean(v)))
        print("        拉开(>+0.3) %5.1f%% ｜ 持平 %5.1f%% ｜ 缩小(<-0.3) %5.1f%%" %
              (100.0 * up / len(v), 100.0 * flat / len(v), 100.0 * dn / len(v)))
        mv = moved[s]
        print("        30 帧内自身位移 >1 格 : %5.1f%%  (%d/%d)" %
              (100.0 * mv[0] / mv[1] if mv[1] else 0, mv[0], mv[1]))
    print()
    print("  —— 撤退窗口长度分布（同一窗口内连续重发次数）——")
    h = window_sizes(prefix)
    t = sum(h.values())
    for k in sorted(h):
        print("    %d 次%s : %5d (%5.1f%%)" % (k, "≥8" if k == 8 else "  ",
                                               h[k], 100.0 * h[k] / t))


if __name__ == "__main__":
    run("gi", "基线 gi")
    run("kb", "kb（M1+M2+M3）")
    run("kc", "kc（+M4 窗口首帧清 prevDK）")
    run("kd", "kd（+M5 拉扯撤退锁）")
