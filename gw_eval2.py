#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
方案A 验证：食物:黄金 配比 5:3（A臂 gy+gh，24局） vs 5:4（B臂 gi，24局）

八口径：
  ① 计数正确性  逐帧 派工口径 F+W+G+S  vs  引擎实况 Frm
  ② 经济结构    铜器后稳定期(frame>=21000 且 G>0) 工种人数 / 占比，并分中后期
  ③ 金工达标率  按各臂自身配比算目标（DEN=3 → *3/5；DEN=4 → *4/5）
  ④ 派工令总量  金矿令/树令/食物令（引擎动作日志，不受采样影响）
  ⑤ 健康度      胜负 / 末日帧 / 落成建筑 / 首金时间
  ⑥ goldRich    触发率（连带效应：阈值随 DEN 升高 ⇒ 应更难触发）
  ⑦ 存量风险    Fd/Wd/Gd 均值 + 食物告急率(Fd<100)
  ⑧ 军队规模    唯一军队单位 SN 数（复合弓兵/方阵兵/投石车/阔剑兵）

用法：python gw_eval2.py
"""
import re, glob, os, statistics, collections

ROOT = r"C:\new-aoe3.0.7g"
os.chdir(ROOT)

ECO = re.compile(
    r"ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+)"
    r" \|\| goldRich:(\d+) woodStop:(\d+) stoneStop:(\d+) foodStop:(\d+) woodTarget:(\d+)")
FRM = re.compile(r"\bFrm:(\d+)\s+Idle:(\d+)\(Carry:(\d+)\)\s+Walk:(\d+)\s+Work:(\d+)")
FR = re.compile(r"\|\s*(\d+)\s*\|")

LGOLD = re.compile(r"设置工作目标为 金矿")
LTREE = re.compile(r"设置工作目标为 树 (\d+)")
LFOOD = re.compile(r"设置工作目标为 (浆果|瞪羚|大象|农场)")
ARMY = re.compile(r"HumanAction:(复合弓兵|方阵兵|投石车|阔剑兵) (\d+)")
# [F] PREP | Fd Wd St Gd | Frm Idle(Carry) Walk Work Atk | Mil E
PREP = re.compile(
    r"\[(\d+)\] PREP \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \| Frm:(\d+) Idle:(\d+)\(Carry:(\d+)\)"
    r" Walk:(\d+) Work:(\d+) Atk:(\d+) \| Mil:(\d+) E:(\d+)")

WIN = "VICTORY! Siege Workshop converted"
LOSE = ("DEFEAT: Priest killed", "DEFEAT: Town Center destroyed")
BUILT = "建造完毕"

A_ARM = sorted(glob.glob("gy*.ait")) + sorted(glob.glob("gh*.ait"))   # DEN=3
B_ARM = sorted(glob.glob("gi*.ait"))                                  # DEN=4
ARMS = [("A臂 DEN=3", A_ARM, 3), ("B臂 DEN=4", B_ARM, 4)]


def rows(fs, min_frame=21000, max_frame=None, require_gold=True):
    """稳定期 ECO 采样 -> [(fr, Fd, Wd, St, Gd, F, W, G, S, rich)]"""
    out = []
    for fn in fs:
        for line in open(fn, encoding="utf-8", errors="replace"):
            m = ECO.search(line)
            if not m:
                continue
            g = [int(x) for x in m.groups()]
            f = FR.search(line)
            fr = int(f.group(1)) if f else 0
            if fr < min_frame:
                continue
            if max_frame is not None and fr >= max_frame:
                continue
            if require_gold and g[6] == 0:
                continue
            out.append((fr, g[0], g[1], g[2], g[3], g[4], g[5], g[6], g[7], g[8]))
    return out


def cnt_ref(fs):
    diffs, sums, frms = [], [], []
    for fn in fs:
        lines = open(fn, encoding="utf-8", errors="replace").read().split("\n")
        for i, line in enumerate(lines):
            mf = FRM.search(line)
            if not mf:
                continue
            f = FR.search(line)
            fr = int(f.group(1)) if f else 0
            if fr < 21000:
                continue
            me = ECO.search(line)
            if not me:
                for j in range(i + 1, min(i + 6, len(lines))):
                    if ECO.search(lines[j]):
                        me = ECO.search(lines[j]); break
            if not me:
                continue
            g = [int(x) for x in me.groups()]
            s = g[4] + g[5] + g[6] + g[7]
            frm = int(mf.group(1))
            diffs.append(s - frm); sums.append(s); frms.append(frm)
    if not diffs:
        return None
    ok = sum(1 for d in diffs if abs(d) <= 1) * 100.0 / len(diffs)
    return len(diffs), statistics.mean(diffs), ok, statistics.mean(sums), statistics.mean(frms)


def actions(fs):
    g = t = f = 0
    for fn in fs:
        for line in open(fn, encoding="utf-8", errors="replace"):
            if LGOLD.search(line): g += 1
            elif LTREE.search(line): t += 1
            elif LFOOD.search(line): f += 1
    return g, t, f


def health(fs):
    vic = los = 0
    lasts, builts, firsts = [], [], []
    for fn in fs:
        txt = open(fn, encoding="utf-8", errors="replace").read()
        if WIN in txt: vic += 1
        if any(x in txt for x in LOSE): los += 1
        builts.append(txt.count(BUILT))
        last, first = 0, None
        for line in txt.split("\n"):
            f = FR.search(line)
            if f: last = max(last, int(f.group(1)))
            m = ECO.search(line)
            if m and int(m.group(7)) > 0 and first is None:
                ff = FR.search(line); first = int(ff.group(1)) if ff else 0
        lasts.append(last)
        if first: firsts.append(first)
    return vic, los, len(fs) - vic - los, lasts, builts, firsts


def army_scale(fs):
    sn = set()
    for fn in fs:
        for line in open(fn, encoding="utf-8", errors="replace"):
            m = ARMY.search(line)
            if m: sn.add((m.group(1), m.group(2)))
    return len(sn)


def last_frame(fn):
    last = 0
    for line in open(fn, encoding="utf-8", errors="replace"):
        f = FR.search(line)
        if f:
            last = max(last, int(f.group(1)))
    return last


def full_games(fs, thresh=44000):
    """只保留跑到 total 时限的局，消除早崩局的样本偏差"""
    return [fn for fn in fs if last_frame(fn) >= thresh]


def per_game_mil(fs):
    """返回 [(file, Mil峰值, Mil末值, Atk峰值, E峰值, PREP采样数)]"""
    out = []
    for fn in fs:
        mil, atk, ene = [], [], []
        for line in open(fn, encoding="utf-8", errors="replace"):
            m = PREP.search(line)
            if not m:
                continue
            mil.append(int(m.group(12)))
            atk.append(int(m.group(11)))
            ene.append(int(m.group(13)))
        if mil:
            out.append((fn, max(mil), mil[-1], max(atk), max(ene), len(mil)))
    return out


def fmt_econ(tag, r, den):
    F = statistics.mean([x[5] for x in r]); W = statistics.mean([x[6] for x in r])
    G = statistics.mean([x[7] for x in r]); S = statistics.mean([x[8] for x in r])
    t = F + W + G
    reach = [min(100.0, x[7] * 100.0 / max(1, int(x[5] * den / 5 + 0.999))) for x in r]
    print("  %-8s %-6d F=%5.1f(%4.1f%%) W=%5.1f(%4.1f%%) G=%5.1f(%4.1f%%) S=%4.1f | 达标 %5.1f%%"
          % (tag, len(r), F, F * 100 / t, W, W * 100 / t, G, G * 100 / t, S, statistics.mean(reach)))


def main():
    print("=" * 108)
    print("方案A 验证 | A臂 = gy+gh (%d局, DEN=3)   B臂 = gi (%d局, DEN=4)" % (len(A_ARM), len(B_ARM)))
    print("=" * 108)

    # ①
    print("\n① 计数正确性：派工口径 F+W+G+S vs 引擎 Frm（frame>=21000 逐帧）")
    for lbl, fs, den in ARMS:
        r = cnt_ref(fs)
        if r:
            n, d, ok, s, frm = r
            print("  %-12s 样本 %-5d 差额均值 %+.2f  |差额|<=1 占 %5.1f%%  派工 %.1f  Frm %.1f"
                  % (lbl, n, d, ok, s, frm))
        else:
            print("  %-12s 无 Frm 字段" % lbl)

    # ②
    print("\n② 经济结构（铜器后稳定期 frame>=21000 且 G>0）")
    for lbl, fs, den in ARMS:
        r = rows(fs)
        if r: fmt_econ("全体", r, den)
        r2 = rows(fs, 21000, 33000)          # 反攻前中期
        if r2: fmt_econ("中期", r2, den)
        r3 = rows(fs, 33000, None)           # 反攻后
        if r3: fmt_econ("后期", r3, den)

    # ③④⑤
    print("\n③ 派工令总量")
    for lbl, fs, den in ARMS:
        g, t, f = actions(fs)
        n = max(len(fs), 1)
        print("  %-12s 金矿令 %-6d 树令 %-6d 食物令 %-6d  （24局折算：金 %d / 树 %d / 食 %d）"
              % (lbl, g, t, f, g * 24 // n, t * 24 // n, f * 24 // n))

    print("\n④ 健康度")
    print("  %-12s %-5s %-5s %-7s %-12s %-12s %-10s %s"
          % ("批次", "胜", "负", "无结局", "末日帧中位", "落成建筑中位", "首金中位", "军队规模"))
    for lbl, fs, den in ARMS:
        vic, los, non, lasts, builts, firsts = health(fs)
        print("  %-12s %-5d %-5d %-7d %-12d %-12d %-10s %d"
              % (lbl, vic, los, non, statistics.median(lasts), statistics.median(builts),
                 ("%.1f分" % (statistics.median(firsts) / 1500)) if firsts else "-", army_scale(fs)))

    # ⑥⑦
    print("\n⑤ goldRich 触发率 / 存量风险")
    for lbl, fs, den in ARMS:
        allrows = []
        for fn in fs:
            for line in open(fn, encoding="utf-8", errors="replace"):
                m = ECO.search(line)
                if m: allrows.append([int(x) for x in m.groups()])
        if not allrows:
            continue
        rich = sum(1 for x in allrows if x[8] == 1)
        r = [x for x in allrows if x[6] > 0]     # 只看有金工的样本
        fd = statistics.mean([x[0] for x in r]) if r else 0
        wd = statistics.mean([x[1] for x in r]) if r else 0
        gd = statistics.mean([x[3] for x in r]) if r else 0
        low = sum(1 for x in r if x[0] < 100) * 100.0 / max(len(r), 1)
        print("  %-12s 采样 %-5d goldRich %5.1f%%  | 有金工时 Fd=%6.1f Wd=%6.1f Gd=%6.1f | 食物<100 占 %5.1f%%"
              % (lbl, len(allrows), rich * 100.0 / len(allrows), fd, wd, gd, low))

    # ⑥ 军力（方案A 风险指标）
    print("\n⑥ 军力（PREP 诊断行：Mil=我方军力 / E=敌方军力；受局时长影响，仅作趋势参考）")
    print("  %-12s %-9s %-13s %-13s %-13s %s"
          % ("批次", "有PREP局", "Mil峰值中位", "Mil峰值最大", "Mil末值中位", "E峰值中位"))
    for lbl, fs, den in ARMS:
        pg = per_game_mil(fs)
        if not pg:
            print("  %-12s 无 PREP 行" % lbl)
            continue
        peak = [x[1] for x in pg]
        lastm = [x[2] for x in pg]
        epeak = [x[4] for x in pg]
        print("  %-12s %-9d %-13.0f %-13d %-13.0f %.0f"
              % (lbl, len(pg), statistics.median(peak), max(peak),
                 statistics.median(lastm), statistics.median(epeak)))

    # ⑦ 仅满时长局（消除早崩局样本偏差 —— 铁律：不同时长的局不可混入同一均值）
    print("\n⑦ 仅满时长局（末帧 >= 44000，消除早崩局污染）")
    print("  %-12s %-10s %-34s %-12s %s"
          % ("批次", "满时长局", "铜器后 F/W/G 人数(占比)", "食物存量Fd", "胜/负"))
    for lbl, fs, den in ARMS:
        fg = full_games(fs)
        if not fg:
            print("  %-12s 无满时长局" % lbl)
            continue
        r = rows(fg)
        vic, los, non, lasts, builts, firsts = health(fg)
        allrows = []
        for fn in fg:
            for line in open(fn, encoding="utf-8", errors="replace"):
                m = ECO.search(line)
                if m:
                    allrows.append([int(x) for x in m.groups()])
        rr = [x for x in allrows if x[6] > 0]
        if not r:
            print("  %-12s %-10d 无样本" % (lbl, len(fg)))
            continue
        F = statistics.mean([x[5] for x in r]); W = statistics.mean([x[6] for x in r])
        G = statistics.mean([x[7] for x in r]); S = statistics.mean([x[8] for x in r])
        t = F + W + G
        fd = statistics.mean([x[0] for x in rr]) if rr else 0
        print("  %-12s %-10d F=%5.1f(%4.1f%%) W=%5.1f(%4.1f%%) G=%5.1f(%4.1f%%)  Fd=%7.1f  %d/%d"
              % (lbl, len(fg), F, F * 100 / t, W, W * 100 / t, G, G * 100 / t, fd, vic, los))


if __name__ == "__main__":
    main()
