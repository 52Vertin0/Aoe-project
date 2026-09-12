# -*- coding: utf-8 -*-
"""反攻期祭司"离太远/很少感化敌军"实测
口径：
  · 反攻起点 = min(POP-FULL 闸帧, ALL WAVES DEFEATED! Counterattack! 帧)
  · 感化令  = HumanAction:祭司 <SN> 设置转换目标为 <兵种> <TSN>  （引擎动作日志，不受采样影响）
  · 距离量  = Priest st= 行的 nearE(到最近敌[军队+箭塔]) / nearAlly(到最近友军)，每 100 帧一行（可能跳号）
用法： python _priest_far.py <TAG> [TAG2 ...]
"""
import glob
import re
import statistics
import sys

BL = 35.777

POP = re.compile(r'POP-FULL COUNTERATTACK! Frame=(\d+)')
CA = re.compile(r'ALL WAVES DEFEATED! Counterattack! Frame=(\d+)')
FR = re.compile(r'^\d\d:\d\d:\d\d+\s*\|\s*(\d+)\s*\|')
# Priest st=1 hp=1.00 nearE=... threat=... mode=0 | ally=0 wound25=0 nearAlly=...BL cd=0
PST = re.compile(r'Priest st=(\d+) hp=([\d.]+) nearE=([-\d.e]+) threat=([-\d.e]+) mode=(\d+) \| ally=(\d+) wound25=(\d+) nearAlly=([-\d.e]+)BL cd=(\d+)')
CONV = re.compile(r'HumanAction:祭司 (\d+) 设置转换目标为 ([\u4e00-\u9fa5A-Za-z.]+) (\d+)')
CONV_W = re.compile(r'HumanAction:祭司 (\d+) 设置工作目标为 ([\u4e00-\u9fa5A-Za-z.]+) (\d+)')
MOVE = re.compile(r'HumanMove:祭司 (\d+) 移动至 \(([\d.]+),([\d.]+)\)')


def outcome(s):
    if '被祭司转换,归属阵营1->0' in s:
        return 'W'
    if 'DEFEAT: Priest killed' in s:
        return 'P'
    if 'DEFEAT: Town Center destroyed' in s or '敌方 摧毁主营' in s:
        return 'T'
    return 'U'


def big(v):
    """哨兵值/无效值判定"""
    try:
        f = float(v)
    except ValueError:
        return True
    return f > 1e4  # nearE 最大也就 ~140 格


def frame_of(line):
    p = line.split(' | ', 3)
    if len(p) < 2:
        return None
    try:
        return int(p[1])
    except ValueError:
        return None


def main(tags):
    print('=' * 96)
    print('反攻期祭司距离与感化敌军统计（源：ait 引擎动作日志 + Priest st= 诊断行）')
    print('=' * 96)
    for tag in tags:
        files = sorted(glob.glob('%s_map_r0_*.ait' % tag))
        if not files:
            print('[%s] 无文件' % tag)
            continue
        rows = []
        for fn in files:
            s = open(fn, encoding='utf-8', errors='replace').read()
            mp, mc = POP.search(s), CA.search(s)
            cand = [int(x.group(1)) for x in (mp, mc) if x]
            atk = min(cand) if cand else None
            res = outcome(s)
            conv_all = conv_pre = conv_post = 0
            tgt_post = {}
            nearE_post = []
            nearAlly_post = []
            for ln in s.splitlines():
                fr = frame_of(ln)
                if fr is None:
                    continue
                m = CONV.search(ln)
                if m:
                    conv_all += 1
                    post = (atk is not None and fr >= atk)
                    if post:
                        conv_post += 1
                        tgt_post[m.group(2)] = tgt_post.get(m.group(2), 0) + 1
                    else:
                        conv_pre += 1
                    continue
                m = PST.search(ln)
                if m and atk is not None and fr >= atk:
                    if not big(m.group(3)):
                        nearE_post.append(float(m.group(3)))
                    if not big(m.group(8)):
                        nearAlly_post.append(float(m.group(8)))
            rows.append(dict(fn=fn, res=res, atk=atk,
                             conv_all=conv_all, conv_pre=conv_pre, conv_post=conv_post,
                             tgt=tgt_post, ne=nearE_post, na=nearAlly_post))
        n = len(rows)
        W = sum(1 for r in rows if r['res'] == 'W')
        convs = [r['conv_all'] for r in rows]
        pre = [r['conv_pre'] for r in rows]
        post = [r['conv_post'] for r in rows]
        has_atk = [r for r in rows if r['atk'] is not None]
        print()
        print('### %s   n=%d  胜=%d (%.1f%%)   有反攻点=%d' % (tag, n, W, 100.0 * W / n, len(has_atk)))
        print('  感化令(全部)  中位=%.0f  均=%.1f  零条局=%d/%d' % (
            statistics.median(convs), statistics.mean(convs), sum(1 for c in convs if c == 0), n))
        print('  感化令(反攻前)中位=%.0f  均=%.1f' % (statistics.median(pre), statistics.mean(pre)))
        print('  感化令(反攻期)中位=%.0f  均=%.1f  零条局=%d/%d' % (
            statistics.median(post), statistics.mean(post),
            sum(1 for c in post if c == 0), n))
        # 目标类型（反攻期，合并全部局）
        agg = {}
        for r in rows:
            for k, v in r['tgt'].items():
                agg[k] = agg.get(k, 0) + v
        top = sorted(agg.items(), key=lambda kv: -kv[1])[:12]
        print('  反攻期感化目标类型: ' + ' | '.join('%s:%d' % (k, v) for k, v in top))
        # 距离
        allempty = True
        for key, arr in (('nearE(近敌)', [x for r in rows for x in r['ne']]),
                         ('nearAlly(近友军)', [x for r in rows for x in r['na']])):
            if not arr:
                print('  %s: 无数据' % key)
                continue
            allempty = False
            arr_s = sorted(arr)
            q = lambda p: arr_s[min(len(arr_s) - 1, int(p * len(arr_s)))]
            print('  %s: n=%d 中位=%.1f 均=%.1f p10=%.1f p90=%.1f max=%.1f  |  >12格占%.1f%%  >28格占%.1f%%'
                  % (key, len(arr_s), statistics.median(arr_s), statistics.mean(arr_s),
                     q(0.10), q(0.90), arr_s[-1],
                     100.0 * sum(1 for x in arr_s if x > 12) / len(arr_s),
                     100.0 * sum(1 for x in arr_s if x > 28) / len(arr_s)))
        # 胜/负分组
        for grp, sel in (('胜局', [r for r in rows if r['res'] == 'W']),
                         ('祭死局', [r for r in rows if r['res'] == 'P']),
                         ('超时局', [r for r in rows if r['res'] == 'U'])):
            if not sel:
                continue
            cp = [r['conv_post'] for r in sel]
            ne = [x for r in sel for x in r['ne']]
            print('   [%s n=%d] 反攻期感化中位=%.0f  近敌中位=%s' % (
                grp, len(sel), statistics.median(cp),
                ('%.1f' % statistics.median(ne)) if ne else 'n/a'))


if __name__ == '__main__':
    main(sys.argv[1:] or ['club8n'])
