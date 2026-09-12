#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
塔闸修复验证（2026-09-17）
  问题：祭司在「敌军全灭 + 箭塔全拆」时不感化敌方武器厂。
  根因：clearOk 的保险项 enemyBldSeenN >= 2，而终局(塔拆光)时列表只剩武器厂 ⇒ seen=1 ⇒ 永久拦死。

本脚本按三组口径统计：
  A 机制量【闸是否放行】：起手次数（分路径）、[SIEGE-WAIT] 被拦样本的 towers/seen/alive
  B 结果量【胜负】：VICTORY / DEFEAT / 无结局
  C 健康度：末日帧、落成建筑、崩溃

用法: python towergate_probe.py tg1.ait tg2.ait ...
"""
import re
import sys
import glob
import os

SIEGE_WAIT = re.compile(
    r'\[SIEGE-WAIT f=(\d+)\] hp=([\d.]+) towers=(\d+) seen=(\d+)'
    r'(?: clearOk=(\d+))?(?: alive=(\d+))? dS=([\d.-]+)')
CONVERT = re.compile(r'>> Priest converting Siege Workshop! f=(\d+) d=([\d.-]+) hp=([\d.]+)'
                     r' nearT=([\d.-]+) towers=(\d+) path=(\w+)')
ADVANCE = re.compile(r'>> Priest ADVANCE to Siege f=(\d+) d=([\d.-]+)')
HOLD = re.compile(r'\[SIEGE-HOLD f=(\d+)\]')
VICTORY = 'VICTORY! Siege Workshop converted'
DEFEAT_PRIEST = 'DEFEAT: Priest killed'
DEFEAT_TC = 'DEFEAT: Town Center destroyed'
BUILT = '建造完毕'


def frame_of(line):
    m = re.search(r'\|\s*(\d+)\s*\|', line)
    return int(m.group(1)) if m else None


def analyse(fn):
    d = dict(file=fn, conv=[], wait=[], adv=0, hold=0, vic=0, dp=0, dt=0,
             built=0, last_frame=0, lines=0)
    try:
        lines = open(fn, encoding='utf-8', errors='replace').read().split('\n')
    except FileNotFoundError:
        return None
    d['lines'] = len(lines)
    for line in lines:
        if not line.strip():
            continue
        fr = frame_of(line)
        if fr:
            d['last_frame'] = max(d['last_frame'], fr)
        m = CONVERT.search(line)
        if m:
            d['conv'].append(dict(f=int(m.group(1)), dist=float(m.group(2)),
                                  hp=float(m.group(3)), nearT=float(m.group(4)),
                                  towers=int(m.group(5)), path=m.group(6)))
            continue
        m = SIEGE_WAIT.search(line)
        if m:
            d['wait'].append(dict(f=int(m.group(1)), hp=float(m.group(2)),
                                  towers=int(m.group(3)), seen=int(m.group(4)),
                                  clearOk=m.group(5), alive=m.group(6),
                                  ds=float(m.group(7))))
            continue
        if ADVANCE.search(line):
            d['adv'] += 1
        if HOLD.search(line):
            d['hold'] += 1
        if VICTORY in line:
            d['vic'] += 1
        if DEFEAT_PRIEST in line:
            d['dp'] += 1
        if DEFEAT_TC in line:
            d['dt'] += 1
        if BUILT in line:
            d['built'] += 1
    return d


def main(files):
    if not files:
        files = sorted(glob.glob('tg*.ait'))
    rows = [analyse(f) for f in files]
    rows = [r for r in rows if r]

    print('=' * 100)
    print('A. 闸是否放行（机制量）')
    print('=' * 100)
    print('%-10s %-8s %-26s %-10s %-10s' % ('file', '起手', '起手路径分布', 'WAIT拦截', 'WAIT中towers=0'))
    print('-' * 100)
    for r in rows:
        paths = {}
        for c in r['conv']:
            paths[c['path']] = paths.get(c['path'], 0) + 1
        pstr = ', '.join('%s=%d' % (k, v) for k, v in sorted(paths.items())) or '-'
        z = [w for w in r['wait'] if w['towers'] == 0]
        print('%-10s %-8d %-26s %-10d %-10d' % (r['file'], len(r['conv']), pstr, len(r['wait']), len(z)))

    tot_conv = sum(len(r['conv']) for r in rows)
    print('-' * 100)
    print('合计起手 = %d 次 / %d 局' % (tot_conv, len(rows)))

    # WAIT 样本明细（尤其 towers=0 的——修复前这是被拦的典型）
    print()
    print('--- [SIEGE-WAIT] 中 towers=0 的样本（修复前全部被 seen>=2 拦死）---')
    n = 0
    for r in rows:
        for w in r['wait']:
            if w['towers'] == 0:
                n += 1
                if n <= 20:
                    print('   %-10s f=%-7d hp=%-5.2f towers=0 seen=%s alive=%-5s dS=%.1f'
                          % (r['file'], w['f'], w['hp'], w['seen'], w['alive'] or '?', w['ds']))
    if n == 0:
        print('   （无）')
    else:
        print('   共 %d 条' % n)

    # 起手明细
    print()
    print('--- 起手明细 ---')
    for r in rows:
        for c in r['conv']:
            print('   %-10s f=%-7d d=%-6.1f hp=%-5.2f nearT=%-6.1f towers=%-2d path=%s'
                  % (r['file'], c['f'], c['dist'], c['hp'], c['nearT'], c['towers'], c['path']))

    print()
    print('=' * 100)
    print('B. 结果量（胜负）')
    print('=' * 100)
    print('%-10s %-6s %-6s %-6s %-8s %-10s %-10s %-8s' %
          ('file', 'VICT', 'D-PRST', 'D-TC', '结局', '末日帧', '落成建筑', 'ADV'))
    print('-' * 100)
    for r in rows:
        if r['vic']:
            res = '胜'
        elif r['dp'] or r['dt']:
            res = '负'
        else:
            res = '无'
        print('%-10s %-6d %-6d %-6d %-8s %-10d %-10d %-8d' %
              (r['file'], r['vic'], r['dp'], r['dt'], res,
               r['last_frame'], r['built'], r['adv']))

    print()
    print('=' * 100)
    print('C. 汇总')
    print('=' * 100)
    w = sum(1 for r in rows if r['vic'])
    l = sum(1 for r in rows if r['dp'] or r['dt'])
    print('胜 %d / 负 %d / 无结局 %d（共 %d 局）' % (w, l, len(rows) - w - l, len(rows)))
    print('起手合计 %d 次' % tot_conv)
    z = sum(1 for r in rows for x in r['wait'] if x['towers'] == 0)
    print('仍被拦的 towers=0 样本 %d 条（应接近 0）' % z)


if __name__ == '__main__':
    main(sys.argv[1:])
