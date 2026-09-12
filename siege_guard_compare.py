# -*- coding: utf-8 -*-
"""祭司感化武器厂：起手现场对比（sg 批次 = 有起手保护 + 全程可观测；sb/fc/dm/sba = 改前）。

新批次(sg) 可直接解析带字段的日志：
  >> Priest converting Siege Workshop! f=N d=D hp=H nearT=T towers=K path=early|front
  [SIEGE-HOLD f=N] hp=H nearT=T towers=K dS=D
  >> Priest ADVANCE to Siege f=N d=D nearT=T towers=K enemy_cleared
旧批次没有这些字段 ⇒ 用引擎动作日志 `HumanAction:祭司 N 设置转换目标为 攻城武器厂 N` 反推起手时刻，
再统计起手前后窗口内"敌箭塔射击祭司"的次数（代替"起手时塔距"，因为旧日志无塔位）。
"""
import re, sys, os, glob

CONV = re.compile(r'Priest converting Siege Workshop! f=(\d+) d=([\d.]+) hp=([\d.]+) nearT=(-?[\d.]+) towers=(\d+) path=(\w+)')
CONV_OLD = re.compile(r'Priest converting Siege Workshop!(?! f=)')
HOLD = re.compile(r'\[SIEGE-HOLD f=(\d+)\] hp=([\d.]+) nearT=([\d.]+) towers=(\d+) dS=([\d.]+)')
ADV = re.compile(r'Priest ADVANCE to Siege f=(\d+) d=([\d.]+) nearT=(-?[\d.]+) towers=(\d+)')
HUM_ACTION_SIEGE = re.compile(r'HumanAction:祭司 (\d+) 设置转换目标为 攻城武器厂 (\d+)')
TOWER_HIT_PRIEST = re.compile(r'箭塔.*祭司')


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
    d = {'file': os.path.basename(path), 'end': ev[-1][0] if ev else 0,
         'conv': [], 'hold': [], 'adv': [], 'legacy': [], 'vic': 0, 'dead': 0,
         'tower_hit': [fr for fr, m in ev if TOWER_HIT_PRIEST.search(m)]}
    for fr, m in ev:
        g = CONV.search(m)
        if g:
            d['conv'].append((int(g.group(1)), float(g.group(2)), float(g.group(3)),
                              float(g.group(4)), int(g.group(5)), g.group(6)))
            continue
        if CONV_OLD.search(m):
            d['legacy'].append(fr)
        g = HOLD.search(m)
        if g:
            d['hold'].append((int(g.group(1)), float(g.group(2)), float(g.group(3)), int(g.group(4)), float(g.group(5))))
        g = ADV.search(m)
        if g:
            d['adv'].append((int(g.group(1)), float(g.group(2)), float(g.group(3)), int(g.group(4))))
        if 'VICTORY' in m:
            d['vic'] += 1
        if 'DEFEAT: Priest killed' in m:
            d['dead'] += 1
    # 旧口径：HumanAction 起手（取帧号——正则两个捕获组都是 SN，不是帧号）
    d['ha'] = sorted({fr for fr, m in ev for g in [HUM_ACTION_SIEGE.search(m)] if g})
    return d


def main():
    batches = sys.argv[1:] or ['sb', 'sg']
    allrows = []
    for b in batches:
        for i in range(1, 9):
            f = '%s%d.ait' % (b, i)
            if not os.path.exists(f):
                continue
            allrows.append((b, summarize(f)))

    print('%-10s %7s %6s %5s %5s  %s' % ('file', '末帧', '胜负', '起手', 'HOLD', '起手现场 (f / d / hp / nearT / towers / path)'))
    for b, d in allrows:
        res = 'WIN' if d['vic'] else ('DIED' if d['dead'] else 'TIME')
        n = len(d['conv']) or len(d['legacy']) or len(d['ha'])
        fields = []
        for c in d['conv']:
            fields.append('f=%d d=%.1f hp=%.2f nearT=%.1f tw=%d %s' % c)
        print('%-10s %7d %6s %5d %5d  %s' % (d['file'], d['end'], res, n, len(d['hold']), '; '.join(fields) if fields else '-'))
        for h in d['hold']:
            print('        HOLD f=%d hp=%.2f nearT=%.1f tw=%d dS=%.1f' % h)
        for a in d['adv']:
            print('        ADV  f=%d d=%.1f nearT=%.1f tw=%d' % a)

    print()
    for b in batches:
        rows = [d for bb, d in allrows if bb == b]
        if not rows:
            continue
        wins = sum(d['vic'] for d in rows)
        died = sum(1 for d in rows if d['dead'])
        conv = sum(max(len(d['conv']), len(d['legacy']), len(d['ha'])) for d in rows)
        hold = sum(len(d['hold']) for d in rows)
        adv = sum(len(d['adv']) for d in rows)
        print('[%s] 局=%d 胜=%d 祭死=%d 起手=%d HOLD=%d ADV=%d' % (b, len(rows), wins, died, conv, hold, adv))
        cs = [c for d in rows for c in (d['conv'] or [])]
        if cs:
            import statistics
            print('     起手时 nearT: %s' % sorted('%.1f' % c[3] for c in cs))
            print('     起手时 hp   : %s' % sorted('%.2f' % c[2] for c in cs))
            print('     起手时 towers: %s' % sorted(str(c[4]) for c in cs))


if __name__ == '__main__':
    main()
