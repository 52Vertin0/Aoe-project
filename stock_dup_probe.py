# -*- coding: utf-8 -*-
"""
仓库重复建造诊断探针（2026-09-20）
目标：回答"同一瞪羚群附近为何出现 2 座仓库"。
口径：
  - 建造令来源 = [BUILD-ISSUE ...] type=3（仓库 STOCK）at=(x,y)  —— 全量，无采样
  - Block A（瞪羚群中心仓库，cpp:1658）日志 = [GAZELLE-STOCK ...] —— 受 frame%60==0 采样
  - Block B（第二仓库，cpp:1907）无专属日志，但时机闸 frame>WAVE2_TIME(13500) 可做归因
判据：
  - 同点重复：两座仓库块距 <= 9（tryBuild 偏移表为 0/±3/±6 ⇒ 同簇被挤到旁边）
  - 同群邻近：10 ~ 20（同一连通群内，B 的"距现有仓库 >20 格"判据把它们当两只独立远距瞪羚）
  - 分散：> 20
"""
import re, os, sys, glob, math
from collections import defaultdict, Counter

AIT_GLOB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "*.ait")
RE_BUILD = re.compile(r"\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) .*?at=\((\d+),(\d+)\)")
RE_GZSTOCK = re.compile(r"\[GAZELLE-STOCK")
WAVE2 = 13500
WINDOW_END = 16500


def parse(path):
    """返回 (stocks, gz_logs)；stocks = [(frame,x,y), ...]"""
    stocks = []
    gz = 0
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if "[GAZELLE-STOCK" in line:
                    gz += 1
                if "[BUILD-ISSUE" not in line or "type=3 " not in line:
                    continue
                m = RE_BUILD.search(line)
                if m:
                    stocks.append((int(m.group(1)), int(m.group(2)) if False else int(m.group(4)), int(m.group(5))))
    except Exception:
        pass
    return stocks, gz


def main():
    files = sorted(glob.glob(AIT_GLOB))
    batches = defaultdict(lambda: {"games": 0, "with2": 0, "dup_point": 0, "dup_herd": 0,
                                   "spread": 0, "stockcnt": Counter(), "first_frame": Counter(),
                                   "min_dists": [], "gzlog": 0})
    examples = []
    total_gzlog = 0

    for fp in files:
        name = os.path.basename(fp)
        b = name.split("_")[0] if "_" in name else name.replace(".ait", "")
        st, gz = parse(fp)
        total_gzlog += gz
        d = batches[b]
        d["games"] += 1
        d["gzlog"] += gz
        n = len(st)
        d["stockcnt"][n] += 1
        if n == 0:
            continue
        # 首座仓库的下令帧 → 归因（< 13500 只可能是 A；> 13500 两可）
        d["first_frame"]["<13500" if st[0][0] < WAVE2 else ("13500~16500" if st[0][0] <= WINDOW_END else ">16500")] += 1
        if n < 2:
            continue
        d["with2"] += 1
        # 最小成对距离
        best = None
        for i in range(n):
            for j in range(i + 1, n):
                dd = math.hypot(st[i][1] - st[j][1], st[i][2] - st[j][2])
                if best is None or dd < best[0]:
                    best = (dd, i, j)
        md = best[0]
        d["min_dists"].append(md)
        if md <= 9:
            d["dup_point"] += 1
            if len(examples) < 25:
                examples.append((name, md, st))
        elif md <= 20:
            d["dup_herd"] += 1
            if len(examples) < 50:
                examples.append((name, md, st))
        else:
            d["spread"] += 1

    print("=" * 96)
    print("【0】样本规模")
    allgames = sum(d["games"] for d in batches.values())
    print(f"  ait 文件（局）={allgames}  批次={len(batches)}  [GAZELLE-STOCK] 日志总条数={total_gzlog}")
    print()
    print("=" * 96)
    print("【1】每局仓库建造令条数分布（BUILD-ISSUE type=3）")
    tot = Counter()
    for d in batches.values():
        tot.update(d["stockcnt"])
    for k in sorted(tot):
        print(f"  {k} 座 : {tot[k]:5d} 局 ({tot[k]/allgames*100:5.1f}%)")
    print()
    print("=" * 96)
    print("【2】多仓局的成对距离分类（同点<=9 / 同群10~20 / 分散>20）")
    print(f"  {'批次':<8}{'局数':>6}{'≥2仓':>7}{'同点':>7}{'同群':>7}{'分散':>7}   首座下令帧分布")
    g2 = gpt = gph = gsp = 0
    for b in sorted(batches):
        d = batches[b]
        g2 += d["with2"]; gpt += d["dup_point"]; gph += d["dup_herd"]; gsp += d["spread"]
        ff = " ".join(f"{k}:{v}" for k, v in sorted(d["first_frame"].items()))
        print(f"  {b:<8}{d['games']:>6}{d['with2']:>7}{d['dup_point']:>7}{d['dup_herd']:>7}{d['spread']:>7}   {ff}")
    print(f"  {'合计':<8}{allgames:>6}{g2:>7}{gpt:>7}{gph:>7}{gsp:>7}")
    print(f"  ⇒ 多仓局中，同点/同群重复占比 = {(gpt+gph)/max(1,g2)*100:.1f}%  (同点 {gpt/max(1,g2)*100:.1f}% + 同群 {gph/max(1,g2)*100:.1f}%)")
    print()
    print("=" * 96)
    print("【3】多仓局最小仓间距分布（块）")
    alld = [x for d in batches.values() for x in d["min_dists"]]
    hist = Counter()
    for x in alld:
        hist[int(x) // 5 * 5] += 1
    for k in sorted(hist):
        print(f"  {k:3d}~{k+4:3d} : {hist[k]:4d}  {'#'*min(60,hist[k])}")
    print()
    print("=" * 96)
    print("【4】实例（同点/同群优先）")
    for name, md, st in examples[:30]:
        tag = "同点" if md <= 9 else "同群"
        pts = " ".join(f"f{f}({x},{y})" for f, x, y in st)
        print(f"  [{tag}] {name:<16} minD={md:5.1f}  {pts}")
    print()
    print("=" * 96)
    print("【5】[GAZELLE-STOCK] 日志（Block A 的唯一可观测点）")
    print(f"  全库命中 = {total_gzlog} 条  ⇒ " +
          ("Block A 在样本中【从未成功建仓】" if total_gzlog == 0 else "Block A 有活动"))
    # 原始行抽查
    hit = 0
    for fp in files[:400]:
        with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if "GAZELLE-STOCK" in line:
                    print("   ", line.strip()[:150]); hit += 1
                    if hit >= 5: break
        if hit >= 5: break


if __name__ == "__main__":
    main()
