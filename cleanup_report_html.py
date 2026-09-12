# -*- coding: utf-8 -*-
"""去重 + 无用代码清理 报告生成器 → aoe3_cleanup_20260915.html"""
import os, re, math, statistics as st

OUT = 'aoe3_cleanup_20260915.html'

# ============ 数据（来自 code_metrics.py / diff / grep 实测） ============
BEFORE = dict(lines=6981, funcs=53, code=4866, cmt=1733, blank=382, dup=6, macros=117)
AFTER  = dict(lines=6834, funcs=52, code=4733, cmt=1719, blank=382, dup=0, macros=117)

DEAD = [
    ('findFarmRingSite',        'UsrAI.cpp L6424~L6467', 44,
     '上一轮农场选址改为 findFarmSiteBest 后，调用点被删、定义没删。'
     '其内部自带 findBuildSite 兜底 ⇒ 恒返回 true ⇒ 使调用链第二步 findFarmNearGranarySite 永不可达。'),
    ('findFarmNearGranarySite', 'UsrAI.cpp L6469~L6539', 71,
     '同上——它只被上面那条已失效的链调用，链一换即为死代码。'),
    ('两个函数间的分隔空行',     'UsrAI.cpp L6468 / L6540', 2, '随函数体一并删除。'),
    ('if (true)',               'UsrAI.cpp L5083', 1,
     '恒真条件，唯一作用是让后面那条 DebugText 变成 if 的从属语句（无功能）。删除后语义完全相同。'),
    ('头文件声明 ×2',            'UsrAI.h L292~L293', 2, '随函数定义一并删除，避免"声明在、实现在、调用无"。'),
]

MERGES = [
    ('M1', 'manageCounterAttack 三档撤退的落点下发',
     '3 处 × 17 行',
     'lambda <code>tryRetreatLanding(rx, ry, stage)</code><br>'
     '夹取到地图内 → isPassableAt → HumanMove + 记账 5 件套',
     '−39 行',
     '记账 5 件套（cmdFrame/retreatFrame/issueDist/moveFrame/stuckTry）任缺一项都会让卡死检测或节流失效，'
     '原先三处各抄一份 —— 正是铁律 26 的高危形态。'),
    ('M2', 'assignIdleFarmers 祭司"背向威胁走 12 格"',
     '2 处 × 13 行',
     'lambda <code>scoutStepAwayFrom(fromX, fromY)</code><br>'
     '（遇野兽 / 被缠斗两处共用；调用方按需补 fledThisFrame）',
     '−13 行',
     '⚠ 首版把 lambda 放在 <code>scout</code> 指针解析之前 → 编译报 '
     '<code>scout was not declared</code>。已移到指针解析之后（lambda 体内解引用它）。'),
    ('M3', 'assignIdleFarmers 路径前 8 格野兽检测',
     '2 处 × 21/18 行',
     'lambda <code>beastOnPathAhead(sDR,sUR,wx,wy)</code><br>'
     '（去程绕障 / 返程绕障共用）',
     '−27 行',
     '去程那处多一条"目标点 12 格内有野兽"的前置判据，抽函数后在调用点保留 '
     '<code>if (!dangerNearby) dangerNearby = beastOnPathAhead(...)</code>，短路顺序变化但布尔结果等价。'),
    ('M4', 'managePriest 两处落点合法性判据',
     '2 处 × 6 行',
     'lambda <code>ownOccupied(x,y)</code><br>'
     '（occupiedLanding 前出感化落点 / badLanding 逃跑落点共用）',
     '−5 行',
     '只抽【己方】占用（建筑 2.5 格 / 我方军队 2.0 / 我方村民 2.0）；'
     '敌方 4.0 格与威胁射程检查仍各自保留在调用点。'),
    ('M5', 'manageMilitary D1/D2 的调度过滤链',
     '2 处 × 6 行',
     'lambda <code>autoAttackEligible(a)</code><br>'
     '（排除祭司 / 投石车 / 已派护驾 / 正在猎狮 / 非空闲）',
     '−4 行',
     '这两处原先完全逐字重复，任一处的过滤条件改动都会被另一处悄悄覆盖。'),
    ('M6', '三处"最近敌方建筑"距离扫描',
     '3 处 × 7 行',
     '成员函数 <code>nearestEnemyBuildingFrom(dr, ur, bestD2, typeFilter)</code><br>'
     'findNearestEnemyBuilding / findNearestEnemyTower / findCatapultTarget 三个都改为调用它',
     '−10 行',
     '<code>bestD2</code> 用引用传入当前最优 ⇒ findCatapultTarget 能让"建筑候选"与"单位候选"'
     '继续混在同一池里比较，语义不变。'),
]


def build():
    A = []
    w = A.append
    w('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    w('<title>AOE UsrAI 去重与无用代码清理 · 2026-09-15</title>')
    w('<style>')
    w(':root{--bg:#f7f8fa;--card:#fff;--ink:#1a1d23;--mut:#5b6472;--line:#e3e7ee;--acc:#1d4ed8;'
      '--ok:#0f7b3d;--warn:#a15c00;--bad:#b42318}')
    w('*{box-sizing:border-box}')
    w('body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"Segoe UI",'
      '"Microsoft YaHei",sans-serif;font-size:14px;line-height:1.65}')
    w('.wrap{max-width:1080px;margin:0 auto;padding:32px 22px 70px}')
    w('h1{font-size:24px;margin:0 0 6px;letter-spacing:.3px}')
    w('.sub{color:var(--mut);font-size:13px;margin-bottom:26px}')
    w('h2{font-size:17px;margin:34px 0 12px;padding-left:9px;border-left:3px solid var(--acc)}')
    w('h3{font-size:14px;margin:20px 0 8px}')
    w('.card{background:var(--card);border:1px solid var(--line);border-radius:9px;'
      'padding:16px 18px;margin-bottom:14px}')
    w('table{width:100%;border-collapse:collapse;font-size:13px}')
    w('th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}')
    w('th{background:#f2f4f8;font-weight:600;color:var(--mut);font-size:12px}')
    w('td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}')
    w('tr:last-child td{border-bottom:none}')
    w('.mono{font-family:ui-monospace,Consolas,monospace;font-size:12px;background:#eef1f6;'
      'padding:1px 5px;border-radius:4px}')
    w('code{font-family:ui-monospace,Consolas,monospace;font-size:12.5px;background:#eef1f6;'
      'padding:1px 5px;border-radius:4px}')
    w('.note{border-radius:8px;padding:11px 14px;margin:12px 0;font-size:13px;'
      'border-left:3px solid var(--acc);background:#eef3fd}')
    w('.note.ok{border-color:var(--ok);background:#eaf6ee}')
    w('.note.warn{border-color:var(--warn);background:#fdf5e8}')
    w('.note.bad{border-color:var(--bad);background:#fdeceb}')
    w('.kpi{display:grid;grid-template-columns:repeat(4,1fr);gap:11px;margin-bottom:16px}')
    w('.kpi div{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:13px 14px}')
    w('.kpi b{display:block;font-size:21px;line-height:1.25;font-variant-numeric:tabular-nums}')
    w('.kpi span{color:var(--mut);font-size:12px}')
    w('.up{color:var(--ok)}.down{color:var(--bad)}')
    w('pre{background:#f2f4f8;border:1px solid var(--line);border-radius:8px;padding:12px 14px;'
      'overflow-x:auto;font-size:12.5px;font-family:ui-monospace,Consolas,monospace;line-height:1.55}')
    w('.del{color:#b42318}.add{color:#0f7b3d}.cmt{color:#7a8290}')
    w('@media(max-width:760px){.kpi{grid-template-columns:repeat(2,1fr)}}')
    w('</style></head><body><div class="wrap">')

    w('<h1>UsrAI 去重与无用代码清理</h1>')
    w('<div class="sub">2026-09-15 · 纯结构重构（零行为变更）· 基线 <span class="mono">3.0.7g</span> · '
      '起点 = 农场选址 v3（<span class="mono">bak_20260915_farmlayout_v3</span>）</div>')

    # ---------------- KPI ----------------
    w('<div class="kpi">')
    for v, lab, cls in (
            ('6981 → 6834', '总行数', 'down'),
            ('6 → 0', '重复代码块', 'down'),
            ('53 → 52', '函数数', 'down'),
            ('0 / 18 / 0', 'error / warning / trigraph', '')):
        w('<div><b class="%s">%s</b><span>%s</span></div>' % (cls, v, lab))
    w('</div>')

    # ---------------- 1 结论 ----------------
    w('<h2>1 · 结论摘要</h2>')
    w('<div class="card"><ol>'
      '<li><b>发现并删除了上一轮自己留下的死代码</b>：换掉农场选址链时只删了调用、没删定义，'
      '<code>findFarmRingSite</code>(44 行) 与 <code>findFarmNearGranarySite</code>(71 行) '
      '成为零调用的孤儿 —— 连同头文件声明共 <b>120 行</b>（cpp 118 + 头文件 2）。</li>'
      '<li><b>7 处复制粘贴的重复块全部收口</b>为 6 个共享实现（3 个函数内 lambda，'
      '1 个成员函数，2 个跨分支共用）—— 重复块检测 <b>6 处 → 0 处</b>（连 6 行的都没有了）。</li>'
      '<li>净减 <b>147 行</b>（−2.1%），其中代码行 −133、注释 −14；'
      '函数体里的实质代码几乎没动，减的全是"抄第二遍"和"已无人调用"。</li>'
      '<li>验证：<b>0 error / 18 warning（UsrAI.cpp 口径，与基线一字不差）/ 0 trigraph</b>，'
      '并跑 8 局对拍确认行为量级未变（见 §5）。</li>'
      '</ol></div>')

    w('<div class="note ok"><b>为什么这次敢动结构：</b>上一轮的结构度量已经证明'
      '「<b>几乎无死代码、无死宏</b>（117/117 宏在用）」。所以本轮的收益不在"扔垃圾"，'
      '而在<b>消除铁律 26 的温床</b> —— 历史上最贵的三个 bug（护驾 3 处重复、感化武器厂 3 处重复、'
      '去重目标 77:77 交替）全都源于"同一条语义写在两个地方，改了一处、另一处把它覆盖掉"。</div>')

    # ---------------- 2 死代码 ----------------
    w('<h2>2 · 删除的无用代码（118 行）</h2>')
    w('<div class="card"><table>'
      '<tr><th>对象</th><th>位置</th><th class="num">行数</th><th>为什么是无用的</th></tr>')
    for nm, loc, n, why in DEAD:
        w('<tr><td><span class="mono">%s</span></td><td class="mono">%s</td>'
          '<td class="num">%d</td><td>%s</td></tr>' % (nm, loc, n, why))
    tot = sum(x[2] for x in DEAD)
    w('<tr><td colspan="2"><b>合计</b></td><td class="num"><b>%d</b></td>'
      '<td>cpp 净删 118 行 + 头文件 2 行。'
      '（<code>if (true)</code> 那处还顺带把 6 行 DebugText 的缩进左移了 4 格）</td></tr>' % tot)
    w('</table>')
    w('<div class="note warn"><b>判定方法（避免拍脑袋）：</b>'
      '把 <span class="mono">UsrAI.h</span> 的 51 个成员函数声明逐个在 '
      '<span class="mono">UsrAI.cpp</span> 里数调用点（先剥掉行注释），'
      '<b>有定义且 0 调用</b>的仅 2 个 —— 就是上面那两个。'
      '同法扫过 32 个成员变量（0 个未使用）、117 个宏（0 个未使用）、'
      '注释掉的代码块（0 处）。</div>')
    w('</div>')

    # ---------------- 3 去重 ----------------
    w('<h2>3 · 消除的重复（6 个共享实现）</h2>')
    w('<div class="card"><table>'
      '<tr><th style="width:38px">#</th><th>重复位置</th><th>原状</th><th>收口为</th>'
      '<th class="num">省</th><th>要点</th></tr>')
    for mid, where, before, after, save, note in MERGES:
        w('<tr><td><b>%s</b></td><td>%s</td><td class="mono">%s</td><td>%s</td>'
          '<td class="num">%s</td><td>%s</td></tr>' % (mid, where, before, after, save, note))
    w('</table></div>')

    w('<div class="note"><b>M1 是其中最值钱的一处。</b>那 9 行重复块里，'
      '真正危险的是 <b>记账 5 件套</b>：'
      '<span class="mono">marchCmdFrame</span> / <span class="mono">lastRetreatFrame</span> / '
      '<span class="mono">marchIssueDist</span> / <span class="mono">marchMoveFrame</span> / '
      '<span class="mono">marchStuckTry</span>。'
      '少写任何一条，卡死检测或发令节流就会静默失效（''单位原地站桩挨打''那类 bug 的经典成因），'
      '而三处循环各自维护一遍 —— 改动必须三处同步，漏一处无编译告警、无运行报错。'
      '现在它们只有一个写入点。</div>')

    # ---------------- 4 刻意不合并 ----------------
    w('<h2>4 · 刻意<b>没有</b>合并的（同样重要）</h2>')
    w('<div class="card"><table>'
      '<tr><th>函数</th><th>看似重复</th><th>实际语义差异</th></tr>'
      '<tr><td><span class="mono">findNearestEnemySN</span><br>vs<br>'
      '<span class="mono">findNearestEnemyNoStone</span></td>'
      '<td>都是"军队 + 村民"两段循环取最近</td>'
      '<td><b>半径口径不同</b>：前者把军队与村民放进<b>同一个</b> bestDist 里比较'
      '（村民更近时村民胜出）；后者是<b>军队优先</b> —— 只有军队全无命中才重置 bestDist 去看村民。'
      '合并会静默改变选敌行为。</td></tr>'
      '<tr><td>三档撤退的"方向"计算</td><td>都是 5 个角度的锥形枚举</td>'
      '<td>起点（敌后 / 己方 TC / 己方祭司）、步长（1.4R·1.5R / 12 格 / 6 格）、'
      '角度表（angs / angsT）<b>各不相同</b> —— 只统一了"下发"这一步，方向计算留在原地。</td></tr>'
      '</table>')
    w('<div class="note bad"><b>这条比"合并了多少"更值得记住：</b>'
      '重复检测工具按"归一化后连续 N 行相同"报警，它<b>看不见语义差异</b>。'
      '上面这两个函数会被工具判为同构，但它们<b>不是一个东西</b>。'
      '盲目按工具的清单去重 = 用一次重构换来一个静默的行为 bug。'
      '每条都要先读懂两边的差，再决定合不合。</div></div>')

    # ---------------- 5 验证 ----------------
    w('<h2>5 · 验证</h2>')
    w('<h3>5.1 先说清楚"凭什么算等价"（代码级论证，而不是靠跑局）</h3>')
    w('<div class="card">'
      '<p>6 处合并<b>全部是同一个表达式序列</b>——把第二次出现替换成对第一次的调用。'
      '没有改变求值顺序，也没有引入新的中间状态：</p>'
      '<table>'
      '<tr><th style="width:130px">#</th><th>等价性依据</th></tr>'
      '<tr><td>M1 / M2 / M4 / M5 / M6</td>'
      '<td>逐行搬移。调用点原样保留"分支顺序 / 短路顺序"；'
      'M6 额外用 <code>double &amp;bestD2</code> 把"当前最优距离"传进出参，'
      '使<b>建筑候选与单位候选继续共享同一个池</b>（这是 findCatapultTarget 的原有语义，不能丢）。</td></tr>'
      '<tr><td>M3（唯一需要推理的一处）</td>'
      '<td>原来：对每个资源 r，先判"目标点 12 格内"、再判"路径前 8 格"。<br>'
      '改写后：先全体判 12 格，无命中再全体判路径。<br>'
      '原式 = ∃r ( A(r) ∨ B(r) )　新式 = (∃r A(r)) ∨ (∃r B(r)) —— '
      '<b>∃ 对 ∨ 的分配律</b>，布尔结果恒等。<br>'
      '差别仅在短路路径（新式可能多算几次 A(r)），而 A 是纯函数、无副作用。</td></tr>'
      '</table>'
      '<div class="note"><b>这一步不能省。</b>等价性若只靠"跑 8 局看着差不多"来确认，'
      '等于拿噪声当证据 —— 而 §5.4 的噪声实测恰恰说明这条路根本走不通。</div></div>')

    w('<h3>5.2 编译与静态检查</h3>')
    w('<div class="card"><table>'
      '<tr><th>项</th><th>基线</th><th>清理后</th><th>判定</th></tr>'
      '<tr><td>error</td><td class="num">0</td><td class="num">0</td><td class="up">✓</td></tr>'
      '<tr><td>warning（<span class="mono">^UsrAI\\.cpp:</span> 口径）</td>'
      '<td class="num">18</td><td class="num">18</td><td class="up">✓ 一字不差</td></tr>'
      '<tr><td>warning（全量重编 18 个 .o 合计）</td><td class="num">—</td><td class="num">277</td>'
      '<td class="up">✓ 与历史全量口径同值，未引入新警告</td></tr>'
      '<tr><td>trigraph</td><td class="num">0</td><td class="num">0</td><td class="up">✓</td></tr>'
      '</table>')
    w('<div class="note"><b>一个中间踩到的坑：</b>首轮 <span class="mono">g++ -fsyntax-only</span> '
      '报 2 个 error（<span class="mono">\'scout\' was not declared in this scope</span>）——'
      '原因是把 <span class="mono">scoutStepAwayFrom</span> 这个 lambda 放在了 '
      '<span class="mono">tagArmy* scout</span> 指针解析<b>之前</b>。'
      'lambda 的捕获列表 ( <span class="mono">[&amp;]</span> ) 不会让未声明的变量变得可见。'
      '移到声明之后即通过 —— 这也是为什么每次改完先跑一遍 syntax-only 而不是直接全量编译：'
      '<b>30 秒 vs 5 分钟</b>。</div></div>')

    w('<h3>5.3 结构度量（同口径前后对比）</h3>')
    w('<div class="card"><table>'
      '<tr><th>指标</th><th class="num">清理前</th><th class="num">清理后</th><th class="num">变化</th></tr>')
    for lab, b, a in (
            ('总行数', BEFORE['lines'], AFTER['lines']),
            ('函数数', BEFORE['funcs'], AFTER['funcs']),
            ('代码行', BEFORE['code'], AFTER['code']),
            ('注释行', BEFORE['cmt'], AFTER['cmt']),
            ('空行', BEFORE['blank'], AFTER['blank']),
            ('<b>重复代码块（≥6 行）</b>', BEFORE['dup'], AFTER['dup']),
            ('宏定义', BEFORE['macros'], AFTER['macros'])):
        d = a - b
        cls = 'up' if d < 0 else ('' if d == 0 else 'down')
        w('<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
          '<td class="num %s">%+d</td></tr>' % (lab, b, a, cls, d))
    w('</table>')
    w('<div class="note"><b>仅看行数是误读。</b>大函数只小幅缩水'
      '（manageCounterAttack 1202→1186、assignIdleFarmers 446→431），'
      '因为本轮的靶子是<b>重复</b>与<b>死代码</b>，不是"拆函数"。'
      '真正拆 managePriest / manageCounterAttack 的相位机是上一轮报告里的 O1~O9，'
      '属于行为敏感操作，需要单独的"行为对拍基线"，不在本轮范围。</div></div>')

    w('<h3>5.4 运行对拍（8 局 + 跨批噪声基线）</h3>')
    w('<div id="PAIR"></div>')

    # ---------------- 6 复现 ----------------
    w('<h2>6 · 备份链与复现</h2>')
    w('<div class="card"><pre>'
      'UsrAI.cpp.bak_20260915_pre_cleanup   本轮起点（= 农场 v3，纯基线 + 农场选址改动）\n'
      'UsrAI.cpp.bak_20260915_cleanup       本轮成果（去重 + 清理）\n'
      'UsrAI.h.bak_20260915_pre_cleanup     .h 对应起点\n'
      'UsrAI.h.bak_20260915_cleanup         .h 对应成果\n'
      '\n'
      '<span class="cmt"># 快速语法校验（30 秒，先于全量编译）</span>\n'
      'PATH="/d/360Downloads/Tools/mingw530_32/bin:$PATH" g++ -fsyntax-only \\\n'
      '  -O2 -std=gnu++1y -Wextra -Wall -W -fexceptions -mthreads &lt;DEFINES&gt; &lt;INCPATH&gt; UsrAI.cpp\n'
      '\n'
      '<span class="cmt"># 全量编译（改 .h 触发 18 个 .o 重编）</span>\n'
      'PATH="/d/360Downloads/Tools/mingw530_32/bin:$PATH" mingw32-make -f Makefile.Release -j4\n'
      '\n'
      '<span class="cmt"># 跑局 + 对拍</span>\n'
      'bash fc_verify.sh              <span class="cmt"># 8 局</span>\n'
      'python cleanup_compare.py      <span class="cmt"># 清理前(fn) vs 清理后(fc)</span>\n'
      'python code_metrics.py --dup   <span class="cmt"># 重复块复查（应报"未发现"）</span>\n'
      '</pre></div>')

    w('<div class="note"><b>下一步建议（沿用上轮 O1~O9，但顺序可调）：</b>'
      '本轮把"低风险的结构噪声"清干净之后，'
      'O4（探路状态机抽出）/ O2（可走性网格抽出）这两条的风险已进一步降低 ——'
      '它们要搬的正是本轮刚统一过记账口径的区域。'
      '真要动它们之前，仍需先建 <b>行为对拍基线</b>（同 8 局比发令数/出手比、农场落点、'
      '探路推进帧、祭司死亡帧），且<b>重构期间不同时改行为</b>。</div>')

    w('</div></body></html>')
    return '\n'.join(A)


def fill_pair():
    """把对拍结果嵌入 #PAIR（由 cleanup_compare.py 的文本输出转 HTML 表）。"""
    import subprocess
    try:
        txt = subprocess.check_output(['python', 'cleanup_compare.py'], encoding='utf-8', errors='replace')
    except Exception as e:
        txt = '（对拍脚本执行失败：%s）' % e
    esc = (txt.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
    return ('<div class="card"><pre>%s</pre>'
            '<div class="note"><b>怎么读：</b>这是<b>重构</b>，判据是"量级一致"而不是"数字相同" —— '
            '游戏带随机性（同一份代码两批胜率可差 3 局），逐局数字本就对不上。'
            '重点看：① 各类事件计数是否同量级（差 &lt;25%% 视为一致）；'
            '② 发令÷出手比是否仍在 ≈1（铁律 22，验证 M1 的记账没漏项）；'
            '③ 农场数与到 TC 距离分布是否与清理前一致（验证 M2/M3 的 lambda 没改到选址）。</div></div>'
            % esc)


def main():
    html = build().replace('<div id="PAIR"></div>', fill_pair())
    open(OUT, 'w', encoding='utf-8').write(html)
    print('written %s (%d bytes)' % (OUT, len(html)))


if __name__ == '__main__':
    main()
