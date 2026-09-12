# -*- coding: utf-8 -*-
"""
注释补漏：findFarmSiteBest 的【函数级】注释块里还有一份「谷仓/仓库」措辞（文件头那份已在
patch_20260919_farm_anchor_granary_only.py 里改过）。纯注释，零行为影响。
用法：python patch_20260919_comment_sweep.py [--dry]
"""
import sys

P = r'C:\new-aoe3.0.7g\UsrAI.cpp'
DRY = '--dry' in sys.argv


def rep(text, old, new, tag):
    o = old.replace('\r\n', '\n').replace('\n', '\r\n')
    n = new.replace('\r\n', '\n').replace('\n', '\r\n')
    c = text.count(o)
    if c != 1:
        raise SystemExit('[FAIL] %s 命中 %d 次（期望 1）' % (tag, c))
    return text.replace(o, n)


raw = open(P, 'rb').read().decode('utf-8')

raw = rep(raw,
    '//   候选空间 = TC 环 ∪ 各已建成【谷仓 GRANARY / 仓库 STOCK】环（半径 [R_MIN, R_MAX]，隔 1 格几何）。',
    '//   候选空间 = TC 环 ∪ 各已建成【谷仓 GRANARY】环（半径 [R_MIN, R_MAX]，隔 1 格几何）；\n'
    '//   ★ 2026-09-19 用户要求：仓库 STOCK 不再作锚点（详见文件头 FARM_ANCHOR_R_MAX 下方需求块）。',
    'S1 函数级注释-候选空间')

raw = rep(raw,
    '//   ⇒ TC 旁优先；只有 TC 环半径内全满，谷仓/仓库旁才会胜出 = 用户原话「基地附近位置不够的话」。',
    '//   ⇒ TC 旁优先；只有 TC 环半径内全满，谷仓旁才会胜出 = 用户原话「基地附近位置不够的话」。',
    'S2 函数级注释-谷仓旁')

if DRY:
    print('[DRY] S1/S2 各命中 1 次，未落盘')
else:
    open(P, 'wb').write(raw.encode('utf-8'))
    print('[OK] 已落盘，bytes=%d lines=%d' % (len(raw.encode('utf-8')), raw.count('\n')))
