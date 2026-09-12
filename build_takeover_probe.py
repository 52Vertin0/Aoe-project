# -*- coding: utf-8 -*-
"""
"交孤儿抢救接手"的真实接手率探针
------------------------------------------------
[BUILDER-HARD] percent>0 的处置写着「仅释放登记(交孤儿抢救接手)」。
本探针核对：这些地基 SN 在硬超时之后，是否真的出现了同 SN 的 [ORPHAN] 补派。
  接手率 = 之后有 ORPHAN 的 SN 数 / 移交 SN 数

用法: python build_takeover_probe.py [前缀...]
"""
import os, re, sys, glob, collections

ROOT = r'C:\new-aoe3.0.7g'
RE_HARD = re.compile(r'\[BUILDER-HARD f=(\d+)\] 建造者SN=(\d+) type=(\d+) 地基SN=(\d+) percent=(\d+) 超时(\d+)帧 → (.*)')
RE_ORPH = re.compile(r'\[ORPHAN f=(\d+)\] 地基SN=(\d+) type=(\d+) percent=(\d+) 补派村民SN=(\d+)(.*)')

TNAME = {0: '房屋', 1: '谷仓', 2: 'TC', 3: '仓库', 4: '农场', 5: '市场',
         6: '箭塔', 7: '兵营', 8: '马厩', 9: '靶场', 10: '码头', 11: '武器厂', 12: '学院'}


def message(line):
    p = line.split(' | ', 3)
    if len(p) < 4:
        return None
    q = p[3].split(' | ', 1)
    return q[1] if len(q) > 1 else q[0]


def main():
    prefixes = sys.argv[1:]
    files = []
    for pat in (prefixes if prefixes else ['*']):
        files += glob.glob(os.path.join(ROOT, pat + '*.ait'))
    files = sorted(set(files))

    tot_hand = 0          # 声明"交孤儿抢救接手"的事件数
    tot_scrap = 0         # "作废另址重建"事件数
    taken = 0             # 之后确有 ORPHAN 的移交事件数
    by_type_hand = collections.Counter()
    by_type_taken = collections.Counter()
    never_files = 0
    per_file_pending = []  # (文件, 移交数, 接手数)

    for f in files:
        if not os.path.exists(f):
            continue
        events = []
        try:
            with open(f, 'r', encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    if '[BUILDER-HARD' in line or '[ORPHAN' in line:
                        m = message(line)
                        if not m:
                            continue
                        if '[BUILDER-HARD' in m:
                            g = RE_HARD.search(m)
                            if g:
                                frame, bsn, typ, dsn, pct = int(g.group(1)), int(g.group(2)), int(
                                    g.group(3)), int(g.group(4)), int(g.group(5))
                                events.append(('H', frame, dsn, typ, pct, g.group(7)))
                        else:
                            g = RE_ORPH.search(m)
                            if g:
                                events.append(('O', int(g.group(1)), int(g.group(2)), int(g.group(3)), 0, ''))
        except Exception as e:
            print('!!', f, e)
            continue

        events.sort(key=lambda e: e[1])
        n_hand = n_scrap = n_taken = 0
        for i, e in enumerate(events):
            if e[0] != 'H':
                continue
            kind, fr, dsn, typ, pct, disp = e
            if '孤儿' in disp:
                n_hand += 1
                by_type_hand[typ] += 1
                # 之后是否有同 SN 的 ORPHAN
                hit = any(ev[0] == 'O' and ev[2] == dsn and ev[1] >= fr for ev in events[i + 1:])
                if hit:
                    n_taken += 1
                    by_type_taken[typ] += 1
            else:
                n_scrap += 1
        tot_hand += n_hand
        tot_scrap += n_scrap
        taken += n_taken
        if n_hand and n_taken == 0:
            never_files += 1
        if n_hand:
            per_file_pending.append((os.path.basename(f), n_hand, n_taken))

    print('=' * 80)
    print('样本局数            %d' % len(files))
    print('硬超时-作废另址重建   %d  (%.2f/局)' % (tot_scrap, tot_scrap / max(1, len(files))))
    print('硬超时-交孤儿接手     %d  (%.2f/局)' % (tot_hand, tot_hand / max(1, len(files))))
    print('  其中确被 ORPHAN 接手 %d  ⇒ 接手率 %.1f%%' % (taken, 100.0 * taken / max(1, tot_hand)))
    print('  只移交、始终无接手   %d' % (tot_hand - taken))
    print('至少有一次移交但零接手的局数: %d / %d' % (never_files, len(files)))
    print('-' * 80)
    print('%-8s %10s %10s %8s' % ('类型', '移交', '接手', '接手率'))
    for t in sorted(by_type_hand, key=lambda x: -by_type_hand[x]):
        h, k = by_type_hand[t], by_type_taken[t]
        print('%-8s %10d %10d %7.0f%%' % (TNAME.get(t, '?%d' % t), h, k, 100.0 * k / h))
    print('-' * 80)
    print('移交最多但零接手的 10 局:')
    zero = [x for x in per_file_pending if x[2] == 0]
    zero.sort(key=lambda x: -x[1])
    for name, h, k in zero[:10]:
        print('   %-16s 移交=%d 接手=0' % (name, h))


if __name__ == '__main__':
    main()
