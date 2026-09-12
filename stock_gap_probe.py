# -*- coding: utf-8 -*-
"""仓库重复下令：连发间隔与落点偏移诊断（2026-09-20）"""
import re, os, glob, math
from collections import Counter, defaultdict

RE = re.compile(r"\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) .*?at=\((\d+),(\d+)\)")
WAVE2 = 13500


def main():
    files = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "*.ait")))
    gaps = Counter()          # 相邻两条仓库令的帧间隔
    gaps_same_spot = Counter()  # 块距<=9 时的帧间隔
    offsets = Counter()       # 同群(<20)时的偏移形态
    firstmin = None
    nfirst_after_wave2 = 0
    games = 0
    per_batch = defaultdict(lambda: Counter())

    for fp in files:
        games += 1
        st = []
        with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if "[BUILD-ISSUE" not in line or "type=3 " not in line:
                    continue
                m = RE.search(line)
                if m:
                    st.append((int(m.group(1)), int(m.group(4)), int(m.group(5))))
        if not st:
            continue
        f0 = st[0][0]
        firstmin = f0 if firstmin is None else min(firstmin, f0)
        if f0 >= WAVE2:
            nfirst_after_wave2 += 1
        for i in range(len(st) - 1):
            df = st[i + 1][0] - st[i][0]
            dd = math.hypot(st[i + 1][1] - st[i][1], st[i + 1][2] - st[i][2])
            gaps[df if df <= 30 else 31] += 1
            if dd <= 9:
                gaps_same_spot[df if df <= 30 else 31] += 1
                offsets[f"({st[i+1][1]-st[i][1]:+d},{st[i+1][2]-st[i][2]:+d})"] += 1

    print("=" * 90)
    print(f"局数={games}  出现过仓库建造令的局内，首条仓库令最早帧 = {firstmin}")
    print(f"首条仓库令 >= WAVE2_TIME(13500) 的局数 = {nfirst_after_wave2}  ⇒ Block A(无时机闸) 建仓嫌疑 = "
          f"{'无' if nfirst_after_wave2 == games else '有'}")
    print()
    print("【1】相邻两条仓库建造令的帧间隔分布（上限桶 31 = >30）")
    for k in sorted(gaps):
        lab = ">30" if k == 31 else str(k)
        print(f"  间隔 {lab:>4} 帧 : {gaps[k]:5d} 次  {'#'*min(70, gaps[k]//2)}")
    print()
    print("【2】仅『同点/同群(块距<=9)』的相邻下令：帧间隔分布")
    for k in sorted(gaps_same_spot):
        lab = ">30" if k == 31 else str(k)
        print(f"  间隔 {lab:>4} 帧 : {gaps_same_spot[k]:5d} 次  {'#'*min(70, gaps_same_spot[k]//2)}")
    print()
    print("【3】同群重复时的落点偏移形态（dx,dy）")
    for k, v in offsets.most_common(20):
        print(f"  {k:>10} : {v:5d}")


if __name__ == "__main__":
    main()
