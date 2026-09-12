# -*- coding: utf-8 -*-
"""生成 shrink 轮报告（HTML）：UsrAI.cpp 四个最长函数的代码精简。
用法：python shrink_report_html.py        # tc(精简前基线) / sz(精简后)
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
    'PRIEST GUARD': re.compile(r'\[PRIEST GUARD\]'),
}
DESC = {'tc': 'tc · 精简前（towerskip 成品，A 臂）', 'sz': 'sz · 本轮（四长函数精简后）'}

CHANGES = [
    ("A1", "manageBuildings 抽 9 个建造收口 lambda",
     "tryBuildHouse / tryBuildGranary / tryBuildMarket / tryBuildArmyCamp / tryBuildRange / tryBuildTower / "
     "tryBuildStable / farmWoodNeedNow / farmerCountNow（+ popHeadroomLowNow、canAffordEconNow 两个局部常量）",
     "794 → 692"),
    ("A2", "8 类重复建造块改用 lambda（共 19 处下发点）",
     "房屋×2 / 兵营×3 / 靶场×4 / 箭塔×2 / 马厩×2 / 谷仓×3 / 市场×3；删 <span class=mono>canAffordBuilding</span> / "
     "<span class=mono>canAffordEcon</span> 局部变量", "−29 行"),
    ("A2b", "删死块 + 两处同源判据收口",
     "删 <span class=mono>nearBushFood</span>（结果从不读取）；新增 <span class=mono>clusterCovered</span> / "
     "<span class=mono>isFarGazelle</span>（原各写两遍，铁律 26）", "−37 行"),
    ("A3", "manageBuildings 长注释压缩（9 处）",
     "保留结论/关键理由/日期决策，删除考古过程与失效分支说明", "注释 −33 行"),
    ("P1", "managePriest 抽 2 个射程 lambda + 感化目标选择合一",
     "<span class=mono>isRangedSort</span> / <span class=mono>enemyThreatRange</span> 收口三处；"
     "findConvertTarget 五段重复循环（方阵兵/近战/远程/投石车/村民）合一为 <span class=mono>pickByBlood(mode)</span>",
     "71 → 40 行"),
    ("P2", "managePriest 治疗档三件套收口",
     "抽 <span class=mono>healLandingOk</span>（落点合法性，原两处各一份）/ <span class=mono>pickHealTarget</span>"
     "（目标选择，原两段筛选循环）/ <span class=mono>moveAdjacentToAlly</span>（贴身上前，含可选"全被否→选离敌最远"兜底）",
     "742 → 686"),
    ("M1", "manageMilitary 删死代码 + 三组同源收口",
     "删 <span class=mono>enemyNearTC</span>（只被 (void) 引用的死 lambda，铁律 27）；收口 "
     "<span class=mono>priestAttackerSN</span>（D-1 一处 + D0 每兵各扫一遍）/ <span class=mono>nearestGuardTarget</span>"
     "（紧急+预警两档）/ <span class=mono>holdNearBase</span>（回基地螺旋 ×2，共 51 行 → 1 行×2）", "−30 行"),
    ("M2", "manageMilitary 长注释压缩（10 处）",
     "同 A3 口径：保留结论与关键理由，删考古", "注释 −19 行"),
    ("C1", "manageCounterAttack 长注释压缩（37 处）",
     "该函数注释占比 34%（359 行）为全文件最高；本轮压到 26%（256 行），保留全部 ★★★ 级根因记录与实测帧号", "950 → 968 体量 −103"),
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
        if m and m.group(1) not in ('祭司', '村民'):
            x = float(m.group(3)) / BL; y = float(m.group(4)) / BL
            moves.setdefault(m.group(1), []).append((fr, ((x - TC_C[0]) ** 2 + (y - TC_C[1]) ** 2) ** 0.5))
        if 'Enemy Siege Workshop found' in msg and not wsf:
            wsf = fr
        if 'VICTORY' in msg and not victf:
            victf = fr
        if 'Force COUNTERATTACK' in msg and not decf:
            decf = fr
        if 'DEFEAT: Priest killed' in msg and not deat:
            deat = fr
    far = max((dd for v in moves.values() for _, dd in v), default=0.0)
    stuck = sum(1 for seq in moves.values() for i in range(1, len(seq))
                if seq[i][0] - seq[i - 1][0] >= 600 and abs(seq[i][1] - seq[i - 1][1]) < 0.5)
    return d, endf, wsf, victf, deat, decf, far, stuck


def lines_of(path):
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) >= 5:
            out.append((p[1].strip(), p[3].strip(), p[4]))
    return out


def load(b):
    out = []
    for i in range(1, 9):
        p = '%s%d.ait' % (b, i)
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            out.append((p, one(p)))
    return out


def med(v):
    return st.median(v) if v else 0.0


def main():
    A, B = load('tc'), load('sz')
    today = datetime.date.today().strftime('%Y-%m-%d')

    # 确定性重放
    replay = []
    for i in range(1, 9):
        pa, pb = 'tc%d.ait' % i, 'sz%d.ait' % i
        if not (os.path.exists(pa) and os.path.exists(pb)):
            continue
        la, lb = lines_of(pa), lines_of(pb)
        same = 0
        for ka, kb in zip(la, lb):
            if ka == kb:
                same += 1
            else:
                break
        replay.append((i, len(la), len(lb), same, la[same] if same < min(len(la), len(lb)) else None,
                       lb[same] if same < min(len(la), len(lb)) else None))

    def rowres(nm, D):
        n = len(D) or 1
        w = sum(1 for _, r in D if r[3] and not r[4])
        return ('%d/%d' % (w, n), '%d/%d' % (sum(1 for _, r in D if r[4]), n),
                '%d/%d' % (sum(1 for _, r in D if r[2]), n), '%d/%d' % (sum(1 for _, r in D if r[5]), n),
                '%d' % med([r[1] for _, r in D]))

    keys = ['HumanMove', 'HumanAction', '设攻目标', '开始攻击', '转换目标', 'KIT-R', 'LC-DBG', 'TOWER-TGT', 'TOWER-SKIP']

    def rowmech(D):
        totf = sum(r[1] for _, r in D) or 1
        return ['%.2f' % (1000.0 * sum(r[0][k] for _, r in D) / totf) for k in keys]

    def rowevents(D):
        out = []
        for p, r in D:
            out.append((os.path.basename(p)[:-4], r[2] or '-', r[5] or '-', r[3] or '-', r[4] or '-', r[1]))
        return out

    hp = []
    hp.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    hp.append('<title>AOE UsrAI · 四长函数代码精简（shrink 轮）</title>')
    hp.append("""<style>
body{font:14px/1.7 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;color:#1c2430;background:#f5f7fa;margin:0;padding:28px}
.wrap{max-width:1180px;margin:0 auto}
h1{font-size:24px;margin:0 0 6px}
h2{font-size:17px;margin:30px 0 10px;padding-left:10px;border-left:4px solid #2f6fd0}
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
ul{margin:6px 0 0 18px;padding:0}
li{margin:3px 0}
</style></head><body><div class="wrap">""")
    hp.append('<h1>UsrAI.cpp 四个最长函数的代码精简</h1>')
    hp.append('<div class="sub">shrink 轮 · %s · 基线 C:\\new-aoe3.0.7g · 红线：纯重构，行为零变化 · '
              'A 臂 = tc（精简前源码 8 局） / B 臂 = sz（精简后 8 局）</div>' % today)

    ta, tb = sum(r[1] for _, r in A), sum(r[1] for _, r in B)
    hp.append('<div class=card><h2>0 · 结论</h2><ul>')
    hp.append('<li><b>体量</b>：全文 6736 → 6424 行（<b>−312 行 / −4.6%%</b>）；注释 1727 → 1571（−156）；'
              '代码 4631 → 4473（−158）。</li>')
    hp.append('<li><b>四个最长函数全部精简</b>：manageCounterAttack 1071→968、manageBuildings 794→692、'
              'managePriest 742→686、manageMilitary 605→554，合计 <b>−312 行</b>（占全文减量 100%%）。</li>')
    hp.append('<li><b>编译</b>：<span class=ok>0 error / 18 warning</span>（与基线同口径，无新增告警类别）。</li>')
    hp.append('<li><b>行为</b>：见第 3 节确定性重放对拍。</li>')
    hp.append('</ul></div>')

    # 结构
    hp.append('<div class=card><h2>1 · 结构指标（pre_shrink → shrink）</h2><table>')
    hp.append('<tr><th>指标</th><th>精简前</th><th>精简后</th><th>变化</th><th>降幅</th></tr>')
    for label, a, b in (('总行数', 6736, 6424), ('注释行', 1727, 1571), ('代码行', 4631, 4473), ('空行', 378, 380)):
        d = b - a
        pct = '%.1f%%' % (100.0 * -d / a) if a else '-'
        hp.append('<tr><td>%s</td><td>%d</td><td>%d</td><td class="%s">%+d</td><td>%s</td></tr>'
                  % (label, a, b, 'ok' if d <= 0 else 'warn', d, pct))
    hp.append('</table><table style="margin-top:14px">')
    hp.append('<tr><th>函数</th><th>体量 前→后</th><th>降幅</th><th>注释 前→后</th><th>注释降幅</th>'
              '<th>注释占比 前→后</th></tr>')
    for n, a, b, ca, cb in (('manageCounterAttack', 1071, 968, 359, 256),
                            ('manageBuildings', 794, 692, 221, 188),
                            ('managePriest', 742, 686, 152, 151),
                            ('manageMilitary', 605, 554, 137, 118)):
        hp.append('<tr><td class=mono>%s</td><td>%d → <b>%d</b></td><td class="ok">%.1f%%</td>'
                  '<td>%d → %d</td><td class="ok">%.1f%%</td><td>%.0f%% → %.0f%%</td></tr>'
                  % (n, a, b, 100.0 * (b - a) / a, ca, cb, 100.0 * (cb - ca) / ca,
                     100.0 * ca / a, 100.0 * cb / b))
    hp.append('</table></div>')

    # 改动明细
    hp.append('<div class=card><h2>2 · 改动明细（全部为「等价收口」或「删死代码/压注释」）</h2><table>')
    hp.append('<tr><th style="width:52px">编号</th><th style="width:270px">改动</th><th>说明</th>'
              '<th style="width:120px">体量</th></tr>')
    for t, ttl, desc, sz in CHANGES:
        hp.append('<tr><td class=mono>%s</td><td>%s</td><td>%s</td><td class=mono>%s</td></tr>' % (t, ttl, desc, sz))
    hp.append('</table>')
    hp.append('<div class=note style="margin-top:12px">红线执行方式：所有收口均保持<b>原判据、原阈值、原分支顺序、'
              '原日志字段</b>不变；每次替换用脚本按"首行唯一锚点 + 末行唯一锚点 + 命中次数断言"定位，未命中即 ABORT 不写文件；'
              '注释压缩额外断言<b>被替换区间内每一行必须是注释行或空行</b>，从机制上杜绝误删代码。</div></div>')

    # 行为对拍
    hp.append('<div class=card><h2>3 · 行为对拍：确定性重放一致性（本轮主判据）</h2>')
    hp.append('<p style="font-size:13px;color:#475569;margin:6px 0 10px">同地图（map3.njust / rotate 90 / -exam / freq MAX）'
              '下引擎为确定论：若重构无行为变化，两臂日志应<b>逐行一致</b>。下表为逐局"共同前缀行数"。</p>')
    hp.append('<table><tr><th>局</th><th>A 行数(tc)</th><th>B 行数(sz)</th><th>相同前缀</th><th>判定</th></tr>')
    nall = 0
    for i, la, lb, same, xa, xb in replay:
        verdict = ('<span class=ok>完全一致</span>' if same == la == lb
                   else '<span class=warn>首差@行 %d</span>' % (same + 1))
        if same == la == lb:
            nall += 1
        hp.append('<tr><td>tc/sz%d</td><td>%d</td><td>%d</td><td>%d</td><td>%s</td></tr>' % (i, la, lb, same, verdict))
    hp.append('</table>')
    tot_a = sum(r[1] for r in replay); tot_b = sum(r[2] for r in replay)
    tot_s = sum(r[3] for r in replay)
    hp.append('<p style="margin-top:10px">合计：A=%d 行、B=%d 行，<b>逐行最长相符前缀 %d 行（%.1f%%）</b>，'
              '<b>%d/8 局完全一致</b>。</p>' % (tot_a, tot_b, tot_s, 100.0 * tot_s / max(1, max(tot_a, tot_b)), nall))
    for i, la, lb, same, xa, xb in replay:
        if same < min(la, lb):
            hp.append('<div class=note style="margin-top:10px"><b>sz%d 首处分叉（第 %d 行）</b><br>'
                      'A：<span class=mono>%s</span><br>B：<span class=mono>%s</span></div>'
                      % (i, same + 1, html.escape(str(xa)[:220]), html.escape(str(xb)[:220])))
            break
    hp.append('</div>')

    # 结果
    hp.append('<div class=card><h2>4 · 结果指标（8 局噪声大，仅参考 —— 铁律 25）</h2><table>')
    hp.append('<tr><th>批次</th><th>胜</th><th>祭司阵亡</th><th>发现武器厂</th><th>发起反攻</th><th>末帧中位</th></tr>')
    for nm, D in (('tc 精简前', A), ('sz 精简后', B)):
        v = rowres(nm, D)
        hp.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % ((nm,) + v))
    hp.append('</table></div>')

    # 机制
    hp.append('<div class=card><h2>5 · 机制量（每千帧 —— 铁律 29 抗局长差异）</h2><table>')
    hp.append('<tr><th>批次</th><th>总帧/千</th>' + ''.join('<th>%s</th>' % k for k in keys) + '</tr>')
    for nm, D in (('tc 精简前', A), ('sz 精简后', B)):
        totf = sum(r[1] for _, r in D) or 1
        hp.append('<tr><td>%s</td><td>%.1f</td>' % (nm, totf / 1000.0)
                  + ''.join('<td>%s</td>' % v for v in rowmech(D)) + '</tr>')
    hp.append('</table>')
    hp.append('<p style="font-size:13px;color:#475569;margin-top:8px">'
              '推进/卡死：' + ' ｜ '.join(
                  '%s 最深推进 中位%.0f / 最大%.0f 格，疑似卡死 %d 次'
                  % (nm, med([r[6] for _, r in D]), max([r[6] for _, r in D] or [0]), sum(r[7] for _, r in D))
                  for nm, D in (('tc', A), ('sz', B))) + '</p>')
    hp.append('</div>')

    # 时间线
    hp.append('<div class=card><h2>6 · 关键事件时间线（帧）</h2><table>')
    hp.append('<tr><th>局</th><th>发现WS</th><th>发起反攻</th><th>VICTORY</th><th>祭司死</th><th>末帧</th></tr>')
    for nm, D in (('tc', A), ('sz', B)):
        for p, r in rowevents(D):
            hp.append('<tr><td class=mono>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                      % ((p,) + r[1:]))
    hp.append('</table></div>')

    hp.append('<div class=card><h2>7 · 遗留</h2><ul>'
              '<li>managePriest 的注释占比在精简后由 20%% 升到 22%%（体量降幅 56 行主要来自代码收口而非注释）——'
              '其注释多为祭司优先级/保命红线的"为什么"，属高价值，本轮刻意保留。</li>'
              '<li>结构优化清单 O1~O9（codemetrics 报告）中，O4 抽 <span class=mono>manageScout</span>（~400 行）'
              '仍为最大单块来源；两个最长的函数（968 / 692 行）已接近"单函数体量"的可维护上限，'
              '后续可考虑按决策阶段拆分为独立成员函数。</li>'
              '</ul></div>')

    hp.append('</div></body></html>')

    out = 'aoe3_shrink_%s.html' % today.replace('-', '')
    open(out, 'w', encoding='utf-8').write('\n'.join(hp))
    print('written', out, len('\n'.join(hp)), 'bytes')


if __name__ == '__main__':
    main()
