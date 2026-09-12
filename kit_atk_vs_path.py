# -*- coding: utf-8 -*-
"""
决定性一问：撤退令之后单位不动，是因为【下一帧被攻击令覆盖】还是【路径被堵】？

口径：同一 SN 的相邻 KIT-R 两窗口（gap 25~45 帧）之间的【自身位移】，
      按"该区间内有没有出现攻击令"分桶。若"无攻击令"桶位移显著更大 ⇒ 攻击令是压制源；
      若两桶都≈0 ⇒ 是路径/落点问题（与攻击令无关）。
"""
import re, glob, collections, statistics

RE_KIT = re.compile(
    r"\[KIT-R f=(\d+)\] SN=(\d+) dK=([\d.]+) R=([\d.]+) stage=(\d+) stuck=(\d+) aged=(\d+) self=\(([\d.-]+),([\d.-]+)\) tgt=\(([\d.-]+),([\d.-]+)\)")
RE_AT = re.compile(r"HumanAction:[\u4e00-\u9fa5A-Za-z.]+ (\d+) 设置攻击目标为 ")
RE_MV = re.compile(r"HumanMove:[\u4e00-\u9fa5A-Za-z.]+ (\d+) 移动至 \(([\d.]+),([\d.]+)\)")


def load(prefix):
    return sorted(glob.glob(prefix + "*.ait"),
                  key=lambda f: int(re.search(r"(\d+)", f).group(1)))


def run(prefix, label):
    per = collections.defaultdict(list)
    buck = collections.defaultdict(list)      # ('atk'|'noatk', stage) -> [step]
    dkchg = collections.defaultdict(list)
    for f in load(prefix):
        ev = collections.defaultdict(list)
        atk = collections.defaultdict(list)
        for line in open(f, encoding="utf-8", errors="replace"):
            p = line.split(" | ", 3)
            if len(p) < 4:
                continue
            try:
                fr = int(p[1])
            except ValueError:
                continue
            b = p[3]
            m = RE_KIT.search(b)
            if m:
                g = m.groups()
                ev[int(g[1])].append((int(g[0]), float(g[2]), int(g[4]),
                                      float(g[7]), float(g[8])))
                continue
            m = RE_AT.search(b)
            if m:
                atk[int(m.group(1))].append(fr)
        for sn, seq in ev.items():
            seq.sort()
            a = atk.get(sn, [])
            for i in range(1, len(seq)):
                f0, d0, s0, x0, y0 = seq[i - 1]
                f1, d1, s1, x1, y1 = seq[i]
                if not (25 <= f1 - f0 <= 45):
                    continue
                step = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
                has_atk = any(f0 < t <= f1 for t in a)
                buck[("atk" if has_atk else "noatk", s0)].append(step)
                dkchg[("atk" if has_atk else "noatk", s0)].append(d1 - d0)

    print("=" * 88)
    print("【%s】" % label)
    print("  %-18s %6s %10s %10s %10s" % ("区间内攻击令", "样本", "位移中位", "位移>1格%", "dK变化中位"))
    for k in ("noatk", "atk"):
        for s in (1, 2):
            v = buck.get((k, s))
            if not v or len(v) < 20:
                continue
            dv = dkchg[(k, s)]
            print("  %-18s %6d %10.2f %9.1f%% %+10.2f" %
                  ("无" if k == "noatk" else "有", len(v), statistics.median(v),
                   100.0 * sum(1 for x in v if x > 1.0) / len(v), statistics.median(dv)))
    # 汇总（不分 stage）
    for k in ("noatk", "atk"):
        v = buck.get((k, 1), []) + buck.get((k, 2), [])
        if v:
            print("  —— %s攻击令 : 全体位移中位 %.2f 格 ｜ 位移>1格 %.1f%% ｜ 位移<0.2格 %.1f%%" %
                  ("无" if k == "noatk" else "有", statistics.median(v),
                   100.0 * sum(1 for x in v if x > 1.0) / len(v),
                   100.0 * sum(1 for x in v if x < 0.2) / len(v)))


if __name__ == "__main__":
    run("gi", "基线 gi")
    run("kb", "kb（M1~M3）")
    run("kc", "kc（M1~M4）")
    run("kd", "kd（M1~M4 + M5 拉扯撤退锁）")
