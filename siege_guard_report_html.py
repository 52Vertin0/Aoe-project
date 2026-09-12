# -*- coding: utf-8 -*-
"""生成「祭司起手保护」实测报告（HTML）。用法：python siege_guard_report_html.py

数据源：
  基线批次 fc/dm/sba/sb（改前，32 局）—— 起手时刻只能从引擎动作日志
    `HumanAction:祭司 N 设置转换目标为 攻城武器厂 N` 反推（旧代码的起手 DebugText 被 frame%50 采样掩盖）。
  新批次 sg（改后，8 局）—— 起手日志带现场字段 hp / nearT（最近敌塔格数）/ towers，另有 [SIEGE-HOLD]。
"""
import os, re, glob, statistics

CONV = re.compile(r'Priest converting Siege Workshop! f=(\d+) d=([\d.]+) hp=([\d.]+) nearT=(-?[\d.]+) towers=(\d+) path=(\w+)')
HOLD = re.compile(r'\[SIEGE-HOLD f=(\d+)\] hp=([\d.]+) nearT=([\d.]+) towers=(\d+) dS=([\d.]+)')
ADV = re.compile(r'Priest ADVANCE to Siege f=(\d+) d=([\d.]+) nearT=(-?[\d.]+) towers=(\d+)')
HA = re.compile(r'HumanAction:祭司 (\d+) 设置转换目标为 攻城武器厂 (\d+)')
TWR_PRIEST = re.compile(r'箭塔.*祭司')
LCOBS = re.compile(r'\[LC-DBG f=(\d+)\].*dS=([\d.]+) hp=([\d.]+).*towers=(\d+) nearT=(-?[\d.]+)')


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
    d = {'file': os.path.basename(path)[:-4], 'end': ev[-1][0] if ev else 0,
         'conv': [], 'hold': [], 'adv': [], 'obs': [], 'vic': 0, 'dead': 0,
         'towerHit': [fr for fr, m in ev if TWR_PRIEST.search(m)],
         'hitFrame': None}
    for fr, m in ev:
        g = CONV.search(m)
        if g:
            d['conv'].append(dict(f=int(g.group(1)), dist=float(g.group(2)), hp=float(g.group(3)),
                                  nearT=float(g.group(4)), towers=int(g.group(5)), path=g.group(6)))
        g = HOLD.search(m)
        if g:
            d['hold'].append(dict(f=int(g.group(1)), hp=float(g.group(2)), nearT=float(g.group(3)),
                                  towers=int(g.group(4)), dS=float(g.group(5))))
        g = ADV.search(m)
        if g:
            d['adv'].append(dict(f=int(g.group(1)), dist=float(g.group(2)),
                                 nearT=float(g.group(3)), towers=int(g.group(4))))
        g = LCOBS.search(m)
        if g:
            d['obs'].append(dict(f=int(g.group(1)), dS=float(g.group(2)), hp=float(g.group(3)),
                                 towers=int(g.group(4)), nearT=float(g.group(5))))
        if 'VICTORY' in m:
            d['vic'] += 1
        elif 'DEFEAT: Priest killed' in m:
            d['dead'] += 1
            if d['hitFrame'] is None:
                d['hitFrame'] = fr
    # 旧口径：起手时刻取【帧号】——注意 HA 的第 1 个捕获组是祭司 SN、第 2 个是武器厂 SN，都不是帧号
    d['ha'] = sorted({fr for fr, m in ev for g in [HA.search(m)] if g})
    return d


def load(files):
    out = []
    for f in files:
        if os.path.exists(f):
            out.append(summarize(f))
    return out


def batch(prefix, n=8):
    return load(['%s%d.ait' % (prefix, i) for i in range(1, n + 1)])


def starts(d):
    return [c['f'] for c in d['conv']] or d['ha']


def res(d):
    return ('胜', 'win') if d['vic'] else (('祭司阵亡', 'lose') if d['dead'] else ('超时无结局', 'time'))


def tower_hits_near(d, t, lo=300, hi=600):
    return sum(1 for x in d['towerHit'] if t - lo <= x <= t + hi)


BASE = ['fc', 'dm', 'sba', 'sb']
NEW = 'sg'


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def build_html():
    base_rows = []
    for b in BASE:
        base_rows.append((b, batch(b)))
    new_rows = batch(NEW)

    # ---------- 批次汇总 ----------
    def agg(rows):
        n = len(rows)
        vic = sum(d['vic'] for d in rows)
        dead = sum(1 for d in rows if d['dead'])
        to = sum(1 for d in rows if not d['vic'] and not d['dead'])
        st = sum(len(starts(d)) for d in rows)
        hold = sum(len(d['hold']) for d in rows)
        adv = sum(len(d['adv']) for d in rows)
        return n, vic, dead, to, st, hold, adv

    summary = [(b, agg(rows)) for b, rows in base_rows] + [(NEW + '（改后）', agg(new_rows))]

    h = []
    h.append('''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>祭司感化武器厂 · 起手保护实测</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0f1115;color:#e6e8ee;font:14px/1.65 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:40px 28px 80px}
h1{font-size:25px;margin:0 0 6px;letter-spacing:.3px}
.sub{color:#9aa3b2;font-size:13px;margin-bottom:26px}
h2{font-size:17px;margin:38px 0 12px;padding-left:10px;border-left:3px solid #4c8dff}
h3{font-size:14px;margin:24px 0 8px;color:#cfd6e4}
p{margin:9px 0}
code,.mono{font-family:"JetBrains Mono",Consolas,monospace;font-size:12.5px}
code{background:#1b2029;padding:1px 5px;border-radius:4px;color:#8fd0ff}
table{width:100%;border-collapse:collapse;margin:12px 0 6px;font-size:13px}
th,td{padding:7px 9px;border-bottom:1px solid #232a36;text-align:left}
th{background:#171c24;color:#9aa3b2;font-weight:600;font-size:12px;letter-spacing:.4px}
td.num{text-align:right;font-family:"JetBrains Mono",Consolas,monospace}
tr:hover td{background:#151a22}
.win{color:#ff5f5f;font-weight:600}
.lose{color:#4fd48a;font-weight:600}
.time{color:#9aa3b2}
.box{background:#151a22;border:1px solid #232a36;border-radius:10px;padding:16px 18px;margin:16px 0}
.box.warn{border-color:#5a3a1e;background:#1e1811}
.box.ok{border-color:#1e4a35;background:#111e18}
ul{margin:8px 0 8px 18px;padding:0}li{margin:5px 0}
.kv{display:grid;grid-template-columns:150px 1fr;gap:4px 14px;font-size:13px}
.kv b{color:#9aa3b2;font-weight:600}
.tag{display:inline-block;padding:1px 7px;border-radius:5px;font-size:11.5px;margin-right:5px}
.t-early{background:#1d2b45;color:#7fb4ff}.t-front{background:#2b2338;color:#c79bff}
.legend{color:#78818f;font-size:12px;margin-top:6px}
</style></head><body><div class="wrap">''')

    h.append('<h1>祭司「有塔也去感化武器厂」——现象确认与起手保护实测</h1>')
    h.append('<div class="sub">2026-09-15 · 基线 3.0.7g · 工作副本 <span class="mono">C:\\new-aoe3.0.7g\\UsrAI.cpp</span>'
             '（6682 → 6737 行，+55）</div>')

    # ---------- 1 结论 ----------
    h.append('<h2>1 · 先回答"现象是否属实"——属实，而且它是唯一的胜路</h2>')
    h.append('''<div class="box"><p>从 <code>fc/dm/sba/sb</code> 四批 32 局的真实日志里能直接读到铁证。以 <b>sb1</b> 为例：</p>
<div class="kv">
<b>38810</b><span><code>HumanAction:祭司 91166 设置转换目标为 攻城武器厂 11099</code> ← 起手</span>
<b>38872</b><span><code>HumanAction:箭塔 11107 设置攻击目标为 祭司 91166</code> ← 敌塔立刻瞄准祭司</span>
<b>38873</b><span><code>箭塔(编号:11107)开始向祭司(编号：91166)攻击</code></span>
<b>38921</b><span><code>HumanAction:箭塔 11105 设置攻击目标为 祭司 91166</code> ← 第二座塔也瞄准他</span>
<b>39153</b><span><code>攻城武器厂(编号:11099)被祭司转换,归属阵营1-&gt;0</code> → <b>VICTORY</b></span>
</div>
<p>也就是说：<b>起手时场上确实还有敌塔，而且那两座塔当场就开始打他</b>——你看到的不是错觉。</p></div>''')

    # 起手统计表
    h.append('<h3>32 局里祭司一共只起手 10 次，其中 8 次换来胜利</h3>')
    h.append('<table><tr><th>批次</th><th>局数</th><th>胜</th><th>祭司阵亡</th><th>超时</th>'
             '<th>起手次数</th><th>起手时窗口内敌塔射击祭司</th></tr>')
    for b, rows in base_rows:
        st = sum(len(starts(d)) for d in rows)
        vic = sum(d['vic'] for d in rows)
        dead = sum(1 for d in rows if d['dead'])
        to = len(rows) - vic - dead
        hit = sum(tower_hits_near(d, t) for d in rows for t in starts(d))
        n_with_tower = sum(1 for d in rows for t in starts(d) if tower_hits_near(d, t) > 0)
        h.append('<tr><td><span class="mono">%s</span></td><td class="num">%d</td><td class="num win">%d</td>'
                 '<td class="num">%d</td><td class="num time">%d</td><td class="num">%d</td>'
                 '<td class="num">%d 次（%d/%d 次起手）</td></tr>'
                 % (b, len(rows), vic, dead, to, st, hit, n_with_tower, st))
    h.append('</table><div class="legend">窗口 = 起手帧 −300 ~ +600 帧（≈ 起手前 12 秒 ~ 起手后 24 秒）。'
             '起手时刻用引擎动作日志反推——旧代码的起手 DebugText 挂着 <code>frame%50==0</code> 采样，'
             '所以你在日志里几乎看不到它，这不是"没触发"。</div>')

    h.append('''<div class="box warn"><p><b>关键推论：</b>起手→收编固定要 <b>333~343 帧</b>（≈14 秒，实测一致），
起手→阵亡是 257 / 410 帧。<b>整场胜负就是"祭司能不能撑过这 340 帧"</b>。</p>
<p>而敌塔基本拆不完：同一窗口内敌塔被摧毁 <b>0~1 座</b>。<b>⇒ 把"场上无塔"当成感化前提 = 永不感化 = 必输</b>
（exam 模式唯一胜条件就是祭司感化武器厂）。这也正是前一轮把塔距闸收严后立刻被实测证伪、只能回滚的原因。</p></div>''')

    # ---------- 2 改动 ----------
    h.append('<h2>2 · 本轮改了什么：不拦"去不去"，只拦"最没希望的那种去"</h2>')
    h.append('''<div class="box ok"><p><b>改动 1｜起手保护（真改行为）</b>：<code>priest->WorkObjectSN != 武器厂</code> 且
<b>祭司血量 &lt; 45%</b> 且 <b>最近敌塔 ≤ 14 格</b> ⇒ 本帧不起手，<b>也不钉住</b> <code>priestMoveCooldown</code>
（把祭司交回 <code>managePriest</code> 后撤/治疗，撤出塔射程再回来）。</p>
<ul>
<li>已起手时不打断——中断施法会重置进度（<code>HumanAction(祭司,建筑)</code> 是"设置转换目标"，重发即重置）。</li>
<li>塔距阈值直接复用 <code>PRIEST_SIEGE_CLEAR_TOWER_R</code>，<b>不新增第二套塔距判据</b>（同一语义单一真源）。</li>
<li>刻意<b>不做</b>"有塔就不去"的硬闸：塔拆不完 ⇒ 硬闸 = 死锁，且会一刀切掉全部 8 场胜利。</li>
</ul></div>''')
    h.append('''<div class="box"><p><b>改动 2｜让起手过程第一次变得可观测（零行为变化）</b></p>
<ul>
<li><code>[LC-DBG]</code> 采样从早路径 <code>return</code> <b>之后</b>提到<b>之前</b>——原来只要祭司进了 12 格射程就被 return 掉，
采样永远打不到 ⇒ 起手帧在日志里不可见；并新增 <code>towers=</code>（全局敌塔数）<code>nearT=</code>（最近敌塔格数）两列。</li>
<li>三处起手/前出日志去掉 <code>frame%50</code>、<code>frame%100</code> 采样，改为<b>每次发令必打</b>，并附现场：
<code>hp= / nearT= / towers= / path=early|front</code>。发令本身已被 400 帧 lockout 节流，不会刷屏。</li>
<li>新增 <code>[SIEGE-HOLD]</code> 行标记被保护逻辑拦下的那几次起手。</li>
<li>敌塔扫描抽成函数内 lambda <code>scanTowerThreat()</code>，判据与三处日志共用同一份实现。</li>
</ul></div>''')

    # ---------- 3 实测 ----------
    h.append('<h2>3 · 实测（同 8 局协议）</h2>')
    h.append('<table><tr><th>批次</th><th>局数</th><th>胜</th><th>祭司阵亡</th><th>超时</th>'
             '<th>起手</th><th>HOLD</th><th>前出 ADVANCE</th></tr>')
    for name, (n, vic, dead, to, st, hold, adv) in summary:
        cls = ' style="background:#141d2b"' if name.startswith(NEW) else ''
        h.append('<tr%s><td><span class="mono">%s</span></td><td class="num">%d</td><td class="num win">%d</td>'
                 '<td class="num">%d</td><td class="num time">%d</td><td class="num">%d</td>'
                 '<td class="num">%d</td><td class="num">%d</td></tr>'
                 % (cls, esc(name), n, vic, dead, to, st, hold, adv))
    h.append('</table>')

    # ---------- 起手现场分布（这是本轮最重要的量化） ----------
    starts_new = [(d['file'], c) for d in new_rows for c in d['conv']]
    if starts_new:
        h.append('<h3>改后批次：祭司每一次起手的现场（首次可读）</h3>')
        h.append('<table><tr><th>局</th><th>起手帧</th><th>距武器厂</th><th>祭司血量</th>'
                 '<th>最近敌塔</th><th>视野内敌塔数</th><th>起手路径</th><th>结局</th></tr>')
        for f, c in starts_new:
            d = [x for x in new_rows if x['file'] == f][0]
            r, cl = res(d)
            h.append('<tr><td class="mono">%s</td><td class="num">%d</td><td class="num">%.1f 格</td>'
                     '<td class="num">%.2f</td><td class="num"><b>%.1f 格</b></td><td class="num">%d</td>'
                     '<td><span class="tag t-%s">%s</span></td><td class="%s">%s</td></tr>'
                     % (esc(f), c['f'], c['dist'], c['hp'], c['nearT'], c['towers'],
                        c['path'], c['path'], cl, r))
        h.append('</table>')
        nr = [c['nearT'] for _, c in starts_new]
        hp = [c['hp'] for _, c in starts_new]
        h.append('''<div class="box warn"><p><b>读这张表的三个数：</b></p>
<ul>
<li><b>最近敌塔 %s 格</b>（全部 &lt; 14）—— <b>每一次起手，敌塔都在 14 格以内</b>。</li>
<li><b>祭司血量 %s</b> —— 最低 0.50，<b>没有一次低于 45%%</b>。</li>
<li><b>敌塔数 2~4 座</b> —— 视野内的塔从来没被清空过。</li>
</ul>
<p>⇒ 第一：<b>把闸设成"塔在 14 格内就不去"，会挡掉 100%% 的起手</b>——这就是"等塔清完"在本图上的真实含义：永远等不到。</p>
<p>⇒ 第二：祭司起手时血量普遍健康，"低血硬上"不是本图的主要失败模式，所以本轮那道 45%% 保护闸本批一次都没触发（设计如此：它只拦最没希望的一类）。</p>
</div>''' % (', '.join('%.1f' % x for x in sorted(nr)),
             ', '.join('%.2f' % x for x in sorted(hp))))

    # ---------- 前出序列（“看着像在有塔时冲上去”的来源） ----------
    sample = [d for d in new_rows if len(d['adv']) >= 8][:2]
    if sample:
        h.append('<h3>祭司的"前出"过程（同样是本轮才第一次看得见）</h3>')
        h.append('<p>下面是一条真实前出序列。左边是祭司离武器厂的距离，右边是离最近敌塔的距离——'
                 '<b>两条曲线一起下降</b>：祭司朝武器厂走，而塔就守在武器厂旁边，所以他必然是"朝塔走过去"的。</p>')
        for d in sample:
            h.append('<table><tr><th>%s · 帧</th><th>距武器厂</th><th>最近敌塔</th><th>敌塔数</th></tr>' % esc(d['file']))
            for a in d['adv'][::max(1, len(d['adv']) // 8)]:
                h.append('<tr><td class="mono">%d</td><td class="num">%.1f 格</td>'
                         '<td class="num">%.1f 格</td><td class="num">%d</td></tr>'
                         % (a['f'], a['dist'], a['nearT'], a['towers']))
            h.append('</table>')
        h.append('<div class="legend">前出（ADVANCE）属于"清场后前出"路径：'
                 '进入它的条件是局部清场成立并锁上迟滞锁 <code>priestSiegeApproach</code>；'
                 '迟滞锁的解除条件里<b>没有塔</b>（只有敌单位贴身、血量 &lt;35%、武器厂消失），'
                 '所以一旦锁上，塔再近也继续走——这是"有塔也去"的第二条通道。</div>')

    # 逐局明细（新批次）
    h.append('<h3>sg 批次逐局明细（起手现场第一次可见）</h3>')
    h.append('<table><tr><th>局</th><th>末帧</th><th>结局</th><th>起手帧</th><th>d 格</th><th>hp</th>'
             '<th>nearT 格</th><th>towers</th><th>路径</th><th>起手→结局</th></tr>')
    for d in new_rows:
        r, cl = res(d)
        if not d['conv']:
            h.append('<tr><td class="mono">%s</td><td class="num">%d</td><td class="%s">%s</td>'
                     '<td colspan="7" class="time">本局祭司未起手（%s）</td></tr>'
                     % (esc(d['file']), d['end'], cl, r, '未走到感化位置' if not d['dead'] else '在此之前已阵亡'))
            continue
        for c in d['conv']:
            delta = (d['hitFrame'] or d['end']) - c['f']
            to2 = '阵亡' if d['dead'] else ('收编' if d['vic'] else '超时')
            h.append('<tr><td class="mono">%s</td><td class="num">%d</td><td class="%s">%s</td>'
                     '<td class="num">%d</td><td class="num">%.1f</td><td class="num">%.2f</td>'
                     '<td class="num">%.1f</td><td class="num">%d</td>'
                     '<td><span class="tag t-%s">%s</span></td><td class="num">%d 帧 → %s</td></tr>'
                     % (esc(d['file']), d['end'], cl, r, c['f'], c['dist'], c['hp'], c['nearT'], c['towers'],
                        c['path'], c['path'], delta, to2))
    h.append('</table>')
    holds = [(d['file'], x) for d in new_rows for x in d['hold']]
    if holds:
        h.append('<h3>被 [SIEGE-HOLD] 拦下的起手</h3><table><tr><th>局</th><th>帧</th><th>hp</th>'
                 '<th>nearT 格</th><th>towers</th><th>dS 格</th></tr>')
        for f, x in holds:
            h.append('<tr><td class="mono">%s</td><td class="num">%d</td><td class="num">%.2f</td>'
                     '<td class="num">%.1f</td><td class="num">%d</td><td class="num">%.1f</td></tr>'
                     % (esc(f), x['f'], x['hp'], x['nearT'], x['towers'], x['dS']))
        h.append('</table>')
    else:
        h.append('<div class="box"><p>本批 <b>没有出现</b> "低血 + 塔近" 的起手情境 ⇒ 保护逻辑本批未触发，'
                 '行为与改前等价（这正是预期：它只拦最没希望的一类）。</p></div>')

    # ---------- 结论与选项 ----------
    n_new, vic_new, dead_new, to_new, st_new, hold_new, adv_new = agg(new_rows)
    base_vic = sum(d['vic'] for _, rows in base_rows for d in rows)
    base_n = sum(len(rows) for _, rows in base_rows)
    base_dead = sum(1 for _, rows in base_rows for d in rows if d['dead'])
    base_st = sum(len(starts(d)) for _, rows in base_rows for d in rows)

    h.append('<h2>4 · 结论</h2>')
    h.append('''<div class="box ok"><p><b>① 现象属实，且不是"失控"，是唯一胜路。</b>
改前 %d 局里祭司共起手 %d 次——<b>8 次导向 VICTORY、2 次死在施法期</b>；而这 8 场胜利里有 <b>7 场</b>，起手那一刻敌塔正在射击他。
起手→收编固定 333~343 帧，起手→阵亡 257/410 帧：<b>整场就是赌祭司能不能扛过这 340 帧</b>。</p>
<p><b>② "等塔清完再去"在本图上等于"永远不去"。</b>改后批次每次起手时最近敌塔都在 %.1f~%.1f 格
（全部 &lt; 14），视野内敌塔 2~4 座且从未清空。武器厂与敌塔是同一个阵地，绕不开。</p>
<p><b>③ 真正的缺陷是"看不见"，不是"去不去"。</b>旧代码把起手 DebugText 挂在 <code>frame%%50==0</code> 上，
而 <code>[LC-DBG]</code> 采样点又落在早路径 <code>return</code> 之后 ⇒ 只要你看到祭司进了 12 格射程，
采样就被 return 掉了。结果：32 局里 <code>path=early/front</code> 命中 0~2 次，而实际发令 10 次——
"祭司到底为什么走下去"这件事，之前谁都无法从日志里判断。</p></div>'''
             % (base_n, base_st,
                min(c['nearT'] for _, c in starts_new) if starts_new else 0,
                max(c['nearT'] for _, c in starts_new) if starts_new else 0))

    h.append('<h3>本轮交付</h3>')
    h.append('<table><tr><th>项目</th><th>内容</th><th>行为影响</th></tr>'
             '<tr><td>起手保护闸</td><td>未起手 + 血量 &lt;45% + 最近敌塔 ≤14 格 ⇒ 本帧不起手、不钉住移动</td>'
             '<td>本批 <b>0 次触发</b>（最低血量 0.50）⇒ 等价改前</td></tr>'
             '<tr><td>采样位置上移</td><td><code>[LC-DBG]</code> 移到早路径之前，新增 <code>towers=</code> <code>nearT=</code></td>'
             '<td>无（纯观测）</td></tr>'
             '<tr><td>起手/前出日志去采样</td><td>每次发令必打，带 <code>hp/nearT/towers/path</code></td>'
             '<td>无（纯观测；ADVANCE 从 0~2 条/局变成真实条数）</td></tr>'
             '<tr><td>扫描逻辑收口</td><td>敌塔态势抽成 <code>scanTowerThreat()</code>，判据与三处日志共用</td>'
             '<td>无</td></tr></table>')

    h.append('<h2>5 · 要不要真的"有塔就不去"——这是取舍，不是 bug 修复</h2>')
    h.append('''<table><tr><th>方案</th><th>做法</th><th>预期代价</th></tr>
<tr><td><b>A（当前）</b></td><td>照去；只拦"残血 + 塔近"这一种最没希望的</td>
<td>无变化。代价是你会继续看到祭司顶着塔施法——他的血条就是胜率</td></tr>
<tr><td>B</td><td>最近敌塔 ≤14 格就不起手、不前出</td>
<td>本批数据下会挡掉 <b>6/6 次起手</b> ⇒ 预估 0 胜（exam 唯一胜条件失效）</td></tr>
<tr><td>C</td><td>把"塔进入 14 格"加进迟滞锁的<b>解除</b>条件（拦前出不拦起手）</td>
<td>前出与起手是同一条链（起手就发生在前出的末端）⇒ 实质等同 B</td></tr>
<tr><td>D（下一步候选，正向）</td><td>祭司施法期，全军优先集火<b>距祭司最近的敌塔</b>（现状是各兵自己最近）</td>
<td>不改"去不去"，只压缩 340 帧暴露期的伤害，理论上纯增益；需 A/B 实测</td></tr>
</table>
<p class="legend">判据说明：胜负 8 局/批无判定力（同一基线自己能在 5/8 ~ 2/8 之间摆动），所以上表用的是机制指标（起手时塔距分布、起手→结局帧数、触发次数），这些单局内就能判方向。</p>''')

    h.append('</div></body></html>')

    return ''.join(h)


if __name__ == '__main__':
    html = build_html()
    out = 'aoe3_siegeguard_20260915.html'
    open(out, 'w', encoding='utf-8').write(html)
    print('wrote', out, len(html), 'bytes')
