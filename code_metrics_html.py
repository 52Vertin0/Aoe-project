# -*- coding: utf-8 -*-
"""UsrAI.cpp 结构度量报告（HTML）。数据源 = code_metrics.py 的解析结果。"""
import re, os, collections, statistics as st
import code_metrics as cm

L, N, funcs = cm.L, cm.N, cm.funcs
A = []
def w(s): A.append(s)

# ---------- 复算 ----------
rows = []
for f in funcs:
    lines = L[f['start'] - 1:f['end']]
    b, c, m = cm.classify(lines)
    rows.append(dict(name=f['name'], st=f['start'], en=f['end'], body=f['body'],
                     blank=b, code=c, cmt=m, nest=cm.max_nest(lines)))
rows.sort(key=lambda r: -r['body'])
tot_body = sum(r['body'] for r in rows)
blank, code, cmt = cm.classify(L)

# 段
segdata = {}
for f in funcs:
    if f['body'] <= 200:
        continue
    lines = L[f['start'] - 1:f['end']]
    marks = [(j, s.strip()) for j, s in enumerate(lines) if cm.is_seg_title(s)]
    if not marks:
        continue
    segs = []
    for k, (j, txt) in enumerate(marks):
        nxt = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
        b2, c2, m2 = cm.classify(lines[j:nxt])
        segs.append(dict(line=f['start'] + j, n=nxt - j, code=c2, cmt=m2, txt=txt))
    segdata[f['name']] = dict(meta=f, segs=segs)

# 深度
hist = collections.Counter(); deep = collections.defaultdict(list)
for f in funcs:
    for j, s in enumerate(L[f['start'] - 1:f['end']]):
        t = s.strip()
        if not t or t.startswith('//'):
            continue
        d = (len(s) - len(s.lstrip(' '))) // 4
        hist[d] += 1
        if d >= 6:
            deep[f['name']].append(d)
tot_code_lines = sum(hist.values())

# 发令点
CALLS = ['HumanAction', 'HumanMove', 'HumanBuild', 'DebugText']
callrows = []
for f in funcs:
    t = '\n'.join(x.split('//')[0] for x in L[f['start'] - 1:f['end']])
    cnt = {c: len(re.findall(r'\b' + c + r'\s*\(', t)) for c in CALLS}
    if sum(cnt.values()):
        callrows.append((sum(cnt[c] for c in CALLS[:3]), f['name'], f['body'], cnt))
callrows.sort(reverse=True)

def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# ---------- 写入 ----------
w('''<style>
:root{--ink:#1a1a1a;--mut:#6b7280;--line:#e5e7eb;--bg:#fafafa;--card:#fff;
--blue:#1d4ed8;--red:#b42318;--amber:#b45309;--green:#15803d;--violet:#6d28d9}
*{box-sizing:border-box}
body{margin:0;padding:34px 30px 70px;background:var(--bg);color:var(--ink);
font:14px/1.7 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1180px;margin:0 auto}
h1{font-size:25px;margin:0 0 6px;letter-spacing:-.3px}
h2{font-size:19px;margin:34px 0 12px;padding-bottom:7px;border-bottom:2px solid var(--line)}
h3{font-size:15px;margin:22px 0 8px;color:var(--violet)}
.sub{color:var(--mut);font-size:13px;margin-bottom:22px}
.card{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:16px 18px;margin:12px 0}
.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:11px;margin:14px 0}
.kpi div{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:12px 14px}
.kpi b{display:block;font-size:23px;line-height:1.25;letter-spacing:-.5px}
.kpi span{color:var(--mut);font-size:12px}
table{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0}
th,td{padding:6px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#f3f4f6;font-weight:600;font-size:12px;color:#374151;white-space:nowrap}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tr:hover td{background:#fcfcfd}
.mono{font-family:ui-monospace,Consolas,"Courier New",monospace;font-size:12px}
.bar{height:11px;border-radius:3px;background:var(--blue);display:inline-block;vertical-align:middle}
.bar.red{background:var(--red)}.bar.amber{background:var(--amber)}.bar.green{background:var(--green)}
.note{background:#fff7ed;border-left:4px solid var(--amber);padding:11px 14px;border-radius:0 7px 7px 0;
font-size:13px;margin:12px 0}
.note.b{border-color:var(--blue);background:#eff6ff}
.note.r{border-color:var(--red);background:#fef2f2}
.note.g{border-color:var(--green);background:#f0fdf4}
details{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:10px 16px;margin:10px 0}
summary{cursor:pointer;font-weight:600;font-size:14px;padding:4px 0}
summary:hover{color:var(--blue)}
pre{background:#f8f9fb;border:1px solid var(--line);border-radius:7px;padding:12px;
overflow:auto;font-size:12px;font-family:ui-monospace,Consolas,monospace;line-height:1.5}
.pill{display:inline-block;padding:1px 7px;border-radius:99px;font-size:11px;font-weight:600}
.p-red{background:#fee2e2;color:var(--red)}.p-amber{background:#fef3c7;color:var(--amber)}
.p-green{background:#dcfce7;color:var(--green)}.p-blue{background:#dbeafe;color:var(--blue)}
.p-gray{background:#f3f4f6;color:#4b5563}
.tag{color:var(--mut);font-size:12px}
</style>''')

w('<div class="wrap">')
w('<h1>UsrAI.cpp 结构度量 —— 优化前基线</h1>')
w('<div class="sub">生成于 2026-09-15 · 源码 <span class="mono">C:\\new-aoe3.0.7g\\UsrAI.cpp</span>'
  '（工作副本 = 农场 v3）· 共 %d 行 / %d 个函数 / 117 个宏</div>' % (N, len(funcs)))

# KPI
top4 = sum(r['body'] for r in rows[:4])
top7 = sum(r['body'] for r in rows[:7])
w('<div class="kpi">')
for v, lab in [(('%d' % N), '总行数（.cpp）'),
               (('%d' % len(funcs)), '函数个数'),
               (('%.0f%%' % (100.0 * cmt / (code + cmt))), '注释占比（非空行）'),
               (('%.0f%%' % (100.0 * top7 / tot_body)), '前 7 个函数占代码量'),
               (('%.0f%%' % (100.0 * sum(len(v) for v in deep.values()) / tot_code_lines)), '嵌套 ≥6 层占比'),
               (('6 处'), '重复代码块（≥6 行）')]:
    w('<div><b>%s</b><span>%s</span></div>' % (v, lab))
w('</div>')

w('<div class="note b"><b>一句话结论：</b>代码量极度集中 —— <b>4 个函数占 50.7%</b>（manageCounterAttack 1202 / '
  'manageBuildings 794 / managePriest 740 / manageMilitary 602），其中 <b>manageCounterAttack 一个函数 = 全文件的 1/5</b>；'
  '而它内部还有 <b>单个 289 行的功能段</b>（远程兵打-拉相位机）。'
  '真正拖慢维护的不是"长"，是<b>长 + 深嵌套 + 职责混杂</b>：'
  'managePriest 嵌到 11 层、assignIdleFarmers 里塞着一个约 400 行的祭司探路状态机。'
  '好消息是<b>没有死宏、几乎没有死代码</b>（117/117 宏在用），所以优化空间在"结构"，不在"清理垃圾"。</div>')

# ---------------- 1. 函数长度 ----------------
w('<h2>1 · 函数长度排行</h2>')
w('<div class="card"><table><tr><th>#</th><th>函数</th><th class="num">行数</th>'
  '<th class="num">代码</th><th class="num">注释</th><th class="num">注释%</th><th class="num">嵌套</th>'
  '<th>长度（相对）</th><th class="num">起始行</th></tr>')
mx = rows[0]['body']
for i, r in enumerate(rows):
    if r['body'] < 5:
        continue
    color = 'red' if r['body'] >= 600 else ('amber' if r['body'] >= 300 else '')
    w('<tr><td class="num">%d</td><td class="mono">%s</td><td class="num"><b>%d</b></td>'
      '<td class="num">%d</td><td class="num">%d</td><td class="num">%.0f%%</td>'
      '<td class="num"%s>%d</td><td><span class="bar %s" style="width:%dpx"></span></td>'
      '<td class="num tag">L%d</td></tr>'
      % (i + 1, r['name'], r['body'], r['code'], r['cmt'],
         100.0 * r['cmt'] / max(1, r['body']),
         ' style="color:#b42318;font-weight:600"' if r['nest'] >= 9 else '',
         r['nest'], color, max(2, int(210.0 * r['body'] / mx)), r['st']))
w('</table>')
w('<div class="note">条形 = 行数相对值（<span class="pill p-red">红</span> ≥600 行 · '
  '<span class="pill p-amber">橙</span> ≥300 行）。"嵌套"列 = 最大缩进层数（4 空格 = 1 层）；'
  '<b>≥9 层的函数有 4 个</b>（managePriest 11 / assignIdleFarmers 10 / manageCounterAttack 9 / manageBuildings 9 / manageMilitary 9），'
  '这几个函数每改一处都要跨 9~11 层作用域推理。</div>')
w('</div>')

# 帕累托
w('<h3>帕累托：改动成本集中在哪里</h3>')
w('<div class="card"><table><tr><th>累计</th><th>纳入函数</th><th class="num">合计行数</th>'
  '<th class="num">占比</th></tr>')
acc = 0
for k in (4, 7, 12):
    acc = sum(r['body'] for r in rows[:k])
    w('<tr><td>前 %d 个</td><td class="mono">%s</td><td class="num">%d</td><td class="num">%.1f%%</td></tr>'
      % (k, ' , '.join(r['name'] for r in rows[:k]), acc, 100.0 * acc / tot_body))
w('</table><div class="note g"><b>读法：</b>只梳理前 7 个函数（占 70%），就等于梳理了整个文件；'
  '其余 46 个函数（平均 43 行）可以直接跳过。'
  '<b>优化排期应严格按这张表的顺序</b>，不要从"看起来丑的小函数"开始。</div></div>')

# ---------------- 2. 嵌套 ----------------
w('<h2>2 · 嵌套深度分布</h2>')
w('<div class="card"><table><tr><th class="num">深度</th><th class="num">行数</th><th class="num">占比</th><th>分布</th></tr>')
for d in sorted(hist):
    p = 100.0 * hist[d] / tot_code_lines
    cls = 'red' if d >= 8 else ('amber' if d >= 6 else '')
    w('<tr><td class="num">%d</td><td class="num">%d</td><td class="num">%.1f%%</td>'
      '<td><span class="bar %s" style="width:%dpx"></span></td></tr>'
      % (d, hist[d], p, cls, max(1, int(420.0 * hist[d] / max(hist.values())))))
w('</table>')
deep_tot = sum(len(v) for v in deep.values())
w('<div class="note r"><b>深度 ≥6 的 %d 行（%.1f%%）是"改不动的区域"</b>：' %
  (deep_tot, 100.0 * deep_tot / tot_code_lines))
for name, ds in sorted(deep.items(), key=lambda x: -len(x[1]))[:6]:
    w('<br>· <span class="mono">%s</span> —— %d 行在 6~%d 层' % (name, len(ds), max(ds)))
w('<br>深度 8+ 集中在 <b>assignIdleFarmers</b>（51 行）与 <b>manageCounterAttack</b>（48 行）。'
  '这两处的共同点是"多层 for 循环里嵌 if 链"，抽子函数时最需要小心（循环变量要显式传参）。</div>')
w('</div>')

# ---------------- 3. 功能段 ----------------
w('<h2>3 · 大函数内部的功能段</h2>')
w('<div class="note b">段标题 = 代码里的 <span class="mono">// ★ / // ==== / // ----</span> 分隔注释。'
  '这是本文件事实上的"模块边界"——<b>但只有注释，没有函数边界</b>：'
  '一个段里的局部变量会泄漏到下一个段（这正是过去几次"标志位互相覆盖"类 bug 的温床）。</div>')

segcount = {n: len(d['segs']) for n, d in segdata.items()}
w('<div class="card"><table><tr><th>函数</th><th class="num">行数</th><th class="num">段数</th>'
  '<th class="num">平均段长</th><th class="num">最长段</th><th>最长段内容</th></tr>')
for n, d in sorted(segdata.items(), key=lambda x: -x[1]['meta']['body']):
    ss = d['segs']
    lg = max(ss, key=lambda s: s['n'])
    w('<tr><td class="mono">%s</td><td class="num">%d</td><td class="num">%d</td>'
      '<td class="num">%.0f</td><td class="num"><b>%d</b> <span class="tag">@L%d</span></td>'
      '<td class="tag">%s</td></tr>'
      % (n, d['meta']['body'], len(ss), d['meta']['body'] / max(1, len(ss)),
         lg['n'], lg['line'], esc(lg['txt'][2:80])))
w('</table></div>')

for n, d in sorted(segdata.items(), key=lambda x: -x[1]['meta']['body']):
    ss = sorted(d['segs'], key=lambda s: -s['n'])[:12]
    w('<details><summary>%s（%d 行 · %d 段）—— 最大的 %d 段</summary>'
      % (n, d['meta']['body'], len(d['segs']), len(ss)))
    w('<table><tr><th class="num">行号</th><th class="num">段长</th><th class="num">码/注</th><th>段标题</th></tr>')
    for s in ss:
        cls = ' style="color:#b42318;font-weight:600"' if s['n'] >= 100 else ''
        w('<tr><td class="num mono">L%d</td><td class="num"%s>%d</td><td class="num tag">%d/%d</td>'
          '<td>%s</td></tr>' % (s['line'], cls, s['n'], s['code'], s['cmt'], esc(s['txt'][2:110])))
    w('</table></details>')

# ---------------- 4. 重复 ----------------
w('<h2>4 · 重复代码块（可直接抽函数）</h2>')
w('<div class="note">判定：去注释 / 数字→N / 去全部空白后，<b>连续 ≥6 行完全相同</b>，'
  '并按"最长匹配"聚簇（同一个复制粘贴只报一次）。</div>')
DUPS = [
    (10, ['assignIdleFarmers:L2440', 'assignIdleFarmers:L2529'],
     '探路绕行落点计算（away 向量归一化 + 12 格外推 + 地图 clamp + HumanMove）',
     '抽 <span class="mono">scoutMoveAway(SN, fromX, fromY, dist)</span>', '低'),
    (9, ['manageCounterAttack:L5019', 'manageCounterAttack:L5041', 'manageCounterAttack:L5065'],
     '落点 clamp + 可达性预检 + HumanMove + march 记账（4 个 map 同时写）',
     '抽 <span class="mono">marchMoveTo(a, rx, ry)</span>——顺带把"记账四件套"收口，杜绝以后漏写一个 map',
     '低'),
    (8, ['assignIdleFarmers:L2645', 'assignIdleFarmers:L2701'],
     '路径前方 8 格内的障碍/危险点投影检测（点线距离 + 参数 t 截断）',
     '抽 <span class="mono">blockedAhead(sx, sy, wx, wy, lookahead)</span>', '低'),
    (7, ['manageMilitary:L4287', 'manageMilitary:L4306'],
     '"全军扑向正在攻击祭司的敌人"的两段同构遍历（含同样的 4 个 continue 过滤）',
     '抽 <span class="mono">orderGuardOnPriest(attackerSN)</span>', '低-中'),
    (6, ['managePriest:L706', 'managePriest:L947'],
     '落点占用检测（2.5 格内有建筑 / 2.0 格内有军队 / 敌方单位 → 判定非法）',
     '抽 <span class="mono">isLandingBlocked(x, y)</span>——注意两处半径常量可能已漂移，抽之前先对齐',
     '低'),
    (6, ['findNearestEnemyTower:L5789', 'findCatapultTarget:L5938',
          '（同族）findNearestEnemyBuilding:L5773', '（同族）findNearestEnemySN:L5889'],
     '最近敌方建筑查找（BlockDR+1 → 像素 → 距离平方 → 取最小）在 5 个函数里各写一遍',
     '合并为 <span class="mono">findNearestEnemyBuildingOf(maskTypes, dr, ur, range)</span>，'
     '5 个旧函数退化为 3 行包装',
     '低'),
]
w('<div class="card"><table><tr><th class="num">重复长度</th><th>出现位置</th><th>这段在干什么</th>'
  '<th>建议</th><th>风险</th></tr>')
for ln, locs, what, how, risk in DUPS:
    pills = {'低': 'p-green', '低-中': 'p-amber', '中': 'p-amber'}[risk]
    w('<tr><td class="num"><b>%d 行</b></td><td class="mono tag">%s</td><td>%s</td><td>%s</td>'
      '<td><span class="pill %s">%s</span></td></tr>'
      % (ln, '<br>'.join(locs), what, how, pills, risk))
w('</table><div class="note g"><b>合计可回收约 %d 行</b>，但真正的价值不是行数 —— 是'
  '<b>消除"同一语义多处实现"这个已知 bug 源</b>。'
  '本项目的铁律 26 就是从这个坑里总结出来的（护驾 3 处、感化武器厂 3 处，都曾因改漏一处而表现为"改了像没改"）。'
  '这 6 处目前<b>恰好都还一致</b>，但没有任何机制保证它们继续一致。</div></div>'
  % sum(d[0] * (len(d[1]) - 1) for d in DUPS))

# ---------------- 5. 调用点 ----------------
w('<h2>5 · 发令点分布（优化的真正风险面）</h2>')
w('<div class="note r">重构之所以危险，是因为<b>改变"发令的帧序"就会改变行为</b>。'
  '下表是引擎调用（HumanAction / HumanMove / HumanBuild）在代码里的静态出现次数：'
  '<b>共 %d 处</b>。任何一次"合并两个分支""调整 if 顺序"都可能改动其中某处的执行时机。'
  '<br>⇒ 所以重构必须配 <b>行为对拍</b>：同 8 局跑重构前后，比对发令序列与关键帧。'
  '（本项目已有 <span class="mono">thrash_lint.py</span> / <span class="mono">tower_lock_report.py</span> 的发令计数口径可直接复用）</div>'
  % sum(1 for s in L if any(re.search(r'\b' + c + r'\s*\(', s.split('//')[0]) for c in CALLS[:3])))
w('<div class="card"><table><tr><th>函数</th><th class="num">行数</th><th class="num">发令点</th>'
  '<th class="num">HumanAction</th><th class="num">HumanMove</th><th class="num">HumanBuild</th>'
  '<th class="num">DebugText</th><th class="num">每百行发令</th></tr>')
for tot, n, ln, cnt in callrows:
    w('<tr><td class="mono">%s</td><td class="num">%d</td><td class="num"><b>%d</b></td>'
      '<td class="num">%d</td><td class="num">%d</td><td class="num">%d</td><td class="num tag">%d</td>'
      '<td class="num">%.1f</td></tr>'
      % (n, ln, tot, cnt['HumanAction'], cnt['HumanMove'], cnt['HumanBuild'], cnt['DebugText'],
         100.0 * tot / ln))
w('</table><div class="note">诊断打印（<span class="mono">DebugText</span>）全文件 86 处，'
  '本身不改变行为，但<b>会淹没日志</b>（实测 ait 里大量行是打印）。'
  '建议统一收进 <span class="mono">#if ENABLE_DIAG</span>，或收敛到 <span class="mono">DBGF(...)</span> 宏，'
  '这样"跑正式局"与"跑诊断局"能用同一个 exe 的两个开关区分。</div></div>')

# ---------------- 6. 优化清单 ----------------
w('<h2>6 · 优化候选清单（按 ROI 排序）</h2>')
w('<div class="note b">排序原则：<b>①纯搬移先于改逻辑 ②高嵌套先于高行数 ③同一语义多处实现优先收口</b>。'
  '每一行都是"可以立刻做、且不改变行为"的重构。</div>')

CANDS = [
    ('O1', 'assignIdleFarmers 里的祭司探路状态机', 'L2338~L2744（约 400 行，含单个 282 行巨段）',
     '抽成 <span class="mono">manageScout()</span>，纯搬移。<br>'
     '附带把 <span class="mono">scoutPhase / scoutWalkTimer / scoutReturnTry / scoutIssue*</span> 这些成员变量归属到一个地方。',
     'assignIdleFarmers 446 → 约 50 行；<b>探路可独立调试</b>（现在想看探路必须先跑完整个派工逻辑）',
     '低', '纯搬移，唯一风险是漏搬一个成员变量 → 编译期即可发现'),
    ('O2', 'manageCounterAttack 开篇的可走性网格预建', 'L4422~L4576（155 行）',
     '抽成 <span class="mono">buildPassabilityGrid()</span>，把 forestGrid 变成返回值或成员。',
     '主函数 −155 行；网格构建可单独测',
     '低', '注意 grid 生命周期：现在是函数局部栈对象，抽出后要保证仍在同一帧内使用'),
    ('O3', '<b>manageCounterAttack 的"远程兵打-拉双状态机相位优先段"</b>',
     'L4837~L5125（<b>289 行</b>，本文件最大的单个功能段）+ L5187~L5310（124 行）',
     '这两块合计 413 行 = 主函数的 34%，且是"相位机"（打/拉/推进/记账），职责与"反攻决策"正交。'
     '抽成 <span class="mono">manageRangedKite()</span> / <span class="mono">manageMarchPhases()</span>。',
     '主函数 −413 行（1202 → 约 620 行）',
     '中', '<b>状态机搬迁最怕隐式耦合</b>：这两个相位机与前文的 <span class="mono">forestGrid</span>、'
     '<span class="mono">marchCmdFrame</span> 等成员有读写交叉，抽函数时必须显式传参，不能靠作用域'),
    ('O4', '5 个"最近敌方建筑/单位"查找', 'L5769 / L5786 / L5889 / L5906 / L5927',
     '合并为带类型掩码的通用查找 + 5 个 3 行包装。',
     '−40 行，<b>消除"改一处漏一处"</b>',
     '低', '各函数的过滤条件略有差异（排除投石车 / 排除石头），必须逐个核对后再合并'),
    ('O5', '3 处 march 落地块 + 2 处探路绕行块 + 2 处路径危险检测', '见 §4 表',
     '抽 3 个工具函数（moveClamped / scoutMoveAway / blockedAhead）。',
     '−60 行，且记账逻辑收口',
     '低', '纯搬移'),
    ('O6', 'managePriest 拆分', '740 行 / 40 段 / 11 层嵌套',
     '按已有的<span class="mono">// ====</span>分隔拆 5 个子函数：<br>'
     '<span class="mono">priestConvert / priestFlee / priestHeal / priestReturnAnchor / priestScoutSkip</span>。'
     '<b>分 5 次提交，每次只搬一段</b>。',
     '主函数 → 约 80 行；11 层嵌套消失（每段独立后最多 4~5 层）',
     '中', '<b>最大风险点</b>：块尾无条件 <span class="mono">return</span> 的语义、'
     '以及"前一段设置的标志位被后一段读取"的隐式耦合（如 <span class="mono">mustFlee</span> 提前计算供迟滞锁用）。'
     '必须先画出"段间数据流"再动手'),
    ('O7', 'manageBuildings 拆分', '794 行 / 55 段 / 9 层',
     '按阶段边界拆：瞪羚仓库段 / 第一波段 / 第二波段 / 反攻段 / 兜底段。',
     '主函数 → 约 150 行',
     '中', '全是 <span class="mono">builtThisFrame</span> 争抢逻辑（"市场抢在第二仓库前"的历史 bug），'
     '拆开后<b>争抢顺序必须原样保留</b>，一旦顺序变了就会重现旧 bug'),
    ('O8', '注释瘦身', '1733 行注释（26%）；宏头部 254/380 行是注释',
     '把"★ 2026-09-xx 改了什么"这类<b>历史沿革</b>移到 <span class="mono">detail_*.md</span>，'
     '代码里只留"当前语义 + 为什么是这个值 + 铁律编号"。',
     '预计 −600~900 行',
     '低', '<b>先归档再删</b>。这些注释是十几轮实测的考古层，删掉容易，重建不可能'),
    ('O9', '诊断打印收口', '86 处 DebugText',
     '统一为 <span class="mono">#if ENABLE_DIAG</span> 包裹或 <span class="mono">DBG()</span> 宏。',
     '正式局日志干净；诊断局一键开',
     '低', '无（但别改动打印内容，历史日志要靠它做纵向对比）'),
]
w('<div class="card"><table><tr><th>#</th><th>目标</th><th>位置</th><th>动作</th><th>预期收益</th>'
  '<th>风险</th><th>风险说明</th></tr>')
for cid, tgt, loc, act, gain, risk, why in CANDS:
    pills = {'低': 'p-green', '低-中': 'p-amber', '中': 'p-amber'}[risk]
    w('<tr><td><b>%s</b></td><td><b>%s</b></td><td class="mono tag">%s</td><td>%s</td><td>%s</td>'
      '<td><span class="pill %s">%s</span></td><td class="tag">%s</td></tr>'
      % (cid, tgt, loc, act, gain, pills, risk, why))
w('</table></div>')

w('<h3>建议的执行顺序</h3>')
w('<div class="card"><ol>'
  '<li><b>先建对拍基线</b>（1 批 8 局，用当前 exe）。重构不改变行为，所以要能证明"没变"。'
  '对拍指标：发令数 / 出手数、探路阶段推进帧、农场数与落点、祭司死亡帧、最终帧数。</li>'
  '<li><b>O4 + O5</b>（工具函数收口，纯搬移，−100 行）→ 编译 + 对拍。</li>'
  '<li><b>O2 + O1</b>（两个"独立职责"大块搬出去，−555 行）→ 编译 + 对拍。</li>'
  '<li><b>O3</b>（413 行的相位机，主函数 −34%）→ 编译 + 对拍。</li>'
  '<li><b>O8</b>（注释归档，−600 行以上）→ 只需编译。</li>'
  '<li><b>O6 / O7</b>（两个最难的主函数）—— 放最后，而且<b>每次只搬一段</b>，每段都对拍。</li>'
  '</ol><div class="note r"><b>贯穿全程的一条红线：</b>重构期间<b>不要同时改行为</b>。'
  '历史上最贵的 bug（护驾三处重复、感化武器厂三处重复）都发生在"顺手一起改"的时候 —— '
  '一旦对拍不一致，你无法判断是重构搬错了还是新逻辑错了。</div></div>')

w('<h2>7 · 复现</h2>')
w('<pre>cd /c/new-aoe3.0.7g\n'
  'python code_metrics.py            # 全量（函数/段/嵌套/重复/死码）\n'
  'python code_metrics.py --fn       # 只看函数长度\n'
  'python code_metrics.py --seg      # 只看功能段\n'
  'python code_metrics.py --nest     # 只看嵌套深度\n'
  'DUPMIN=6 python code_metrics.py --dup   # 重复块（可调阈值）\n'
  'python code_metrics.py --macro    # 宏使用情况\n'
  'python code_metrics_html.py       # 本文件</pre>')
w('</div>')

html = '\n'.join(A)
open('aoe3_codemetrics_20260915.html', 'w', encoding='utf-8').write(html)
print('written', len(html), 'bytes')
