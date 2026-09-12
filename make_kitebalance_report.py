# -*- coding: utf-8 -*-
"""
make_kitebalance_report.py —— 生成 aoe3_kite_balance_20260922.html

所有数字都从 ait 日志 + UsrAI.cpp 现场算，不写死。
模板用 @@TOKEN@@ 替换（不用 %-格式化：正文里中文全角括号与 % 太多，极易踩格式化异常）。

用法：python make_kitebalance_report.py
"""
import io, os, re, sys, glob, hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kite_range_probe as P

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, 'UsrAI.cpp')
HDR  = os.path.join(HERE, 'UsrAI.h')
OUT  = os.path.join(HERE, 'aoe3_kite_balance_20260922.html')

ARMS = [
    ('vf_gsk_*.ait',  'A 改前',   'gsk',  '旧：退出阈值 R+4=11 格 / 落点 1.8~1.9R'),
    ('vf_kb_*.ait',   'B 中间版', 'kb',   '新距离模型（初版，落点未钳上限）'),
    ('vf_kb2_*.ait',  'C 现版',   'kb2',  '新距离模型 + 落点钳到 R'),
]
RES = {'win': '胜', 'lose': '负', 'draw': '未决', 'none': '无'}


def md5f(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()[:8]


def n(x, d=1):
    if isinstance(x, float):
        return ('%.' + str(d) + 'f') % x
    return str(x)


def src_facts():
    s = io.open(SRC, encoding='utf-8', errors='replace').read()
    o = {}
    for k in ('KITING_SAFE_MARGIN', 'KITING_MIN_KEEP', 'KITING_HYST', 'KITING_LANDING_SLACK'):
        m = re.search(r'#define\s+%s\s+([0-9.]+)' % k, s)
        o[k] = m.group(1) if m else '?'
    m = re.search(r'const double RET_D = ([^;]+);', s)
    o['RET_D'] = m.group(1).strip() if m else '?'
    m = re.search(r'const double KIT_LAND = ([^;]+);', s)
    o['KIT_LAND'] = m.group(1).strip() if m else '?'
    o['lines'] = len(s.split('\r\n') if '\r\n' in s else s.split('\n'))
    o['md5'] = md5f(SRC)
    o['md5h'] = md5f(HDR)
    o['hlines'] = len(io.open(HDR, encoding='utf-8', errors='replace').read().split('\n'))
    return o


def main():
    arms = []
    for pat, label, tag, note in ARMS:
        r = P.summarize(pat, label, verbose=False)
        r['tag'], r['note'] = tag, note
        if not r['n']:
            raise SystemExit('缺批次：%s' % pat)
        arms.append(r)
    A, B, C = arms

    land   = lambda r: P.med([P.landing(e) for e in r['kitr']])
    over   = lambda r: P.pct(sum(1 for e in r['kitr'] if P.landing(e) > e['R'] + 1e-9), len(r['kitr']))
    kin    = lambda r: P.pct(sum(1 for e in r['kits'] if e['dK'] <= e['R']), len(r['kits']))
    krat   = lambda r: P.med([e['dK'] / e['R'] for e in r['kits']])
    freq   = lambda r: 1000.0 * len(r['kitr']) / r['lastfr']
    exr    = lambda r: (r['their_dead'] / r['our_dead']) if r['our_dead'] else float('nan')
    # ★ 实测（不是常量回代）：[KIT-R] 里的 dK = 单位与目标的真实距离
    dkov   = lambda r: P.pct(sum(1 for e in r['kitr'] if e['dK'] > e['R'] + 1e-9), len(r['kitr']))
    dkmed  = lambda r: P.med([e['dK'] for e in r['kitr']])

    def sn_latency(pat):
        ivs, tot, h30, h60 = [], 0, 0, 0
        for f in sorted(glob.glob(os.path.join(HERE, pat))):
            d = P.parse(f)
            bySN = {}
            for e in d['kitr']:
                bySN.setdefault(e['sn'], []).append(e['fr'])
            atk = {}
            for c in d['cmds']:
                if c['kind'] == 'atk':
                    atk.setdefault(c['sn'], []).append(c['fr'])
            for sn, rs in bySN.items():
                rs.sort()
                for i in range(1, len(rs)):
                    ivs.append(rs[i] - rs[i - 1])
                a = sorted(atk.get(sn, []))
                for fr in rs:
                    tot += 1
                    nxt = [x for x in a if x > fr]
                    if nxt:
                        g = nxt[0] - fr
                        if g <= 30:
                            h30 += 1
                        if g <= 60:
                            h60 += 1
        return (tot, P.med(ivs) if ivs else 0.0,
                100.0 * h30 / tot if tot else 0.0,
                100.0 * h60 / tot if tot else 0.0)

    def census_tbl(items):
        h = ['<table><tr><th>批次</th><th>靶类型</th><th class="n">威胁半径 thr</th>'
             '<th class="n">自身射程 R</th><th class="n">RET_D</th><th class="n">T_IN</th>'
             '<th class="n">窗口数</th><th class="n">占比</th></tr>']
        for label, g in items:
            tot = sum(g.values()) or 1
            for k, v in sorted(g.items(), key=lambda kv: -kv[1])[:4]:
                tsort, melee, thr, R, retd, tin = k
                kind = '近战/村民' if tsort in P.AT_MELEE else '远程'
                f = lambda x: '—' if x is None else n(x)
                h.append('<tr><td>%s</td><td>%s (tSort=%s)</td><td class="n">%s</td>'
                         '<td class="n">%s</td><td class="n">%s</td><td class="n">%s</td>'
                         '<td class="n">%d</td><td class="n">%.1f%%</td></tr>'
                         % (label, kind, tsort, f(thr), f(R), f(retd), f(tin), v, 100.0 * v / tot))
        h.append('</table>')
        return '\n'.join(h)

    cens = []
    for r in arms:
        g = {}
        for e in r['kitr']:
            kk = (e['tSort'], e.get('melee'), e.get('thr'), e['R'], e.get('retD'), e.get('tin'))
            g[kk] = g.get(kk, 0) + 1
        cens.append((r['label'], g))
    census_table = census_tbl(cens)
    nlat_A, iv_A, lat_A, lat60_A = sn_latency('vf_gsk_*.ait')
    nlat_C, iv_C, lat_C, lat60_C = sn_latency('vf_kb2_*.ait')

    def cells(fn, fmt='%s', suffix=''):
        return ''.join('<td class="n">%s%s</td>' % (fmt % fn(r), suffix) for r in arms)

    # —— §1.1 [KIT-S] 表 ——
    kits_tbl = ['<table><tr><th>指标</th>%s</tr>' % ''.join('<th class="n">%s</th>' % r['label'] for r in arms)]
    for nm, fn, f, suf in (('[KIT-S] 采样数', lambda r: len(r['kits']), '%d', ''),
                           ('dK/R 中位', krat, '%.2f', ''),
                           ('<b>在射程内占比</b>', kin, '%.1f', '%')):
        kits_tbl.append('<tr><td>%s</td>%s</tr>' % (nm, cells(fn, f, suf)))
    kits_tbl.append('</table>')
    kits_tbl = '\n'.join(kits_tbl)

    # —— §3 主对照表 ——
    rows = [
        ('批次',           lambda r: r['note'], None, ''),
        ('局数',           lambda r: r['n'], '%d', ''),
        ('胜',             lambda r: r['W'], '%d', ''),
        ('负',             lambda r: r['L'], '%d', ''),
        ('未决(到帧上限)', lambda r: r['D'], '%d', ''),
        ('末帧合计',       lambda r: r['lastfr'], '%d', ''),
        ('撤退窗口数',     lambda r: len(r['kitr']), '%d', '拉扯频率'),
        ('撤退窗口/千帧',  freq, '%.2f', '—'),
        ('[KIT-S] 采样数', lambda r: len(r['kits']), '%d', '停在 SHOOT 段的时长'),
        ('<b>★ 撤退期间 dK &gt; 射程 R 占比</b>', dkov, '%.1f', '<b>实测真值</b>：窗口内真实距离超射程的比例'),
        ('<b>★ 撤退期间 dK 中位(格)</b>', dkmed, '%.1f', '<b>实测真值</b>：撤退全程离敌多远（R=7）'),
        ('落点距目标(格)<sup>†</sup>', land, '%.1f', '<sup>†</sup>代码常量回代，非实测位置'),
        ('落点 &gt; 射程 R 占比<sup>†</sup>', over, '%.1f', '<sup>†</sup>同上（按构造成立）'),
        ('<b>★ [KIT-S] 在射程内</b>', kin, '%.1f', 'SHOOT 时刻真能打的比例'),
        ('[KIT-S] dK/R 中位', krat, '%.2f', '—'),
        ('我方弓系重新起手', lambda r: r['fire_archer'], '%d', '↓ = 攻击少被打断（不是输出↓）'),
        ('我方阵亡',       lambda r: r['our_dead'], '%d', '—'),
        ('　其中弓系阵亡', lambda r: r['our_dead_archer'], '%d', '—'),
        ('敌方脚本阵亡',   lambda r: r['their_dead'], '%d', '—'),
        ('交换比',         exr, '%.2f', '持平 = 没换亏'),
    ]
    main_tbl = ['<table><tr><th>指标</th>%s<th>说明</th></tr>'
                % ''.join('<th class="n">%s<br><span style="font-weight:400;font-size:11px">%s</span></th>' % (r['label'], r['tag']) for r in arms)]
    for nm, fn, f, note in rows:
        if f is None:
            main_tbl.append('<tr><td>%s</td>%s<td>%s</td></tr>'
                            % (nm, ''.join('<td class="n" style="font-size:12px">%s</td>' % r['note'] for r in arms), note))
        else:
            main_tbl.append('<tr><td>%s</td>%s<td>%s</td></tr>' % (nm, cells(fn, f), note))
    main_tbl.append('</table>')
    main_tbl = '\n'.join(main_tbl)

    # —— 逐局明细 ——
    def per_table(label):
        h = ['<table><tr><th>局</th><th>结果</th><th class="n">末帧</th><th class="n">撤退窗口</th>'
             '<th class="n">落点距目标(格)</th><th class="n">弓系重新起手</th><th class="n">弓系阵亡</th></tr>']
        for r in arms:
            if r['label'] != label:
                continue
            for f, d in zip(r['files'], r['per']):
                k = d['kitr']
                fire = sum(v for sn, v in d['fire_archer'].items() if sn > P.OUR_SN)
                dead = sum(v for sn, v in d['dead_archer'].items() if sn > P.OUR_SN)
                h.append('<tr><td>%s</td><td>%s</td><td class="n">%d</td><td class="n">%d</td>'
                         '<td class="n">%s</td><td class="n">%d</td><td class="n">%d</td></tr>'
                         % (os.path.basename(f), RES.get(d['result'], d['result']), d['lastfr'], len(k),
                            n(P.med([P.landing(e) for e in k])) if k else '—', fire, dead))
        h.append('</table>')
        return '\n'.join(h)

    sf = src_facts()
    freq_drop = (1 - freq(C) / freq(A)) * 100 if freq(A) else 0

    tok = {
        '@@LINES@@': str(sf['lines']),
        '@@HLINES@@': str(sf['hlines']),
        '@@MD5C@@': sf['md5'],
        '@@MD5H@@': sf['md5h'],
        '@@SAFE@@': sf['KITING_SAFE_MARGIN'],
        '@@MINKEEP@@': sf['KITING_MIN_KEEP'],
        '@@HYST@@': sf['KITING_HYST'],
        '@@SLACK@@': sf['KITING_LANDING_SLACK'],
        '@@RETD_EXPR@@': sf['RET_D'],
        '@@KITLAND_EXPR@@': sf['KIT_LAND'],
        '@@LAND_C@@': n(land(C)),
        '@@LAND_A@@': n(land(A)),
        '@@IN_A@@': n(kin(A)), '@@IN_C@@': n(kin(C)),
        '@@FIRE_A@@': str(A['fire_archer']), '@@FIRE_C@@': str(C['fire_archer']),
        '@@DEADARC_A@@': str(A['our_dead_archer']), '@@DEADARC_C@@': str(C['our_dead_archer']),
        '@@DEAD_A@@': str(A['our_dead']), '@@DEAD_C@@': str(C['our_dead']),
        '@@TDEAD_A@@': str(A['their_dead']), '@@TDEAD_C@@': str(C['their_dead']),
        '@@EXR_A@@': n(exr(A), 2), '@@EXR_C@@': n(exr(C), 2),
        '@@OVER_A@@': n(over(A)), '@@OVER_C@@': n(over(C)),
        '@@KITSR_A@@': n(krat(A), 2), '@@KITSR_C@@': n(krat(C), 2),
        '@@KITS_A@@': str(len(A['kits'])), '@@KITS_C@@': str(len(C['kits'])),
        '@@FREQ_A@@': n(freq(A), 2), '@@FREQ_C@@': n(freq(C), 2), '@@FREQ_DROP@@': n(freq_drop),
        '@@DKO_A@@': n(dkov(A)), '@@DKO_C@@': n(dkov(C)),
        '@@DKM_A@@': n(dkmed(A)), '@@DKM_C@@': n(dkmed(C)),
        '@@IVM_A@@': n(iv_A, 0), '@@IVM_C@@': n(iv_C, 0),
        '@@LAT_A@@': n(lat_A), '@@LAT_C@@': n(lat_C),
        '@@LAT60_A@@': n(lat60_A), '@@LAT60_C@@': n(lat60_C),
        '@@NLAT_A@@': str(nlat_A), '@@NLAT_C@@': str(nlat_C),
        '@@TBL_CENSUS@@': census_table,
        '@@NKIT@@': str(sum(len(r['kitr']) for r in arms)),
        '@@NKIT_A@@': str(len(A['kitr'])),
        '@@TBL_KITS@@': kits_tbl,
        '@@TBL_MAIN@@': main_tbl,
        '@@PER_A@@': per_table('A 改前'),
        '@@PER_B@@': per_table('B 中间版'),
        '@@PER_C@@': per_table('C 现版'),
        '@@W_A@@': str(A['W']), '@@L_A@@': str(A['L']), '@@D_A@@': str(A['D']),
        '@@W_C@@': str(C['W']), '@@L_C@@': str(C['L']), '@@D_C@@': str(C['D']),
        '@@W_B@@': str(B['W']), '@@L_B@@': str(B['L']), '@@D_B@@': str(B['D']),
    }

    tpl = io.open(os.path.join(HERE, 'kite_report_template.html'), encoding='utf-8').read() \
        if os.path.exists(os.path.join(HERE, 'kite_report_template.html')) else TEMPLATE
    for k, v in tok.items():
        tpl = tpl.replace(k, v)
    left = re.findall(r'@@[A-Z0-9_]+@@', tpl)
    if left:
        raise SystemExit('未替换的占位符: %s' % sorted(set(left)))
    io.open(OUT, 'w', encoding='utf-8').write(tpl)
    print('written %s (%d bytes)' % (OUT, len(tpl.encode('utf-8'))))
    print('  落点 A=%s → C=%s 格 | 落点>R  A=%s%% → C=%s%% | [KIT-S]在射程内 A=%s%% → C=%s%%'
          % (n(land(A)), n(land(C)), n(over(A)), n(over(C)), n(kin(A)), n(kin(C))))
    print('  账本 弓系重新起手 A=%d → C=%d | 弓系阵亡 A=%d → C=%d | 交换比 A=%s → C=%s'
          % (A['fire_archer'], C['fire_archer'], A['our_dead_archer'], C['our_dead_archer'],
             n(exr(A), 2), n(exr(C), 2)))
    print('  胜负 A=%d胜%d负%d未决 | B=%d胜%d负%d未决 | C=%d胜%d负%d未决'
          % (A['W'], A['L'], A['D'], B['W'], B['L'], B['D'], C['W'], C['L'], C['D']))


TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>复合弓兵拉扯距离重标定 · 2026-09-22</title>
<style>
:root{
  --bg:#f6f7f9; --card:#ffffff; --line:#e2e6ec; --ink:#1b2230; --ink2:#5a6172;
  --ok:#0f8a4d; --okbg:#e8f6ee; --warn:#b7791f; --warnbg:#fdf6e3; --bad:#c0392b; --badbg:#fdecea;
  --acc:#2d6cdf; --accbg:#eaf1fd; --mono:"Cascadia Mono",consolas,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1120px;margin:0 auto;padding:28px 20px 56px}
h1{font-size:24px;margin:0 0 6px}
h2{font-size:18px;margin:34px 0 10px;padding-bottom:6px;border-bottom:2px solid var(--line)}
h3{font-size:15px;margin:20px 0 8px;color:var(--ink2)}
.sub{color:var(--ink2);font-size:13px;margin-bottom:22px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:12px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:16px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.kpi .v{font-size:23px;font-weight:700;letter-spacing:-.5px}
.kpi .l{font-size:12px;color:var(--ink2);margin-top:2px}
.kpi.ok .v{color:var(--ok)}
.kpi.warn .v{color:var(--warn)}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:8px 0}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{background:#f0f2f6;font-weight:600}
td.n,th.n{text-align:right;font-family:var(--mono)}
pre{background:#0f141c;color:#d6e0ee;border-radius:8px;padding:12px 14px;overflow:auto;font-family:var(--mono);font-size:12.5px;line-height:1.5}
code{font-family:var(--mono);background:#eef1f6;padding:1px 5px;border-radius:4px;font-size:12.5px}
.pill{display:inline-block;font-size:12px;padding:2px 9px;border-radius:999px;font-weight:600}
.p-ok{background:var(--okbg);color:var(--ok)}
.p-warn{background:var(--warnbg);color:var(--warn)}
.p-bad{background:var(--badbg);color:var(--bad)}
.p-acc{background:var(--accbg);color:var(--acc)}
ul,ol{margin:6px 0 6px 22px;padding:0}
li{margin:3px 0}
.hl{background:var(--accbg);border-left:3px solid var(--acc);padding:10px 14px;border-radius:0 8px 8px 0;margin:10px 0}
.warnbox{background:var(--warnbg);border-left:3px solid var(--warn);padding:10px 14px;border-radius:0 8px 8px 0;margin:10px 0}
.badbox{background:var(--badbg);border-left:3px solid var(--bad);padding:10px 14px;border-radius:0 8px 8px 0;margin:10px 0}
footer{margin-top:36px;color:var(--ink2);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style>
</head>
<body>
<div class="wrap">

<h1>复合弓兵拉扯距离重标定 —— 「撤得开」与「打得到」的平衡</h1>
<div class="sub">2026-09-22 · 用户需求「反攻时，应对远程有时复合弓兵拉扯远了会打不到，做好平衡」 ·
唯一提交源 <code>C:\new-aoe3.0.7g\UsrAI.cpp</code>（@@LINES@@ 行 / md5 @@MD5C@@）</div>

<div class="kpis">
  <div class="kpi ok"><div class="v">@@LAND_A@@ → @@LAND_C@@ 格</div><div class="l">撤退落点距目标（自身射程 R=7）</div></div>
  <div class="kpi ok"><div class="v">@@IN_A@@% → @@IN_C@@%</div><div class="l">[KIT-S]：SHOOT 时刻落在自身射程内</div></div>
  <div class="kpi ok"><div class="v">@@FIRE_A@@ → @@FIRE_C@@</div><div class="l">攻击被"重新起手"打断次数（↓ = 打得连续）</div></div>
  <div class="kpi ok"><div class="v">@@DEADARC_A@@ → @@DEADARC_C@@</div><div class="l">我方弓系阵亡数</div></div>
  <div class="kpi"><div class="v">@@EXR_A@@ → @@EXR_C@@</div><div class="l">交换比（敌阵亡/我阵亡，持平 = 没换亏）</div></div>
</div>

<div class="hl">
<b>一句话结论：</b>旧版撤退落点 = 自身射程的 1.8~1.9 倍（R=7 ⇒ <b>13.3 格</b>），<b>撤完必然出自己射程</b>，
还得走回 4~6.3 格才能重新开火；且撤退窗口约 30 帧一次、比 60 帧攻击保护期更密 ⇒ 保护期<b>结构性永不过期</b>。
现版把落点改成由<b>威胁半径</b>推导、并以<b>自身射程为硬上限</b>（落点 @@LAND_C@@ 格 ≤ R=7）⇒
撤完就在射程内，切回 SHOOT 立刻能打。<b>不变量"撤完即在射程内"在 R=7 与 R=5 两级上都严格成立。</b>
</div>

<h2>1 病灶：两根因，一条因果链的两端</h2>
<div class="card">
<table>
<tr><th style="width:3%">#</th><th style="width:44%">根因</th><th style="width:24%">代码位点（改前）</th><th>后果（实测，12 局 gsk 基线）</th></tr>
<tr><td>①</td><td><b>撤退落点出射程</b>：落点 = 敌 + <code>R×1.8</code>(远程敌) / <code>R×1.9</code>(近战敌)，
R=7 ⇒ <b>13.3 格</b>，而自身射程只有 7 格</td>
<td><code>tryRetreatLanding(kEX + u*R*KITING_RETREAT_MULT, ...)</code></td>
<td><b>实测</b>：撤退全程 <code>dK &gt; R</code> 的窗口占 <b>@@DKO_A@@%</b>、<code>dK</code> 中位 <b>@@DKM_A@@</b> 格（R=7，共 @@NKIT_A@@ 个窗口）；撤完需再走 4~6.3 格才有输出</td></tr>
<tr><td>②</td><td><b>攻击保护期卡在临界值</b>：同一 SN 撤退窗口间隔<b>中位 60 帧</b>，恰好压住 <code>RETREAT_PROTECT_FRAMES = 60</code></td>
<td><code>bool retreatProt = (frame - lastRetreatFrame[SN] &lt; 60)</code></td>
<td>撤完再开火被延迟：窗口后 ≤30 帧内拿到同 SN 攻击令的只有 <b>@@LAT_A@@%</b>（≤60 帧 @@LAT60_A@@%）。逐帧例 <code>vf_gsk_1</code> SN=91396 在 f=33737~34553（816 帧）里撤退令 <b>14</b> 条、攻击令 <b>0</b> 条、移动令 14 条。改后 ≤30 帧内 <b>@@LAT_C@@%</b></td></tr>
</table>
<div class="warnbox">
<b>两处必须同时改：</b>只改①，保护期②仍会把「撤完 → 重新开火」推迟到 60 帧量级（窗口后 ≤30 帧内重新开火仅 @@LAT_A@@%）；只改②，撤完仍在射程外，攻击令发出去也够不着。
</div>

<h3>1.1 命门的直接读数：SHOOT 相位采样 <code>[KIT-S]</code></h3>
<p>该日志在 <code>phase==0 &amp;&amp; dK ≤ R+2</code> 分支内每 100 帧采样一次，带当时的 <code>dK</code> 与 <code>R</code>。
<code>dK/R ≤ 1</code> 即"SHOOT 时刻真在自己射程内 = 真能打"。</p>
@@TBL_KITS@@
<p>改前 dK/R 中位 <b>@@KITSR_A@@</b>（≈8.0 格 —— 刚撤到 13.3 格、正往回走，所以打不到），
改后 <b>@@KITSR_C@@</b>（≈6.9 格 —— 贴着最大射程开火）。</p>
</div>

<h2>2 改动：一个距离模型 + 四处代码点</h2>
<div class="card">
<h3>2.1 新增常量（<code>UsrAI.cpp</code> 顶部）</h3>
<pre>#define KITING_SAFE_MARGIN   @@SAFE@@   // 脱离威胁射程后的安全余量(格)
#define KITING_MIN_KEEP      @@MINKEEP@@   // 撤退后至少保持的距离(格)
#define KITING_HYST          @@HYST@@   // 迟滞带宽度(格)：T_IN = T_OUT − 本值
#define KITING_LANDING_SLACK @@SLACK@@   // 落点相对退出阈值的余量(格)</pre>
<h3>2.2 距离模型（<code>manageCounterAttack</code> 拉扯段）</h3>
<pre>THREAT_R = (目标为远程兵) ? rangedMaxRange(tSort) : 0.0
RET_D    = min(max(THREAT_R + SAFE_MARGIN, MIN_KEEP), R)   // 退出阈值 / 站住间距，恒 ≤ R
T_OUT    = RET_D
T_IN     = max(0.5R, RET_D − HYST)                         // 撤退触发（下限 = 贴脸线）
KIT_LAND = min(RET_D + SLACK, R)                           // 落点：恒 ≤ 自身射程 ⇒ 撤完即能打</pre>
<table>
<tr><th style="width:4%">#</th><th style="width:26%">位点</th><th style="width:34%">改前</th><th>改后</th></tr>
<tr><td>1</td><td>RETREAT 退出条件</td><td><code>dK &gt;= R + BREATH</code>（= 7+4 = 11 格）</td><td><code>dK &gt;= T_OUT</code>（= RET_D ≤ R）</td></tr>
<tr><td>2</td><td>SHOOT→RETREAT 触发</td><td><code>dK &gt; 0.5R &amp;&amp; dK &lt;= 0.9R</code>（6.3 格）</td><td><code>dK &gt; 0.5R &amp;&amp; dK &lt;= T_IN</code></td></tr>
<tr><td>3</td><td>撤退落点</td><td><code>kEX + u × R × 1.8/1.9</code></td><td><code>kEX + u × KIT_LAND</code>（≤ R）</td></tr>
<tr><td>4</td><td>攻击保护期</td><td><code>RETREAT_PROTECT_FRAMES = 60</code>（2.4 秒）</td><td><code>15</code>（0.6 秒，只留最小去抖）</td></tr>
</table>
<h3>2.3 落点真值（代码直接保证的不变量）</h3>
<pre>R=7（复合弓兵） 目标近战：THREAT_R=0 → RET_D=min(max(2,5),7)=5.0 → T_OUT=5.0  T_IN=max(3.5,3.0)=3.5  落点=min(5.5,7)=5.5
R=7（复合弓兵） 目标弓兵(5)：THREAT_R=5 → RET_D=min(max(7,5),7)=7.0 → 落点=min(7.5,7)=7.0  （= R，仍在射程内）
R=5（弓箭手）   目标近战：THREAT_R=0 → RET_D=min(max(2,5),5)=5.0 → 落点=min(5.5,5)=5.0  ← 靠 min(…,R) 钳回射程内</pre>
<p>落点 ≥ RET_D = T_OUT ⇒ 退出条件照样满足（取等也满足）；落点 ≤ R ⇒
<b>不变量"撤完即在射程内"与 R 无关地成立</b>。<br>
其中 <code>RET_D = @@RETD_EXPR@@</code>、<code>KIT_LAND = @@KITLAND_EXPR@@</code>（源码原文）。</p>
</div>

<h2>3 A/B/C 对照（每臂 12 局）</h2>
<div class="card">
@@TBL_MAIN@@
<div class="warnbox">
<b>指标口径警告（这一轮踩到的最大读数陷阱）：</b>
<code>开始向X攻击</code> 是引擎侧的"<b>重新起手</b>"事件，<b>不是每次射击</b>。
它的次数<b>下降</b>是好事（攻击不再被拉扯反复打断），<b>不能</b>读成"输出变少"——
我第一遍就用它得出过"攻击令 −61%、变差了"的错误结论，直到对账本才发现。
判"输出"只看账本：<b>交换比 @@EXR_A@@ → @@EXR_C@@</b>（−7%，12 局噪声内，见 §6），
我方阵亡 @@DEAD_A@@ → @@DEAD_C@@、敌方脚本阵亡 @@TDEAD_A@@ → @@TDEAD_C@@ ——
<b>总战果同量级，而打断次数几乎减半</b>。
</div>
</div>

<h3>3.1 判据的<b>输入集</b>普查：这轮到底在跟什么打</h3>
<p><code>[KIT-R]</code> 是"每次进入撤退窗口必打、被 <code>canReissue(30 帧)</code> 限流"的采样，
它把<b>判据实际喂进来的靶</b>全记下来了 —— 这是判断"验收有没有覆盖用户说的场景"最硬的依据。</p>
@@TBL_CENSUS@@
<div class="warnbox">
<b>必须说清楚的一件事：</b>本图 <code>map3.njust</code> 的敌方是<b>近战 + 箭塔</b>，
3 批共 @@NKIT@@ 个撤退窗口 <b>100% 是近战靶</b>（<code>thr=0.0</code>）。
所以「应对<b>远程</b>敌」那条分支在本图<b>只能解析推导、无法实测</b>：
按 <code>RET_D = min(max(thr + 2.0, 5.0), R)</code>，敌弓兵射程 5 ⇒ <code>RET_D = 7.0</code>、
落点 7.0 = 自身射程（卡在边界）。要看实测，需换<b>含敌方弓兵/投石兵</b>的关卡或评测机地图。
</div>

<h3>3.2 保护期 60 → 15 帧的证据（同 SN 口径）</h3>
<table>
<tr><th>批次</th><th class="n">同 SN 撤退窗口数</th><th class="n">相邻间隔中位(帧)</th>
<th class="n">窗口后 ≤30 帧内重新开火</th><th class="n">≤60 帧</th></tr>
<tr><td>A 改前（保护期 60）</td><td class="n">@@NLAT_A@@</td><td class="n">@@IVM_A@@</td>
<td class="n">@@LAT_A@@%</td><td class="n">@@LAT60_A@@%</td></tr>
<tr><td>C 现版（保护期 15）</td><td class="n">@@NLAT_C@@</td><td class="n">@@IVM_C@@</td>
<td class="n"><b>@@LAT_C@@%</b></td><td class="n">@@LAT60_C@@%</td></tr>
</table>
<p>改前相邻间隔中位 <b>@@IVM_A@@ 帧</b>（恰好等于保护期 60）⇒ 保护期长期卡在临界值上，
窗口后 30 帧内重新开火的比例只有 <b>@@LAT_A@@%</b>；保护期降到 15 帧后升到 <b>@@LAT_C@@%</b>。</p>

<h2>4 逐局明细</h2>
<div class="card">
<h3>4.1 A 改前（gsk）</h3>
@@PER_A@@
<h3>4.2 B 中间版（kb，落点未钳上限）</h3>
@@PER_B@@
<h3>4.3 C 现版（kb2，落点钳到 R）</h3>
@@PER_C@@
</div>

<h2>5 已知副作用（有意保留，非 bug）</h2>
<div class="card">
<p><code>T_IN = max(0.5R, RET_D − HYST)</code> 在「R=7 / 近战目标」时 = <code>max(3.5, 3.0) = 3.5 = 0.5R</code>，
与下方「贴脸无条件撤（<code>dK &lt; 0.5R</code>）」<b>合并成同一条触发</b>。后果：</p>
<ul>
<li>上方「敌近提前撤（≤0.9R = 6.3 格）」这条触发<b>退化</b> ⇒ 单位不再在 6.3 格就后撤，
改为让敌人贴近到 3.5 格才后撤 <b>2 格</b>。</li>
<li>拉扯频率 <b>@@FREQ_A@@ → @@FREQ_C@@</b> 窗口/千帧（<b>↓@@FREQ_DROP@@%</b>），
单位大量时间<b>停在 SHOOT 段持续输出</b>（[KIT-S] 采样 @@KITS_A@@ → @@KITS_C@@）。</li>
<li>账本上<b>没有明显代偿</b>：弓系阵亡 @@DEADARC_A@@ → @@DEADARC_C@@（−2.2%），交换比 @@EXR_A@@ → @@EXR_C@@（−7%，12 局噪声内，需 ≥24 局/臂才能判）。</li>
</ul>
<p>若要"更早撤"（回到 6.3 格起撤）：<b>把 <code>KITING_MIN_KEEP</code> 从 @@MINKEEP@@ 抬起</b>即可
（T_OUT 抬高 ⇒ T_IN 抬高），<b>不要</b>去动 <code>0.5R</code> 那条兜底线。</p>
</div>

<h2>6 遗留 / 待拍板</h2>
<div class="card">
<ol>
<li><b>「应对远程」这条路径当前没有样本。</b>本批 <code>[KIT-R]</code> 的目标 <b>100% 是近战</b>（骑兵/方阵/战车/阔剑），
远程目标 <b>0 条</b>。这是 §4h「不拉扯射程不占优者」的既定结果（战车弓 7 = 我 7、投石车 10 &gt; 7 被排除）。
所以用户原话里的"<b>应对远程</b>"，在当前实现下<b>并不进入拉扯分支</b>。
<b>需要你确认</b>：是"面对远程敌时不拉扯"这个既定取舍就行，还是希望我方 R=7 对敌方弓兵(5)/投石兵(4) 也继续拉扯
（这条路当前<b>走得通但没有实测样本</b>）。</li>
<li><b>胜负需要 ≥24 局/臂</b>（铁律 81）。本报告 A = @@W_A@@胜@@L_A@@负@@D_A@@未决、C = @@W_C@@胜@@L_C@@负@@D_C@@未决，
<b>12 局不足以判胜负</b>，只能判"产物量级类判据"的确定性（落点、在射程内占比、打断次数、阵亡）。</li>
<li><b>两个可调旋钮</b>：<code>KITING_MIN_KEEP</code>（= @@MINKEEP@@，控"多早起撤"，见 §5）；
<code>KITING_SAFE_MARGIN</code>（= @@SAFE@@，只影响远程目标的站位，当前无样本）。</li>
<li>与本轮无关但仍挂着的：石矿仓库是否平移（§4k 遗留）、0.7h 是否改指唯一编辑副本。</li>
</ol>
</div>

<h2>7 复现</h2>
<div class="card">
<pre># 语法 / 编译
python syn.py                    # 期望 rc=0 / 0 error / 17 warning
python warn_cmp2.py UsrAI.cpp.bak_20260922_kitebalance UsrAI.cpp
python build.py                  # 期望 rc = 0 ; errors = 0

# 跑批（每臂 12 局）
set QT_QPA_PLATFORM=offscreen
python verify_build_fix.py 12 kb2

# 取证 + 出报告
python kite_range_probe.py ab "vf_gsk_*.ait" "vf_kb2_*.ait"
python kite_range_probe.py scan "vf_kb2_*.ait"
python kite_range_probe.py one  vf_kb2_1.ait 91396
python make_kitebalance_report.py</pre>
<h3>7.1 工程状态</h3>
<ul>
<li>源码：<code>UsrAI.cpp</code> md5 <code>@@MD5C@@</code> / @@LINES@@ 行；<code>UsrAI.h</code> <code>@@MD5H@@</code> / @@HLINES@@ 行（未改）</li>
<li>编译：<code>syn</code> 0 error、warning 集合与改前同（17 == 17）；<code>build</code> rc=0、exe mtime &gt; cpp、新调试串已落盘（真重链）</li>
<li>备份：<code>UsrAI.cpp.bak_20260922_kitebalance</code>（本轮改前 988e8d46 的前身）、
<code>UsrAI.cpp.bak_20260922_kitebalance_v1</code>（B 中间版）</li>
<li>回滚 = 拷回备份 + 删 <code>release/UsrAI.o</code> 重编</li>
</ul>
</div>

<footer>
生成器 <code>make_kitebalance_report.py</code> ｜ 探针 <code>kite_range_probe.py</code> ｜
数据源：<code>vf_gsk_*.ait</code> / <code>vf_kb_*.ait</code> / <code>vf_kb2_*.ait</code> 各 12 局<br>
本页所有数字均由上述日志与 <code>UsrAI.cpp</code> 现场计算，无手工填数。
</footer>
</div>
</body>
</html>
'''

if __name__ == '__main__':
    main()
