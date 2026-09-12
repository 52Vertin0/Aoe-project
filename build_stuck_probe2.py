#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 建筑待建诊断：扫描 ait 日志，统计 ORPHAN 抢救 / BUILDER-HARD 超时，并定位"反复 ORPHAN 同一地基"的持久失败地基。
import io, re, os, glob, sys
from collections import defaultdict

RE_ORPHAN = re.compile(r'\[ORPHAN f=(\d+)\] 地基SN=(\d+) type=(\d+) percent=(\d+).*?(?:\(抽采集岗\))?')
RE_HARD = re.compile(r'\[BUILDER-HARD f=(\d+)\] 建造者SN=(\d+) type=(\d+) 地基SN=(\d+) percent=(\d+) 超时(\d+)帧 -> (.*)$')
RE_ISSUE = re.compile(r'\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) 村民SN=(\d+) at=\((\d+),(\d+)\) wood=(\d+)')

def analyze(fp):
    orphans=[]; hards=[]; issues=0
    for r in io.open(fp, encoding='utf-8', errors='replace').readlines():
        m=RE_ORPHAN.search(r)
        if m: orphans.append((int(m.group(2)), int(m.group(4)))); continue
        m=RE_HARD.search(r)
        if m: hards.append((int(m.group(4)), int(m.group(5)), m.group(7))); continue
        if RE_ISSUE.search(r): issues+=1
    return orphans, hards, issues

batch = sys.argv[1] if len(sys.argv)>1 else 'wd'
files = sorted(glob.glob('%s*.ait'%batch))
if not files:
    print('no %s*.ait'%batch); sys.exit(0)
print('=== 批次 %s：%d 局 ===' % (batch, len(files)))
tot_orphan=tot_hard=tot_issue=0
persist=defaultdict(int)
hard_dead=0; hard_release=0
type_name={1:'HOME',2:'GRANARY',3:'FARM',4:'MARKET',5:'ARMYCAMP',6:'RANGE',7:'STABLE',8:'ARROWTOWER',9:'STOCK',10:'COLLAGE'}
for fp in files:
    orphans,hards,issues = analyze(fp)
    tot_orphan+=len(orphans); tot_hard+=len(hards); tot_issue+=issues
    for sn,pc in orphans: persist[sn]+=1
    for sn,pc,sub in hards:
        if '作废' in sub: hard_dead+=1
        else: hard_release+=1
print('BUILD-ISSUE 总条数 = %d（约 %.1f/局）' % (tot_issue, tot_issue/len(files)))
print('ORPHAN 抢救总次数 = %d（约 %.1f/局）' % (tot_orphan, tot_orphan/len(files)))
print('BUILDER-HARD 总次数 = %d（作废另址=%d / 仅释放=%d）' % (tot_hard, hard_dead, hard_release))
print()
print('【被反复 ORPHAN（同一地基 ≥3 次）的持久失败地基】')
for fp in files:
    orphans,hards,issues = analyze(fp)
    seen=set()
    for sn,pc in orphans:
        if persist[sn] >= 3 and sn not in seen:
            seen.add(sn)
            print('  文件=%s 地基SN=%d 被ORPHAN=%d次 末次percent=%d' % (os.path.basename(fp), sn, persist[sn], pc))
