# -*- coding: utf-8 -*-
"""dm（直达敌方基地附近目标点，删步进/绕路）vs fc（清理后基线）对比。

判据分层（铁律 25）：
  · 机制指标：反攻期军事单位推进深度（离 TC 最远距离）、HumanMove 量/千帧、卡死迹象
  · 结果指标：胜负、祭司阵亡、发现 WS —— 8 局噪声大，仅参考
"""
import re, os, statistics as st

TC_C = (20, 19)                      # map3+rotate90：(19,18)块左下 → 中心 (20,19)
RE_MOVE = re.compile(r'HumanMove[:：]\s*(\S+)\s+(\d+)\s+移动至\s*\(([\d.]+),([\d.]+)\)')
BL = 40.0

PAT = {
    'HumanMove':   re.compile(r'HumanMove'),
    '设攻目标':     re.compile(r'设置攻击目标为'),
    '开始攻击':     re.compile(r'开始向.*攻击'),
    '转换目标':     re.compile(r'设置转换目标'),
    'KIT-R':      re.compile(r'\[KIT-R'),
    'LC-DBG':     re.compile(r'\[LC-DBG'),
    'PRIEST GUARD': re.compile(r'\[PRIEST GUARD\]'),
}


def one(path):
    d = dict((k, 0) for k in PAT)
    endf = wsf = victf = decf = 0
    deat = 0
    moves = {}                       # unitname -> list[(frame, dist_to_TC_blocks)]
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) < 5:
            continue
        fs = p[1].strip()
        if not fs.isdigit():
            continue
        fr = int(fs); endf = max(endf, fr); msg = p[4]
        for k, rx in PAT.items():
            if rx.search(msg):
                d[k] += 1
        m = RE_MOVE.search(msg)
        if m:
            nm = m.group(1)
            if nm not in ('祭司', '村民'):
                x = float(m.group(3)) / BL; y = float(m.group(4)) / BL
                moves.setdefault(nm, []).append((fr, ((x - TC_C[0]) ** 2 + (y - TC_C[1]) ** 2) ** 0.5))
        if 'Enemy Siege Workshop found' in msg and not wsf:
            wsf = fr
        if 'VICTORY' in msg and not victf:
            victf = fr
        if 'Force COUNTERATTACK' in msg and not decf:
            decf = fr
        if 'DEFEAT: Priest killed' in msg and not deat:
            deat = fr
    # 推进深度：所有非祭司/村民单位 HumanMove 落点中离 TC 最远者
    far = max((dd for v in moves.values() for _, dd in v), default=0.0)
    # 卡死迹象：任一单位连续 ≥600 帧落点完全不变
    stuck = 0
    for nm, seq in moves.items():
        for i in range(1, len(seq)):
            if seq[i][0] - seq[i - 1][0] >= 600 and abs(seq[i][1] - seq[i - 1][1]) < 0.5:
                stuck += 1
    return d, endf, wsf, victf, deat, decf, far, stuck, len(moves)


def load(b):
    out = []
    for i in range(1, 9):
        p = '%s%d.ait' % (b, i)
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            out.append((p, one(p)))
    return out


def med(v):
    return st.median(v) if v else 0.0


def main():
    A, B = load('fc'), load('dm')
    print('=' * 100)
    print('反攻探路最简化：fc(步进/绕路版) %d 局  vs  dm(直达目标点版) %d 局' % (len(A), len(B)))
    print('=' * 100)

    print('\n【1. 结果指标（8 局噪声大，仅参考）】')
    print('%-6s %8s %10s %10s %10s %12s' % ('批次', '胜', '祭司死', '发现WS', '发起反攻', '末帧中位'))
    for nm, D in (('fc', A), ('dm', B)):
        n = len(D)
        w = sum(1 for _, r in D if r[3] and not r[4])
        print('%-6s %8s %10s %10s %10s %12d'
              % (nm, '%d/%d' % (w, n),
                 '%d/%d' % (sum(1 for _, r in D if r[4]), n),
                 '%d/%d' % (sum(1 for _, r in D if r[2]), n),
                 '%d/%d' % (sum(1 for _, r in D if r[5]), n),
                 med([r[1] for _, r in D])))

    print('\n【2. 推进机制指标（本轮真正要看的）】')
    print('%-6s %12s %12s %12s %12s %10s' % ('批次', '最深推进(格)', '末帧中位', 'Move/千帧', '被移动单位数', '疑似卡死'))
    for nm, D in (('fc', A), ('dm', B)):
        fars = [r[6] for _, r in D]
        ends = [r[1] for _, r in D]
        mv = sum(r[0]['HumanMove'] for _, r in D)
        totf = sum(ends) or 1
        print('%-6s %12s %12s %12.2f %12s %10d'
              % (nm, '中位%.0f 最大%.0f' % (med(fars), max(fars or [0])),
                 med(ends), 1000.0 * mv / totf,
                 '%.1f' % (sum(r[8] for _, r in D) / max(1, len(D))),
                 sum(r[7] for _, r in D)))

    print('\n【3. 关键事件时间线（帧）】')
    print('%-4s %10s %10s %10s %10s %10s' % ('局', '发现WS', '发起反攻', 'VICTORY', '祭司死', '末帧'))
    for nm, D in (('fc', A), ('dm', B)):
        for p, r in D:
            print('%-4s %10s %10s %10s %10s %10s'
                  % (p.replace('.ait', ''), r[2] or '-', r[5] or '-', r[3] or '-', r[4] or '-', r[1]))

    print('\n【4. 发令 ÷ 真出手（铁律 22：正常≈1）】')
    for nm, D in (('fc', A), ('dm', B)):
        c = sum(r[0]['设攻目标'] for _, r in D)
        h = sum(r[0]['开始攻击'] for _, r in D)
        print('  %-4s 设攻目标=%-6d 开始攻击=%-6d 比值=%.2f' % (nm, c, h, (c / h) if h else 0))
    print('=' * 100)


if __name__ == '__main__':
    main()
