# -*- coding: utf-8 -*-
"""祭司【移动令来源交替率】与【推进效率】量化 —— 仲裁器改动的直接机制指标。

为什么需要它：胜负要 24 局/臂才敢下结论，但机制量可以立刻判"改动有没有打中病根"。
本工具的判据全部来自 [BEAT] 行（基线就有，无需重跑插桩）：

  ① 来源交替率  flip
     取每个桶的 pm 主导档（f/ca/h/cnt/o 里计数最大者，全 0 记 '-'），
     再看相邻桶之间主导档是否变化。flip = 变化次数 / 相邻桶对数。
     · 极限环（flee⇄heal / ca⇄cnt 交替夺权）⇒ flip 高、主导档在两个值之间来回。
     · 已承诺（仲裁器生效）⇒ 主导档成串持续 ⇒ flip 低。
  ② 停滞率  stall
     相邻桶 pr@ 位移 < 0.5 格的占比（祭司 6 秒只挪不到半格 = 被判据锁住）。
  ③ 推进效率  eff   （仅反攻段，b >= 反攻开始桶）
     净位移 / 逐桶位移之和。1.0 = 一路直走；≈0 = 原地来回。
  ④ 最长同档连跑  runMax  —— 越大越说明"有人守住了话语权"。

用法:  python _arbstat.py "arb1_*_r0_*.ait"
       python _arbstat.py --cmp base0 fix1 arb1     （按 tag 聚合）
"""
import re, sys, glob, os, collections

SRC = ['f', 'ca', 'h', 'cnt', 'o']


def parse(path):
    t = open(path, encoding='utf-8', errors='replace').read()
    d = {'file': os.path.basename(path)}
    m = re.search(r'^(.*?)_(map\d?)_r\d+_\d+\.ait', d['file'])
    d['tag'] = m.group(1) if m else '?'
    d['map'] = m.group(2) if m else '?'
    d['win'] = bool(re.search(r'攻城武器厂\(编号:\d+\)被祭司转换', t)) \
        or 'VICTORY! Siege Workshop converted' in t
    d['pdeath'] = 'DEFEAT: Priest killed' in t
    mc = re.search(r'Counterattack! Frame=(\d+)', t)
    d['caF'] = int(mc.group(1)) if mc else None

    # 逐桶 [BEAT]：b / pr@ / pm
    rows = []
    for l in t.splitlines():
        if '[BEAT f=' not in l:
            continue
        mb = re.search(r'\bb=(\d+)\]', l)
        mp_ = re.search(r'pr@=\(([\d.]+),([\d.]+)\)', l)
        mp = re.search(r'pm f(\d+) ca(\d+) h(\d+) cnt(\d+) o(\d+)', l)
        if not mb:
            continue
        r = {'b': int(mb.group(1)),
             'p': (float(mp_.group(1)), float(mp_.group(2))) if mp_ else None,
             'pm': [int(mp.group(i)) for i in range(1, 6)] if mp else None}
        rows.append(r)
    # 去重（状态跃迁行会有同 b）
    seen = {}
    for r in rows:
        seen[r['b']] = r
    rows = [seen[b] for b in sorted(seen)]

    # ① 主导档 + 交替率
    dom = []
    for r in rows:
        if not r['pm'] or sum(r['pm']) == 0:
            dom.append('-')
        else:
            dom.append(SRC[max(range(5), key=lambda i: r['pm'][i])])
    flips = sum(1 for i in range(1, len(dom)) if dom[i] != dom[i - 1] and dom[i] != '-' and dom[i - 1] != '-')
    pairs = sum(1 for i in range(1, len(dom)) if dom[i] != '-' and dom[i - 1] != '-')
    d['flip'] = (flips / pairs) if pairs else 0.0
    d['dom'] = dom

    # ④ 最长同档连跑
    run = best = 0
    prev = None
    for x in dom:
        if x == '-':
            continue
        run = run + 1 if x == prev else 1
        best = max(best, run)
        prev = x
    d['runMax'] = best

    # ② 停滞率（相邻桶 pr@ 位移）
    pos = [(r['b'], r['p']) for r in rows if r['p']]
    still = tot = 0
    for i in range(1, len(pos)):
        dx = pos[i][1][0] - pos[i - 1][1][0]
        dy = pos[i][1][1] - pos[i - 1][1][1]
        tot += 1
        if (dx * dx + dy * dy) ** 0.5 < 0.5:
            still += 1
    d['stall'] = (still / tot) if tot else 0.0

    # ③ 反攻段推进效率
    caB = None
    if d['caF'] is not None:
        caB = d['caF'] // 150
    seg = [(b, p) for b, p in pos if caB is None or b >= caB]
    if len(seg) >= 3:
        net = ((seg[-1][1][0] - seg[0][1][0]) ** 2 + (seg[-1][1][1] - seg[0][1][1]) ** 2) ** 0.5
        path = 0.0
        for i in range(1, len(seg)):
            path += ((seg[i][1][0] - seg[i - 1][1][0]) ** 2 + (seg[i][1][1] - seg[i - 1][1][1]) ** 2) ** 0.5
        d['eff'] = (net / path) if path > 0.01 else 0.0
    else:
        d['eff'] = None
    return d


def main():
    files = []
    tags = []
    if '--cmp' in sys.argv:
        tags = sys.argv[sys.argv.index('--cmp') + 1:]
        for tg in tags:
            files += sorted(glob.glob(tg + '_*_r0_*.ait'))
    else:
        for a in sys.argv[1:]:
            if not a.startswith('--'):
                files += sorted(glob.glob(a))
    if not files:
        print('no files'); return
    rows = [parse(f) for f in files]

    print('%-30s %-5s %-6s %-7s %-7s %-8s %-7s %s' % (
        'file', 'map', '结果', 'flip', 'stall', 'runMax', 'eff', '主导档序列(截尾24桶)'))
    for d in rows:
        res = '胜' if d['win'] else ('祭死' if d['pdeath'] else '未结算')
        print('%-30s %-5s %-6s %-7.2f %-7.2f %-8d %-7s %s' % (
            d['file'][:30], d['map'], res, d['flip'], d['stall'], d['runMax'],
            ('%.2f' % d['eff']) if d['eff'] is not None else '—',
            ''.join(x if x != '-' else '.' for x in d['dom'][-24:])))

    print()
    agg = collections.defaultdict(lambda: {'n': 0, 'w': 0, 'flip': 0.0, 'stall': 0.0, 'run': 0, 'eff': 0.0, 'effn': 0})
    for d in rows:
        for key in [(d['tag'], 'ALL'), (d['tag'], d['map'])]:
            a = agg[key]
            a['n'] += 1
            a['w'] += 1 if d['win'] else 0
            a['flip'] += d['flip']; a['stall'] += d['stall']; a['run'] += d['runMax']
            if d['eff'] is not None:
                a['eff'] += d['eff']; a['effn'] += 1
    print('=== 按 tag / 图聚合 ===')
    print('%-8s %-6s %4s %6s %7s %7s %7s %7s' % ('tag', 'map', 'n', '胜率', 'flip', 'stall', 'runMax', 'eff'))
    for key in sorted(agg):
        a = agg[key]
        print('%-8s %-6s %4d %5.0f%% %7.2f %7.2f %7.1f %7s' % (
            key[0], key[1], a['n'], 100.0 * a['w'] / a['n'],
            a['flip'] / a['n'], a['stall'] / a['n'], a['run'] / a['n'],
            ('%.2f' % (a['eff'] / a['effn'])) if a['effn'] else '—'))


if __name__ == '__main__':
    main()
