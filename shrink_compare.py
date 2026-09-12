# -*- coding: utf-8 -*-
"""shrink 批次对拍：tc（精简前）vs sz（四个最长函数精简后）。

本轮是【纯重构】，红线 = 行为零变化，故判据以"确定性重放一致性"为主：
  ① 逐局 ait 日志行序列比对（同 map/rotate/exam ⇒ 引擎确定论步骤相同，期望逐行一致）
     - 完全相同 = 强证据（零行为变化）
     - 首处分叉帧 + 分叉前后内容 = 定位差异来源
  ② 机制量（千帧率）：HumanMove / 设攻目标 / 开始攻击 / 转换目标 / KIT-R / LC-DBG
  ③ 结果量（8 局噪声大，仅参考）：胜、祭司阵亡、发现 WS、发起反攻
"""
import re, os, statistics as st

RE_MOVE = re.compile(r'HumanMove[:：]\s*(\S+)\s+(\d+)\s+移动至\s*\(([\d.]+),([\d.]+)\)')
TC_C = (20, 19)
BL = 40.0

PAT = {
    'HumanMove': re.compile(r'HumanMove'),
    'HumanAction': re.compile(r'HumanAction'),
    '设攻目标': re.compile(r'设置攻击目标为'),
    '开始攻击': re.compile(r'开始向.*攻击'),
    '转换目标': re.compile(r'设置转换目标'),
    'KIT-R': re.compile(r'\[KIT-R'),
    'LC-DBG': re.compile(r'\[LC-DBG'),
    'TOWER-TGT': re.compile(r'\[TOWER-TGT'),
    'TOWER-SKIP': re.compile(r'\[TOWER-SKIP'),
    'PRIEST GUARD': re.compile(r'\[PRIEST GUARD\]'),
}


def one(path):
    d = dict((k, 0) for k in PAT)
    endf = wsf = victf = deat = decf = 0
    moves = {}
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
    far = max((dd for v in moves.values() for _, dd in v), default=0.0)
    stuck = 0
    for nm, seq in moves.items():
        for i in range(1, len(seq)):
            if seq[i][0] - seq[i - 1][0] >= 600 and abs(seq[i][1] - seq[i - 1][1]) < 0.5:
                stuck += 1
    return d, endf, wsf, victf, deat, decf, far, stuck


def lines_of(path):
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) >= 5:
            out.append((p[1].strip(), p[3].strip(), p[4]))
    return out


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
    A, B = load('tc'), load('sz')
    print('=' * 100)
    print('四个最长函数代码精简：tc(精简前) %d 局  vs  sz(精简后) %d 局' % (len(A), len(B)))
    print('=' * 100)

    print('\n【0. 确定性重放一致性（本轮主判据）】')
    print('%-6s %10s %12s %10s %8s' % ('局', 'A行数', 'B行数', '相同行', '判定'))
    tot_a = tot_b = tot_same = 0
    for i in range(1, 9):
        pa, pb = 'tc%d.ait' % i, 'sz%d.ait' % i
        if not (os.path.exists(pa) and os.path.exists(pb)):
            continue
        la, lb = lines_of(pa), lines_of(pb)
        same = 0
        for ka, kb in zip(la, lb):
            if ka == kb:
                same += 1
            else:
                break
        tot_a += len(la); tot_b += len(lb); tot_same += same
        verdict = '完全一致' if (same == len(la) == len(lb)) else '首差@行%d' % (same + 1)
        print('%-6s %10d %12d %10d %8s' % ('tc/sz%d' % i, len(la), len(lb), same, verdict))
    print('  合计：A=%d 行, B=%d 行, 前缀一致=%d 行 (%.1f%%)'
          % (tot_a, tot_b, tot_same, 100.0 * tot_same / max(1, max(tot_a, tot_b))))

    print('\n【1. 结果指标（8 局噪声大，仅参考）】')
    print('%-6s %8s %10s %10s %12s %10s' % ('批次', '胜', '祭司死', '发现WS', '发起反攻', '末帧中位'))
    for nm, D in (('tc', A), ('sz', B)):
        n = len(D)
        w = sum(1 for _, r in D if r[3] and not r[4])
        print('%-6s %8s %10s %10s %12s %10d'
              % (nm, '%d/%d' % (w, n),
                 '%d/%d' % (sum(1 for _, r in D if r[4]), n),
                 '%d/%d' % (sum(1 for _, r in D if r[2]), n),
                 '%d/%d' % (sum(1 for _, r in D if r[5]), n),
                 med([r[1] for _, r in D])))

    print('\n【2. 机制量（每千帧，抗局长差异 —— 铁律 29）】')
    keys = ['HumanMove', 'HumanAction', '设攻目标', '开始攻击', '转换目标', 'KIT-R', 'LC-DBG', 'TOWER-TGT', 'TOWER-SKIP']
    print('%-6s %10s' % ('批次', '总帧/千') + ''.join('%12s' % k for k in keys))
    for nm, D in (('tc', A), ('sz', B)):
        totf = sum(r[1] for _, r in D) or 1
        row = '%-6s %10.1f' % (nm, totf / 1000.0)
        for k in keys:
            v = sum(r[0][k] for _, r in D)
            row += '%12.2f' % (1000.0 * v / totf)
        print(row)

    print('\n【3. 推进/卡死】')
    print('%-6s %22s %10s' % ('批次', '最深推进(格)', '疑似卡死'))
    for nm, D in (('tc', A), ('sz', B)):
        fars = [r[6] for _, r in D]
        print('%-6s %22s %10d' % (nm, '中位%.0f 最大%.0f' % (med(fars), max(fars or [0])),
                                  sum(r[7] for _, r in D)))

    print('\n【4. 关键事件时间线（帧）】')
    print('%-6s %10s %10s %10s %10s %10s' % ('局', '发现WS', '发起反攻', 'VICTORY', '祭司死', '末帧'))
    for nm, D in (('tc', A), ('sz', B)):
        for p, r in D:
            print('%-6s %10s %10s %10s %10s %10s'
                  % (p.replace('.ait', ''), r[2] or '-', r[5] or '-', r[3] or '-', r[4] or '-', r[1]))

    print('\n【5. 发令 ÷ 真出手（铁律 22：正常≈1）】')
    for nm, D in (('tc', A), ('sz', B)):
        c = sum(r[0]['设攻目标'] for _, r in D)
        h = sum(r[0]['开始攻击'] for _, r in D)
        print('  %-4s 设攻目标=%-6d 开始攻击=%-6d 比值=%.2f' % (nm, c, h, (c / h) if h else 0))
    print('=' * 100)


if __name__ == '__main__':
    main()
