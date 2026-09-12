# -*- coding: utf-8 -*-
"""把 kb 批验证结果 + M4 根因写进报告（替换第 5 节起的所有内容）。"""
P = "aoe3_kiting_20260918.html"
NL = "\r\n"

NEW = """<h2>5 · kb 批验证（24 局）：有改善，但<b>没解决</b></h2>

<p>24 局跑完（<code>kb1..kb24.ait</code>），机械量对比 <code>gi</code> 批（同规模 24 局）：</p>

<table>
  <thead><tr><th>指标（口径逐字一致）</th><th>gi 基线</th><th>kb（M1+M2+M3）</th><th>结论</th></tr></thead>
  <tbody>
    <tr><td>撤退窗口总数</td><td class="num">7321</td><td class="num">9497 (+30%)</td><td class="dn">更多了</td></tr>
    <tr><td>撤退后 60 帧内出现攻击令</td><td class="num">96.7%</td><td class="num">89.5%</td><td class="up">↓ 7.2pp</td></tr>
    <tr><td>撤退后 90 帧内又被反向落点顶掉</td><td class="num">40.4%</td><td class="num">30.9%</td><td class="up">↓ 9.5pp</td></tr>
    <tr><td>窗口内单位位移 &lt; 0.5 格（空转）</td><td class="num">88.5%</td><td class="num">72.1%</td><td class="up">↓ 16.4pp</td></tr>
    <tr><td><b>dK 走向「拉开 : 缩小」</b></td><td class="num">40%</td><td class="num"><b>37%</b></td><td class="dn">✗ 未改善</td></tr>
    <tr><td>祭司起手 / 胜局</td><td class="num">0 / 0</td><td class="num">1 / 1</td><td class="eq">噪声内</td></tr>
  </tbody>
</table>

<div class="card bad">
  <b>关键否证：距离根本拉不开。</b>三处修正让"顶着撤退令的反向指令"少了、空转少了，
  但 <b>与敌距离实际拉开的比例反而从 40% 降到 37%</b>——<b>撤了，但没撤开</b>。
  这说明前三条修的都是<b>次要抵消源</b>，真正把钱花在别处。
</div>

<div class="card warn">
  <b>顺带发现 M1 的方向有问题。</b>kb 批的 dK 中位 <b>7.8 格</b>、<b>61% 落在 &lt;8.5 格</b>——
  而 M1 把退出阈值抬到了 <b>11 格</b>。单位物理上撤不到 11 格 ⇒ 永远满足不了退出条件 ⇒
  只能每 60 帧靠兜底强制切回 SHOOT。这就是撤退窗口 +30% 的来源。
  M1 的<b>意图</b>（迟滞带由负转正）是对的，但<b>绝对阈值</b>超出了单位可达范围。
  暂不回退——等 M4 生效后 dK 能真正拉开到 12 格，11 的阈值才有意义。
</div>

<h2>6 · 决定性根因：档位结构性互斥（76% 的撤退令方向是错的）</h2>

<p>我回到 <code>KIT-R</code> 日志的 <code>stage</code> 字段——它记录本次撤退令走的是哪一档。
两批数据<b>完全一致</b>，说明这是与 M1/M2/M3 <b>无关的独立结构性缺陷</b>：</p>

<table>
  <thead><tr><th>撤退档位</th><th>gi 占比</th><th>kb 占比</th><th>该档的 dK 拉开比</th></tr></thead>
  <tbody>
    <tr><td><b>stage=1</b>「远离敌」（落点 = 敌 + 1.8R，真正的撤退）</td><td class="num">23.7%</td><td class="num">23.5%</td><td class="up"><b>86~90%（有效）</b></td></tr>
    <tr><td><b>stage=2</b>「朝己方 TC 撤 12 格」（方向盲）</td><td class="num">76.3%</td><td class="num">76.5%</td><td class="dn"><b>15~18%（无效）</b></td></tr>
    <tr><td>stage=3「朝祭司撤」/ 失败</td><td class="num">0%</td><td class="num">0%</td><td class="eq">—</td></tr>
  </tbody>
</table>

<p><b>四分之三的撤退令走的是一条不背离敌人的路。</b>而它<b>可靠地有效</b>的那一档（stage=1），只被用上 24%。</p>

<h3>为什么第 1 档被跳过：跨窗口比较</h3>

<pre><span class="c">// cpp:4850 —— 「上一次没拉开 0.3 格 ⇒ 本次跳过第 1 档」</span>
if (kitingRetPrevDK.count(a.SN)) {
    if (dK &lt; kitingRetPrevDK[a.SN] + 0.3 * BL)   <span class="hi">← prevDK 是【上一轮窗口末】的 dK</span>
        kitingRetStuck[a.SN]++;
}
...
bool skipAwayStage = (kitingRetStuck[a.SN] &gt; 0);   <span class="hi">← 一旦为真，本帧直接走 stage=2</span>
</pre>

<div class="card bad">
  <b>结构性互斥（与 <code>enemyBldSeenN&gt;=2</code> 同类）。</b><br>
  新一轮 RETREAT 的触发条件是「<b>敌贴身</b>」（<code>dK ≤ 0.5R</code> 或 <code>≤0.9R 且 aged≥6</code>），
  而 <code>kitingRetPrevDK</code> 存的是<b>上一轮窗口结束时的 dK</b>（也就是这一轮"撤得最远"的成果）。<br>
  ⇒ 本轮首帧 dK <b>必然</b>小于上轮末 dK ⇒ <code>dK &lt; prevDK + 0.3</code> <b>必然成立</b> ⇒
  <code>stuck</code> 必堆到 1 ⇒ <b>第 1 档「远离敌」在几乎所有窗口里都被跳过</b>，
  只能落到第 2 档「朝 TC 撤」——而 TC 在敌方来向的<b>反侧</b>，方向完全盲。
</div>

<p><b>铁证（计数一一对应）：</b>两批各 24 局里 <code>stuck=0</code> 的窗口数
<b>1739 / 2232</b>，而 <code>stage=1</code> 的窗口数 <b>1737 / 2231</b>——<b>几乎完全相等</b>。
即：<b>只有"没被判定为撤不动"的那一次，才走了真正的撤退档。</b></p>

<p>而且<code>kitingRetStuck</code> 每开新窗口都清零（三处 <code>= 0</code>），
<code>kitingRetPrevDK</code> 却<b>从不清</b>——一个清、一个不清，正是互斥的来源。</p>

<h2>7 · 本次修正 M4（3 处，同一语义）</h2>

<table>
  <thead><tr><th>位置</th><th>改动</th><th>作用</th></tr></thead>
  <tbody>
    <tr>
      <td><code>cpp:4791 / 4806 / 4820</code>（3 处窗口起点）</td>
      <td>在 <code>kitingRetStuck[a.SN] = 0</code> 之后补 <code>kitingRetPrevDK.erase(a.SN)</code></td>
      <td>清掉跨窗口的陈旧基准 ⇒ 窗口首帧不做「撤不动」判定 ⇒ 首帧<b>无条件走第 1 档「远离敌」</b>。
          第 2 帧起恢复判定（此时基准是本窗口自己的 dK，语义正确）</td>
    </tr>
  </tbody>
</table>

<pre><span class="c">// 修正后的判定语义</span>
窗口首帧 : prevDK 已清除 → 不判定 → stuck=0 → <span class="g">stage=1「远离敌」（有效档）✓</span>
第 2 帧   : prevDK = 本窗口首帧 dK → 真撤得动则 dK↑&gt;0.3 → 保持 stage=1 <span class="g">✓</span>
           若确实撤不动        → stuck=1 → 转 stage=2 兜底 <span class="g">（保留原有逃生设计）</span>
</pre>

<div class="card ok">
  <b>三步校验通过。</b><code>syn</code> rc=0 · 0 error · 18 warning｜<code>warn_cmp2</code> 类别集合一致｜
  <code>build</code> rc=0 · errors=0，<code>release/newAOE.exe</code> 2149888 B。<br>
  源码指纹 <code>48a27cda</code> / 6683 行｜回滚点 <code>UsrAI.cpp.bak_20260918_pre_kiting_m4</code>
</div>

<h2>8 · 待验证（kc 批 24 局，正在跑）</h2>

<table>
  <thead><tr><th>指标</th><th>kb 批</th><th>期望方向</th></tr></thead>
  <tbody>
    <tr><td><b>stage=1 占比</b></td><td class="num">23.5%</td><td class="up">→ 应接近 100%</td></tr>
    <tr><td><b>dK 拉开比（总）</b></td><td class="num">37%</td><td class="up">→ 应显著超过 50%</td></tr>
    <tr><td>dK 中位</td><td class="num">7.8 格</td><td class="up">→ 应升到 10 格以上</td></tr>
    <tr><td>空转率</td><td class="num">72.1%</td><td class="up">↓</td></tr>
    <tr><td>撤退窗口总数</td><td class="num">9497</td><td class="up">↓（撤得开 ⇒ 少触发）</td></tr>
  </tbody>
</table>

<div class="card warn">
  <b>已排队未做的下一项。</b>③「落点筛选太弱」仍未动：<code>tryRetreatLanding</code> 用 <code>isPassableAt</code>
  （只判海洋 + <code>forestGrid</code>，树 ±2 格/矿 ±1 格），<b>不判占用、不判路径、无 <code>snapWalkable</code> 吸附</b>
  （同文件的 <code>issueMarch</code> 有）。第 1 档被它整档拒掉的压力不小。按「一次只改一组变量」留作下一轮。
</div>

<h2>9 · 一个顺带发现（未修）</h2>

<p>复合弓兵攻箭塔的放行判据用的是 <code>ARROWTOWER_RANGE</code>（<code>cpp:144</code> 定义为 <b>8.0</b>），
而 <code>config.json</code> 里 <code>DIS_ARROWTOWER</code> 真值是 <b>7</b>，代码注释却写着"与 config.json 一致"。
后果是射程同为 7 的战车弓兵被误判为"够不着塔"而禁止打塔。这是纯 bug，与拉扯问题无关，留档待办。</p>

<div class="foot">
  证据文件：<code>gi1..gi24.ait</code>（基线，kiting 修正前）· <code>kb1..kb24.ait</code>（M1+M2+M3）· <code>kc1..kc24.ait</code>（M4，跑批中）<br>
  探针：<code>kb_cmp_probe.py</code>（两批机械量对比）· <code>kit_stage_probe.py</code>（<b>档位/相位时长/dK 走向，本轮决定性</b>）·
  <code>kit_override_probe.py</code>（反向顶掉率）· <code>kit_move_xcheck.py</code>（令 vs 日志交叉验证）·
  <code>kit_step_probe.py</code>（步长分桶）· <code>kit_trace.py</code>（单兵时间线）<br>
  源码：<code>C:\\new-aoe3.0.7g\\UsrAI.cpp</code>（唯一编译源）· 回滚：<code>UsrAI.cpp.bak_20260918_pre_kiting_m4</code>
</div>

</div>
</body>
</html>
"""

s = open(P, encoding="utf-8", newline="").read()
i = s.index("<h2>5 \u00b7")
s = s[:i] + NEW.replace("\n", NL)
open(P, "w", encoding="utf-8", newline="").write(s)
print("report patched, new size =", len(s))
