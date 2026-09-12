# -*- coding: utf-8 -*-
"""
priest_lose_probe.py — 当前版本「会输」的败因结构（2026-09-18，修正版）

⚠ 修正说明：上一版误用 `Prof.Lu` 作为祭司 —— 实测 `Prof.Lu` 是【敌方】单位
  （一局 6 个：91112/91143~91149），我方祭司日志单位名是【祭司】（一局 1 个，flag 0）。
  本版全部改用 `祭司`。

口径：
  结局    VICTORY! Siege Workshop converted / DEFEAT: Priest killed / DEFEAT: Town Center destroyed / none
  机制量  祭司产生帧、祭司死亡帧（可多次=重建）、感化起手帧、转换成功帧
"""
import glob, os, re, statistics, collections

BATCHES = ['gw', 'gx', 'gy', 'gz', 'gh', 'gi']
RE_WIN  = re.compile(r'VICTORY! Siege Workshop converted')
RE_LP   = re.compile(r'DEFEAT: Priest killed')
RE_LT   = re.compile(r'DEFEAT: Town Center destroyed')
RE_CONV = re.compile(r'设置转换目标为\s*攻城武器厂')
RE_CONVED = re.compile(r'攻城武器厂\(编号:?\d+\)被祭司转换')
RE_BORN = re.compile(r'产生了新的祭司\(编号:?(\d+)\)')
RE_DEAD = re.compile(r'祭司\(编号:?(\d+)\)死亡')


def analyze(path):
    end = None; last = 0
    conv = []; conved = []; born = {}; dead = []
    for line in open(path, 'r', encoding='utf-8', errors='replace'):
        p = line.split(' | ', 3)
        if len(p) < 4:
            continue
        try:
            fr = int(p[1])
        except ValueError:
            continue
        last = fr
        m = p[3]
        if RE_WIN.search(m):    end = 'win'; continue
        if RE_LP.search(m):     end = 'lose_priest'; continue
        if RE_LT.search(m):     end = 'lose_tc'; continue
        if RE_CONVED.search(m): conved.append(fr); continue
        if RE_CONV.search(m):   conv.append(fr); continue
        b = RE_BORN.search(m)
        if b: born.setdefault(int(b.group(1)), fr); continue
        d = RE_DEAD.search(m)
        if d: dead.append((int(d.group(1)), fr)); continue
    return dict(file=os.path.basename(path), end=end or 'none', last=last,
                born=born, dead=dead, conv=conv, conved=conved,
                first_born=(min(born.values()) if born else None),
                first_dead=(min(x[1] for x in dead) if dead else None),
                n_dead=len(dead))


def main():
    rows = []
    for b in BATCHES:
        for f in sorted(glob.glob(b + '*.ait'), key=lambda x: (len(x), x)):
            r = analyze(f)
            r['batch'] = b
            rows.append(r)

    print('=' * 104)
    print('批次 × 结局（%d 局，单位 = 我方「祭司」）' % len(rows))
    print('=' * 104)
    print('%-5s %5s %4s %11s %8s %8s %10s %10s %10s' %
          ('批次', '局数', '胜', '祭司被杀', 'TC被毁', '无结局', '祭司死过局', '起手局', '转换成功'))
    for b in BATCHES:
        s = [r for r in rows if r['batch'] == b]
        print('%-5s %5d %4d %11d %8d %8d %10d %10d %10d' % (
            b, len(s),
            sum(1 for r in s if r['end'] == 'win'),
            sum(1 for r in s if r['end'] == 'lose_priest'),
            sum(1 for r in s if r['end'] == 'lose_tc'),
            sum(1 for r in s if r['end'] == 'none'),
            sum(1 for r in s if r['n_dead'] > 0),
            sum(1 for r in s if r['conv']),
            sum(1 for r in s if r['conved'])))

    print()
    print('=' * 104)
    print('全批汇总（%d 局）' % len(rows))
    print('=' * 104)
    for k, v in collections.Counter(r['end'] for r in rows).most_common():
        print('  %-14s %3d 局  %5.1f%%' % (k, v, 100.0 * v / len(rows)))
    n = len(rows)
    print('  ── 祭司在局内死亡过：%d 局 (%.1f%%)' % (sum(1 for r in rows if r['n_dead']), 100.0 * sum(1 for r in rows if r['n_dead']) / n))
    print('  ── 祭司曾起手感化：  %d 局 (%.1f%%)' % (sum(1 for r in rows if r['conv']), 100.0 * sum(1 for r in rows if r['conv']) / n))
    print('  ── 感化转换成功：    %d 局 (%.1f%%)' % (sum(1 for r in rows if r['conved']), 100.0 * sum(1 for r in rows if r['conved']) / n))
    print('  ── 跑满 ≥44500 帧：  %d 局 (%.1f%%)' % (sum(1 for r in rows if r['last'] >= 44500), 100.0 * sum(1 for r in rows if r['last'] >= 44500) / n))

    dd = [r for r in rows if r['first_dead']]
    print()
    print('=' * 104)
    print('★ 祭司首次死亡的时间定位（%d 局）' % len(dd))
    print('=' * 104)
    if dd:
        fr = [r['first_dead'] for r in dd]
        print('  死亡帧：中位 %d (%.1f 分)  均值 %d  min %d (%.1f分)  max %d (%.1f分)' %
              (statistics.median(fr), statistics.median(fr) / 1500.0, statistics.mean(fr),
               min(fr), min(fr) / 1500.0, max(fr), max(fr) / 1500.0))
        print('  相对反攻门槛 33000（22 分）：死在【反攻之前】%d 局 (%.1f%%) ｜ 之后 %d 局' %
              (sum(1 for x in fr if x < 33000), 100.0 * sum(1 for x in fr if x < 33000) / len(fr),
               sum(1 for x in fr if x >= 33000)))
        cb = [r for r in dd if r['conv'] and r['conv'][0] <= r['first_dead']]
        print('  死前【已起手过感化】：%d 局 (%.1f%%)' % (len(cb), 100.0 * len(cb) / len(dd)))
        print('  死前【从未起手】：    %d 局 (%.1f%%)  ← 没走到武器厂' % (len(dd) - len(cb), 100.0 * (len(dd) - len(cb)) / len(dd)))

    print()
    print('=' * 104)
    print('★ 无结局局（跑满 45000 帧 = "推不动"）')
    print('=' * 104)
    nn = [r for r in rows if r['end'] == 'none']
    if nn:
        print('  %d 局：其中起手过 %d 局 (%.1f%%)｜祭司死过 %d 局 (%.1f%%)｜中位末帧 %d (%.1f 分)' %
              (len(nn), sum(1 for r in nn if r['conv']), 100.0 * sum(1 for r in nn if r['conv']) / len(nn),
               sum(1 for r in nn if r['n_dead']), 100.0 * sum(1 for r in nn if r['n_dead']) / len(nn),
               statistics.median(r['last'] for r in nn), statistics.median(r['last'] for r in nn) / 1500.0))

    print()
    print('=' * 104)
    print('★ 胜局 vs 负局/无结局 的机制对照（找"赢的那局有什么不同"）')
    print('=' * 104)
    for label, sel in (('胜局', [r for r in rows if r['end'] == 'win']),
                       ('祭司被杀', [r for r in rows if r['end'] == 'lose_priest']),
                       ('无结局', [r for r in rows if r['end'] == 'none'])):
        if not sel:
            continue
        print('  %-8s n=%-3d 起手率 %5.1f%%  转换成功 %5.1f%%  祭司死过 %5.1f%%  祭司死亡中位帧 %s  末帧中位 %d' % (
            label, len(sel),
            100.0 * sum(1 for r in sel if r['conv']) / len(sel),
            100.0 * sum(1 for r in sel if r['conved']) / len(sel),
            100.0 * sum(1 for r in sel if r['n_dead']) / len(sel),
            ('%d' % statistics.median([r['first_dead'] for r in sel if r['first_dead']])) if any(r['first_dead'] for r in sel) else '-',
            statistics.median(r['last'] for r in sel)))

    print()
    print('★ 逐局明细（末 30 局）')
    print('%-9s %-13s %9s %9s %7s %7s' % ('file', 'end', 'firstDead', 'lastFrame', 'nConv', 'nConved'))
    for r in rows[-30:]:
        print('%-9s %-13s %9s %9d %7d %7d' % (
            r['file'], r['end'], r['first_dead'] if r['first_dead'] else '-', r['last'], len(r['conv']), len(r['conved'])))


if __name__ == '__main__':
    main()
