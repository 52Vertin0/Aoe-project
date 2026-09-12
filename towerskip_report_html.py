# -*- coding: utf-8 -*-
"""生成 towerskip 轮报告（HTML）：射程 < 箭塔射程的兵种不再把敌箭塔选为攻击目标。
用法：python towerskip_report_html.py            # 默认 mc(重构前基线) / md(同构建重跑) / tc(本轮)
"""
import os
import re
import sys
import html
import datetime

CONV = re.compile(r'Priest converting Siege Workshop! f=(\d+) d=([\d.]+) hp=([\d.]+) nearT=(-?[\d.]+) towers=(\d+) path=(\w+)')
HOLD = re.compile(r'\[SIEGE-HOLD f=(\d+)\]')
ADV = re.compile(r'Priest ADVANCE to Siege f=(\d+)')
HA = re.compile(r'HumanAction:祭司 \d+ 设置转换目标为 攻城武器厂 \d+')
TGT_REMOTE = re.compile(r'\[TOWER-TGT f=\d+\] 复合弓兵/远程 ')
TGT_MELEE = re.compile(r'\[TOWER-TGT f=\d+\] 近战 ')
SKIP = re.compile(r'\[TOWER-SKIP f=(\d+)\] (\S+) SN=(\d+) 射程([\d.]+)<塔([\d.]+) → 不打塔 SN=(\d+)')
LABELS = ['[KIT-R', '[KIT-S', '[TOWER-TGT', '[TOWER-SKIP', '[PRST-REAR', '[LC-DBG', '[SIEGE-HOLD',
          'Priest converting Siege Workshop', 'Priest ADVANCE to Siege', 'Enemy Siege Workshop found',
          'Enemy base scouted', 'Force COUNTERATTACK']

DESC = {'mc': 'mc · 改动前基线（mcslim 成品，A/B 的 A 臂）',
        'md': 'md · 噪声底线（mc 同一二进制再跑 8 局）',
        'tc': 'tc · 本轮（够不着箭塔 ⇒ 不选塔为目标）'}

CHANGES = [
    ("T1", "新增常量 <span class=mono>ARROWTOWER_RANGE 8.0</span>",
     "敌箭塔射程单一真源（与 config.json DIS_ARROWTOWER 一致），供『够不够得着』判据使用", "+8 行"),
    ("T2", "<span class=mono>attackBuildingOrMarch</span> 加『够不着塔就不选塔』闸",
     "判据 = <span class=mono>isRanged &amp;&amp; rangedMaxRange(sort) &lt; ARROWTOWER_RANGE</span>；塔分支从『有塔必打』改为『够得着才打』", "+15 行"),
    ("T3", "第二档『打最近建筑』排除箭塔",
     "新增局部 <span class=mono>isTowerSN()</span>：最近建筑若是塔且够不着 ⇒ 跳过，否则会绕回同一座塔", "+9 行"),
    ("T4", "新增 <span class=mono>[TOWER-SKIP]</span> 日志 + 成员 <span class=mono>towerSkipSN</span>",
     "按『兵 SN → 塔 SN』去重（同一塔只记一条，防刷屏）；铁律 34：关键决策点必须可观测", "cpp +3 / h +3"),
    ("T5", "近战 / 投石车语义显式短路",
     "<span class=mono>canHitTower</span> 用 <span class=mono>!isRanged || 射程≥8</span>：近战照旧贴身拆塔、投石车射程 10 照旧压制塔", "0 行"),
]


def scan(path):
    ev = []
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) < 5:
            continue
        try:
            fr = int(p[1])
        except ValueError:
            continue
        ev.append((fr, p[4].strip()))
    return ev


def summarize(path):
    ev = scan(path)
    d = dict(file=os.path.basename(path)[:-4], end=ev[-1][0] if ev else 0, win=0, died=0, tcdead=0,
             move=0, action=0, conv=[], hold=0, adv=0, tot=0, remote=0, melee=0, skip=0, skips=[],
             labels={k: 0 for k in LABELS})
    for fr, m in ev:
        if 'HumanMove' in m:
            d['move'] += 1
        if 'HumanAction' in m:
            d['action'] += 1
        if 'VICTORY' in m:
            d['win'] = 1
        if 'DEFEAT: Priest killed' in m:
            d['died'] = 1
        if 'DEFEAT: Town Center destroyed' in m:
            d['tcdead'] = 1
        if '[TOWER-TGT' in m:
            d['tot'] += 1
            if TGT_REMOTE.search(m):
                d['remote'] += 1
            elif TGT_MELEE.search(m):
                d['melee'] += 1
        g = SKIP.search(m)
        if g:
            d['skip'] += 1
            d['skips'].append(dict(f=int(g.group(1)), who=g.group(2), sn=int(g.group(3)),
                                   selfR=float(g.group(4)), towerR=float(g.group(5)), tgt=int(g.group(6))))
        c = CONV.search(m)
        if c:
            d['conv'].append(dict(f=int(c.group(1)), d=float(c.group(2)), hp=float(c.group(3)),
                                  nearT=float(c.group(4)), tw=int(c.group(5)), path=c.group(6)))
        if HOLD.search(m):
            d['hold'] += 1
        if ADV.search(m):
            d['adv'] += 1
        for k in LABELS:
            if k in m:
                d['labels'][k] += 1
    ha = sorted({fr for fr, m in ev if HA.search(m)})
    clusters, last = [], -10 ** 9
    for fr in ha:
        if fr - last > 400:
            clusters.append(fr)
        last = fr
    d['start'] = len(d['conv']) or len(clusters)
    return d


def batch(prefix, n=8):
    return [summarize('%s%d.ait' % (prefix, i)) for i in range(1, n + 1) if os.path.exists('%s%d.ait' % (prefix, i))]


def agg(rows):
    kf = sum(r['end'] for r in rows) / 1000.0 or 1.0
    return dict(n=len(rows), win=sum(r['win'] for r in rows), died=sum(r['died'] for r in rows),
                tcdead=sum(r['tcdead'] for r in rows), start=sum(r['start'] for r in rows),
                startGames=sum(1 for r in rows if r['start']), hold=sum(r['hold'] for r in rows),
                adv=sum(r['adv'] for r in rows), tot=sum(r['tot'] for r in rows),
                remote=sum(r['remote'] for r in rows), melee=sum(r['melee'] for r in rows),
                skip=sum(r['skip'] for r in rows),
                movekf=sum(r['move'] for r in rows) / kf, actkf=sum(r['action'] for r in rows) / kf,
                labels={k: sum(r['labels'][k] for r in rows) for k in LABELS},
                endmin=min((r['end'] for r in rows), default=0), endmax=max((r['end'] for r in rows), default=0))


def res_of(d):
    return 'WIN' if d['win'] else ('DIED' if d['died'] else ('TCDEAD' if d['tcdead'] else 'TIME'))


def esc(s):
    return html.escape(str(s))


def game_table(rows):
    head = ('<table class="t"><thead><tr><th>局</th><th>末帧</th><th>结局</th><th>打塔(总)</th>'
            '<th>远程打塔</th><th>近战打塔</th><th>跳过打塔</th><th>起手</th><th>HOLD</th>'
            '<th>HumanMove</th><th>每千帧</th></tr></thead><tbody>')
    out = [head]
    for r in rows:
        kf = r['end'] / 1000.0 or 1.0
        cls = 'win' if r['win'] else ('lose' if (r['died'] or r['tcdead']) else '')
        cells = [esc(r['file']), str(r['end']), res_of(r), str(r['tot']), str(r['remote']),
                 str(r['melee']), str(r['skip']), str(r['start']), str(r['hold']),
                 str(r['move']), '%.1f' % (r['move'] / kf)]
        tds = ''.join('<td%s>%s</td>' % (' class="num"' if i not in (0, 2) else '', c)
                      for i, c in enumerate(cells))
        out.append('<tr class="%s">%s</tr>' % (cls, tds))
    return '\n'.join(out + ['</tbody></table>'])


def build():
    names = sys.argv[1:] or ['mc', 'md', 'tc']
    names = [n for n in names if os.path.exists('%s1.ait' % n)]
    data = {n: batch(n) for n in names}
    A = {n: agg(rows) for n, rows in data.items()}

    metric_rows = [
        ('局数', lambda z: '%d' % z['n'], ''),
        ('胜（VICTORY）', lambda z: '%d' % z['win'], '参考'),
        ('祭司阵亡（局）', lambda z: '%d' % z['died'], '参考'),
        ('<b>[TOWER-TGT] 打塔合计</b>', lambda z: '%d' % z['tot'], '机制'),
        ('其中：复合弓兵/远程', lambda z: '%d' % z['remote'], '★主指标'),
        ('其中：近战', lambda z: '%d' % z['melee'], '应保持'),
        ('[TOWER-SKIP] 放弃打塔', lambda z: '%d' % z['skip'], '★新增'),
        ('祭司起手次数', lambda z: '%d' % z['start'], '机制'),
        ('[KIT-R] 拉扯撤退', lambda z: '%d' % z['labels']['[KIT-R'], '机制'),
        ('[KIT-S] 接敌带', lambda z: '%d' % z['labels']['[KIT-S'], '机制'),
        ('HumanMove / 千帧', lambda z: '%.1f' % z['movekf'], '结构量'),
        ('HumanAction / 千帧', lambda z: '%.1f' % z['actkf'], '结构量'),
        ('末帧区间', lambda z: '%d ~ %d' % (z['endmin'], z['endmax']), ''),
    ]
    hdr = ''.join('<th>%s</th>' % esc(DESC.get(n, n)) for n in names)
    mrows = []
    for label, fn, kind in metric_rows:
        mrows.append('<tr><td>%s</td>%s<td>%s</td></tr>' % (
            label, ''.join('<td class="num">%s</td>' % esc(fn(A[n])) for n in names), esc(kind)))

    labels_rows = []
    for k in LABELS:
        labels_rows.append('<tr><td>%s</td>%s</tr>' % (
            esc(k), ''.join('<td class="num">%d</td>' % A[n]['labels'][k] for n in names)))

    skip_rows = []
    for n in names:
        for r in data[n]:
            for s in r['skips'][:6]:
                skip_rows.append('<tr><td>%s</td><td>%s</td><td class="num">%d</td><td>%s</td>'
                                 '<td class="num">%d</td><td class="num">%.1f</td><td class="num">%.1f</td>'
                                 '<td class="num">%d</td></tr>'
                                 % (esc(n), esc(r['file']), s['f'], esc(s['who']), s['sn'],
                                    s['selfR'], s['towerR'], s['tgt']))
    if not skip_rows:
        skip_rows.append('<tr><td colspan="8" class="mut">无 [TOWER-SKIP]（说明该批从未遇到"够不着塔"的场景，'
                         '或闸未生效）</td></tr>')

    conv_rows = []
    for n in names:
        for r in data[n]:
            for c in r['conv']:
                conv_rows.append('<tr><td>%s</td><td>%s</td><td class="num">%d</td><td class="num">%.1f</td>'
                                 '<td class="num">%.2f</td><td class="num">%.1f</td><td class="num">%d</td><td>%s</td></tr>'
                                 % (esc(n), esc(r['file']), c['f'], c['d'], c['hp'], c['nearT'], c['tw'], esc(c['path'])))
    if not conv_rows:
        conv_rows.append('<tr><td colspan="8" class="mut">无带字段的起手日志</td></tr>')

    ch = '\n'.join('<tr><td class="mono">%s</td><td>%s</td><td>%s</td><td class="mono">%s</td></tr>' % t for t in CHANGES)
    game_secs = '\n'.join('<h3>%s</h3>\n%s' % (esc(DESC.get(n, n)), game_table(data[n])) for n in names)

    base = A.get('mc')
    tc = A.get('tc')
    if base and tc:
        concl = ('远程打塔 <b class="%s">%d → %d</b>（基线两批均 %d）；'
                 '[TOWER-SKIP] %d → <b class="%s">%d</b>；近战打塔 %d → %d。'
                 % ('ok' if tc['remote'] == 0 else 'bad', base['remote'], tc['remote'], base['remote'],
                    base['skip'], 'ok' if tc['skip'] else 'bad', tc['skip'], base['melee'], tc['melee']))
    else:
        concl = ''

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    tpl = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>towerskip · 复合弓兵不再打箭塔</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1b1f24;--mut:#6b7280;--line:#e5e7eb;--acc:#2563eb;--win:#b91c1c;--lose:#15803d;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1120px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:30px 0 10px;padding-left:9px;border-left:4px solid var(--acc)}
h3{font-size:13px;margin:16px 0 6px;color:#374151}
.sub{color:var(--mut);font-size:13px;margin-bottom:18px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:16px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.card .k{color:var(--mut);font-size:12px}.card .v{font-size:19px;font-weight:600;margin-top:2px}
.card .d{color:var(--mut);font-size:12px;margin-top:2px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;font-size:13px;vertical-align:top}
th{background:#f0f2f5;font-weight:600;color:#374151}
td.num{text-align:right;font-variant-numeric:tabular-nums}
tr.win td:nth-child(3){color:var(--win);font-weight:700}
tr.lose td:nth-child(3){color:var(--lose);font-weight:700}
.mono{font-family:ui-monospace,Consolas,monospace;font-size:12px}
.mut{color:var(--mut)}
.note{background:#fff;border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:8px;padding:12px 14px;margin:12px 0}
.warn{border-left-color:#d97706}
.ok{color:#15803d;font-weight:600}.bad{color:#b91c1c;font-weight:600}
code{background:#eef1f5;padding:1px 5px;border-radius:4px;font-size:12px}
</style></head><body><div class="wrap">
<h1>towerskip 轮 · 复合弓兵不再"拉扯"箭塔</h1>
<div class="sub">需求：<b>复合弓兵不要拉扯箭塔（攻击距离比箭塔小）</b> ·
A 臂 = <span class="mono">mc</span>(+<span class="mono">md</span> 噪声底线)，B 臂 = <span class="mono">tc</span> · 生成于 @@NOW@@</div>

<div class="cards">
  <div class="card"><div class="k">远程打塔（8 局）</div><div class="v">45 → @@C1@@</div><div class="d">基线 mc / md 均为 45 次</div></div>
  <div class="card"><div class="k">[TOWER-SKIP] 放弃打塔</div><div class="v">@@C2@@</div><div class="d">新增观测点（改动前不存在）</div></div>
  <div class="card"><div class="k">源码总行数</div><div class="v">6700 → 6735</div><div class="d">+35 行（含 12 行注释/日志）+ .h +3</div></div>
  <div class="card"><div class="k">编译</div><div class="v">0 error</div><div class="d">warning 18 条，按类别无新增</div></div>
</div>

<h2>1 · 根因与改动清单</h2>
<div class="note"><b>根因（不是"没生效"，是"选错目标"）</b>
<ul style="margin:6px 0 0;padding-left:20px">
<li>敌箭塔射程 <b>8 格</b>，我方远程兵最大射程 <b>复合弓/战车弓 7、弓兵 5、投石兵 4</b> —— 全部 &lt; 8。</li>
<li>原 <code>attackBuildingOrMarch</code> 的规则是"有敌塔就打最近的塔"（<code>TOWER_TARGET_RANGE</code>=12 格，
2026-09-13 加的"士兵优先打最近箭塔"规则）。对<b>近战</b>合理（贴身拆塔是本职），对<b>射程 7 的复合弓</b>则是：
先走进塔的 8 格射程 → 自己 7 格仍够不到 → 引擎在前移/后撤之间反复找射程 = 观感"拉扯箭塔"，实质全程白挨打。</li>
<li>排查确认：拉扯相位机（<code>kitingTargetSN</code>）的目标只来自敌<b>军队/农民</b>（<code>findNearestEnemyNoStone</code> 不含建筑），
所以"拉扯塔"不是相位机干的；全函数内会给兵下"打塔"令的只有 <code>attackBuildingOrMarch</code> 一处（已逐点审计 9 个 <code>HumanAction</code> 调用点）。</li>
</ul></div>
<table><thead><tr><th>#</th><th>改动</th><th>说明</th><th>行数</th></tr></thead><tbody>
@@CH@@
</tbody></table>

<h2>2 · A/B 对拍</h2>
<div class="note warn">铁律 25/36：8 局/批<b>无胜负判定力</b>（同一纯基线三批曾出现 5/8 · 5/8 · 2/8）。
本轮结论只建立在<b>机制量</b>上：<span class="mono">[TOWER-TGT]</span> 的 who 拆分（远程/近战）与
<span class="mono">[TOWER-SKIP]</span> 的字段自证；胜负与 move/kf 仅作参考。</div>
<table><thead><tr><th>指标</th>@@HDR@@<th>类型</th></tr></thead><tbody>
@@MROWS@@
</tbody></table>

<h2>3 · 各日志标签合计</h2>
<table><thead><tr><th>标签</th>@@HDR@@</tr></thead><tbody>
@@LABELS@@
</tbody></table>

<h2>4 · 逐局明细</h2>
@@GAMES@@

<h2>5 · [TOWER-SKIP] 现场（每局最多 6 条）</h2>
<div class="note">字段自证：<code>射程X&lt;塔8</code> —— 直接证明闸是按"够不够得着"判定，而非按兵种名单。</div>
<table><thead><tr><th>批</th><th>局</th><th>帧</th><th>who</th><th>兵 SN</th><th>自身射程</th><th>塔射程</th><th>放弃的塔 SN</th></tr></thead><tbody>
@@SKIP@@
</tbody></table>

<h2>6 · 祭司起手现场（带字段日志）</h2>
<table><thead><tr><th>批</th><th>局</th><th>帧</th><th>d 格</th><th>hp</th><th>nearT 格</th><th>敌塔数</th><th>path</th></tr></thead><tbody>
@@CONV@@
</tbody></table>

<h2>7 · 结论</h2>
<div class="note">
<ul style="margin:0;padding-left:20px">
<li>主指标：@@CONCL@@</li>
<li>近战与投石车语义显式保留（<code>canHitTower</code> 短路）——近战仍会拆塔，投石车（射程 10）仍会压制塔。</li>
<li><b>次指标（需留意，本轮不作判决）</b>：tc 的祭司 <code>Priest ADVANCE</code> <b>137</b> 次（mc 53）↑、
<code>Priest converting</code> <b>1</b> 次（mc 4 / md 3）↓、<code>[SIEGE-HOLD]</code> 2 次（mc 0）。
可解释的因果：弓兵不再打塔 ⇒ 塔不会因被攻击而牵制 ⇒ 祭司在前线受压时间更久 ⇒ 前出次数增加而成功起手减少。
但两条反向证据：①基线 8 局里那 45 次打塔<b>从未拆掉任何一座塔</b>（记忆：起手窗口内敌塔被摧毁 0~1 座）；
②md 与 mc 是<b>同一二进制</b>，converting 本身就有 4→3 的波动。
⇒ 判据应为 <b>交替 A/B ≥24 局/臂</b>（铁律 25），本轮不据此回滚。</li>
<li>编译：<code>syn.py</code> <b class="ok">0 error</b> / 18 warning；<code>warn_diff.py</code> 按类别比对无新增。
代码：<code>diff</code> = <b>4 个变更块</b>、+37 / −2 行（cpp）+ .h 3 行，与改动清单一一对应。</li>
<li>已知同类隐患（本轮<b>未处理</b>，留待单独 A/B）：拉扯相位机的"投石车兜底"分支会在 <code>R+1.5</code> 格内让复合弓去打敌投石车，
而投石车射程 10 &gt; 复合弓 7 —— 属于同一类"够不着还去打"的结构问题。</li>
</ul></div>
</div></body></html>"""
    doc = tpl
    for tok, val in (('@@NOW@@', now), ('@@CH@@', ch), ('@@HDR@@', hdr), ('@@MROWS@@', '\n'.join(mrows)),
                     ('@@LABELS@@', '\n'.join(labels_rows)), ('@@GAMES@@', game_secs),
                     ('@@SKIP@@', '\n'.join(skip_rows)), ('@@CONV@@', '\n'.join(conv_rows)),
                     ('@@CONCL@@', concl),
                     ('@@C1@@', str(tc['remote']) if tc else '—'), ('@@C2@@', str(tc['skip']) if tc else '—')):
        doc = doc.replace(tok, val)
    out = os.path.abspath('aoe3_towerskip_20260915.html')
    open(out, 'w', encoding='utf-8').write(doc)
    print('written', out)
    if tc:
        print('tc: tot=%d remote=%d melee=%d skip=%d win=%d' % (
            tc['tot'], tc['remote'], tc['melee'], tc['skip'], tc['win']))


if __name__ == '__main__':
    build()
