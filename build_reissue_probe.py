#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 建筑重建/卡死范围：统计每个 wd 局中"唯一建筑"(谷仓/市场/兵营/靶场/马厩/学院)被 BUILD-ISSUE 的次数。
# 唯一建筑正常只发 1 次(建完 countBuildingsExisting>=1 不再发)；若发 >=2 次 = 前一座未完工(被卡/被毁)→ 重建或卡死证据。
import io, re, glob, sys
from collections import defaultdict, Counter

RE_ISSUE = re.compile(r'\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) 村民SN=(\d+) at=\((\d+),(\d+)\) wood=(\d+)')
UNIQUE = {2:'GRANARY',3:'FARM',4:'MARKET',5:'ARMYCAMP',6:'RANGE',7:'STABLE',10:'COLLAGE'}
# 注：FARM 非唯一(可多座)，但同坐标重复下发也异常；这里只统计唯一建筑

batch = sys.argv[1] if len(sys.argv)>1 else 'wd'
files = sorted(glob.glob('%s*.ait'%batch))
print('=== %s：唯一建筑 BUILD-ISSUE 复发(>=2次=前座未完工) ===' % batch)
games_with_reissue=0
for fp in files:
    cnt = Counter()
    for r in io.open(fp, encoding='utf-8', errors='replace').readlines():
        m=RE_ISSUE.search(r)
        if m:
            t=int(m.group(2))
            if t in UNIQUE: cnt[t]+=1
    reissued = {UNIQUE[t]:c for t,c in cnt.items() if c>=2}
    if reissued:
        games_with_reissue+=1
        print('  %-10s 复发=%s' % (fp, reissued))
print('含唯一建筑复发的局数 = %d / %d' % (games_with_reissue, len(files)))
