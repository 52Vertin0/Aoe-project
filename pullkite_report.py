#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成反攻期拉扯（pullkite）HTML 报告：ln 批（改前）/ kt 批（中间版）/ pu 批（终版）。"""
import os, glob, importlib.util
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))

def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

pc = load_mod('pc', os.path.join(BASE, 'pullkite_compare.py'))

def collect(pattern):
    out = []
    for f in sorted(glob.glob(os.path.join(BASE, pattern))):
        s = pc.one(f)
        s['name'] = os.path.basename(f).replace('.ait', '')
        out.append(s)
    return out

def agg(rows):
    t = defaultdict(float)
    for s in rows:
        for k in ('win', 'defeat', 'bow_atk', 'bow_mv', 'kitr', 'kits', 'bow_dead', 'cat_atk', 'cat_mv', 'cat_dead'):
            t[k] += s[k]
        t['bowTg'] += len(s['bow_tg']); t['catTg'] += len(s['cat_tg'])
        t['bowN'] += len(s['bow_sn']); t['catN'] += len(s['cat_sn'])
        t['near'] += s['near']
        t['epi'] += s['episodes']
        t['stuckMax'] = max(t['stuckMax'], s['stuckMax'])
    t['games'] = max(1, len(rows))
    t['bowAtkPer'] = t['bow_atk'] / max(1, t['bowN'])
    t['catAtkPer'] = t['cat_atk'] / max(1, t['catN'])
    t['bowTgPer'] = t['bowTg'] / max(1, t['bowN'])
    t['catTgPer'] = t['catTg'] / max(1, t['catN'])
    t['nearPct'] = 100.0 * t['near'] / max(1, t['kitr'])
    return t

def game_rows(rows, label):
    h = ['局', '胜负', '发现WS', '复合弓', '攻击令', '令/单位', '目标种类', '种/单位', '移动令', 'KIT-R', 'KIT-S', '窗口', 'stuck峰值', '被贴近%', '弓阵亡',
         '投石车', '攻击令', '令/单位', '种/单位', '移动令', '车阵亡']
    out = [f'<table><thead><tr>' + ''.join(f'<th>{x}</th>' for x in h) + '</tr></thead><tbody>']
    for s in rows:
        st = '<span class="win">胜</span>' if s['win'] else ('<span class="lose">负</span>' if s['defeat'] else '<span class="draw">平</span>')
        nb = max(1, len(s['bow_sn'])); nc = max(1, len(s['cat_sn']))
        npct = f"{100.0*s['near']/max(1,s['kitr']):.0f}"
        out.append('<tr>'
                   f"<td class='mono'>{s['name']}</td><td>{st}</td><td class='num mono'>{s['scoutF'] or '—'}</td>"
                   f"<td class='num'>{len(s['bow_sn'])}</td><td class='num'>{s['bow_atk']}</td><td class='num'>{s['bow_atk']/nb:.0f}</td>"
                   f"<td class='num'>{len(s['bow_tg'])}</td><td class='num'>{len(s['bow_tg'])/nb:.2f}</td>"
                   f"<td class='num'>{s['bow_mv']}</td><td class='num'>{s['kitr']}</td><td class='num'>{s['kits']}</td>"
                   f"<td class='num'>{s['episodes']}</td><td class='num'>{s['stuckMax']}</td>"
                   f"<td class='num'>{npct}</td><td class='num'>{s['bow_dead']}</td>"
                   f"<td class='num'>{len(s['cat_sn'])}</td><td class='num'>{s['cat_atk']}</td><td class='num'>{s['cat_atk']/nc:.0f}</td>"
                   f"<td class='num'>{len(s['cat_tg'])/nc:.1f}</td><td class='num'>{s['cat_mv']}</td><td class='num'>{s['cat_dead']}</td></tr>")
    out.append('</tbody></table>')
    return f'<h3>{label}</h3>' + ''.join(out)

def bar(v1, v2, label, unit='', lower_better=False):
    mx = max(v1, v2, 1)
    return f'''<div style="margin:12px 0">
<div style="font-size:12.5px;color:#9aa4b5;margin-bottom:4px">{label}{'（越低越好）' if lower_better else ''}</div>
<div style="display:flex;align-items:center;gap:8px;margin:3px 0"><span style="width:44px;font-size:11.5px;color:#9aa4b5">改前</span>
<div style="height:15px;width:{100.0*v1/mx:.1f}%;background:#4c8dff;border-radius:3px"></div><b class="num" style="font-size:12.5px">{v1:.1f}{unit}</b></div>
<div style="display:flex;align-items:center;gap:8px;margin:3px 0"><span style="width:44px;font-size:11.5px;color:#9aa4b5">改后</span>
<div style="height:15px;width:{100.0*v2/mx:.1f}%;background:#a371f7;border-radius:3px"></div><b class="num" style="font-size:12.5px">{v2:.1f}{unit}</b></div>
</div>'''

CSS = """:root{--bg:#0f1116;--panel:#171a22;--line:#272c38;--fg:#e8ecf3;--dim:#9aa4b5;--red:#e5484d;--green:#3fb950;--blue:#4c8dff;--amber:#d4a72c;--pur:#a371f7}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.7 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;padding:32px 20px 80px}
.wrap{max-width:1180px;margin:0 auto}
h1{font-size:26px;margin:0 0 6px}
h2{font-size:19px;margin:38px 0 12px;padding-left:10px;border-left:4px solid var(--blue)}
h3{font-size:16px;margin:22px 0 8px;color:#cbd5e6}
.sub{color:var(--dim);font-size:13px;margin-bottom:26px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:14px 0}
table{width:100%;border-collapse:collapse;font-size:13px;margin:10px 0}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}
th{color:var(--dim);font-weight:600;background:#1c2029}
td.num{font-variant-numeric:tabular-nums;text-align:right}
.win{color:var(--red);font-weight:700}
.lose{color:var(--green);font-weight:700}
.draw{color:var(--amber)}
code{background:#1c2029;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:12.5px;color:#a5d6ff}
pre{background:#12151c;border:1px solid var(--line);border-radius:8px;padding:12px 14px;overflow:auto;font-size:12px;line-height:1.55;color:#c9d3e3}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin:12px 0}
.kv div{background:#1c2029;border:1px solid var(--line);border-radius:9px;padding:10px 12px}
.kv b{display:block;font-size:22px;font-variant-numeric:tabular-nums}
.kv span{color:var(--dim);font-size:12px}
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:12px;border:1px solid}
.b-ok{color:var(--green);border-color:#2d5a37;background:#122417}
.b-bad{color:var(--red);border-color:#5a2d30;background:#241214}
.b-warn{color:var(--amber);border-color:#5a4a1d;background:#241f12}
.note{border-left:3px solid var(--amber);background:#1f1c12;padding:10px 14px;border-radius:0 8px 8px 0;margin:12px 0;font-size:13.5px}
.ok{border-left-color:var(--green);background:#121f15}
.bad{border-left-color:var(--red);background:#1f1214}
ul{padding-left:22px}li{margin:5px 0}
.mono{font-family:ui-monospace,Consolas,monospace;font-size:12px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:860px){.two{grid-template-columns:1fr}}"""

def main():
    before = collect('ln*.ait')
    after = collect('pu*.ait')
    if not after:
        print('!! 没有 pu*.ait'); return
    A, B = agg(before), agg(after)
    mid = agg(collect('kt*.ait')) if glob.glob(os.path.join(BASE, 'kt*.ait')) else None

    def pct(x, y):
        if x == 0: return '—'
        v = 100.0 * (y - x) / x
        return f"{v:+.0f}%"

    def row_html(n, a, b, lower_better=None, fmt='{:.1f}'):
        bg = ''
        if lower_better is True:
            bg = 'background:#121f15' if b < a else ('background:#1f1214' if b > a else '')
        elif lower_better is False:
            bg = 'background:#121f15' if b > a else ''
        style = f' style="{bg}"' if bg else ''
        return (f"<tr{style}><td>{n}</td><td class='num'>{fmt.format(a)}</td>"
                f"<td class='num'>{fmt.format(b)}</td><td class='num mono'>{pct(a,b)}</td></tr>")

    rows = [
        ('胜局', A['win'], B['win'], False, '{:.0f}'),
        ('负局（祭司被杀/TC 被毁，按先出现者判定）', A['defeat'], B['defeat'], True, '{:.0f}'),
        ('复合弓·攻击令总数', A['bow_atk'], B['bow_atk'], True, '{:.0f}'),
        ('复合弓·攻击令/单位', A['bowAtkPer'], B['bowAtkPer'], True, '{:.1f}'),
        ('复合弓·目标种类/单位（跳变度）', A['bowTgPer'], B['bowTgPer'], True, '{:.2f}'),
        ('复合弓·KIT-R 撤退令', A['kitr'], B['kitr'], False, '{:.0f}'),
        ('复合弓·撤退窗口数（>90 帧算新窗口）', A['epi'], B['epi'], False, '{:.0f}'),
        ('复合弓·stuck 峰值（"发令却没拉开"的连续次数，越低越好）', A['stuckMax'], B['stuckMax'], True, '{:.0f}'),
        ('复合弓·KIT-S（SHOOT 采样）', A['kits'], B['kits'], False, '{:.0f}'),
        ('复合弓·被贴近率 %（撤退令里 dK≤2 格占比）', A['nearPct'], B['nearPct'], True, '{:.0f}'),
        ('复合弓·阵亡', A['bow_dead'], B['bow_dead'], True, '{:.0f}'),
        ('投石车·单位数', A['catN'], B['catN'], None, '{:.0f}'),
        ('投石车·攻击令/单位', A['catAtkPer'], B['catAtkPer'], True, '{:.1f}'),
        ('投石车·目标种类/单位（改前投石车几乎不行动，口径仅供参考）', A['catTgPer'], B['catTgPer'], None, '{:.2f}'),
        ('投石车·移动令（后撤+逼近）', A['cat_mv'], B['cat_mv'], None, '{:.0f}'),
        ('投石车·阵亡', A['cat_dead'], B['cat_dead'], True, '{:.0f}'),
    ]
    ctable = ('<table><thead><tr><th>指标（反攻窗口 f≥33000）</th><th>改前 ln</th><th>改后 pu</th><th>变化</th></tr></thead><tbody>'
              + ''.join(row_html(*r) for r in rows) + '</tbody></table>')

    midblock = ''
    if mid:
        midblock = f"""
<div class="note bad"><b>中间版 kt 批次（8 局）暴露的第二个坑 —— 记录在此，因为它正是一条新铁律</b>
<ul>
<li>投石车移动令暴涨到 <b>{mid['cat_mv']:.0f}</b> 条（改前 {A['cat_mv']:.0f}）：<code>if (stuckTry&lt;=0 &amp;&amp; canReissue) {{…}} else {{ marchWaypoint()→HumanMove }}</code>
——那个 <code>else</code> 恰好只在"<b>已被节流</b>(canReissue=false)"时进入 ⇒ <b>每帧都发一条移动令</b>（kt4 投石车 91129 单局 9555 条，全部指向同一点）。</li>
<li>旧版本块在 <code>NowState != IDLE</code> 闸之后，只有 IDLE 才跑到，问题被长期掩盖；<b>本轮给投石车豁免该闸后立刻暴露</b>。</li>
<li>➜ 铁律 15：<b>「节流 else 分支」= 节流失效</b>。把 <code>if (节流) {{下令}} else {{换个方式下令}}</code> 写在一起，等于无条件下单；</li>
<li>➜ 铁律 16：<b>放开一道闸之前，先问"闸后面有哪些代码是被这道闸保护的"</b>（豁免 IDLE 闸 = 让每帧都跑的代码第一次真正每帧都跑）。</li>
</ul></div>"""

    kt_summary = (f"中间版 kt 批次：胜 {mid['win']:.0f}/8、复合弓目标跳变度 {mid['bowTgPer']:.2f} 种/单位、"
                  f"投石车移动令 {mid['cat_mv']:.0f}（刷屏）" if mid else '')

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>反攻期拉扯修复报告（2026-09-14）</title>
<style>{CSS}</style></head><body><div class="wrap">

<h1>反攻期拉扯：投石车 + 复合弓</h1>
<div class="sub">2026-09-14 · 改前 <b>ln</b>（{A['games']:.0f} 局） vs 改后 <b>pu</b>（{B['games']:.0f} 局）· 基线 3.0.7g · 25fps（45000 帧上限）· 统计窗口 = 反攻期 f≥33000 · {kt_summary}</div>

<div class="card">
<h3 style="margin-top:0">一句话结论</h3>
<p>「拉扯不成功」的真因不是"不会撤"，而是 <b>目标每帧跳变 ⇒ <code>HumanAction</code> 每帧重设攻击目标 ⇒ 引擎出手进度永远归零</b>（铁律 14 的又一例）。
改后：复合弓<b>目标跳变度 {A['bowTgPer']:.2f} → {B['bowTgPer']:.2f} 种/单位</b>、攻击令 {A['bowAtkPer']:.0f} → {B['bowAtkPer']:.0f} 条/单位、SHOOT 采样 {A['kits']:.0f} → {B['kits']:.0f} 条；
投石车用"目标粘滞 + 射程带站桩 + 贴身才撤"重建了 standoff 循环。</p>
</div>

<h2>1. 改前实测：为什么"拉扯不成功"</h2>
<div class="two">
<div class="card"><h3 style="margin-top:0">复合弓（ln7 · SN=91382，2574 帧）</h3>
<pre>f=33993 dK=7.7 stage=1 aged=0
f=34023 dK=7.7 stage=2 aged=30
f=34113 dK=6.0 stage=2 stuck=3
f=34311 dK=2.6 stage=2 stuck=9
f=34521 dK=1.8 stage=2   ← 被贴脸
f=36267 dK=7.9 stage=1 aged=0
· 882 条撤退令 / 仅 27 条 SHOOT 采样
· stage 恒 2（朝 TC 撤）：stuck&gt;0 后永久
  跳过"远离敌"档 = 棘轮
· dK 一路 7.9→1.8：净位移≈0，越撤越近</pre></div>
<div class="card"><h3 style="margin-top:0">投石车（ln1 · SN=91129）</h3>
<pre>f=35664 目标→方阵兵 91135
f=35667 目标→复合弓兵 91122
f=35668 目标→战车弓兵 91163
f=35671 目标→战车弓兵 91141
…共 586 条攻击令 / 13 个目标
· 每 1~3 帧换一次目标 ⇒ 引擎每帧记一条
  "开始向X攻击"，一炮未中
· 同时段撤退令 = 0 条
· 撤退线 11 格 &gt; 射程 10 格 ⇒ 永远进不到
  射程内；又 &lt; 目标选取范围 15 格 ⇒ 空转</pre></div>
</div>

<div class="two">
<div class="card ok" style="border-left:3px solid var(--green)"><h3 style="margin-top:0">改后 · 复合弓（pu2 · SN=91369）</h3>
<pre>f=34006 dK=6.8 stage=1 stuck=0  ← 窗口以"远离敌"档重开
f=34036 dK=6.1 stage=2 stuck=1
f=34432 dK=7.2 stage=1 stuck=0  ← 拉开了 → stuck 复位
f=34900 dK=8.3 stage=1 stuck=0  ← 撤到射程外（R=7）
f=35570 dK=8.2 stage=2 stuck=1
f=35750 dK=7.8 stage=2 stuck=1
f=35980 dK=6.0 stage=2 stuck=2
· dK 在 6.0~8.3 之间循环（R±1.5 带内）
· stuck 峰值 2（改前 9~25）
· 被贴近(dK≤2)占比 7%（改前 17%）</pre></div>
<div class="card ok" style="border-left:3px solid var(--green)"><h3 style="margin-top:0">改后 · 投石车（pu4 · SN=91128）</h3>
<pre>f=38026 HumanMove → 站位
f=38027 HumanAction → 投石车 91124
f=38056 HumanMove → 站位
f=38057 HumanAction → 投石车 91124
f=38146 HumanMove → 站位（微调）
f=38147 HumanAction → 投石车 91124
f=38326 HumanAction → 箭塔 11107（目标切换
       仅在旧目标消失/明显更近时）
· 单一粘滞目标 + 30 帧节奏站位/开火
· 该局投石车：攻击令 104 条 / 移动令 129 条
  （中间版 kt 曾达 9555 条移动令刷屏）</pre></div>
</div>

<div class="note bad"><b>三条根因</b>
<ul>
<li><b>① 每帧换目标</b>：<code>HumanAction(单位, 目标)</code> 是"设置攻击目标"，每帧重发 = 引擎每帧重设 = 出手进度恒 0（铁律 14）。</li>
<li><b>② 相位机被推进段截胡</b>：复合弓 dK∈(R, R+2] 时不落"接敌带"而落 <code>issueMarch</code>（目标=敌基地=朝前）⇒ 撤退令与推进令互相抵消；RETREAT 相位在 <code>!canReissue</code> 时同样掉进推进段。</li>
<li><b>③ 投石车块位置错了</b>：它在 <code>NowState != IDLE → continue</code> 闸<b>之后</b> ⇒ 开火(ATTACKING)时整段被跳过，<b>永远不会后撤</b>（弓兵相位机在闸之前，所以弓兵有拉扯、投石车没有）；再叠加"撤退线 &gt; 射程"，投石车注定 0 输出。</li>
</ul></div>

<h2>2. 改动清单</h2>
<table><thead><tr><th>#</th><th>位置</th><th>改动</th><th>作用</th></tr></thead><tbody>
<tr><td>1</td><td class="mono">UsrAI.h</td><td>新增 6 张表：<code>kitingTargetSN / kitingAtkFrame / catTargetSN / catTargetFrame / catAtkFrame / catRetreat</code></td><td>目标粘滞 + 指令节流 + 撤退迟滞的状态</td></tr>
<tr><td>2</td><td class="mono">kiting·选目标</td><td>先沿用粘滞目标（存活且 ≤20 格），仅"消失/跑远"才重选最近敌</td><td>消灭"每帧换目标"</td></tr>
<tr><td>3</td><td class="mono">kiting·进撤退</td><td>每次新开撤退窗口都 <code>kitingRetStuck=0</code></td><td>解除"一次撤不动就永久放弃远离敌档"的棘轮</td></tr>
<tr><td>4</td><td class="mono">SHOOT 段</td><td>站桩带 R → <b>R+2 格</b>；攻击令 20 帧节流；<b>不再发移动令</b></td><td>弓兵"停下来射"，而不是被推过目标贴脸</td></tr>
<tr><td>5</td><td class="mono">RETREAT 段</td><td>新增 <code>if (phase==1) continue;</code></td><td>撤退途中绝不被推进令推回去</td></tr>
<tr><td>6</td><td class="mono">IDLE 闸</td><td>对 <code>AT_STONE_THROWER</code> 豁免</td><td>投石车开火中也能执行 standoff/后撤</td></tr>
<tr><td>7</td><td class="mono">投石车块</td><td>目标粘滞（30 帧评估、需近 ≥2 格才换）+ 攻击令 20/30 帧节流 + 射程带 ≤10.5 格站桩 + 贴身 ≤7 格后撤、退到 14 格才停（迟滞）</td><td>投石车首次形成"打-撤-再打"闭环</td></tr>
<tr><td>8</td><td class="mono">投石车·推进段</td><td>把 <code>if (节流){{…}} else {{发令}}</code> 改为 <code>if (节流){{ 内部再分支 }}</code></td><td>修掉"被节流时反而每帧发令"（kt 批次暴露）</td></tr>
</tbody></table>
{midblock}

<h2>3. 改前 / 改后对比（反攻窗口 f≥33000）</h2>
{ctable}
<div class="note"><b>读表注意（避免误读）</b>
<ul>
<li><b>口径</b>：只有"反攻窗口 f≥33000 + flag=0（我方 AI 指令）"计入；胜负按 <code>VICTORY</code> 与 <code>DEFEAT:</code>（<b>带冒号</b>）谁先出现判定 —— 用 <code>'DEFEAT' in msg</code> 会把 <code>ALL WAVES DEFEATED!</code> 误判成失败，本轮踩过。</li>
<li><b>stuck 峰值是本次最干净的指标</b>：它衡量"发了撤退令却没拉开距离"的连续次数。改前 14~25（= 撤令持续被吞），改后 <b>8 局全部 = 2</b>。</li>
<li><b>投石车一栏不要看"目标种类"</b>：改前投石车大多处于"不动也不打"状态（每局 1 条攻击令、0~21 条移动令），目标种类自然少；改后它真的在作战，目标种类多属正常。真正可比的信号是<b>是否出现有节奏的站位/开火</b>（pu4：104 条攻击令 + 129 条移动令，节拍 30 帧），以及中间版 kt 的 9555 条刷屏已被消除。</li>
<li><b>胜率方差</b>：8 局/批在本项目历史上方差极大（12%~67% 都出现过），<b>5/8 vs 2/8 不能单独当作定论</b>；但"发现WS→收编"环节（5/6 vs 2/3）与 stuck 峰值这类机制指标是稳定的。</li>
</ul></div>

<div class="card"><h3 style="margin-top:0">关键指标条形对比</h3>
<div class="two">
<div>
{bar(A['bowTgPer'], B['bowTgPer'], '复合弓·目标种类/单位（跳变度）', lower_better=True)}
{bar(A['bowAtkPer'], B['bowAtkPer'], '复合弓·攻击令/单位', lower_better=True)}
{bar(A['kits'], B['kits'], '复合弓·KIT-S（SHOOT 采样）')}
{bar(A['stuckMax'], B['stuckMax'], '复合弓·stuck 峰值（撤不动的连续次数）', lower_better=True)}
{bar(A['nearPct'], B['nearPct'], '复合弓·被贴近率 %', lower_better=True)}
</div><div>
{bar(A['catAtkPer'], B['catAtkPer'], '投石车·攻击令/单位', lower_better=True)}
{bar(A['catTgPer'], B['catTgPer'], '投石车·目标种类/单位', lower_better=True)}
{bar(A['cat_mv'], B['cat_mv'], '投石车·移动令（后撤/逼近）')}
{bar(A['kitr'], B['kitr'], '复合弓·KIT-R 撤退令')}
</div></div></div>

<h2>4. 每局明细</h2>
{game_rows(before, f"改前 · ln 批次（{A['games']:.0f} 局）")}
{game_rows(after, f"改后 · pu 批次（{B['games']:.0f} 局）")}

<h2>5. 机制与观测口径</h2>
<div class="card">
<h3 style="margin-top:0">拉扯闭环（改后）</h3>
<pre>投石车 standoff 带：  威胁 ≥14 格 ──逼近──▶ ≤10.5 格 ──站桩开火──▶ 威胁 ≤7 格 ──后撤──▶ 14 格（迟滞）
复合弓 kiting 循环：  接敌带 dK≤R+2（只发攻击令，引擎自行走到 R 开火）
                      ── SHOOT 满 30 帧 或 敌进 0.9R ──▶ RETREAT（落点 = 目标 + 1.4R，真出射程）
                      ── dK≥R+1.5 或满 60 帧 ──▶ 回 SHOOT（kitingRetStuck 清零，重试"远离敌"档）</pre>
<p class="mono" style="color:#9aa4b5">日志口径：ait 第 4 列 flag，0=我方 UsrAI、1=敌方（已用"祭司 91166 感化武器厂 11099 归属 1→0"交叉验证）；frame/1500 = 游戏分钟。</p>
</div>

<h2>6. 校验与回滚</h2>
<ul>
<li>编译：<code>mingw32-make -f Makefile.Release -j4</code> → <b>0 error / 18 warning（UsrAI.cpp 口径，基线 19）</b>，trigraph 0；产物 <code>release/newAOE.exe</code> 2,154,496 B。</li>
<li>备份：<code>UsrAI.cpp.bak_20260914_pre_pullkite</code> / <code>UsrAI.h.bak_20260914_pre_pullkite</code>（回滚后务必抽查关键常量 —— 铁律：回滚会静默撤销其后的改动）。</li>
<li>脚本：<code>pu_verify.sh</code>（终版 8 局）、<code>kt_verify.sh</code>（中间版 8 局）、<code>pullkite_compare.py</code>（指标）、<code>pullkite_report.py</code>（本报告）、<code>kit_lint.py</code>（逐单位时间线）。</li>
</ul>

</div></body></html>
"""
    out = os.path.join(BASE, 'aoe3_pullkite_20260914.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print('written', out)
    for tag, X in (('before ln', A), ('after pu', B)):
        print(tag, dict(games=X['games'], win=X['win'], defeat=X['defeat'], bowAtkPer=round(X['bowAtkPer'], 1),
                        bowTgPer=round(X['bowTgPer'], 2), kitr=X['kitr'], kits=X['kits'],
                        nearPct=round(X['nearPct']), catN=X['catN'], catAtkPer=round(X['catAtkPer'], 1),
                        catTgPer=round(X['catTgPer'], 2), catMv=X['cat_mv']))

if __name__ == '__main__':
    main()
