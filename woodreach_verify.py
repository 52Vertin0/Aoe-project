#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-09-21 woodreach 验证分析：当前批次(wd) vs 历史基线
# 主判据：
#   ① WOOD-TREE|enclosedSkipped= 的累计跳过数（应适中；若某局极大=森林树被误杀）
#   ② [STUCK] 计数（应下降，说明围死树不再被派）
#   ③ 仓库同群重复（type=3 BUILD-ISSUE 相邻块距<=9）
import io, re, os, glob, math, sys

PY = sys.executable
RE_WOOD = re.compile(r'WOOD-TREE \| sn=(\d+) anchor=([-\d.]+)BL villager=([-\d.]+)BL cnt=(\d+) \(maxAnchor=([\d.]+)BL\) \| enclosedSkipped=(\d+)')
RE_STUCK = re.compile(r'\[STUCK\]')
RE_BUILD3 = re.compile(r'\[BUILD-ISSUE f=(\d+)\] type=3 .*?at=\((\d+),(\d+)\)')

def analyze(fp):
    d = {'wood_n':0,'enclosed':[],'stuck':0,'build3':[]}
    for r in io.open(fp, encoding='utf-8', errors='replace').readlines():
        m = RE_WOOD.search(r)
        if m:
            d['wood_n'] += 1
            d['enclosed'].append(int(m.group(6)))
        if RE_STUCK.search(r):
            d['stuck'] += 1
        m2 = RE_BUILD3.search(r)
        if m2:
            d['build3'].append((int(m2.group(1)), int(m2.group(2)), int(m2.group(3))))
    return d

def stock_dup(build3):
    # 相邻两条 type=3 令 块距<=9 的对数
    pairs = 0
    for i in range(len(build3)):
        for j in range(i+1, len(build3)):
            if math.hypot(build3[i][1]-build3[j][1], build3[i][2]-build3[j][2]) <= 9:
                pairs += 1
    return pairs

batch = sys.argv[1] if len(sys.argv)>1 else 'wd'
files = sorted(glob.glob('%s*.ait' % batch))
if not files:
    print('no %s*.ait' % batch); sys.exit(0)
print('=== 批次 %s：%d 局 ===' % (batch, len(files)))
tot_wood=tot_stuck=tot_dup=0
max_enc_per_game=[]
games_with_big_enc=0
for fp in files:
    d = analyze(fp)
    tot_wood += d['wood_n']
    tot_stuck += d['stuck']
    tot_dup += stock_dup(d['build3'])
    me = max(d['enclosed']) if d['enclosed'] else 0
    max_enc_per_game.append(me)
    if me >= 50: games_with_big_enc += 1
    # 单局简报（前几局）
print('WOOD-TREE 诊断总条数 = %d（每局约 %d 条，frame%%600）' % (tot_wood, tot_wood//len(files)))
print('enclosedSkipped：单局最大值 中位/平均 = %d / %d' % (
    max(max_enc_per_game), sum(max_enc_per_game)//len(max_enc_per_game)))
print('  ⚠ 单局 max(enclosed)>=50 的局数 = %d / %d（若多=森林树被误杀，需回退）' % (games_with_big_enc, len(files)))
print('[STUCK] 总次数 = %d（历史基线 700+局 2376 ≈ 3.4/局；应明显下降）' % tot_stuck)
print('仓库同群重复(块距<=9)对数 = %d（历史多仓局 45.6%% 出现；应趋近0）' % tot_dup)
print()
print('【单局 max(enclosedSkipped) 列表】')
for fp,me in zip(files, max_enc_per_game):
    print('  %-12s max=%d' % (os.path.basename(fp), me))
