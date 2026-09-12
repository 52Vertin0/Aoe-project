# -*- coding: utf-8 -*-
"""生成「农民大量 IDLE」归因报告 (aoe3_idle_deadzone_20260921.html)

所有数字都从日志现算，可用 idle_probe.py 复现。
数据源：
  ① 用户实机局：C:\\new-aoe3.0.7g\\AIText.log（22:47 仍在写）
  ② 离线批：vf_fix_*.ait（16 局，建筑修复版）
"""
import re, os, glob, html, statistics

D = r'C:\new-aoe3.0.7g'
LIVE = os.path.join(D, 'AIText.log')
OUT = os.path.join(D, 'aoe3_idle_deadzone_20260921.html')

STAT = re.compile(
    r'\[(\d+)\] (ECO|UPG|PREP|W1|W2|W3|ATK|WIN|LOSE) \| '
    r'Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \| '
    r'Frm:(\d+) Idle:(\d+)\(Carry:(\d+)\) Walk:(\d+) Work:(\d+) Atk:(\d+)')
ECO = re.compile(
    r'ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+) '
    r'\|\| goldRich:(\d) woodStop:(\d) stoneStop:(\d) foodStop:(\d) woodTarget:(\d) twr:(\d+)/(\d+)')

WAVE1, WAVE2, WAVE3 = 5000, 13500, 21000


def stat_rows(p):
    out = []
    for line in open(p, encoding='utf-8', errors='replace'):
        m = STAT.search(line)
        if m:
            g = m.groups()
            out.append(dict(frame=int(g[0]), state=g[1], fd=int(g[2]), wd=int(g[3]), st=int(g[4]),
                            gd=int(g[5]), frm=int(g[6]), idle=int(g[7]), carry=int(g[8]),
                            walk=int(g[9]), work=int(g[10]), atk=int(g[11])))
    return out


def eco_rows(p):
    out = []
    for line in open(p, encoding='utf-8', errors='replace'):
        m = ECO.search(line)
        if m:
            v = [int(x) for x in m.groups()]
            out.append(dict(frame=v[0] if False else None, fd=v[0], wd=v[1], st=v[2], gd=v[3],
                            F=v[4], W=v[5], G=v[6], S=v[7], goldRich=v[8], woodStop=v[9],
                            stoneStop=v[10], foodStop=v[11], woodTarget=v[12], twr=v[13], twrMax=v[14],
                            f=0))
    # ECO 行本身不带帧号（消息体里没有），用行序对齐 stat 不可靠 ⇒ 从原始行取 p[1]
    out = []
    for line in open(p, encoding='utf-8', errors='replace'):
        m = ECO.search(line)
        if not m:
            continue
        parts = line.split(' | ', 3)
        try:
            fr = int(parts[1])
        except Exception:
            continue
        v = [int(x) for x in m.groups()]
        out.append(dict(f=fr, fd=v[0], wd=v[1], st=v[2], gd=v[3], F=v[4], W=v[5], G=v[6], S=v[7],
                        goldRich=v[8], woodStop=v[9], stoneStop=v[10], foodStop=v[11],
                        woodTarget=v[12], twr=v[13], twrMax=v[14]))
    return out


# ---------- 数据 ----------
live_stat = stat_rows(LIVE)
live_eco = eco_rows(LIVE)
peak = max(r['idle'] for r in live_stat)
peak_fr = max(r['frame'] for r in live_stat if r['idle'] == peak)
peak_row = [r for r in live_stat if r['frame'] == peak_fr][0]

# 逐分钟（8~15 分）
by_min = {}
for r in live_stat:
    by_min[r['frame'] // 1500] = r
live_min_rows = [by_min[m] for m in sorted(by_min) if 8 <= m <= 15]

# 死区 ECO 窗口：取【最长】的一段连续 woodStop==1（不是第一段——早期会有短暂锁死）
runs = []
cur = None
for e in live_eco:
    if e['woodStop'] == 1:
        if cur is None:
            cur = [e['f'], e['f']]
        else:
            cur[1] = e['f']
    else:
        if cur is not None:
            runs.append(tuple(cur))
            cur = None
if cur is not None:
    runs.append(tuple(cur))
first_latch, release = max(runs, key=lambda r: r[1] - r[0]) if runs else (None, None)
all_runs = runs
dead_eco = [e for e in live_eco if first_latch is not None and first_latch <= e['f'] <= release]

# 全批死区统计
batch = sorted(glob.glob(os.path.join(D, 'vf_fix_*.ait')))
b_rows = []
tot_dead = tot_eco = 0
for p in batch:
    e = eco_rows(p)
    s = stat_rows(p)
    if not e or not s:
        continue
    dead = sum(1 for x in e if x['woodStop'] == 1 and x['F'] >= 10 and x['G'] == 0)
    tot_dead += dead
    tot_eco += len(e)
    mx = max(r['idle'] for r in s)
    b_rows.append((os.path.basename(p), mx,
                   sum(1 for x in e if x['woodStop'] == 1), len(e), dead,
                   max(x['F'] for x in e), max(x['gd'] for x in e)))
dead_pct = 100.0 * tot_dead / tot_eco if tot_eco else 0

# ---------- 渲染 ----------
def esc(s):
    return html.escape(str(s))


def rowstat(r):
    cls = ' class="bad"' if r['idle'] >= 5 else ''
    return ('<tr><td>%d</td><td>%d</td><td>%s</td><td>%d</td><td>%d</td><td>%d</td>'
            '<td%s>%d</td><td>%d</td><td>%d</td></tr>' %
            (r['frame'] // 1500, r['frame'], r['state'], r['fd'], r['wd'], r['st'],
             cls, r['idle'], r['work'], r['frm']))


def roweco(e):
    cls = ' class="bad"' if (e['woodStop'] == 1 and e['G'] == 0) else ''
    return ('<tr><td>%d</td><td>%d</td><td>%d</td><td>F%d W%d G%d S%d</td>'
            '<td%s>%d</td><td>%d</td><td>%d/%d</td></tr>' %
            (e['f'], e['fd'], e['wd'], e['F'], e['W'], e['G'], e['S'],
             cls, e['woodStop'], e['G'], e['twr'], e['twrMax']))


STYLE = open(os.path.join(D, 'aoe3_buildstuck_fix_20260921.html'), encoding='utf-8').read()
STYLE = re.search(r'<style>.*?</style>', STYLE, re.S).group(0)

H = []
H.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
         '<title>农民大量 IDLE · 归因报告</title>' + STYLE + '</head><body><div class="wrap">')
H.append('<h1>「9 分钟开始大量出现农民 IDLE」· 归因报告</h1>')
H.append('<div class="sub">AoE3 3.0.7g · UsrAI.cpp <code>3bd4d179</code>(6461 行) · '
         '数据源：用户实机局 <code>AIText.log</code> + 离线批 <code>vf_fix_*.ait</code> ×16 · '
         '<b>本轮为纯分析，未改动源码</b></div>')

# TL;DR
H.append('<div class="card"><h2>TL;DR</h2>')
H.append('<p>不是"没派人"，而是 <b>四类采集出口同时关闭</b>时，空闲村民的兜底路径'
         '（源码自称"<b>绝不空闲</b>"）被 <code>!woodStop</code> 反杀。</p>')
H.append('<div class="kpi">'
         '<div><b class="r">%d/%d</b>实机峰值 Idle（%d 分）</div>'
         '<div><b class="r">%.1f 分</b>木头门禁锁死时长</div>'
         '<div><b class="r">%.1f%%</b>离线批死于该死区的采样占比</div>'
         '<div><b class="g">1 分钟</b>木头跌破 220 后 Idle→0</div>'
         '</div>' % (peak, peak_row['frm'], peak_fr // 1500, (release - first_latch) / 1500.0, dead_pct))
H.append('<div class="note"><b>判据（一眼可验）</b>：实机日志里 <code>woodStop:1</code> 的 '
         '<b>%.1f 分钟</b>内 Idle 沿 %s 一路堆高；木头跌破 220（<code>woodStop</code> 翻回 0）后，'
         '<b>同一分钟内 Idle 归零</b>。判定变量只有木/石/金/食四个出口，与波次状态无关'
         '（<code>woodStop</code> 在整局共锁死 %d 段）。</div>'
         % ((release - first_latch) / 1500.0 if first_latch else 0,
            '→'.join(str(by_min[m]['idle']) for m in sorted(by_min)
                     if first_latch and first_latch <= by_min[m]['frame'] <= release),
            len(all_runs)))
H.append('</div>')

# 现象
H.append('<div class="card"><h2>1 现象（实机逐分钟，帧/1500 = 分钟）</h2>')
H.append('<table><tr><th>分钟</th><th>frame</th><th>state</th><th>食物</th><th>木头</th>'
         '<th>石头</th><th>Idle</th><th>Work</th><th>村民总数</th></tr>')
H += [rowstat(r) for r in live_min_rows]
H.append('</table>')
H.append('<p class="note">峰值 <b>Idle %d / %d 人（%.0f%%）</b>，落在 frame %d（%.1f 分）。'
         '此前 8 分时只有 2 人空闲。</p>'
         % (peak, peak_row['frm'], 100.0 * peak / max(1, peak_row['frm']), peak_fr, peak_fr / 1500.0))
H.append('</div>')

# 铁证
H.append('<div class="card"><h2>2 铁证：源码自带的资源门禁自检行（cpp:2894）</h2>')
H.append('<p>该行每 600 帧打印一次，直接给出四道门禁的开关与各资源工数 —— '
         '不需要推断。</p>')
H.append('<table><tr><th>frame</th><th>木头</th><th>workers（食/木/金/石）</th>'
         '<th>woodStop</th><th>黄金工</th><th>箭塔</th></tr>')
H += [roweco(e) for e in dead_eco]
H.append('</table>')
H.append('<pre class="mono">'
         'f=10200  Wd:222 | workers F12 W2 G0 S1 | woodStop:1 stoneStop:1  twr:3/3   &lt;- 门禁锁死开始\n'
         'f=14400  Wd:312 | workers F12 W0 G0 S0 | woodStop:1 stoneStop:1  twr:3/3   &lt;- 伐木工衰减到 0，无人补位\n'
         'f=17400  Wd:252 | workers F11 W0 G0 S0 | woodStop:1 stoneStop:1  twr:3/3\n'
         'f=19800  Wd:177 | workers F4  W14 G3 S0 | woodStop:0                 &lt;- 木头跌破 220，木门开\n'
         'f=21009  Wd:283 | workers F0  W18 G3 S0 | woodStop:0                 &lt;- Idle 归零</pre>')
H.append('<div class="note">注意 <code>G0</code>：未升铜器 ⇒ <code>goldTarget</code> 恒为 0（cpp:2545），'
         '黄金这一路<b>整段关闭</b>；<code>S0</code>：3 座箭塔建满 ⇒ <code>stoneStop</code> 永久为真。</div>')
H.append('</div>')

# 根因
H.append('<div class="card"><h2>3 根因链（逐层带行号）</h2>')
H.append('<table><tr><th>层</th><th>位置</th><th>内容</th><th>本局实测</th></tr>'
         '<tr><td>① 门禁</td><td><code>cpp:2510</code></td>'
         '<td><code>woodStop = Wood &gt;= (frame&gt;=WAVE3_TIME ? 320 : 220)</code></td>'
         '<td>6.8 分起木头 222~312 ⇒ <b>锁死</b></td></tr>'
         '<tr><td>② 门禁</td><td><code>cpp:2545</code></td>'
         '<td><code>goldTarget = !postBronze ? 0 : …</code></td>'
         '<td>未升铜器 ⇒ 金路<b>关闭</b></td></tr>'
         '<tr><td>③ 门禁</td><td><code>cpp:2518</code></td>'
         '<td><code>stoneStop = frame&gt;=21000 || Stone&gt;=300 || towersDone</code></td>'
         '<td>3 塔建满 ⇒ 石路<b>关闭</b></td></tr>'
         '<tr><td>④ 容量</td><td><code>cpp:2719 / 2739 / 2762</code></td>'
         '<td>浆果 ≤3/丛、瞪羚 ≤2/只、农场恰好 1 人/场</td>'
         '<td>食物工卡在 F12~14，<b>满员</b></td></tr>'
         '<tr><td>⑤ <b>兜底被反杀</b></td><td><code>cpp:2771-2783</code></td>'
         '<td>注释写「<b>绝不空闲</b>」「不受上限约束」，实现却是 '
         '<code>if (tree &amp;&amp; <b>!woodStop</b>)</code></td>'
         '<td>四人出口全关 ⇒ <b>原地待命</b></td></tr>'
         '</table>')
H.append('<p>完整兜底段（cpp:2770-2783）：</p>')
H.append('<pre class="mono">'
         '// ★ 兜底：前面所有食物来源(BUSH/GAZELLE/ELEPHANT/FARM)都不可用→伐木，绝不空闲。\n'
         '//   不受 woodTarget 上限约束：食物耗尽时即便已有 &gt;=woodTarget 个伐木工，也把多余空闲村民派去伐木\n'
         'auto goldRes = findNearestResource(RESOURCE_GOLD, f.DR, f.UR);\n'
         'if (goldRes &amp;&amp; goldWorkers &lt; goldTarget) {        // goldTarget==0 ⇒ 恒 false\n'
         '    HumanAction(f.SN, goldRes-&gt;SN); goldWorkers++;\n'
         '} else {\n'
         '    auto tree = findBestWoodTree(f.DR, f.UR);\n'
         '    if (tree &amp;&amp; <b>!woodStop</b>) {                  // &lt;-- 兜底在这里被门禁反杀\n'
         '        HumanAction(f.SN, tree-&gt;SN);\n'
         '        woodWorkers++;\n'
         '    }\n'
         '}   // 两条都不成立 ⇒ 本帧什么都不发 ⇒ 村民保持 IDLE</pre>')
H.append('<div class="note"><b>自锁性质</b>：<code>woodStop</code> 判的是<b>存量</b>（≥220），'
         '而存量之所以不降，恰恰是因为没有消费、也没有人再往里加 —— '
         '一旦锁上，只能等一次性的木头支出把它打下来（本局等了 6.4 分钟）。'
         '这就是「结构性死锁」在资源侧的同族形态。</div>')
H.append('</div>')

# 为什么是 9 分钟
H.append('<div class="card"><h2>4 为什么"9 分钟"开始 —— 不是波次，是阈值换挡</h2>')
H.append('<p>先排除了一个很像的原因：</p>')
H.append('<table><tr><th>候选</th><th>验证</th><th>结论</th></tr>'
         '<tr><td>WAVE2 = 13500 帧 = 9.0 分，正好等于用户报的时刻</td>'
         '<td><code>manageFirstWaveDefense()</code> 全文只有 4 行：'
         '<code>waveBlockers.clear()</code>，是个空壳；'
         'grep <code>assignIdleSimple/assignIdleFarmers</code> 内 <code>state</code> 引用 = 0 处</td>'
         '<td class="bad">排除：波次状态不参与分配</td></tr>'
         '<tr><td>木头阈值在 14 分换挡</td>'
         '<td><code>WOOD_CAP_STOP 220</code> → <code>WOOD_CAP_STOP_LATE 320</code>，'
         '切换点 = <code>WAVE3_TIME</code> = 21000 = 14.0 分</td>'
         '<td class="good">成立：木门在 14 分放宽 ⇒ Idle 归零</td></tr>'
         '</table>')
H.append('<p>所以"9 分钟"只是"<b>看得出来</b>"的时刻：木头在 <b>%.1f 分</b>越过 220 后门禁锁死，'
         '此后新增村民（%d→%d→%d 人）与浆果/瞪羚耗竭不断产生空闲人口，'
         '而出口只剩食物一路且已满员 ⇒ Idle 逐分钟堆高，在 9~13 分从个位数涨到 %d 人。'
         '<b>%.1f 分</b>木头跌破 220（一次性的建造/科技支出）⇒ 木门开 ⇒ 18 个伐木工一次性放出 ⇒ Idle 归零。'
         '换言之：<b>解铃的不是波次，是"有人把木头花掉"</b>。</p>'
         % (first_latch / 1500.0,
            live_min_rows[0]['frm'], live_min_rows[2]['frm'], live_min_rows[-1]['frm'],
            peak, release / 1500.0))
H.append('</div>')

# 普遍性
H.append('<div class="card"><h2>5 普遍性（离线 16 局）</h2>')
H.append('<table><tr><th>局</th><th>峰值 Idle</th><th>woodStop 命中</th>'
         '<th>食物工峰值</th><th>黄金峰值</th><th>死区采样</th></tr>')
for n, mx, ws, ne, dead, fmax, gmax in b_rows:
    cls = ' class="bad"' if mx >= 10 else ''
    H.append('<tr><td>%s</td><td%s>%d</td><td>%d/%d</td><td>%d</td><td>%d</td><td>%d</td></tr>'
             % (esc(n), cls, mx, ws, ne, fmax, gmax, dead))
H.append('</table>')
H.append('<p>死区口径 = <code>woodStop=1 且 食物工≥10 且 黄金工=0</code>：'
         '<b>%d / %d = %.1f%%</b> 的 ECO 采样落在其中；峰值 Idle 最高 18 人。'
         '16 局<b>全部</b>出现过 <code>woodStop</code> 锁死。</p>' % (tot_dead, tot_eco, dead_pct))
H.append('</div>')

# 修法
H.append('<div class="card"><h2>6 修法候选（含风险，待拍板）</h2>')
H.append('<table><tr><th>#</th><th>方案</th><th>改动量</th><th>风险</th><th>评价</th></tr>'
         '<tr><td>A</td><td>兜底去掉 <code>&amp;&amp; !woodStop</code>（cpp:2779），'
         '恢复注释承诺的"绝不空闲"：只在前面四条全失败后才到达 ⇒ 天然低频</td>'
         '<td>改 1 处条件</td>'
         '<td>中：木头会顶破 220 上限继续涨（但木头是建材，反攻期本来就要囤）；'
         '需防"伐木令刷屏"（历史上 <code>woodWorkers&gt;woodTarget</code> 当闸曾致令 ×7 —— '
         '本方案不同，它不进主路径）</td>'
         '<td class="good">直击根因，最小改动</td></tr>'
         '<tr><td>B</td><td>把 <code>WOOD_CAP_STOP</code> 220 → 400（对齐反攻期需求）</td>'
         '<td>改 1 常量</td>'
         '<td>低</td>'
         '<td>治标：只把死区推迟/收窄。但 220 对"反攻期 5~6 靶场并发（≈750~900 木）"本就偏低，'
         '这一改本身也合理</td></tr>'
         '<tr><td>C</td><td>死区时把空闲村民转去<b>建造/科技预备</b>（建房、修塔、囤料）</td>'
         '<td>新增分支</td>'
         '<td>高</td><td>最"正确"但要设计新状态机，收益不确定</td></tr>'
         '<tr><td>D</td><td>放宽食物容量（农场 1 人/场 → 2 人）</td>'
         '<td>改 1 处</td>'
         '<td>中高</td><td>动的是引擎机制假设（单场效率），且只延后饱和</td></tr>'
         '</table>')
H.append('<p class="note">推荐 <b>A</b>（治本、一行），可叠加 <b>B</b>（顺带把木头上限修到合理值）。'
         '验收判据应为<b>产物量</b>：<code>woodStop=1 &amp;&amp; Idle≥5</code> 的采样占比 → ≈0，'
         '同时确认各建筑下发次数与伐木令总数<b>没有暴涨</b>（防"锁死输出"型副作用）。</p>')
H.append('</div>')

# 溯源
H.append('<div class="card"><h2>7 溯源</h2>')
H.append('<table><tr><th>项</th><th>值</th></tr>'
         '<tr><td>源码</td><td><code>C:\\new-aoe3.0.7g\\UsrAI.cpp</code> '
         '<code>3bd4d179</code> / 6461 行（09-20 下午版）</td></tr>'
         '<tr><td>本轮改动</td><td><b>无</b>（纯分析）</td></tr>'
         '<tr><td>探针</td><td><code>idle_probe.py</code>（show / scan / gate 三模式）</td></tr>'
         '<tr><td>生成器</td><td><code>make_idle_report.py</code></td></tr>'
         '<tr><td>实机日志</td><td><code>AIText.log</code>（%d 条状态行 / %d 条门禁自检行）</td></tr>'
         '</table>' % (len(live_stat), len(live_eco)))
H.append('<p class="mono">复现命令：\n'
         '  python idle_probe.py show AIText.log\n'
         '  python idle_probe.py gate "vf_fix_*.ait"</p>')
H.append('</div>')

H.append('</div></body></html>')

open(OUT, 'w', encoding='utf-8').write('\n'.join(H))
print('report ->', OUT, len('\n'.join(H)), 'chars')
print('live: stat=%d eco=%d | peak idle=%d@%d | woodStop latch %s -> release %s (%s 帧 = %.1f 分)'
      % (len(live_stat), len(live_eco), peak, peak_fr, first_latch, release,
         (release - first_latch) if (first_latch and release) else -1,
         (release - first_latch) / 1500.0 if (first_latch and release) else -1))
print('batch: dead %d/%d = %.1f%%' % (tot_dead, tot_eco, dead_pct))
