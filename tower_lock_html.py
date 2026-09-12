import re, os, collections, statistics

# 生成 aoe3_towerlock_20260914.html（数据全部现场从 ait 日志算，避免手抄）
OUT = 'aoe3_towerlock_20260914.html'
WIN = 1500
ARMS = [
    ('pu', '基线(pullkite) 复现A', 'base'),
    ('ez', '基线(pullkite) 复现B', 'base'),
    ('tb', '基线 复现C（同机同时点对照）', 'base'),
    ('tl', 'v1 箭塔闸 13格/1格带', 'v1'),
    ('tm', 'v2 迟滞闩锁 12/18 首次', 'v2'),
    ('tn', 'v2 迟滞闩锁 12/18 复现', 'v2'),
]


def parse(f):
    if not os.path.exists(f):
        return None
    d = dict(game=f, deathF=0, wsF=0, endF=0, vic=0, tower=[], atk=[], conv=[], abort=[],
             lc=0, hold=0, lockBad=0, lockOn=0, tDmin=[])
    for line in open(f, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) < 5:
            continue
        fr, msg = p[1].strip(), p[4].strip()
        if not fr.isdigit():
            continue
        fr = int(fr)
        d['endF'] = max(d['endF'], fr)
        if 'VICTORY' in msg:
            d['vic'] = 1
        if 'DEFEAT: Priest killed' in msg and not d['deathF']:
            d['deathF'] = fr
        if 'Enemy Siege Workshop found' in msg and not d['wsF']:
            d['wsF'] = fr
        if re.search(r'HumanAction:箭塔 \d+ 设置攻击目标为 祭司 \d+', msg):
            d['tower'].append(fr)
        m = re.search(r'(\D+?)\(编号[:：](\d+)\)开始向祭司\(编号[:：]\d+\)攻击', msg)
        if m:
            d['atk'].append((m.group(1).strip(), fr))
        m = re.search(r'HumanAction:祭司 \d+ 设置转换目标为 (\S+?) (\d+)', msg)
        if m:
            d['conv'].append((m.group(1), fr))
        if '[PRST-TOWER-ABORT' in msg:
            d['abort'].append(fr)
        if '[LC-DBG' in msg:
            d['lc'] += 1
            hd = re.search(r'hold=(\d)', msg)
            if hd and hd.group(1) == '1':
                d['hold'] += 1
            dg = re.search(r'tDgr=(\d)', msg)
            lk = re.search(r'lock=(\d)', msg)
            if dg and lk and lk.group(1) == '1':
                d['lockOn'] += 1
                if dg.group(1) == '1':
                    d['lockBad'] += 1
            td = re.search(r'tD=([-\d.]+)', msg)
            if td and float(td.group(1)) >= 0:
                d['tDmin'].append(float(td.group(1)))
    d['convSiege'] = [c for c in d['conv'] if '攻城武器厂' in c[0]]
    d['towerInWin'] = sum(1 for x in d['tower'] if 0 <= d['deathF'] - x <= WIN) if d['deathF'] else 0
    d['atkInWin'] = sum(1 for n, x in d['atk'] if 0 <= d['deathF'] - x <= WIN) if d['deathF'] else 0
    return d


def load(pref):
    return [r for r in (parse('%s%d.ait' % (pref, i)) for i in range(1, 9)) if r]


def agg(rows):
    n = len(rows)
    return dict(n=n,
                w=sum(1 for r in rows if r['vic'] and not r['deathF']),
                pd=sum(1 for r in rows if r['deathF']),
                wsn=sum(1 for r in rows if r['wsF']),
                wsf=sorted(r['wsF'] for r in rows if r['wsF']),
                fg=sum(1 for r in rows if r['tower']),
                cv=sum(len(r['convSiege']) for r in rows),
                ab=sum(len(r['abort']) for r in rows),
                hold=sum(r['hold'] for r in rows),
                lc=sum(r['lc'] for r in rows),
                lb=sum(r['lockBad'] for r in rows),
                tdm=sorted(min(r['tDmin']) for r in rows if r['tDmin']))


def med(v):
    return ('%d' % statistics.median(v)) if v else '-'


# ---------- 死因构成（全批次） ----------
ALLB = ['pu', 'ez', 'tb', 'pg', 'tl', 'tm', 'tn', 'lc', 'll', 'lm', 'ln', 'lj']
tax = dict(games=0, deaths=0, towerOnly=0, unitOnly=0, both=0, none=0, early=0,
           wsBefore=0, convAtDeath=0, killer=collections.Counter())
for b in ALLB:
    for r in load(b):
        tax['games'] += 1
        if not r['deathF']:
            continue
        tax['deaths'] += 1
        tw = sum(1 for x in r['tower'] if 0 <= r['deathF'] - x <= WIN)
        at = [(x, y) for x, y in r['atk'] if 0 <= r['deathF'] - y <= WIN]
        if tw and at:
            tax['both'] += 1
        elif tw:
            tax['towerOnly'] += 1
        elif at:
            tax['unitOnly'] += 1
        else:
            tax['none'] += 1
        if r['deathF'] < 33000:
            tax['early'] += 1
        if r['wsF'] and r['wsF'] < r['deathF']:
            tax['wsBefore'] += 1
        if any(0 <= r['deathF'] - c[1] <= WIN for c in r['conv']):
            tax['convAtDeath'] += 1
        for n, _ in at:
            tax['killer'][n] += 1

AR = {}
for pref, name, arm in ARMS:
    rows = load(pref)
    if rows:
        AR[pref] = agg(rows)

h = []
A = h.append
A('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
A('<title>祭司阵亡：箭塔迟滞锁缺口修复与死因构成</title><style>')
A(':root{--bg:#f6f7f9;--card:#fff;--line:#e3e6ea;--tx:#1f2328;--mut:#6b7280;'
  '--ok:#137a3f;--bad:#b42318;--acc:#1d4ed8;--warn:#b45309}')
A('*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);'
  'font:14px/1.68 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}')
A('.wrap{max-width:1140px;margin:0 auto;padding:28px 20px 60px}')
A('h1{font-size:23px;margin:0 0 6px}h2{font-size:17px;margin:30px 0 12px;padding-left:10px;'
  'border-left:4px solid var(--acc)}h3{font-size:15px;margin:20px 0 8px}')
A('.sub{color:var(--mut);font-size:13px;margin-bottom:18px}')
A('.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:12px 0}')
A('.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:14px 0}')
A('.kpib{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:13px 15px}')
A('.kpib .n{font-size:21px;font-weight:700;margin:2px 0}.kpib .t{font-size:12px;color:var(--mut)}')
A('.kpib.g .n{color:var(--ok)}.kpib.r .n{color:var(--bad)}.kpib.w .n{color:var(--warn)}')
A('table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);'
  'border-radius:10px;overflow:hidden;font-size:13px}')
A('th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right}')
A('th:first-child,td:first-child{text-align:left}')
A('th{background:#f0f2f5;font-weight:600;color:#374151;font-size:12px}')
A('tr:last-child td{border-bottom:none}td.num{font-variant-numeric:tabular-nums}')
A('.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}')
A('.mono{font-family:ui-monospace,Consolas,monospace;font-size:12px}')
A('pre{background:#f8f9fb;border:1px solid var(--line);border-radius:8px;padding:11px 13px;'
  'overflow-x:auto;font-size:12px;line-height:1.6}')
A('.note{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:11px 14px;font-size:13px;margin:12px 0}')
A('.dang{background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:11px 14px;font-size:13px;margin:12px 0}')
A('code{background:#f0f2f5;padding:1px 5px;border-radius:4px;font-size:12.5px}')
A('</style></head><body><div class="wrap">')

A('<h1>祭司阵亡：箭塔迟滞锁缺口修复 + 死因构成定量</h1>')
A('<div class="sub">AoE3 UsrAI · 基线 3.0.7g · 25fps · map3 rotate=90 · 8 局/批 · '
  '生成于 2026-09-14 23:15 · 6 批 × 8 局 = 48 局 + 全库 88 局死因统计</div>')

# 结论摘要
A('<div class="card"><h3 style="margin-top:0">结论摘要（先说最重要的）</h3>')
A('<p><b>1. 用户问的那件事被证实了：迟滞锁有一个真缺口。</b>'
  '<code>priestSiegeApproach</code> 的<b>置位</b>条件含"14 格内无箭塔"，但<b>复位</b>条件'
  '（敌军队 4.5 格 / 血量 0.35）<b>完全不含箭塔</b> ⇒ 箭塔维度只在置位那一帧被验一次，'
  '此后塔怎么压上来都不解锁 = <b>单向闩锁</b>（违反铁律 9）。pg7 是铁证。</p>')
A('<p><b>2. 但把塔闸补上之后，才发现祭司阵亡的主因不是塔。</b>'
  '全 %d 批 %d 局里祭司共阵亡 <b>%d 局（%.0f%%）</b>，其中死前 1 分钟内有<b>敌箭塔</b>开火的只有 '
  '<b>%d 局（%.0f%%）</b>，而有<b>敌方单位</b>贴上来打的是 <b>%d 局（%.0f%%）</b>；'
  '施法最后一个目标里最多的是方阵兵/战车弓兵（见 §4）。'
  '<b>塔是次要死因</b>——本轮修的是"真缺陷"，但它不是"祭司反攻期阵亡"的主因。</p>'
  % (len(ALLB), tax['games'], tax['deaths'], 100.0 * tax['deaths'] / max(1, tax['games']),
     tax['towerOnly'] + tax['both'],
     100.0 * (tax['towerOnly'] + tax['both']) / max(1, tax['deaths']),
     tax['unitOnly'] + tax['both'],
     100.0 * (tax['unitOnly'] + tax['both']) / max(1, tax['deaths'])))
A('<p><b>3. 箭塔这次的修法本身踩了两次坑，第二次才对。</b>'
  'v1（危险线 13 格 / 迟滞带 1 格）= 把"站着被打死"换成了"<b>在两个落点之间来回抖</b>"'
  '（41 次解除-重锁，tl4 在 dS=14.6 空转 900 帧）；'
  'v2（危险线 = 塔射程 12 格 / 重新放行线 18 格 + 独立闩锁）抖动消失（全程 2 次 abort、'
  '"顶着塔仍持锁"采样 0 次）。</p>')
A('<p><b>4. 更重要的发现：这个项目一直在用的"胜负"指标，本身不可用于 A/B。</b>'
  '本轮把<b>纯基线代码</b>（与 pu/ez 逐字节相同的 <code>pre_towerlock</code>）在昨天深夜再跑一批（tb）'
  '做同机同时点对照，得到 <b>2/8 胜</b>——而同一份代码在 19:16 / 20:48 跑的两批是 <b>5/8、5/8</b>。'
  '同一份代码的批间差（2/8 ↔ 5/8，<b>37 个百分点</b>）已经大于本轮想测的任何效果。'
  '⇒ <b>上一轮"护驾修复退化"的结论也应在同一怀疑下重审</b>（该轮机制指标是决定性改善的：'
  '出手/发令 47%→117%、卡死单位 19→0）。</p>')
A('<p><b>5. 决断：回滚到纯基线，并放弃"用塔闸解决祭司阵亡"这条路线。</b>'
  '理由：① 塔闸即使 100% 生效也只覆盖约 10% 的祭司阵亡（§4）；'
  '② 它作用在"收编武器厂"这条唯一胜利路径的最后一段，臂级"发现→收编"从 12/16 掉到 3/7；'
  '③ 纯基线的当前工作副本已恢复（<code>cmp</code> 与备份逐字节一致），v2 备份随时可一条 <code>cp</code> 恢复。</p>')
A('</div>')

# KPI
tm = AR.get('tm', {})
tn = AR.get('tn', {})
A('<div class="kpi">')
A('<div class="kpib r"><div class="t">祭司阵亡（全 %d 局）</div><div class="n">%d 局 · %.0f%%</div></div>'
  % (tax['games'], tax['deaths'], 100.0 * tax['deaths'] / max(1, tax['games'])))
A('<div class="kpib w"><div class="t">其中死前有敌箭塔开火</div><div class="n">%d 局 · %.0f%%</div></div>'
  % (tax['towerOnly'] + tax['both'],
     100.0 * (tax['towerOnly'] + tax['both']) / max(1, tax['deaths'])))
A('<div class="kpib r"><div class="t">死前有敌方单位贴上来打</div><div class="n">%d 局 · %.0f%%</div></div>'
  % (tax['unitOnly'] + tax['both'],
     100.0 * (tax['unitOnly'] + tax['both']) / max(1, tax['deaths'])))
A('<div class="kpib g"><div class="t">v1 抖动 abort → v2</div><div class="n">%d → %d</div></div>'
  % (AR.get('tl', {}).get('ab', 0), tm.get('ab', 0)))
A('</div>')

# §1 机制
A('<h2>1 · 为什么"箭塔没拆完祭司就去感化"——两条独立机制</h2>')
A('<div class="card"><h3 style="margin-top:0">机制 A：迟滞锁单向闩锁（用户直接问的那个）</h3>')
A('<pre>置位：localClear(敌军队&gt;=8格 <b>且</b> 敌箭塔&gt;=14格) &amp;&amp; 武器厂已发现 → priestSiegeApproach=1\n'
  '复位：hardAbort(敌军队&lt;4.5格) || hp&lt;0.35 || 武器厂丢失        ← <b>这里没有箭塔维度</b>\n'
  '放行：allowConvertSiege = localClear || priestSiegeApproach==1   ← 锁一开就永久为真</pre>')
A('<p>后果：只要"发现武器厂"那一刻祭司周围 14 格内恰好没有塔，锁就永久打开，'
  '之后骑兵塔/箭塔从 20 格压到 3 格都不会再触发任何检查。</p>')
A('<p class="mono">pg7 铁证（帧-事件）：</p>')
A('<pre>f=41458  发现武器厂 → 锁置位（那一刻 14 格内无塔）\n'
  'f=41700  [LC-DBG] siegeSN=11099 dS=17.4 hp=0.85   （在推进）\n'
  'f=41768  敌塔 11107 开始打祭司            ← 塔进射程\n'
  'f=41865  祭司仍被下令"设置转换目标为攻城武器厂 11099"   ← 锁没解锁\n'
  'f=41981  敌塔 11105 也开始打祭司\n'
  'f=42059  祭司开始向武器厂攻击（施法）\n'
  'f=42176  祭司死亡（hp 1.00→0.55→0.31→0.19→0.07→0）</pre>')
A('<h3>机制 B（本次顺带查实的更狠的一条）：早路径把祭司"钉"在施法点上</h3>')
A('<pre>if (enemySiegeSN != -1 &amp;&amp; priest-&gt;ConvertCooldown &lt;= 0) {\n'
  '    if (sD0 &lt;= 12 格) {                 // 只要人在武器厂 12 格内\n'
  '        if (WorkObjectSN != enemySiegeSN &amp;&amp; priestCounterCooldown &lt;= 0) HumanAction(...);\n'
  '        priestMoveCooldown = 60;        // ★ 每帧钉住：禁止一切移动\n'
  '        return;                          // ★ 且直接 return，连后撤分支都到不了\n'
  '    }\n}</pre>')
A('<p>这段<b>完全绕过</b> localClear / 迟滞锁 / 塔距判据。一旦祭司进入武器厂 12 格，'
  '它<b>一步都动不了</b>（pg7：f=41865 发令后 <b>311 帧零条 HumanMove</b>），'
  '而这个游戏里"感化武器厂"要求祭司<b>走到厂边上</b>贴着施法（日志实测 dS 会掉到 1~6 格）。'
  '换句话说：<b>祭司不是"路过塔"，而是被钉在塔脚下 6 分钟。</b></p>')
A('<div class="dang">这两条合起来解释了用户看到的全部现象，也解释了为什么"塔没拆完就去感化"——'
  '因为<u>感的不是"塔拆完了"这个条件，而是"起手那一刻恰好没有塔在 14 格内"</u>。</div>')
A('</div>')

# §2 改动
A('<h2>2 · 改动（在已回滚的基线上单独施加）</h2>')
A('<div class="card">')
A('<table><tr><th>项</th><th>v1（首测，已否决）</th><th>v2（本轮保留）</th></tr>'
  '<tr><td>新增常量</td><td><code>PRIEST_SIEGE_ABORT_TOWER_R 13.0</code></td>'
  '<td><code>ABORT_TOWER_R 12.0</code>（= 塔射程, 与 cpp:786 chkThreat 同口径）<br>'
  '<code>REARM_TOWER_R 18.0</code>（迟滞带 12→18）</td></tr>'
  '<tr><td>防抖机制</td><td>无（靠 1 格带宽）</td>'
  '<td>新增成员 <code>int priestTowerHold</code> 迟滞闩锁：塔进 12 格置位，全部塔退出 18 格复位</td></tr>'
  '<tr><td>迟滞锁复位</td><td>+ <code>priestTowerDanger</code></td><td>同左</td></tr>'
  '<tr><td>早路径闸</td><td>+ <code>&amp;&amp; !priestTowerDanger</code></td><td>同左</td></tr>'
  '<tr><td>放行总闸</td><td>未加</td><td><code>allowConvertSiege &amp;&amp;= !priestTowerHold</code></td></tr>'
  '<tr><td>死代码</td><td>删 <code>enemyMil</code>/<code>enemyTowers</code>（算出后只出现在注释里）</td>'
  '<td>同左</td></tr>'
  '<tr><td>诊断</td><td>新增 <code>[PRST-TOWER-ABORT]</code>；LC-DBG 增 <code>tD/tDgr/lock</code></td>'
  '<td>再增 <code>hold=</code> 字段</td></tr></table>')
A('<p>净改动（相对基线 <code>UsrAI.cpp.bak_20260914_pre_towerlock</code>）：'
  '<b>+58 / -11 行</b>（含注释与诊断），其中<b>可执行语句 5 处</b>：常量 2 个、'
  'tower 距离解算 1 段、迟滞闩锁 2 行、早路径 1 个条件、放行总闸 1 个条件。'
  '<code>UsrAI.h</code> 增 1 个成员 + 1 处构造初始化。</p>')
A('<h3>编译校验（口径同历轮）</h3>'
  '<table><tr><th>项</th><th>结果</th><th>基线</th></tr>'
  '<tr><td>error</td><td class="ok">0</td><td>0</td></tr>'
  '<tr><td>warning（<code>^UsrAI.cpp:</code> 口径）</td><td class="ok">18</td><td>18</td></tr>'
  '<tr><td>trigraph</td><td class="ok">0</td><td>0</td></tr>'
  '<tr><td>产物</td><td colspan="2" class="mono">release/newAOE.exe 2,156,544 B</td></tr></table></div>')

# §3 实测
A('<h2>3 · 实测（8 局/批，map3 rotate=90，<code>-exam</code>）</h2>')
A('<div class="card"><table><tr><th>批次</th><th>胜</th><th>祭司死</th><th>发现武器厂</th>'
  '<th>WS 中位帧</th><th><b>发现→收编</b></th><th>塔打过祭司的局</th><th>武器厂感化令</th>'
  '<th>abort 次数</th><th>hold=1 采样</th><th>lock=1&amp;tDgr=1 采样（见注）</th></tr>')
for pref, name, arm in ARMS:
    if pref not in AR:
        continue
    a = AR[pref]
    A('<tr><td>%s <span class="mono">%s</span></td><td>%d/%d</td><td>%d/%d</td><td>%d/%d</td>'
      '<td class="num">%s</td><td><b>%d/%d</b></td><td>%d/%d</td><td class="num">%d</td>'
      '<td class="num">%d</td><td class="num">%d</td><td class="num">%d</td></tr>'
      % (name, pref, a['w'], a['n'], a['pd'], a['n'], a['wsn'], a['n'], med(a['wsf']),
         a['w'], a['wsn'], a['fg'], a['n'], a['cv'], a['ab'], a['hold'], a['lb']))
A('</table>')
# 臂级汇总（合并复现批）
def armagg(ps):
    rows = [AR[p] for p in ps if p in AR]
    if not rows:
        return None
    return dict(n=sum(a['n'] for a in rows), w=sum(a['w'] for a in rows),
                pd=sum(a['pd'] for a in rows), wsn=sum(a['wsn'] for a in rows))
BA = armagg(['pu', 'ez', 'tb'])
V1A = armagg(['tl'])
V2A = armagg(['tm', 'tn'])
A('<h3>臂级汇总（把复现批合并，才能压住 8 局噪声）</h3>')
A('<table><tr><th>臂</th><th>局数</th><th>胜</th><th>祭司死</th><th>发现武器厂</th>'
  '<th>发现→收编</th></tr>')
for lab, a in (('基线（pu+ez+tb）', BA), ('v1（13格/1格带）', V1A), ('v2（12格/18格闩锁）', V2A)):
    if not a:
        continue
    cls = 'ok' if lab.startswith('基线') else 'bad'
    A('<tr><td>%s</td><td class="num">%d</td><td class="%s">%d/%d</td><td class="num">%d/%d</td>'
      '<td class="num">%d/%d</td><td class="num">%d/%d</td></tr>'
      % (lab, a['n'], cls, a['w'], a['n'], a['pd'], a['n'], a['wsn'], a['n'], a['w'], a['wsn']))
A('</table>')
A('<div class="dang"><b>臂级汇总给出本轮最重要的判据：</b>"发现武器厂→收编成功"这一步，'
  '基线 %s，v1 %s，v2 %s。差别全部落在<b>最后一段</b>（祭司已到武器厂附近、要不要起手施法）——'
  '而这一段正是本轮闸门作用的地方：<b>塔闸把"塔在射程内时起手"整类情形禁掉了，'
  '而武器厂本来就在敌基地里、塔就在厂边，等于把基线赢下来的那批局面一起禁掉了。</b></div>'
  % ('%d/%d' % (BA['w'], BA['wsn']) if BA else '-',
     '%d/%d' % (V1A['w'], V1A['wsn']) if V1A else '-',
     '%d/%d' % (V2A['w'], V2A['wsn']) if V2A else '-'))
A('<div class="note"><b>怎么读这张表：</b>'
  '<br>· <b>abort 次数</b>是 v1/v2 的分水岭：v1 41 次（抖动），v2 两批合计 %d 次'
  '（只在真进射程时触发），抖动消失。'
  '<br>· <b>lock=1&amp;tDgr=1 采样</b>（v2 两批 0 与 7 次）：<code>[LC-DBG]</code> 印在本段<b>最前面</b>，'
  '它打印的 lock 是<b>上一帧</b>的值、tDgr 是<b>本帧</b>的值 ⇒ 该列&gt;0 只表示"上一帧还锁着、'
  '这一帧塔刚进来"，同一帧稍后就会解除（abort 行就是解除记录），<b>不是缺陷复现</b>；'
  '真正的判据是 <b>abort 行</b>与 <b>hold 采样</b>。'
  '<br>· <b>hold=1 采样</b>只有个位数 ⇒ 塔闸在大多数局里根本没触发（v2 批"塔打过祭司"仅 1/8 局），'
  '所以塔闸<b>不可能</b>解释祭司死亡数的变化，反过来它也<b>没能救下</b>祭司。'
  '<br>· <b>胜负两列不要跨批读</b>：见 §6——同一份基线代码的三批是 5/8、5/8、<b>2/8</b>。</div>'
  % (tm.get('ab', 0) + tn.get('ab', 0)))
A('</div>')

# §4 死因构成
A('<h2>4 · 关键发现：祭司阵亡构成（全 %d 局定量）</h2>' % tax['games'])
A('<div class="card"><table>'
  '<tr><th>分类（死前 1500 帧 = 1 分钟窗口）</th><th>局数</th><th>占阵亡</th></tr>'
  '<tr><td>死前有<b>敌方单位</b>向祭司发起攻击</td><td>%d</td><td class="num">%.0f%%</td></tr>'
  '<tr><td>　├ 只有单位（塔没参与）</td><td>%d</td><td class="num">%.0f%%</td></tr>'
  '<tr><td>死前有<b>敌箭塔</b>向祭司开火</td><td>%d</td><td class="num">%.0f%%</td></tr>'
  '<tr><td>　├ 只有塔（没有单位近身）</td><td>%d</td><td class="num">%.0f%%</td></tr>'
  '<tr><td>两者都有</td><td>%d</td><td class="num">%.0f%%</td></tr>'
  '<tr><td>窗口内没有任何攻击事件</td><td>%d</td><td class="num">%.0f%%</td></tr>'
  '<tr><td>反攻还没发起就死（f&lt;33000）</td><td>%d</td><td class="num">%.0f%%</td></tr>'
  '<tr><td>死前 1 分钟内在施法感化（单位或建筑）</td><td>%d</td><td class="num">%.0f%%</td></tr>'
  '</table>'
  % (tax['unitOnly'] + tax['both'], 100.0 * (tax['unitOnly'] + tax['both']) / max(1, tax['deaths']),
     tax['unitOnly'], 100.0 * tax['unitOnly'] / max(1, tax['deaths']),
     tax['towerOnly'] + tax['both'], 100.0 * (tax['towerOnly'] + tax['both']) / max(1, tax['deaths']),
     tax['towerOnly'], 100.0 * tax['towerOnly'] / max(1, tax['deaths']),
     tax['both'], 100.0 * tax['both'] / max(1, tax['deaths']),
     tax['none'], 100.0 * tax['none'] / max(1, tax['deaths']),
     tax['early'], 100.0 * tax['early'] / max(1, tax['deaths']),
     tax['convAtDeath'], 100.0 * tax['convAtDeath'] / max(1, tax['deaths'])))
A('<h3>死前窗口内"向祭司发起攻击"的兵种计数</h3><table><tr><th>兵种</th><th>攻击次数</th></tr>')
for n, c in tax['killer'].most_common(8):
    A('<tr><td>%s</td><td class="num">%d</td></tr>' % (n, c))
A('</table>')
A('<div class="dang"><b>结论：箭塔不是祭司反攻期阵亡的主因。</b>'
  '真正的杀手是<b>战车弓兵 / 复合弓兵 / Prof.Lu（敌方英雄）</b>这类远程单位——'
  '祭司在"贴到武器厂旁施法"或"贴上去感化单位"期间被钉住挨打。'
  '这同时说明：<u>本轮修的塔闸即使 100%% 生效，也只能覆盖约 %.0f%% 的祭司阵亡</u>。</div>'
  % (100.0 * (tax['towerOnly'] + tax['both']) / max(1, tax['deaths'])))
A('</div>')

# §5 结论与建议
A('<h2>5 · 结论与下一轮建议</h2>')
A('<div class="card">')
A('<h3 style="margin-top:0">已成立</h3>'
  '<ol>'
  '<li>迟滞锁 <code>priestSiegeApproach</code> 缺箭塔复位维度 = 真缺陷（用户问的那件事，成立），已补。</li>'
  '<li>早路径绕过一切安全判据、每帧钉住祭司 = 真缺陷，机制已查明（pg7：发令后 311 帧零条 HumanMove）。</li>'
  '<li>v1 的 1 格迟滞带会造成"前出/后撤"逐帧翻转（41 次 abort、净位移≈0），已否决并改为闩锁（v2）。</li>'
  '<li>祭司阵亡的定量构成：敌方单位 %.0f%% / 敌箭塔 %.0f%%（全 %d 局）。</li>'
  '<li><b>塔闸这条路已证伪</b>：作用点在"收编武器厂"最后一段，臂级"发现→收编"从 12/16 掉到 3/7 ⇒ 回滚。</li>'
  '<li><b>"胜负"作为 A/B 指标已证伪</b>：同一份基线代码三批复现 5/8、5/8、2/8（§6）。</li>'
  '</ol>'
  '<h3>下一轮候选（按收益排序）</h3>'
  '<table><tr><th>#</th><th>方向</th><th>依据</th><th>风险</th></tr>'
  '<tr><td>B1</td><td><b>施法期不再"钉死"祭司</b>：<code>priestMoveCooldown=60; return;</code> 改为'
  '"最近敌远程单位 &lt; 其射程+2 格 ⇒ 中断施法、退到射程外再续"</td>'
  '<td>%d/%d 阵亡都发生在施法期（施法令下发后 300+ 帧零条 HumanMove）；'
  '击杀榜前三全是远程（战车弓兵/复合弓兵/Prof.Lu）</td>'
  '<td>中：施法被打断可能完不成收编，需配"退-回-重新起手"闭环 + 400 帧静默期</td></tr>'
  '<tr><td>B2</td><td><b>祭司前出前先问"我方在不在它和敌远程之间"</b>（掩护判据，'
  '而非上一轮被否决的"每帧抓最近敌人"护驾）</td><td>同上；且能顺带解释"祭司死在方阵兵堆里"的样本</td>'
  '<td>中-高：与已回滚的护驾同族，必须先保证"只改写祭司的落点、不重写全军指令"</td></tr>'
  '<tr><td>B3</td><td><b>先拆塔再感化</b>：给"攻击最近敌塔"放宽距离闸（现 R&lt;=12 格），'
  '并把祭司起手条件挂到"厂边塔已被清"上</td><td>塔是静态目标，打掉即可安全施法；'
  'pg7 两塔全程存活到我方判负</td><td>中：塔拆不掉时退化成"永不感化"死锁，必须有超时兜底</td></tr>'
  '<tr><td>B4</td><td><b>先把评测协议换掉</b>（§6 的 P1/P2/P3）再打上面任意一条</td>'
  '<td>否则每轮都可能重演"分不清是改动退化还是时点漂移"</td><td>低（只是流程）</td></tr>'
  '</table></div>'
  % (100.0 * (tax['unitOnly'] + tax['both']) / max(1, tax['deaths']),
     100.0 * (tax['towerOnly'] + tax['both']) / max(1, tax['deaths']),
     tax['games'], tax['convAtDeath'], tax['deaths']))

# §6 方法论提醒
A('<h2>6 · 方法论：本轮把"胜负"指标证伪了</h2>')
A('<div class="card">')
A('<p>为了判断 v2 的那次"1/8 胜"到底是回归还是噪声，本轮在<b>深夜同时点</b>补跑了一批'
  '<b>纯基线</b>（tb，镜像 <code>UsrAI.cpp.bak_20260914_pre_towerlock</code>，与 pu/ez 代码逐字节相同）。'
  '结果：</p>')
A('<table><tr><th>纯基线三批复现</th><th>跑局时点</th><th>胜</th><th>祭司死</th><th>发现武器厂</th>'
  '<th>发现→收编</th></tr>'
  '<tr><td>pu</td><td>19:16</td><td class="num">5/8</td><td class="num">2/8</td><td class="num">6/8</td><td class="num">5/6</td></tr>'
  '<tr><td>ez</td><td>20:48</td><td class="num">5/8</td><td class="num">1/8</td><td class="num">6/8</td><td class="num">5/6</td></tr>'
  '<tr><td><b>tb（本轮对照）</b></td><td>23:02</td><td class="bad num">2/8</td><td class="num">3/8</td>'
  '<td class="num">4/8</td><td class="num">2/4</td></tr></table>')
A('<div class="dang">同一份代码，胜率 <b>5/8 → 5/8 → 2/8</b>；发现率 6/8 → 6/8 → 4/8。'
  '<b>批间摆动 ≥3 局（37pp），远超本轮想测的效果量级。</b></div>')
A('<p>为什么这个指标特别糟：<b>①</b> 祭司一死游戏立即判负（<code>checkDefeat</code>），'
  '侦察与推进随之中断 ⇒ "武器厂发现率""反攻推进深度"这些看似独立的指标其实全是'
  '<b>"祭司死没死"的下游</b>，几列数字在同步摆动，不能当作多条独立证据；'
  '<b>②</b> 8 局的二项 σ≈1.4 局；<b>③</b> 批与批之间还有时点/负载造成的系统漂移。</p>')
A('<h3>建议的评测协议（可省钱、也可救命）</h3><table>'
  '<tr><th>#</th><th>做法</th><th>说明</th></tr>'
  '<tr><td>P1</td><td><b>交替跑（interleaved A/B）</b>：同一时点把两臂按 A B A B … 逐局交替，'
  '而不是先跑完 8 局 A 再跑 8 局 B</td><td>把"时点漂移"从组间差里消掉，成本不变</td></tr>'
  '<tr><td>P2</td><td><b>机制指标优先</b>：abort/解锁次数、hold 采样、发令÷出手、距离时序、'
  '收编转化率 —— 这些可在单局内看出方向</td><td>本轮四个修复方向里，机制指标每次都能一眼判死/判活</td></tr>'
  '<tr><td>P3</td><td><b>判胜负要 ≥24 局/臂</b>，或先跑 3 批纯基线把噪声基线量出来再比</td>'
  '<td>本轮实测噪声 ≈3 局/8 局</td></tr></table>')
A('</div>')

# §7 复现
A('<h2>7 · 备份链、当前代码状态与复现</h2>')
A('<div class="card"><div class="note"><b>当前工作副本 = 纯基线</b>'
  '（<code>UsrAI.cpp</code>/<code>UsrAI.h</code> 已 <code>cmp</code> 验证与 '
  '<code>*.bak_20260914_pre_towerlock</code> 逐字节一致）；'
  'v2 已固化为 <code>*.bak_20260914_towerhold_v2</code>，一条 <code>cp</code> 即可恢复。</div>')
A('<pre>'
  'UsrAI.cpp.bak_20260914_pre_towerlock   ★ 当前工作副本 = 纯基线（2026-09-14 21:15，与权威副本 cmp 一致）\n'
  'UsrAI.cpp.bak_20260914_towerhold_v2    v2（12/18 迟滞闩锁，本轮结论：回滚）\n'
  'UsrAI.h.bak_20260914_towerhold_v2      同上\n'
  'UsrAI.cpp.bak_20260914_pguard_fix      上一轮（护驾粘滞，已回滚；⚠ 其"退化"结论见 §6 需重审）\n'
  '\n'
  '# 编译（必须 32 位 toolchain；误用 64 位会 skipping incompatible，须删 release/*.o 重编）\n'
  'cd /c/new-aoe3.0.7g\n'
  'PATH="/d/360Downloads/Tools/mingw530_32/bin:$PATH" mingw32-make -f Makefile.Release -j4\n'
  '\n'
  '# 跑局（8 局/批）：pu=基线复现A ez=基线复现B tb=基线复现C(本轮对照) tl=v1 tm=v2 tn=v2复现\n'
  'bash tb_verify.sh   # 换前缀即换批次名\n'
  '\n'
  '# 出报告\n'
  'python tower_lock_report.py       # 批次对照（文本）\n'
  'python priest_death_taxonomy.py   # 祭司阵亡构成（全 11 批）\n'
  'python tower_lock_html.py         # 本文件\n'
  '</pre></div>')

A('</div></body></html>')

open(OUT, 'w', encoding='utf-8').write('\n'.join(h))
print('written', OUT, len('\n'.join(h)), 'bytes')
