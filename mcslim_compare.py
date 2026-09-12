# -*- coding: utf-8 -*-
"""mcslim 批次 vs sb 批次 · 行为对拍（重构必须"不改行为"）。

对拍两类指标：
  A. 结构量（抗噪）：HumanMove / HumanAction 的【每千帧】发生率；各日志标签的出现次数。
  B. 决策点：结局(WIN/DIED/TIME)、祭司起手次数与现场、[SIEGE-HOLD]、[KIT-R]、[KIT-S]、[TOWER-TGT]。
⚠ 铁律 25：8 局无胜负判定力 —— 这里只看"机制指标是否同级"，胜负仅作参考。
"""
import re, os, sys

CONV = re.compile(r'Priest converting Siege Workshop! f=(\d+) d=([\d.]+) hp=([\d.]+) nearT=(-?[\d.]+) towers=(\d+) path=(\w+)')
HOLD = re.compile(r'\[SIEGE-HOLD f=(\d+)\]')
ADV = re.compile(r'Priest ADVANCE to Siege f=(\d+)')
HA_SIEGE = re.compile(r'HumanAction:祭司 \d+ 设置转换目标为 攻城武器厂 \d+')

LABELS = ['[KIT-R', '[KIT-S', '[TOWER-TGT', '[PRST-REAR', '[LC-DBG', '[SIEGE-HOLD',
          'Priest converting Siege Workshop', 'Priest ADVANCE to Siege', 'Enemy Siege Workshop found',
          'Enemy base scouted', 'Force COUNTERATTACK']


def scan(path):
    ev = []
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) < 5:
            continue
        try:
            fr = int(p[1])
        except ValueError:
            continue
        ev.append((fr, p[4].strip()))
    return ev


def summarize(path):
    ev = scan(path)
    end = ev[-1][0] if ev else 0
    d = dict(file=os.path.basename(path), end=end, win=0, died=0, tcdead=0,
             move=0, action=0, conv=[], hold=0, adv=0, labels={k: 0 for k in LABELS})
    for fr, m in ev:
        if 'HumanMove' in m:
            d['move'] += 1
        if 'HumanAction' in m:
            d['action'] += 1
        if 'VICTORY' in m:
            d['win'] += 1
        if 'DEFEAT: Priest killed' in m:
            d['died'] += 1
        if 'DEFEAT: Town Center destroyed' in m:
            d['tcdead'] += 1
        g = CONV.search(m)
        if g:
            d['conv'].append((int(g.group(1)), float(g.group(2)), float(g.group(3)), float(g.group(4)), int(g.group(5)), g.group(6)))
        if HOLD.search(m):
            d['hold'] += 1
        if ADV.search(m):
            d['adv'] += 1
        for k in LABELS:
            if k in m:
                d['labels'][k] += 1
    # 起手次数：优先用带字段的 conv 日志；否则用引擎动作日志【按 lockout=400 帧聚类】去重
    #   （逐帧重发的 HumanAction 会刷屏，直接计数会把 1 次起手算成上百次）。
    ha_frames = sorted({fr for fr, m in ev if HA_SIEGE.search(m)})
    clusters, last = [], -10 ** 9
    for fr in ha_frames:
        if fr - last > 400:
            clusters.append(fr)
        last = fr
    d['start'] = len(d['conv']) or len(clusters)
    return d


def batch(prefix, n=8):
    return [summarize('%s%d.ait' % (prefix, i)) for i in range(1, n + 1) if os.path.exists('%s%d.ait' % (prefix, i))]


def line(d):
    res = 'WIN' if d['win'] else ('DIED' if d['died'] else ('TCDEAD' if d['tcdead'] else 'TIME'))
    kf = d['end'] / 1000.0
    return '%-8s %6d %-6s move=%5d(%5.1f/kf) act=%5d(%5.1f/kf)' % (
        d['file'], d['end'], res, d['move'], d['move'] / kf, d['action'], d['action'] / kf)


def main():
    batches = sys.argv[1:] or ['sb', 'mc']
    data = {}
    for b in batches:
        data[b] = batch(b)
        print('== %s ==' % b)
        for d in data[b]:
            print('  ' + line(d))
            for c in d['conv']:
                print('      起手 f=%d d=%.1f hp=%.2f nearT=%.1f tw=%d %s' % c)
        lbl = {k: sum(d['labels'][k] for d in data[b]) for k in LABELS}
        print('  标签合计: ' + '  '.join('%s=%d' % (k, v) for k, v in lbl.items() if v))
        print()
    print('== 汇总 ==')
    print('%-6s %4s %4s %5s %5s %5s %6s %7s %7s %6s' % ('批', '局', '胜', '祭死局', '起手', 'HOLD', 'ADV', 'move/kf', 'act/kf', 'KIT-R'))
    for b in batches:
        rows = data[b]
        kf = sum(r['end'] for r in rows) / 1000.0
        print('%-6s %4d %4d %5d %5d %5d %6d %7.1f %7.1f %6d' % (
            b, len(rows), sum(r['win'] for r in rows), sum(1 for r in rows if r['died']),
            sum(r['start'] for r in rows), sum(r['hold'] for r in rows), sum(r['adv'] for r in rows),
            sum(r['move'] for r in rows) / kf, sum(r['action'] for r in rows) / kf,
            sum(r['labels']['[KIT-R'] for r in rows)))


if __name__ == '__main__':
    main()
