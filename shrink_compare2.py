# -*- coding: utf-8 -*-
"""shrink 轮三批次对拍：tc(精简前) / sz(精简后·修复版) / szb(同构建重跑=噪声标尺)。

判据体系（铁律 25/29/36）：
  ① 同构建重跑差（sz vs szb）= 噪声上限 N
  ② pre vs post 差（tc vs sz）：若 ≤ N 量级 ⇒ 判"未改变行为"
  ③ 结构量（推进深度分布、开局时序）抗噪，优先看；事件计数摆动大，只看量/千帧
用法: python shrink_compare2.py
"""
import re, os, statistics as st

BL = 40.0
TC_C = (20, 19)

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
    'MARKET': re.compile(r'\[MARKET'),
    'GATE': re.compile(r'\[GATE f='),
    'SIEGE-HOLD': re.compile(r'\[SIEGE-HOLD'),
}
RE_MOVE = re.compile(r'HumanMove[:：]\s*(\S+)\s+(\d+)\s+移动至\s*\(([\d.]+),([\d.]+)\)')

# 关键建筑/事件（用于"是否真的少建了谷仓"这类结构核对）
KEYMSG = ['[MARKET', '[GATE f=', 'GAZELLE-STOCK', 'BRONZE', 'COLLAGE', 'STABLE']


def one(path):
    d = dict((k, 0) for k in PAT)
    endf = wsf = victf = deat = decf = gbf = 0
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


def load(b):
    out = []
    for i in range(1, 9):
        p = '%s%d.ait' % (b, i)
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            out.append((p, one(p)))
    return out


def med(v):
    return st.median(v) if v else 0.0


def line_of(path):
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) >= 5:
            out.append((p[1].strip(), p[3].strip(), p[4]))
    return out


def block(title, LEFT, RIGHT, an, bn):
    print('\n' + '=' * 108)
    print('【%s】 %s %d 局  vs  %s %d 局' % (title, an, len(LEFT), bn, len(RIGHT)))
    print('=' * 108)

    # ---- 结果指标 ----
    print('\n-- 结果指标（8 局噪声大，仅参考）')
    print('%-6s %10s %10s %10s %12s %12s %10s' % ('批次', '胜', '祭司死', '发现WS', '发起反攻', '最深推进中位', '卡死'))
    for nm, D in ((an, LEFT), (bn, RIGHT)):
        n = len(D)
        w = sum(1 for _, r in D if r[3] and not r[4])
        print('%-6s %10s %10s %10s %12s %12s %10d'
              % (nm, '%d/%d' % (w, n),
                 '%d/%d' % (sum(1 for _, r in D if r[4]), n),
                 '%d/%d' % (sum(1 for _, r in D if r[2]), n),
                 '%d/%d' % (sum(1 for _, r in D if r[5]), n),
                 '%.0f' % med([r[6] for _, r in D]), sum(r[7] for _, r in D)))

    # ---- 机制量（千帧） ----
    print('\n-- 机制量（每千帧，铁律 29）')
    keys = [k for k in PAT]
    print('%-6s %10s' % ('批次', '总帧/千') + ''.join('%12s' % k for k in keys))
    rows = {}
    for nm, D in ((an, LEFT), (bn, RIGHT)):
        totf = sum(r[1] for _, r in D) or 1
        rows[nm] = dict((k, 1000.0 * sum(r[0][k] for _, r in D) / totf) for k in keys)
        totf_k = totf / 1000.0
        rows[nm]['_f'] = totf_k
        print('%-6s %10.1f' % (nm, totf_k) + ''.join('%12.2f' % rows[nm][k] for k in keys))
    print('%-6s %10s' % ('相对差', '') + ''.join(
        '%12s' % ('%+.0f%%' % (100.0 * (rows[bn][k] - rows[an][k]) / rows[an][k]) if rows[an][k] else '-')
        for k in keys))

    # ---- 逐局时间线 ----
    print('\n-- 关键事件时间线（帧）')
    print('%-8s %10s %10s %10s %10s %10s' % ('局', '发现WS', '发起反攻', 'VICTORY', '祭司死', '末帧'))
    for nm, D in ((an, LEFT), (bn, RIGHT)):
        for p, r in D:
            print('%-8s %10s %10s %10s %10s %10s'
                  % (nm + p.replace('.ait', '').lstrip('abcdefghijklmnopqrstuvwxyz'), r[2] or '-', r[5] or '-',
                     r[3] or '-', r[4] or '-', r[1]))


def replay(an, bn):
    print('\n' + '=' * 108)
    print('【确定性重放：逐行前缀一致】%s vs %s' % (an, bn))
    print('=' * 108)
    print('%-10s %10s %12s %10s %8s' % ('局', 'A行数', 'B行数', '相同行', '判定'))
    tot_a = tot_b = tot_same = 0
    for i in range(1, 9):
        pa, pb = '%s%d.ait' % (an, i), '%s%d.ait' % (bn, i)
        if not (os.path.exists(pa) and os.path.exists(pb)):
            continue
        la, lb = line_of(pa), line_of(pb)
        same = 0
        for ka, kb in zip(la, lb):
            if ka == kb:
                same += 1
            else:
                break
        tot_a += len(la); tot_b += len(lb); tot_same += same
        verdict = '完全一致' if (same == len(la) == len(lb)) else '首差@%d' % (same + 1)
        print('%-10s %10d %12d %10d %8s' % ('%s%d' % (an, i), len(la), len(lb), same, verdict))
    print('  合计：A=%d, B=%d, 前缀一致=%d (%.1f%%)'
          % (tot_a, tot_b, tot_same, 100.0 * tot_same / max(1, max(tot_a, tot_b))))


def main():
    tc, sz, szb = load('tc'), load('sz'), load('szb')
    print('#' * 108)
    print('# shrink 轮三批次对拍   tc/%d  sz/%d  szb/%d' % (len(tc), len(sz), len(szb)))
    print('#   ① sz vs szb = 同构建重跑噪声标尺（铁律 36）')
    print('#   ② tc vs sz  = 精简前后差异；≤ 噪声量级 ⇒ 判未改变行为')
    print('#' * 108)

    block('噪声标尺 A：sz(第1批) vs szb(第2批·同构建)', sz, szb, 'sz', 'szb')
    block('主对拍 B：tc(精简前) vs sz(精简后)', tc, sz, 'tc', 'sz')
    replay('sz', 'szb')
    replay('tc', 'sz')
    print('\n' + '#' * 108)


if __name__ == '__main__':
    main()
