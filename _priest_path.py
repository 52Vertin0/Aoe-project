# -*- coding: utf-8 -*-
"""_priest_path.py —— 反攻期祭司移动令由哪条路径下发（判"不主动追敌"抑制是否吃掉了感化）

口径：
  反攻起点 = min(POP-FULL 闸帧, ALL WAVES DEFEATED 帧)，缺则 33000
  pm 五列来自 [BEAT]（桶级增量，需按桶求和）：
     f=Flee | ca=靠近【感化目标】的移动令(priestApproachMove) | h=趋近治疗 | cnt=推进/后撤移动令(manageCounterAttack) | o=其它
  [LC-DBG]（每 300 帧）给 siegeSN / dS / mvcd。
用法： python _priest_path.py <TAG> [TAG2 ...]
"""
import glob
import os
import re
import statistics as st
import sys

POP = re.compile(r'POP-FULL COUNTERATTACK! Frame=(\d+)')
CA = re.compile(r'ALL WAVES DEFEATED! Counterattack! Frame=(\d+)')
PM = re.compile(r'pm f(\d+) ca(\d+) h(\d+) cnt(\d+) o(\d+)')
LC = re.compile(r'\[LC-DBG f=(\d+)\] siegeSN=(-?\d+) mem=\((-?\d+),(-?\d+)\) dS=([\d.]+) hp=([\d.]+) ccd=(-?\d+) st=(\d+) mvcd=(-?\d+) gT=(\d+) seen=(\d+) nearT=([-\d.]+) loc=(\d+)')


def outcome(t):
    if '被祭司转换,归属阵营1->0' in t:
        return '胜'
    if 'DEFEAT: Priest killed' in t:
        return '祭死'
    if 'DEFEAT: Town Center destroyed' in t or '敌方 摧毁主营' in t:
        return 'TC毁'
    return '超时'


def main(tags):
    print('=' * 100)
    print('反攻期祭司移动令来源分解（[BEAT] pm 五列，桶级求和）')
    print('=' * 100)
    for tag in tags:
        tot = dict(f=0, ca=0, h=0, cnt=0, o=0)
        per = []
        lc_tot = lc_nosiege = 0
        conv_post = 0
        for f in sorted(glob.glob('%s_*_r0_*.ait' % tag)):
            t = open(f, encoding='utf-8', errors='replace').read()
            cand = [int(x.group(1)) for x in (POP.search(t), CA.search(t)) if x]
            atk = min(cand) if cand else 33000
            d = dict(f=0, ca=0, h=0, cnt=0, o=0)
            for L in t.splitlines():
                p = L.split(' | ', 3)
                if len(p) < 2:
                    continue
                try:
                    fr = int(p[1])
                except ValueError:
                    continue
                if fr < atk:
                    continue
                m = PM.search(L)
                if m:
                    for i, k in enumerate(('f', 'ca', 'h', 'cnt', 'o')):
                        d[k] += int(m.group(i + 1))
                m = LC.search(L)
                if m:
                    lc_tot += 1
                    if int(m.group(2)) == -1:
                        lc_nosiege += 1
            for k in tot:
                tot[k] += d[k]
            per.append((os.path.basename(f), outcome(t), d, atk, sum(d.values())))
        n = len(per)
        s = sum(tot.values()) or 1
        print()
        print('### %s  局数=%d  反攻期移动令合计=%d（%.1f 条/局）' % (tag, n, s - 0, (s) / n))
        print('   %-6s %8s %8s' % ('类别', '条数', '占比'))
        for k, lab in (('ca', '靠近感化目标'), ('cnt', '推进/后撤(反攻段)'), ('f', '逃跑'), ('h', '趋近治疗'), ('o', '其它')):
            print('   %-6s %8d %7.1f%%   %s' % (k, tot[k], 100.0 * tot[k] / s, lab))
        print('   [LC-DBG] 总计=%d，其中 siegeSN=-1（武器厂未发现）= %d（%.1f%%）' % (
            lc_tot, lc_nosiege, 100.0 * lc_nosiege / lc_tot if lc_tot else 0))
        # 逐局：ca 为 0 的局数
        zero_ca = sum(1 for _, _, d, _, _ in per if d['ca'] == 0)
        small = sum(1 for _, _, d, _, _ in per if d['cnt'] + d['ca'] + d['h'] + d['f'] + d['o'] < 20)
        print('   逐局：反攻期 ca(靠近感化) 为 0 的局 = %d/%d ；反攻期移动令 <20 条的局 = %d/%d' % (
            zero_ca, n, small, n))
        # 结局分组
        print('   %-8s %5s %8s %8s %8s %8s' % ('结局', '局数', 'ca/局', 'cnt/局', '其它/局', '合计/局'))
        for res in ('胜', '祭死', '超时', 'TC毁'):
            g = [x for x in per if x[1] == res]
            if not g:
                continue
            ca = sum(x[2]['ca'] for x in g) / len(g)
            cn = sum(x[2]['cnt'] for x in g) / len(g)
            oo = sum(x[2]['f'] + x[2]['h'] + x[2]['o'] for x in g) / len(g)
            print('   %-8s %5d %8.1f %8.1f %8.1f %8.1f' % (res, len(g), ca, cn, oo, ca + cn + oo))


if __name__ == '__main__':
    main(sys.argv[1:] or ['club8n'])
