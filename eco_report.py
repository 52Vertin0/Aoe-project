#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成资源采集分配诊断报告 HTML（6 批 48 局）。"""
import os, time
from eco_summary import BATCHES, one

REPORT = 'aoe3_eco_alloc_20260914.html'


def head(title):
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{title}</title><style>
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
<h1>{title}</h1>
<div class="sub">AoE3 UsrAI · 基线 3.0.7g · 25fps · map3 rotate=90 · 8 局/批 × 6 批 = <b>48 局</b> ·
生成于 {time.strftime('%Y-%m-%d %H:%M')}</div>"""


def main():
    D = {b: one(b) for b, _n, _c in BATCHES}
    base_w = D['pu']['w'] + D['ez']['w']
    base_t = D['pu']['t'] + D['ez']['t']

    h = [head('资源采集分配：诊断与实测报告')]

    # 摘要
    h.append(f"""<div class="card">
<h3 style="margin-top:0">结论摘要</h3>
<p>本轮在资源采集分配模块中<b>定位并确认了 3 个真实缺陷</b>（工人统计双重计数、
<code>findAnyFarmer</code> 优先级死代码、停采门禁悬崖式+采石永久停采），
并分 6 批 48 局做了对照实测。<b>但实测显示：修复这些缺陷后胜率并未改善，反而下降</b>
（基线合并 {base_w}/{base_t} = {100.0*base_w/base_t:.0f}% → 最小修复集 3/8 = 38%），
复合弓产出从 249/282 腰斩到 134。</p>
<p>由于胜率差异在 8 局/批的样本量下<b>未达统计显著</b>（Fisher 双尾 p≈0.47），
无法断言"修复有害"；但<b>同样没有证据支持修复有益</b>。因此本轮<b>保留基线不回退</b>，
把诊断结论、失败路径与工具留档，供后续重标定时使用。</p>
</div>

<div class="kpi">
<div class="kpib w"><div class="t">发现的真实缺陷</div><div class="n">3 个</div>
<div class="t">均有日志铁证</div></div>
<div class="kpib r"><div class="t">基线胜率（两批一致）</div>
<div class="n">{100.0*base_w/base_t:.0f}%</div><div class="t">pu 5/8 + ez 5/8</div></div>
<div class="kpib r"><div class="t">最小修复集胜率</div><div class="n">38%</div>
<div class="t">ey 3/8</div></div>
<div class="kpib w"><div class="t">差异显著性</div><div class="n">p≈0.47</div>
<div class="t">Fisher 双尾，不显著</div></div>
<div class="kpib g"><div class="t">资源稳定性（唯一确定收益）</div><div class="n">-41%</div>
<div class="t">木锯齿 22→13</div></div>
<div class="kpib g"><div class="t">计数违规（8人报12人）</div><div class="n">→ 0</div>
<div class="t">自检 100% 通过</div></div>
</div>""")

    # 1 诊断
    h.append("""<h2>1. 诊断：资源分配模块的 3 个缺陷</h2>
<div class="card">
<h3>缺陷 ① 工人统计【双重计数】（头号根因）</h3>
<p><code>ResourceSort</code> 的真实语义是 <b>人物手持资源种类</b>
（<span class="mono">config.h「人物手持资源种类」</span> 注释 +
<span class="mono">GlobalVariate.h:141 "手持资源种类"</span>，<code>HUMAN_UNKNOWN=0</code> 表示空）；
<code>WorkObjectSN</code> 才是 <b>工作目标</b>。旧代码对这两个<b>语义完全不同</b>的量<b>各自 ++</b>：
先按手持资源计一次，再到资源表里按工作目标计一次。</p>
<p>而引擎把 <code>WorkObjectSN</code> 当"上次工作目标"<b>长期保留</b>（村民早已改派，字段仍指着旧目标）
⇒ 同一人<b>必被计两次</b>。</p>
<pre>铁证：开局日志旧版字段 Frm:8（全场只有 8 个村民）
      而 workers 之和 = F3 + W7 + G0 + S2 = 12    ← 虚高 50%</pre>
<p><b>后果链</b>：<code>woodWorkers</code> 虚高 ⇒ <code>woodWorkers &lt; woodTarget</code> 恒假
⇒ <b>从不派伐木工</b>；回撤判据 <code>woodWorkers &gt; WOOD_KEEP_MIN</code> 同样被虚高值误触发
（实际 3 人却被当 5 人撤到 2 人）；<code>foodWorkers</code> 虚高 ⇒ 金工配额连带失真。</p>

<h3>缺陷 ② <code>findAnyFarmer()</code> 前三轮是死代码</h3>
<p>判据写成 <code>NowState==WORKING &amp;&amp; ResourceSort==HUMAN_STONE</code>（金/木同构）——
把<b>手持资源</b>当<b>正在采集的资源</b>用。而 <code>WORKING</code> = 正在采集，
此刻手上<b>恰恰没有</b>资源 ⇒ 前三轮（石→金→木）<b>恒返回 nullptr</b>，
"优先抽采石工→采金工→伐木工"的设计优先级<b>从未生效</b>，实际永远落到第 4 轮"任取一个在干活的"。</p>

<h3>缺陷 ③ 停采门禁【悬崖式】+ 采石永久停采</h3>
<p>门禁只有"存量 ≥ 上限"单一判据、<b>没有恢复带</b>：触顶就把该资源工人撤光，
而恢复派工要等"存量跌破上限"且恰好有 IDLE 村民（撤下去的工人早已被转岗、不会回头）。</p>
<pre>实测 8/8 局肉和木都探底到 0。改前 pu1 采样：
肉 70→20→350→537→57→127→36→31→405→655→575→635→538→173→3
木 45→39→24→114→279→150→21→23→117→81→336→318→421→271→13</pre>
<p>另外 <code>stoneStop</code> 里含 <code>frame &gt;= WAVE3_TIME</code> <b>时间闸</b>：
14 分钟一到就永久停采石。而箭塔会被打掉（pu1 末段 <span class="mono">twr 0/3</span>、石仅剩 40）
⇒ 塔全灭后想重建却一块石头都没有。</p>
</div>""")

    # 2 实测
    h.append("<h2>2. 实测：6 批 48 局</h2><table>")
    h.append("<tr><th>批次</th><th>改动集</th><th>胜/负/平</th><th>复合弓</th><th>方阵</th>"
             "<th>农场令</th><th>祭司死</th><th>木材均值</th><th>木锯齿</th></tr>")
    order = ['pu', 'ez', 'ev', 'ew', 'ex', 'ey']
    name_of = {b: (n, c) for b, n, c in BATCHES}
    for b in order:
        s = D[b]
        wld = f"{s['w']}/{s['l']}/{s['d']}"
        hl = " class='ok'" if b in ('pu', 'ez') else ''
        h.append(f"<tr><td class='mono'{hl}>{b}</td><td style='text-align:left'>{name_of[b][1]}</td>"
                 f"<td class='num'{hl}>{wld}</td><td class='num'>{s['cb']}</td><td class='num'>{s['pf']}</td>"
                 f"<td class='num'>{s['farms']}</td><td class='num'>{s['priest']}</td>"
                 f"<td class='num'>{s['wdM']:.0f}</td><td class='num'>{s['sawW']}</td></tr>")
    h.append("</table>")
    h.append(f"""<div class="note"><b>基线可复现性</b>：同一份未修改代码跑了两个独立批次，
胜率完全一致（pu 5/8 = 62.5%、ez 5/8 = 62.5%，复合弓 249 / 282）⇒
基线表现稳定，可以作为对照基准。<br>
<b>Fisher 精确检验</b>（基线合并 10/16 vs 最小修复集 3/8）：双尾 p ≈ 0.47 ⇒
<b>胜率差异未达统计显著</b>；但复合弓产出 249/282 → 134（<b>-50%</b>）是方向一致的机制性证据。</div>""")

    # 3 关键失败病例
    h.append("""<h2>3. 两个关键失败病例（最有价值的过程记录）</h2>
<div class="card">
<h3>病例 A：把 <code>woodTarget</code> 改成人口相关 ⇒ 木材链断裂 ⇒ 复合弓 0</h3>
<p>原 <code>woodTarget</code> 是固定 4/8 人，看起来与 22~34 人的经济脱节，于是改成
人口相关（<span class="mono">4 + tot/10</span> / <span class="mono">8 + tot/8</span>，17人→6/10）。
结果 ev1/ev5 <b>复合弓产出 = 0</b>，祭司在<b>防守期（10.5 分）裸奔被杀</b>。</p>
<pre>ev1 日志： [FARM-TECHWAIT f=15000] 农场等木材加工科技 wood=53~73 meat=55 farms=0/12 mkt=1
          BUILD-ISSUE 只 16 条，其中 type=4(农场) = 0 条   ← 对照 pu1：48 条 / 23 条农场令</pre>
<p><b>链条</b>：抬高伐木配额 ⇒ 挤压食物岗 ⇒ 木材长期卡在 53~73 ⇒ <b>买不起 75 木的木材加工科技</b>
⇒ 农场 0 座 ⇒ 食物链断裂 ⇒ 造不出兵。</p>

<h3>病例 B：「缺口回补」是负优化（明明诊断对了，方案却错了）</h3>
<p>诊断：旧系统的人力重分配<b>只由停采门禁的边沿驱动</b>，主循环派工<b>只认 IDLE 村民</b>
⇒ 木头被一次性大建造掏空后（ev1：木 298→63 只用 11 秒），在岗的 12 个食物工
既不会被"派工"碰到、也不会被"回撤"碰到 ⇒ 木头长期低位。</p>
<p>方案：加"缺口回补"块按缺口驱动（每 60 帧从食物/黄金岗抽 1 人伐木）。
<b>结果反而更差</b>：<code>ECO-PULL</code> 每局触发 41~49 次 ⇒ 平均每 2.4 秒搬 1 人
⇒ 村民大量时间耗在<b>转岗路上</b>；ex 批次村民数 27.5（六批最多）却复合弓只有 152（最少）。</p>
</div>""")

    # 4 教训
    h.append("""<h2>4. 关键教训（可复用）</h2>
<div class="danger">
<p><b>① 修复"虚高统计"会连锁改变所有以它为基数的配额。</b></p>
<p><code>goldTarget = foodWorkers × 3/5</code> 在双重计数下被虚高 ≈1.5×，
而食物工约占人口 45%，于是 <code>goldTarget ≈ 1.5 × 0.45N × 0.6 = 0.4N</code>
—— 虚高<b>意外地</b>把金工配额撑到 ~9 人。修好双重计数后基数缩回真实值
⇒ 配额腰斩到 ~3 ⇒ <b>实测反攻期黄金 59.7 → 10.8（峰值 230→80）</b>
⇒ 复合弓兵(20金)/方阵兵(40金)造不出 ⇒ 0 胜。</p>
<p><b>推论</b>：改任何"统计/计数口径"之前，必须先列出<b>所有以它为基数的下游配额</b>，
并准备好一次性重标定；否则就是"修一个 bug、制造三个失衡"。</p>
</div>
<div class="note">
<p><b>② 胜率对调度细节极度敏感，而 8 局/批的样本量不足以判定小幅差异。</b>
基线获胜多在 38.7k~44.0k 帧（45000 上限前 1~6 分钟）——属于<b>压哨胜</b>，
任何把节奏往后推几分钟的改动都会吃掉胜局。判定这类改动需要 <b>≥16 局/批</b> 才有效力。</p>
<p><b>③ 资源"稳定"不等于"打得赢"。</b>基线的剧烈振荡（肉 0~777）其实对应
"资源一到位就被立刻花掉"的极限转化；给资源加缓冲带后曲线变平滑，
但兵力转化反而变慢（复合弓 -50%）。<b>库存水位不是目标，转化速率才是。</b></p>
</div>""")

    # 5 遗留
    h.append("""<h2>5. 遗留与下一步</h2>
<div class="card">
<p>本轮<b>未解决</b>且已量化的问题：</p>
<ol>
<li><b>金工配额空转</b>：修复后 <code>gT</code> 显示配额 9，但实际金工长期只有 0~4 ——
因为食物岗吸满人力（<span class="mono">F14 W8 G0 tot22</span>，<b>没有 IDLE 村民可派</b>）。
候选修法：在回撤块增加"黄金缺口"分支，且必须比病例 B 的回补<b>保守得多</b>（如每 300 帧 1 人）。</li>
<li><b>祭司在反攻初期（23~29 分）阵亡</b>仍是最主要失败模式（基线两批 2+1 例，修复版 4~5 例），
与 2026-09-13「祭司反攻期安全距离」同源，属独立于资源分配的战斗问题。</li>
<li>若将来要重做本轮修复，<b>必须配套重标定</b>：
<code>woodTarget</code> / <code>goldTarget</code> / <code>WOOD_KEEP_MIN</code> /
<code>MIN_GOLD_WORKERS</code> / <code>*_CAP_STOP</code> 需以"真实统计口径"重新取值，
并以 <b>16 局/批</b> 验证。</li>
</ol>
<p><b>产物</b>：备份 <span class="mono">UsrAI.cpp.bak_20260914_pre_eco</span>（纯基线，已生效）与
<span class="mono">UsrAI.cpp.bak_20260914_eco_min</span>（最小修复集，留档）；
工具 <span class="mono">eco_lint.py</span>（ECO 采样解析 + 计数自检）、
<span class="mono">eco_compare.py</span>、<span class="mono">eco_summary.py</span>、
<span class="mono">gold_lint.py</span>、<span class="mono">eco_report.py</span>。</p>
</div>
</div></body></html>""")

    with open(REPORT, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(h))
    print(f"生成 {REPORT} ({os.path.getsize(REPORT)} bytes)")


if __name__ == '__main__':
    main()
