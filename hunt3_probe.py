# -*- coding: utf-8 -*-
"""
敌方 AI 目标选择模式探针：集火 or 各自为战？波次时间表？
用法: python hunt3_probe.py
"""
import io, glob, re, collections, statistics

RE_ATK = re.compile(r'HumanAction:(\S+) (\d+) 设置攻击目标为 (\S+) (\d+)')


def load(tag='kd'):
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

    print('=' * 104)
    print('A. ★ 敌方"每次下发"的目标唯一性 —— 集火 or 各自为战')
    print('=' * 104)
    # 对 (game, frame) 聚合敌方所有攻击令，看不同目标数
    fr = collections.defaultdict(set)
    for g, f, fl, m in rows:
        if fl != '1':
            continue
        mm = RE_ATK.search(m)
        if mm:
            fr[(g, f)].add(mm.group(3))
    dist = collections.Counter()
    for k, s in fr.items():
        dist[len(s)] += 1
    tot = sum(dist.values())
    print('  敌方"有攻击令的帧"共 %d 个，每帧的不同目标数分布：' % tot)
    for n in sorted(dist):
        print('    %2d 个目标: %5d 帧 (%.1f%%)' % (n, dist[n], 100.0 * dist[n] / tot))
    print('  ⇒ 中位 %.0f 个目标/帧' % statistics.median(
        [len(s) for s in fr.values()]))

    print()
    print('=' * 104)
    print('B. ★ 敌方攻击令的时间分布（1000 帧 = 40 秒为桶）')
    print('=' * 104)
    buckets = collections.Counter()
    for g, f, fl, m in rows:
        if fl == '1' and RE_ATK.search(m):
            buckets[(f // 1500) * 1500] += 1
    mx = max(buckets.values())
    for b in sorted(buckets):
        n = buckets[b]
        bar = '#' * int(60.0 * n / mx)
        print('  %6d~%-6d (%5.1f~%5.1f 分) %6d  %s' %
              (b, b + 1499, b / 1500.0, (b + 1499) / 1500.0, n, bar))

    print()
    print('=' * 104)
    print('C. ★ 每个"锁定时刻"的批号（首令帧的精确值分布）')
    print('=' * 104)
    fst = collections.Counter()
    for g, f, fl, m in rows:
        if fl != '1':
            continue
        mm = RE_ATK.search(m)
        if mm:
            fst[f] += 1
    print('  敌方攻击令帧号 top24（帧 : 条数）：')
    for f, n in fst.most_common(24):
        print('    %7d (%6.2f 分)  %4d 条' % (f, f / 1500.0, n))

    print()
    print('=' * 104)
    print('D. ★ 祭司被锁 vs 我方其它单位被锁 —— 时序对照（kd1 / kd7）')
    print('=' * 104)
    for g in [1, 7]:
        print('--- kd%d ---' % g)
        seq = []
        for gg, f, fl, m in rows:
            if gg != g or fl != '1':
                continue
            mm = RE_ATK.search(m)
            if mm:
                seq.append((f, mm.group(3), mm.group(1)))
        seq.sort()
        last = None
        runs = []
        for f, t, u in seq:
            if last and last[1] == t and f - last[0] <= 1500:
                runs[-1][2] = f
                runs[-1][3] += 1
            else:
                runs.append([f, t, f, 1])
            last = (f, t)
        print('  目标"波段"（相邻同目标且间隔<=1500 帧合并）：共 %d 段' % len(runs))
        for r in runs[:26]:
            mark = ' <<< 祭司' if r[1] == '祭司' else ''
            print('    %7d~%-7d (%5.1f~%5.1f 分) %-8s %3d 条%s' %
                  (r[0], r[2], r[0] / 1500.0, r[2] / 1500.0, r[1], r[3], mark))


if __name__ == '__main__':
    main()
