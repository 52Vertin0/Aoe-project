# -*- coding: utf-8 -*-
"""「复合弓兵不要拉扯战车弓兵和投石车」验收探针（2026-09-21）。

用途：从 .ait 日志里量化"拉扯目标兵种"，直接验证
  ① 改后拉扯对【射程占优】的目标仍生效（[KIT-R]/[KIT-S] 计数不塌）
  ② 拉扯目标里【绝不出现】战车弓(12) / 投石车(8)  —— 判据落地的直接证据
  ③ [KIT-NO] 出现 ⇒ 过滤真的在起效（不是"因为附近没这两种兵才没出现"）

口径（技能 §1/§2.6）：
  · 行 = `time | frame | color | flag | message`，必须 split(' | ', 3) 取 message；
  · [KIT-R]/[KIT-S]/[KIT-NO] 是 AI 的 DebugText(black 行)，帧号取 p[1]（权威帧）。

用法：
  python kitno_probe.py show <ait...>     # 逐局明细
  python kitno_probe.py scan "<glob>"     # 跨局汇总（旧日志无 tSort 字段时只统计 KIT-R/S 总量）
"""
import glob
import os
import re
import sys
from collections import Counter

# 兵种枚举（config.h AT_ARMY）
SORT = {0: '棍棒兵', 1: '投石兵', 2: '弓兵', 3: '侦察兵', 4: '剑士', 5: '精锐弓?',
        6: '骑兵', 7: '船', 8: '投石车', 9: '祭司', 10: '方阵兵', 11: '战车',
        12: '战车弓兵', 13: '阔剑兵', 14: '复合弓兵', -1: '村民/未知'}

RE_KITR = re.compile(r'\[KIT-R f=(\d+)\] SN=(\d+) dK=([\d.]+) R=([\d.]+) stage=(\d+) stuck=(\d+) aged=(\d+).*?tSort=(-?\d+)')
RE_KITR_OLD = re.compile(r'\[KIT-R f=(\d+)\] SN=(\d+)')
RE_KITS = re.compile(r'\[KIT-S f=(\d+)\] SN=(\d+).*?tSort=(-?\d+)')
RE_KITS_OLD = re.compile(r'\[KIT-S f=(\d+)\] SN=(\d+)')
RE_KITNO = re.compile(r'\[KIT-NO f=(\d+)\] SN=(\d+) .*?Sort=(-?\d+)')


def parse(path):
    r = dict(game=os.path.basename(path), kits=Counter(), kitno=Counter(),
             n_kitr=0, n_kits=0, n_kitno=0, tSort_r=Counter(), tSort_s=Counter(),
             stage=Counter(), last_frame=0, victory=0, defeat_priest=0, defeat_tc=0)
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            p = line.split(' | ', 3)
            if len(p) >= 2:
                try:
                    r['last_frame'] = max(r['last_frame'], int(p[1]))
                except ValueError:
                    pass
            if len(p) < 4:
                continue
            msg = p[3]
            m = RE_KITR.search(msg)
            if m:
                r['n_kitr'] += 1
                r['tSort_r'][int(m.group(8))] += 1
                r['stage'][int(m.group(5))] += 1
            elif RE_KITR_OLD.search(msg):      # 旧版日志：无 tSort 字段
                r['n_kitr'] += 1
                r['tSort_r']['OLD'] += 1
            m = RE_KITS.search(msg)
            if m:
                r['n_kits'] += 1
                r['tSort_s'][int(m.group(3))] += 1
            elif RE_KITS_OLD.search(msg):
                r['n_kits'] += 1
                r['tSort_s']['OLD'] += 1
            m = RE_KITNO.search(msg)
            if m:
                r['n_kitno'] += 1
                r['kitno'][int(m.group(3))] += 1
            if 'VICTORY! Siege Workshop converted' in msg:
                r['victory'] += 1
            if 'DEFEAT: Priest killed' in msg:
                r['defeat_priest'] += 1
            if 'DEFEAT: Town Center destroyed' in msg:
                r['defeat_tc'] += 1
    return r


def fmt_cnt(c):
    if not c:
        return '-'
    return ' '.join('%s(%s)=%d' % (k, SORT.get(k, '?') if isinstance(k, int) else '旧日志无此字段', v)
                    for k, v in sorted(c.items(), key=lambda x: str(x[0])))


def show(paths):
    print('%-22s %-7s %-7s %-7s %s' % ('game', 'KIT-R', 'KIT-S', 'KIT-NO', '胜负'))
    bad = 0
    tot_r = tot_s = tot_no = 0
    all_r = Counter(); all_s = Counter(); all_no = Counter()
    for p in paths:
        r = parse(p)
        tot_r += r['n_kitr']; tot_s += r['n_kits']; tot_no += r['n_kitno']
        all_r.update(r['tSort_r']); all_s.update(r['tSort_s']); all_no.update(r['kitno'])
        badhere = r['tSort_r'].get(8, 0) + r['tSort_r'].get(12, 0) + r['tSort_s'].get(8, 0) + r['tSort_s'].get(12, 0)
        bad += badhere
        print('%-22s %-7d %-7d %-7d 末帧=%d V=%d ' % (r['game'], r['n_kitr'], r['n_kits'], r['n_kitno'],
                                                     r['last_frame'], 1 if r['victory'] else 0) +
              ('<!> 出现 8/12 × %d' % badhere if badhere else ''))
    print()
    print('=== 拉扯目标兵种分布（[KIT-R] 撤退窗口）===')
    print('   %s' % fmt_cnt(all_r))
    print('=== 拉扯目标兵种分布（[KIT-S] 站桩射采样）===')
    print('   %s' % fmt_cnt(all_s))
    print('=== [KIT-NO] 被放弃的敌兵种（应当只有 8 投石车 / 12 战车弓）===')
    print('   %s' % fmt_cnt(all_no))
    print()
    print('合计 KIT-R=%d  KIT-S=%d  KIT-NO=%d' % (tot_r, tot_s, tot_no))
    print('★ 验收① 拉扯仍生效 : KIT-R %s' % ('OK（>0，机制没被禁死）' if tot_r > 0 else '!! KIT-R=0 —— 拉扯被禁死了，检查是否误把所有目标都过滤掉'))
    print('★ 验收② 不拉扯 8/12 : %s' % ('OK（0 次）' if bad == 0 else '!! 出现 %d 次 —— 判据漏改' % bad))
    print('★ 验收③ 过滤真起效 : %s' % ('OK（KIT-NO>0，确实发生过"附近只有射程占优敌而被跳过"）' if tot_no > 0
                                        else '⚠ KIT-NO=0 —— 本批可能压根没遇到战车弓/投石车，②的通过不构成证据'))


def scan(pat):
    paths = sorted(glob.glob(pat))
    if not paths:
        print('no file for', pat); return
    print('=== %s : %d 局（跨批只比"拉扯总量"，旧日志无 tSort 字段）===' % (pat, len(paths)))
    z = [0, 0, 0]
    for p in paths:
        r = parse(p)
        z[0] += r['n_kitr']; z[1] += r['n_kits']; z[2] += r['n_kitno']
    print('  KIT-R 总=%d（%.1f/局）  KIT-S 总=%d（%.1f/局）  KIT-NO 总=%d' %
          (z[0], z[0] / len(paths), z[1], z[1] / len(paths), z[2]))


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'show':
        show(sys.argv[2:])
    elif mode == 'scan':
        for a in sys.argv[2:]:
            scan(a)
            print()
