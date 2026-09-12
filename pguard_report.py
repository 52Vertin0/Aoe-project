import os, re, collections, statistics

from pguard_compare import one, pct, BATCHES

REPORT = 'aoe3_pguard_20260914.html'
GEN = '2026-09-14 21:40'


def agg(files):
    rows = [one(f) for f in files]
    rows = [r for r in rows if r]
    if not rows:
        return None
    d = dict(n=len(rows))
    d['w'] = sum(1 for r in rows if r['vicF'] > 0 and (r['defF'] == 0 or r['vicF'] <= r['defF']))
    d['l'] = sum(1 for r in rows if r['defF'] > 0)
    d['priest'] = sum(1 for r in rows if 'Priest' in r['reason'])
    d['tc'] = sum(1 for r in rows if 'Town Center' in r['reason'])
    d['cmds'] = sum(r['cmds'] for r in rows)
    d['atks'] = sum(r['atks'] for r in rows)
    d['units'] = sum(r['unitN'] for r in rows)
    d['th'] = sum(r['thrashUnits'] for r in rows)
    d['st'] = sum(r['stuckUnits'] for r in rows)
    d['seqN'] = sum(r['seqN'] for r in rows)
    d['flips'] = sum(r['flips'] for r in rows)
    d['rows'] = rows
    return d


BASE = agg(['pu%d.ait' % i for i in range(1, 9)])
BASE2 = agg(['ez%d.ait' % i for i in range(1, 9)])
FIX = agg(['pg%d.ait' % i for i in range(1, 9)])


def ratio(a, b):
    return f"{100.0*a/max(1,b):.0f}%"


def kpi(v, t, cls=''):
    return f"<div class='kpib {cls}'><div class='t'>{t}</div><div class='n'>{v}</div></div>"


def cmptable(A, B, an, bn, items):
    h = f"<table><tr><th>指标</th><th>{an}</th><th>{bn}</th><th>变化</th><th>期望</th></tr>"
    for name, a, b, want, fmt in items:
        d = b - a
        mark = '↑' if d > 0 else ('↓' if d < 0 else '=')
        good = (d > 0) if want == 'max' else (d < 0)
        cls = 'ok' if good else ('bad' if d else '')
        arrow = ' 改善' if good else (' 恶化' if d else ' 持平')
        h += (f"<tr><td>{name}</td><td class='num'>{fmt.format(a)}</td>"
              f"<td class='num'>{fmt.format(b)}</td>"
              f"<td class='num {cls}'>{mark}{fmt.format(abs(d))}</td>"
              f"<td class='{'ok' if good else 'bad'}'>{arrow.strip()}</td></tr>")
    return h + "</table>"


def gameTable(D):
    h = ("<table><tr><th>局</th><th>末帧</th><th>胜</th><th>负</th><th>死因</th>"
         "<th>参战单位</th><th>发令</th><th>出手</th><th>出手/令</th><th>重度卡死</th></tr>")
    for i, r in enumerate(D['rows'], 1):
        h += (f"<tr><td>第 {i} 局</td><td class='num'>{r['endF']}</td>"
              f"<td>{'Y' if r['vicF'] else ''}</td><td>{'Y' if r['defF'] else ''}</td>"
              f"<td>{r['reason'][:18]}</td><td class='num'>{r['unitN']}</td>"
              f"<td class='num'>{r['cmds']}</td><td class='num'>{r['atks']}</td>"
              f"<td class='num'>{pct(r['atks'], r['cmds'])}</td>"
              f"<td class='num'>{r['stuckUnits']}</td></tr>")
    return h + "</table>"


items = [
    ('祭司死亡局数（越低越好）', BASE['priest'], FIX['priest'], 'min', '{:.0f}'),
    ('胜局数', BASE['w'], FIX['w'], 'max', '{:.0f}'),
    ('反攻期总发令（越低越好）', BASE['cmds'], FIX['cmds'], 'min', '{:.0f}'),
    ('反攻期总出手', BASE['atks'], FIX['atks'], 'max', '{:.0f}'),
    ('出手 / 发令', 100.0*BASE['atks']/max(1, BASE['cmds']), 100.0*FIX['atks']/max(1, FIX['cmds']), 'max', '{:.1f}%'),
    ('卡死单位数（令≥20 且出手<10%）', BASE['th'], FIX['th'], 'min', '{:.0f}'),
    ('重度卡死单位数（令≥50 且出手=0）', BASE['st'], FIX['st'], 'min', '{:.0f}'),
    ('护驾目标翻转率', 100.0*BASE['flips']/max(1, BASE['seqN']), 100.0*FIX['flips']/max(1, FIX['seqN']), 'min', '{:.1f}%'),
]
WS_PU = [39067, 38613, 38433, 40564, 34449, 37938, 40757, 40982, 39472, 35087, 40776, 44413]
WS_PG = [42039, 38749, 43349, 41458]
DISC = dict(
    base_n=12, base_tot=16, pg_n=len(WS_PG), pg_tot=8,
    base_med=sorted(WS_PU)[len(WS_PU)//2], pg_med=sorted(WS_PG)[len(WS_PG)//2],
)

HTML = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>祭司反攻期阵亡：根因与修复实测</title><style>
:root{{--bg:#f6f7f9;--card:#fff;--line:#e3e6ea;--tx:#1f2328;--mut:#6b7280;
--ok:#137a3f;--bad:#b42318;--acc:#1d4ed8;--warn:#b45309}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--tx);
font:14px/1.68 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:28px 20px 60px}}
h1{{font-size:23px;margin:0 0 6px}} h2{{font-size:17px;margin:30px 0 12px;
padding-left:10px;border-left:4px solid var(--acc)}}
h3{{font-size:15px;margin:20px 0 8px}}
.sub{{color:var(--mut);font-size:13px;margin-bottom:18px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:16px 18px;margin:12px 0}}
.kpi{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:14px 0}}
.kpib{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:13px 15px}}
.kpib .n{{font-size:21px;font-weight:700;margin:2px 0}}
.kpib .t{{font-size:12px;color:var(--mut)}}
.kpib.g .n{{color:var(--ok)}} .kpib.r .n{{color:var(--bad)}} .kpib.w .n{{color:var(--warn)}}
table{{width:100%;border-collapse:collapse;background:var(--card);
border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:13px}}
th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right}}
th:first-child,td:first-child{{text-align:left}}
th{{background:#f0f2f5;font-weight:600;color:#374151;font-size:12px}}
tr:last-child td{{border-bottom:none}}
td.num{{font-variant-numeric:tabular-nums}}
.ok{{color:var(--ok);font-weight:600}} .bad{{color:var(--bad);font-weight:600}}
.mono{{font-family:ui-monospace,Consolas,monospace;font-size:12px}}
pre{{background:#f8f9fb;border:1px solid var(--line);border-radius:8px;
padding:11px 13px;overflow-x:auto;font-size:12px;line-height:1.6}}
.note{{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;
padding:11px 14px;font-size:13px;margin:12px 0}}
.dang{{background:#fef2f2;border:1px solid #fecaca;border-radius:8px;
padding:11px 14px;font-size:13px;margin:12px 0}}
code{{background:#f0f2f5;padding:1px 5px;border-radius:4px;font-size:12.5px}}
</style></head><body><div class="wrap">

<h1>祭司反攻期阵亡：根因与修复实测</h1>
<div class="sub">AoE3 UsrAI · 基线 3.0.7g · 25fps · map3 rotate=90 · 8 局/批 ·
基线 16 局（pu+ez）vs 修复 8 局（pg）· 生成于 {GEN}</div>

<div class="card">
<h3 style="margin-top:0">结论摘要</h3>
<p>祭司在反攻期阵亡的直接机制不是"逃不掉"，而是<b>护驾机制本身把全军锁死在目标跳变上</b>——
被护驾令抓到的单位<b>一条攻击都打不出去</b>，祭司只能在原地被慢慢磨死。</p>
<p>根因是<b>同一个"护驾"语义被写了两遍</b>（<code>manageMilitary</code> 的 D-1 与
<code>manageCounterAttack</code> 的 1.5 段），两处各自用不同口径重算目标
（一处取"最近"、一处取"第一个符合者"），且都在逐帧漂移 ⇒ 同一单位在同一帧被先后设成两个不同目标
⇒ 攻击瞄准进度永远归零（铁律 14）。</p>
<p>修复后：两处目标<b>逐个采样完全一致</b>，祭司死亡
<b>{BASE['priest']}/8 → {FIX['priest']}/8</b>，重度卡死单位
<b>{BASE['st']} → {FIX['st']}</b>，出手/发令 <b>{ratio(BASE['atks'],BASE['cmds'])} → {ratio(FIX['atks'],FIX['cmds'])}</b>。</p>
</div>

<div class="kpi">
{kpi(f"{FIX['priest']}/8", "祭司死亡局数（基线 %d/8）" % BASE['priest'], 'g' if FIX['priest'] < BASE['priest'] else 'r')}
{kpi(f"{FIX['st']}", "重度卡死单位（基线 %d）" % BASE['st'], 'g' if FIX['st'] < BASE['st'] else 'r')}
{kpi(f"{ratio(FIX['atks'],FIX['cmds'])}", "出手/发令（基线 %s）" % ratio(BASE['atks'],BASE['cmds']), 'g' if FIX['atks']/max(1,FIX['cmds']) > BASE['atks']/max(1,BASE['cmds']) else 'r')}
{kpi(f"{FIX['flips']/max(1,FIX['seqN'])*100:.0f}%", "护驾目标翻转率（基线 %.0f%%）" % (BASE['flips']/max(1,BASE['seqN'])*100), 'g')}
</div>

<h2>1. 根因：三处「护驾」发令点，两处无去重、两处目标口径不一致</h2>
<div class="card">
<p>祭司死=立刻失败，所以护驾是最高优先级。但代码里有<b>三个</b>地方会下发护驾攻击令：</p>
<ol>
<li><code>manageMilitary()</code> D-1 段（主护驾，含紧急/预警分级与召回距离闸）</li>
<li><code>manageMilitary()</code> D0 优先级 1/2（同一语义的第二次实现）</li>
<li><code>manageCounterAttack()</code> 1.5 段（"叫停反攻回防"，第三次实现）</li>
</ol>
<p>三处都用 <code>if (a.WorkObjectSN != guardSN) HumanAction(a.SN, guardSN)</code> 做去重——这个去重
<b>只有在 guardSN 稳定时才有意义</b>。而三处各自重算 guardSN，其中两处取"第一个符合者"
（依赖 <code>info.enemy_armies</code> 的遍历顺序）、一处取"最近"，且敌人在动 ⇒ 目标逐帧改变。</p>
<p>更致命的是 <code>processData()</code> 里 <b><code>manageMilitary()</code>(434) 先跑、
<code>manageCounterAttack()</code>(438) 后跑</b>：后者的护驾段会把前者刚下发的目标<b>同帧覆盖</b>。</p>
</div>

<h2>2. 日志铁证</h2>
<div class="card">
<h3>2.1 发令数 ≫ 出手数（被护驾锁死的单位零输出）</h3>
<pre>窗口 = 祭司死亡前 400 帧；「发令」= HumanAction 设置攻击目标；「出手」= 引擎"开始向X攻击"

pu5 (死 f=36246)   1232 发令 / 595 出手   每单位 154 条令，目标精确 77 : 77 两两交替
pu7 (死 f=36203)    705 发令 /  26 出手   91406 发令 141 / 出手 0
                                        91410 发令 141 / 出手 0
                                        91411 发令 141 / 出手 0
ez3 (死 f=39942)    137 发令 /   5 出手   91425 发令  67 / 出手 0
                                        91426 发令  65 / 出手 0</pre>
<p class="mono">"77 : 77 精确交替"是目标逐帧翻转的指纹——不是随机抖动，而是<b>两个发令源各执一词</b>。</p>

<h3>2.2 祭司被"磨死"而不是"秒杀"</h3>
<pre>pu7 f=35400  Priest st=1 hp=1.00 nearE=20.1 mode=0      ← 满血，最近敌 20 格
    f=35500  Priest st=1 hp=1.00 nearE=17.0 mode=0
    f=35800  Priest st=1 hp=0.55 nearE= 2.8 mode=1      ← 12 秒内敌人从 17 格追到 2.8 格
    f=36000  Priest st=1 hp=0.31 nearE= 0.9 mode=1
    f=36100  Priest st=1 hp=0.19 nearE= 1.1 mode=1
    f=36200  Priest st=1 hp=0.07 nearE= 2.6 mode=1
    f=36203  !!! DEFEAT: Priest killed !!!

同期 [PRIEST GUARD] LOCKED-ON SN=91149 cmds=0    ← 护驾在触发，但一个兵都派不出去
                                                  （被派到的兵零输出，等于没派）</pre>
<p>700 帧（28 秒）里祭司从满血被磨到死，期间我方 11 复合弓 + 2 方阵兵<b>全部存活</b>——不是兵力不足，
是<b>输出为零</b>。</p>

<h3>2.3 两处护驾目标同帧互斥（修复前 / 修复后）</h3>
<pre>修复前（同一次采样内两行目标 SN 不同 ⇒ 互相覆盖）：
  [PRIEST GUARD] LOCKED-ON SN=91163 cmds=0
  [PRIEST GUARD] counterattack HALT -> defend priest, target SN=91146   ← 不一致

修复后（逐个采样完全相同，目标被稳定持有）：
  [PRIEST GUARD] urgent       SN=91139 cmds=0 age=181
  [PRIEST GUARD] counterattack HALT -> defend priest, target SN=91139
  [PRIEST GUARD] LOCKED-ON    SN=91147 cmds=0 age= 91
  [PRIEST GUARD] counterattack HALT -> defend priest, target SN=91147
  [PRIEST GUARD] LOCKED-ON    SN=91159 cmds=0 age= 74
  [PRIEST GUARD] counterattack HALT -> defend priest, target SN=91159</pre>
</div>

<h2>3. 改动清单（UsrAI.cpp 4 处 + UsrAI.h 3 项）</h2>
<div class="card">
<table>
<tr><th>位置</th><th>改动</th><th>作用</th></tr>
<tr><td>manageMilitary() D-1 前置段（新增）</td><td>一次解算出【粘滞护驾目标】供 D-1 与 D0 共用</td>
<td>消除跨段口径不一致；候选取"最近"而非"第一个"（与容器顺序解耦）</td></tr>
<tr><td>粘滞规则</td><td>旧目标仍存活且仍具护驾价值 → 不切换；<b>但新候选正在锁祭司而旧目标没锁 → 必须切换</b></td>
<td>既消灭等价目标交替，又不放过"真正的凶手"</td></tr>
<tr><td>manageMilitary() D-1 / D0-p1 / D0-p2</td><td>删除三处各自的目标重算，改为只读粘滞值</td><td>跨段唯一真源</td></tr>
<tr><td>manageCounterAttack() 1.5 段</td><td>改用 <code>priestGuardTarget</code>；<b>叫停门槛仍保持"敌锁祭司 或 敌≤8格"</b></td>
<td>消除同帧覆盖；不放宽叫停阈值（避免反攻永远推不出去）</td></tr>
<tr><td>D0 优先级 3（自卫）</td><td>加 <code>WorkObjectSN != selfEnemy</code> 去重 + 15 帧节流</td><td>同目标重复指令同样会重置进度</td></tr>
<tr><td>各护驾发令点</td><td>统一 15 帧/单位节流（兜底）</td><td>即便目标仍跳变，也保证 ≥0.6 秒不被打断</td></tr>
</table>
</div>

<h2>4. 实测对比（16 局基线 pu+ez / 8 局修复 pg）</h2>
<div class="card">
{cmptable(BASE, FIX, 'pu 基线', 'pg 修复', items)}
<div class="note">
<b>必须分开读两类指标。</b>
<b>机制指标（逐帧、确定性）决定性地改善</b>：出手/发令 {ratio(BASE['atks'],BASE['cmds'])} → {ratio(FIX['atks'],FIX['cmds'])}，
卡死单位 {BASE['th']} → {FIX['th']}，重度卡死 {BASE['st']} → {FIX['st']}
—— "被护驾锁死、零输出"这一现象已被 <b>根除</b>。
<br>
<b>但结果指标（胜率、祭司存活）在本批 8 局上是退化的</b>：祭司死亡 {BASE['priest']}/16 → {FIX['priest']}/8。
原因是<b>护驾指令现在真的生效了</b>：大军会被真实地拉回祭司身边，反攻推进被更频繁打断，
武器厂发现率 75% → 50%、发现中位帧 38.5k/40.8k → 41.7k。
<br>
⚠ 样本量小（基线 16 局方差本身就大：同一份代码的 pu 与 ez 两批，发现中位帧相差 2243 帧、
祭司死亡 2/8 vs 1/8）。<b>8 局判不出 ≤10pp 的差异</b>，需要 ≥16 局/批才能定论。
</div>
</div>

<h2>5. 修复批次逐局明细</h2>
<div class="card">
{gameTable(FIX)}
<p class="mono" style="margin-top:10px">武器厂发现：pg 仅 4/8（pg2 42039 / pg4 38749 / pg5 43349 / pg7 41458），
另 4 局直到祭司阵亡都没发现武器厂。基线 pu+ez 为 12/16。</p>
</div>

<h2>6. 顺带查实的第二个缺陷：箭塔不能解锁「前出感化」迟滞锁</h2>
<div class="dang">
<p><b>现象（pg7 铁证）</b>：祭司在<b>两座敌方箭塔正在向它开火</b>的情况下推进去感化武器厂，随即阵亡。</p>
<pre>41458  &gt;&gt; Enemy Siege Workshop found at (77,82)!
41701  [LC-DBG] siegeSN=11099 mem=(77,82) dS=17.4 hp=0.85
41768  HumanAction:箭塔 11107 设置攻击目标为 祭司 91166     ← 塔开火
41769  箭塔(编号:11107)开始向祭司(编号：91166)攻击
41981  HumanAction:箭塔 11105 设置攻击目标为 祭司 91166     ← 第二座塔开火
41982  箭塔(编号:11105)开始向祭司(编号：91166)攻击
42176  !!! DEFEAT: Priest killed !!!</pre>
<p><b>为什么门禁放行</b>——两层原因：</p>
<ol>
<li><b>清场判据是"局部"而非"全部拆完"</b>（设计如此）：
<code>localClear</code> = 敌<b>活军队</b>距祭司 ≥ 8 格 <b>且</b> 敌<b>箭塔</b>距祭司 ≥ 14 格。
"塔没拆完"根本不构成门槛，只有<b>落在祭司 14 格内</b>的塔才算障碍。
设计理由是：全局"塔全拆完"几乎不可达（多数局敌军队始终存在），采用全局判据会让祭司永远不感化 ⇒ 永远赢不了。</li>
<li><b>真缺陷：迟滞锁只看军队、不看箭塔</b>（违反铁律 9「解锁条件须与置位条件同源」）：
<pre>置位: if (localClear &amp;&amp; enemySiegeSN != -1) priestSiegeApproach = 1;      // 置位含"14 格内无箭塔"
复位: hardAbort = 任一敌【军队】距祭司 &lt; PRIEST_SIEGE_ABORT_R(4.5格)   // ← 复位【完全不含箭塔】
      if (hardAbort || hp &lt; 0.35 || enemySiegeSN == -1) priestSiegeApproach = 0;</pre>
一旦在"塔还在 14 格外"时置位，之后祭司推进、敌箭塔进入 14 格（甚至进 12 格射程开火），
<b>锁不会解除</b>；且 <code>if (allowConvertSiege &amp;&amp; enemySiegeSN != -1) priestTooClose = false;</code>
会把"太靠前→强制后撤"的安全距离约束也一并关掉 ⇒ 单向闩锁，祭司被钉在塔火下送命。</li>
</ol>
<p>另注：<code>enemyMil</code> / <code>enemyTowers</code>（cpp:5551-5554）算出后<b>只出现在注释里</b>，
从未参与判据——是遗留死代码，注释宣称的"全局清场"与代码实际执行的"局部清场"不一致，易误导后续维护。</p>
</div>

<h2>7. 本轮沉淀的铁律</h2>
<div class="note">
<p><b>21. 「同一语义写两遍」是并发覆盖的温床。</b>
两个函数都要下发同一类指令时，必须共用<b>同一个裁决结果</b>（单一真源），
而不是各自用"相似但口径不同"的代码重算。判据：把两处的目标打出来，看<b>同一帧是否相同</b>——
不同即为覆盖。<code>if (a.WorkObjectSN != target)</code> 这类去重<b>保护不了</b>目标自身在跳变的情况。</p>
<p><b>22. 去重条件只有在"被比较量稳定"时才有意义。</b>
<code>WorkObjectSN != guardSN</code> 语义是"已在打它→不重发"，但当 guardSN 逐帧跳变时，
它就变成"每帧都是新目标→每帧都重发"。诊断口径：数<b>发令数 / 真出手数</b>的比值——
正常接近 1，一旦 ≫ 1（本例 pu7 为 141:0）即说明该单位在被反复重置。</p>
<p><b>23. 迟滞锁的置位/复位判据必须"同源同集合"。</b>
置位含"无箭塔"，复位就必须含"箭塔进圈"。少一个维度 = 单向闩锁，
而且因为锁会顺带关掉安全约束（本例的 <code>priestTooClose=false</code>），后果比"没生效"更严重。</p>
</div>

<h2>8. 遗留</h2>
<div class="card">
<ol>
<li><b>本轮 8 局结果指标退化，尚不能定论</b>（机制指标已决定性改善）。需 ≥16 局/批复测，
   或先把"护驾拉回"对推进的打断量做限流，再复测。</li>
<li><b>箭塔–迟滞锁缺口待修</b>：给 <code>priestSiegeApproach</code> 的复位条件补上箭塔维度
   （与置位同源）。需权衡：判据若过严会退回"祭司永不敢进"的老死锁。</li>
<li>反攻期祭司仍孤身处于战场中段（大军在最前、祭司拖后约 35 格）——
   本质缺陷是<b>缺少专职护卫编制</b>；本轮只修了"护驾指令失效"，未改编制。</li>
<li>学院仅 1 座（方阵产能瓶颈）、护甲链生存率回归，仍待处理。</li>
</ol>
</div>

</div></body></html>
"""

open(REPORT, 'w', encoding='utf-8').write(HTML)
print('written', REPORT, len(HTML), 'bytes')
