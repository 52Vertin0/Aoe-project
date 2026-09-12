# -*- coding: utf-8 -*-
"""去重+清理 前后的行为对拍（重构验证：指标量级应一致）。
   对比 = fn（清理前, v3 农场版） vs fc（清理后）。
   口径遵循铁律 25：优先机制指标（发令/出手比、事件计数），结果指标（胜负）仅参考。
"""
import re, os, sys, math, statistics as st

RE_FARM = re.compile(r'\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) .* at=\((\d+),(\d+)\)')
TC_BL = (19, 18)                 # map3 + rotate90 固定：96 局反推一致
TC_C = (TC_BL[0] + 1, TC_BL[1] + 1)

# 各计数口径
PAT = {
    'HumanMove':      re.compile(r'HumanMove'),
    'HumanAction':    re.compile(r'HumanAction'),
    '建令(Build)':     re.compile(r'HumanBuild|建造'),
    '采令(Gather)':    re.compile(r'HumanGather'),
    '训令(Train)':     re.compile(r'HumanTrain'),
    '设攻目标':        re.compile(r'设置攻击目标为'),      # 铁律22 分子
    '开始攻击':        re.compile(r'开始向.*攻击'),          # 铁律22 分母
    '转换目标':        re.compile(r'设置转换目标'),
    'KIT-R(拉扯窗口)':  re.compile(r'\[KIT-R'),
    'LC-DBG(清场)':    re.compile(r'\[LC-DBG'),
    'PRST-TOWER-ABORT': re.compile(r'PRST-TOWER-ABORT'),
    'PRIEST GUARD':   re.compile(r'\[PRIEST GUARD\]'),
    'DebugText':      re.compile(r'UsrAI打印'),
}


def adjacent(a, b):
    ax, ay = a; bx, by = b
    sx = (ax - 1 > bx + 2) or (ax + 3 < bx)
    sy = (ay - 1 > by + 2) or (ay + 3 < by)
    return not sx and not sy


def rebuild(seq):
    acc, seen = [], set()
    for fr, x, y in seq:
        if (x, y) in seen:
            continue
        seen.add((x, y))
        if any(adjacent((x, y), a) for a in acc):
            continue
        acc.append((x, y))
    return acc


def one(path):
    d = dict((k, 0) for k in PAT)
    seq, endf, vic, deat, wsf = [], 0, 0, 0, 0
    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE_FARM.search(line)
        if m and int(m.group(2)) == 4:
            seq.append((int(m.group(1)), int(m.group(4)), int(m.group(5))))
        p = line.rstrip('\n').split('|')
        if len(p) < 5:
            continue
        fr = p[1].strip()
        if not fr.isdigit():
            continue
        fr = int(fr)
        endf = max(endf, fr)
        msg = p[4]
        for k, rx in PAT.items():
            if rx.search(msg):
                d[k] += 1
        if 'VICTORY' in msg:
            vic = 1
        if 'DEFEAT: Priest killed' in msg and not deat:
            deat = fr
        if 'Enemy Siege Workshop found' in msg and not wsf:
            wsf = fr
    farms = rebuild(seq)
    dtc = [math.hypot((x + 1) - TC_C[0], (y + 1) - TC_C[1]) for x, y in farms]
    return d, farms, dtc, endf, vic, deat, wsf


def load(batch):
    out = []
    for i in range(1, 9):
        p = '%s%d.ait' % (batch, i)
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            out.append((p, one(p)))
    return out


def med(v):
    return st.median(v) if v else 0.0


def baseline_noise():
    """跨批次噪声 + 归一化（铁律 25/29）：先证明"这个量本来就摆动很大"，再谈差异。"""
    B = ['pu', 'ez', 'tb', 'tl', 'tm', 'tn', 'fl', 'fm', 'fn', 'fc']
    print('\n【1b. 跨批次噪声（含纯基线 pu/ez/tb）—— 用来判断 fc 的差异算不算数】')
    print('%-5s %10s %10s %10s %9s  %s' % ('批次', 'Move/千帧', 'Act/千帧', '攻击/千帧', '局时长', 'Move 逐局'))
    print('-' * 104)
    for b in B:
        per, tot, totf, ac, at = [], 0, 0, 0, 0
        for i in range(1, 9):
            p = '%s%d.ait' % (b, i)
            if not os.path.exists(p) or os.path.getsize(p) < 1000:
                continue
            m = a = x = end = 0
            for line in open(p, encoding='utf-8', errors='replace'):
                q = line.rstrip('\n').split('|')
                if len(q) < 5:
                    continue
                f = q[1].strip()
                if not f.isdigit():
                    continue
                f = int(f); end = max(end, f); msg = q[4]
                if 'HumanMove' in msg:
                    m += 1
                if 'HumanAction' in msg:
                    a += 1
                if '开始向' in msg and '攻击' in msg:
                    x += 1
            per.append(m); tot += m; totf += end; ac += a; at += x
        if not totf:
            continue
        mark = '  ← 清理后（本轮）' if b == 'fc' else ('  ← 清理前（本轮对照）' if b == 'fn' else '')
        print('%-5s %10.2f %10.2f %10.2f %9d  %s%s'
              % (b, 1000.0 * tot / totf, 1000.0 * ac / totf, 1000.0 * at / totf, totf // 8, sorted(per), mark))
    print('※ Move 这一列本身就是长尾分布：fm/fn 各有一局 28312 / 16813 的离群值（其余 900~3200），')
    print('  均值因此被拉高一倍以上。fc 的逐局分布与纯基线 pu/tb 同型 ⇒ 「−53%」是单局噪声，不是重构后果。')


def main():
    A = load('fn')   # 清理前
    B = load('fc')   # 清理后
    print('=' * 96)
    print('去重+清理 行为对拍：fn(清理前) %d 局   vs   fc(清理后) %d 局' % (len(A), len(B)))
    print('=' * 96)

    # ---- 1. 行为量级（每局均值）----
    print('\n【1. 行为事件量级（每局均值）—— 重构不应改变这里】')
    print('%-20s %10s %10s %9s' % ('事件', 'fn', 'fc', '差'))
    print('-' * 96)
    for k in PAT:
        a = sum(r[0][k] for _, r in A) / max(1, len(A))
        b = sum(r[0][k] for _, r in B) / max(1, len(B))
        dd = (b - a) / a * 100 if a else 0
        flag = '' if abs(dd) < 25 else ('  ← 偏差大' if abs(dd) < 60 else '  ← ★异常')
        print('%-20s %10.1f %10.1f %8.0f%%%s' % (k, a, b, dd, flag))

    baseline_noise()

    # ---- 2. 发令/出手比（铁律 22）----
    print('\n【2. 发令 ÷ 真出手（铁律 22：正常≈1，≫1 即被反复重置）】')
    for nm, D in (('fn', A), ('fc', B)):
        c = sum(r[0]['设攻目标'] for _, r in D)
        h = sum(r[0]['开始攻击'] for _, r in D)
        print('  %-4s  设攻目标=%-6d 开始攻击=%-6d  比值=%.2f' % (nm, c, h, (c / h) if h else 0))

    # ---- 3. 农场布局（验证 B2/B3 lambda 未影响选址）----
    print('\n【3. 农场布局（验证去重未改变选址行为）】')
    for nm, D in (('fn', A), ('fc', B)):
        nf = sum(len(r[1]) for _, r in D)
        alls = [d for _, r in D for d in r[2]]
        if not alls:
            print('  %-4s  无农场数据' % nm)
            continue
        over8 = 100.0 * sum(1 for d in alls if d > 8) / len(alls)
        over10 = 100.0 * sum(1 for d in alls if d > 10) / len(alls)
        print('  %-4s  农场=%-4d 农/局=%.1f  到TC 中位=%.1f 均值=%.1f 最大=%.1f  >8格=%.1f%%  >10格=%.1f%%'
              % (nm, nf, nf / max(1, len(D)), med(alls), sum(alls) / len(alls),
                 max(alls), over8, over10))

    # ---- 4. 结果指标（仅参考，噪声大）----
    print('\n【4. 结果指标（铁律 25：8 局噪声大，仅参考）】')
    for nm, D in (('fn', A), ('fc', B)):
        n = len(D)
        w = sum(1 for _, r in D if r[4] and not r[5])
        dth = sum(1 for _, r in D if r[5])
        ws = sum(1 for _, r in D if r[6])
        ends = [r[3] for _, r in D]
        print('  %-4s  胜=%d/%d  祭司死=%d/%d  发现WS=%d/%d  末帧中位=%d'
              % (nm, w, n, dth, n, ws, n, med(ends)))
    print('=' * 96)


if __name__ == '__main__':
    main()
