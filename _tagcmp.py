# -*- coding: utf-8 -*-
"""按 tag × 图 汇总：胜率 + 败因分解 + 机制量（供 base0 / fix1 / fix2 三臂对照）。

用法:  python _tagcmp.py base0 fix1 fix2
产出:  ① 逐 tag × 图 明细行  ② 四图汇总  ③ 「胜率提升 / 回退」差异列（相对第一个 tag）

口径（与 _quadstat.py 保持一致，勿改）:
  胜   = 引擎事件 `攻城武器厂(编号:N)被祭司转换`  或  AI 串 `VICTORY! Siege Workshop converted`
  祭死 = `DEFEAT: Priest killed`
  TC毁 = `市镇中心(编号:N)被摧毁`
  超时 = 末帧 >= 44000 且以上皆无
  未完 = 其余（进程还在写 / 异常中断）——**统计时应剔除，否则胜率被稀释**
"""
import re, sys, glob, os, collections

MAPS = ['map', 'map1', 'map2', 'map3']


def parse(path):
    t = open(path, encoding='utf-8', errors='replace').read()
    d = {'file': os.path.basename(path)}
    m = re.search(r'^(.*?)_(map\d?)_r(\d+)_(\d+)\.ait', d['file'])
    if m:
        d['tag'], d['map'], d['idx'] = m.group(1), m.group(2), int(m.group(4))
    else:
        d['tag'], d['map'], d['idx'] = '?', '?', 0

    d['win'] = bool(re.search(r'攻城武器厂\(编号:\d+\)被祭司转换', t)) \
        or 'VICTORY! Siege Workshop converted' in t
    d['pdeath'] = 'DEFEAT: Priest killed' in t
    d['tclost'] = bool(re.search(r'市镇中心\(编号:\d+\)被摧毁', t))
    # ⚠ 口径纠错（2026-10-06）：`done` **必须包含超时**。超时局（endf>=45000）同样是"已收尾"的
    #   失败局，之前把它排除在 done 之外 ⇒ 超时局既不计入结算也不进败因 ⇒ 凭空消失
    #   （实测 base0/fix1 各有 3 局 45000 帧超时被吞掉，使结算数 45 < 48）。下面 §走查已复核。
    d['timeout'] = False   # 占位，endf 解析后回填
    fs0 = [int(x) for x in re.findall(r'\|\s*(\d+)\s*\|\s*(?:red|green|blue|black)', t)]
    d['timeout'] = (max(fs0) if fs0 else 0) >= 44000
    d['done'] = d['win'] or d['pdeath'] or d['tclost'] or d['timeout']

    fs = [int(x) for x in re.findall(r'\|\s*(\d+)\s*\|\s*(?:red|green|blue|black)', t)]
    d['endf'] = max(fs) if fs else 0

    # 反攻起点帧 / 祭司死亡帧 —— 用于把「祭死」再切成 反攻前(早) / 反攻后(晚)
    #   早死 ≈ f15000~17000（10~11 分，WAVE2 前后我方军队被全歼 ⇒ 祭司孤身被远程追死）
    #   晚死 ≈ f37000~44000（反攻段，祭司进敌火力圈被塔/兵打死）
    mc = re.search(r'Counterattack! Frame=(\d+)', t)
    d['caF'] = int(mc.group(1)) if mc else None
    md = re.search(r'\|\s*(\d+)\s*\|[^|]*\|[^|]*\|[^|]*DEFEAT: Priest killed', t)
    d['deathF'] = int(md.group(1)) if md else None
    d['deathEarly'] = bool(d['pdeath'] and (d['caF'] is None or (d['deathF'] or 0) < d['caF']))

    d['esc'] = len(re.findall(r'PRIEST-ESCAPE(?!-BREAK)', t))
    d['brk'] = len(re.findall(r'PRIEST-ESCAPE-BREAK', t))

    # 逐桶 [BEAT]：pr@ / pm / hp
    rows, seen = [], {}
    for l in t.splitlines():
        if '[BEAT f=' not in l:
            continue
        mb = re.search(r'\bb=(\d+)\]', l)
        if not mb:
            continue
        mp_ = re.search(r'pr@=\(([\d.]+),([\d.]+)\)', l)
        mh = re.search(r'pr=\(sn\d+ st-?\d+ hp(\d+)/100', l)
        mp = re.search(r'pm f(\d+) ca(\d+) h(\d+) cnt(\d+) o(\d+)', l)
        seen[int(mb.group(1))] = {
            'b': int(mb.group(1)),
            'p': (float(mp_.group(1)), float(mp_.group(2))) if mp_ else None,
            'hp': int(mh.group(1)) if mh else None,
            'pm': [int(mp.group(i)) for i in range(1, 6)] if mp else None,
        }
    rows = [seen[b] for b in sorted(seen)]

    # 停滞率
    pos = [(r['b'], r['p']) for r in rows if r['p']]
    still = tot = 0
    for i in range(1, len(pos)):
        dx = pos[i][1][0] - pos[i - 1][1][0]
        dy = pos[i][1][1] - pos[i - 1][1][1]
        tot += 1
        if (dx * dx + dy * dy) ** 0.5 < 0.5:
            still += 1
    d['stall'] = (still / tot) if tot else 0.0

    # 反攻段推进效率
    mc = re.search(r'Counterattack! Frame=(\d+)', t)
    caB = (int(mc.group(1)) // 150) if mc else None
    seg = [(b, p) for b, p in pos if caB is None or b >= caB]
    if len(seg) >= 3:
        net = ((seg[-1][1][0] - seg[0][1][0]) ** 2 + (seg[-1][1][1] - seg[0][1][1]) ** 2) ** 0.5
        path = sum(((seg[i][1][0] - seg[i - 1][1][0]) ** 2
                    + (seg[i][1][1] - seg[i - 1][1][1]) ** 2) ** 0.5 for i in range(1, len(seg)))
        d['eff'] = (net / path) if path > 0.01 else 0.0
    else:
        d['eff'] = None

    # 主导档序列 → flip / runMax
    dom = []
    for r in rows:
        if not r['pm'] or sum(r['pm']) == 0:
            dom.append('-')
        else:
            dom.append(['f', 'ca', 'h', 'cnt', 'o'][max(range(5), key=lambda i: r['pm'][i])])
    fl = sum(1 for i in range(1, len(dom)) if dom[i] != dom[i - 1] and dom[i] != '-' and dom[i - 1] != '-')
    pr = sum(1 for i in range(1, len(dom)) if dom[i] != '-' and dom[i - 1] != '-')
    d['flip'] = (fl / pr) if pr else 0.0
    run = best = 0
    prev = None
    for x in dom:
        if x == '-':
            continue
        run = run + 1 if x == prev else 1
        best = max(best, run)
        prev = x
    d['runMax'] = best

    hps = [r['hp'] for r in rows if r['hp'] is not None]
    d['hpmin'] = min(hps) if hps else -1
    return d


def cause(d):
    """★ 祭死按【反攻起点】切成早/晚两簇 —— 两簇的根因完全不同，必须分开计数。"""
    if d['win']:
        return '胜'
    if d['pdeath']:
        return '祭死早' if d['deathEarly'] else '祭死晚'
    if d['tclost']:
        return 'TC毁'
    if d['endf'] >= 44000:
        return '超时'
    return '未完'


CAUSE_COLS = ['胜', '祭死早', '祭死晚', '超时', 'TC毁']


def main():
    tags = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not tags:
        print('用法: python _tagcmp.py base0 fix1 fix2'); return

    data = {}
    for tg in tags:
        files = sorted(glob.glob(tg + '_*_r0_*.ait'))
        data[tg] = [parse(f) for f in files]

    print('=== ① 逐 tag × 图   [结算率 = 已收尾局数/总局数] ===')
    print('%-8s %-6s %4s %4s %4s %6s %6s | %-30s | %5s %5s %6s %6s %6s %6s' % (
        'tag', 'map', '总', '结算', '胜', '结算率', '胜率',
        '败因(胜/祭死早/祭死晚/超时/TC毁)', 'esc', 'brk', 'flip', 'stall', 'eff', 'hpMin'))
    summary = collections.defaultdict(dict)
    for tg in tags:
        for mp in MAPS:
            rows = [d for d in data[tg] if d['map'] == mp]
            done = [d for d in rows if d['done']]
            c = collections.Counter(cause(d) for d in done)
            nd = len(done)
            w = c['胜']
            def av(k, src=done):
                vals = [d[k] for d in src if d.get(k) is not None]
                return sum(vals) / len(vals) if vals else float('nan')
            summary[tg][mp] = dict(n=nd, w=w, raw=len(rows), c=c,
                                   esc=av('esc'), brk=av('brk'), flip=av('flip'),
                                   stall=av('stall'), eff=av('eff'), hpmin=av('hpmin'))
            s = summary[tg][mp]
            fmt = lambda v, p: (p % v) if v == v else '—'
            print('%-8s %-6s %4d %4d %4d %5s%% %5s%% | 胜%-2d 早%-2d 晚%-2d 超%-2d TC%-2d | %5s %5s %6.2f %6.2f %6s %6s' % (
                tg, mp, len(rows), nd, w,
                fmt(100.0 * nd / len(rows) if rows else float('nan'), '%.0f'),
                fmt(100.0 * w / nd if nd else float('nan'), '%.0f'),
                c['胜'], c['祭死早'], c['祭死晚'], c['超时'], c['TC毁'],
                fmt(s['esc'], '%.1f'), fmt(s['brk'], '%.1f'), s['flip'], s['stall'],
                fmt(s['eff'], '%.2f'), fmt(s['hpmin'], '%.0f')))

    print()
    print('=== ② 全图汇总（四图合计）   [★主口径 = 全量胜率 w/总局数，A/B 两臂局数相同时才可比] ===')
    print('%-8s %4s %4s %6s | %7s %6s | %-30s | %5s %6s %6s %6s' % (
        'tag', '总', '结算', '结算率', '胜率全量', '胜率结算', '败因', 'esc', 'flip', 'stall', 'eff'))
    for tg in tags:
        allrows = data[tg]
        done = [d for d in allrows if d['done']]
        c = collections.Counter(cause(d) for d in done)
        nd, na = len(done), len(allrows)
        agg = summary[tg]
        def nav(k):
            vals = [agg[mp][k] for mp in MAPS if agg[mp]['n'] and agg[mp][k] == agg[mp][k]]
            return sum(vals) / len(vals) if vals else float('nan')
        fmt = lambda v, p: (p % v) if v == v else '—'
        print('%-8s %4d %4d %5s%% | %6s%% %5s%% | 胜%-2d 早%-2d 晚%-2d 超%-2d TC%-2d | %5s %6.2f %6.2f %6s' % (
            tg, na, nd,
            fmt(100.0 * nd / na if na else float('nan'), '%.0f'),
            fmt(100.0 * c['胜'] / na if na else float('nan'), '%.0f'),
            fmt(100.0 * c['胜'] / nd if nd else float('nan'), '%.0f'),
            c['胜'], c['祭死早'], c['祭死晚'], c['超时'], c['TC毁'],
            fmt(nav('esc'), '%.1f'), nav('flip'), nav('stall'),
            fmt(nav('eff'), '%.2f')))

    print()
    print('=== ③ 胜率差（正=提升）。口径 A=全量(w/总局数)  B=已结算(w/结算局数) ===')
    print('%-8s %s' % ('tag', ' '.join('%11s' % m for m in MAPS + ['ALL'])))
    base = summary[tags[0]]
    for tg in tags:
        cellsA, cellsB = [], []
        for mp in MAPS:
            b, s = base[mp], summary[tg][mp]
            ra = (s['w'] / s['raw'] - b['w'] / b['raw']) if (s['raw'] and b['raw']) else 0.0
            rb = (s['w'] / s['n'] - b['w'] / b['n']) if (s['n'] and b['n']) else 0.0
            cellsA.append('%+5.0f%%' % (100.0 * ra))
            cellsB.append('%+5.0f%%' % (100.0 * rb))
        dn = sum(summary[tg][m]['raw'] for m in MAPS)
        dw = sum(summary[tg][m]['w'] for m in MAPS)
        bn = sum(base[m]['raw'] for m in MAPS)
        bw = sum(base[m]['w'] for m in MAPS)
        dnn = sum(summary[tg][m]['n'] for m in MAPS)
        bnn = sum(base[m]['n'] for m in MAPS)
        cellsA.append('%+5.0f%%' % (100.0 * (dw / dn - bw / bn) if dn and bn else 0))
        cellsB.append('%+5.0f%%' % (100.0 * (dw / dnn - bw / bnn) if dnn and bnn else 0))
        print('%-8s A: %s' % (tg, ' '.join(cellsA)))
        print('%-8s B: %s' % ('', ' '.join(cellsB)))


if __name__ == '__main__':
    main()
