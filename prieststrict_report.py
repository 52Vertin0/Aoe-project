# -*- coding: utf-8 -*-
"""prieststrict 轮报告: 感化武器厂收紧为「敌全灭+塔全拆」"""
import io, os, re

def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

PAT_WAIT = re.compile(r'\[SIEGE-WAIT f=(\d+)\] hp=([\d.]+) clearOk=(\d+) alive=(\d+) towers=(\d+) dS=([\d.]+)')

# 读三批数据
def batch_stat(b):
    rows = []
    tv = tc = tw = 0
    for i in range(1, 9):
        p = '%s%d.ait' % (b, i)
        if not os.path.exists(p):
            continue
        lines = io.open(p, encoding='utf-8', errors='replace').read().splitlines()
        conv = 0; wait = 0; maxf = 0
        for ln in lines:
            q = ln.split('|')
            if len(q) < 5:
                continue
            try:
                f = int(q[1].strip())
            except Exception:
                continue
            maxf = max(maxf, f)
            if 'Priest converting Siege Workshop' in q[4]: conv += 1
            if '[SIEGE-WAIT' in q[4]: wait += 1
        txt = '\n'.join(lines)
        st = 'VICTORY' if 'VICTORY' in txt else ('DEFEAT' if 'DEFEAT:' in txt else 'timeout')
        rows.append((b + str(i), maxf, conv, wait, st))
        tc += conv; tw += wait
        if st == 'VICTORY': tv += 1
    return rows, tc, tw, tv

th_rows, th_c, th_w, th_v = batch_stat('th')
ps_rows, ps_c, ps_w, ps_v = batch_stat('ps')

H = []
H.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
H.append('<title>祭司感化武器厂条件收紧 · 敌全灭+塔全拆</title>')
H.append('''<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1a1d23;--sub:#5b6472;--line:#e3e6ec;
--red:#c62828;--green:#2e7d32;--amber:#ef6c00;--blue:#1565c0;--pur:#6a1b9a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;line-height:1.72}
.wrap{max-width:1080px;margin:0 auto;padding:32px 22px 80px}
h1{font-size:26px;margin:0 0 6px;letter-spacing:.3px}
.sub{color:var(--sub);font-size:13.5px;margin-bottom:22px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:20px 22px;margin:16px 0;box-shadow:0 1px 2px rgba(0,0,0,.04)}
h2{font-size:17.5px;margin:0 0 12px;padding-bottom:9px;border-bottom:2px solid var(--line)}
h3{font-size:14.5px;margin:18px 0 8px;color:var(--ink)}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:10px 0}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left}
th{background:#f0f2f6;font-weight:600;font-size:12.5px;color:var(--sub);text-transform:uppercase;letter-spacing:.4px}
tr:hover td{background:#fafbfc}
code{background:#eef1f5;padding:1.5px 5px;border-radius:4px;font-size:12.5px;
font-family:"Cascadia Code",Consolas,monospace}
pre{background:#1e222a;color:#e6e9ef;padding:14px 16px;border-radius:8px;
overflow-x:auto;font-size:12.5px;line-height:1.6;font-family:"Cascadia Code",Consolas,monospace}
.verdict{border-left:5px solid var(--red);background:#fdf3f3;padding:14px 18px;border-radius:6px;margin:14px 0}
.verdict.ok{border-color:var(--green);background:#f2f8f3}
.verdict.warn{border-color:var(--amber);background:#fff8ef}
.verdict b{font-size:15px}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:12px 0}
.kv div{background:#f8f9fb;border:1px solid var(--line);border-radius:8px;padding:11px 13px}
.kv .n{font-size:21px;font-weight:700}
.kv .l{font-size:12px;color:var(--sub)}
.big{font-size:15px}
.tag{display:inline-block;padding:1.5px 8px;border-radius:11px;font-size:11.5px;font-weight:600}
.t-v{background:#e8f5e9;color:var(--green)} .t-d{background:#fde8e8;color:var(--red)}
.t-t{background:#eceff1;color:var(--sub)}
.mono{font-family:"Cascadia Code",Consolas,monospace;font-size:12.5px}
ul{margin:8px 0;padding-left:22px}li{margin:5px 0}
.note{font-size:12.5px;color:var(--sub);margin-top:8px}
</style></head><body><div class=wrap>''')

H.append('<h1>祭司感化武器厂条件收紧：敌全灭 + 塔全拆</h1>')
H.append('<div class="sub">2026-09-16 · UsrAI.cpp · 判据块上移 + 全局清场闸 · 对照批 th1-8（局部） vs ps1-8（全局）</div>')

# 1 需求与结论
H.append('<div class="card"><h2>1 · 需求与结论</h2>')
H.append('<p class="big"><b>需求</b>：把祭司感化武器厂的条件收紧为「<b>敌方士兵全灭并且箭塔全拆</b>的情况下再去感化」。</p>')
H.append('<div class="verdict"><b>结论：已按需求实施，闸确实生效——但它把感化彻底关掉了。</b><br>'
         '改动后感化次数 <b>8 次 → 0 次</b>（机制指标，不受噪声影响）；胜局 <b>4/8 → 0/8</b>。<br>'
         '经 16 局实测确认根因：<b>「箭塔全拆」在本图结构性不可达——16 局里我方拆除敌塔 0 次</b>，'
         '而「敌方士兵全灭」是可达的（ps1 f=44900 实测 <code>alive=0</code>）。'
         '即：<b>两个条件里卡死系统的是「塔全拆」那一半</b>。</div>')
H.append('<p class="note">说明：胜局 0/8 本身不足以单独定论（同构重跑批 szb 也是 0/8），'
         '但<b>感化次数 8→0 是机制量</b>，直接证明闸生效且功能被关闭——这才是该改动的主要后果。</p>')
H.append('</div>')

# 2 改前量化（先证伪再加闸）
H.append('<div class="card"><h2>2 · 改前量化（先证伪，再加闸）</h2>')
H.append('<p>动手前先用 32 局历史日志（tc/sz/szb/th）量这个条件是否可达：</p>')
H.append('<table><tr><th>判据</th><th>实测值</th><th>含义</th></tr>')
H.append('<tr><td>敌方兵力补充</td><td>每局 <b>120~143</b> 个（<code>产生了新的…</code>）</td><td>敌方持续产兵</td></tr>')
H.append('<tr><td>我方击杀</td><td>每局 <b>16~40</b></td><td>远低于补充量 ⇒ 兵力净增长</td></tr>')
H.append('<tr><td>「敌方士兵全灭」</td><td>32 局 <b>从未出现</b>（事后 ps 批证明可达，见 §4）</td><td>当时判定为不可达</td></tr>')
H.append('<tr><td>我方拆除敌塔</td><td><b>0 次</b>（16 局全零）</td><td>「箭塔全拆」结构性不可达</td></tr>')
H.append('<tr><td>我方塔被拆</td><td>每局 2~4 座（共 42 座）</td><td>战场态势是反过来的</td></tr></table>')
H.append('<div class="verdict warn"><b>量化已预判会死锁，并把选择权交给用户</b>——'
         '用户选择「<b>定为前置条件</b>」：先用数据实测锁定范围，再决定去留。本报告即该实测结果。</div>')
H.append('<p class="note">⚠ 踩坑记录：量化初版用 <code>[LC-DBG] towers=</code> 列判"塔全拆"，得出「f=33300 塔=0」，'
         '实为<b>未探明伪影</b>（塔逐个被探明：0→1→2…，且 33300 恰为反攻起点）。'
         '引擎 <code>info.enemy_buildings</code> 受 <code>explored||visible</code> 约束，<b>"列表空"≠"不存在"</b>。</p>')
H.append('</div>')

# 3 改动
H.append('<div class="card"><h2>3 · 改动（+65/−22，净 +43 行）</h2>')
H.append('<h3>3.1 新增开关</h3>')
H.append('<pre>#define PRIEST_SIEGE_REQUIRE_GLOBAL_CLEAR true   // true=全局清场闸；false=回退局部清场</pre>')
H.append('<h3>3.2 新增全局清场判据（并上移到 early 路径之前）</h3>')
H.append('<pre>int enemyAliveArmyN = 0;\n'
         'for (auto &amp;e : info.enemy_armies)  if (e.Blood &gt; 0) enemyAliveArmyN++;\n'
         'int enemyTowerN = 0;\n'
         'for (auto &amp;b : info.enemy_buildings) if (b.Type == BUILDING_ARROWTOWER) enemyTowerN++;\n'
         'const bool globalClear = (enemyAliveArmyN == 0 &amp;&amp; enemyTowerN == 0 &amp;&amp; enemySiegeSN != -1);\n'
         'const bool clearOk = PRIEST_SIEGE_REQUIRE_GLOBAL_CLEAR ? globalClear : localClear;</pre>')
H.append('<h3>3.3 三处下发点收口到同一 clearOk（铁律 21/26）</h3>')
H.append('<table><tr><th>下发点</th><th>改动</th></tr>')
H.append('<tr><td>early</td><td>新增 <code>if (!clearOk) return;</code> + 诊断 <code>[SIEGE-WAIT]</code>（<b>此前无任何敌情判据</b>）</td></tr>')
H.append('<tr><td>front</td><td>经 <code>allowConvertSiege</code> 间接受控（无需改）</td></tr>')
H.append('<tr><td>legacy</td><td><code>if (siege &amp;&amp; pDist&lt;12*BL &amp;&amp; cd&lt;=0 <b>&amp;&amp; clearOk</b>)</code></td></tr></table>')
H.append('<h3>3.4 两个配套修正</h3>')
H.append('<ul>'
         '<li><b>判据块整体上移到 early 路径之前</b>：early 是实际主力下发点（实测 6/6 起手走它），'
         '闸放在它后面 = <b>形同虚设</b>（铁律 11）。</li>'
         '<li><b>迟滞锁退出条件追加 <code>!clearOk</code></b>：全局模式下若靠"已进入"续命，'
         '首次满足后即永久放行，闸会失效。</li>'
         '<li><b>已探明保险</b>：<code>enemySiegeSN != -1</code>（武器厂已发现）作为可见性充分的代理，'
         '否则"未探明"会被误判成"已全灭/已全拆"。</li></ul>')
H.append('<div class="verdict ok"><b>意外收获</b>：5140 行原注释写的就是「敌方军队全灭 + 箭塔全拆 → 祭司主动前出」，'
         '但其实现一直是局部清场 ⇒ 本轮改动让<b>注释与实现终于对齐</b>。</div>')
H.append('</div>')

# 4 实测
H.append('<div class="card"><h2>4 · 实测结果（th 局部 vs ps 全局）</h2>')
H.append('<div class="kv">')
H.append('<div><div class="n" style="color:var(--red)">8 → 0</div><div class="l">感化次数（机制指标）</div></div>')
H.append('<div><div class="n" style="color:var(--red)">4/8 → 0/8</div><div class="l">胜局（8 局噪声大，仅参考）</div></div>')
H.append('<div><div class="n" style="color:var(--green)">0 次</div><div class="l">我方拆除敌塔（16 局全零）</div></div>')
H.append('<div><div class="n" style="color:var(--blue)">alive=0</div><div class="l">敌兵全灭确实出现过（ps1）</div></div>')
H.append('</div>')

H.append('<h3>th（局部清场，改前）</h3><table>')
H.append('<tr><th>局</th><th>末帧</th><th>感化</th><th>WAIT</th><th>结局</th></tr>')
for r in th_rows:
    cls = 't-v' if r[4] == 'VICTORY' else ('t-d' if r[4] == 'DEFEAT' else 't-t')
    H.append('<tr><td>%s</td><td class=mono>%d</td><td><b>%d</b></td><td>%d</td>'
             '<td><span class="tag %s">%s</span></td></tr>' % (r[0], r[1], r[2], r[3], cls, r[4]))
H.append('<tr><td><b>合计</b></td><td></td><td><b>%d</b></td><td>%d</td><td><b>胜 %d/8</b></td></tr></table>'
         % (th_c, th_w, th_v))

H.append('<h3>ps（全局清场，改后）</h3><table>')
H.append('<tr><th>局</th><th>末帧</th><th>感化</th><th>WAIT</th><th>结局</th></tr>')
for r in ps_rows:
    cls = 't-v' if r[4] == 'VICTORY' else ('t-d' if r[4] == 'DEFEAT' else 't-t')
    H.append('<tr><td>%s</td><td class=mono>%d</td><td><b>%d</b></td><td>%d</td>'
             '<td><span class="tag %s">%s</span></td></tr>' % (r[0], r[1], r[2], r[3], cls, r[4]))
H.append('<tr><td><b>合计</b></td><td></td><td><b>%d</b></td><td>%d</td><td><b>胜 %d/8</b></td></tr></table>'
         % (ps_c, ps_w, ps_v))

H.append('<h3>关键日志证据</h3>')
H.append('<pre>ps1  f=44900 | [SIEGE-WAIT f=44900] hp=0.60 clearOk=0 alive=0 towers=4 dS=8.5\n'
         '                                   ↑ 敌兵已全灭   ↑ 但敌塔还有 4 座 ⇒ 闸不放行</pre>')
H.append('<p class="note">这是全场唯一一条 <code>[SIEGE-WAIT]</code>，且发生在 f=44900（上限 45000 前 100 帧）。'
         '它精确定位了锁死点：<b>不是"敌兵没灭"，而是"敌塔拆不完"</b>。</p>')
H.append('</div>')

# 5 判决
H.append('<div class="card"><h2>5 · 判决与建议</h2>')
H.append('<div class="verdict"><b>按需求字面实施会让该功能永久失效。</b><br>'
         '「敌方士兵全灭」可达（实测 alive=0），但「箭塔全拆」在本图<b>结构性不可达</b>——'
         '我方 16 局拆除敌塔 0 次（根源：我军不具备压制敌塔的手段/意愿，敌塔恒在武器厂 5~10 格）。'
         '因此严格双闸 = 祭司永不感化 = 唯一的胜利路径（exam 胜条件就是祭司感化武器厂）被关闭。</div>')
H.append('<h3>可选方向</h3>')
H.append('<table><tr><th>方案</th><th>做法</th><th>预期</th></tr>')
H.append('<tr><td><b>A 回滚</b>（推荐）</td><td><code>PRIEST_SIEGE_REQUIRE_GLOBAL_CLEAR=false</code>（一行）</td>'
         '<td>恢复局部清场，感化回到 8/8 局可用</td></tr>')
H.append('<tr><td>B 只加「敌全灭」闸</td><td>去掉 <code>enemyTowerN==0</code> 这一半</td>'
         '<td>可能大幅减少感化机会（alive=0 少见），需再跑一批量化</td></tr>')
H.append('<tr><td>C 先解决「拆塔能力」</td><td>查明为何 16 局拆不掉一座敌塔（军队目标选择的塔优先级）</td>'
         '<td>治本：让"塔全拆"成为可达条件，再谈收紧</td></tr></table>')
H.append('<p class="note">建议：<b>先回滚（方案 A）保住胜率，把 C 作为后续正式课题</b>——'
         '否则当前版本是把唯一胜路关掉的版本。</p>')
H.append('</div>')

# 6 元信息
H.append('<div class="card"><h2>6 · 工程元信息</h2><table>')
H.append('<tr><th>项</th><th>值</th></tr>')
H.append('<tr><td>编译</td><td><code>syn.py</code> 0 error；<code>build.py</code> rc=0；'
         '<code>warn_cmp2.py</code> warning 集合 <b>18=18</b>（逐类别一致）</td></tr>')
H.append('<tr><td>改动量</td><td>+65 / −22 行（净 +43，含注释）；文件 6430 → 6473 行</td></tr>')
H.append('<tr><td>备份</td><td><code>bak_20260916_pre_prieststrict_UsrAI.cpp</code>（改前, md5 dc54c88b…）<br>'
         '<code>bak_20260916_prieststrict_UsrAI.cpp</code>（改后, md5 d0a6d619…）</td></tr>')
H.append('<tr><td>脚本</td><td><code>clearstate_probe.py</code> / <code>clearstate_probe2.py</code>（改前量化）<br>'
         '<code>ps_verify.sh</code>（跑批）<code>prieststrict_check.py</code> / <code>ps_probe3.py</code>（核对）</td></tr>')
H.append('<tr><td>对照批</td><td>A 臂 <code>th1-8</code>（局部清场）；B 臂 <code>ps1-8</code>（全局清场）</td></tr>')
H.append('</table></div>')

H.append('</div></body></html>')

out = 'aoe3_prieststrict_20260916.html'
io.open(out, 'w', encoding='utf-8').write('\n'.join(H))
print('written', out, len('\n'.join(H)), 'chars')
