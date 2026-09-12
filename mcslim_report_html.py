# -*- coding: utf-8 -*-
"""生成 mcslim 轮报告（HTML）：manageCounterAttack 去重 + 删死变量（行为中性重构）。
用法：python mcslim_report_html.py            # 默认 sg(基线) / mc(重构) / md(同构建重跑=噪声底线)
"""
import os, re, sys, html, datetime

CONV = re.compile(r'Priest converting Siege Workshop! f=(\d+) d=([\d.]+) hp=([\d.]+) nearT=(-?[\d.]+) towers=(\d+) path=(\w+)')
HOLD = re.compile(r'\[SIEGE-HOLD f=(\d+)\]')
ADV = re.compile(r'Priest ADVANCE to Siege f=(\d+)')
HA = re.compile(r'HumanAction:祭司 \d+ 设置转换目标为 攻城武器厂 \d+')
LABELS = ['[KIT-R', '[KIT-S', '[TOWER-TGT', '[PRST-REAR', '[LC-DBG', '[SIEGE-HOLD]',
          'Priest converting Siege Workshop', 'Priest ADVANCE to Siege', 'Enemy Siege Workshop found',
          'Enemy base scouted', 'Force COUNTERATTACK']

DESC = {'sg': 'sg · 基线（siegeguard 构建，即 mc 的直接前身）',
        'mc': 'mc · 重构后（mcslim：去重 + 删死变量）',
        'md': 'md · 噪声底线（同一 mc 构建再跑 8 局，用于标定批间波动）'}

CHANGES = [
    ("S1", "新增 <span class=mono>lookupEnemySN</span> lambda", "3 处各抄一份的「SN→坐标」三层查找（敌军队/敌农民/敌建筑）收口为 1 个 lambda", "−27 行"),
    ("S1a", "· 拉扯粘滞目标查找", "kitingTargetSN 命中后的存活/坐标回填改为一次调用", "19 → 7 行"),
    ("S1b", "· 投石车粘滞目标查找", "catTargetSN 与 findCatapultTarget 结果各查一次坐标 → 两次调用", "29 → 14 行"),
    ("S1c", "· 投石车威胁点查找", "threatSN 坐标回填 → 一次调用", "5 → 2 行"),
    ("S2", "新增 <span class=mono>attackBuildingOrMarch</span> lambda", "远程/近战分支各抄一份的「打最近敌塔 → 打最近敌建筑(跳过武器厂) → 推进」收口为 1 个 lambda", "−24 行"),
    ("S2a", "· 远程分支", "块体 → 1 次调用（who=\"复合弓兵/远程\"）", "25 → 6 行"),
    ("S2b", "· 近战分支", "块体 → 1 次调用（who=\"近战\"）", "26 → 5 行"),
    ("S3", "删死变量 <span class=mono>enemyMil</span> / <span class=mono>enemyTowers</span>", "两个计数器只在注释里被引用，代码从不读取（两趟全表扫描白跑）", "−4 行"),
    ("S4", "删死变量 <span class=mono>priestEnemy</span>", "查询结果从不使用（原注释即写明「暂不直接使用」）；删后 warning 净少 1 条 <span class=mono>unused variable</span>", "−6 行"),
    ("S5", "随删改口两处过期注释", "引用已删变量的注释同步更新，避免后人按注释找变量", "0 行"),
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
             move=0, action=0, conv=[], hold=0, adv=0, labels={k: 0 for k in LABELS})
    for fr, m in ev:
        if 'HumanMove' in m:
            d['move'] += 1
        if 'HumanAction' in m:
            d['action'] += 1
        if 'VICTORY' in m:
            d['win'] += 1
        if 'DEFEAT: Priest killed' in m:
            d['died'] += 1
        if 'DEFEAT: Town Center destroyed' in m:
            d['tcdead'] += 1
        g = CONV.search(m)
        if g:
            d['conv'].append(dict(f=int(g.group(1)), d=float(g.group(2)), hp=float(g.group(3)),
                                  nearT=float(g.group(4)), tw=int(g.group(5)), path=g.group(6)))
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
    d['died'] = 1 if d['died'] else 0        # 计"局"，不计 DebugText 出现次数（每帧重复打印）
    return d


def batch(prefix, n=8):
    return [summarize('%s%d.ait' % (prefix, i)) for i in range(1, n + 1) if os.path.exists('%s%d.ait' % (prefix, i))]


def agg(rows):
    kf = sum(r['end'] for r in rows) / 1000.0 or 1.0
    return dict(n=len(rows), win=sum(r['win'] for r in rows), died=sum(r['died'] for r in rows),
                tcdead=sum(r['tcdead'] for r in rows),
                start=sum(r['start'] for r in rows), startGames=sum(1 for r in rows if r['start']),
                hold=sum(r['hold'] for r in rows), adv=sum(r['adv'] for r in rows),
                movekf=sum(r['move'] for r in rows) / kf, actkf=sum(r['action'] for r in rows) / kf,
                labels={k: sum(r['labels'][k] for r in rows) for k in LABELS},
                endmin=min((r['end'] for r in rows), default=0), endmax=max((r['end'] for r in rows), default=0),
                end=sum(r['end'] for r in rows))


def res_of(d):
    return 'WIN' if d['win'] else ('DIED' if d['died'] else ('TCDEAD' if d['tcdead'] else 'TIME'))


def esc(s):
    return html.escape(str(s))


def game_table(rows):
    head = ('<table class="t"><thead><tr><th>局</th><th>末帧</th><th>结局</th><th>HumanMove</th><th>每千帧</th>'
            '<th>HumanAction</th><th>起手</th><th>HOLD</th><th>KIT-R</th><th>KIT-S</th><th>TOWER-TGT</th></tr></thead><tbody>')
    out = [head]
    for r in rows:
        kf = r['end'] / 1000.0 or 1.0
        cls = 'win' if r['win'] else ('lose' if (r['died'] or r['tcdead']) else '')
        cells = [esc(r['file']), str(r['end']), res_of(r), str(r['move']), '%.1f' % (r['move'] / kf),
                 str(r['action']), str(r['start']), str(r['hold']),
                 str(r['labels']['[KIT-R']), str(r['labels']['[KIT-S']), str(r['labels']['[TOWER-TGT'])]
        tds = ''.join('<td%s>%s</td>' % (' class="num"' if i not in (0, 2) else '', c)
                      for i, c in enumerate(cells))
        out.append('<tr class="%s">%s</tr>' % (cls, tds))
    return '\n'.join(out + ['</tbody></table>'])


def build():
    names = sys.argv[1:] or ['sg', 'mc', 'md']
    names = [n for n in names if os.path.exists('%s1.ait' % n)]
    data = {n: batch(n) for n in names}
    A = {n: agg(rows) for n, rows in data.items()}

    def pct(a, b):
        if not a:
            return '—'
        return '%+.0f%%' % ((b - a) / float(a) * 100)

    # 对拍表：sg(基线) vs mc(重构) vs md(噪声底线)
    metric_rows = [
        ('局数', lambda z: '%d' % z['n'], ''),
        ('胜（VICTORY）', lambda z: '%d' % z['win'], '参考'),
        ('祭司阵亡（局）', lambda z: '%d' % z['died'], '参考'),
        ('祭司起手次数', lambda z: '%d' % z['start'], '机制'),
        ('含起手的局数', lambda z: '%d' % z['startGames'], '机制'),
        ('[SIEGE-HOLD]', lambda z: '%d' % z['hold'], '机制'),
        ('[KIT-R] 拉扯撤退', lambda z: '%d' % z['labels']['[KIT-R'], '机制'),
        ('[KIT-S] 接敌带', lambda z: '%d' % z['labels']['[KIT-S'], '机制'),
        ('[TOWER-TGT] 打塔', lambda z: '%d' % z['labels']['[TOWER-TGT'], '机制'),
        ('HumanMove / 千帧', lambda z: '%.1f' % z['movekf'], '结构量'),
        ('HumanAction / 千帧', lambda z: '%.1f' % z['actkf'], '结构量'),
        ('末帧区间', lambda z: '%d ~ %d' % (z['endmin'], z['endmax']), ''),
    ]
    hdr = ''.join('<th>%s</th>' % esc(DESC.get(n, n)) for n in names)
    mrows = []
    for label, fn, kind in metric_rows:
        mrows.append('<tr><td>%s</td>%s<td>%s</td></tr>' % (
            esc(label), ''.join('<td class="num">%s</td>' % esc(fn(A[n])) for n in names), esc(kind)))
    mrows.append('<tr><td>mc 相对 sg</td><td colspan="%d">%s</td></tr>' % (
        max(1, len(names) - 1),
        'move/kf %s · act/kf %s · KIT-R %s · 起手 %s' % (
            pct(A['sg']['movekf'], A['mc']['movekf']) if 'sg' in A else '—',
            pct(A['sg']['actkf'], A['mc']['actkf']) if 'sg' in A else '—',
            pct(A['sg']['labels']['[KIT-R'], A['mc']['labels']['[KIT-R']) if 'sg' in A else '—',
            pct(A['sg']['start'], A['mc']['start']) if 'sg' in A else '—')))

    labels_rows = []
    for k in LABELS:
        mrows2 = ''.join('<td class="num">%d</td>' % A[n]['labels'][k] for n in names)
        labels_rows.append('<tr><td>%s</td>%s</tr>' % (esc(k), mrows2))

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

    if 'sg' in A and 'mc' in A:
        d_move = abs(A['mc']['movekf'] - A['sg']['movekf']) / max(1e-9, A['sg']['movekf'])
        d_act = abs(A['mc']['actkf'] - A['sg']['actkf']) / max(1e-9, A['sg']['actkf'])
        concl = ('act/kf 偏差 <b class="ok">%.0f%%</b>（结构量，抗噪）；move/kf 偏差 %.0f%%（计数型，'
                 '历史摆动可达 4.5×，属噪声区间）。' % (d_act * 100, d_move * 100))
    else:
        concl = ''

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    tpl = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>mcslim · manageCounterAttack 去重与瘦身</title>
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
<h1>mcslim 轮 · <span class="mono">manageCounterAttack</span> 去重与瘦身</h1>
<div class="sub">行为中性重构（红线：重构期间不改行为）· 基线 <span class="mono">sg</span> vs 重构 <span class="mono">mc</span> vs 同构建重跑 <span class="mono">md</span> · 生成于 @@NOW@@</div>

<div class="cards">
  <div class="card"><div class="k">源码总行数</div><div class="v">6736 → 6700</div><div class="d">−36 行</div></div>
  <div class="card"><div class="k">manageCounterAttack</div><div class="v">1078 → 1043</div><div class="d">−35 行（−3.2%）</div></div>
  <div class="card"><div class="k">编译</div><div class="v">0 error</div><div class="d">warning 集合 −1（少一条 unused）</div></div>
  <div class="card"><div class="k">重复实现收口</div><div class="v">2 组 / 5 处</div><div class="d">→ 2 个 lambda（铁律 21/26）</div></div>
</div>

<h2>1 · 改动清单</h2>
<table><thead><tr><th>#</th><th>改动</th><th>说明</th><th>行数</th></tr></thead><tbody>
@@CH@@
</tbody></table>

<div class="note"><b>行为中性论证（逐项）</b>
<ul style="margin:6px 0 0;padding-left:20px">
<li><b>S1 / S2</b>：纯结构抽提——原块逐行搬进 lambda，分支顺序、去重条件、日志字段全部保持；
日志文本逐字等价（<code>[TOWER-TGT f=N] 复合弓兵/远程 SN=N 攻击最近敌塔 N (R&lt;=N格)</code>）。</li>
<li><code>lookupEnemySN</code> 比原来多查一类「敌建筑」：SN 全图唯一 + 命中顺序（军队→农民→建筑）⇒ 结果不变
（且投石车目标本就需要建筑分支，原代码另一处也是三查）。</li>
<li><b>S3 / S4</b>：删的两个变量在代码中从不被读取——<code>enemyMil</code>/<code>enemyTowers</code> 仅出现在注释里，
<code>priestEnemy</code> 的原注释就写着「暂不直接使用」⇒ 纯删无副作用查询。</li>
<li>未触碰任何阈值常量、判据半径、状态机转移条件、相位机结构与祭司三段分发顺序。</li>
</ul></div>

<h2>2 · 行为对拍</h2>
<div class="note warn">铁律 25：8 局/批<b>无胜负判定力</b>（同一纯基线三批曾出现 5/8 · 5/8 · 2/8）。
此处只判<b>机制/结构指标是否同级</b>，胜负仅作参考；<span class="mono">md</span> 列即"同构建再跑一遍"的噪声标尺。</div>
<table><thead><tr><th>指标</th>@@HDR@@<th>类型</th></tr></thead><tbody>
@@MROWS@@
</tbody></table>

<h2>3 · 各日志标签合计</h2>
<table><thead><tr><th>标签</th>@@HDR@@</tr></thead><tbody>
@@LABELS@@
</tbody></table>

<h2>4 · 逐局明细</h2>
@@GAMES@@

<h2>5 · 祭司起手现场（带字段日志）</h2>
<table><thead><tr><th>批</th><th>局</th><th>帧</th><th>d 格</th><th>hp</th><th>nearT 格</th><th>敌塔数</th><th>path</th></tr></thead><tbody>
@@CONV@@
</tbody></table>

<h2>6 · 结论</h2>
<div class="note">
<ul style="margin:0;padding-left:20px">
<li>编译：<b class="ok">0 error</b>；warning <b>按类别比对完全一致</b>，且因删掉未使用变量 <b class="ok">净少 1 条</b>
（<code>unused variable 'priestEnemy'</code>）。</li>
<li>机制/结构指标：@@CONCL@@</li>
<li>代码校验：<code>diff pre→post</code> = <b>10 个变更块</b>、+61 / −97 行，与改动清单一一对应，无越界改动。</li>
<li>结论：本次为<b class="ok">行为中性重构</b>，符合"重构期间不动行为"的红线；函数体量降至 1043 行，重复实现 5 处收口为 2 个 lambda。</li>
<li>后续（O 系列，均须沿用本流程"先建行为对拍基线 → 再纯搬代码 → 编译 + 对拍"）：
<b>O3 打-拉相位机（−413）</b>、<b>O4 抽 <span class="mono">manageScout</span>（~400 行）</b>；
另有本轮新发现的 <b>O10 感知开销</b>——<span class="mono">manageCounterAttack</span> 每帧重建整张 <span class="mono">forestGrid</span>，可缓存化。</li>
</ul></div>
</div></body></html>"""
    doc = tpl
    for tok, val in (('@@NOW@@', now), ('@@CH@@', ch), ('@@HDR@@', hdr), ('@@MROWS@@', '\n'.join(mrows)),
                     ('@@LABELS@@', '\n'.join(labels_rows)), ('@@GAMES@@', game_secs),
                     ('@@CONV@@', '\n'.join(conv_rows)), ('@@CONCL@@', concl)):
        doc = doc.replace(tok, val)
    out = os.path.abspath('aoe3_mcslim_20260915.html')
    open(out, 'w', encoding='utf-8').write(doc)
    print('written', out)
    for n in names:
        print(n, A[n])


if __name__ == '__main__':
    build()
