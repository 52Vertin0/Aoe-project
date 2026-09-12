#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""跑局归因统计（复用型）：判定胜负 / 败因 / 感化成功链 / 单位产能。
用法: python winstat.py m3        (统计 m3*.jsonl / m3*.ait)
判据全部来自实测口径（见 MEMORY.md §2），不做任何推断:
  - 胜 = jsonl 中【存在任意一行】 "win":true（必须扫全文件；胜帧后引擎会再写一帧 win:false）
  - 本图胜利条件 = ait 中 "攻城武器厂(编号:11421)被祭司转换"（09-28 逐局核对为 100% 相关）
  - 败因 = DEFEAT: Priest killed / DEFEAT: Town Center；其余未决
  - 真实产能 = "产生了新的X(编号:N)" 且 frame>0（frame=0 是地图预置，会污染统计）
"""
import re, sys, glob, collections, os

PREFIX = sys.argv[1] if len(sys.argv) > 1 else "m3"
# ⚠ 必须锚定【全部四段】前缀 time|frame|color|flag，否则 `\| (\d+) \|` 会错位匹配到别处、
#   产出数字会串成一个固定假值（本脚本第一版就踩了：所有局都显示 7/0/11/0）。
#   行格式（实测 repr）：'00:00:000 | 0 | blue | 0 |  产生了新的村民(编号:41425)'
#   ⇒ group(4)=frame；frame=0 是地图预置单位，必须滤掉才能得到"真实产能"。
NEW = re.compile(r'^(\d+):(\d+):(\d+) \| (\d+) \| (\w+) \| (\d+) \|  产生了新的(.+?)\(编号:(\d+)\)', re.M)
DEF_P = re.compile(r'DEFEAT:\s*Priest killed')
DEF_T = re.compile(r'DEFEAT:\s*Town Center')

rows = []
for jp in sorted(glob.glob(PREFIX + "*.jsonl")):
    base = jp[:-6]
    ap = base + ".ait"
    if not os.path.exists(ap):
        continue
    js = open(jp, encoding='utf-8', errors='replace').read()
    at = open(ap, encoding='utf-8', errors='replace').read()
    win = '"win":true' in js
    conv = re.search(r'被祭司转换', at)
    pk = DEF_P.search(at)
    tc = DEF_T.search(at)
    # 起手次数
    starts = len(re.findall(r'Priest converting Siege Workshop', at))
    towers = re.findall(r'Priest converting Siege Workshop.*?towers=(\d+)', at)
    # 真实产能（frame>0）
    prod = collections.Counter()
    for m in NEW.finditer(at):
        if int(m.group(4)) != 0:              # group(4) = frame；frame=0 = 地图预置
            prod[m.group(7).strip()] += 1     # group(7) = 兵种名
    rows.append(dict(f=os.path.basename(base), win=win, conv=bool(conv),
                     pk=bool(pk), tc=bool(tc), starts=starts,
                     towers=[int(x) for x in towers], prod=prod,
                     last=(re.findall(r'"frame":(\d+)', js) or ["0"])[-1]))

W = [r for r in rows if r['win']]
L = [r for r in rows if not r['win']]
print("=== %s ：共 %d 局  胜=%d 负/未决=%d  胜率=%.1f%% ===" % (
    PREFIX, len(rows), len(W), len(L), 100.0 * len(W) / max(1, len(rows))))
print()
print("%-8s %-5s %-6s %-8s %-6s %-8s %s" % ("局", "胜负", "感化", "祭司死", "起手", "末帧", "产能(复合弓/村民/方阵/棍棒)"))
for r in rows:
    print("%-8s %-5s %-6s %-8s %-6s %-8s 复合弓=%-3d 村民=%-3d 方阵=%-3d 棍棒=%-3d" % (
        r['f'], "WIN" if r['win'] else "LOSS", "Y" if r['conv'] else "-",
        "Y" if r['pk'] else "-", r['starts'], r['last'],
        r['prod'].get('复合弓兵', 0), r['prod'].get('村民', 0),
        r['prod'].get('方阵兵', 0), r['prod'].get('棍棒兵', 0)))

print()
print("=== 相关性核对（胜利条件）===")
print("  胜局有转换 = %d/%d" % (sum(1 for r in W if r['conv']), len(W)))
print("  负局有转换 = %d/%d" % (sum(1 for r in L if r['conv']), len(L)))
print()
print("=== 败因分解 ===")
for r in L:
    why = "祭司死" if r['pk'] else ("TC被毁" if r['tc'] else "未决/其它")
    reason = ""
    if not r['conv'] and r['starts'] == 0:
        reason = "  ← 未起手"
    print("  %-8s %-10s 起手=%d%s" % (r['f'], why, r['starts'], reason))
print()
print("=== 起手 towers 分布 ===")
tc_ = collections.Counter()
for r in rows:
    for t in r['towers']:
        tc_[t] += 1
print("  " + "  ".join("towers=%d:%d" % kv for kv in sorted(tc_.items())))
