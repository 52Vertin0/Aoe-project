# -*- coding: utf-8 -*-
"""
祭司"感化投石车"可行性探针  (2026-09-20)

口径（铁律 2）：
  行 = "hh:mm:ss | frame | color | flag | message"  =>  split(' | ',3) 后
     p[1] = frame   p[2] = color   p[3] = "flag | message"
  ⇒ 必须再 split(' | ',1) 才能拿到 message；直接对 p[3] 做正则会全数漏掉。

用法：
  python priest_stone_probe.py [前缀...]        # 默认扫全部 *.ait
"""
import re, glob, sys, collections

RE_CONV   = re.compile(r'HumanAction:祭司\s+(\d+)\s+设置转换目标为\s+(\S+)\s+(\d+)')
RE_MOVE   = re.compile(r'HumanMove:(\S+)\s+(\d+)\s+移动至\s+\(([\d.]+),([\d.]+)\)')
RE_SPAWN  = re.compile(r'产生了新的(\S+)\(编号:?(\d+)\)')
RE_DEATH  = re.compile(r'(\S+)\(编号:?(\d+)\)死亡')
BL = 35.777


def parse(path):
    """返回 dict：conv[], move{SN:[(fr,x,y,flag)]}, spawn{SN:(fr,flag,name)}, death{SN:fr}"""
    out = dict(conv=[], move=collections.defaultdict(list),
               spawn={}, death={}, success=collections.Counter(), last=0)
    for ln in open(path, encoding='utf-8', errors='replace'):
        p = ln.split(' | ', 3)
        if len(p) < 4:
            continue
        try:
            fr = int(p[1])
        except ValueError:
            continue
        out['last'] = max(out['last'], fr)
        head = p[3].split(' | ', 1)
        flag = head[0].strip()
        msg = head[1].strip() if len(head) > 1 else ''

        m = RE_CONV.match(msg)
        if m:
            out['conv'].append((fr, m.group(2), int(m.group(3))))
            continue
        if '玩家 转换' in msg:
            out['success'][msg.split('玩家 ')[1].split('，')[0]] += 1
            continue
        m = RE_MOVE.match(msg)
        if m:
            out['move'][int(m.group(2))].append(
                (fr, float(m.group(3)) / BL, float(m.group(4)) / BL, flag))
            continue
        m = RE_SPAWN.search(msg)
        if m:
            sn = int(m.group(2))
            if sn not in out['spawn']:
                out['spawn'][sn] = (fr, flag, m.group(1))
            continue
        m = RE_DEATH.match(msg)
        if m:
            out['death'].setdefault(int(m.group(2)), fr)
    return out


def main():
    pats = sys.argv[1:] or ['']
    files = sorted({f for p in pats for f in glob.glob(p + '*.ait')})
    print('文件数 %d' % len(files))

    type_cnt   = collections.Counter()      # 感化令按目标类型
    games_stone = 0                          # 至少有一条"感化投石车"令的局数
    enemy_stone_move = collections.Counter()
    enemy_stone_attack = collections.Counter()
    enemy_stone_dead = 0
    games = 0
    for f in files:
        d = parse(f)
        games += 1
        names = set()
        for fr, nm, tsn in d['conv']:
            type_cnt[nm] += 1
            names.add(nm)
        if '投石车' in names:
            games_stone += 1
        # 敌方投石车（flag=1 产生）的机动/存活情况
        for sn, (fr, fl, nm) in d['spawn'].items():
            if nm == '投石车' and fl == '1':
                enemy_stone_move[sn] += len(d['move'].get(sn, []))
                if sn in d['death']:
                    enemy_stone_dead += 1
    print('局数 %d ｜ 出现过「感化投石车」的局数 %d' % (games, games_stone))
    print('感化令按目标类型：')
    for k, v in type_cnt.most_common():
        print('   %-8s %d' % (k, v))
    print('敌方投石车 SN 的移动令条数：', dict(enemy_stone_move))
    print('敌方投石车阵亡实例数：', enemy_stone_dead)


if __name__ == '__main__':
    main()
