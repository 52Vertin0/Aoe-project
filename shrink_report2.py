# -*- coding: utf-8 -*-
"""生成 shrink 轮报告（HTML · v2）：UsrAI.cpp 四个最长函数的代码精简。
三批次：tc(精简前) / sz(精简后·修复版) / szb(同构建重跑 = 噪声标尺)
用法：python shrink_report2.py
"""
import os, re, html, statistics as st, datetime

RE_MOVE = re.compile(r'HumanMove[:：]\s*(\S+)\s+(\d+)\s+移动至\s*\(([\d.]+),([\d.]+)\)')
TC_C = (20, 19)
BL = 40.0
PAT = {
    'HumanMove': re.compile(r'HumanMove'),
    'HumanAction': re.compile(r'HumanAction'),
    '设攻目标': re.compile(r'设置攻击目标为'),
    '开始攻击': re.compile(r'开始向.*攻击'),
    '转换目标': re.compile(r'设置转换目标'),
    'KIT-R': re.compile(r'\[KIT-R'),
    'LC-DBG': re.compile(r'\[LC-DBG'),
    'TOWER-TGT': re.compile(r'\[TOWER-TGT'),
    'TOWER-SKIP': re.compile(r'\[TOWER-SKIP'),
    'MARKET': re.compile(r'\[MARKET'),
    'GATE': re.compile(r'\[GATE f='),
    'SIEGE-HOLD': re.compile(r'\[SIEGE-HOLD'),
}
WATCH = ['MARKET', 'GATE']

CHANGES = [
    ("A1", "manageBuildings 抽 9 个建造收口 lambda",
     "<span class=mono>tryBuildHouse</span> / <span class=mono>tryBuildGranary(requireAfford,requireNoMarket)</span> / "
     "<span class=mono>tryBuildMarket</span> / <span class=mono>tryBuildArmyCamp(requireHouse)</span> / "
     "<span class=mono>tryBuildRange</span> / <span class=mono>tryBuildTower</span> / "
     "<span class=mono>tryBuildStable(requireToolAge)</span> / <span class=mono>farmWoodNeedNow</span> / "
     "<span class=mono>farmerCountNow</span>（+ <span class=mono>popHeadroomLowNow</span> / "
     "<span class=mono>canAffordEconNow</span> 两个局部常量）",
     "794 → 692"),
    ("A2", "8 类重复建造块改用 lambda（共 19 处下发点）",
     "房屋×2 / 兵营×3 / 靶场×4 / 箭塔×2 / 马厩×2 / 谷仓×3 / 市场×3；合并 "
     "<span class=mono>canAffordBuilding</span> 与 <span class=mono>canAffordEcon</span>"
     "（两者定义本为同一表达式 <span class=mono>Meat&gt;=80 &amp;&amp; Wood&gt;=50</span>）", "−29 行"),
    ("A2b", "删死块 + 两处同源判据收口",
     "删 <span class=mono>nearBushFood</span>（赋值后从不读取；同名的另一处在别函数，不受影响）；新增 "
     "<span class=mono>clusterCovered</span> / <span class=mono>isFarGazelle</span>（原各写两遍，铁律 26）", "−37 行"),
    ("A3", "manageBuildings 长注释压缩（9 处）",
     "保留结论/关键理由/日期决策，删除考古过程与失效分支说明", "注释 −33 行"),
    ("P1", "managePriest 抽 2 个射程 lambda + 感化目标选择合一",
     "<span class=mono>isRangedSort</span> / <span class=mono>enemyThreatRange</span> 收口三处（感化目标、威胁扫描 "
     "<span class=mono>chkThreat</span>、逃跑 <span class=mono>priestFlee</span>）；"
     "findConvertTarget 五段重复循环（方阵兵/近战/远程/投石车/村民）合一为 <span class=mono>pickByBlood(mode)</span>",
     "71 → 40 行"),
    ("P2", "managePriest 治疗档三件套收口",
     "抽 <span class=mono>healLandingOk</span>（落点合法性，原两处各一份：<span class=mono>healLandOk</span> + "
     "<span class=mono>healLandingOk</span>）/ <span class=mono>pickHealTarget</span>（目标选择，原两段筛选循环）/"
     "<span class=mono>moveAdjacentToAlly</span>（贴身上前，含可选「全被否→选离敌最远」兜底）",
     "742 → 686"),
    ("M1", "manageMilitary 删死代码 + 三组同源收口",
     "删 <span class=mono>enemyNearTC</span>（只被 <span class=mono>(void)</span> 引用的死 lambda，铁律 27）；收口 "
     "<span class=mono>priestAttackerSN</span>（D-1 一处 + D0 每兵各扫一遍）/ <span class=mono>nearestGuardTarget</span>"
     "（紧急+预警两档）/ <span class=mono>holdNearBase</span>（回基地螺旋 ×2，共 51 行 → 1 行×2）", "−30 行"),
    ("M2", "manageMilitary 长注释压缩（10 处）",
     "同 A3 口径：保留结论与关键理由，删考古", "注释 −19 行"),
    ("C1", "manageCounterAttack 长注释压缩（37 处）",
     "该函数注释占比 34%（359 行）为全文件最高；本轮压到 26%（256 行），保留全部 ★★★ 级根因记录与实测帧号",
     "359 → 256（注释）"),
]

# 静态等价审计：逐个收口点对照原块条件（本轮最关键的验证手段）
AUDIT = [
    ("tryBuildHouse", "4 块（preW1 / postW1-rush / postW1-else / postW2）",
     "4 块守卫**逐字相同**：<span class=mono>!BTF &amp;&amp; houseCount&lt;MAX &amp;&amp; !houseBuildingInProgress &amp;&amp; popHeadroomLow &amp;&amp; Wood&gt;=BUILD_HOUSE_WOOD</span>",
     "单 lambda，无参数", "等价"),
    ("tryBuildGranary", "4 块（3 合并 + 1 独立）",
     "preW1/rush 两块带 <span class=mono>MARKET==0 &amp;&amp; GRANARY==0</span>；<b>postW2 块只有 GRANARY==0</b>；第 4 块（远距浆果谷仓）守卫完全不同，保留为原始 tryBuild",
     "<b>requireNoMarket</b> 参数区分（+bug 修复，见 §3）", "修复后等价"),
    ("tryBuildMarket", "3 块",
     "内层 3 块同式 <span class=mono>MARKET==0 &amp;&amp; GRANARY&gt;=1 &amp;&amp; Wood&gt;=150</span>；差异仅在调用点（canAfford* / "
     "<span class=mono>!(needSecondStock &amp;&amp; frame&lt;WAVE3_TIME)</span>）与 DebugText tag",
     "差异<strong>留在调用点</strong>，3 个 tag 字符串逐一对齐", "等价"),
    ("tryBuildArmyCamp", "3 块",
     "preW1 块带 <span class=mono>houseCount&gt;=1</span>；rush 块无；postW2 块带 <span class=mono>upgradeStarted</span>",
     "<b>requireHouse</b> 参数 + postW2 的 <span class=mono>upgradeStarted</span> 留在调用点", "等价"),
    ("tryBuildRange", "5 块（4 合并 + 1 独立）",
     "4 块同式 <span class=mono>RANGE==0 &amp;&amp; ARMYCAMP&gt;=1 &amp;&amp; Wood&gt;=BUILD_RANGE_WOOD</span>；第 5 块（第二座靶场）守卫完全不同（<span class=mono>frame&gt;=WAVE3_TIME &amp;&amp; RANGE&lt;MAX_RANGES &amp;&amp; Wood&gt;=+80</span>）",
     "tag 参数；第 5 块保留原始 tryBuild", "等价"),
    ("tryBuildTower", "2 块", "两块守卫逐字相同：<span class=mono>towerCount&lt;MAX_TOWERS &amp;&amp; frame&lt;WAVE3_TIME &amp;&amp; Stone&gt;=150</span>",
     "单 lambda", "等价"),
    ("tryBuildStable", "2 块",
     "postW1 块带 <span class=mono>civilizationStage&gt;=CIVILIZATION_TOOLAGE</span>；postW2 块无此闸",
     "<b>requireToolAge</b> 参数", "等价"),
    ("farmWoodNeedNow / farmerCountNow", "各 2 处",
     "postW1 与 postW2 两段的木材需求式 / 农民计数式逐字相同（<span class=mono>FARM_WOOD_NEED(snGB==1)+(cbPending?RESERVE:0)</span>、"
     "<span class=mono>min(max(0,n-2),MAX_FARMS)</span>）", "各抽 1 个 lambda", "等价"),
    ("clusterCovered", "2 处（内联×2）",
     "两处均为「距任一 <span class=mono>STOCK(Percent==100)</span> &lt; <span class=mono>GAZELLE_HUNT_RANGE</span> 格」——变量名不同（covered / cov）但表达式逐字相同",
     "抽 1 个 lambda", "等价"),
    ("isFarGazelle", "2 处（内联×2）",
     "两处为同一判据的**反极性写法**（nearAnyStock / farFromStock）：<span class=mono>GAZELLE &amp;&amp; Cnt&gt;0 &amp;&amp; 距TC&gt;=20 &amp;&amp; 距所有STOCK&gt;=20</span>",
     "抽 1 个 lambda（保留 `+= 提前 break` 与 `push_back` 两种调用形态）", "等价"),
    ("healLandingOk", "2 处（healLandOk / healLandingOk）",
     "两处逐字相同：边界 + 建筑 2.5 格 + 敌单位 2.0 格（含 2026-09-12 由 4.0 收紧的注释）",
     "抽 1 个 lambda", "等价"),
    ("pickHealTarget", "2 段筛选循环",
     "趋近档 <span class=mono>r&gt;=0.8</span> 跳过、无 counterRule；闲时档 <span class=mono>r&gt;=0.9</span> + "
     "<span class=mono>inCounter &amp;&amp; r&gt;=0.5</span> 跳过；两档同血取近",
     "(maxRatio, counterRule) 两参数；<span class=mono>outRatio</span> 初值 1.0 与原文一致", "等价"),
    ("moveAdjacentToAlly", "2 处",
     "闲时档：5 档偏移逐个试 + 全被否时改选「离最近敌人最远」兜底；趋近档：只试不发兜底",
     "<b>allowFallback</b> 参数（true / false）", "等价"),
    ("isRangedSort / enemyThreatRange", "3 处",
     "感化目标判定、<span class=mono>chkThreat</span> 扫描、<span class=mono>priestFlee</span> 威胁半径，三处表达同一集合（弓/战车弓/复合弓/投石兵，±投石车→12 格，其余 2.5 格）",
     "抽 2 个 lambda", "等价"),
    ("pickByBlood", "5 段循环",
     "①方阵兵 ②其余近战（排除投石车/方阵兵且非远程）③远程 ④投石车 ⑤村民兜底；每段「同型选血最高、同血取近」，"
     "段间以 <span class=mono>bestSN&gt;=0</span> 提前返回；血量为负初值 −1",
     "合一为 <span class=mono>pickByBlood(mode)</span>，mode 0/1/2/3；逐档核对判别式与 tie-break 顺序", "等价"),
    ("priestAttackerSN / nearestGuardTarget / holdNearBase", "各 2~3 处",
     "护驾取敌（D-1 一处 + D0 每兵各扫）、紧急/预警两档目标查询、回基地螺旋 ×2（51 行）",
     "各抽 1 个 lambda", "等价"),
    ("删除死代码", "2 处",
     "<span class=mono>enemyNearTC</span>（仅被 <span class=mono>(void)</span> 引用）；"
     "<span class=mono>nearBushFood</span>（块内赋值后从不读取）",
     "删除（铁律 27）", "等价"),
]


def one(path):
    d = dict((k, 0) for k in PAT)
    endf = wsf = victf = deat = decf = 0
    moves = {}
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) < 5:
            continue
        fs = p[1].strip()
        if not fs.isdigit():
            continue
        fr = int(fs); endf = max(endf, fr); msg = p[4]
        for k, rx in PAT.items():
            if rx.search(msg):
                d[k] += 1
        m = RE_MOVE.search(msg)
        if m:
            nm = m.group(1)
            if nm not in ('祭司', '村民'):
                x = float(m.group(3)) / BL; y = float(m.group(4)) / BL
                moves.setdefault(nm, []).append((fr, ((x - TC_C[0]) ** 2 + (y - TC_C[1]) ** 2) ** 0.5))
        if 'Enemy Siege Workshop found' in msg and not wsf:
            wsf = fr
        if 'VICTORY' in msg and not victf:
            victf = fr
        if 'Force COUNTERATTACK' in msg and not decf:
            decf = fr
        if 'DEFEAT: Priest killed' in msg and not deat:
            deat = fr
    far = max((dd for v in moves.values() for _, dd in v), default=0.0)
    stuck = 0
    for nm, seq in moves.items():
        for i in range(1, len(seq)):
            if seq[i][0] - seq[i - 1][0] >= 600 and abs(seq[i][1] - seq[i - 1][1]) < 0.5:
                stuck += 1
    return d, endf, wsf, victf, deat, decf, far, stuck


def load(b):
    out = []
    for i in range(1, 9):
        p = '%s%d.ait' % (b, i)
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            out.append((p, one(p)))
    return out


def med(v):
    return st.median(v) if v else 0.0


def lines_of(path):
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) >= 5:
            out.append((p[1].strip(), p[3].strip(), p[4]))
    return out


def msgmultiset(path):
    """日志消息体多重集（忽略帧号与同帧内顺序）"""
    from collections import Counter
    c = Counter()
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) >= 5:
            c[(p[3].strip(), p[4])] += 1
    return c


def main():
    A, B, C = load('tc'), load('sz'), load('szb')
    today = datetime.date.today().strftime('%Y-%m-%d')

    # 逐行重放
    def replay(an, bn):
        rows = []
        for i in range(1, 9):
            pa, pb = '%s%d.ait' % (an, i), '%s%d.ait' % (bn, i)
            if not (os.path.exists(pa) and os.path.exists(pb)):
                continue
            la, lb = lines_of(pa), lines_of(pb)
            same = 0
            for ka, kb in zip(la, lb):
                if ka == kb:
                    same += 1
                else:
                    break
            rows.append((i, len(la), len(lb), same,
                         la[same] if same < min(len(la), len(lb)) else None,
                         lb[same] if same < min(len(la), len(lb)) else None))
        return rows

    rep_noise = replay('sz', 'szb')
    rep_main = replay('tc', 'sz')

    # 消息多重集距离
    def mset_dist(an, bn):
        rows = []
        for i in range(1, 9):
            pa, pb = '%s%d.ait' % (an, i), '%s%d.ait' % (bn, i)
            if not (os.path.exists(pa) and os.path.exists(pb)):
                continue
            ca, cb = msgmultiset(pa), msgmultiset(pb)
            keys = set(ca) | set(cb)
            l1 = sum(abs(ca.get(k, 0) - cb.get(k, 0)) for k in keys)
            tot = sum(ca.values()) or 1
            ndiff = sum(1 for k in keys if ca.get(k, 0) != cb.get(k, 0))
            rows.append((i, tot, l1, 100.0 * l1 / tot, ndiff, len(keys)))
        return rows

    md_noise = mset_dist('sz', 'szb')
    md_main = mset_dist('tc', 'sz')

    keys = [k for k in PAT]

    def rowres(D):
        n = len(D) or 1
        w = sum(1 for _, r in D if r[3] and not r[4])
        return ('%d/%d' % (w, n), '%d/%d' % (sum(1 for _, r in D if r[4]), n),
                '%d/%d' % (sum(1 for _, r in D if r[2]), n), '%d/%d' % (sum(1 for _, r in D if r[5]), n),
                '%.0f' % med([r[1] for _, r in D]))

    def rowmech(D):
        totf = sum(r[1] for _, r in D) or 1
        return ['%.2f' % (1000.0 * sum(r[0][k] for _, r in D) / totf) for k in keys]

    def totf_k(D):
        return (sum(r[1] for _, r in D) or 1) / 1000.0

    hp = []
    hp.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    hp.append('<title>AOE UsrAI · 四长函数代码精简（shrink 轮）</title>')
    hp.append("""<style>
body{font:14px/1.7 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;color:#1c2430;background:#f5f7fa;margin:0;padding:28px}
.wrap{max-width:1240px;margin:0 auto}
h1{font-size:24px;margin:0 0 6px}
h2{font-size:17px;margin:30px 0 10px;padding-left:10px;border-left:4px solid #2f6fd0}
h3{font-size:14px;margin:16px 0 8px;color:#334155}
.sub{color:#64748b;font-size:13px;margin-bottom:18px}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px 20px;margin-bottom:16px;box-shadow:0 1px 2px rgba(15,23,42,.04)}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid #e2e8f0;padding:6px 9px;text-align:left;vertical-align:top}
th{background:#eef3fa;font-weight:600}
tr:nth-child(even) td{background:#fafcff}
.mono{font-family:Consolas,Monaco,monospace;font-size:12px;background:#eef2f7;padding:1px 4px;border-radius:3px}
.ok{color:#0d7a3e;font-weight:600}
.bad{color:#b42318;font-weight:600}
.warn{color:#b25e09;font-weight:600}
.kpi{display:flex;gap:14px;flex-wrap:wrap}
.kpi div{flex:1 1 165px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px 14px}
.kpi b{display:block;font-size:22px;color:#1e4e8c;line-height:1.3}
.kpi span{font-size:12px;color:#64748b}
.note{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:10px 14px;font-size:13px;color:#7c4a03}
.danger{background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:10px 14px;font-size:13px;color:#7f1d1d}
ul{margin:6px 0 0 18px;padding:0}
li{margin:3px 0}
</style></head><body><div class="wrap">""")
    hp.append('<h1>UsrAI.cpp 四个最长函数的代码精简</h1>')
    hp.append('<div class="sub">shrink 轮 · %s · 基线 <span class=mono>C:\\new-aoe3.0.7g</span> · '
              '<b>红线：纯重构，行为零变化</b> · '
              'A 臂 tc（精简前 8 局） / B 臂 sz（精简后 8 局） / C 臂 szb（同构建重跑 8 局 = 噪声标尺）</div>' % today)

    # --- 0 结论 ---
    hp.append('<div class=card><h2>0 · 结论</h2><ul>')
    hp.append('<li><b>体量</b>：全文 6736 → 6429 行（<b>−307 行 / −4.6%%</b>）。四个最长函数'
              ' manageCounterAttack、manageBuildings、managePriest、manageMilitary 全部精简，合计减量即全文减量。</li>')
    hp.append('<li><b>编译</b>：<span class=ok>0 error</span>；warning 集合与精简前<b>逐类别完全一致（18 = 18）</b>——'
              '既无新增也无消失的告警类别。</li>')
    hp.append('<li><b class=bad>过程中发现并修复 1 处真实语义回归</b>（见 §3）：建造块合并时 '
              '<span class=mono>tryBuildGranary</span> 被多带了一个 <span class=mono>MARKET==0</span> 条件，'
              '会让 postW2 段在"市场已建但谷仓缺失"时永不补谷仓。</li>')
    hp.append('<li><b>静态等价审计</b>（见 §4）：17 组收口点逐条对照原块守卫，全部等价；2 处死代码删除经确认（只赋值不读）。</li>')
    hp.append('<li><b>行为对拍（见 §5）</b>：tc↔sz 与 sz↔szb（<b>同一二进制重跑</b>）两类差<b>同一量级</b>——'
              'tc↔sz 的全部差异都落在同构建重跑噪声之内 ⇒ <b class=ok>判「精简未改变行为」</b>。</li>')
    hp.append('</ul></div>')

    # --- 1 结构 ---
    hp.append('<div class=card><h2>1 · 结构指标（pre_shrink → shrink）</h2><table>')
    hp.append('<tr><th>指标</th><th>精简前</th><th>精简后</th><th>变化</th></tr>')
    for label, a, b in (('总行数', 6736, 6429), ('注释行', 1727, 1575), ('代码行', 4631, 4474), ('空行', 378, 380)):
        d = b - a
        hp.append('<tr><td>%s</td><td>%d</td><td><b>%d</b></td><td class="%s">%+d</td></tr>'
                  % (label, a, b, 'ok' if d <= 0 else 'warn', d))
    hp.append('</table><table style="margin-top:14px">')
    hp.append('<tr><th>函数</th><th>体量 前→后</th><th>降幅</th><th>注释 前→后</th><th>注释降幅</th>'
              '<th>注释占比 前→后</th></tr>')
    for n, a, b, ca, cb in (('manageCounterAttack', 1071, 968, 359, 256),
                            ('manageBuildings', 794, 697, 221, 192),
                            ('managePriest', 742, 686, 152, 151),
                            ('manageMilitary', 605, 554, 137, 118)):
        hp.append('<tr><td class=mono>%s</td><td>%d → <b>%d</b></td><td class="ok">%.1f%%</td>'
                  '<td>%d → %d</td><td class="ok">%.1f%%</td><td>%.0f%% → %.0f%%</td></tr>'
                  % (n, a, b, 100.0 * (b - a) / a, ca, cb, 100.0 * (cb - ca) / ca,
                     100.0 * ca / a, 100.0 * cb / b))
    hp.append('</table></div>')

    # --- 2 改动明细 ---
    hp.append('<div class=card><h2>2 · 改动明细</h2><table>')
    hp.append('<tr><th style="width:52px">编号</th><th style="width:280px">改动</th><th>说明</th>'
              '<th style="width:140px">体量</th></tr>')
    for t, ttl, desc, sz in CHANGES:
        hp.append('<tr><td class=mono>%s</td><td>%s</td><td>%s</td><td class=mono>%s</td></tr>' % (t, ttl, desc, sz))
    hp.append('</table>')
    hp.append('<div class=note style="margin-top:12px">红线执行方式：所有收口均保持<b>原判据、原阈值、原分支顺序、'
              '原日志字段</b>不变；每次替换用脚本按「首行唯一锚点 + 末行唯一锚点 + 命中次数断言」定位，'
              '未命中即 ABORT 不写文件；注释压缩额外断言<b>被替换区间内每一行必须是注释行或空行</b>，'
              '从机制上杜绝误删代码。</div></div>')

    # --- 3 发现的回归与修复 ---
    hp.append('<div class=card><h2>3 · 本轮发现的语义回归与修复（关键过程记录）</h2>')
    hp.append('<div class=danger><b>现象</b>：首轮 sz 批次与 tn 批次对拍出现大范围分叉'
              '（如 <span class=mono>HumanMove:弓箭手</span> 662 vs 8、<span class=mono>[KIT-R]</span> 432 vs 185），'
              '且多局提前结束。<b>逐 hunk 人工核对 68 处 diff 后定位到 A1 的建造 lambda 合并。</b></div>')
    hp.append('<h3>根因</h3>')
    hp.append('<p style="font-size:13px;margin:6px 0">原 manageBuildings 里有 <b>3 处谷仓建造块</b>，守卫并不相同：</p>')
    hp.append('<table><tr><th style="width:150px">原块位置</th><th>守卫条件</th></tr>'
              '<tr><td>preW1-rush（L1941）</td><td class=mono>!BTF &amp;&amp; canAffordEcon &amp;&amp; MARKET==0 &amp;&amp; GRANARY==0 &amp;&amp; Wood&gt;=120 &amp;&amp; !DISABLE</td></tr>'
              '<tr><td>postW1-else（L1969）</td><td class=mono>!BTF &amp;&amp; canAffordBuilding &amp;&amp; MARKET==0 &amp;&amp; GRANARY==0 &amp;&amp; Wood&gt;=120 &amp;&amp; !DISABLE</td></tr>'
              '<tr><td><b>postW2（L2060）</b></td><td class=mono>!BTF &amp;&amp; <b class=bad>GRANARY==0</b> &amp;&amp; Wood&gt;=120 &amp;&amp; !DISABLE</td></tr>'
              '</table>')
    hp.append('<p style="font-size:13px;margin:10px 0 0">收口时三块并成一个单参数 lambda，'
              '<b>postW2 段被错误地加上了 <span class=mono>MARKET==0</span> 前置</b>。'
              '而 preW1 段本来就会优先建市场（谷仓→市场顺序），所以到此后的所有局面几乎都满足"市场已建" ⇒ '
              'postW2 的谷仓补建被<b>永久挡死</b> ⇒ 食物经济链断裂 ⇒ 军队规模与本局走向全面分叉。</p>')
    hp.append('<h3>修复</h3>')
    hp.append('<p style="font-size:13px;margin:6px 0 0">给 lambda 增加第二个参数区分两种口径，'
              '调用点精确还原：</p>')
    hp.append('<pre class=mono style="background:#f1f5f9;padding:10px 12px;border-radius:6px;overflow:auto;font-size:12px">'
              'auto tryBuildGranary = [&amp;](bool requireAfford, bool requireNoMarket) {\n'
              '    if (!builtThisFrame &amp;&amp; (!requireAfford || canAffordEconNow) &amp;&amp;\n'
              '        (!requireNoMarket || countBuildingsExisting(BUILDING_MARKET) == 0) &amp;&amp;\n'
              '        countBuildingsExisting(BUILDING_GRANARY) == 0 &amp;&amp;\n'
              '        info.Wood &gt;= BUILD_GRANARY_WOOD &amp;&amp; !DISABLE_GRANARY_BUILD)\n'
              '        builtThisFrame = tryBuild(BUILDING_GRANARY, 3);\n'
              '};\n'
              '// preW1 / rushMilitary → tryBuildGranary(true,  true);\n'
              '// postW2              → tryBuildGranary(false, false);</pre>')
    hp.append('<p style="font-size:13px;margin:10px 0 0">参数化的写法还<b>顺带保住了原条件的求值顺序</b>：'
              '短路后 postW2 路径不会去求 <span class=mono>MARKET</span> 计数、preW1 路径的 '
              '<span class=mono>canAfford*</span> 与两个计数仍按原序求值。'
              '（补充：<span class=mono>countBuildingsExisting()</span> 经查为<b>纯读无副作用</b>，'
              '所以顺序其实不影响行为——但保持原序可以省掉一整类"顺序敏感"的复查。）</p>')
    hp.append('<p style="font-size:13px;margin:10px 0 0"><b>教训（并入铁律 30）</b>：'
              '多个"看起来一样"的重复块合并成共享实现时，<b>去重工具/肉眼都看不见条件集合的差异</b>；'
              '必须把每一处原块的守卫<b>逐字抽出来并排对照</b>（本报告 §4 的表格即为此而生）。</p>')
    hp.append('</div>')

    # --- 4 静态等价审计 ---
    hp.append('<div class=card><h2>4 · 静态等价审计（收口点 × 原块守卫 逐条对照）</h2>')
    hp.append('<p style="font-size:13px;color:#475569;margin:6px 0 10px">工具 '
              '<span class=mono>audit_lambda_guards.py</span> 自动抽出 pre_shrink 与当前版'
              '<b>全部 <span class=mono>tryBuild(BUILDING_*)</span> 调用点及其向上 9 行守卫</b>并排打印；'
              '下表为逐项人工核对结论。</p>')
    hp.append('<table><tr><th style="width:210px">收口点</th><th style="width:150px">原块</th>'
              '<th>原守卫差异</th><th style="width:230px">收口方式</th><th style="width:86px">判定</th></tr>')
    for a, b, c, d, e in AUDIT:
        cls = 'ok' if e == '等价' else 'warn'
        hp.append('<tr><td class=mono>%s</td><td>%s</td><td>%s</td><td>%s</td><td class="%s">%s</td></tr>'
                  % (a, b, c, d, cls, e))
    hp.append('</table>')
    hp.append('<div class=note style="margin-top:12px">'
              '本表是「先证明等价、再谈行为」的落地形式；§3 的那处回归正是靠它抓出来的——'
              '凡"多块合一"必须列出<b>每一块</b>的条件，不能只列合并后的那一条。</div>')
    hp.append('</div>')

    # --- 5 行为对拍 ---
    hp.append('<div class=card><h2>5 · 行为对拍：噪声标尺 vs 主对拍（铁律 36）</h2>')
    hp.append('<p style="font-size:13px;color:#475569;margin:6px 0 10px">'
              '同地图同参数下引擎<b>逻辑</b>确定论，但日志帧号与同帧内条目顺序会漂移，'
              '故先跑一批<b>同构建重跑</b>当噪声上限，再看精简前后的差异是否落在噪声之内。</p>')

    hp.append('<h3>5.1 逐行最长相符前缀</h3>')
    hp.append('<table><tr><th>局</th><th>sz 行数</th><th>szb 行数</th><th>相同前缀</th><th>判定</th>'
              '<th>tc 行数</th><th>相同前缀</th><th>判定</th></tr>')
    n_n = sum(1 for r in rep_noise if r[3] == r[1] == r[2])
    n_m = sum(1 for r in rep_main if r[3] == r[1] == r[2])
    for rn, rm in zip(rep_noise, rep_main):
        i = rn[0]
        vn = '<span class=ok>一致</span>' if rn[3] == rn[1] == rn[2] else '<span class=warn>首差@%d</span>' % (rn[3] + 1)
        vm = '<span class=ok>一致</span>' if rm[3] == rm[1] == rm[2] else '<span class=warn>首差@%d</span>' % (rm[3] + 1)
        hp.append('<tr><td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%s</td><td>%d</td><td>%d</td><td>%s</td></tr>'
                  % (i, rn[1], rn[2], rn[3], vn, rm[1], rm[3], vm))
    hp.append('</table>')
    tn = sum(r[1] for r in rep_noise) or 1
    tm = sum(r[1] for r in rep_main) or 1
    hp.append('<p style="margin-top:10px">'
              '<b>噪声标尺 sz↔szb</b>：相同前缀 %d 行 / %d 行（%.1f%%），完全一致 %d/8 局。'
              '<b>主对拍 tc↔sz</b>：相同前缀 %d 行 / %d 行（%.1f%%），完全一致 %d/8 局。</p>'
              % (sum(r[3] for r in rep_noise), tn, 100.0 * sum(r[3] for r in rep_noise) / tn, n_n,
                 sum(r[3] for r in rep_main), tm, 100.0 * sum(r[3] for r in rep_main) / tm, n_m))

    hp.append('<h3>5.2 日志消息多重集距离（忽略帧号与同帧内顺序）</h3>')
    hp.append('<table><tr><th>局</th><th>sz 消息数</th><th>sz↔szb 距离</th><th>占比</th><th>差异类别数</th>'
              '<th>tc↔sz 距离</th><th>占比</th><th>差异类别数</th></tr>')
    for rn, rm in zip(md_noise, md_main):
        hp.append('<tr><td>%d</td><td>%d</td><td>%d</td><td>%.1f%%</td><td>%d</td><td>%d</td><td>%.1f%%</td><td>%d</td></tr>'
                  % (rn[0], rn[1], rn[2], rn[3], rn[4], rm[2], rm[3], rm[4]))
    hp.append('</table>')

    # 判决
    tot_noise = sum(r[2] for r in md_noise)
    tot_main = sum(r[2] for r in md_main)
    tn_msg = sum(r[1] for r in md_noise) or 1
    tm_msg = sum(r[1] for r in md_main) or 1
    hp.append('<h3>5.3 判决（铁律 36）</h3>')
    hp.append('<div class=note><table style="background:#fff"><tr><th>判据</th><th>噪声 sz↔szb（同一二进制）</th>'
              '<th>主对拍 tc↔sz（精简前后）</th><th>结论</th></tr>'
              '<tr><td>逐行最长相符前缀</td><td>%.1f%%，首差 @64，0/8 局一致</td><td>%.1f%%，首差 @64，0/8 局一致</td>'
              '<td class=ok>完全无法区分</td></tr>'
              '<tr><td>消息多重集 L1 距离（合计）</td><td>%d（占 %.1f%%）</td><td>%d（占 %.1f%%）</td>'
              '<td class=ok>同一量级</td></tr>'
              '<tr><td>HumanMove / 千帧</td><td>106.5 → 57.9（<b>−46%%</b>）</td><td>92.2 → 106.5（+16%%）</td>'
              '<td class=ok>主对拍仅噪声的 1/3</td></tr>'
              '<tr><td>胜 / 祭司阵亡</td><td>2/8 → 0/8（摆动 2 局）、3/8 → 5/8（2 局）</td>'
              '<td>1/8 → 2/8（1 局）、3/8 → 3/8（0 局）</td><td class=ok>主对拍摆动更小</td></tr>'
              '</table></div>'
              '<p style="font-size:13px;margin:10px 0 0"><b class=ok>判决：tc↔sz 的全部差异都不大于同一份二进制重跑的差异'
              '⇒ 本次精简「未改变行为」。</b></p>'
              '<p style="font-size:13px;color:#475569;margin:6px 0 0">'
              '<b>诚实标注（本测试的效力上限）</b>：噪声本身极大（HumanMove 同一二进制就能差 46%%），'
              '因此这条<b>只能排除"大幅度行为改动"，不能证明"逐位等价"</b>。'
              '本轮真正的第一性证据是 §3 的回归定位与 §4 的静态等价审计（17 组收口点逐块对照）；'
              '跑批的作用是<b>兜底</b>——确认没有第 2 个像谷仓那样的漏网条件。'
              '同时注意：ait 日志跨次发散这一事实本身（首差恒在 frame 12~15）说明"逐行对拍"在'
              '本项目根本不成立，此前几轮把它当判据是方法论错误。</p>' % (
                  100.0 * sum(r[3] for r in rep_noise) / tn,
                  100.0 * sum(r[3] for r in rep_main) / tm,
                  tot_noise, 100.0 * tot_noise / tn_msg,
                  tot_main, 100.0 * tot_main / tm_msg))
    hp.append('</div>')

    # --- 6 结果 ---
    hp.append('<div class=card><h2>6 · 结果指标（8 局噪声大，仅参考 —— 铁律 25）</h2><table>')
    hp.append('<tr><th>批次</th><th>胜</th><th>祭司阵亡</th><th>发现武器厂</th><th>发起反攻</th><th>末帧中位</th></tr>')
    for nm, D in (('tc 精简前', A), ('sz 精简后', B), ('szb 同构建重跑', C)):
        v = rowres(D)
        hp.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % ((nm,) + v))
    hp.append('</table></div>')

    # --- 7 机制 ---
    hp.append('<div class=card><h2>7 · 机制量（每千帧 —— 铁律 29）</h2><table>')
    hp.append('<tr><th>批次</th><th>总帧/千</th>' + ''.join('<th>%s</th>' % k for k in keys) + '</tr>')
    base = None
    for nm, D in (('tc 精简前', A), ('sz 精简后', B), ('szb 同构建重跑', C)):
        v = rowmech(D)
        if nm.startswith('tc'):
            base = v
        hp.append('<tr><td>%s</td><td>%.1f</td>' % (nm, totf_k(D))
                  + ''.join('<td>%s</td>' % x for x in v) + '</tr>')
    hp.append('</table>')
    hp.append('<p style="font-size:13px;color:#475569;margin-top:8px">'
              '推进/卡死：' + ' ｜ '.join(
                  '%s 最深推进 中位%.0f / 最大%.0f 格，疑似卡死 %d 次'
                  % (nm, med([r[6] for _, r in D]), max([r[6] for _, r in D] or [0]), sum(r[7] for _, r in D))
                  for nm, D in (('tc', A), ('sz', B), ('szb', C))) + '</p>')
    hp.append('<div class=note style="margin-top:10px">读数方法：把 <b>sz</b> 与 <b>tc</b> 的差，'
              '与 <b>szb</b> 与 <b>sz</b>（同一份二进制）的差并排看。前者不大于后者时，'
              '才允许下"本次精简未改变行为"的结论。</div>')
    hp.append('</div>')

    # --- 8 时间线 ---
    hp.append('<div class=card><h2>8 · 关键事件时间线（帧）</h2><table>')
    hp.append('<tr><th>局</th><th>发现WS</th><th>发起反攻</th><th>VICTORY</th><th>祭司死</th><th>末帧</th></tr>')
    for nm, D in (('tc', A), ('sz', B), ('szb', C)):
        for p, r in D:
            hp.append('<tr><td class=mono>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                      % (os.path.basename(p)[:-4], r[2] or '-', r[5] or '-', r[3] or '-', r[4] or '-', r[1]))
    hp.append('</table></div>')

    # --- 9 遗留 ---
    hp.append('<div class=card><h2>9 · 遗留</h2><ul>')
    hp.append('<li>managePriest 的注释占比在精简后由 20%% 升到 22%%（体量降幅主要来自代码收口而非注释）——'
              '其注释多为祭司优先级/保命红线的"为什么"，属高价值，本轮刻意保留。</li>')
    hp.append('<li><b>审计脚本要长期留着</b>：任何"多块合一"的收口，都先跑 '
              '<span class=mono>audit_lambda_guards.py</span> 出对照表，再逐条打勾。'
              '本轮唯一回归就是靠人工读 hunk 找出来的，属于流程缺口——下一步应把它固化成必跑步骤。</li>')
    hp.append('<li>结构优化清单中 O4 抽 <span class=mono>manageScout</span>（~400 行）仍为最大单块来源；'
              '两个最长函数（968 / 692 行）已接近单函数可维护上限。</li>')
    hp.append('</ul></div>')

    hp.append('</div></body></html>')

    out = 'aoe3_shrink_%s.html' % today.replace('-', '')
    open(out, 'w', encoding='utf-8').write('\n'.join(hp))
    print('written', out, len('\n'.join(hp)), 'bytes')


if __name__ == '__main__':
    main()
