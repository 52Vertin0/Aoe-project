#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
采金人数修复验证（2026-09-17）

问题：采金人数偏少（金工达成率仅 50.7%）。
根因（三条叠加）：
  ① 【计数虚高】goldWorkers/foodWorkers 用两条并列 if 累加
     （ResourceSort 手持 + WorkObjectSN 工作目标）⇒ 同一村民被数两次
     ⇒ 派工判据 `goldWorkers < goldTarget` 提前满足 ⇒ 不再派人
  ② 【伐木滞留】木头 100~220 区间：woodTarget 已从 8 回落到 4，
     但撤人条件只看 woodStop(木头≥220) ⇒ 多出的 4 人永久滞留伐木
  ③ 【撤了不回金】reassignToDeficit 无黄金分支 ⇒ 撤下来的人只去伐木/食物

本脚本按三组口径统计：
  A 机制量：金工达成率、伐木工滞留、金矿实际采集人数
  B 结果量：胜负、金存量、反攻单位数
  C 健康度：末日帧、落成建筑、崩溃

用法: python goldworker_probe.py gw1.ait gw2.ait ...
"""
import re
import sys
import glob

ECO = re.compile(
    r'ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+)'
    r' \|\| goldRich:(\d+) woodStop:(\d+) stoneStop:(\d+) foodStop:(\d+) woodTarget:(\d+)')
FR = re.compile(r'\|\s*(\d+)\s*\|')
VICTORY = 'VICTORY! Siege Workshop converted'
DEFEAT_PRIEST = 'DEFEAT: Priest killed'
DEFEAT_TC = 'DEFEAT: Town Center destroyed'
BUILT = '建造完毕'
GOLD_ORDER = re.compile(r'HumanAction:村民 (\d+) 设置工作目标为 金矿')
GOLD_DEPOSIT = re.compile(r'ResourceSort|金矿')


def analyse(fn):
    try:
        txt = open(fn, encoding='utf-8', errors='replace').read()
    except FileNotFoundError:
        return None
    d = dict(file=fn, eco=[], gold_sns=set(), gold_orders=0,
             vic=0, dp=0, dt=0, built=0, last=0)
    lines = txt.split('\n')
    for line in lines:
        m = EcoMatch = ECO.search(line)
        if m:
            fr = FR.search(line)
            d['eco'].append((int(fr.group(1)) if fr else 0,
                             [int(x) for x in m.groups()]))
        mf = FR.search(line)
        if mf:
            d['last'] = max(d['last'], int(mf.group(1)))
        if GOLD_ORDER.search(line):
            d['gold_orders'] += 1
            d['gold_sns'].add(GOLD_ORDER.search(line).group(1))
        if VICTORY in line:
            d['vic'] += 1
        if DEFEAT_PRIEST in line:
            d['dp'] += 1
        if DEFEAT_TC in line:
            d['dt'] += 1
        if BUILT in line:
            d['built'] += 1
    return d


def post_bronze_rows(d):
    """已进铜器后的采样（有食物或黄金存量）"""
    out = []
    for fr, g in d['eco']:
        Fd, Wd, St, Gd, Wf, Ww, Wg, Ws, rich, ws, ss, fs, wt = g
        if Fd == 0 and Gd == 0 and Wf == 0:
            continue                    # 未进铜器
        out.append((fr,) + tuple(g))
    return out


def gold_target(Wf):
    return max(1, int(Wf * 3 / 5 + 0.999))


def report(rows, label):
    print('=' * 96)
    print('%s' % label)
    print('=' * 96)
    print('%-10s %-9s %-9s %-9s %-9s %-8s %s' %
          ('file', '金工均值', '目标均值', '达成率', '伐木均值', 'rich', '结局'))
    print('-' * 96)
    reaches = []
    for d in rows:
        pb = post_bronze_rows(d)
        if not pb:
            continue
        n = len(pb)
        gw = sum(r[7] for r in pb) / n          # 金工（ECO 第8字段 = G）
        tgt = sum(gold_target(r[5]) for r in pb) / n
        ww = sum(r[6] for r in pb) / n          # 伐木工（ECO 第7字段 = W）
        rich = sum(r[9] for r in pb) / n
        reach = (gw / tgt * 100) if tgt > 0 else 0
        reaches.append(reach)
        res = '胜' if d['vic'] else ('负' if (d['dp'] or d['dt']) else '无')
        print('%-10s %-9.2f %-9.2f %-8.1f%% %-9.2f %-8.2f %s' %
              (d['file'], gw, tgt, reach, ww, rich, res))
    if reaches:
        print('-' * 96)
        print('平均金工达成率 = %.1f%%' % (sum(reaches) / len(reaches)))
    print()


def wood_buckets(all_rows):
    print('=' * 96)
    print('伐木工滞留区检查（木头存量 vs 伐木工人数）')
    print('=' * 96)
    print('%-22s %-8s %-10s %-10s %s' % ('木头区间', '采样数', '伐木均值', '木目标', 'woodStop'))
    print('-' * 96)
    buckets = {}
    for d in all_rows:
        for fr, g in d['eco']:
            Wd, Ww, ws, wt = g[1], g[5], g[9], g[12]
            if Wd < 50:
                b = '0-50'
            elif Wd < 100:
                b = '50-100'
            elif Wd < 220:
                b = '100-220 (滞留区)'
            else:
                b = '>=220'
            buckets.setdefault(b, []).append((Ww, wt, ws))
    for b in ['0-50', '50-100', '100-220 (滞留区)', '>=220']:
        v = buckets.get(b, [])
        if not v:
            continue
        print('%-22s %-8d %-10.2f %-10.2f %.2f' %
              (b, len(v), sum(x[0] for x in v) / len(v),
               sum(x[1] for x in v) / len(v), sum(x[2] for x in v) / len(v)))
    print()


def main(files):
    if not files:
        files = sorted(glob.glob('gw*.ait'))
    rows = [r for r in (analyse(f) for f in files) if r]
    if not rows:
        print('无数据')
        return

    report(rows, 'A. 金工达成率（机制量）')
    wood_buckets(rows)

    print('=' * 96)
    print('B. 结果量 & 健康度')
    print('=' * 96)
    print('%-10s %-7s %-7s %-8s %-10s %-10s %-9s %s' %
          ('file', 'VICT', 'DEFEAT', '结局', '末日帧', '落成建筑', '金矿人次', '唯一金村民'))
    print('-' * 96)
    for d in rows:
        res = '胜' if d['vic'] else ('负' if (d['dp'] or d['dt']) else '无')
        print('%-10s %-7d %-7d %-8s %-10d %-10d %-9d %d' %
              (d['file'], d['vic'], d['dp'] + d['dt'], res, d['last'],
               d['built'], d['gold_orders'], len(d['gold_sns'])))
    w = sum(1 for d in rows if d['vic'])
    l = sum(1 for d in rows if d['dp'] or d['dt'])
    print('-' * 96)
    print('胜 %d / 负 %d / 无结局 %d（共 %d 局）' % (w, l, len(rows) - w - l, len(rows)))


if __name__ == '__main__':
    main(sys.argv[1:])
