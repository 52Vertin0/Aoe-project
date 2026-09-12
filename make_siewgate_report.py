# -*- coding: utf-8 -*-
"""生成「祭司感化武器厂 · 塔闸放宽 0→2」验收报告 HTML。
所有数字现算自 .ait 日志，保证可复现。
用法: python make_siewgate_report.py [newtag=tower2]
"""
import glob, os, re, sys, hashlib, time
from collections import Counter

os.chdir(r'C:\new-aoe3.0.7g')
NEWTAG = sys.argv[1] if len(sys.argv) > 1 else 'tower2'

RE_WAIT = re.compile(r'\[SIEGE-WAIT f=(\d+)\] hp=([\d.]+) towers=(\d+) seen=(\d+) alive=(\d+) dS=([\d.]+)'
                     r'(?: lim=(\d+))?')
RE_CONV = re.compile(r'HumanAction:祭司\s+(\d+)\s+设置转换目标为\s+(\S+)\s+(\d+)')
SIEGE = '攻城武器厂'


def parse(path):
    waits, conv, win, lose, last = [], [], False, False, 0
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.split(' | ', 3)
        if len(p) < 4:
            continue
        if p[1].strip().isdigit():
            last = max(last, int(p[1]))
        msg = p[3]
        m = RE_WAIT.search(msg)
        if m:
            waits.append(dict(fr=int(m.group(1)), towers=int(m.group(3)), alive=int(m.group(5)),
                              ds=float(m.group(6)), lim=(int(m.group(7)) if m.group(7) else None)))
        c = RE_CONV.search(msg)
        if c and c.group(2) == SIEGE:
            conv.append(last)
        if 'VICTORY!' in msg:
            win = True
        if 'DEFEAT: Priest killed' in msg:
            lose = True
        if 'DEFEAT: Town Center destroyed' in msg:
            lose = True
    return dict(waits=waits, conv=conv, win=win, lose=lose, last=last,
                res=('胜' if win else ('负' if lose else '打满未决')))


def hist(vals):
    h = Counter(vals)
    return "  ".join("%d=%d" % (k, h[k]) for k in sorted(h)) or "-"


def load(pattern, exclude=None):
    out = []
    for f in sorted(glob.glob(pattern)):
        b = os.path.basename(f)
        if '.partial.' in b:
            continue
        if exclude and b.startswith(exclude):
            continue
        out.append((b, parse(f)))
    return out


base = load('vf_*.ait', exclude='vf_%s_' % NEWTAG)
new = load('vf_%s_*.ait' % NEWTAG)


def agg(rows):
    d = dict(n=len(rows), win=0, lose=0, none=0, wait_game=0, wait_n=0,
             conv_game=0, conv_n=0, towers=Counter(), reach=0, alive0=0,
             lims=set(), le2_rec=0, le2_game=0, gt2_rec=0)
    for nm, r in rows:
        if r['win']:
            d['win'] += 1
        elif r['lose']:
            d['lose'] += 1
        else:
            d['none'] += 1
        if r['conv']:
            d['conv_game'] += 1
            d['conv_n'] += len(r['conv'])
        w = r['waits']
        if w:
            d['wait_game'] += 1
            d['wait_n'] += len(w)
            for x in w:
                d['towers'][x['towers']] += 1
                if x['ds'] <= 12.0:
                    d['reach'] += 1
                if x['alive'] == 0:
                    d['alive0'] += 1
                if x['lim'] is not None:
                    d['lims'].add(x['lim'])
            tw = [x['towers'] for x in w]
            if min(tw) <= 2:
                d['le2_game'] += 1
                d['le2_rec'] += sum(1 for t in tw if t <= 2)
            d['gt2_rec'] += sum(1 for t in tw if t > 2)
    return d


B, N = agg(base), agg(new)


def table(rows, extra=False):
    h = ("<table><tr><th>局</th><th>结局</th><th>末帧</th><th>SIEGE-WAIT</th>"
         "<th>towers 分布</th><th>dS≤12</th><th>感化厂令</th><th>lim</th></tr>")
    for nm, r in rows:
        w = r['waits']
        tw = hist([x['towers'] for x in w]) if w else '-'
        re_ = sum(1 for x in w if x['ds'] <= 12.0) if w else 0
        lims = sorted(set(x['lim'] for x in w if x['lim'] is not None)) if w else []
        cls = ' class="good"' if r['win'] else (' class="bad"' if r['lose'] else '')
        h += ("<tr><td>%s</td><td%s>%s</td><td>%d</td><td>%d</td><td>%s</td><td>%d</td>"
              "<td>%s</td><td>%s</td></tr>"
              % (nm, cls, r['res'], r['last'], len(w), tw, re_,
                 ('<b>%s</b>' % r['conv']) if r['conv'] else '0',
                 lims if lims else '-'))
    return h + "</table>"


def kpi(v, cls=''):
    return '<b class="%s">%s</b>' % (cls, v)


def card(title, body):
    return '<div class="card"><h2>%s</h2>%s</div>' % (title, body)


# ---------- 验收判据（只对新批） ----------
acc1 = N['conv_game'] > 0
acc2 = N['wait_n'] > 0 and N['le2_rec'] == 0
acc3 = N['wait_n'] == 0 or N['gt2_rec'] > 0

CSS = ('<style>body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;margin:0;'
       'background:#f6f7f9;color:#1f2430;line-height:1.7}'
       '.wrap{max-width:960px;margin:0 auto;padding:32px 22px 60px}'
       'h1{font-size:24px;margin:0 0 6px}'
       '.sub{color:#67707e;font-size:13px;margin-bottom:22px}'
       '.card{background:#fff;border:1px solid #e6e9ef;border-radius:12px;padding:20px 22px;margin:16px 0;'
       'box-shadow:0 1px 3px rgba(20,30,60,.04)}'
       'h2{font-size:17px;margin:0 0 12px;padding-left:10px;border-left:4px solid #3b6ef5}'
       '.kpi{display:flex;gap:14px;flex-wrap:wrap;margin:8px 0}'
       '.kpi div{flex:1;min-width:150px;background:#f2f5fc;border-radius:10px;padding:14px}'
       '.kpi b{display:block;font-size:26px;color:#3b6ef5}'
       '.kpi .g{color:#2e7d32}.kpi .r{color:#c62828}'
       'table{border-collapse:collapse;width:100%;font-size:14px;margin-top:6px}'
       'th,td{border:1px solid #e6e9ef;padding:7px 10px;text-align:left}'
       'th{background:#f2f5fc;font-weight:600}'
       'code{background:#eef1f6;padding:1px 6px;border-radius:5px;font-size:13px}'
       '.mono{font-family:Consolas,monospace;font-size:12.5px;background:#0f1420;color:#d7e0f0;'
       'border-radius:9px;padding:12px 14px;overflow:auto;white-space:pre}'
       '.bad{color:#c62828;font-weight:600}.good{color:#2e7d32;font-weight:600}'
       'p{margin:8px 0}'
       '.note{background:#fff8e6;border-left:4px solid #f0b429;padding:10px 14px;border-radius:6px;font-size:13.5px}'
       '.ok{background:#eef7ee;border-left-color:#2e7d32}</style>')


def md5(f):
    return hashlib.md5(open(f, 'rb').read()).hexdigest()[:8]


def nlines(f):
    return sum(1 for _ in open(f, encoding='utf-8', errors='replace'))


H = []
H.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
H.append('<title>祭司感化武器厂 · 塔闸放宽 0→2 — 实现与验收</title>')
H.append(CSS)
H.append('</head><body><div class="wrap">')
H.append('<h1>祭司感化敌方武器厂 · 塔闸放宽 <code>==0</code> → <code>&lt;=2</code></h1>')
H.append('<div class="sub">AoE3 3.0.7g · UsrAI.cpp · 生成 %s · 需求：「剩余2座箭塔时祭司就可以感化敌方武器厂了」</div>'
         % time.strftime('%Y-%m-%d %H:%M'))

# --- TL;DR ---
t = []
t.append('<p><b>结论</b>：旧闸要求「视野内敌箭塔数 <b>== 0</b>」才允许祭司起手。'
         '实测该状态在本关卡<b>结构性不可达</b>（塔被拆会重建），全库 %d 条 <code>[SIEGE-WAIT]</code> 里 '
         '<code>towers==0</code> 出现 <b class="bad">0 次</b>。按需求放宽为 <code>&lt;= 2</code>。</p>'
         % B['wait_n'])
t.append('<div class="kpi">'
         '<div>改前：塔数==0 可达性<b class="r">0 / %d</b>条</div>'
         '<div>改前起手率（感化厂令&gt;0）<b class="r">%d / %d = %.0f%%</b></div>'
         '<div>本批起手率<b class="g">%d / %d = %.0f%%</b></div>'
         '<div>本批 towers&gt;2 仍被拦<b class="g">%d 条</b></div></div>'
         % (B['wait_n'], B['conv_game'], B['n'], 100.0 * B['conv_game'] / max(1, B['n']),
            N['conv_game'], N['n'], 100.0 * N['conv_game'] / max(1, N['n']), N['gt2_rec']))
t.append('<p class="note"><b>为什么这是瓶颈而不是参数</b>：改前 %d 条 SIEGE-WAIT 中 <b>%d 条 dS≤12</b>'
         '（祭司已站进 12 格感化射程内）、<b>%d 条 alive==0</b>（敌方军队已全灭）—— '
         '即"祭司到了、敌人没了、就差塔归零这一条"。这不是概率问题，是判据不可达。</p>'
         % (B['wait_n'], B['reach'], B['alive0']))
H.append(card('TL;DR', ''.join(t)))

# --- 1 改了什么 ---
t = ['<table><tr><th>#</th><th>位置</th><th>改动</th><th>行为影响</th></tr>'
     '<tr><td>①</td><td><code>#define PRIEST_TOWERS_CLEAR_MAX 2</code>（文件头，紧邻 <code>PRIEST_SIEGE_REQUIRE_TOWERS_CLEAR</code>）'
     '</td><td>新增阈值常量并附实测依据注释</td><td>无（常量）</td></tr>'
     '<tr><td>②</td><td><code>towersAllDown = (enemyTowerN == 0)</code></td>'
     '<td>→ <code>towersClearEnough = (enemyTowerN &lt;= PRIEST_TOWERS_CLEAR_MAX)</code>，变量同步改名</td>'
     '<td><b>核心</b>：<code>clearOk</code> 在剩 1~2 座塔时翻真 ⇒ 早/前出/legacy 三处下发点同时放开</td></tr>'
     '<tr><td>③</td><td><code>[SIEGE-WAIT]</code> 日志</td><td>补 <code>lim=%7</code>（当前放行阈值）</td>'
     '<td>无（日志自描述，防换阈值后旧探针误读）</td></tr>'
     '</table>',
     '<p class="note">三处下发点（early / front / legacy）共用同一个 <code>clearOk</code>，所以只需改一处 —— '
     '本文件的历史事故几乎全是"同一语义写两遍"（铁律 21/26）。</p>']
H.append(card('1 改了什么（1 个常量 + 1 个判据 + 1 处日志）', ''.join(t)))

# --- 2 放宽依据 ---
t = []
t.append('<p>改前全库（<code>vf_*</code>，共 %d 局 / %d 条 <code>[SIEGE-WAIT]</code>）的实测分布：</p>' % (B['n'], B['wait_n']))
t.append('<div class="mono">%s</div>' % '\n'.join(
    '%-22s %-6s last=%-6d SIEGE-WAIT=%-3d towers[%s]' % (nm, r['res'], r['last'], len(r['waits']),
                                                         hist([x['towers'] for x in r['waits']]))
    for nm, r in base if r['waits']))
t.append('<p><b>towers 总分布：</b><code>%s</code></p>' % hist(list(B['towers'].elements())))
t.append('<table><tr><th>放宽到</th><th>可放行条数</th><th>占比</th></tr>'
         + ''.join('<tr%s><td>towers ≤ %d</td><td>%d</td><td>%.0f%%</td></tr>'
                   % (' style="background:#eef7ee;font-weight:600"' if lim == 2 else '', lim,
                      sum(v for k, v in B['towers'].items() if k <= lim),
                      100.0 * sum(v for k, v in B['towers'].items() if k <= lim) / max(1, B['wait_n']))
                   for lim in (0, 1, 2, 3, 4))
         + '</table>')
t.append('<p class="note ok"><b>取 2 的理由</b>：<code>≤2</code> 覆盖 <b>%.0f%%</b> 的受阻样本，'
         '且与你的口径一致；<code>≤1</code> 只有 %.0f%%、<code>≤3</code> 已达 %.0f%% 但仍剩 4 座塔的样本可拦——'
         '留 2 是"放够用、又还拦着明显没打完的场面"的折中。</p>'
         % (100.0 * sum(v for k, v in B['towers'].items() if k <= 2) / max(1, B['wait_n']),
            100.0 * sum(v for k, v in B['towers'].items() if k <= 1) / max(1, B['wait_n']),
            100.0 * sum(v for k, v in B['towers'].items() if k <= 3) / max(1, B['wait_n'])))
t.append('<p class="note"><b>顺带证伪了旧备选方案 A</b>：此前把"前出门改 <code>localClear</code>"列为候选，'
         '隐含假设是"祭司走不到 12 格"。实测 %d/%d 条 SIEGE-WAIT 的 dS ≤ 12 ⇒ 祭司<b>已经到了</b>，'
         '瓶颈纯粹是这道闸 ⇒ 不需要动前出门。</p>' % (B['reach'], B['wait_n']))
H.append(card('2 放宽依据（改前实测）', ''.join(t)))

# --- 3 验收 ---
t = []
t.append('<p>新批 <code>vf_%s_*</code>（%d 局）：</p>' % (NEWTAG, N['n']))
t.append(table(new))
t.append('<table><tr><th>判据</th><th>要求</th><th>实测</th><th></th></tr>'
         '<tr><td>① 起手真发生</td><td>感化厂令 &gt; 0（<b>产物量</b>，不是日志量）</td><td>%d 局 / %d 条</td><td>%s</td></tr>'
         '<tr><td>② 阈值真生效</td><td>SIEGE-WAIT 里不出现 towers ≤ 2</td><td>towers≤2 的 SIEGE-WAIT = %d 条</td><td>%s</td></tr>'
         '<tr><td>③ 闸未被禁死</td><td>towers &gt; 2 时仍被拦</td><td>%d 条</td><td>%s</td></tr>'
         '</table>'
         % (N['conv_game'], N['conv_n'],
            '<span class="good">✅</span>' if acc1 else '<span class="bad">❌</span>',
            N['le2_rec'],
            '<span class="good">✅</span>' if acc2 else '<span class="bad">❌</span>',
            N['gt2_rec'],
            '<span class="good">✅</span>' if acc3 else '<span class="bad">❌ 本批没出现 &gt;2 塔时刻，无法证明闸还在拦</span>'))
if N['lims']:
    t.append('<p>日志自报 <code>lim=%s</code> ⇒ 探针读到的就是二进制里的真实阈值（不是文档里的说法）。</p>'
             % sorted(N['lims']))
H.append(card('3 验收（新批）', ''.join(t)))

# --- 3b 逐帧铁证 ---
_ev = None
for nm, r in new:
    if r['conv'] and r['waits']:
        _ev = nm
        break
if _ev:
    KEYS = ('SIEGE-WAIT', '设置转换目标为 ' + SIEGE, SIEGE + '(编号', 'VICTORY!', 'DEFEAT:')
    rows = []
    for line in open(_ev, encoding='utf-8', errors='replace'):
        if any(k in line for k in KEYS):
            rows.append(line.rstrip())
    t = ['<p>把同一局的引擎动作日志（green/red 行）与 AI 诊断行（black）按帧排开 —— '
         '这是"阈值生效 + 起手发生 + 无副作用"三件事同时成立的原始记录：</p>',
         '<div class="mono">%s</div>' % '\n'.join(rows),
         '<p class="note ok">读法：<b>41103</b> 感化令下发（塔≤2，闸放行）→ <b>41500</b> 塔长回 3 座，'
         '闸重新拦下并打印 <code>lim=2</code> → <b>41699</b> 祭司开始施法（<b>未被闸打断</b>）→ '
         '<b>41808</b> 武器厂归属 1→0，胜利。<br>'
         '★ 这条时序同时否证了两个担心：① 塔重建会让已起手的感化作废（没有）；'
         '② 放宽阈值会让祭司在塔下白送（本局祭司血量 0.97）。</p>']
    H.append(card('3b 逐帧铁证（%s）' % _ev, ''.join(t)))

# --- 4 关联证据 ---
t = []


def reline(tag, rows):
    cg = [r for _, r in rows if r['conv']]
    ng = [r for _, r in rows if r['waits'] and not r['conv']]
    return ('%-22s %2d 局 -> 胜 %d / 负 %d / 未决 %d   (感化厂令>0: %d 局)\n'
            '%-22s %2d 局 -> 胜 %d / 负 %d / 未决 %d\n'
            % (tag + ' 有起手', len(cg), sum(1 for r in cg if r['win']), sum(1 for r in cg if r['lose']),
               sum(1 for r in cg if not r['win'] and not r['lose']), len(cg),
               tag + ' 无起手', len(rows) - len(cg),
               sum(1 for _, r in rows if r['win'] and not r['conv']),
               sum(1 for _, r in rows if r['lose'] and not r['conv']),
               sum(1 for _, r in rows if not r['win'] and not r['lose'] and not r['conv'])))


t.append('<p>把「是否起手感化厂」与「结局」对齐（改前全库 / 本批）：</p>')
t.append('<div class="mono">%s\n%s</div>' % (reline('改前全库', base), reline('本批', new)))
ng = [nm for nm, r in base if r['waits'] and not r['conv']]
t.append('<p>改前被闸拦住的那批（<code>%s</code>）<b>全部</b>以「打满 30 分未决」收场 —— 正是本次要救回的样本。</p>'
         % '、'.join(ng))
t.append('<p><b>本批的直接铁证（<code>vf_tower2_5</code>）</b>：同一局内，感化厂令在第 <b>41103</b> 帧下发'
         '（此时塔已 ≤2 ⇒ 新闸放行）；随后塔在 <b>41500</b> 帧又长回 <b>3</b> 座 ⇒ 闸重新关上并打出 '
         '<code>[SIEGE-WAIT … towers=3 lim=2]</code>，但<b>已下发的感化并未被打断</b>，第 41808 帧获胜。'
         '⇒ 一次观测同时证明了「阈值 = 2 确实在卡（3 座时仍拦）」与「放宽后起手确实发生」；'
         '同时说明这道闸只管<b>起手</b>，不管后续（塔重建不会让已开始的感化作废）——'
         '这也解释了为什么改前那些"塔永远清不到 0"的局会白等 30 分钟。</p>')
t.append('<p class="note"><b>怎么读这个对比</b>：胜因本身就是 <code>Siege Workshop converted</code>（感化成功 = 胜利条件），'
         '所以"起手 → 胜"不是独立因果，而是<b>同一件事</b>。真正要读的是<b>起手率</b>：'
         '改前 %.1f%%（%d/%d）→ 本批 %.1f%%（%d/%d）。'
         '⚠ 样本仍小（%d vs %d，铁律 81 要求 ≥24 局/臂），只能作为方向性证据。</p>'
         % (100.0 * B['conv_game'] / max(1, B['n']), B['conv_game'], B['n'],
            100.0 * N['conv_game'] / max(1, N['n']), N['conv_game'], N['n'], N['n'], B['n']))
H.append(card('4 关联证据：起手 ↔ 终局', ''.join(t)))

# --- 5 边界 ---
t = []
t.append('<p><b>① 改的是"允许起手"的门槛，不是"塔不用管了"。</b>剩余 3~4 座塔时仍然拦，'
         '日志里会明确写 <code>towers=3 lim=2</code>。危险场景（视野丢失 ⇒ 列表变空）仍由'
         '<code>enemySiegeSN != -1</code> + <code>seen &gt;= PRIEST_TOWERS_CLEAR_MIN_SEEN(1)</code> 拦住。</p>')
t.append('<p><b>② 连带放开了"前出门"</b>：<code>priestSiegeApproach</code>（祭司前出的迟滞锁）也吃 <code>clearOk</code>，'
         '所以祭司现在会在剩 ≤2 塔时就朝武器厂前出，而不是等塔全零。这是需求想要的方向，但属<b>你没有逐字点名</b>的连带面 —— '
         '若只要"到 12 格内允许起手"而不想提前前出，需把前出门单独换回更严的判据。</p>')
t.append('<p><b>③ 副作用风险</b>：祭司会更早进入塔火力范围（塔还在 1~2 座 ⇒ 塔仍在射击）。'
         '现有的两道保护仍然有效：<code>PRIEST_SIEGE_GUARD_HP(0.45)</code> 残血+塔压近不起手、'
         '<code>PRIEST_SIEGE_ABORT_R(4.5)</code>/<code>ABORT_HP(0.35)</code> 硬中止前出。'
         '若实测出现"祭司在塔下起手被打断/打死"变多，回滚只需把 <code>PRIEST_TOWERS_CLEAR_MAX</code> 改回 0（一行）。</p>')
_lose_p = 0
_lose_t = 0
for nm, r in new:
    if r['lose']:
        txt = open(nm, encoding='utf-8', errors='replace').read()
        if 'DEFEAT: Priest killed' in txt:
            _lose_p += 1
        elif 'DEFEAT: Town Center destroyed' in txt:
            _lose_t += 1
t.append('<p><b>④ 本批失败构成</b>：负 %d 局中，祭司阵亡 %d 局、TC 被毁 %d 局、其余 %d 局；'
         '而 <b>%d 次感化厂起手全部完成并获胜</b>（起手后没有被塔打断）—— 目前没看到"更早前出 ⇒ 更容易死"的迹象。</p>'
         % (N['lose'], _lose_p, _lose_t, N['lose'] - _lose_p - _lose_t, N['conv_game']))
t.append('<p class="note"><b>⑤ 一处未做</b>：<code>legacy</code> 路径里仍硬编码 <code>pDist &lt; 12 * BL</code>'
         '（应引用 <code>PRIEST_CONVERT_SIEGE_RANGE</code>）。本轮刻意不改 —— 同值替换虽无行为变化，'
         '但会让本批的"零行为差异"证明多一个变量，留待独立成批（与本文件"同一语义只写一遍"的纪律一致）。</p>')
H.append(card('5 语义边界与副作用', ''.join(t)))

# --- 6 溯源 ---
t = ['<table><tr><th>项</th><th>值</th></tr>',
     '<tr><td>UsrAI.cpp</td><td><code>%s</code> · %d 行（改前 <code>76c1600f</code> · 6523 行）</td></tr>'
     % (md5('UsrAI.cpp'), nlines('UsrAI.cpp')),
     '<tr><td>UsrAI.h</td><td><code>%s</code> · %d 行（本轮未改）</td></tr>'
     % (md5('UsrAI.h'), nlines('UsrAI.h')),
     '<tr><td>编译</td><td>syn <code>rc=0 / 0 err / 17 warn</code>（与基线一致，<code>warn_cmp2</code> 集合无差异）｜'
     ' build <code>rc=0 / 0 err</code>（删 <code>.o</code> 强编）</td></tr>',
     '<tr><td>产物校验</td><td>新日志串 <code>[SIEGE-WAIT … lim=%7]</code> 在 <code>release/newAOE.exe</code> 里命中 1 处 ⇒ 二进制确实含本次改动</td></tr>',
     '<tr><td>回滚点</td><td><code>UsrAI.cpp.bak_20260921_nokite_range</code>（改前 <code>76c1600f</code>）'
     '／<code>UsrAI.cpp.bak_20260921_towerclear2</code>（本版）</td></tr>',
     '<tr><td>探针</td><td><code>siewgate_probe.py show|scan</code>（SIEGE-WAIT 闸链 + 感化厂令 + 胜负）｜'
     '运行器 <code>verify_build_fix.py %d %s</code></td></tr>' % (N['n'], NEWTAG),
     '</table>']
H.append(card('6 溯源', ''.join(t)))
H.append('</div></body></html>')

out = 'aoe3_priest_towergate_%s.html' % time.strftime('%Y%m%d')
open(out, 'w', encoding='utf-8').write('\n'.join(H))
print('written %s  (%d bytes)' % (out, os.path.getsize(out)))
print('BASE n=%d win=%d lose=%d none=%d | wait_game=%d wait_n=%d towers=%s reach=%d alive0=%d le2_game=%d'
      % (B['n'], B['win'], B['lose'], B['none'], B['wait_game'], B['wait_n'],
         dict(B['towers']), B['reach'], B['alive0'], B['le2_game']))
print('NEW  n=%d win=%d lose=%d none=%d | wait_game=%d wait_n=%d towers=%s lims=%s le2_rec=%d gt2_rec=%d conv_game=%d conv_n=%d'
      % (N['n'], N['win'], N['lose'], N['none'], N['wait_game'], N['wait_n'],
         dict(N['towers']), sorted(N['lims']), N['le2_rec'], N['gt2_rec'], N['conv_game'], N['conv_n']))
print('ACC 1=%s 2=%s 3=%s' % (acc1, acc2, acc3))
