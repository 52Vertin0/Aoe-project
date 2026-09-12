# -*- coding: utf-8 -*-
"""
祭司"被猎杀"的暴露量与因果探针
用法: python hunt4_probe.py
"""
import io, glob, re, collections, statistics, math

RE_ATK = re.compile(r'HumanAction:(\S+) (\d+) 设置攻击目标为 (\S+) (\d+)')
RE_PMV = re.compile(r'HumanMove:祭司 (\d+) 移动至 \(([\d.]+),([\d.]+)\)')
RE_DEAD = re.compile(r'DEFEAT: Priest killed')
RE_ENGAGE = re.compile(r'祭司\(编号:(\d+)\)开始向')
BL = 35.777
# 我方 TC 块坐标 (19,18) -> 世界坐标
TC = ((19 + 1) * BL, (18 + 1) * BL)


def load(tag='kd'):
    per = collections.defaultdict(list)
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
            per[g].append((f, p[3].strip(), p[4].strip()))
    return per


def main():
    per = load('kd')

    print('=' * 104)
    print('A. ★ 每局：祭司暴露量 —— 被锁次数 / 被锁帧数 / 存活时长 / 结局')
    print('=' * 104)
    print('%-6s %8s %9s %9s %9s %9s %10s %s' %
          ('局', '被锁令', '被锁帧', '存活帧', '暴露率', '存活分钟', '临死前锁', '结局'))
    rows = []
    for g in sorted(per):
        seq = per[g]
        lockf = set()
        lockn = 0
        for f, fl, m in seq:
            if fl == '1':
                mm = RE_ATK.search(m)
                if mm and mm.group(3) == '祭司':
                    lockf.add(f)
                    lockn += 1
        last = max(f for f, fl, m in seq)
        dead = 0
        for f, fl, m in seq:
            if RE_DEAD.search(m):
                dead = f
                break
        alive = dead or last
        # 临死前 1500 帧内的锁定
        near_lock = sum(1 for f in lockf if alive - 1500 <= f <= alive)
        end = '胜' if any('VICTORY' in m for f, fl, m in seq) else ('祭司死' if dead else '无结局')
        expo = 100.0 * len(lockf) / max(1, alive)
        print('%-6s %8d %9d %9d %8.1f%% %9.1f %10d %s' %
              ('kd%d' % g, lockn, len(lockf), alive, expo, alive / 1500.0, near_lock, end))
        rows.append((g, lockn, len(lockf), expo, near_lock, end))

    print()
    print('=' * 104)
    print('B. ★ 祭司被锁时它在哪 —— 距我方 TC 的距离分布（格）')
    print('=' * 104)
    alld = []
    for g in sorted(per):
        seq = per[g]
        # 建立祭司移动目标的时间序列
        mv = [(f, float(x), float(y)) for f, fl, m in seq
              for x, y in [RE_PMV.search(m).groups()[1:] if RE_PMV.search(m) else (None, None)]
              if x is not None]
        if not mv:
            continue
        for f, fl, m in seq:
            if fl != '1':
                continue
            mm = RE_ATK.search(m)
            if not mm or mm.group(3) != '祭司':
                continue
            # 找最近的移动目标
            cand = [v for v in mv if v[0] <= f]
            if not cand:
                continue
            _, x, y = cand[-1]
            d = math.hypot(x - TC[0], y - TC[1]) / BL
            alld.append((g, f, d))
    if alld:
        ds = [d for _, _, d in alld]
        print('  样本 %d。距我方 TC：中位 %.1f 格  均值 %.1f  最小 %.1f  最大 %.1f' %
              (len(ds), statistics.median(ds), sum(ds) / len(ds), min(ds), max(ds)))
        buckets = collections.Counter()
        for _, _, d in alld:
            if d < 10: buckets['0~10 格(家门口)'] += 1
            elif d < 20: buckets['10~20 格'] += 1
            elif d < 30: buckets['20~30 格'] += 1
            elif d < 50: buckets['30~50 格(推进中)'] += 1
            else: buckets['>50 格(敌腹地)'] += 1
        for k in ['0~10 格(家门口)', '10~20 格', '20~30 格', '30~50 格(推进中)', '>50 格(敌腹地)']:
            if buckets.get(k):
                print('    %-18s %5d (%.1f%%)' % (k, buckets[k], 100.0 * buckets[k] / len(ds)))

    print()
    print('=' * 104)
    print('C. ★ 祭司与敌方的真实交战（引擎行"祭司开始向X攻击"）')
    print('=' * 104)
    print('%-6s %8s %10s %12s   %s' % ('局', '交战次数', '首次交战帧', '= 分钟', '交战对象'))
    for g in sorted(per):
        eng = []
        for f, fl, m in per[g]:
            mm = RE_ENGAGE.search(m)
            if mm:
                mm2 = re.search(r'开始向(\S+?)\(', m)
                if mm2:
                    eng.append((f, mm2.group(1)))
        if eng:
            c = collections.Counter(t for _, t in eng)
            print('%-6s %8d %10d %12.1f   %s' %
                  ('kd%d' % g, len(eng), eng[0][0], eng[0][0] / 1500.0,
                   dict(c.most_common(5))))
        else:
            print('%-6s %8d %10s %12s   -' % ('kd%d' % g, 0, '-', '-'))

    print()
    print('=' * 104)
    print('D. ★ "被锁"与"死亡"的因果：死亡局的临死前锁定强度 vs 存活局')
    print('=' * 104)
    deadg = [r for r in rows if r[5] == '祭司死']
    aliveg = [r for r in rows if r[5] != '祭司死']
    print('  死亡局 %d：临死前1500帧锁定 中位 %.1f  均值 %.1f' %
          (len(deadg), statistics.median([r[4] for r in deadg]),
           sum(r[4] for r in deadg) / len(deadg)))
    if aliveg:
        print('  非死亡局 %d：全程锁定 中位 %.1f' %
              (len(aliveg), statistics.median([r[1] for r in aliveg])))


if __name__ == '__main__':
    main()
