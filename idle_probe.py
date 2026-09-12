# -*- coding: utf-8 -*-
"""农民 IDLE 时间序列探针

数据源：doDebugOutput()（每 150 帧一行）的 UsrAI打印 状态行：
  [<frame>] <STATE> | Fd:a Wd:b St:c Gd:d | Frm:e Idle:f(Carry:g) Walk:h Work:i Atk:j | Mil:k E:l

用途：
  1) 单局逐分钟看 Idle 走势（frame/1500 = 分钟）
  2) 全批定位「Idle 首次放大」的帧号，并与 WAVE1/2/3 = 5000/13500/21000 对齐
  3) 同时给出资源(Fd/Wd/St/Gd)与状态(W1/W2/W3/ATK)，判断是「卡在建造」还是「资源满停手」

用法：
  python idle_probe.py show vf_rollback_1.ait [更多局...]   # 逐分钟时间线
  python idle_probe.py scan <glob>                          # 全批拐点统计
"""
import re, sys, os, glob, statistics

STAT = re.compile(
    r'\[(\d+)\] (ECO|UPG|PREP|W1|W2|W3|ATK|WIN|LOSE) \| '
    r'Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \| '
    r'Frm:(\d+) Idle:(\d+)\(Carry:(\d+)\) Walk:(\d+) Work:(\d+) Atk:(\d+) \| '
    r'Mil:(\d+) E:(\d+)')

FIELDS = ['frame', 'state', 'fd', 'wd', 'st', 'gd',
          'frm', 'idle', 'carry', 'walk', 'work', 'atk', 'mil', 'e']
WAVES = {'WAVE1_TIME': 5000, 'WAVE2_TIME': 13500, 'WAVE3_TIME': 21000}


def parse(path):
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = STAT.search(line)
        if not m:
            continue
        g = m.groups()
        rec = {}
        for i, k in enumerate(FIELDS):
            rec[k] = g[i] if k == 'state' else int(g[i])
        out.append(rec)
    return out


def show(path):
    recs = parse(path)
    if not recs:
        print('  (no status lines)')
        return
    print('=== %s ===  样本 %d 行，帧 %d..%d (%.1f 分)'
          % (os.path.basename(path), len(recs), recs[0]['frame'], recs[-1]['frame'],
             recs[-1]['frame'] / 1500.0))
    print('  %4s %6s %5s %4s %5s %6s %5s %5s %4s %4s %4s %6s %6s' %
          ('min', 'frame', 'state', 'Frm', 'Idle', 'Carry', 'Walk', 'Work', 'Atk', 'Mil', 'E', 'Wd', 'Gd'))
    last_min = -1
    for r in recs:
        mn = r['frame'] // 1500
        if mn == last_min:
            continue
        last_min = mn
        flag = ''
        if r['idle'] >= 5:
            flag = '  <== IDLE>=5'
        elif r['idle'] >= 3:
            flag = '  < IDLE>=3'
        print('  %4d %6d %5s %4d %5d %6d %5d %5d %4d %4d %4d %6d %6d%s' %
              (mn, r['frame'], r['state'], r['frm'], r['idle'], r['carry'],
               r['walk'], r['work'], r['atk'], r['mil'], r['e'], r['wd'], r['gd'], flag))


def scan(paths, tag):
    print('=== 拐点扫描：%s（%d 局）===' % (tag, len(paths)))
    print('  %-26s %-7s %-7s %-7s %-7s  %s'
          % ('game', 'maxIdle', 'pk/min', 'onset>=3', 'onset>=5', '终局/末帧'))
    onsets3, onsets5, peaks = [], [], []
    for p in sorted(paths):
        recs = parse(p)
        if not recs:
            continue
        mx = max(r['idle'] for r in recs)
        peak_min = max(r['frame'] for r in recs if r['idle'] == mx) / 1500.0
        o3 = next((r['frame'] for r in recs if r['idle'] >= 3), None)
        o5 = next((r['frame'] for r in recs if r['idle'] >= 5), None)
        last = recs[-1]
        if o3:
            onsets3.append(o3)
        if o5:
            onsets5.append(o5)
        peaks.append(mx)
        print('  %-26s %-7d %-7.1f %-7s %-7s  %s@%.1f分 Frm=%d'
              % (os.path.basename(p), mx, peak_min,
                 ('%d(%.1f分)' % (o3, o3 / 1500.0)) if o3 else '-',
                 ('%d(%.1f分)' % (o5, o5 / 1500.0)) if o5 else '-',
                 last['state'], last['frame'] / 1500.0, last['frm']))
    print()
    print('  峰值 Idle 中位 = %.1f ；onset>=3 中位 = %s ；onset>=5 中位 = %s'
          % (statistics.median(peaks) if peaks else -1,
             ('%.1f 分 (%d 帧)' % (statistics.median(onsets3) / 1500.0, statistics.median(onsets3))) if onsets3 else '未出现',
             ('%.1f 分 (%d 帧)' % (statistics.median(onsets5) / 1500.0, statistics.median(onsets5))) if onsets5 else '未出现'))
    print('  波次常量：WAVE1=%d(3.3分)  WAVE2=%d(9.0分)  WAVE3=%d(14.0分)' % tuple(WAVES.values()))


ECO = re.compile(
    r'ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+) '
    r'\|\| goldRich:(\d) woodStop:(\d) stoneStop:(\d) foodStop:(\d) woodTarget:(\d) twr:(\d+)/(\d+)')


def gate(paths):
    """统计门禁死区：woodStop 锁死期间，各出口是否全关，Idle 是否随之堆积。"""
    print('=== 门禁死区统计（%d 局）===' % len(paths))
    print('  %-26s %-5s %-6s %-7s %-7s %-6s %-7s %s'
          % ('game', 'peak', 'pk/min', 'woodStop', 'Fmax', 'Gmax', 'Smax', '死区样本(woodStop&F>=10)'))
    hits = 0
    tot = 0
    for p in sorted(paths):
        recs = parse(p)
        eco = []
        for line in open(p, encoding='utf-8', errors='replace'):
            m = ECO.search(line)
            if m:
                eco.append([int(x) for x in m.groups()])
        if not recs:
            continue
        mx = max(r['idle'] for r in recs)
        pk = max(r['frame'] for r in recs if r['idle'] == mx) / 1500.0
        n = len(eco)
        if n == 0:
            print('  %-26s %-5d %-6.1f  (no ECO lines)' % (os.path.basename(p), mx, pk))
            continue
        ws = sum(1 for e in eco if e[9] == 1)
        fmax = max(e[4] for e in eco)
        gmax = max(e[6] for e in eco)
        smax = max(e[7] for e in eco)
        dead = sum(1 for e in eco if e[9] == 1 and e[4] >= 10 and e[6] == 0)
        hits += dead
        tot += n
        print('  %-26s %-5d %-6.1f %-7s %-7d %-6d %-7d %d/%d'
              % (os.path.basename(p), mx, pk, '%d/%d' % (ws, n), fmax, gmax, smax, dead, n))
    print()
    print('  死区样本合计 %d / %d 次 ECO 采样（%.1f%%）= woodStop 锁死 且 食物工≥10 且 黄金工=0'
          % (hits, tot, 100.0 * hits / tot if tot else 0))


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'gate':
        g = sys.argv[2] if len(sys.argv) > 2 else '*.ait'
        gate(glob.glob(os.path.join(r'C:\new-aoe3.0.7g', g))[:120])
    elif mode == 'show':
        for p in sys.argv[2:]:
            show(p if os.path.isabs(p) else os.path.join(r'C:\new-aoe3.0.7g', p))
    else:
        g = sys.argv[2] if len(sys.argv) > 2 else 'vf_rollback_*.ait'
        scan(glob.glob(os.path.join(r'C:\new-aoe3.0.7g', g)), g)
