# -*- coding: utf-8 -*-
"""把 kc 判决 + M5 根因与修正 追加进 aoe3_kiting_20260918.html（保留前 7 节）。"""
import io

P = "aoe3_kiting_20260918.html"
s = io.open(P, encoding="utf-8").read()
mark = "<h2>8 · "
i = s.index(mark)
head = s[:i]

tail = u"""<h2>8 · kc 批验证（M4）：档位修对了，距离仍没拉开</h2>

<table>
  <thead><tr><th>指标</th><th>gi 基线</th><th>kb（M1~M3）</th><th>kc（+M4）</th><th>判定</th></tr></thead>
  <tbody>
    <tr><td><b>stage=1「远离敌」占比</b></td><td class="num">23.7%</td><td class="num">23.5%</td>
        <td class="num">65.5%</td><td class="up">↑ 42pp ✅ M4 生效</td></tr>
    <tr><td>stage=2「朝 TC」占比</td><td class="num">76.3%</td><td class="num">76.5%</td>
        <td class="num">34.5%</td><td class="up">↓</td></tr>
    <tr><td><b>dK 全体中位</b></td><td class="num">5.5 格</td><td class="num">7.8 格</td>
        <td class="num">7.6 格</td><td class="dn">✗ 没动</td></tr>
    <tr><td>dK &lt; 8.5 格占比</td><td class="num">98%</td><td class="num">61%</td>
        <td class="num">62%</td><td class="dn">✗ 没动</td></tr>
    <tr><td>stage=1 的 dK 拉开比</td><td class="num">90%</td><td class="num">86%</td>
        <td class="num">56%</td><td class="dn">↓（口径被污染，见下）</td></tr>
    <tr><td>stuck 分布</td><td class="num">0:1739 1:3617 2:1965</td>
        <td class="num">0:2232 1:4638 2:2627</td><td class="num">0:7175 1:3780</td>
        <td class="eq">只剩 0/1 两档</td></tr>
    <tr><td>撤退窗口总数</td><td class="num">7321</td><td class="num">9497</td>
        <td class="num">10955</td><td class="dn">↑</td></tr>
  </tbody>
</table>

<p>kc 的 <code>stuck=0</code> 计数 <b>7175</b> ≈ <code>stage=1</code> 计数 <b>7174</b>，<code>stuck=1</code>
<b>3780</b> ≈ <code>stage=2</code> <b>3781</b> —— 说明窗口形态被压成了固定两拍：
<b>第 1 帧走 stage=1，第 2 帧就被判"没拉开"翻去 stage=2</b>。所以 stage=1 占比的暴涨只是
"每窗口都试了一次正确的方向"，<b>距离一点没多</b>。</p>

<div class="card bad">
  <b>M4 的方向是对的，但不够。</b>它让每个撤退窗口都无条件试一次「远离敌」，
  但只买到 <b>一帧</b> —— 下一帧就拿"一帧内没拉开"去审判结果，翻回方向盲的 stage=2。
</div>

<h2>9 · 决定性测量：撤退令本身<b>有效</b>，是攻击令把它顶掉了</h2>

<p>换一套口径再问一次：把同一 SN 相邻两个撤退窗口之间的 25~45 帧切成一个个区间，
按<b>区间内有没有出现攻击令</b>分桶，看单位到底动没动。</p>

<table>
  <thead><tr><th>撤退窗口区间内</th><th>样本</th><th>30 帧位移中位</th><th>位移 &gt;1 格</th><th>位移 &lt;0.2 格</th><th>dK 变化中位</th></tr></thead>
  <tbody>
    <tr><td><b>无攻击令</b></td><td class="num">609</td><td class="num">1.50 格</td>
        <td class="num up">89.3%</td><td class="num">4.4%</td><td class="num up">+0.60 格</td></tr>
    <tr><td><b>有攻击令</b></td><td class="num">6142（90.9%）</td><td class="num">0.00 格</td>
        <td class="num">8.8%</td><td class="num dn">85.5%</td><td class="num dn">+0.00 格</td></tr>
  </tbody>
</table>

<p>gi 基线同口径：无攻击令 → 位移中位 <b>1.58 格</b>、<b>93.5%</b> 位移 &gt;1 格；
有攻击令 → <b>0.00 格</b>、<b>94.4%</b> 位移 &lt;0.2 格。<b>两批完全一致。</b></p>

<div class="card tldr">
  <b>结论句：撤退令没问题，问题是它活不过下一帧。</b><br>
  ① 撤退 <code>HumanMove</code> 一旦下发，单位确实会走出去（无攻击令时 89% 位移 &gt;1 格、dK 真的 +0.6 格）。<br>
  ② 但撤退窗口内 <b>90.9%</b> 的区间夹着攻击令；攻击令是"本帧最后写入的指令"，
     直接把撤退落点顶掉 ⇒ 位移恒为 <b>0.00 格</b>。<br>
  ③ 这<b>不是</b>"审判得太早"：把时间放宽到 30 帧，位移 &gt;1 格仍只有 <b>19.3%</b>
     （gi 基线 5.2%）—— 给足时间也不走，因为指令活不到那么久。
</div>

<h3>覆盖源定位：帧序 + 豁免链</h3>

<ul>
  <li><b>不可能来自 kiting 自己。</b>kiting 的 SHOOT 带有 <code>RETREAT_PROTECT_FRAMES = 60</code>
      保护，撤退令后 60 帧内它不会发攻击令；而我们的区间只有 25~45 帧。</li>
  <li><b>帧序决定责任方。</b><code>manageMilitary</code>（<code>cpp:3744</code>）每帧先于
      <code>manageCounterAttack</code>（<code>cpp:4386</code>）运行。它对该单位下发的攻击令，
      会把<b>上一帧</b>的撤退 <code>HumanMove</code> 顶掉。</li>
  <li>该函数里的攻击令下发点：<code>D-1 祭司护驾</code>（<code>!urgent</code> 才跳过 ATTACKING ⇒ 紧急时不跳）、
      <code>D0 优先级 1/2/3</code>、<code>D1</code>（要求 IDLE）、<code>D2</code>（反攻期已跳过）。</li>
  <li>预算 <code>maxAttackCmds = isWarTime ? 8 : 4</code> —— 每帧只服务 8 个单位，但一个 30 帧窗口
      足以覆盖到同一个兵。</li>
</ul>

<p>单兵铁证（<code>kc10.ait</code>，SN=91382，帧 35375 起）：</p>

<pre>35375  MOVE -&gt; (2397.0,2159.3)   <span class="c">← 撤退令，落点 3.6 格外</span>
35376  ATK  -&gt; 方阵兵            <span class="hi">← 下一帧就被攻击令覆盖</span>
35404  KIT  self=(67.5,63.9)    <span class="hi">← 30 帧后坐标一字未动</span>
35405  MOVE -&gt; (2103.0,1991.5)
35406  ATK  -&gt; Prof.Lu
35464  KIT  self=(67.5,63.9)    <span class="hi">← 又 60 帧，仍是 (67.5,63.9)</span>
...    （self 在 200+ 帧内恒为 (67.5,63.9)）</pre>

<h2>10 · 本次修正 M5：拉扯撤退锁（单一真源，4 处）</h2>

<p>把"正在撤退"提升为一个<b>全局状态</b>，由所有攻击令下发点共同尊重 —— 而不是只在 kiting 段内部
自己保护自己（这正是一周前 <code>enemyBldSeenN</code> 那一族病：同一语义分散在多处，改一处漏一处）。</p>

<table>
  <thead><tr><th>#</th><th>位置</th><th>改动</th></tr></thead>
  <tbody>
    <tr><td>M5-a</td><td><code>cpp:4138</code></td>
        <td>新增<b>单一真源</b> <code>kiteRetreatLocked(sn)</code> = ① <code>kitingPhase[sn]==1</code>
            （RETREAT 相位）或 ② 撤退令后 <code>KITING_HOLD_FRAMES=40</code> 帧内（让撤步走完再允许接战）</td></tr>
    <tr><td>M5-b</td><td><code>cpp:4179</code>（D-1 护驾）</td>
        <td><code>if (!urgent &amp;&amp; kiteRetreatLocked(a.SN)) continue;</code> ——
            <b>预警级</b>不得覆盖撤退中的弓兵；<b>紧急级</b>（敌已锁祭司 / 贴到祭司 8 格内）仍可覆盖</td></tr>
    <tr><td>M5-c</td><td><code>cpp:4219</code>（D0）</td>
        <td>同一行，<b>刻意放在优先级 1 之后</b> ⇒ 敌已锁祭司时不锁（保命优先），其余全部让位于撤退</td></tr>
    <tr><td>M5-d</td><td><code>cpp:4290</code>（D1）</td>
        <td>同一行，防"IDLE 时被就近清敌令抓走"</td></tr>
  </tbody>
</table>

<div class="card ok">
  <b>豁免清单（有意不锁）：</b><code>D-1 紧急级</code> · <code>D0 优先级 1</code> ·
  <code>manageCounterAttack 1.5 祭司护驾 HALT</code>。理由一致：<b>祭司死 = 立刻失败</b>，
  保命优先于拉扯。
</div>

<p><b>校验</b>：<code>syn</code> 0 error / 18 warning ｜ <code>warn_cmp2</code> 类别集合一致 ｜
<code>build</code> <code>rc=0 / errors=0</code>（exe 2150400 B）。指纹 <code>5cc43dee</code> / <b>6709 行</b>。
回滚点 <code>UsrAI.cpp.bak_20260918_pre_kite_lock</code>。</p>

<h2>11 · 残余（已定位，本轮未动）</h2>

<h3>① 1.5 祭司护驾 HALT：整个反攻段被直接 return 掉</h3>
<p><code>cpp:4566</code>：祭司 8 格内有敌、或有敌以祭司为目标时，<b>整个 <code>manageCounterAttack</code>
直接 <code>return</code></b>（含 kiting 段），并对<b>全军</b>下发攻击令。
实测占反攻期约 <b>7~12%</b>（同局相邻 HALT 日志间隔 78% 恰为 50 帧 = 持续触发状态）。
判为祭司保命路径，本轮按"一次只改一组变量"未动。</p>

<h3>② M1 的绝对阈值 11 格超出单位可达范围</h3>
<p>kc 批 dK 中位 <b>7.6 格</b>、<b>62%</b> 在 8.5 格以内，而 M1 把 RETREAT 退出阈值抬到了
<code>R+4.0 = 11</code> 格 ⇒ 单位物理上撤不到，只能每 60 帧靠兜底切回 SHOOT ——
这是撤退窗口 +30% 的一部分来源。迟滞带由负转正的<b>意图</b>是对的，<b>绝对值</b>超出可达范围。
M5 让撤退真正能走出去后再评估是否回调。</p>

<h3>③ <code>tryRetreatLanding</code> 落点筛选仍太弱</h3>
<p>只调 <code>isPassableAt</code>（海洋 + <code>forestGrid</code>），<b>不判占用、不判路径、无吸附</b>
（同文件的 <code>issueMarch</code> 有 <code>snapWalkable</code>）。留作下一轮。</p>

<h2>12 · kd 批验收口径（24 局，正在跑）</h2>

<table>
  <thead><tr><th>指标</th><th>kc（M4）</th><th>目标</th></tr></thead>
  <tbody>
    <tr><td><b>撤退窗口内出现攻击令占比</b></td><td class="num">90.9%</td><td class="up">→ 应 &lt; 30%</td></tr>
    <tr><td><b>撤退窗口内位移中位</b></td><td class="num">0.00 格</td><td class="up">→ 应 &gt; 1.0 格</td></tr>
    <tr><td>dK 全体中位</td><td class="num">7.6 格</td><td class="up">→ 应 ≥ 9.5 格</td></tr>
    <tr><td>dK &lt; 8.5 格占比</td><td class="num">62%</td><td class="up">→ 应 &lt; 35%</td></tr>
  </tbody>
</table>

<p><b>同时做回归检查</b>（防"锁把输出也锁死"）：祭司起手次数、胜负分布、攻击令总数、末日帧中位。
按铁律 25，单批 24 局不足以判胜负，只作机制量判据。</p>

<h2>13 · 一个顺带发现（未修）</h2>

<p>复合弓兵攻箭塔的放行判据用的是 <code>ARROWTOWER_RANGE</code>（<code>cpp:144</code> 定义为 <b>8.0</b>），
而 <code>config.json</code> 里 <code>DIS_ARROWTOWER</code> 真值是 <b>7</b>，代码注释却写着"与 config.json 一致"。
后果是射程同为 7 的战车弓兵被误判为"够不着塔"而禁止打塔。这是纯 bug，与拉扯问题无关，留档待办。</p>

<div class="foot">
  证据文件：<code>gi1..gi24.ait</code>（基线）· <code>kb1..kb24.ait</code>（M1+M2+M3）·
  <code>kc1..kc24.ait</code>（M4）· <code>kd1..kd24.ait</code>（M5，跑批中）<br>
  探针：<code>kit_atk_vs_path.py</code>（<b>攻击令 vs 位移分桶，本轮决定性</b>）·
  <code>kit_stage_probe.py</code>（档位/相位时长/dK 走向）· <code>kit_grace_probe.py</code>（给足时间能否拉开）·
  <code>kb_cmp_probe.py</code>（机械量对比）· <code>kit_override_probe.py</code>（反向顶掉率）·
  <code>kit_trace.py</code>（单兵时间线）<br>
  源码：<code>C:\\new-aoe3.0.7g\\UsrAI.cpp</code>（唯一编译源，<code>5cc43dee</code> / 6709 行）·
  回滚：<code>UsrAI.cpp.bak_20260918_pre_kite_lock</code>
</div>

</div>
</body>
</html>
"""

io.open(P, "w", encoding="utf-8", newline="\n").write(head + tail)
print("已写入，总行数 =", (head + tail).count("\n") + 1)
