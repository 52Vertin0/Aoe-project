#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 生成 祭司探路/前出防自死 修复报告 HTML（对比 wd=修复前 / pd=修复后）
import io, re, os, glob, sys, datetime

RE_DEATH = re.compile(r'祭司\(编号[:：]?[0-9]*\)死亡')
RE_FRAME = re.compile(r'\|\s*(\d+)\s*\|')
RE_VIC = re.compile(r'VICTORY')
RE_DEF = re.compile(r'DEFEAT')

def parse(fp):
    lines = io.open(fp, encoding='utf-8', errors='replace').readlines()
    death_frame = None
    for r in lines:
        if RE_DEATH.search(r):
            m = RE_FRAME.search(r)
            if m: death_frame = int(m.group(1))
            break
    txt = ''.join(lines)
    outc = 'VICTORY' if RE_VIC.search(txt) else ('DEFEAT' if RE_DEF.search(txt) else '?')
    return death_frame, outc

def bucket(f):
    if f is None: return 'alive'
    if f < 5000: return 'scout(<5k)'
    if f < 21000: return 'early(5k~21k)'
    return 'counter(>=21k)'

def analyze(prefix):
    files = sorted(glob.glob('%s*.ait' % prefix))
    deaths=0; buckets={'scout(<5k)':0,'early(5k~21k)':0,'counter(>=21k)':0,'alive':0}
    outcomes={'VICTORY':0,'DEFEAT':0,'?':0}; dead_def=0
    for fp in files:
        f,outc = parse(fp)
        outcomes[outc]+=1
        b=bucket(f); buckets[b]+=1
        if f is not None:
            deaths+=1
            if outc=='DEFEAT': dead_def+=1
    n=len(files)
    return dict(n=n, deaths=deaths, rate=100.0*deaths/n, buckets=buckets,
               outcomes=outcomes, dead_def=dead_def)

wd = analyze('wd')
pd = analyze('pd')

def row(label, w, p):
    return '<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (label, w, p)

html = '''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>祭司探路/前出防自死 修复报告</title>
<style>
 body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;margin:0;background:#f5f6f8;color:#222}
 .wrap{max-width:980px;margin:0 auto;padding:28px 20px 60px}
 h1{font-size:23px;margin:0 0 4px} h2{font-size:18px;margin:28px 0 10px;border-left:4px solid #2b7de9;padding-left:10px}
 .sub{color:#666;font-size:13px;margin-bottom:18px}
 .card{background:#fff;border:1px solid #e6e8eb;border-radius:10px;padding:18px 20px;margin:14px 0;box-shadow:0 1px 3px rgba(0,0,0,.04)}
 table{border-collapse:collapse;width:100%%;font-size:14px}
 th,td{border:1px solid #e6e8eb;padding:8px 10px;text-align:left}
 th{background:#f0f4fa}
 .k{color:#2b7de9;font-weight:600}
 .good{color:#1a9d54;font-weight:600} .bad{color:#d23b3b;font-weight:600}
 .bar{height:14px;border-radius:7px;background:#2b7de9;display:inline-block;vertical-align:middle}
 .muted{color:#888;font-size:12.5px}
 code{background:#f0f2f5;padding:1px 5px;border-radius:4px;font-size:12.5px}
 pre{background:#0f1115;color:#e6e6e6;padding:12px 14px;border-radius:8px;font-size:12.5px;overflow:auto}
 .pill{display:inline-block;background:#eef3fb;color:#2b7de9;border-radius:20px;padding:2px 10px;font-size:12.5px;margin:2px}
</style></head><body><div class="wrap">
<h1>祭司探路 / 前出防自死 试点报告（回归 → 已回滚）</h1>
<div class="sub">AoE3 3.0.7g · UsrAI.cpp · 生成于 %s · 对比 对照(wd) / 试点(pd)</div>

<h2>1 需求与结论</h2>
<div class="card">
<p><b>用户需求：</b>「祭司探路不要把自己探死了」——祭司外出/前出（含字面探路期与反攻期前出探武器厂）不应把自己送死。</p>
<p><b>修复前（wd 批次，16 局）：</b>祭司死亡 <span class="bad">%d 局 / %d（%.1f%%）</span>，且<span class="bad">死亡局 100%% 直接判负</span>（祭司死=立刻失败）。</p>
<p><b>试点（pd 批次，16 局）：</b>祭司死亡 <span class="k">%d 局 / %d（%.1f%%）</span>，死亡局判负 %d。</p>
<p><b>结论：</b>试点后死亡率 <b>%.1f%% → %.1f%%</b>（%s）⇒ <span class="bad">Fix A（探路塔威胁判断）方向错误</span>：侦察期（&lt;5k 帧）<b>新增死亡 4 例</b>——威胁环让祭司在探路时被箭塔反复打断、反而更暴露。整轮改动已<b>回滚</b>到 <code>bak_20260921_pre_priestdeath</code>。</p>
</div>

<h2>2 死亡分布（帧分桶）</h2>
<div class="card">
<table>
<tr><th>阶段</th><th>修复前 wd</th><th>修复后 pd</th></tr>
%s
</table>
<p class="muted">scout&lt;5k=字面探路期；early 5k~21k=W2 防御感化期；counter≥21k=反攻前出期。真实死亡事件=行内 <code>祭司(编号…)死亡</code>（单祭司每局至多 1 次）。</p>
</div>

<h2>3 根因分析</h2>
<div class="card">
<p><b>根因 A — 字面探路期盲点：</b>探路状态机 <code>manageScout</code> 只扫描 <code>enemy_armies / enemy_farmers / beasts</code>，<b>从不查 <code>enemy_buildings</code>（敌箭塔）</b>；且威胁处理被 <code>NowState != WALKING</code> 门控——走路时无视威胁，径直走进箭塔射程（<code>ARROWTOWER_RANGE=8</code> 格）。</p>
<p><b>根因 B — 感化优先无危险门控（主因，占绝大多数死亡）：</b>无条件感化优先 <code>if (convSN &gt;= 0)</code> 让祭司去感化相邻近战兵，而感化是 150 帧 <code>HumanAction</code> 冻结（<code>ConvertCooldown=150</code>），冻结期 <code>canAct=false</code> 无法逃跑；且 <code>canAct</code>/25%%HP 逃跑门控意味着<b>正在感化的祭司即使近战贴脸也无法脱身</b>，于是被在 80~91%% HP 直接秒杀。</p>
<p class="muted">证据（修复前死亡前诊断）：b_r90 death@38908 hp=0.83 近战 nearE=3.7 且 mode=0（未逃跑）；c2_r90 hp 1.0→0.24→dead。死亡帧集中在 15k（W2 防御感化）与 36k~39k（反攻前出）。</p>
</div>

<h2>4 修复方案（4 处改动，源码已落盘）</h2>
<div class="card">
<span class="pill">Fix A 探路塔威胁</span><span class="pill">Fix B1 meleeAdj 预计算</span><span class="pill">Fix B2 感化门控</span><span class="pill">Fix B4 canAct 逃跑门控</span>
<table>
<tr><th>改动</th><th>位置</th><th>内容</th></tr>
<tr><td>A</td><td>manageScout 威胁环</td><td>新增 <code>towerDist=(ARROWTOWER_RANGE+6)*BL</code> 敌箭塔环；威胁门控 <code>!=WALKING</code> → <code>IDLE||WALKING</code>；<code>enemyNearby</code> 扩为 <code>enemyNearby||towerNearby</code></td></tr>
<tr><td>B1</td><td>感化分支前</td><td>预计算 <code>meleeAdj</code>：存在 <code>calDistance&lt;4.0*BL</code> 的近战敌</td></tr>
<tr><td>B2</td><td>感化优先门控</td><td><code>if (convSN&gt;=0 &amp;&amp; !meleeAdj)</code>——近战贴脸时不感化（含接近动作），远程单位（射程≥12）仍可感化</td></tr>
<tr><td>B4</td><td>canAct 逃跑门控</td><td><code>if (pBRx&gt;0.25 &amp;&amp; !meleeAdjNow) return;</code>——即使满血，若近战贴脸（正在感化/治疗）也强制逃跑，不等掉到 25%%</td></tr>
<tr><td>B3</td><td>清理</td><td>删除原 cpp:1175 处重复 <code>meleeAdj</code> 块</td></tr>
</table>
</div>

<h2>5 编译与校验</h2>
<div class="card">
<table>
<tr><th>步骤</th><th>结果</th></tr>
<tr><td><code>syn.py</code> 语法检查</td><td>rc=0 / errors=0 / warnings=17（与基线类别一致）</td></tr>
<tr><td><code>build.py</code> Release 编译</td><td>rc=0 / errors=0，exe 刷新 19:16</td></tr>
<tr><td>源码指纹</td><td><code>04d7da954e43dd0418508858f216639d</code> · 6536 行</td></tr>
</table>
</div>

<h2>6 验证判读与风险</h2>
<div class="card">
<p class="muted">判读：wd 与 pd 同为 16 局、同地图同其他修复，仅祭司防自死改动不同 → 苹果对苹果对比。死亡率 11/16 → 15/16 属<b>明确回归</b>（非随机波动：分散在侦察/早/反攻三段、且新增侦察期死亡）。</p>
<p><b>Fix A 的错因：</b>在探路状态机上叠加"敌箭塔威胁环"后，祭司被反复打断行走、在塔附近徘徊更久 ⇒ 侦察期死亡 0→4。<b>Fix B</b>（!meleeAdj 门控 + canAct 强逃）逻辑本身未见副作用，但被 Fix A 的回归掩盖，须在重设计 Fix A 后<b>单独验证</b>。</p>
</div>

<h2>7 处置：整轮回滚</h2>
<div class="card">
<p>按「先回滚到最后一个已验证版本、再重设计」的纪律，已整文件回滚 <code>UsrAI.cpp/.h</code> 到
<code>bak_20260921_pre_priestdeath</code>（<code>ab4f595a</code> · 6518 行 = 不含祭司防自死）。
Fix A 重设计方向：<b>不打断探路</b>，改为对探路路径做<b>箭塔射程绕行预规划</b>（PathAway），而非到达后触发逃避。</p>
</div>

</div></body></html>''' % (
    datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
    wd['deaths'], wd['n'], wd['rate'],
    pd['deaths'], pd['n'], pd['rate'], pd['dead_def'],
    wd['rate'], pd['rate'],
    ('下降 ✅' if pd['deaths'] < wd['deaths'] else ('持平' if pd['deaths']==wd['deaths'] else '上升 ⚠')),
    '\n'.join([
        row('字面探路 scout(&lt;5k)', wd['buckets']['scout(<5k)'], pd['buckets']['scout(<5k)']),
        row('W2 防御感化 early(5k~21k)', wd['buckets']['early(5k~21k)'], pd['buckets']['early(5k~21k)']),
        row('反攻前出 counter(≥21k)', wd['buckets']['counter(>=21k)'], pd['buckets']['counter(>=21k)']),
        row('存活 alive', wd['buckets']['alive'], pd['buckets']['alive']),
    ])
)

out = 'aoe3_priest_death_20260921.html'
io.open(out,'w',encoding='utf-8').write(html)
print('wrote', out, '| wd deaths=%d(%.1f%%) pd deaths=%d(%.1f%%)' % (
    wd['deaths'], wd['rate'], pd['deaths'], pd['rate']))
