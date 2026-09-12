# -*- coding: utf-8 -*-
"""诊断：dm（直达）比 fc（步进/绕路）HumanMove 多 3 倍 —— 是"卡住反复发同一点"还是"正常多发令"？
判据：唯一落点率、单一坐标最高重复次数、以及"重复坐标是否伴随长时间不位移"。
"""
import re, os, collections

RE_MOVE = re.compile(r'HumanMove[:：]\s*(\S+)\s+(\d+)\s+移动至\s*\(([\d.]+),([\d.]+)\)')


def one(path):
    tot = 0
    per_unit = collections.defaultdict(list)     # sn -> [(frame, x, y)]
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) < 5:
            continue
        fs = p[1].strip()
        if not fs.isdigit():
            continue
        m = RE_MOVE.search(p[4])
        if not m:
            continue
        tot += 1
        per_unit[m.group(1) + '#' + m.group(2)].append((int(fs), m.group(3), m.group(4)))
    uniq = set()
    worst = ('-', 0, 0)
    stuckruns = 0
    for sn, seq in per_unit.items():
        c = collections.Counter((a, b) for _, a, b in seq)
        (bx, by), bn = c.most_common(1)[0]
        if bn > worst[1]:
            worst = (sn, bn, len(seq))
        for (fx, fy), _ in ((k, v) for k, v in c.items()):
            pass
        # 连续同坐标的最长跨度（帧差）
        last = None
        for fr, x, y in seq:
            if last and last[1] == x and last[2] == y and fr - last[0] >= 300:
                stuckruns += 1
            last = (fr, x, y)
        uniq |= set((a, b) for _, a, b in seq)
    return tot, len(uniq), worst, stuckruns, len(per_unit)


print('%-8s %7s %7s %8s %9s %12s %8s' % ('局', 'Move总数', '唯一落点', '唯一率', '单位数', '最重复(单位:次/条)', '长停滞'))
for b in ('fc', 'dm'):
    print('--- %s' % b)
    for i in range(1, 9):
        p = '%s%d.ait' % (b, i)
        if not os.path.exists(p) or os.path.getsize(p) < 1000:
            continue
        tot, u, worst, sr, nu = one(p)
        print('%-8s %7d %7d %7.1f%% %9d %12s %8d'
              % (p, tot, u, 100.0 * u / max(tot, 1), nu, '%s:%d/%d' % worst, sr))
