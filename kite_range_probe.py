# -*- coding: utf-8 -*-
"""
kite_range_probe.py —— 「反攻时复合弓兵拉扯远了会打不到」取证探针（A/B 双批对照）

口径（严格按技能 §2.7/2.8/§2.16）：
  ait 行 = time | frame | color | flag | message     → split(' | ', 3)
  ⇒ p[1] = 权威帧号；**p[2] = color**；p[3] = "flag | message"
  ⚠ 两个易错点（都实际踩过）：
    ① color 在 p[2] 不是 p[3]（判终局胜负必须 p[2]=='black'）；
    ② HumanMove/HumanAction 的 flag = 指令来源阵营（0 = 我方 UsrAI）⇒ 统计我方【指令】必须先按 flag==0 过滤；
       而引擎侧战斗事件（`开始向X攻击` / `X死亡`）的 flag 是 **-1**，按 flag==0 过滤会把它们全部丢掉
       ⇒ 这类事件改为按 **SN 区间** 分敌我（敌脚本恒 91110~91168；我方自建恒 >91200）。

三段证据链：
  ① 撤退窗口（[KIT-R]）按【目标兵种】分类：量 dK、R、stage，并给出 dK>R 占比
  ② 【★命门】撤退落点距目标 vs 自身射程 R —— 落点 > R ⇒ 撤完出自己射程 ⇒ 必须走回去才有输出
     改后日志含 retD/tin/thr/melee 字段 ⇒ 直接读真值落点 = min(retD+SLACK, R)；改前日志无此字段 ⇒ 回退 R×(1.9|1.8)
  ③ [KIT-S]（SHOOT 相位每 100 帧采样）的 dK/R 分布 —— ≤1 即"SHOOT 时刻在射程内 = 真能打"
  ④ 产物量级账本（铁律 53：用产物量不用日志条数）——
     我方弓系【真开火/重新起手】次数、阵亡数、敌方脚本阵亡数、交换比
     ⚠ `开始向X攻击` 是"重新起手"事件（不是每次射击）⇒ 次数高 = 攻击被反复打断（拉扯churn），并**不是**输出高

用法：
  python kite_range_probe.py scan "vf_gsk_*.ait"        # 单批
  python kite_range_probe.py ab   "vf_gsk_*.ait" "vf_kb2_*.ait"   # 双批对照
  python kite_range_probe.py one  vf_gsk_1.ait 91396    # 单单位时间线
"""
import re, sys, glob, os, statistics as st

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BL = 1.0

AT_MELEE = {0, 3, 4, 5, 6, 10, 11, 13}
AT_RANGED = {1, 2, 8, 12, 14}
SORT_NAME = {0: '棍兵', 1: '投石兵', 2: '弓兵', 3: '侦察', 4: '剑士', 5: '精锐',
             6: '骑兵', 7: '船', 8: '投石车', 9: '祭司', 10: '方阵兵', 11: '战车',
             12: '战车弓', 13: '阔剑兵', 14: '复合弓'}

OUR_SN   = 91200            # > 此值 = 我方自建单位；敌脚本恒 ≤ 91168
LANDING_SLACK = 0.5         # 与 UsrAI.cpp 的 KITING_LANDING_SLACK 同口径

RE_KITR_NEW = re.compile(r'\[KIT-R f=(\d+)\] SN=(\d+) dK=([\d.]+) R=([\d.]+) stage=(\d+) stuck=(\d+) '
                         r'aged=(\d+) self=\(([\d.]+),([\d.]+)\) tgt=\(([\d.]+),([\d.]+)\) tSort=(-?\d+) '
                         r'retD=([\d.]+) tin=([\d.]+) thr=([\d.]+) melee=(\d+)')
RE_KITR_OLD = re.compile(r'\[KIT-R f=(\d+)\] SN=(\d+) dK=([\d.]+) R=([\d.]+) stage=(\d+) stuck=(\d+) '
                         r'aged=(\d+) self=\(([\d.]+),([\d.]+)\) tgt=\(([\d.]+),([\d.]+)\) tSort=(-?\d+)')
RE_KITS     = re.compile(r'\[KIT-S f=(\d+)\] SN=(\d+) phaseAged=\d+ dK=([\d.]+) R=([\d.]+) tSort=(-?\d+)')
RE_MOVE     = re.compile(r'HumanMove:([\u4e00-\u9fa5]+)\s+(\d+)\s+移动至\s+\(([\d.]+),([\d.]+)\)')
RE_ATK      = re.compile(r'HumanAction:([\u4e00-\u9fa5]+)\s+(\d+)\s+设置攻击目标为\s+([\u4e00-\u9fa5]+)\s+(\d+)')
RE_FIRE     = re.compile(r'([\u4e00-\u9fa5A-Za-z.]+)\(编号:(\d+)\)开始向')
RE_DEAD     = re.compile(r'([\u4e00-\u9fa5A-Za-z.]+)\(编号(\d+)\)死亡')
RE_WIN      = re.compile(r'VICTORY! Siege Workshop converted')
RE_LOSE     = re.compile(r'DEFEAT: (Priest killed|Town Center destroyed)')
ARCHER      = re.compile(r'^(复合弓兵|弓箭手)$')


def pct(a, b):
    return (100.0 * a / b) if b else float('nan')


def med(v):
    return st.median(v) if v else float('nan')


def parse(path):
    """→ dict(kitr=[], kits=[], cmds=[], fire={sn:n}, dead={sn:n}, lastfr, result)"""
    kitr, kits, cmds = [], [], []
    fire, dead = {}, {}
    fire_archer, dead_archer = {}, {}
    lastfr = 0
    last_black = None
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            if ' | ' not in line:
                continue
            p = line.split(' | ', 3)
            if len(p) < 4:
                continue
            try:
                fr = int(p[1])
            except ValueError:
                continue
            lastfr = max(lastfr, fr)
            color = p[2].strip()
            flag = p[3].split(' | ', 1)[0].strip() if ' | ' in p[3] else p[3].strip()
            msg = p[3].split(' | ', 1)[1] if ' | ' in p[3] else ''
            if color == 'black' and msg.strip():
                last_black = msg
            # —— 引擎侧战斗事件（flag=-1）：按 SN 分敌我 ——
            m = RE_FIRE.search(msg)
            if m:
                sn = int(m.group(2))
                fire[sn] = fire.get(sn, 0) + 1
                if ARCHER.match(m.group(1)):
                    fire_archer[sn] = fire_archer.get(sn, 0) + 1
            m = RE_DEAD.search(msg)
            if m:
                sn = int(m.group(2))
                dead[sn] = dead.get(sn, 0) + 1
                if ARCHER.match(m.group(1)):
                    dead_archer[sn] = dead_archer.get(sn, 0) + 1
            # —— 下方只统计【我方 UsrAI 指令/日志】（flag==0）——
            if flag != '0':
                continue
            m = RE_KITR_NEW.search(msg)
            if m:
                g = m.groups()
                kitr.append(dict(fr=int(g[0]), sn=int(g[1]), dK=float(g[2]), R=float(g[3]), stage=int(g[4]),
                                 stuck=int(g[5]), aged=int(g[6]), sx=float(g[7]), sy=float(g[8]),
                                 tx=float(g[9]), ty=float(g[10]), tSort=int(g[11]),
                                 retD=float(g[12]), tin=float(g[13]), thr=float(g[14]), melee=int(g[15])))
                continue
            m = RE_KITR_OLD.search(msg)
            if m:
                g = m.groups()
                kitr.append(dict(fr=int(g[0]), sn=int(g[1]), dK=float(g[2]), R=float(g[3]), stage=int(g[4]),
                                 stuck=int(g[5]), aged=int(g[6]), sx=float(g[7]), sy=float(g[8]),
                                 tx=float(g[9]), ty=float(g[10]), tSort=int(g[11]),
                                 retD=None, tin=None, thr=None, melee=None))
                continue
            m = RE_KITS.search(msg)
            if m:
                kits.append(dict(fr=int(m.group(1)), sn=int(m.group(2)),
                                 dK=float(m.group(3)), R=float(m.group(4)), tSort=int(m.group(5))))
                continue
            m = RE_MOVE.search(msg)
            if m:
                cmds.append(dict(fr=fr, sn=int(m.group(2)), kind='move', x=float(m.group(3)), y=float(m.group(4))))
                continue
            m = RE_ATK.search(msg)
            if m:
                cmds.append(dict(fr=fr, sn=int(m.group(2)), kind='atk', dn=m.group(3), dsn=int(m.group(4))))
    result = 'none'
    if last_black:
        if RE_WIN.search(last_black):
            result = 'win'
        elif RE_LOSE.search(last_black):
            result = 'lose'
        else:
            result = 'draw'
    return dict(kitr=kitr, kits=kits, cmds=cmds, fire=fire, dead=dead,
                fire_archer=fire_archer, dead_archer=dead_archer, lastfr=lastfr, result=result)


def landing(e):
    """撤退落点距目标（格）——改后取日志真值 retD；改前无字段则回退代码常量 R×(1.9|1.8)。"""
    if e['retD'] is not None:
        return min(e['retD'] + LANDING_SLACK, e['R'])
    return e['R'] * (1.9 if e['tSort'] in AT_MELEE else 1.8)


def load(pat):
    files = sorted(glob.glob(pat), key=lambda x: (len(x), x))
    return files, [parse(f) for f in files]


def summarize(pat, label, verbose=True):
    files, per = load(pat)
    allk = [e for d in per for e in d['kitr']]
    alls = [e for d in per for e in d['kits']]
    tot_fire = sum(n for d in per for sn, n in d['fire'].items() if sn > OUR_SN)
    tot_fire_archer = sum(n for d in per for sn, n in d['fire_archer'].items() if sn > OUR_SN)
    tot_our_dead_archer = sum(n for d in per for sn, n in d['dead_archer'].items() if sn > OUR_SN)
    tot_their_dead = sum(n for d in per for sn, n in d['dead'].items() if 91100 <= sn <= OUR_SN)
    tot_our_dead = sum(n for d in per for sn, n in d['dead'].items() if sn > OUR_SN)
    tot_last = sum(d['lastfr'] for d in per)
    W = sum(1 for d in per if d['result'] == 'win')
    L = sum(1 for d in per if d['result'] == 'lose')
    D = sum(1 for d in per if d['result'] == 'draw')
    r = dict(label=label, n=len(per), kitr=allk, kits=alls, fire=tot_fire, fire_archer=tot_fire_archer,
             their_dead=tot_their_dead, our_dead=tot_our_dead, our_dead_archer=tot_our_dead_archer,
             lastfr=tot_last, W=W, L=L, D=D, per=per, files=files)
    if verbose:
        print('=== %s : %s  (%d 局)   胜=%d 负=%d 未决=%d ===' % (label, pat, len(per), W, L, D))
        print('%-16s %7s %6s %6s %6s' % ('file', 'KIT-R', '远程', '近战', '其他'))
        for f, d in zip(files, per):
            k = d['kitr']
            nr = sum(1 for e in k if e['tSort'] in AT_RANGED)
            nm = sum(1 for e in k if e['tSort'] in AT_MELEE)
            print('%-16s %7d %6d %6d %6d   %s' % (os.path.basename(f), len(k), nr, nm, len(k) - nr - nm, d['result']))
        print()
        print('① 撤退窗口分类：')
        print('  %-10s %7s %8s %8s %9s %8s %8s' % ('目标', '条数', 'dK中位', 'R中位', 'dK>R占比', 'stage1', 'stage2'))
        for lbl, pred in (('远程', lambda e: e['tSort'] in AT_RANGED),
                          ('近战', lambda e: e['tSort'] in AT_MELEE),
                          ('其他', lambda e: e['tSort'] not in AT_RANGED and e['tSort'] not in AT_MELEE),
                          ('全部', lambda e: True)):
            s = [e for e in allk if pred(e)]
            if not s:
                print('  %-10s %7d' % (lbl, 0)); continue
            print('  %-10s %7d %8.1f %8.1f %8.1f%% %8d %8d' % (
                lbl, len(s), med([e['dK'] for e in s]), med([e['R'] for e in s]),
                pct(sum(1 for e in s if e['dK'] > e['R']), len(s)),
                sum(1 for e in s if e['stage'] == 1), sum(1 for e in s if e['stage'] == 2)))
        print()
        print('② 【命门】撤退落点距目标 vs 自身射程 R：')
        print('  %-14s %8s %11s %10s %10s %10s' % ('我方兵种(R)', '条数', '落点距目标', '自身射程R', '落点-R', '越界条数'))
        for R in sorted({e['R'] for e in allk}):
            s = [e for e in allk if e['R'] == R]
            lands = [landing(e) for e in s]
            over = sum(1 for e in s if landing(e) > e['R'] + 1e-9)
            print('  %-14s %8d %11.1f %10.1f %+10.1f %10d' % ('R=%.0f' % R, len(s), med(lands), R,
                                                              med(lands) - R, over))
        src = '' if allk and allk[0]['retD'] is not None else '  （本批日志无 retD 字段 ⇒ 落点按代码常量 R×1.9/1.8 回退）'
        print('  落点来源：%s%s' % ('日志真值 min(retD+0.5, R)' if allk and allk[0]['retD'] is not None else '回退常量',
                                    ''))
        print('  thr/tin 取值：%s' % (sorted({(e['thr'], e['tin'], e['retD'], e['melee']) for e in allk})[:6]
                                      if allk and allk[0]['retD'] is not None else 'n/a'))
        print()
        print('③ [KIT-S] SHOOT 相位采样（每 100 帧）的 dK/R —— ≤1 即"SHOOT 时刻在射程内=真能打"：')
        if alls:
            rr = [e['dK'] / e['R'] for e in alls]
            print('  样本=%d   dK/R 中位=%.2f   ≤1 占比=%.1f%%   >1.2 占比=%.1f%%' % (
                len(rr), med(rr), pct(sum(1 for x in rr if x <= 1.0), len(rr)),
                pct(sum(1 for x in rr if x > 1.2), len(rr))))
        else:
            print('  样本=0')
        print()
        print('④ 产物量级账本：')
        print('  我方弓系【重新起手】=%d (%.1f/局)  每千帧=%.2f' % (tot_fire_archer, tot_fire_archer / len(per), 1000.0 * tot_fire_archer / tot_last))
        print('  我方【全部单位】重新起手=%d  每千帧=%.2f' % (tot_fire, 1000.0 * tot_fire / tot_last))
        print('  我方阵亡=%d (其中弓系 %d)   敌方脚本阵亡=%d   交换比=%.2f' % (
            tot_our_dead, tot_our_dead_archer, tot_their_dead, tot_their_dead / tot_our_dead if tot_our_dead else -1))
        print()
    return r


def ab(p1, p2):
    a = summarize(p1, 'A 改前', verbose=False)
    b = summarize(p2, 'B 改后', verbose=False)

    def line(name, va, vb, fmt='%8.2f', delta=False):
        sa = fmt % va
        sb = fmt % vb
        sd = ''
        if delta and va:
            sd = '   %+6.1f%%' % ((vb - va) / va * 100.0)
        print('%-26s %s %s%s' % (name, sa, sb, sd))

    def cnt(x):
        return len(x) if isinstance(x, list) else x

    print('========== A/B 对照 ==========')
    print('  A(改前) = %s' % p1)
    print('  B(改后) = %s' % p2)
    print('%-26s %8s %8s' % ('指标', 'A 改前', 'B 改后'))
    print('%-26s %8d %8d' % ('局数', a['n'], b['n']))
    print('%-26s %8d %8d' % ('胜', a['W'], b['W']))
    print('%-26s %8d %8d' % ('负', a['L'], b['L']))
    print('%-26s %8d %8d' % ('未决(到帧上限)', a['D'], b['D']))
    print('%-26s %8d %8d' % ('末帧合计', a['lastfr'], b['lastfr']))
    print('-' * 46)
    line('撤退窗口数', cnt(a['kitr']), cnt(b['kitr']), '%8d', True)
    line('撤退窗口/千帧', 1000.0 * cnt(a['kitr']) / a['lastfr'], 1000.0 * cnt(b['kitr']) / b['lastfr'], '%8.2f', True)
    line('[KIT-S] 采样数', cnt(a['kits']), cnt(b['kits']), '%8d', True)
    line('我方弓系重新起手', cnt(a['fire_archer']), cnt(b['fire_archer']), '%8d', True)
    line('  /千帧', 1000.0 * cnt(a['fire_archer']) / a['lastfr'], 1000.0 * cnt(b['fire_archer']) / b['lastfr'], '%8.2f', True)
    line('我方阵亡', a['our_dead'], b['our_dead'], '%8d', True)
    line('  其中弓系阵亡', a['our_dead_archer'], b['our_dead_archer'], '%8d', True)
    line('敌方脚本阵亡', a['their_dead'], b['their_dead'], '%8d', True)
    line('交换比', a['their_dead'] / a['our_dead'] if a['our_dead'] else 0,
         b['their_dead'] / b['our_dead'] if b['our_dead'] else 0, '%8.2f', True)
    print('-' * 46)
    la = [landing(e) for e in a['kitr']]
    lb = [landing(e) for e in b['kitr']]
    line('★落点距目标(格) 中位', med(la), med(lb), '%8.1f')
    line('★落点 > 自身射程R (%)',
         pct(sum(1 for e in a['kitr'] if landing(e) > e['R'] + 1e-9), len(la)),
         pct(sum(1 for e in b['kitr'] if landing(e) > e['R'] + 1e-9), len(lb)), '%8.1f')
    line('★[KIT-S] dK/R 中位', med([e['dK'] / e['R'] for e in a['kits']]),
         med([e['dK'] / e['R'] for e in b['kits']]), '%8.2f')
    line('★[KIT-S] 在射程内 (%)',
         pct(sum(1 for e in a['kits'] if e['dK'] <= e['R']), len(a['kits'])),
         pct(sum(1 for e in b['kits'] if e['dK'] <= e['R']), len(b['kits'])), '%8.1f')
    return a, b


def one(path, sn):
    d = parse(path)
    k = [e for e in d['kitr'] if e['sn'] == sn]
    cmds = sorted([c for c in d['cmds'] if c['sn'] == sn], key=lambda c: c['fr'])
    kits = [e for e in d['kits'] if e['sn'] == sn]
    print('=== %s SN=%d  终局=%s  KIT-R=%d  KIT-S=%d  我方指令=%d ===' % (path, sn, d['result'], len(k), len(kits), len(cmds)))
    ev = [('KIT-R', e['fr'], 'dK=%.1f R=%.1f stage=%d stuck=%d aged=%d tgt=(%.1f,%.1f) tSort=%d(%s)%s' % (
        e['dK'], e['R'], e['stage'], e['stuck'], e['aged'], e['tx'] / BL, e['ty'] / BL, e['tSort'],
        SORT_NAME.get(e['tSort'], '村民/建筑'),
        '' if e['retD'] is None else ' retD=%.1f tin=%.1f thr=%.1f' % (e['retD'], e['tin'], e['thr']))) for e in k]
    ev += [('KIT-S', e['fr'], 'dK=%.1f R=%.1f %s' % (e['dK'], e['R'], '★在射程内' if e['dK'] <= e['R'] else '出射程')) for e in kits]
    for c in cmds:
        if c['kind'] == 'move':
            ev.append(('MOVE', c['fr'], '→(%.1f,%.1f)' % (c['x'] / BL, c['y'] / BL)))
        else:
            ev.append(('ATK', c['fr'], '→ %s %d' % (c['dn'], c['dsn'])))
    ev.sort(key=lambda x: x[1])
    for kind, fr, txt in ev:
        print('  f=%-6d %-6s %s' % (fr, kind, txt))


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == 'scan':
        summarize(sys.argv[2], '扫描')
    elif len(sys.argv) >= 4 and sys.argv[1] == 'ab':
        ab(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 4 and sys.argv[1] == 'one':
        one(sys.argv[2], int(sys.argv[3]))
    else:
        print(__doc__)
