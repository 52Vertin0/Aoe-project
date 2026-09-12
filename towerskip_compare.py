# -*- coding: utf-8 -*-
"""towerskip 批次 × 基线批次 · 行为对比（"复合弓兵不打箭塔"必须有机制铁证）。

主指标（机制量，抗噪）：
  remote_tower = [TOWER-TGT] 中 who="复合弓兵/远程" 的次数  → 改后期望归零
  melee_tower  = [TOWER-TGT] 中 who="近战" 的次数          → 应保持（近战照旧拆塔）
  skip         = [TOWER-SKIP] 次数                        → 改后 >0，且字段自证"射程<8"
辅指标：
  结局/祭司起手/HumanMove·HumanAction 千帧率（铁律 25：8 局无胜负判定力，只看机制量是否同级）
"""
import os
import re
import sys

CONV = re.compile(r'Priest converting Siege Workshop! f=(\d+) d=([\d.]+) hp=([\d.]+) nearT=(-?[\d.]+) towers=(\d+) path=(\w+)')
TGT_R = re.compile(r'\[TOWER-TGT f=(\d+)\] (.+?) SN=(\d+) .*?(\d+) \(R<=(\d+)格\)')
TGT_REMOTE = re.compile(r'\[TOWER-TGT f=\d+\] 复合弓兵/远程 ')
TGT_MELEE = re.compile(r'\[TOWER-TGT f=\d+\] 近战 ')
SKIP = re.compile(r'\[TOWER-SKIP f=(\d+)\] (\S+) SN=(\d+) 射程([\d.]+)<塔([\d.]+) → 不打塔 SN=(\d+)')
HA_SIEGE = re.compile(r'HumanAction:祭司 \d+ 设置转换目标为 攻城武器厂 \d+')


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
             move=0, action=0, conv=[], tot=0, remote=0, melee=0, skip=0, skips=[], adv=0, hold=0)
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
        if '[TOWER-TGT' in m:
            d['tot'] += 1
            if TGT_REMOTE.search(m):
                d['remote'] += 1
            elif TGT_MELEE.search(m):
                d['melee'] += 1
        g = SKIP.search(m)
        if g:
            d['skip'] += 1
            d['skips'].append((int(g.group(1)), g.group(2), int(g.group(3)), float(g.group(4)),
                               float(g.group(5)), int(g.group(6))))
        c = CONV.search(m)
        if c:
            d['conv'].append((int(c.group(1)), float(c.group(2)), float(c.group(3)),
                              float(c.group(4)), int(c.group(5)), c.group(6)))
        if '[SIEGE-HOLD' in m:
            d['hold'] += 1
        if 'Priest ADVANCE to Siege' in m:
            d['adv'] += 1
    ha = sorted({fr for fr, m in ev if HA_SIEGE.search(m)})
    clusters, last = [], -10 ** 9
    for fr in ha:
        if fr - last > 400:
            clusters.append(fr)
        last = fr
    d['start'] = len(d['conv']) or len(clusters)
    return d


def batch(prefix, n=8):
    return [summarize('%s%d.ait' % (prefix, i)) for i in range(1, n + 1)
            if os.path.exists('%s%d.ait' % (prefix, i))]


def res_of(d):
    return 'WIN' if d['win'] else ('DIED' if d['died'] else ('TCDEAD' if d['tcdead'] else 'TIME'))


def main():
    batches = sys.argv[1:] or ['mc', 'md', 'tc']
    data = {}
    for b in batches:
        rows = batch(b)
        data[b] = rows
        print('== %s ==' % b)
        for d in rows:
            kf = d['end'] / 1000.0 or 1.0
            print('  %-8s %6d %-6s 打塔 tot=%3d(远程%3d/近战%3d) 跳过=%3d move=%5.1f/kf'
                  % (d['file'], d['end'], res_of(d), d['tot'], d['remote'], d['melee'], d['skip'],
                     d['move'] / kf))
            for c in d['conv']:
                print('       起手 f=%d d=%.1f hp=%.2f nearT=%.1f tw=%d %s' % c)
            for s in d['skips'][:4]:
                print('       SKIP f=%d %s SN=%d 射程%.1f<塔%.1f tgt=%d' % s)
            if len(d['skips']) > 4:
                print('       ... 共 %d 条 TOWER-SKIP' % len(d['skips']))
        print()
    print('== 汇总 ==')
    print('%-6s %4s %4s %4s %5s %5s %7s %7s %8s %8s %8s' %
          ('批', '局', '胜', '祭死', '起手', 'TOWER-TGT', '远程打塔', '近战打塔', 'TOWER-SKIP', 'move/kf', 'act/kf'))
    for b in batches:
        rows = data[b]
        kf = sum(r['end'] for r in rows) / 1000.0 or 1.0
        print('%-6s %4d %4d %4d %5d %5d %7d %8d %9d %8.1f %8.1f' % (
            b, len(rows), sum(r['win'] for r in rows), sum(1 for r in rows if r['died']),
            sum(r['start'] for r in rows), sum(r['tot'] for r in rows), sum(r['remote'] for r in rows),
            sum(r['melee'] for r in rows), sum(r['skip'] for r in rows),
            sum(r['move'] for r in rows) / kf, sum(r['action'] for r in rows) / kf))


if __name__ == '__main__':
    main()
