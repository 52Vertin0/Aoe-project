# -*- coding: utf-8 -*-
"""木头上限 220/320 → 400/400 的经济对照分析器。

数据源（同一局两种打印）：
  A) 状态行（每 150 帧）：[f] STATE | Fd Wd St Gd | Frm Idle(Carry) Walk Work Atk | Mil E
  B) 自检行（每 600 帧）：ECO | Fd Wd St Gd || workers F W G S || goldRich woodStop stoneStop foodStop woodTarget twr:x/y

核心指标（用于判断"抬高木闸"是修好了死区、还是把食物/升级拖坏了）：
  死区样本%   = ECO 采样中 (woodStop==1 且 食物工>=10 且 黄金工==0) 的占比
  最长死区窗口 = 连续死区采样的最大长度 ×600 帧（→ 分钟）
  峰值 Idle / Idle均值
  木头峰值 / 木头均值 / 木头≥400 的采样占比
  伐木工峰值 / 均值，食物工均值
  升铜器时刻（首次出现 UPG 状态的帧）；终局胜负

用法：python wood400_analyze.py <标签> <glob> [<标签> <glob> ...]
"""
import re, sys, os, glob, statistics

STAT = re.compile(
    r'\[(\d+)\] (ECO|UPG|PREP|W1|W2|W3|ATK|WIN|LOSE) \| '
    r'Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \| '
    r'Frm:(\d+) Idle:(\d+)\(Carry:(\d+)\) Walk:(\d+) Work:(\d+) Atk:(\d+) \| '
    r'Mil:(\d+) E:(\d+)')

ECO = re.compile(
    r'ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+) '
    r'\|\| goldRich:(\d) woodStop:(\d) stoneStop:(\d) foodStop:(\d) woodTarget:(\d) twr:(\d+)/(\d+)')

FIELD = {0: 'fd', 1: 'wd', 2: 'st', 3: 'gd', 4: 'f', 5: 'w', 6: 'g',
         7: 's', 8: 'goldRich', 9: 'woodStop', 10: 'stoneStop',
         11: 'foodStop', 12: 'woodTarget', 13: 'twr', 14: 'twrMax'}


def frame_of(line):
    p = line.split(' | ', 3)
    if len(p) >= 2:
        try:
            return int(p[1])
        except ValueError:
            return None
    return None


def load(path):
    st, eco = [], []
    win = lose = 0
    for line in open(path, encoding='utf-8', errors='replace'):
        m = STAT.search(line)
        if m:
            g = m.groups()
            st.append({'frame': int(g[0]), 'state': g[1], 'fd': int(g[2]), 'wd': int(g[3]),
                       'st': int(g[4]), 'gd': int(g[5]), 'frm': int(g[6]), 'idle': int(g[7]),
                       'carry': int(g[8]), 'walk': int(g[9]), 'work': int(g[10]),
                       'atk': int(g[11]), 'mil': int(g[12]), 'e': int(g[13])})
        m2 = ECO.search(line)
        if m2:
            fr = frame_of(line)
            rec = {'frame': fr if fr else 0}
            for i, v in enumerate(m2.groups()):
                rec[FIELD[i]] = int(v)
            eco.append(rec)
        if 'VICTORY! Siege Workshop converted' in line:
            win += 1
        if 'DEFEAT:' in line:
            lose += 1
    return st, eco, win, lose


def dead(e):
    return e['woodStop'] == 1 and e['f'] >= 10 and e['g'] == 0


def longest_run(eco):
    best = cur = 0
    for e in eco:
        if dead(e):
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def metrics(path):
    st, eco, win, lose = load(path)
    if not st or not eco:
        return None
    mx = max(r['idle'] for r in st)
    pk_f = max(r['frame'] for r in st if r['idle'] == mx)
    d = sum(1 for e in eco if dead(e))
    late = [e for e in eco if e['frame'] >= 21000]
    upg = next((r['frame'] for r in st if r['state'] == 'UPG'), None)
    return {
        'name': os.path.basename(path),
        'idle_max': mx,
        'idle_pk_min': pk_f / 1500.0,
        'idle_mean': statistics.mean(r['idle'] for r in st),
        'idle_ge5': sum(1 for r in st if r['idle'] >= 5),
        'st_n': len(st),
        'eco_n': len(eco),
        'ws_n': sum(1 for e in eco if e['woodStop'] == 1),
        'dead_n': d,
        'dead_pct': 100.0 * d / len(eco),
        'dead_run': longest_run(eco),
        'dead_run_min': longest_run(eco) * 600 / 1500.0,
        'wd_max': max(e['wd'] for e in eco),
        'wd_mean': statistics.mean(e['wd'] for e in eco),
        'wd_ge400': sum(1 for e in eco if e['wd'] >= 400),
        'wd_late_mean': statistics.mean([e['wd'] for e in late]) if late else -1,
        'w_max': max(e['w'] for e in eco),
        'w_mean': statistics.mean(e['w'] for e in eco),
        'f_mean': statistics.mean(e['f'] for e in eco),
        'fd_mean': statistics.mean(e['fd'] for e in eco),
        'mil_max': max(r['mil'] for r in st),
        'last_frame': st[-1]['frame'],
        'upg_min': (upg / 1500.0) if upg else None,
        'win': win, 'lose': lose,
    }


def agg(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None and r.get(key) >= 0]
    if not vals:
        return '-'
    return '%.1f' % statistics.median(vals)


def report(tag, paths):
    rows = [m for m in (metrics(p) for p in sorted(paths)) if m]
    if not rows:
        print('  (no data for %s)' % tag)
        return None
    n = len(rows)
    print('=== %s : %d 局 ===' % (tag, n))
    print('  %-24s %-5s %-6s %-7s %-6s %-6s %-8s %-8s %-5s %-6s %-5s %s'
          % ('game', 'peakId', 'pk/min', 'idleavg', 'dead%', 'runMin',
             'deadRunCnt', 'WdMax', 'Wmax', 'Wavg', 'mil', 'UPG末局'))
    for r in rows:
        print('  %-24s %-5d %-6.1f %-7.2f %-6.1f %-6.1f %-8d %-8d %-5d %-6.1f %-5d %s'
              % (r['name'], r['idle_max'], r['idle_pk_min'], r['idle_mean'], r['dead_pct'],
                 r['dead_run_min'], r['dead_run'], r['wd_max'], r['w_max'], r['w_mean'],
                 r['mil_max'],
                 ('%.1f分' % r['upg_min']) if r['upg_min'] else '未升'))
    print('  ---- 中位汇总 ----')
    print('  峰值Idle=%s  死区占比=%s%%  最长死区=%s分  死区采样数=%s  木峰值=%s  木均值=%s'
          % (agg(rows, 'idle_max'), agg(rows, 'dead_pct'), agg(rows, 'dead_run_min'),
             agg(rows, 'dead_run'), agg(rows, 'wd_max'), agg(rows, 'wd_mean')))
    print('  伐木工峰值=%s  伐木工均值=%s  食物工均值=%s  食物存量均值=%s  军队峰值=%s  末帧中位=%s'
          % (agg(rows, 'w_max'), agg(rows, 'w_mean'), agg(rows, 'f_mean'),
             agg(rows, 'fd_mean'), agg(rows, 'mil_max'), agg(rows, 'last_frame')))
    print('  木头≥400 的采样局数=%d/%d  木峰值>=400 局数=%d/%d'
          % (sum(1 for r in rows if r['wd_ge400'] > 0), n,
             sum(1 for r in rows if r['wd_max'] >= 400), n))
    print('  UPG（升铜器）时刻中位=%s分'
          % (('%.1f' % statistics.median([r['upg_min'] for r in rows if r['upg_min']]))
             if any(r['upg_min'] for r in rows) else '未升'))
    # ⚠ DEFEAT 是【逐帧重复打印】的（实测单局 33 次）⇒ 只看"该局是否判负"，不可按行求和
    print('  死区出现局数=%d/%d  峰值Idle>=5局数=%d/%d  判负局数=%d/%d  胜局=%d  升铜器局=%d/%d'
          % (sum(1 for r in rows if r['dead_n'] > 0), n,
             sum(1 for r in rows if r['idle_max'] >= 5), n,
             sum(1 for r in rows if r['lose'] > 0), n,
             sum(1 for r in rows if r['win'] > 0),
             sum(1 for r in rows if r['upg_min']), n))
    print()
    return rows


if __name__ == '__main__':
    D = r'C:\new-aoe3.0.7g'
    args = sys.argv[1:]
    for i in range(0, len(args) - 1, 2):
        tag, g = args[i], args[i + 1]
        ps = g if os.path.isabs(g) else os.path.join(D, g)
        report(tag, glob.glob(ps)[:60])
