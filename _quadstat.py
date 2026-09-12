# -*- coding: utf-8 -*-
"""四图矩阵胜率与败因归因（读 *_r?_*.ait）
用法:
  python _quadstat.py base0_*_r0_*.ait
  python _quadstat.py --map base0_map_*    # 按图聚合
口径（铁律）:
  胜   = '!!! VICTORY! Siege Workshop converted !!!'
  祭死 = 'DEFEAT: Priest killed'
  超时 = 末帧 >= 44000 且无以上
"""
import re, sys, os, glob, collections

MAP_WS = {  # 敌武器厂块坐标（来自 _maprev.py）
    'map':  (11, 86),
    'map1': (93, 11),
    'map2': (24, 6),
    'map3': (82, 20),
}


def parse(path):
    txt = open(path, encoding='utf-8', errors='replace').read()
    lines = txt.splitlines()
    d = {'file': os.path.basename(path)}
    m = re.match(r'.*?_(map\d?)_r(\d+)_(\d+)\.ait', d['file'])
    if not m:
        m2 = re.search(r'(map\d?)', d['file'])
        d['map'] = m2.group(1) if m2 else '?'
        d['rot'] = -1
        d['idx'] = 0
    else:
        d['map'], d['rot'], d['idx'] = m.group(1), int(m.group(2)), int(m.group(3))

    # ⚠ 胜判据：以引擎事件为准（`攻城武器厂(编号:N)被祭司转换`）。AI 侧的 `!!! VICTORY!` 行
    #   在某些局【不会写进 AIText】——实测 base0_map_r0_3 转换成功但无 VICTORY 行 ⇒ 只看 AI 串会漏判。
    d['win'] = bool(re.search(r'攻城武器厂\(编号:\d+\)被祭司转换', txt)) \
        or 'VICTORY! Siege Workshop converted' in txt
    d['pdeath'] = 'DEFEAT: Priest killed' in txt
    # TC 被毁（第三条失败原因）
    d['tclost'] = bool(re.search(r'市镇中心\(编号:\d+\)被摧毁', txt))
    # 日志是否写到收尾（用于剔除"进程仍在写"的半成品文件）
    d['done'] = d['win'] or d['pdeath'] or d['tclost']
    # 末帧
    frames = [int(x) for x in re.findall(r'\[BEAT f=(\d+)', txt)]
    d['lastf'] = max(frames) if frames else 0
    # 结束帧（更准：引擎帧号）
    fs = [int(x) for x in re.findall(r'\|\s*(\d+)\s*\|\s*(?:red|green|blue|black)', txt)]
    d['endf'] = max(fs) if fs else d['lastf']
    d['esc'] = len(re.findall(r'PRIEST-ESCAPE(?!-BREAK)', txt))
    d['brk'] = len(re.findall(r'PRIEST-ESCAPE-BREAK', txt))
    # 转换成功帧
    cf = re.findall(r'\|\s*(\d+)\s*\|.*?攻城武器厂\(编号:\d+\)被祭司转换', txt)
    d['convf'] = int(cf[0]) if cf else None
    # 祭司 SN
    ms = re.findall(r'产生了新的祭司\(编号:(\d+)\)', txt)
    d['psn'] = int(ms[0]) if ms else None
    # 祭司轨迹（块坐标）
    tr = [(int(b), float(x), float(y)) for b, x, y in
          re.findall(r'\[BEAT f=\d+ b=(\d+)\].*?pr@=\(([\d.]+),([\d.]+)\)', txt)]
    d['track'] = tr
    # 祭司最长静止（连续同点）
    best = (0, 0, None)
    run = 0
    prev = None
    for b, x, y in tr:
        if prev and abs(x - prev[1]) < 0.5 and abs(y - prev[2]) < 0.5:
            run += 1
        else:
            run = 1
            start = b
        if run > best[0]:
            best = (run, start, (x, y))
        prev = (b, x, y)
    d['still_run'], d['still_start'], d['still_at'] = best
    # nEB 统计
    nebs = [int(x) for x in re.findall(r'nEB=(\d+)', txt)]
    d['nEBmax'] = max(nebs) if nebs else 0
    d['nEBfirst'] = next((i for i, v in enumerate(nebs) if v > 0), None)
    # 祭司最低 hp
    hps = [int(h) for h in re.findall(r'pr=\(sn\d+ st-?\d+ hp(\d+)/100', txt)]
    d['hpmin'] = min(hps) if hps else -1
    d['hptrack'] = hps
    # 祭司最终位置 vs 敌武器厂
    d['prlast'] = (tr[-1][1], tr[-1][2]) if tr else None
    ws = MAP_WS.get(d['map'])
    if ws and tr:
        d['dws'] = ((tr[-1][1] - ws[0]) ** 2 + (tr[-1][2] - ws[1]) ** 2) ** 0.5
    else:
        d['dws'] = None
    # 我方军力轨迹
    mils = [int(x) for x in re.findall(r'Mil=(\d+)', txt)]
    d['milmax'] = max(mils) if mils else 0
    d['millast'] = mils[-1] if mils else 0
    # 我方建筑被毁
    d['myTowerLost'] = len(re.findall(r'箭塔\(编号:1\d+\)被摧毁', txt))
    return d


def result(d):
    if d['win']:
        return '胜'
    if d['pdeath']:
        return '祭司死'
    if d['tclost']:
        return 'TC毁'
    if d['endf'] >= 44000:
        return '超时'
    return '未完@%.0f分' % (d['endf'] / 1500.0)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    bymap = '--bymap' in sys.argv
    files = []
    for a in args:
        files += sorted(glob.glob(a))
    if not files:
        print('no files'); return
    rows = [parse(f) for f in files]
    print('%-34s %-5s %-8s %-7s %-5s %-5s %-7s %-7s %-9s' % (
        'file', 'map', '结果', '结束分', 'ESCAPE', 'BREAK', 'd(武器厂)', '最长静止', 'hp最低'))
    for d in rows:
        st = d['still_run']
        print('%-34s %-5s %-8s %-7.2f %-5d %-5d %-7s %-7s %-9d' % (
            d['file'], d['map'], result(d), d['endf'] / 1500.0, d['esc'], d['brk'],
            ('%.1f' % d['dws']) if d['dws'] is not None else '—',
            '%d桶@b%d' % (st, d['still_start']) if st else '—',
            d['hpmin']))
    print()
    agg = collections.defaultdict(lambda: collections.Counter())
    for d in rows:
        agg[d['map']][result(d)] += 1
    print('=== 按图聚合 ===')
    for mp in sorted(agg):
        c = agg[mp]
        n = sum(c.values())
        print('%-6s n=%-3d 胜=%-3d (%.0f%%) | %s' % (
            mp, n, c['胜'], 100.0 * c['胜'] / n,
            ' '.join('%s=%d' % (k, v) for k, v in sorted(c.items()))))


if __name__ == '__main__':
    main()
