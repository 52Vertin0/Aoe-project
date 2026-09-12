# -*- coding: utf-8 -*-
"""
tower_atk_batch.py — 批量统计「反攻期军队攻塔覆盖率」与「敌塔距离窗口」。
用法: python tower_atk_batch.py fd1 fd2 ... (不带扩展名)
"""
import sys, io, re, glob
from collections import defaultdict, Counter

RE_ATK = re.compile(r'设置攻击目标为\s*([\u4e00-\u9fa5A-Za-z.]+)\s+(\d+)')
RE_ACTOR = re.compile(r'HumanAction:([\u4e00-\u9fa5A-Za-z.]+)\s+(\d+)')
RE_NEW = re.compile(r'产生了新的([\u4e00-\u9fa5A-Za-z.]+)\(编号:(\d+)\)')
RE_LCD = re.compile(r'gT=(\d+)\s+seen=(\d+)\s+nearT=(-?[\d.]+)')
BL = 35.777
CA = 33000          # COUNTER_ATTACK_FORCE_TIME
RANGE = 12.0        # TOWER_TARGET_RANGE

def load(path):
    rows = []
    for raw in io.open(path, encoding='utf-8', errors='replace'):
        p = raw.rstrip('\r\n').split(' | ', 3)
        if len(p) < 4:
            continue
        try:
            fr = int(p[1])
        except ValueError:
            continue
        seq = p[3].split(' | ')
        rows.append((fr, seq[0].strip(), (seq[-1] if len(seq) > 1 else '').strip()))
    return rows

def main():
    names = sys.argv[1:] or sorted(set(f[:-4] for f in glob.glob('fd*.ait')))
    print('%-10s %7s %7s %7s %6s %8s %7s %7s  %s' %
          ('局', '弓兵数', '攻塔数', '覆盖率', '塔令', '总攻击令', '建筑令', 'TGT', 'nearT<=12帧占比 / nearT中位'))
    tot = defaultdict(int)
    near_all = []
    for nm in names:
        path = nm + '.ait'
        try:
            rows = load(path)
        except IOError:
            continue
        mine = set()
        for fr, flag, m in rows:
            mm = RE_NEW.search(m)
            if mm and flag == '0' and mm.group(1) == '复合弓兵':
                mine.add(int(mm.group(2)))
        tower_sn = set(); n_tower_order = 0; n_atk = 0; n_bld = 0; n_tgt = 0
        BLD = {'箭塔', '农场', '谷仓', '房屋', '仓库', '武器厂', '城镇中心', '兵营', '靶场', '马厩'}
        for fr, flag, m in rows:
            if fr < CA or flag != '0':
                continue
            if 'HumanAction:' in m:
                ma = RE_ACTOR.search(m); mt = RE_ATK.search(m)
                if ma:
                    n_atk += 1
                    if ma.group(1) == '复合弓兵' and mt and mt.group(1) == '箭塔':
                        tower_sn.add(int(ma.group(2)))
                if mt and mt.group(1) in BLD:
                    n_bld += 1
            if 'TOWER-TGT' in m:
                n_tgt += 1
        # nearT 序列
        near = []
        for fr, flag, m in rows:
            if fr < CA:
                continue
            g = RE_LCD.search(m)
            if g:
                v = float(g.group(3))
                if v >= 0:
                    near.append(v)
        pct = (100.0 * sum(1 for v in near if v <= RANGE) / len(near)) if near else 0.0
        med = sorted(near)[len(near) // 2] if near else -1
        near_all += near
        cov = (100.0 * len(tower_sn) / len(mine)) if mine else 0.0
        print('%-10s %7d %7d %6.0f%% %6d %8d %7d %7d  nearT<=12: %4.0f%% (%d/%d) 中位%.1f' %
              (nm, len(mine), len(tower_sn), cov, n_tower_order, n_atk, n_bld, n_tgt,
               pct, sum(1 for v in near if v <= RANGE), len(near), med))
        tot['army'] += len(mine); tot['tower'] += len(tower_sn)
        tot['atk'] += n_atk; tot['bld'] += n_bld; tot['tgt'] += n_tgt
    print('-')
    if tot['army']:
        print('合计: 复合弓兵 %d 个, 攻塔 %d 个 → 覆盖率 %.0f%%' %
              (tot['army'], tot['tower'], 100.0 * tot['tower'] / tot['army']))
        print('      反攻期总攻击令 %d, 其中建筑类 %d (%.2f%%)' %
              (tot['atk'], tot['bld'], 100.0 * tot['bld'] / max(1, tot['atk'])))
    if near_all:
        le = sum(1 for v in near_all if v <= RANGE)
        print('      nearT 样本 %d, <=12 格占 %.0f%% (%d), 中位 %.1f 格, 最小 %.1f' %
              (len(near_all), 100.0 * le / len(near_all), le,
               sorted(near_all)[len(near_all) // 2], min(near_all)))

if __name__ == '__main__':
    main()
