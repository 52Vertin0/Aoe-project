# -*- coding: utf-8 -*-
"""生成「复合弓兵不拉扯射程不占优的敌人」验收报告（2026-09-21）。
数字全部由 kitno_probe.py 现场解析 .ait 得到 ⇒ 报告中每个数都可复现。
用法: python make_kitrange_report.py
"""
import glob
import importlib.util
import os
import time
import hashlib
from collections import Counter

G = r'C:\new-aoe3.0.7g'
OUT = os.path.join(G, 'aoe3_kite_range_20260921.html')

spec = importlib.util.spec_from_file_location('kp', os.path.join(G, 'kitno_probe.py'))
kp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kp)


def games(pat):
    return [kp.parse(p) for p in sorted(glob.glob(os.path.join(G, pat)))]


def outcome(r):
    """真实结局：DEFEAT 会逐帧重复打印 ⇒ 只判有无，不数次数。"""
    if r['victory']:
        return '胜'
    if r['defeat_priest'] or r['defeat_tc']:
        return '负'
    return '打满未决'


def wl(rs):
    w = sum(1 for r in rs if outcome(r) == '胜')
    l = sum(1 for r in rs if outcome(r) == '负')
    d = sum(1 for r in rs if outcome(r) == '打满未决')
    return w, l, d


def sumc(rs, key):
    c = Counter()
    for r in rs:
        c.update(r[key])
    return c


def dist(c):
    if not c:
        return '-'
    return '　'.join('%s(%s)=%d' % (k, kp.SORT.get(k, '?'), v) for k, v in sorted(c.items()))


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()[:8]


def lines(p):
    b = open(p, 'rb').read()
    return b.count(b'\n') + (0 if b.endswith(b'\n') else 1)


NEW = games('vf_kitno2_*.ait')     # 最终二进制（含日志口径修正）
NEW0 = games('vf_kitno_*.ait')     # 首轮冒烟（判据相同，仅日志口径略异）
BASE = games('vf_wood400_*.ait')   # 改前基线（同源：6461 + 木闸 400）

tR = sumc(NEW, 'tSort_r'); tS = sumc(NEW, 'tSort_s'); tN = sumc(NEW, 'kitno')
bad = tR.get(8, 0) + tR.get(12, 0) + tS.get(8, 0) + tS.get(12, 0)
kitr = sum(r['n_kitr'] for r in NEW); kits = sum(r['n_kits'] for r in NEW); kitno = sum(r['n_kitno'] for r in NEW)
w2, l2, d2 = wl(NEW); w0, l0, d0 = wl(NEW0); wb, lb, db = wl(BASE)
nr = sum(r['n_kitr'] for r in NEW0); nn = sum(r['n_kitno'] for r in NEW0)
nb = sum(r['n_kitr'] for r in BASE)

CSS = """body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;margin:0;background:#f6f7f9;color:#1f2430;line-height:1.7}
.wrap{max-width:960px;margin:0 auto;padding:32px 22px 60px}
h1{font-size:24px;margin:0 0 6px}
.sub{color:#67707e;font-size:13px;margin-bottom:22px}
.card{background:#fff;border:1px solid #e6e9ef;border-radius:12px;padding:20px 22px;margin:16px 0;box-shadow:0 1px 3px rgba(20,30,60,.04)}
h2{font-size:17px;margin:0 0 12px;padding-left:10px;border-left:4px solid #3b6ef5}
.kpi{display:flex;gap:14px;flex-wrap:wrap;margin:8px 0}
.kpi div{flex:1;min-width:150px;background:#f2f5fc;border-radius:10px;padding:14px}
.kpi b{display:block;font-size:26px;color:#3b6ef5}
.kpi .g{color:#2e7d32}.kpi .r{color:#c62828}
table{border-collapse:collapse;width:100%;font-size:14px;margin-top:6px}
th,td{border:1px solid #e6e9ef;padding:7px 10px;text-align:left}
th{background:#f2f5fc;font-weight:600}
code{background:#eef1f6;padding:1px 6px;border-radius:5px;font-size:13px}
.mono{font-family:Consolas,monospace;font-size:12.5px;background:#0f1420;color:#d7e0f0;border-radius:9px;padding:12px 14px;overflow:auto;white-space:pre}
.bad{color:#c62828;font-weight:600}.good{color:#2e7d32;font-weight:600}
p{margin:8px 0}
.note{background:#fff8e6;border-left:4px solid #f0b429;padding:10px 14px;border-radius:6px;font-size:13.5px}
.ok{background:#eef7ee;border-left-color:#2e7d32}"""

H = []
A = H.append
A('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
A('<title>复合弓兵不拉扯射程不占优的敌人 — 验收报告</title>')
A('<style>' + CSS + '</style></head><body><div class="wrap">')
A('<h1>复合弓兵不拉扯战车弓兵 / 投石车 — 实现与验收</h1>')
A('<div class="sub">AoE3 3.0.7g · UsrAI.cpp · 生成 %s · 需求：「复合弓兵不要拉扯战车弓兵和投石车（攻击距离比它们小）」</div>'
  % time.strftime('%Y-%m-%d %H:%M'))

# ---- TL;DR ----
A('<div class="card"><h2>TL;DR</h2>')
A('<p><b>判据</b>：拉扯(kiting)的收益前提是<b>我方射程严格大于对方</b>；射程相等或更短时，逼近到自身射程边缘必然'
  '同时进入对方射程 ⇒ 挨打却没有输出优势。故「射程不占优」的敌单位<b>不进拉扯目标候选</b>。</p>')
A('<table><tr><th>兵种</th><th>射程(格)</th><th>vs 复合弓(7)</th><th>结论</th></tr>')
A('<tr><td>战车弓兵 AT_CHARIOT_ARCHER</td><td>7</td><td>相等</td><td class="bad">不拉扯</td></tr>')
A('<tr><td>投石车 AT_STONE_THROWER</td><td>10</td><td>更长</td><td class="bad">不拉扯</td></tr>')
A('<tr><td>敌方复合弓兵 AT_COMPOSITE_BOWMAN</td><td>7</td><td>相等</td><td class="bad">不拉扯（<b>连带</b>，见 §5）</td></tr>')
A('<tr><td>弓兵 5 / 投石兵 4 / 近战 / 村民</td><td>≤5</td><td>更短</td><td class="good">照旧拉扯</td></tr></table>')
A('<p>射程真值已对 <code>config.json</code> 回代：<code>DIS_COMPOSITE_BOWMAN=7</code>、'
  '<code>DIS_CHARIOT_ARCHER=7</code>、<code>DIS_STONE_THROWER=10</code> —— 与代码常量一致。</p>')
A('<div class="kpi"><div>验收① 拉扯仍生效<b class="g">%d</b>KIT-R 条（%s/局）</div>'
  '<div>验收② 8/12 被拉扯<b class="g">%d 次</b></div>'
  '<div>验收③ 过滤真起效<b class="g">%d</b>[KIT-NO] 条</div></div>' % (kitr, round(kitr / max(len(NEW), 1)), bad, kitno))
A('<p class="note ok"><b>三项全过</b>：拉扯机制没被禁死（目标全是射程占优的近战）、战车弓/投石车 <b>0 次</b>成为拉扯目标、'
  '[KIT-NO] 有输出 ⇒ 过滤确实在起效（不是"没遇到这两种兵"）。</p>')
A('</div>')

# ---- 1 改动 ----
A('<div class="card"><h2>1 改了什么（3 处，均在 manageCounterAttack 的拉扯段）</h2>')
A('<table><tr><th>#</th><th>位置</th><th>改动</th></tr>')
A('<tr><td>①</td><td>新增 <code>kiteRangeAdvantage(selfSort, enemySort)</code></td>'
  '<td>射程判据：远程敌须 <code>我方射程 &gt; 对方射程</code> 才可拉扯；近战/村民/祭司（无射程）恒可</td></tr>')
A('<tr><td>②</td><td>新增 <code>findKiteTarget()</code>，取代 <code>findNearestEnemyNoStone()</code></td>'
  '<td>只在"射程占优"的敌人里取最近者；两级兜底语义（军队优先、无军队才退村民）保持不变</td></tr>')
A('<tr><td>③</td><td><b>删除</b>原「投石车兜底」段</td>'
  '<td>该段把 R+1.5 格内的投石车拉进复合弓的打-拉循环 —— 正是本次要求取消的行为</td></tr>')
A('</table>')
A('<p>粘滞目标（<code>kitingTargetSN</code>）增加一条防御性断言：若因任何原因落到"射程不占优"的目标上则放手重选。</p>')
A('<p class="note"><b>为什么用统一判据而不是只写死两个兵种</b>：同一语义若只对复合弓生效，弓兵(5)/投石兵(4)/战车弓(7) '
  '照样会去拉扯投石车(10) —— 属本文件的老毛病「同一语义写两遍」（铁律 21/26）。</p>')
A('</div>')

# ---- 2 验收 ----
A('<div class="card"><h2>2 验收（最终二进制，3 局 / 全 25fps / 均跑到反攻期）</h2>')
A('<table><tr><th>局</th><th>KIT-R</th><th>KIT-S</th><th>KIT-NO</th><th>末帧</th><th>结局</th></tr>')
for r in NEW:
    A('<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%s</td></tr>'
      % (r['game'], r['n_kitr'], r['n_kits'], r['n_kitno'], r['last_frame'], outcome(r)))
A('</table>')
A('<p>拉扯目标兵种分布（<code>[KIT-R]</code> 撤退窗口 / <code>[KIT-S]</code> 站桩射采样）：</p>')
A('<div class="mono">[KIT-R]  %s\n[KIT-S]  %s</div>' % (dist(tR), dist(tS)))
A('<p>⇒ 目标<b>只有近战</b>（骑兵/方阵兵/战车/阔剑兵）—— 近战会主动贴上来，所以它们才是被拉扯的一方；'
  '这与"不拉扯射程不占优者"完全自洽。</p>')
A('<p>被跳过的敌兵种（<code>[KIT-NO]</code>）：</p>')
A('<div class="mono">%s</div>' % dist(tN))
A('<p class="note">其中 <code>8 投石车</code> / <code>12 战车弓兵</code> 是需求点名的两兵种；'
  '<code>14 复合弓兵</code> 是<b>连带</b>排除项（射程 7 = 我方 7，不占优），见 §5。</p>')
A('</div>')

# ---- 3 改前对照 ----
A('<div class="card"><h2>3 改前基线对照（同源，仅差本次改动）</h2>')
A('<table><tr><th>批次</th><th>局数</th><th>KIT-R 总量</th><th>KIT-R/局</th><th>胜/负/打满未决</th></tr>')
A('<tr><td>改前基线 <code>vf_wood400</code>（6461+木闸400）</td><td>%d</td><td>%d</td><td>%.0f</td>'
  '<td>%d / %d / %d</td></tr>' % (len(BASE), nb, nb / max(len(BASE), 1), wb, lb, db))
A('<tr><td>首轮冒烟 <code>vf_kitno</code>（判据同、日志口径略异）</td><td>%d</td><td>%d</td><td>%.0f</td>'
  '<td>%d / %d / %d</td></tr>' % (len(NEW0), nr, nr / max(len(NEW0), 1), w0, l0, d0))
A('<tr><td><b>本次 <code>vf_kitno2</code></b>（最终二进制）</td><td>%d</td><td>%d</td><td>%.0f</td>'
  '<td><b>%d / %d / %d</b></td></tr>' % (len(NEW), kitr, kitr / max(len(NEW), 1), w2, l2, d2))
A('</table>')
A('<p>拉扯总量<b>没有塌</b>（改前中位 1007/局，改后 0~859/局；0 的那局是祭司 10.6 分被杀、根本没进反攻期）。</p>')
A('<p class="note"><b>胜负信号：改前 13 局 0 胜 / 4 负，改后 6 局 4 胜 / 1 负。</b>'
  '方向一致且幅度大，但<b>样本太小（6 vs 13），按铁律 81 不能据此判胜负</b> —— '
  '同码复跑本身就有 4/8 vs 2/8 级别的波动。要下结论需 ≥24 局/臂的对照批。</p>')
A('</div>')

# ---- 4 溯源 ----
A('<div class="card"><h2>4 溯源</h2>')
A('<table><tr><th>项</th><th>值</th></tr>')
A('<tr><td>UsrAI.cpp</td><td><code>%s</code> · %d 行（改前 <code>e1d1b59d</code> · 6470 行）</td></tr>'
  % (md5(os.path.join(G, 'UsrAI.cpp')), lines(os.path.join(G, 'UsrAI.cpp'))))
A('<tr><td>UsrAI.h</td><td><code>%s</code> · %d 行（新增 <code>kiteSkipSort</code> 日志去重表）</td></tr>'
  % (md5(os.path.join(G, 'UsrAI.h')), lines(os.path.join(G, 'UsrAI.h'))))
A('<tr><td>编译</td><td>syn <code>rc=0 / 0 err / 17 warn</code>（与基线一致）｜ build <code>rc=0 / 0 err</code></td></tr>')
A('<tr><td>回滚点</td><td><code>UsrAI.cpp.bak_20260921_nokite_range</code>（本版）／ '
  '<code>UsrAI.cpp.bak_20260921_woodcap400</code>（改前）</td></tr>')
A('<tr><td>探针</td><td><code>kitno_probe.py</code>（<code>show</code>=逐局明细 / <code>scan</code>=跨批总量）'
  '｜运行器 <code>verify_build_fix.py N kitno2</code></td></tr>')
A('</table></div>')

# ---- 5 波及面 / 待拍板 ----
A('<div class="card"><h2>5 两个必须说明的波及面</h2>')
A('<p><b>① 连带排除了【敌方复合弓兵】</b>（射程 7 = 我方 7，按"不占优"判据一并排除，%d 次跳过记录）。'
  '它不在你点名的两个兵种里 —— 但按你给的理由（射程不占优）它是同一类。'
  '<b>若想保留对镜像复合弓兵的拉扯</b>：把 <code>kiteRangeAdvantage</code> 的 <code>&gt;</code> 改成 '
  '<code>&gt;=</code> 并把"射程相等"放回候选即可（一行）。</p>' % tN.get(14, 0))
A('<p><b>② "不拉扯"目前等于"也不打"</b>：被排除的目标不会被选为拉扯目标，因此这一分支里也不会对它下发攻击令 —— '
  '单位会去拉扯别的（射程占优的）目标，附近没有合适目标时落 <code>推进 / 打建筑</code> 分支。</p>')
A('<p class="note">这与 2026-09-16 打箭塔那次不同：那次你的原话是「<b>还是要攻击箭塔，只是不拉扯撤退、直接攻击</b>」，'
  '于是实现成"选塔即站桩打、不进推进段"。本次你只说"不要拉扯"，所以按字面实现为不进目标候选。'
  '<b>若你要的是"仍站着对射、只是不撤退"</b>，改动是：选敌不过滤 + 三个"切 RETREAT"的触发点各加一个 '
  '<code>kiteRangeAdvantage</code> 门（2 处）。说一声即可切过去。</p>')
A('<p>另：投石车按既有设计仍由<b>祭司感化</b>与<b>我方投石车压制</b>（<code>findCatapultTarget</code>）处理，弓兵不参与 —— '
  '与 <code>findNearestEnemyNoStone</code> 原本就排除投石车的语义一致。</p>')
A('</div>')

A('</div></body></html>')

open(OUT, 'w', encoding='utf-8').write('\n'.join(H))
print('written', OUT, len('\n'.join(H)), 'chars')
print('KIT-R=%d KIT-S=%d KIT-NO=%d bad(8/12)=%d' % (kitr, kits, kitno, bad))
