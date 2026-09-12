# -*- coding: utf-8 -*-
"""把各验证批次的【结果指标 + 机制指标】汇总成一张排名表。
用途：回答"回滚到胜率最高的那一版" —— 但必须先证明"胜率"这个指标本身可信。
铁律 25/36：8 局/批的结果指标（胜负）噪声 σ≈1.4 局，摆动 ≥3 局 = 37pp，不可单独定论。
所以本脚本同时打印机制指标（感化起手 = 引擎动作日志，不受采样影响）。"""
import os, re, glob, sys

BASE = r"C:\new-aoe3.0.7g"
# 批次 -> 物理代码版本（行数/md5 已人工核对）
TAGS = [
    ("sg",  "bak_20260915_shrink_UsrAI.cpp",    "shrink 修复版 6428行"),
    ("dm",  "? (directmarch)",                  "反攻直达+退让"),
    ("sb",  "? (stuckback 修后)",               "卡死退让修复"),
    ("sba", "? (stuckback 缺陷版)",             "卡死退让缺陷"),
    ("th",  "bak_20260916_towerhit_UsrAI.cpp",  "towerhit 6430行"),
    ("sz",  "bak_20260915_shrink_UsrAI.cpp",    "shrink（sz 与 sg 同码复跑）"),
    ("mc",  "? (mcslim 重构)",                  "mcslim 重构"),
    ("md",  "? (mcslim 重构复跑)",              "mcslim 同码复跑"),
    ("ps",  "bak_20260916_prieststrict_UsrAI.cpp","prieststrict 6473行"),
]

WIN  = "VICTORY! Siege Workshop converted"
LOSE = re.compile(r"DEFEAT: (Priest killed|Town Center destroyed)")
START = "设置转换目标为 攻城武器厂"

def analyze(tag):
    files = sorted(glob.glob(os.path.join(BASE, tag + "[0-9]*.ait")))
    if not files:
        return None
    w = d = t = 0
    start = 0
    for fp in files:
        raw = open(fp, "rb").read().decode("utf-8", "replace")
        if WIN in raw:
            w += 1
        elif LOSE.search(raw):
            d += 1
        else:
            t += 1
        start += raw.count(START)
    return dict(tag=tag, n=len(files), win=w, lose=d, timeout=t,
                start=start, conv=(w * 100 // start if start else 0))

rows = []
for tag, fname, note in TAGS:
    r = analyze(tag)
    if r:
        r["file"] = fname
        r["note"] = note
        rows.append(r)

print("=" * 96)
print("批次汇总（结果指标 + 机制指标）")
print("=" * 96)
print(f"{'批次':<5}{'胜':<4}{'负':<4}{'无结局':<7}{'胜率':<8}{'感化起手':<9}{'转化率':<8}{'代码版本'}")
print("-" * 96)
for r in sorted(rows, key=lambda x: (-x["win"], -x["start"])):
    print(f"{r['tag']:<5}{r['win']:<4}{r['lose']:<4}{r['timeout']:<7}"
          f"{str(r['win']*100//r['n'])+'%':<8}{r['start']:<9}{str(r['conv'])+'%':<8}{r['file']}")
print("=" * 96)
print()
print("★ 判读规则（铁律 25/36）：")
print("  - 8 局/批的『胜率』摆动可达 37pp，sg 与 th 的 4/8 平局【无法区分】。")
print("  - 机制指标『感化起手』是引擎动作日志，不受采样影响，才是可信排序依据。")
print("  - 同码复跑对照：sg vs sz（同 shrink 码）→ 4/8 vs 2/8；mc vs md（同 mcslim 码）→ 2/8 vs 1/8。")
print("    ⇒ 同一份代码自己就差 2 胜/1 胜，证明 8 局/批的胜率差不可作因果结论。")
