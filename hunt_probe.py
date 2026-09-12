# -*- coding: utf-8 -*-
"""
敌方"猎杀祭司小队"归因探针
--------------------------------------------------
判据全部来自 ait 日志：
  - flag=0 = 我方(player1) AI 的指令 / 我方单位事件
  - flag=1 = 敌方(player2) AI 的指令 / 敌方单位事件
  - 引擎行 "X(编号:N)开始向Y(编号：M)攻击" 是真实交战（red/-1）
用法:
  python hunt_probe.py            # 全批次对比
  python hunt_probe.py kd7        # 单局明细
"""
import io, glob, re, sys, collections, statistics

RE_ATK = re.compile(r'HumanAction:(\S+) (\d+) 设置攻击目标为 (\S+) (\d+)')
RE_NEW = re.compile(r'产生了新的(\S+?)\(编号:(\d+)\)')
RE_ENG = re.compile(r'(\S+?)\(编号:(\d+)\)开始向(\S+?)\(编号：(\d+)\)攻击')
TAGS = ['gi', 'kb', 'kc', 'kd']


def split_line(l):
    """返回 (frame, color, flag, msg) 或 None"""
    p = l.split(' | ')
    if len(p) < 5:
        return None
    try:
        f = int(p[1])
    except Exception:
        return None
    return f, p[2].strip(), p[3].strip(), p[4].strip()


def load(tag):
    """返回 list of (game, frame, flag, msg)"""
    out = []
    for fp in sorted(glob.glob(tag + '*.ait'),
                     key=lambda x: int(re.findall(r'\d+', x.split('/')[-1])[0])):
        g = re.findall(r'\d+', fp.split('/')[-1])[0]
        for l in io.open(fp, encoding='utf-8', errors='replace'):
            r = split_line(l)
            if r:
                out.append((g,) + r)
    return out


def main():
    if len(sys.argv) > 1:
        one(sys.argv[1])
        return
    print('=' * 100)
    print('A. 我方(flag=0)单位名册 vs 敌方(flag=1)攻击令密度')
    print('=' * 100)
    def row(a, b, c, d, e):
        return '%-4s %-14s %7s %8s %10s' % (a, b, c, d, e)
    hdr = ('批', '目标', '出产数', '被锁令', '令/单位')
    for tag in TAGS:
        rows = load(tag)
        # 我方单位产出（flag=0 的 "产生了新的X"）
        made = collections.Counter()
        for g, f, c, fl, m in rows:
            if fl == '0':
                mm = RE_NEW.search(m)
                if mm:
                    made[mm.group(1)] += 1
        # 敌方对该目标的攻击令（flag=1 的 HumanAction）
        hit = collections.Counter()
        for g, f, c, fl, m in rows:
            if fl == '1':
                mm = RE_ATK.search(m)
                if mm:
                    hit[mm.group(3)] += 1
        print('\n--- %s ---' % tag.upper())
        print(row(*hdr))
        for name, n in made.most_common(14):
            h = hit.get(name, 0)
            dens = h / n if n else 0
            star = '  <<<' if name == '祭司' else ''
            print(row(tag, name, n, h, '%.1f' % dens) + star)
        # 被锁但不算我方"出产"的（建筑）
        for name in ['箭塔', '农场', '谷仓', '房屋', '市镇中心', '兵营']:
            if hit.get(name):
                print(row(tag, name + '(建筑)', '-', hit[name], '-'))

    print()
    print('=' * 100)
    print('B. ★ 同帧并发锁定祭司 —— “小队”规模分布')
    print('=' * 100)
    print('%-4s %8s %8s %8s %8s %8s %6s   %s' %
          ('批', '锁定帧', '去重令', '涉及局', '峰值/帧', '并发>=2', '中位', '并发规模分布'))
    for tag in TAGS:
        rows = load(tag)
        pergame = collections.defaultdict(lambda: collections.defaultdict(set))
        for g, f, c, fl, m in rows:
            if fl == '1':
                mm = RE_ATK.search(m)
                if mm and mm.group(3) == '祭司':
                    pergame[g][f].add(mm.group(2))   # 同帧去重（同单位重复下令）
        peak = 0; ge2 = 0; conc = []
        for g, d in pergame.items():
            for f, s in d.items():
                n = len(s)
                conc.append(n)
                peak = max(peak, n)
                if n >= 2: ge2 += 1
        dist = collections.Counter(conc)
        med = statistics.median(conc) if conc else 0
        nframes = sum(len(d) for d in pergame.values())
        ncmds = sum(len(s) for d in pergame.values() for s in d.values())
        print('%-4s %8d %8d %8d %8d %8d %6.0f   %s' %
              (tag, nframes, ncmds, len(pergame), peak, ge2, med,
               dict(sorted(dist.items()))))

    print()
    print('=' * 100)
    print('C. 猎杀小队的单位构成（谁在锁祭司）')
    print('=' * 100)
    for tag in ['kd']:
        rows = load(tag)
        src = collections.Counter()
        for g, f, c, fl, m in rows:
            if fl == '1':
                mm = RE_ATK.search(m)
                if mm and mm.group(3) == '祭司':
                    src[mm.group(1)] += 1
        print('%-4s 下令单位类型: %s' % (tag, dict(src.most_common())))
        # 唯一 SN 数
        sns = set()
        for g, f, c, fl, m in rows:
            if fl == '1':
                mm = RE_ATK.search(m)
                if mm and mm.group(3) == '祭司':
                    sns.add(mm.group(2))
        print('     不同单位 SN 数 = %d' % len(sns))

    print()
    print('=' * 100)
    print('D. 逐局：祭司被锁时间线 vs 反攻 vs 死亡')
    print('=' * 100)
    RE_WAVE = re.compile(r'ALL WAVES DEFEATED! Counterattack! Frame=(\d+)')
    RE_DEAD = re.compile(r'DEFEAT: Priest killed')
    print('%-7s %8s %8s %8s %8s %8s %10s %8s' %
          ('局', '首锁帧', '首锁=分', '反攻帧', '死亡帧', '死亡=分', '锁祭司令数', '结局含胜'))
    rows_kd = load('kd')
    bygame = collections.defaultdict(list)
    for g, f, c, fl, m in rows_kd:
        bygame[g].append((f, fl, m))
    for g in sorted(bygame, key=lambda x: int(x)):
        rows = bygame[g]
        txt = io.open('kd%s.ait' % g, encoding='utf-8', errors='replace').read()
        locks = []
        for f, fl, m in rows:
            if fl == '1':
                mm = RE_ATK.search(m)
                if mm and mm.group(3) == '祭司':
                    locks.append(f)
        mw = RE_WAVE.search(txt)
        wave = int(mw.group(1)) if mw else 0
        dead = 0
        for l in txt.split('\n'):
            r = split_line(l)
            if r and RE_DEAD.search(r[3]):
                dead = r[0]; break
        first = min(locks) if locks else 0
        print('%-7s %8s %8s %8s %8s %8s %10d %8s' %
              ('kd' + g, first or '-', ('%.1f' % (first / 1500.0)) if first else '-',
               wave or '-', dead or '-', ('%.1f' % (dead / 1500.0)) if dead else '-',
               len(locks), 'Y' if 'VICTORY' in txt else '-'))


def one(g):
    """单局明细"""
    rows = [(f, fl, m) for (gg, f, c, fl, m) in load(g) if gg == g.replace('kd', '')]
    locks = collections.defaultdict(set)
    for f, fl, m in rows:
        if fl == '1':
            mm = RE_ATK.search(m)
            if mm and mm.group(3) == '祭司':
                locks[f].add((mm.group(1), mm.group(2)))
    print('=== %s 锁祭司的帧（按帧聚合）共 %d 帧 ===' % (g, len(locks)))
    for f in sorted(locks)[:60]:
        print('%7d (%6.1f 分)  %d 个单位: %s' %
              (f, f / 1500.0, len(locks[f]),
               [x[0] + '#' + x[1] for x in sorted(locks[f])][:8]))


if __name__ == '__main__':
    main()
