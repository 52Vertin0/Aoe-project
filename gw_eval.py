#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
采金修复最终评估：基线 th（旧计数） vs 最终版 gy+gh（新计数）
四个口径：
  ① 计数正确性：派工口径 F+W+G+S  vs  引擎实况 Frm      —— 判断"尺子"是否可信
  ② 经济结构：铜器后稳定期(frame>=21000 且 G>0) 各工种人数与占比
  ③ 达成率：min(100%, goldWorkers / goldTarget)
  ④ 健康度：胜负 / 末日帧 / 落成建筑 / 首金时间 / 动作日志总量
用法：python gw_eval.py
"""
import re, glob, os, statistics, collections

ROOT = r"C:\new-aoe3.0.7g"
os.chdir(ROOT)

# ECO 采样行（含我方统计 workers ... 与停采闸）
ECO = re.compile(
    r"ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+)"
    r" \|\| goldRich:(\d+) woodStop:(\d+) stoneStop:(\d+) foodStop:(\d+) woodTarget:(\d+)")
# 全量行（引擎实况）—— 只在部分版本存在，可能缺失
FRM = re.compile(r"\bFrm:(\d+)\s+Idle:(\d+)\(Carry:(\d+)\)\s+Walk:(\d+)\s+Work:(\d+)")
FR = re.compile(r"\|\s*(\d+)\s*\|")

LGOLD = re.compile(r"设置工作目标为 金矿")
LTREE = re.compile(r"设置工作目标为 树 (\d+)")
LFOOD = re.compile(r"设置工作目标为 (浆果|瞪羚|大象|农场)")

WIN = "VICTORY! Siege Workshop converted"
LOSE = ("DEFEAT: Priest killed", "DEFEAT: Town Center destroyed")
BUILT = "建造完毕"


def games(pat):
    return sorted(glob.glob(pat))


def econ_rows(files, min_frame=0, require_gold=False):
    """返回铜器后采样 [(fr, F, W, G, S)]"""
    out = []
    for fn in files:
        for line in open(fn, encoding="utf-8", errors="replace"):
            m = ECO.search(line)
            if not m:
                continue
            g = [int(x) for x in m.groups()]
            f = FR.search(line)
            fr = int(f.group(1)) if f else 0
            if fr < min_frame:
                continue
            if require_gold and g[6] == 0:
                continue
            out.append((fr, g[4], g[5], g[6], g[7]))
    return out


def count_reference(files):
    """逐帧比对 派工口径 F+W+G+S 与 引擎 Frm，返回 (样本数, 差额均值, |差额|<=1 的占比, 派工均值, Frm均值)"""
    diffs, sums, frms = [], [], []
    for fn in files:
        lines = open(fn, encoding="utf-8", errors="replace").read().split("\n")
        for i, line in enumerate(lines):
            mf = FRM.search(line)
            if not mf:
                continue
            f = FR.search(line)
            fr = int(f.group(1)) if f else 0
            if fr < 21000:            # 只看稳定期，避开早期人少抖动
                continue
            # 找同一行或随后最近的 ECO 行
            me = ECO.search(line)
            if not me:
                for j in range(i + 1, min(i + 6, len(lines))):
                    if ECO.search(lines[j]):
                        me = ECO.search(lines[j])
                        break
            if not me:
                continue
            g = [int(x) for x in me.groups()]
            s = g[4] + g[5] + g[6] + g[7]
            frm = int(mf.group(1))
            diffs.append(s - frm)
            sums.append(s)
            frms.append(frm)
    if not diffs:
        return None
    ok = sum(1 for d in diffs if abs(d) <= 1) * 100.0 / len(diffs)
    return len(diffs), statistics.mean(diffs), ok, statistics.mean(sums), statistics.mean(frms)


def action_counts(files):
    g = t = f = 0
    for fn in files:
        for line in open(fn, encoding="utf-8", errors="replace"):
            if LGOLD.search(line):
                g += 1
            elif LTREE.search(line):
                t += 1
            elif LFOOD.search(line):
                f += 1
    return g, t, f


def health(files):
    vic = los = 0
    lasts, builts, firsts = [], [], []
    for fn in files:
        txt = open(fn, encoding="utf-8", errors="replace").read()
        if WIN in txt:
            vic += 1
        if any(x in txt for x in LOSE):
            los += 1
        builts.append(txt.count(BUILT))
        last, first = 0, None
        for line in txt.split("\n"):
            f = FR.search(line)
            if f:
                last = max(last, int(f.group(1)))
            m = ECO.search(line)
            if m and int(m.group(7)) > 0 and first is None:
                ff = FR.search(line)
                first = int(ff.group(1)) if ff else 0
        lasts.append(last)
        if first:
            firsts.append(first)
    return vic, los, len(files) - vic - los, lasts, builts, firsts


def reach_rate(files):
    """铜器后稳定期金工/目标 的达成率"""
    vals = []
    for fn in files:
        for line in open(fn, encoding="utf-8", errors="replace"):
            m = ECO.search(line)
            if not m:
                continue
            g = [int(x) for x in m.groups()]
            f = FR.search(line)
            fr = int(f.group(1)) if f else 0
            if fr < 21000 or g[6] == 0:
                continue
            tgt = max(1, int(g[4] * 3 / 5 + 0.999))
            vals.append(min(100.0, g[6] * 100.0 / tgt))
    return vals


def line(tag):
    print(tag)


def main():
    A = games("th*.ait")
    B = games("gy*.ait") + games("gh*.ait")
    print("=" * 96)
    print("基线 th = %d 局（旧计数） | 最终版 gy+gh = %d 局（新计数）" % (len(A), len(B)))
    print("=" * 96)

    # ① 计数正确性
    print("\n① 计数正确性：派工口径 F+W+G+S  vs  引擎实况 Frm（稳定期 frame>=21000 逐帧比对）")
    for lbl, fs in (("th 基线", A), ("gy+gh 最终版", B)):
        r = count_reference(fs)
        if r:
            n, d, ok, s, frm = r
            print("  %-12s 样本 %-5d  差额均值 %+.2f  |差额|<=1 占 %.1f%%  派工均值 %.1f  Frm均值 %.1f"
                  % (lbl, n, d, ok, s, frm))
        else:
            print("  %-12s 无 Frm 字段（旧日志格式）" % lbl)

    # ② 经济结构
    print("\n② 经济结构（铜器后稳定期 frame>=21000 且 G>0）")
    print("  %-12s %-6s %-16s %-16s %-16s %s"
          % ("批次", "样本", "食物工 F", "伐木工 W", "金工 G", "金工占比"))
    for lbl, fs in (("th 基线", A), ("gy+gh 最终版", B)):
        rows = econ_rows(fs, 21000, True)
        if not rows:
            print("  %-12s 无样本" % lbl)
            continue
        F = statistics.mean([r[1] for r in rows])
        W = statistics.mean([r[2] for r in rows])
        G = statistics.mean([r[3] for r in rows])
        t = F + W + G
        print("  %-12s %-6d %-16s %-16s %-16s %.1f%%"
              % (lbl, len(rows), "%.1f" % F, "%.1f" % W, "%.1f" % G, G * 100 / t))

    # ③ 达成率
    print("\n③ 金工达标率（金工 / goldTarget，上限 100%）")
    for lbl, fs in (("th 基线", A), ("gy+gh 最终版", B)):
        v = reach_rate(fs)
        if v:
            print("  %-12s 样本 %-5d 均值 %.1f%%  中位 %.1f%%  >=90%% 占 %.1f%%"
                  % (lbl, len(v), statistics.mean(v), statistics.median(v),
                     sum(1 for x in v if x >= 90) * 100.0 / len(v)))

    # ④ 动作日志
    print("\n④ 派工令总量（引擎动作日志，不受采样影响）")
    print("  %-12s %-10s %-10s %s" % ("批次", "金矿令", "树令", "食物令"))
    for lbl, fs in (("th 基线", A), ("gy+gh 最终版", B)):
        g, t, f = action_counts(fs)
        print("  %-12s %-10d %-10d %d   （%d 局折算 12 局：金 %d / 树 %d / 食 %d）"
              % (lbl, g, t, f, len(fs), g * 12 // len(fs), t * 12 // len(fs), f * 12 // len(fs)))

    # ⑤ 健康度
    print("\n⑤ 健康度")
    print("  %-12s %-5s %-5s %-7s %-12s %-12s %s"
          % ("批次", "胜", "负", "无结局", "末日帧中位", "落成建筑中位", "首金中位"))
    for lbl, fs in (("th 基线", A), ("gy+gh 最终版", B)):
        vic, los, non, lasts, builts, firsts = health(fs)
        print("  %-12s %-5d %-5d %-7d %-12d %-12d %s"
              % (lbl, vic, los, non, statistics.median(lasts), statistics.median(builts),
                 ("%.1f 分" % (statistics.median(firsts) / 1500)) if firsts else "-"))

    # ⑥ 分组明细（最终版两批分开看，检验批次方差）
    print("\n⑥ 最终版两批分组（校验批间方差，铁律 25）")
    for lbl, fs in (("gy1-12", games("gy*.ait")), ("gh1-12", games("gh*.ait"))):
        if not fs:
            continue
        rows = econ_rows(fs, 21000, True)
        v = reach_rate(fs)
        vic, los, non, lasts, builts, firsts = health(fs)
        F = statistics.mean([r[1] for r in rows]) if rows else 0
        W = statistics.mean([r[2] for r in rows]) if rows else 0
        G = statistics.mean([r[3] for r in rows]) if rows else 0
        print("  %-8s F=%.1f W=%.1f G=%.1f (金占比 %.1f%%) | 达标 %.1f%% | 胜%d/负%d/无%d | 末日帧中位 %d | 建筑中位 %d"
              % (lbl, F, W, G, G * 100 / max(F + W + G, 1),
                 statistics.mean(v) if v else 0, vic, los, non,
                 statistics.median(lasts), statistics.median(builts)))


if __name__ == "__main__":
    main()
