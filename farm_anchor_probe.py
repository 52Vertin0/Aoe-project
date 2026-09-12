# -*- coding: utf-8 -*-
"""农场锚点验收探针（读 [FARM-PICK] 机制量日志，100% 精确）。

为什么不用 [BUILD-ISSUE] 反推锚点：本图存在**不经 tryBuild** 的预置经济建筑（如 (13,34)），
日志里没有它的建造记录 ⇒ 从外部反推锚点必然漏算。改用落位时打印的
`[FARM-PICK] base=(锚点) r=(环号) tcR=(相对TC环号) -> (x,y) ty=[类型序列]`
⇒ 直接读引擎的选择，且 ty= 让"锚点到底是不是仓库"有了直接证据。

判据（2026-09-19 版）：
  ① r == 4（= FARM_ANCHOR_R_MIN，紧邻环）占比 = 100%            ← 用户选定的「只许紧邻环」硬限制
  ② ty 里出现 'S'(仓库) 的局数 = 0                              ← 用户要求「不能建在仓库附近」
  ③ base 指向的锚点型别 = 'C'(TC) 或 'G'(谷仓)，绝不能是 'S'
  ④ 农场数（BUILD-ISSUE type=4）应仍能接近 MAX_FARMS=12        ← 排除仓库后容量是否掉
  ⑤ tcR：TC 环农场 tcR==4；谷仓环农场天然大（本图谷仓距 TC 10~54 格）

类型字母：C=BUILDING_CENTER(2) / G=BUILDING_GRANARY(1) / S=BUILDING_STOCK(3)
用法：python farm_anchor_probe.py [批次前缀...]（默认 fd）
"""
import re
import sys
import glob
import collections
import statistics as st

RE = re.compile(
    r'\[FARM-PICK f=(\d+)\] base=(\d+)\((-?\d+),(-?\d+)\) r=(\d+) tcR=(\d+) '
    r'-> \((-?\d+),(-?\d+)\)(?:\s+ty=\[([CGS,]*)\])?')
RE_FARM = re.compile(r'BUILD-ISSUE f=\d+\] type=4 size=3')
R_MIN = 4
MAX_FARMS = 12


def parse(path):
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE.search(line)
        if not m:
            continue
        ty = (m.group(9) or '').replace(',', '')
        out.append(dict(fr=int(m.group(1)), base=int(m.group(2)),
                        ax=int(m.group(3)), ay=int(m.group(4)),
                        r=int(m.group(5)), tcR=int(m.group(6)),
                        x=int(m.group(7)), y=int(m.group(8)), ty=ty))
    return out


def count_farms(path):
    n = 0
    for line in open(path, encoding='utf-8', errors='replace'):
        if RE_FARM.search(line):
            n += 1
    return n


def gkey(p):
    m = re.search(r'\d+', p)
    return int(m.group()) if m else 0


def main():
    tags = sys.argv[1:] or ['fd']
    rhist = collections.Counter()
    tyhist = collections.Counter()
    btype = collections.Counter()
    per_game = []
    bad = []
    games_with_S = []
    picks_on_S = []
    games_no_ty = 0
    for tag in tags:
        for fp in sorted(glob.glob(tag + '*.ait'), key=gkey):
            rows = parse(fp)
            if not rows:
                continue
            name = fp.replace('.ait', '')
            rs = [d['r'] for d in rows]
            tys = set(d['ty'] for d in rows)
            if not any(tys):
                games_no_ty += 1
            for t in tys:
                if t:
                    tyhist[t] += 1
            if any('S' in t for t in tys):
                games_with_S.append(name)
            for d in rows:
                rhist[d['r']] += 1
                if d['base'] == 0:
                    btype['TC'] += 1
                else:
                    lt = d['ty'][d['base']] if d['ty'] and d['base'] < len(d['ty']) else '?'
                    btype['谷仓' if lt == 'G' else
                          '仓库' if lt == 'S' else '未知'] += 1
                    if lt == 'S':
                        picks_on_S.append((name, d))
                if d['r'] != R_MIN:
                    bad.append((name, d))
            per_game.append((name, rows, rs, tys, count_farms(fp)))

    tot = sum(rhist.values())
    print('======== ① 落位环号（相对【选中锚点】）========')
    print('样本：%d 局 / %d 次落位' % (len(per_game), tot))
    if tot == 0:
        print('  ⚠ 0 次落位：批还没跑到农场阶段（本图首座农场约在 f≈18700 = 12.5 游戏分），')
        print('    或日志前缀不对 / 该批 exe 不含 [FARM-PICK] 日志。')
        return
    for r in sorted(rhist):
        mark = '   ← 紧邻环 ✓' if r == R_MIN else '   ★ 越界'
        print('  r=%-4d %4d 次 (%5.1f%%)%s' % (r, rhist[r], 100.0 * rhist[r] / tot, mark))
    print('  → 紧邻环占比 %.1f%%（目标 100%%）｜越界 %d 次（目标 0）'
          % (100.0 * rhist[R_MIN] / tot, tot - rhist[R_MIN]))

    print()
    print('======== ② 锚点集合类型签名（ty=[...]）========')
    if games_no_ty:
        print('  ⚠ %d 局无 ty= 字段（旧 exe 日志），无法核对锚点类型' % games_no_ty)
    for k, v in tyhist.most_common():
        has_s = '★ 含仓库 S' if 'S' in k else ''
        print('  ty=[%s]  %d 局  %s' % (','.join(k), v, has_s))
    print('  → 锚点集合里出现「仓库 S」的局数：%d（目标 0）' % len(games_with_S))

    print()
    print('======== ③ 落位归属锚点类型 ========')
    for k, v in btype.most_common():
        print('  %-6s %4d 次 (%5.1f%%)' % (k, v, 100.0 * v / tot))
    print('  → 落在「仓库」锚点上的落位数：%d（目标 0）' % len(picks_on_S))

    print()
    print('======== ④ 每局明细 ========')
    print('%-8s %6s %6s %8s %8s %6s %6s' %
          ('局', '落位', '农场数', 'TC环', '谷仓环', '最差r', '越界'))
    for g, rows, rs, tys, nfarm in per_game:
        tc = [d for d in rows if d['base'] == 0]
        print('%-8s %6d %6d %8d %8d %6d %6d' %
              (g, len(rows), nfarm, len(tc), len(rows) - len(tc),
               max(rs), sum(1 for r in rs if r != R_MIN)))
    if per_game:
        tcR_all = [d['tcR'] for _, rows, _, _, _ in per_game for d in rows if d['base'] == 0]
        if tcR_all:
            print('  TC 环 tcR：中位 %.0f / 最大 %d' % (st.median(tcR_all), max(tcR_all)))
        fs = [nf for _, _, _, _, nf in per_game]
        print('  农场数：中位 %.0f / 最大 %d（MAX_FARMS=%d）' % (st.median(fs), max(fs), MAX_FARMS))

    if bad:
        print()
        print('======== 越界明细（最多 30 条）========')
        for g, d in bad[:30]:
            print('  %-8s f=%-6d at=(%d,%d) r=%-3d 锚点%d(%d,%d) ty=[%s]'
                  % (g, d['fr'], d['x'], d['y'], d['r'], d['base'], d['ax'], d['ay'], d['ty']))
    else:
        print()
        print('  ★ 全部落位都在某锚点的紧邻环（r=4）内 —— 无任何外溢。')


if __name__ == '__main__':
    main()
