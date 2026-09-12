# -*- coding: utf-8 -*-
"""量化"石头是否多采"：逐局看石头存量的峰值 & 与 150 的余数关系。
用户观察：每次会多采 40 石头。
假设：STONE_CAP_STOP=300 是【存量阈值】，但一车石头 = 10（150石只需15车）。
      若停采判据只看"存量≥300"，而采石工手上未交回的那部分没算，
      则实际会超出；另外若判据用 countBuildings(仅已建成) 而漏掉在建塔，
      则第2/3座塔的地基不会提前触发停采。
"""
import os, re, glob

BASE = r"C:\new-aoe3.0.7g"
TAGS = ["sg", "th", "hc3", "hc4", "sz"]

def scan(tag):
    files = sorted(glob.glob(os.path.join(BASE, tag + "[0-9]*.ait")))
    if not files:
        return
    print("=" * 80)
    print(f"批次 {tag}（{len(files)} 局）")
    print("=" * 80)
    for fp in files:
        raw = open(fp, "rb").read().decode("utf-8", "replace")
        lines = raw.splitlines()
        # 石头存量：找 [STONE...] 或资源打印
        peaks = []
        for ln in lines:
            m = re.search(r"Stone[=:]\s*(\d+)", ln)
            if m:
                peaks.append(int(m.group(1)))
        # 采石相关标签
        stoneTags = re.findall(r"\[(STONE[^\]]*)\]", raw)
        nTower = raw.count("箭塔(编号")
        nTowerDone = len(re.findall(r"箭塔\(编号:\d+\)建造完毕", raw))
        win = "VICTORY! Siege Workshop converted" in raw
        print(f"  {os.path.basename(fp):<14} 石头峰值样本={len(peaks):<4} "
              f"max={max(peaks) if peaks else 'NA':<5} "
              f"塔完工={nTowerDone} 胜={win} 标签={sorted(set(stoneTags))[:3]}")

for t in TAGS:
    scan(t)
