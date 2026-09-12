# -*- coding: utf-8 -*-
"""
待建建筑（地基）派人情况探针
------------------------------------------------
统计日志中四类建造事件，按批次分组给出"每局均值 + 类型分布"：
  1. [BUILD-ISSUE]  建造令下发（type/size/村民SN/坐标/木材）
  2. [ORPHAN]       孤儿地基抢救触发（地基SN/type/percent/补派村民/是否抽采集岗）
  3. [BUILDER-HARD] 建造者硬超时放弃（处置：作废另址重建 / 仅释放登记）
  4. [FARM-RING]    农场锚点紧邻环无空位 ⇒ 本帧不建

用法:  python build_pending_probe.py [前缀...]      # 省略前缀 = 全部 *.ait
"""
import os, re, sys, glob, collections

ROOT = r'C:\new-aoe3.0.7g'

RE_BI = re.compile(r'\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) 村民SN=(\d+) at=\((\d+),(\d+)\) wood=(-?\d+)')
RE_OR = re.compile(r'\[ORPHAN f=(\d+)\] 地基SN=(\d+) type=(\d+) percent=(\d+) 补派村民SN=(\d+)(.*)')
RE_BH = re.compile(r'\[BUILDER-HARD f=(\d+)\] 建造者SN=(\d+) type=(\d+) 地基SN=(\d+) percent=(\d+) 超时(\d+)帧 → (.*)')
RE_FR = re.compile(r'\[FARM-RING f=(\d+)\] 锚点紧邻环无空位 farms=(\d+)/(\d+) 谷仓锚点=(\d+) 仓库\(已排除\)=(\d+)')

TYPE_NAME = {0: '房屋', 1: '谷仓', 2: '市场', 3: '兵营', 4: '靶场', 5: '马厩',
             6: '箭塔', 7: '农场', 8: '学院', 9: '仓库', 10: 'TC升级', 11: '武器厂'}


def message(line):
    """ait 行: time | frame | color | flag | message"""
    p = line.split(' | ', 3)
    if len(p) < 4:
        return None
    q = p[3].split(' | ', 1)
    return q[1] if len(q) > 1 else q[0]


def main():
    prefixes = sys.argv[1:]
    files = []
    for pat in (prefixes if prefixes else ['*']):
        files += [f for f in glob.glob(os.path.join(ROOT, pat + '*.ait')) if not f.endswith('.bak')]
    files = sorted(set(files))
    if not files:
        print('未找到 ait 文件')
        return

    # 按前缀分组（文件名去掉 _数字 与 .ait）
    groups = collections.defaultdict(list)
    for f in files:
        base = os.path.basename(f)[:-4]
        g = re.sub(r'[_\-]?\d+$', '', base) or base
        groups[g].append(f)

    overall = collections.Counter()
    print('=' * 96)
    print('%-10s %5s %9s %9s %9s %9s' % ('批次', '局数', 'BI/局', 'ORPHAN/局', 'HARD/局', 'FRING/局'))
    print('=' * 96)
    for g in sorted(groups):
        fl = groups[g]
        n = len(fl)
        c_bi = c_or = c_bh = c_fr = 0
        for f in fl:
            try:
                with open(f, 'r', encoding='utf-8', errors='replace') as fh:
                    for line in fh:
                        if '[BUILD-ISSUE' in line:
                            c_bi += 1
                        elif '[ORPHAN' in line:
                            c_or += 1
                        elif '[BUILDER-HARD' in line:
                            c_bh += 1
                        elif '[FARM-RING' in line:
                            c_fr += 1
            except Exception as e:
                print('  !!', f, e)
        overall['files'] += n
        overall['bi'] += c_bi
        overall['or'] += c_or
        overall['bh'] += c_bh
        overall['fr'] += c_fr
        print('%-10s %5d %9.2f %9.2f %9.2f %9.2f' % (g, n, c_bi / n, c_or / n, c_bh / n, c_fr / n))

    N = overall['files']
    print('-' * 96)
    print('%-10s %5d %9.2f %9.2f %9.2f %9.2f' % ('合计', N, overall['bi'] / N, overall['or'] / N,
                                                 overall['bh'] / N, overall['fr'] / N))
    return groups


if __name__ == '__main__':
    main()
