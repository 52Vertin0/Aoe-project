# -*- coding: utf-8 -*-
"""祭司【移动令落点】的交替性分析：用引擎动作日志 `HumanMove:祭司 <SN> 移动至 (x,y)` 重建令序列。

为什么需要它：`[BEAT]` 的 `pm` 字段只在 2026-10-06 之后编译的 exe 里才有（base0 无此字段），
而对拍【历史的 base0】只能靠引擎动作日志。引擎动作日志不受采样影响，是更基础的机制量。

判据：
  · 主导落点交替率 alt2 = 相邻两条令在「top2 落点」之间来回切换的比例。
    双吸引子极限环 ⇒ alt2 ≈ 1.0；单向推进/正常撤退 ⇒ alt2 低。
  · 令间距 med = 相邻令的中位帧距（≈ priestMoveCooldown；flee=18 / heal=30 交替 ⇒ 混合间距）。
  · 净位移/路程 = 首尾距离 / 逐点路程和（≈0 ⇒ 原地打转）。

用法:  python _fleeflip.py base0_map_r0_2.ait [更多文件...]
"""
import re, sys, os, statistics, collections

BL = 35.777


def parse(path):
    txt = open(path, encoding='utf-8', errors='replace').read()
    d = {'file': os.path.basename(path)}
    d['win'] = bool(re.search(r'攻城武器厂\(编号:\d+\)被祭司转换', txt)) \
        or 'VICTORY! Siege Workshop converted' in txt
    d['pdeath'] = 'DEFEAT: Priest killed' in txt
    m = re.search(r'产生了新的祭司\(编号:(\d+)\)', txt)
    psn = m.group(1) if m else None
    d['psn'] = psn

    # 祭司移动令（引擎动作日志）→ 块坐标
    mv = []
    for l in txt.splitlines():
        mf = re.search(r'\|\s*(\d+)\s*\|', l)
        if not mf:
            continue
        if 'HumanMove:祭司' not in l:
            continue
        m2 = re.search(r'移动至 \(([\d.]+),([\d.]+)\)', l)
        if m2:
            mv.append((int(mf.group(1)), float(m2.group(1)) / BL, float(m2.group(2)) / BL))
    d['n_mv'] = len(mv)
    # ★ 核心机制量：祭司【真感化令】次数 ÷ 【移动令】次数。
    #   病根判据：早死局实测 165 条移动令 却只有 1 条感化令（比值 0.006）
    #   ⇒ 祭司整局都在"走过去"从未到达感化射程（`priestApproachMove` 每 20 帧重选目标）。
    d['n_conv'] = len(re.findall(r'HumanAction:祭司 \d+ 设置转换目标为', txt))
    d['conv_per_mv'] = (d['n_conv'] / len(mv)) if mv else None
    if len(mv) < 6:
        d.update(alt2=None, med=None, net=None, nTargets=0, top2=[])
        return d

    cnt = collections.Counter((round(x, 1), round(y, 1)) for _, x, y in mv)
    top2 = [k for k, _ in cnt.most_common(2)]
    d['top2'] = top2
    d['nTargets'] = len(cnt)

    # 交替率：只看落在 top2 上的令，统计相邻（按序）切换比例
    seq = [k for _, x, y in mv for k in [(round(x, 1), round(y, 1))] if k in top2]
    flips = sum(1 for i in range(1, len(seq)) if seq[i] != seq[i - 1])
    d['alt2'] = (flips / (len(seq) - 1)) if len(seq) > 1 else 0.0

    d['med'] = statistics.median([mv[i][0] - mv[i - 1][0] for i in range(1, len(mv))])

    # 净位移 / 路程（用实际落点序列近似轨迹）
    path = sum(((mv[i][1] - mv[i - 1][1]) ** 2 + (mv[i][2] - mv[i - 1][2]) ** 2) ** 0.5
               for i in range(1, len(mv)))
    net = ((mv[-1][1] - mv[0][1]) ** 2 + (mv[-1][2] - mv[0][2]) ** 2) ** 0.5
    d['net'] = (net / path) if path > 0.01 else 0.0
    # top2 相距
    if len(top2) == 2:
        d['sep'] = ((top2[0][0] - top2[1][0]) ** 2 + (top2[0][1] - top2[1][1]) ** 2) ** 0.5
    else:
        d['sep'] = None
    return d


def main():
    files = []
    for a in sys.argv[1:]:
        files.append(a)
    if not files:
        print('用法: python _fleeflip.py <ait>...'); return
    print('%-26s %-5s %5s %5s %6s %6s %6s %6s %6s  %s' % (
        'file', '结果', '令数', '感化', '感化/令', '落点数', 'alt2', '中位间距', '净/路程', 'top2 落点(块)'))
    for f in files:
        d = parse(f)
        res = '胜' if d['win'] else ('祭死' if d['pdeath'] else '—')
        f2 = lambda v, p: (p % v) if v is not None else '—'
        print('%-26s %-5s %5d %5d %6s %6d %6s %7s %7s  %s' % (
            d['file'], res, d['n_mv'], d['n_conv'], f2(d['conv_per_mv'], '%.3f'),
            d['nTargets'], f2(d['alt2'], '%.2f'), f2(d['med'], '%.0f'), f2(d['net'], '%.2f'),
            ' '.join('(%.1f,%.1f)' % t for t in d['top2'])))


if __name__ == '__main__':
    main()
