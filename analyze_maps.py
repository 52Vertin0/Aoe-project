#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨地图胜率统计（z 批次：z0=map.njust / z1=map1 / z2=map2 / z3=map3）
判据：
  胜 = jsonl 任一行 "win":true   （必须扫全文件；胜帧后引擎还会再写 win:false）
  负 = ait 含 "DEFEAT: Priest killed"
       （"ALL WAVES DEFEATED!" 是反攻启动事件，非胜负）
  其余 = 未决
附带：祭司死亡帧 / 早死(<23253) / 是否进入反攻 / ADV_SIEGE / 首次感化帧
"""
import glob, json, os, re, sys, math
from collections import defaultdict

MAPS = [("z0", "map.njust (map0)"), ("z1", "map1.njust"), ("z2", "map2.njust"), ("z3", "map3.njust")]
EARLY = 23253          # 复合弓首产中位帧（早死判据）
FINAL = 45000          # 打满帧上限


def analyze(base):
    """返回一局的字典；base 为不含扩展名的路径"""
    ait, js = base + ".ait", base + ".jsonl"
    if not os.path.exists(ait):
        return None
    win = False
    if os.path.exists(js):
        with open(js, errors="replace") as f:
            for line in f:
                if '"win":true' in line:
                    win = True
                    break
    death = None
    counter = None
    adv = conv = 0
    first_conv = None
    last_frame = 0
    with open(ait, errors="replace") as f:
        for line in f:
            m = re.match(r"[^|]*\|\s*(\d+)\s*\|", line)
            if m:
                fr = int(m.group(1))
                if fr > last_frame:
                    last_frame = fr
            else:
                fr = None
            if "DEFEAT: Priest killed" in line and fr is not None:
                if death is None or fr < death:
                    death = fr
            if "ALL WAVES DEFEATED" in line and fr is not None and counter is None:
                counter = fr
            if "Priest ADVANCE to Siege" in line:
                adv += 1
            if "Priest converting Siege Workshop" in line:
                conv += 1
                if first_conv is None and fr is not None:
                    first_conv = fr
    if win:
        res = "WIN"
    elif death is not None:
        res = "LOSS"
    else:
        res = "UND"
    return dict(base=os.path.basename(base), res=res, death=death, counter=counter,
                adv=adv, conv=conv, first_conv=first_conv, last_frame=last_frame)


def fisher(a, b, c, d):
    """two-tailed Fisher exact; table [[a,b],[c,d]]"""
    n = a + b + c + d
    def C(n, k):
        return math.comb(n, k) if 0 <= k <= n else 0
    r1, r2, c1 = a + b, c + d, a + c
    if n == 0 or c1 == 0:
        return 1.0
    pcut = C(r1, a) * C(r2, c) / C(n, c1)
    p = 0.0
    for i in range(max(0, c1 - r2), min(c1, r1) + 1):
        pv = C(r1, i) * C(r2, c1 - i) / C(n, c1)
        if pv <= pcut + 1e-15:
            p += pv
    return p


def wilson(k, n):
    if n == 0:
        return (0, 0)
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h) * 100, min(1, c + h) * 100)


def main(prefixes):
    print("=" * 96)
    print("跨地图胜率矩阵  (判据: 胜=jsonl任一行 win:true / 负=DEFEAT: Priest killed / 其余=未决)")
    print("=" * 96)
    hdr = "%-20s %5s %5s %5s %5s  %8s %10s   %6s %6s %6s %6s %6s"
    print(hdr % ("地图", "n", "胜", "负", "未决", "胜率", "95%CI", "祭司死", "早死", "进反攻", "ADV>0", "首感化"))
    print("-" * 96)
    total = defaultdict(int)
    per_map = {}
    for pre, label in prefixes:
        games = [g for g in (analyze(b) for b in sorted(glob.glob(pre + "*.ait")) ) if g]
        games = [analyze(base) for base in sorted(set(f[:-4] for f in glob.glob(pre + "*.ait")))]
        games = [g for g in games if g]
        n = len(games)
        if n == 0:
            print(hdr % (label, 0, "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"))
            continue
        w = sum(1 for g in games if g["res"] == "WIN")
        l = sum(1 for g in games if g["res"] == "LOSS")
        u = sum(1 for g in games if g["res"] == "UND")
        deaths = sum(1 for g in games if g["death"] is not None)
        early = sum(1 for g in games if g["death"] is not None and g["death"] < EARLY)
        cnt = sum(1 for g in games if g["counter"] is not None)
        advg = sum(1 for g in games if g["adv"] > 0)
        fcs = [g["first_conv"] for g in games if g["first_conv"]]
        fc = int(sum(fcs) / len(fcs)) if fcs else "-"
        lo, hi = wilson(w, n)
        print(hdr % (label, n, w, l, u, "%.1f%%" % (100 * w / n), "%.1f~%.1f" % (lo, hi),
                     deaths, early, cnt, advg, fc))
        per_map[pre] = dict(n=n, w=w, l=l, u=u, deaths=deaths, early=early, cnt=cnt, advg=advg, games=games)
        total["n"] += n; total["w"] += w; total["l"] += l; total["u"] += u
        total["deaths"] += deaths; total["early"] += early
    print("-" * 96)
    if total["n"]:
        lo, hi = wilson(total["w"], total["n"])
        print(hdr % ("合计", total["n"], total["w"], total["l"], total["u"],
                     "%.1f%%" % (100 * total["w"] / total["n"]), "%.1f~%.1f" % (lo, hi),
                     total["deaths"], total["early"], "", "", ""))

    # 逐局明细
    print()
    print("=" * 96)
    print("逐局明细")
    print("=" * 96)
    print("%-8s %-6s %-8s %-8s %-6s %-6s" % ("局", "结果", "死亡帧", "反攻起", "ADV", "CONV"))
    for pre, label in prefixes:
        for g in per_map.get(pre, {}).get("games", []):
            print("%-8s %-6s %-8s %-8s %-6d %-6d" % (
                g["base"], g["res"], g["death"] if g["death"] is not None else "-",
                g["counter"] if g["counter"] is not None else "-", g["adv"], g["conv"]))
        print()

    # 地图两两显著性（胜率）
    print("=" * 96)
    print("地图 vs map3 胜率差异（Fisher 精确检验, two-tailed）")
    print("=" * 96)
    if "z3" in per_map:
        b = per_map["z3"]
        for pre, label in prefixes:
            if pre == "z3" or pre not in per_map:
                continue
            a = per_map[pre]
            p = fisher(a["w"], a["n"] - a["w"], b["w"], b["n"] - b["w"])
            print("  %-20s 胜率 %5.1f%% vs map3 %5.1f%%   p=%.4f %s" % (
                label, 100 * a["w"] / a["n"], 100 * b["w"] / b["n"], p,
                "<-- 显著" if p < 0.05 else ""))


if __name__ == "__main__":
    pres = MAPS if len(sys.argv) < 2 else [(a, a) for a in sys.argv[1:]]
    main(pres)
