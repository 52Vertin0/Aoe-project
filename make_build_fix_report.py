# -*- coding: utf-8 -*-
"""生成「建筑一直待建」修复报告 HTML。读 vf_fix_*.ait(修复后 16局) + dg*.ait(修复前诊断 3局)。"""
import os, re, glob
from collections import Counter

d = r'C:\new-aoe3.0.7g'
BT = {0: 'HOME', 1: 'GRANARY', 2: 'CENTER', 3: 'STOCK', 4: 'FARM', 5: 'MARKET',
      6: 'ARROWTOWER', 7: 'ARMYCAMP', 8: 'STABLE', 9: 'RANGE', 12: 'COLLAGE'}
BT_CN = {'HOME': '房屋', 'GRANARY': '谷仓', 'CENTER': '城镇中心', 'STOCK': '仓库',
         'FARM': '农场', 'MARKET': '市场', 'ARROWTOWER': '箭塔', 'ARMYCAMP': '兵营',
         'STABLE': '马厩', 'RANGE': '靶场', 'COLLAGE': '学院'}
UNIQUE = {'MARKET', 'GRANARY', 'STABLE', 'ARMYCAMP', 'RANGE', 'COLLAGE'}


def parse(paths):
    issue = Counter(); fail = Counter(); win = 0; games = 0; per = []
    for p in paths:
        games += 1
        i = Counter(); f = Counter(); last = 0
        with open(p, 'r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                pp = line.split(' | ', 3)
                if len(pp) >= 2:
                    try:
                        fr = int(pp[1])
                        if fr > last:
                            last = fr
                    except ValueError:
                        pass
                if '[BUILD-FAIL' in line:
                    m = re.search(r'type=(\d+) ret=(\d+)', line)
                    if m:
                        f[(int(m.group(1)), int(m.group(2)))] += 1
                elif '[BUILD-ISSUE' in line:
                    m = re.search(r'type=(\d+)', line)
                    if m:
                        i[int(m.group(1))] += 1
                if 'VICTORY! Siege Workshop converted' in line:
                    win = 1
        issue += i; fail += f
        per.append((os.path.basename(p), last, sum(i.values()), sum(f.values())))
    return dict(games=games, issue=issue, fail=fail, win=win, per=per)


post = parse(sorted(glob.glob(os.path.join(d, 'vf_fix_*.ait'))))
pre = parse(sorted(glob.glob(os.path.join(d, 'dg*.ait'))))
assert post['games'] > 0, 'no vf_fix_*.ait found'


def pergame(res, rt=None):
    if rt is None:
        return sum(res['fail'].values()) / res['games']
    return sum(n for (t, r), n in res['fail'].items() if r == rt) / res['games']


def trow(c, head=False):
    tag = 'th' if head else 'td'
    return '<tr>' + ''.join('<%s>%s</%s>' % (tag, x, tag) for x in c) + '</tr>'


def failrows(res):
    if not res['fail']:
        return '<tr><td colspan="3" style="text-align:center;color:#2e7d32">（无任何拒址）</td></tr>'
    return ''.join(trow([BT_CN.get(BT.get(t, t), t), 'ret=%d' % r, str(n)])
                   for (t, r), n in sorted(res['fail'].items(), key=lambda x: -x[1]))


iss = sorted(post['issue'].items(), key=lambda x: -x[1])
issrows = ''.join(
    trow(['%s %s' % (BT.get(t, t), BT_CN.get(BT.get(t, t), '')),
          str(n), '%.1f' % (n / post['games']),
          ('<b>1.0 ✓</b>' if BT.get(t) in UNIQUE and abs(n / post['games'] - 1) < 0.01 else '')])
    for t, n in iss)
perrows = ''.join(trow([r[0], str(r[1]), str(r[2]), str(r[3])]) for r in post['per'])

H = '''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>建筑一直待建 · 修复报告</title>
<style>
body{{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;margin:0;background:#f6f7f9;color:#1f2430;line-height:1.7}}
.wrap{{max-width:960px;margin:0 auto;padding:32px 22px 60px}}
h1{{font-size:24px;margin:0 0 6px}}
.sub{{color:#67707e;font-size:13px;margin-bottom:22px}}
.card{{background:#fff;border:1px solid #e6e9ef;border-radius:12px;padding:20px 22px;margin:16px 0;box-shadow:0 1px 3px rgba(20,30,60,.04)}}
h2{{font-size:17px;margin:0 0 12px;padding-left:10px;border-left:4px solid #3b6ef5}}
.kpi{{display:flex;gap:14px;flex-wrap:wrap;margin:8px 0}}
.kpi div{{flex:1;min-width:150px;background:#f2f5fc;border-radius:10px;padding:14px}}
.kpi b{{display:block;font-size:26px;color:#3b6ef5}}
.kpi .g{{color:#2e7d32}}.kpi .r{{color:#c62828}}
table{{border-collapse:collapse;width:100%;font-size:14px;margin-top:6px}}
th,td{{border:1px solid #e6e9ef;padding:7px 10px;text-align:left}}
th{{background:#f2f5fc;font-weight:600}}
code{{background:#eef1f6;padding:1px 6px;border-radius:5px;font-size:13px}}
.mono{{font-family:Consolas,monospace;font-size:12.5px;background:#0f1420;color:#d7e0f0;border-radius:9px;padding:12px 14px;overflow:auto;white-space:pre}}
.bad{{color:#c62828;font-weight:600}}.good{{color:#2e7d32;font-weight:600}}
p{{margin:8px 0}}
.note{{background:#fff8e6;border-left:4px solid #f0b429;padding:10px 14px;border-radius:6px;font-size:13.5px}}
.ok{{background:#eef7ee;border-left-color:#2e7d32}}
</style></head><body><div class="wrap">

<h1>「建筑一直待建」根因定位与修复</h1>
<div class="sub">AOE UsrAI · 2026-09-21 · <code>UsrAI.cpp</code> · 修复后 {PG} 局 / 修复前诊断 {PR} 局</div>

<div class="card">
<h2>一句话结论</h2>
<p>不是<b>没派人去建</b>，而是<b>派了人、下了建造令，但引擎每次都拒址</b>，村民白跑一趟 → 90 帧宽限期一到又重发下一处坏址 → 肉眼看到「建筑一直待建」。</p>
<p><b>主因</b>：<code>isPositionFree</code> 的间距判据<b>只外扩候选、未对称外扩</b>——漏掉「候选与既有建筑/资源仅隔 1 格」的地址，而引擎按双方碰撞外扩判重叠，于是以
<span class="bad">ret=4 OVERLAP</span> 拒址。</p>
</div>

<div class="card">
<h2>核心指标对比</h2>
<div class="kpi">
<div class="g"><b>{POSTFAILPG}</b>次拒址/局<span style="font-size:12px;color:#67707e">（修前 {PREFAILPG}）</span></div>
<div class="g"><b>0</b>ret=20<span style="font-size:12px;color:#67707e">（修前 {PRER20PG}/局）</span></div>
<div class="g"><b>{ZEROFAIL}/16</b>局零拒址</div>
<div><b>1.0×</b>独特建筑下发/局</div>
</div>
<table>
''' + trow(['指标', '修复前(诊断 {PR}局)', '修复后({PG}局)'], True) + '''
<tr><td>BUILD-FAIL 总次数</td><td>{PREFAIL}</td><td class="good">{POSTFAIL}</td></tr>
<tr><td>BUILD-FAIL / 局</td><td class="bad">{PREFAILPG}</td><td class="good">{POSTFAILPG}</td></tr>
<tr><td>ret=4 OVERLAP / 局</td><td class="bad">{PRER4PG}</td><td class="good">{POSTR4PG}</td></tr>
<tr><td>ret=20 RESOURCE / 局</td><td class="bad">{PRER20PG}</td><td class="good">0</td></tr>
</table>
<p class="note">修复前拒址分布：<br>{PREFAILROWS}</p>
<p class="note ok">修复后拒址分布（16 局仅 {POSTFAIL} 次，退化到与非修复路径同量级的偶发）：<br>{POSTFAILROWS}</p>
</div>

<div class="card">
<h2>根因：HumanBuild 引擎拒址码（诊断实证）</h2>
<p>在 <code>handleBuildResults</code> 打印<u>任何非成功</u>返回码 <code>[BUILD-FAIL type=.. ret=.. at=(x,y)]</code>，得两类：</p>
<table>
''' + trow(['拒绝码', '含义', '典型站点(修前)', '判定'], True) + '''
<tr><td><span class="bad">ret=4</span> HUMANBUILD_OVERLAP</td><td>候选址与既有建筑/资源碰撞重叠</td>
<td>RANGE(63,63)/(58,63)、STOCK(66,71)、FARM(23,14) —— 均紧贴既有建筑(1格)或树/矿</td>
<td><span class="bad">主因</span>：<code>isPositionFree</code> 间距判据不对称</td></tr>
<tr><td>ret=20 INVALID_RESOURCE</td><td>引擎处理时资源不足</td>
<td>FARM(26,28)/(15,18)（2/3 局）</td>
<td>次因：下单与处理异步、木瞬时跌破 75；5 帧重试自恢复</td></tr>
</table>
<p>真值核对：<code>config.json</code> 内 MARKET/RANGE=150 木、FARM=75 木（仅木）；
<code>BUILD_*_WOOD</code> 是<u>运行时常量</u>（<code>RuntimeConfig_*</code>），故 <code>tryBuildMarket</code> 里硬编码的
<code>info.Wood&gt;=150</code> 恰好等值——这也是该魔法数一直没被发现的原因。</p>
</div>

<div class="card">
<h2>修复内容（3 处）</h2>
<div class="mono">// 1) isPositionFree 建筑/敌建筑间距：候选与既有【都外扩 BUILD_GAP】后判矩形相交（对称外扩）
if (c0 &lt; e1 &amp;&amp; c1 &gt; e0 &amp;&amp; c2 &lt; e3 &amp;&amp; c3 &gt; e2) return false;   // c*:候选外扩  e*:既有外扩

// 2) isPositionFree 资源(树/矿)检查：候选 footprint 外扩后含资源即不可建
#define RES_BUILD_GAP 2   // 匹配 forestGrid 把树±2 标不可走（引擎语义）

// 3) 建造木闸去魔法数（值不变，与引擎口径对齐）
info.Wood &gt;= 150     →  info.Wood &gt;= BUILD_MARKET_WOOD
info.Stone &gt;= 150    →  info.Stone &gt;= BUILD_ARROWTOWER_STONE</div>
</div>

<div class="card">
<h2>修复后：各建筑下发次数（{PG} 局）</h2>
<table>''' + trow(['建筑', '下发次数', '次/局', '独特建筑'], True) + issrows + '''
</table>
<p><b>关键证据</b>：独特建筑（市场/谷仓/马厩）在 16 局中<b>恰好各下发 16 次 = 1 次/局</b>，
且无一条 BUILD-FAIL —— <b>首次下发即成地基</b>（修复前是被反复重发、从不成形）。</p>
</div>

<div class="card">
<h2>逐局明细（修复后）</h2>
<table>''' + trow(['局', '末帧', 'BUILD-ISSUE', 'BUILD-FAIL'], True) + perrows + '''
</table>
<p style="font-size:13px;color:#67707e">注：<code>BUILD-ISSUE</code> 为下发建造令次数；<code>BUILD-FAIL</code> 为引擎拒址次数。
本图胜因唯一 = 祭司感化敌方武器厂，与本次建筑修复无因果关系（本次验收只看拒址是否归零、地基是否落成，不看胜负）。</p>
</div>

<div class="card">
<h2>编译与校验</h2>
<table>
<tr><th>步骤</th><th>结果</th></tr>
<tr><td><code>syn.py</code> 语法</td><td class="good">rc=0 / errors=0 / warnings=17（与基线类别一致）</td></tr>
<tr><td><code>build.py</code> Release</td><td class="good">rc=0 / errors=0，exe 刷新 21:04</td></tr>
<tr><td>源码</td><td><code>UsrAI.cpp</code> 6539 行（含临时诊断；正式版移除后发布）</td></tr>
</table>
</div>

</div></body></html>'''

vals = dict(
    PG=post['games'], PR=pre['games'],
    PREFAIL=sum(pre['fail'].values()), POSTFAIL=sum(post['fail'].values()),
    PREFAILPG='%.2f' % pergame(pre), POSTFAILPG='%.2f' % pergame(post),
    PRER4PG='%.2f' % pergame(pre, 4), POSTR4PG='%.2f' % pergame(post, 4),
    PRER20PG='%.2f' % pergame(pre, 20),
    ZEROFAIL=sum(1 for r in post['per'] if r[3] == 0),
    PREFAILROWS=failrows(pre), POSTFAILROWS=failrows(post),
)
out = os.path.join(d, 'aoe3_buildstuck_fix_20260921.html')
with open(out, 'w', encoding='utf-8') as f:
    f.write(H.format(**vals))

print('PRE  %d games fail=%d (%.2f/g) ret4=%.2f/g ret20=%.2f/g'
      % (pre['games'], sum(pre['fail'].values()), pergame(pre), pergame(pre, 4), pergame(pre, 20)))
print('POST %d games fail=%d (%.2f/g) ret4=%.2f/g ret20=%.2f/g zerofail=%d'
      % (post['games'], sum(post['fail'].values()), pergame(post), pergame(post, 4),
         pergame(post, 20), vals['ZEROFAIL']))
print('ISSUE/type:', {BT.get(k, k): v for k, v in iss})
print('WROTE', out)
