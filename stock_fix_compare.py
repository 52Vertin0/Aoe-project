# -*- coding: utf-8 -*-
"""stock_fix_compare.py —— 2026-09-20「同群重复建仓库」修复的三臂对照

臂定义（全部同源：改前 = 3bd4d179，改后 = 559b50af）
  A1 = sr_1..8    改前二进制（代码精简验收的 B 臂）
  A2 = srC_1..8   改前二进制【重跑】 ⇒ A/A2 之差 = 批间噪声标尺（铁律 81）
  B  = fu_1..16   改后二进制（本次修复）
主判据：同群重复（任一两条仓库令的块距 <= 9 的局数）。改前全库 69 个 8 局批的噪声带 = 40.4% ± 16.4pp。
"""
import io, re, os, math, statistics as st
from collections import Counter

RE_ISSUE = re.compile(r"\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) .*?at=\((\d+),(\d+)\)")
RE_GATE = re.compile(r"\[GATE f=(\d+)\].*? stock=(\d+)(?:.*?距上次仓库令=(-?\d+)帧)?")

HERE = os.path.dirname(os.path.abspath(__file__))


def load(nm):
    p = os.path.join(HERE, nm + ".ait")
    if not os.path.exists(p):
        return None
    with io.open(p, encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    d = {"issues": [], "gate": [], "last": 0, "gz": 0, "hard": 0, "orphan": 0,
         "waves": None, "win": None, "settle_obs": 0}
    for raw in lines:
        q = raw.split(" | ")
        if len(q) >= 2:
            try:
                d["last"] = max(d["last"], int(q[1]))
            except ValueError:
                pass
        if "[BUILD-ISSUE" in raw and "type=3 " in raw:
            m = RE_ISSUE.search(raw)
            if m:
                d["issues"].append((int(m.group(1)), int(m.group(4)), int(m.group(5))))
        elif "[GATE f=" in raw:
            m = RE_GATE.search(raw)
            if m:
                d["gate"].append((int(m.group(1)), int(m.group(2)),
                                  int(m.group(3)) if m.group(3) is not None else None))
                if m.group(3) is not None and 0 <= int(m.group(3)) <= 600:
                    d["settle_obs"] += 1
        elif "[GAZELLE-STOCK" in raw:
            d["gz"] += 1
        elif "BUILDER-HARD" in raw:
            d["hard"] += 1
        elif "[ORPHAN" in raw:
            d["orphan"] += 1
        elif "ALL WAVES DEFEATED" in raw and d["waves"] is None:
            try:
                d["waves"] = int(q[1])
            except (ValueError, IndexError):
                pass
        elif "VICTORY" in raw and d["win"] is None:
            d["win"] = "胜"
        elif "DEFEAT" in raw and d["win"] is None:
            d["win"] = "负"
    return d


def dup_pairs(st, thr):
    n = 0
    for i in range(len(st)):
        for j in range(i + 1, len(st)):
            if math.hypot(st[i][1] - st[j][1], st[i][2] - st[j][2]) <= thr:
                n += 1
    return n


def burst5(st):
    """相邻两条仓库令间隔 == 5 帧（= buildCooldown）的次数，并按块距 <=9 细分"""
    all5 = same5 = 0
    for i in range(len(st) - 1):
        if st[i + 1][0] - st[i][0] == 5:
            all5 += 1
            if math.hypot(st[i + 1][1] - st[i][1], st[i + 1][2] - st[i][2]) <= 9:
                same5 += 1
    return all5, same5


def arm(names):
    rows = []
    for nm in names:
        d = load(nm)
        if d is not None:
            rows.append((nm, d))
    n = len(rows)
    dup9 = sum(1 for _, d in rows if dup_pairs(d["issues"], 9) > 0)
    dup20 = sum(1 for _, d in rows if dup_pairs(d["issues"], 20) > 0)
    b5 = sum(burst5(d["issues"])[0] for _, d in rows)
    b5same = sum(burst5(d["issues"])[1] for _, d in rows)
    cnt = Counter(len(d["issues"]) for _, d in rows)
    endstock = [d["gate"][-1][1] for _, d in rows if d["gate"]]
    lasts = [d["last"] for _, d in rows]
    waves = [d["waves"] for _, d in rows if d["waves"]]
    gz = sum(d["gz"] for _, d in rows)
    hard = sum(d["hard"] for _, d in rows)
    orphan = sum(d["orphan"] for _, d in rows)
    settle = sum(d["settle_obs"] for _, d in rows)
    res = {
        "n": n, "dup9": dup9, "dup20": dup20, "b5": b5, "b5same": b5same,
        "cnt": cnt, "endstock": endstock, "last_med": st.median(lasts) if lasts else 0,
        "waves_med": st.median(waves) if waves else None,
        "gz": gz, "hard": hard, "orphan": orphan, "settle": settle,
        "win": sum(1 for _, d in rows if d["win"] == "胜"),
        "lose": sum(1 for _, d in rows if d["win"] == "负"),
        "avg_issues": sum(len(d["issues"]) for _, d in rows) / max(1, n),
    }
    return res, rows


def show(tag, r, r2=None):
    print(f"  {tag:<22}{r['n']:>4}局 {r['dup9']:>3}局({r['dup9']/max(1,r['n'])*100:5.1f}%) "
          f"{r['dup20']:>3}局({r['dup20']/max(1,r['n'])*100:5.1f}%) {r['b5']:>4} {r['b5same']:>4} "
          f"{r['avg_issues']:>6.2f} {r['gz']:>4} {r['hard']:>4} {r['orphan']:>4} "
          f"{str(r['waves_med']):>8} {r['win']:>2}/{r['lose']:<2}")


def main():
    arms = {
        "A1 pre(sr)": ["sr_%d" % i for i in range(1, 9)],
        "A2 pre(srC 重跑)": ["srC_%d" % i for i in range(1, 9)],
        "B  post(fu)": ["fu%d" % i for i in range(1, 17)],
    }
    R = {}
    for k, v in arms.items():
        R[k] = arm(v)[0]
    print("=" * 118)
    print("【主表】 臂                      局数  同群≤9重复      同群≤20重复     5帧连发(其中同群) 令/局 "
          "GS  HARD ORPHAN 反攻帧中位 胜/负")
    for k in ["A1 pre(sr)", "A2 pre(srC 重跑)", "B  post(fu)"]:
        show(k, R[k])
    print()
    A_all = {kk: R["A1 pre(sr)"][kk] + R["A2 pre(srC 重跑)"][kk]
             for kk in ["n", "dup9", "dup20", "b5", "b5same", "gz", "hard", "orphan", "settle"]}
    A_all["avg_issues"] = (R["A1 pre(sr)"]["avg_issues"] + R["A2 pre(srC 重跑)"]["avg_issues"]) / 2
    A_all["waves_med"] = R["A1 pre(sr)"]["waves_med"]
    A_all["win"] = R["A1 pre(sr)"]["win"] + R["A2 pre(srC 重跑)"]["win"]
    A_all["lose"] = R["A1 pre(sr)"]["lose"] + R["A2 pre(srC 重跑)"]["lose"]
    show("A 合并(改前 16 局)", A_all)
    print()
    print("【仓库令条数分布】")
    keys = sorted(set(list(R["B  post(fu)"]["cnt"]) + [0, 1, 2, 3, 4]))
    for k in ["A1 pre(sr)", "A2 pre(srC 重跑)", "B  post(fu)"]:
        c = R[k]["cnt"]
        print(f"  {k:<22}" + "  ".join(f"{kk}座:{c.get(kk,0)}" for kk in keys))
    print()
    print("【末条 GATE 的 stock= 终值】")
    for k in ["A1 pre(sr)", "A2 pre(srC 重跑)", "B  post(fu)"]:
        v = R[k]["endstock"]
        print(f"  {k:<22} n={len(v)} 中位={st.median(v) if v else '-'} 分布={dict(Counter(v))}")
    print()
    print("【B 臂 settle 闸可观测】B 臂 GATE 采样中『距上次仓库令<=600 帧』(即 settle 闸生效) 的条数 = %d"
          % R["B  post(fu)"]["settle"])
    print("   对照：A1=%d  A2=%d（改前无此闸，该值仅作口径对照，不代表闸生效）"
          % (R["A1 pre(sr)"]["settle"], R["A2 pre(srC 重跑)"]["settle"]))


if __name__ == "__main__":
    main()
