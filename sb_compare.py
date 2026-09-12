# -*- coding: utf-8 -*-
"""sb 批次（卡死脱困）对照 dm 批次（无脱困）。
输出：①逐局胜负/祭司死/末帧 ②移动令诊断（总量、唯一落点率、最长同坐标停滞）
"""
import re, os, collections, sys

RE_MOVE = re.compile(r'HumanMove[:：]\s*(\S+)\s+(\d+)\s+移动至\s*\(([\d.]+),([\d.]+)\)')
BATCHES = sys.argv[1:] or ['dm', 'sb']


def tail(p):
    fr = 0
    for line in open(p, encoding='utf-8', errors='replace'):
        t = line.rstrip('\n').split('|')
        if len(t) >= 5 and t[1].strip().isdigit():
            fr = int(t[1])
    return fr


def result(p):
    v = d = w = False
    for line in open(p, encoding='utf-8', errors='replace'):
        if 'VICTORY! Siege Workshop converted' in line: v = True
        if 'DEFEAT:' in line or 'DEFEAT：' in line: d = True
        if 'ALL WAVES DEFEATED' in line: w = True
    return v, d, w


def moves(p):
    tot = 0
    per = collections.defaultdict(list)
    for line in open(p, encoding='utf-8', errors='replace'):
        t = line.rstrip('\n').split('|')
        if len(t) < 5 or not t[1].strip().isdigit():
            continue
        m = RE_MOVE.search(t[4])
        if not m:
            continue
        tot += 1
        per[m.group(1) + '#' + m.group(2)].append((int(t[1]), m.group(3), m.group(4)))
    uniq = set(); worst = ('-', 0, 0); stall = 0
    for sn, seq in per.items():
        c = collections.Counter((a, b) for _, a, b in seq)
        (bx, by), bn = c.most_common(1)[0]
        if bn > worst[1]: worst = (sn, bn, len(seq))
        last = None
        for fr, x, y in seq:
            if last and last[1] == x and last[2] == y and fr - last[0] >= 300:
                stall += 1
            last = (fr, x, y)
        uniq |= set((a, b) for _, a, b in seq)
    return tot, len(uniq), worst, stall, len(per)


rows = {}
for b in BATCHES:
    for i in range(1, 9):
        p = '%s%d.ait' % (b, i)
        if not os.path.exists(p) or os.path.getsize(p) < 10000:
            continue
        v, d, w = result(p)
        tag = 'VICTORY' if v else ('DEFEAT' if d else ('WAVES-ONLY' if w else 'TIMEOUT/OPEN'))
        fr = tail(p)
        tot, u, worst, stall, nu = moves(p)
        rows['%s%d' % (b, i)] = (tag, fr, tot, u, worst, stall, nu)

print('%-6s %-12s %8s %8s %9s %8s %14s %6s' % ('局', '结局', '末帧', 'Move数', '唯一落点', '唯一率', '最重复(单位:次/条)', '长停滞'))
for k in sorted(rows, key=lambda s: (re.sub(r'\d+$', '', s), int(re.search(r'\d+$', s).group()))):
    tag, fr, tot, u, worst, stall, nu = rows[k]
    print('%-6s %-12s %8d %8d %9d %7.1f%% %14s %6d'
          % (k, tag, fr, tot, u, 100.0 * u / max(tot, 1), '%s:%d/%d' % worst, stall))

print('\n--- 汇总')
for b in BATCHES:
    ks = [k for k in rows if re.fullmatch(b + r'\d+', k)]
    if not ks: continue
    win = sum(1 for k in ks if rows[k][0] == 'VICTORY')
    dead = sum(1 for k in ks if rows[k][0] == 'DEFEAT')
    mt = sum(rows[k][2] for k in ks); fr = sum(rows[k][1] for k in ks)
    print('%-4s 局=%d 胜=%d 祭死=%d   Move/千帧=%.1f  长停滞合计=%d'
          % (b, len(ks), win, dead, 1000.0 * mt / max(fr, 1), sum(rows[k][5] for k in ks)))
