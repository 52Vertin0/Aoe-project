# -*- coding: utf-8 -*-
"""
losecause_probe.py — 当前版本「会输」的败因结构探针（2026-09-18）

回答：现在这些局到底输在哪一环。
证据口径：引擎动作日志（.ait），不受采样影响。
  结局    VICTORY! Siege Workshop converted / DEFEAT: Priest killed / DEFEAT: Town Center destroyed / 无结局
  机制量  祭司感化起手帧（设置转换目标为 攻城武器厂）
          祭司死亡帧、祭司被塔锁定次数
          末帧（是否跑满 45000）
"""
import glob, os, re, statistics, collections

BATCHES = ['gw', 'gx', 'gy', 'gz', 'gh', 'gi']

RE_WIN  = re.compile(r'VICTORY! Siege Workshop converted')
RE_LP   = re.compile(r'DEFEAT: Priest killed')
RE_LT   = re.compile(r'DEFEAT: Town Center destroyed')
RE_CONV = re.compile(r'设置转换目标为\s*攻城武器厂')
RE_PRIEST_BORN = re.compile(r'产生了新的Prof\.Lu\(编号:?(\d+)\)')
RE_PRIEST_DEAD = re.compile(r'Prof\.Lu\(编号:?(\d+)\)死亡')
RE_TOWER_LOCK  = re.compile(r'HumanAction:箭塔\s+(\d+)\s+设置攻击目标为\s+(Prof\.Lu|[\u4e00-\u9fa5]+)\s+(\d+)')
RE_MOVE_PRIEST = re.compile(r'HumanMove:Prof\.Lu\s+(\d+)\s+移动至\s+\(([\d.]+),([\d.]+)\)')


def analyze(path):
    end = None; last_frame = 0
    conv = []; priest_born = set(); priest_dead = {}; tower_lock = collections.Counter()
    priest_moves = []
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                p = line.split(' | ', 3)
                if len(p) < 4:
                    continue
                try:
                    fr = int(p[1])
                except ValueError:
                    continue
                last_frame = fr
                m = p[3]
                if RE_WIN.search(m):   end = 'win';  continue
                if RE_LP.search(m):    end = 'lose_priest'; continue
                if RE_LT.search(m):    end = 'lose_tc'; continue
                if RE_CONV.search(m):  conv.append(fr); continue
                mb = RE_PRIEST_BORN.search(m)
                if mb: priest_born.add(int(mb.group(1))); continue
                md = RE_PRIEST_DEAD.search(m)
                if md:
                    sn = int(md.group(1))
                    priest_dead.setdefault(sn, fr); continue
                mt = RE_TOWER_LOCK.search(m)
                if mt:
                    tower_lock[int(mt.group(3))] += 1; continue
                mm = RE_MOVE_PRIEST.search(m)
                if mm:
                    priest_moves.append((fr, float(mm.group(2)), float(mm.group(3)))); continue
    except Exception as e:
        return None
    first_dead = min(priest_dead.values()) if priest_dead else None
    return dict(file=os.path.basename(path), end=end or 'none', last=last_frame,
                conv=conv, first_conv=(conv[0] if conv else None), n_conv=len(conv),
                priest_dead=priest_dead, first_dead=first_dead,
                tower_lock=sum(tower_lock.values()), n_priest_born=len(priest_born),
                last_priest_move=(priest_moves[-1] if priest_moves else None))


def main():
    rows = []
    for b in BATCHES:
        for f in sorted(glob.glob(b + '*.ait'), key=lambda x: (len(x), x)):
            r = analyze(f)
            if r:
                r['batch'] = b
                rows.append(r)
    if not rows:
        print('无数据'); return

    print('=' * 96)
    print('批次 × 结局（%d 局）' % len(rows))
    print('=' * 96)
    print('%-6s %5s %8s %10s %8s %8s %10s %10s' %
          ('批次', '局数', '胜', '祭司被杀', 'TC被毁', '无结局', '起手过感化', '中位末帧'))
    for b in BATCHES:
        s = [r for r in rows if r['batch'] == b]
        if not s: continue
        w = sum(1 for r in s if r['end'] == 'win')
        lp = sum(1 for r in s if r['end'] == 'lose_priest')
        lt = sum(1 for r in s if r['end'] == 'lose_tc')
        nn = sum(1 for r in s if r['end'] == 'none')
        cv = sum(1 for r in s if r['n_conv'] > 0)
        print('%-6s %5d %8d %10d %8d %8d %10d %10d' %
              (b, len(s), w, lp, lt, nn, cv, statistics.median(r['last'] for r in s)))

    print()
    print('=' * 96)
    print('全批汇总（%d 局）' % len(rows))
    print('=' * 96)
    tot = collections.Counter(r['end'] for r in rows)
    for k, v in tot.most_common():
        print('  %-14s %3d 局  %5.1f%%' % (k, v, 100.0 * v / len(rows)))
    conv_any = sum(1 for r in rows if r['n_conv'] > 0)
    print('  ── 曾经起手感化：%d 局 (%.1f%%)' % (conv_any, 100.0 * conv_any / len(rows)))
    print('  ── 跑满 45000 帧：%d 局 (%.1f%%)' %
          (sum(1 for r in rows if r['last'] >= 44500), 100.0 * sum(1 for r in rows if r['last'] >= 44500) / len(rows)))

    print()
    print('=' * 96)
    print('★ 祭司之死定位（只取祭司有死亡的局）')
    print('=' * 96)
    dd = [r for r in rows if r['first_dead']]
    print('祭司死亡局数：%d / %d (%.1f%%)' % (len(dd), len(rows), 100.0 * len(dd) / len(rows)))
    if dd:
        fr = [r['first_dead'] for r in dd]
        print('祭司死亡帧：中位 %d (%.1f分)  均值 %d  min %d  max %d' %
              (statistics.median(fr), statistics.median(fr) / 1500.0, statistics.mean(fr), min(fr), max(fr)))
        print('  分布：<33000(反攻前) %d 局｜33000~37000 %d 局｜37000~42000 %d 局｜>42000 %d 局' %
              (sum(1 for x in fr if x < 33000), sum(1 for x in fr if 33000 <= x < 37000),
               sum(1 for x in fr if 37000 <= x < 42000), sum(1 for x in fr if x >= 42000)))
        # 死前是否已起手感化
        conv_before = sum(1 for r in dd if r['first_conv'] and r['first_conv'] <= r['first_dead'])
        print('  死前【已起手感化】: %d 局 (%.1f%%)  ← 起手了但没成功 = 施法期被打死' %
              (conv_before, 100.0 * conv_before / len(dd)))
        print('  死前【从未起手】  : %d 局 (%.1f%%)  ← 根本没走到武器厂' %
              (len(dd) - conv_before, 100.0 * (len(dd) - conv_before) / len(dd)))
        # 起手到死亡的间隔
        gaps = [r['first_dead'] - r['first_conv'] for r in dd if r['first_conv'] and r['first_conv'] <= r['first_dead']]
        if gaps:
            print('  「起手 → 死亡」间隔：中位 %d 帧 (%.1f秒)  min %d  max %d' %
                  (statistics.median(gaps), statistics.median(gaps) / 25.0, min(gaps), max(gaps)))

    print()
    print('=' * 96)
    print('★ 无结局局（跑满时长仍未分胜负 = "推不动"）')
    print('=' * 96)
    nn = [r for r in rows if r['end'] == 'none']
    if nn:
        nc = sum(1 for r in nn if r['n_conv'] > 0)
        print('无结局 %d 局：其中【起手过感化】%d 局 (%.1f%%)｜从未起手 %d 局 (%.1f%%)' %
              (len(nn), nc, 100.0 * nc / len(nn), len(nn) - nc, 100.0 * (len(nn) - nc) / len(nn)))
        print('  中位末帧 %d (%.1f分)' % (statistics.median(r['last'] for r in nn), statistics.median(r['last'] for r in nn) / 1500.0))
        pd = sum(1 for r in nn if r['first_dead'])
        print('  其中祭司在局内死过 %d 局 (%.1f%%)' % (pd, 100.0 * pd / len(nn)))

    print()
    print('=' * 96)
    print('★ 祭司被敌方箭塔锁定（塔把祭司当攻击目标）的频次')
    print('=' * 96)
    tl = [r['tower_lock'] for r in rows]
    print('  有塔锁祭司的局：%d / %d (%.1f%%)' %
          (sum(1 for x in tl if x > 0), len(rows), 100.0 * sum(1 for x in tl if x > 0) / len(rows)))
    print('  锁定次数 中位 %d  均值 %.1f  max %d' % (statistics.median(tl), statistics.mean(tl), max(tl)))
    ddl = [r for r in rows if r['first_dead']]
    if ddl:
        tld = [r['tower_lock'] for r in ddl]
        print('  祭司死亡局里的锁定次数 中位 %d（对照：未死局 中位 %d）' %
              (statistics.median(tld), statistics.median([r['tower_lock'] for r in rows if not r['first_dead']])))


if __name__ == '__main__':
    main()
