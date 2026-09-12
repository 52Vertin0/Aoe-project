# -*- coding: utf-8 -*-
"""
敌方"猎杀祭司小队"成员识别探针
判据：对每个敌方单位 SN（flag=1），统计它一共下过多少条攻击令、其中多少指向祭司。
     若某单位"只锁祭司"或"高度偏斜"，则它是专门猎杀者。
用法: python hunt2_probe.py
"""
import io, glob, re, collections, statistics

RE_ATK = re.compile(r'HumanAction:(\S+) (\d+) 设置攻击目标为 (\S+) (\d+)')
RE_WAVE = re.compile(r'ALL WAVES DEFEATED! Counterattack! Frame=(\d+)')
RE_DEAD = re.compile(r'DEFEAT: Priest killed')


def load(tag):
    out = []
    for fp in sorted(glob.glob(tag + '*.ait'),
                     key=lambda x: int(re.findall(r'\d+', x.split('/')[-1])[0])):
        g = int(re.findall(r'\d+', fp.split('/')[-1])[0])
        for l in io.open(fp, encoding='utf-8', errors='replace'):
            p = l.split(' | ')
            if len(p) < 5:
                continue
            try:
                f = int(p[1])
            except Exception:
                continue
            out.append((g, f, p[3].strip(), p[4].strip()))
    return out


def main():
    rows = load('kd')
    # (game, sn) -> Counter(target)
    per = collections.defaultdict(collections.Counter)
    kind = {}
    first = {}
    for g, f, fl, m in rows:
        if fl != '1':
            continue
        mm = RE_ATK.search(m)
        if not mm:
            continue
        key = (g, mm.group(2))
        per[key][mm.group(3)] += 1
        kind[key] = mm.group(1)
        if key not in first or f < first[key]:
            first[key] = f

    print('=' * 104)
    print('A. 每局的"锁祭司单位"明细（只列锁过祭司的单位）')
    print('=' * 104)
    print('%-7s %-11s %9s %8s %9s %6s  %s' %
          ('局', '单位(SN)', '锁祭司', '总令数', '祭司占比', '首令帧', '其它目标分布'))
    per_game_stats = collections.defaultdict(list)
    for (g, sn), c in sorted(per.items(), key=lambda x: (x[0][0], -x[1].get('祭司', 0))):
        p = c.get('祭司', 0)
        if p == 0:
            continue
        tot = sum(c.values())
        others = {k: v for k, v in c.items() if k != '祭司'}
        per_game_stats[g].append((sn, kind[(g, sn)], p, tot))
        print('%-7s %-11s %9d %8d %8s %6d  %s' %
              ('kd%d' % g, '%s#%s' % (kind[(g, sn)], sn), p, tot,
               '%.0f%%' % (100.0 * p / tot), first[(g, sn)],
               dict(sorted(others.items(), key=lambda x: -x[1])[:5]) or '无'))

    print()
    print('=' * 104)
    print('B. ★ 小队规模：每局有几个单位锁过祭司 + 它们是否"专一"')
    print('=' * 104)
    print('%-7s %6s %10s %12s %12s   %s' %
          ('局', '成员数', '锁祭司令数', '专一成员数', '专一占比', '成员(类型#SN:锁祭司令)'))
    szs = []
    for g in sorted(per_game_stats):
        lst = per_game_stats[g]
        szs.append(len(lst))
        pure = [x for x in lst if x[2] / max(1, x[3]) >= 0.9]
        detail = ' '.join('%s#%s:%d/%d' % (x[1], x[0], x[2], x[3]) for x in lst)
        print('%-7s %6d %10d %12d %12s   %s' %
              ('kd%d' % g, len(lst), sum(x[2] for x in lst), len(pure),
               '%d/%d' % (len(pure), len(lst)), detail[:78]))
    print('\n小队规模: 中位 %.0f  均值 %.2f  范围 %d~%d' %
          (statistics.median(szs), sum(szs) / len(szs), min(szs), max(szs)))

    print()
    print('=' * 104)
    print('C. ★ 小队成员的"专一性"汇总（是否只打祭司）')
    print('=' * 104)
    buckets = collections.Counter()
    for (g, sn), c in per.items():
        p = c.get('祭司', 0)
        if p == 0:
            continue
        r = p / sum(c.values())
        if r >= 0.99:
            buckets['100%% 只锁祭司'] += 1
        elif r >= 0.9:
            buckets['90~99%'] += 1
        elif r >= 0.5:
            buckets['50~90%'] += 1
        else:
            buckets['<50% (兼打其它)'] += 1
    for k, v in buckets.most_common():
        print('  %-18s %d 个单位' % (k, v))

    print()
    print('=' * 104)
    print('D. ★ 这些单位是否也攻击我方其它目标？—— 全量目标分布（flag=1，限"锁过祭司的单位"）')
    print('=' * 104)
    hunters = set(k for k, c in per.items() if c.get('祭司', 0) > 0)
    agg = collections.Counter()
    for g, f, fl, m in rows:
        if fl != '1':
            continue
        mm = RE_ATK.search(m)
        if not mm:
            continue
        if (g, mm.group(2)) in hunters:
            agg[mm.group(3)] += 1
    print('  %s' % dict(agg.most_common(20)))

    print()
    print('=' * 104)
    print('E. ★ 猎杀小队的出现是否早于反攻？（首令帧 vs 反攻帧）')
    print('=' * 104)
    RE_WAVE = RE_WAVE
    for g in sorted(per_game_stats):
        txt = io.open('kd%d.ait' % g, encoding='utf-8', errors='replace').read()
        mw = RE_WAVE.search(txt)
        wave = int(mw.group(1)) if mw else 0
        fmin = min(first[(g, sn)] for sn, _, _, _ in per_game_stats[g])
        fmax = max(first[(g, sn)] for sn, _, _, _ in per_game_stats[g])
        dead = 0
        for l in txt.split('\n'):
            p = l.split(' | ')
            if len(p) >= 5 and RE_DEAD.search(p[4]):
                try:
                    dead = int(p[1])
                except Exception:
                    pass
                break
        print('  kd%-3d 小队首令帧 %6d~%-6d  反攻帧 %-7s  死亡帧 %-7s  %s' %
              (g, fmin, fmax, wave or '-', dead or '-',
               '小队早于反攻' if wave and fmin < wave else ('无反攻' if not wave else '晚于反攻')))


if __name__ == '__main__':
    main()
