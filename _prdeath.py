# -*- coding: utf-8 -*-
"""祭司死因时间线：把败局末段 [BEAT] 的 pr@/hp/nEB/pm/last 拉出来。

用法: python _prdeath.py "fix1_map_r0_*.ait" [--tail 14]
口径（铁律）：
  · 胜 = 引擎事件 `攻城武器厂(编号:N)被祭司转换`（AI 侧 VICTORY 行可能不写盘）
  · 祭司死 = 'DEFEAT: Priest killed'
  · [BEAT] 新尾巴 pm f/ca/h/cnt/o + last=(x,y) 块坐标
  · hp 从 `pr=(sn91211 st? hp NN/100` 取（0~100 整数）
"""
import re, sys, os, glob

MAP_WS = {'map': (11, 86), 'map1': (93, 11), 'map2': (24, 6), 'map3': (82, 20)}


def beats(path):
    """按行抽 [BEAT] 字段（逐行 re.search，不用 split —— 首行结构与正文不同）"""
    out = []
    for l in open(path, encoding='utf-8', errors='replace'):
        if '[BEAT f=' not in l:
            continue
        g = lambda p: (re.search(p, l).group(1) if re.search(p, l) else None)
        b = g(r'\bb=(\d+)\]')
        if b is None:
            continue
        row = {
            'b': int(b),
            'f': int(g(r'\[BEAT f=(\d+)') or 0),
            'pr': None, 'hp': -1, 'nEB': 0,
            'pm': None, 'last': None,
            'st': g(r'st=([A-Z*\-]+)'),
        }
        m = re.search(r'pr@=\(([\d.]+),([\d.]+)\)', l)
        if m:
            row['pr'] = (float(m.group(1)), float(m.group(2)))
        m = re.search(r'pr=\(sn\d+ st-?\d+ hp(\d+)/100', l)
        if m:
            row['hp'] = int(m.group(1))
        m = re.search(r'nEB=(\d+)', l)
        if m:
            row['nEB'] = int(m.group(1))
        m = re.search(r'pm f(\d+) ca(\d+) h(\d+) cnt(\d+) o(\d+) last=\(([-\d.]+),([-\d.]+)\)', l)
        if m:
            row['pm'] = (int(m.group(1)), int(m.group(2)), int(m.group(3)),
                         int(m.group(4)), int(m.group(5)))
            row['last'] = (float(m.group(6)), float(m.group(7)))
        out.append(row)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    tail = 14
    if '--tail' in sys.argv:
        tail = int(sys.argv[sys.argv.index('--tail') + 1])
    files = []
    for a in args:
        files += sorted(glob.glob(a))
    for f in files:
        txt = open(f, encoding='utf-8', errors='replace').read()
        win = bool(re.search(r'攻城武器厂\(编号:\d+\)被祭司转换', txt)) \
            or 'VICTORY! Siege Workshop converted' in txt
        pdeath = 'DEFEAT: Priest killed' in txt
        bs = beats(f)
        if not bs:
            continue
        mp = re.search(r'(map\d?)', os.path.basename(f))
        mp = mp.group(1) if mp else '?'
        ws = MAP_WS.get(mp)
        res = '胜' if win else ('祭司死' if pdeath else '未结算')
        # 死亡帧（祭司死 → 引擎行里的帧号）
        df = None
        m = re.search(r'\|\s*(\d+)\s*\|.*?DEFEAT: Priest killed', txt)
        if m:
            df = int(m.group(1))
        print('===== %s  %s  %s  deathF=%s' % (os.path.basename(f), mp, res, df))
        # 打印最后 tail 个"有 pr 或 pm"的桶（跳过死亡后 0,0 行）
        sel = [r for r in bs if r['pr'] and r['pr'] != (0.0, 0.0) and r['pm']]
        for r in sel[-tail:]:
            dws = ''
            if ws and r['pr']:
                dws = ' dWS=%.1f' % (((r['pr'][0] - ws[0]) ** 2 + (r['pr'][1] - ws[1]) ** 2) ** 0.5)
            pm = r['pm']
            print('  b=%-4d f=%-6d st=%-5s hp=%-4d nEB=%-3d pr@=(%5.1f,%5.1f)%s | pm f%d ca%d h%d cnt%d o%d last=(%s,%s)' % (
                r['b'], r['f'], r['st'] or '?', r['hp'], r['nEB'],
                r['pr'][0], r['pr'][1], dws,
                pm[0], pm[1], pm[2], pm[3], pm[4],
                ('%.1f' % r['last'][0]) if r['last'] else '?',
                ('%.1f' % r['last'][1]) if r['last'] else '?'))
        print()


if __name__ == '__main__':
    main()
