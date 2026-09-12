# -*- coding: utf-8 -*-
"""
祭司感化「投石车」漏斗探针  (2026-09-20)

不依赖坐标（坐标反推经自检只有 12.5% 命中，已弃用），改用两个引擎事实：
  ① 「被感化」的判据 = 该敌方投石车之后开始收到 **flag=0**（我方 AI）的指令
     —— `HumanAction`/`HumanMove` 的 flag = 指令来源阵营（铁律 51）。
  ② 「被我们打死」的判据 = `投石车(编号:SN)死亡` 且该 SN 从未收到 flag=0。

对每个敌方投石车实例（spawn flag=1 + 名称 投石车）分三类：接管 / 阵亡未接管 / 存活未碰。

用法： python priest_stone_funnel.py [前缀...]
"""
import re, glob, sys, collections

RE_CONV = re.compile(r'HumanAction:祭司\s+(\d+)\s+设置转换目标为\s+(\S+)\s+(\d+)')
RE_SPAWN = re.compile(r'产生了新的(\S+)\(编号:?(\d+)\)')
RE_OWN = re.compile(r'Human(?:Action|Move):投石车\s+(\d+)\s+')
RE_DEATH = re.compile(r'(\S+)\(编号:?(\d+)\)死亡')
RE_ROSTER = re.compile(r'产生了新的(\S+)\(编号:?(\d+)\)')


def main():
    pats = sys.argv[1:] or ['']
    files = sorted({f for p in pats for f in glob.glob(p + '*.ait')})
    games = 0
    cls = collections.Counter()            # 三类结局
    conv_per_game = collections.Counter()  # 每局感化投石车令数分布
    roster = collections.Counter()         # 敌方单位构成（按局去重）
    ord_mix = collections.Counter()        # 感化令目标构成
    games_take = 0
    for f in files:
        games += 1
        stone, conv, flag0, died = set(), collections.defaultdict(list), {}, {}
        seen_units = set()
        n_conv = 0
        for ln in open(f, encoding='utf-8', errors='replace'):
            p = ln.split(' | ', 3)
            if len(p) < 4:
                continue
            try:
                fr = int(p[1])
            except ValueError:
                continue
            h = p[3].split(' | ', 1)
            fl = h[0].strip()
            m = h[1].strip() if len(h) > 1 else ''
            ms = RE_SPAWN.search(m)
            if ms and fl == '1':
                sn, nm = int(ms.group(2)), ms.group(1)
                if sn not in seen_units:
                    seen_units.add(sn)
                    roster[nm] += 1
                if nm == '投石车':
                    stone.add(sn)
            mc = RE_CONV.match(m)
            if mc:
                ord_mix[mc.group(2)] += 1
                if mc.group(2) == '投石车':
                    conv[int(mc.group(3))].append(fr)
                    n_conv += 1
            mo = RE_OWN.match(m)
            if mo:
                sn = int(mo.group(1))
                if fl == '0' and sn not in flag0:
                    flag0[sn] = fr
            md = RE_DEATH.match(m)
            if md:
                died.setdefault(int(md.group(2)), fr)
        conv_per_game[n_conv] += 1
        took = 0
        for sn in stone:
            if sn in flag0:
                cls['① 被我方接管'] += 1
                took += 1
            elif sn in died:
                cls['② 阵亡但从未接管（被我们打死）'] += 1
            else:
                cls['③ 存活到局末、从未碰过'] += 1
            if sn in conv and sn not in flag0:
                cls['  ②中：祭司曾指定、但没转成'] += 1
        if took:
            games_take += 1
    print('局数 %d' % games)
    print('敌方投石车实例结局：')
    for k, v in sorted(cls.items()):
        print('   %-30s %d' % (k, v))
    tot = sum(v for k, v in cls.items() if k[0] in '①②③')
    print('   合计 %d  （%s）' % (tot, '；'.join(
        '%s=%.1f%%' % (k[0], 100.0 * v / max(1, tot)) for k, v in sorted(cls.items()) if k[0] in '①②③')))
    print('至少接管 1 个投石车的局数 %d/%d = %.1f%%' % (games_take, games, 100.0 * games_take / games))
    print('每局「感化投石车」令数分布：', {k: conv_per_game[k] for k in sorted(conv_per_game)})
    print()
    print('敌方单位构成（每局去重，%d 局合计）：' % games)
    for k, v in roster.most_common():
        print('   %-10s %5d  (%.2f/局)' % (k, v, v / games))
    print()
    print('感化令目标构成：')
    tt = sum(ord_mix.values())
    for k, v in ord_mix.most_common():
        print('   %-10s %5d  (%.1f%%；敌方占比 %.1f%% ⇒ 表示度 %.2f)'
              % (k, v, 100.0 * v / tt, 100.0 * roster[k] / max(1, sum(roster.values())),
                 (v / tt) / max(1e-9, roster[k] / max(1, sum(roster.values())))))


if __name__ == '__main__':
    main()
