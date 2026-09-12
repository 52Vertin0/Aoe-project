#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反攻期拉扯指标对比（2026-09-14 pullkite 轮）
口径: 只统计 flag=0（我方 AI 下发的指令）且 frame >= START（反攻窗口）。
输出: 每局一行的 TSV，便于与上一批（ln）对比。
"""
import re, sys, os, glob
from collections import defaultdict

LINE = re.compile(r'^\s*([\d:]+)\s*\|\s*(\d+)\s*\|\s*([\w-]+)\s*\|\s*(-?\d+)\s*\|\s*(.*)$')
HA = re.compile(r'HumanAction:(\S+) (\d+) 设置(?:攻击|转换)目标为 (\S+) (\d+)')
HM = re.compile(r'HumanMove:(\S+) (\d+) 移动至')
KITR = re.compile(r'\[KIT-R .*SN=(\d+) dK=([\d.]+)')
KITS = re.compile(r'\[KIT-S .*SN=(\d+)')
DEAD = re.compile(r'^(\S+)\(编号:(\d+)\)被摧毁')
START = 33000

def one(path):
    st = dict(bow_atk=0, bow_tg=set(), bow_mv=0, bow_sn=set(),
              cat_atk=0, cat_tg=set(), cat_mv=0, cat_sn=set(),
              kitr=0, kits=0, near=0, dkmin=1e9, dkmax=0,
              bow_dead=0, cat_dead=0, win=0, defeat=0, scoutF=0, counterF=0, vicF=0, defF=0,
              stuckMax=0, kitr_frames=[])
    our_units = set()
    dead_units = set()
    for line in open(path, encoding='utf-8', errors='ignore'):
        m = LINE.match(line)
        if not m: continue
        fr = int(m.group(2)); flag = int(m.group(4)); msg = m.group(5).strip()
        low = msg
        if 'Force COUNTERATTACK' in low or 'COUNTERATTACK' in low:
            if st['counterF'] == 0: st['counterF'] = fr
        if 'Enemy Siege Workshop found' in low and st['scoutF'] == 0: st['scoutF'] = fr
        if 'VICTORY' in low and st['vicF'] == 0: st['vicF'] = fr
        # ⚠ 必须用 "DEFEAT:"（带冒号）：`ALL WAVES DEFEATED!` 也含 "DEFEAT" 子串，
        #   用 'DEFEAT' in msg 会把每局都判成失败（本轮踩过，ln 批 8/8 "负" 全是假象）。
        if 'DEFEAT:' in low and st['defF'] == 0: st['defF'] = fr
        d = DEAD.search(low)
        if d: dead_units.add(int(d.group(2)))
        r = KITR.search(low)
        if r:
            st['kitr'] += 1
            dk = float(r.group(2))
            st['dkmin'] = min(st['dkmin'], dk); st['dkmax'] = max(st['dkmax'], dk)
            if dk <= 2.0: st['near'] += 1
            su = re.search(r'stuck=(\d+)', low)
            if su: st['stuckMax'] = max(st['stuckMax'], int(su.group(1)))
            st['kitr_frames'].append(fr)
        if KITS.search(low): st['kits'] += 1
        if fr < START or flag != 0: continue
        a = HA.search(low)
        if a:
            kind, sn, tgt, tsn = a.group(1), int(a.group(2)), a.group(3), int(a.group(4))
            if kind == '复合弓兵':
                st['bow_atk'] += 1; st['bow_tg'].add(tsn); st['bow_sn'].add(sn); our_units.add(sn)
            elif kind == '投石车':
                st['cat_atk'] += 1; st['cat_tg'].add(tsn); st['cat_sn'].add(sn); our_units.add(sn)
        v = HM.search(low)
        if v:
            kind, sn = v.group(1), int(v.group(2))
            if kind == '复合弓兵': st['bow_mv'] += 1
            elif kind == '投石车': st['cat_mv'] += 1
    st['bow_dead'] = len([s for s in st['bow_sn'] if s in dead_units])
    st['cat_dead'] = len([s for s in st['cat_sn'] if s in dead_units])
    fs_ = st['kitr_frames']
    st['episodes'] = (1 + sum(1 for i in range(1, len(fs_)) if fs_[i] - fs_[i - 1] > 90)) if fs_ else 0
    # 胜负按"先出现者"判定：VICTORY 的 DebugText 同局重复 33 次，且 exam 胜利后不停止模拟，
    # 祭司随后仍可能被杀 ⇒ 一局里两个字符串都可能有，不能只看"出现过"。
    st['win'] = 1 if (st['vicF'] > 0 and (st['defF'] == 0 or st['vicF'] <= st['defF'])) else 0
    st['defeat'] = 1 if (st['defF'] > 0 and (st['vicF'] == 0 or st['defF'] < st['vicF'])) else 0
    return st

def main():
    files = sys.argv[1:] or sorted(glob.glob('kt*.ait'))
    hdr = ['game', 'win', 'defeat', 'scoutF', 'bowN', 'bowAtk', 'bowAtk/u', 'bowTg', 'bowTg/u', 'bowMv', 'kits', 'kitr',
           'epi', 'stuckMax', 'near%', 'dkmin', 'dkmax', 'bowDead', 'catN', 'catAtk', 'catAtk/u', 'catTg', 'catTg/u', 'catMv', 'catDead']
    print('\t'.join(hdr))
    tot = defaultdict(float); n = 0
    for f in files:
        if not os.path.exists(f): continue
        s = one(f)
        nb = max(1, len(s['bow_sn'])); nc = max(1, len(s['cat_sn']))
        row = [os.path.basename(f), s['win'], s['defeat'], s['scoutF'], len(s['bow_sn']), s['bow_atk'],
               f"{s['bow_atk']/nb:.1f}", len(s['bow_tg']), f"{len(s['bow_tg'])/nb:.2f}", s['bow_mv'], s['kits'], s['kitr'],
               f"{100.0*s['near']/max(1,s['kitr']):.0f}", f"{s['dkmin']:.1f}", f"{s['dkmax']:.1f}",
               s['bow_dead'], len(s['cat_sn']), s['cat_atk'], f"{s['cat_atk']/nc:.1f}", len(s['cat_tg']),
               f"{len(s['cat_tg'])/nc:.2f}", s['cat_mv'], s['cat_dead']]
        row.insert(12, s['episodes']); row.insert(13, s['stuckMax'])
        print('\t'.join(str(x) for x in row))
        for k in ('win', 'defeat', 'bow_atk', 'bow_mv', 'kitr', 'kits', 'bow_dead', 'cat_atk', 'cat_mv', 'cat_dead'):
            tot[k] += s[k]
        tot['bowTg'] += len(s['bow_tg']); tot['catTg'] += len(s['cat_tg'])
        tot['bowN'] += len(s['bow_sn']); tot['catN'] += len(s['cat_sn'])
        n += 1
    if n:
        print('---- 合计/均值 ----')
        print(f"局数={n} 胜={tot['win']:.0f} 负={tot['defeat']:.0f} | 复合弓: 单位={tot['bowN']:.0f} "
              f"攻击令={tot['bow_atk']:.0f}({tot['bow_atk']/max(1,tot['bowN']):.1f}/单位) "
              f"目标种类={tot['bowTg']:.0f} 移动令={tot['bow_mv']:.0f} KITR={tot['kitr']:.0f} KITS={tot['kits']:.0f} "
              f"阵亡={tot['bow_dead']:.0f}")
        print(f"投石车: 单位={tot['catN']:.0f} 攻击令={tot['cat_atk']:.0f} 目标种类={tot['catTg']:.0f} "
              f"移动令={tot['cat_mv']:.0f} 阵亡={tot['cat_dead']:.0f}")

if __name__ == '__main__':
    main()
