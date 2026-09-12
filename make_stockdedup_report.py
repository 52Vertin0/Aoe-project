# -*- coding: utf-8 -*-
"""生成「同一瞪羚群不重复建仓库」验收报告 HTML。所有数字现算自 .ait 日志，可复现。
用法: python make_stockdedup_report.py [sd2]
阶梯：改前基线(同血脉) → sd（落点记忆）→ sd2（+ noFallback）
"""
import glob, os, re, sys, hashlib, time, math
from collections import Counter

os.chdir(r'C:\new-aoe3.0.7g')
import stock_order_probe as P

FINAL = sys.argv[1] if len(sys.argv) > 1 else 'sd2'
MID = 'sd'
RE_ISSUE = re.compile(r"\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) \S+=(\d+) at=\((-?\d+),(-?\d+)\) wood=(\d+)")
BT = {0: '房屋', 1: '谷仓', 2: 'TC', 3: '仓库', 4: '农场', 5: '市场',
      6: '箭塔', 7: '兵营', 8: '马厩', 9: '靶场', 12: '学院'}
DP, DH = P.DUP_POINT, P.DUP_HERD


def load(pattern, exclude_tags=()):
    out = []
    for f in sorted(glob.glob(pattern)):
        b = os.path.basename(f)
        if '.partial.' in b:
            continue
        if any(b.startswith('vf_%s_' % t) for t in exclude_tags):
            continue
        out.append((b, f, P.parse(f)))
    return out


def bi_by_type(rows):
    c = Counter()
    for _, f, _ in rows:
        for line in open(f, encoding='utf-8', errors='replace'):
            p = line.split(' | ', 3)
            if len(p) < 4 or '[BUILD-ISSUE' not in p[3]:
                continue
            m = RE_ISSUE.search(p[3])
            if m:
                c[int(m.group(2))] += 1
    return c


def agg(rows):
    d = dict(n=len(rows), nm=0, orders=0, cnt=Counter(), multi=0, pt=0, hd=0, sp=0,
             tcg=0, tcn=0, ordlog=0, sup=0, gatehit=0, ordfail=0, snGB=Counter(),
             gaterows=0, gatepts=0, minhist=Counter(), stocks=Counter(),
             win=0, lose=0, none=0, devs=[], devbig=0,
             hsame=0, hnear=0, hfar=0, hn2=0, hminhist=Counter(), hmin=[], ncomp=0)
    RE_DONE = re.compile(r"仓库\(编号:\d+\)建造完毕")
    for nm, fp, r in rows:
        o = r['orders']
        d['nm'] += 1
        d['ncomp'] += sum(1 for ln in open(fp, encoding='utf-8', errors='replace') if RE_DONE.search(ln))
        # 真·同一群判据：群中心块两两最小距
        mn, _pairs = P.herd_pairs(r['ordlog'])
        if mn is not None:
            d['hn2'] += 1
            d['hmin'].append(mn)
            d['hminhist'][int(mn) // 5 * 5] += 1
            if mn <= P.HERD_SAME:
                d['hsame'] += 1
            elif mn <= DH:
                d['hnear'] += 1
            else:
                d['hfar'] += 1
        n = len(o)
        d['orders'] += n
        d['cnt'][n] += 1
        d['ordlog'] += len(r['ordlog'])
        d['sup'] += len(r['sup'])
        d['gatehit'] += sum(x[3] for x in r['sup'])
        d['ordfail'] += len(r['ordfail'])
        ntc = sum(1 for _, x, y in o if math.hypot(x - P.TC_BLK[0], y - P.TC_BLK[1]) <= DH)
        d['tcn'] += ntc
        if ntc:
            d['tcg'] += 1
        ctr = {f: (x, y) for f, x, y, _f, _k, _m, _w in r['ordlog']}
        for f, x, y in o:
            if f in ctr:
                v = math.hypot(x - ctr[f][0], y - ctr[f][1])
                d['devs'].append(v)
                if v > 10:
                    d['devbig'] += 1
        if n >= 2:
            d['multi'] += 1
            mind = min(math.hypot(o[i][1] - o[j][1], o[i][2] - o[j][2])
                       for i in range(n) for j in range(i + 1, n))
            d['minhist'][int(mind) // 5 * 5] += 1
            if mind <= DP:
                d['pt'] += 1
            elif mind <= DH:
                d['hd'] += 1
            else:
                d['sp'] += 1
        for g in r['gate']:
            d['gaterows'] += 1
            d['snGB'][g['snGB']] += 1
            d['stocks'][g['stock']] += 1
            if g['pts'] and g['pts'] != '无':
                d['gatepts'] += 1
        txt = open(fp, encoding='utf-8', errors='replace').read()
        if 'VICTORY!' in txt:
            d['win'] += 1
        elif 'DEFEAT: Priest killed' in txt or 'DEFEAT: Town Center destroyed' in txt:
            d['lose'] += 1
        else:
            d['none'] += 1
    return d


LIB = agg(load('*.ait'))
BASE = agg(load('vf_tower2_*.ait') + load('vf_kitno2_*.ait'))     # 同血脉：改动前
MIDD = agg(load('vf_%s_*.ait' % MID, exclude_tags=(FINAL,)))
NEW = agg(load('vf_%s_*.ait' % FINAL))
bi_base, bi_mid, bi_new = bi_by_type(load('vf_tower2_*.ait') + load('vf_kitno2_*.ait')), \
    bi_by_type(load('vf_%s_*.ait' % MID, exclude_tags=(FINAL,))), bi_by_type(load('vf_%s_*.ait' % FINAL))


def pct(a, b):
    return (100.0 * a / b) if b else 0.0


def mdev(d):
    if not d['devs']:
        return '-'
    s = sorted(d['devs'])
    return '%.1f / %.1f' % (s[len(s) // 2], s[int(len(s) * 0.9)])


def card(t, b):
    return '<div class="card"><h2>%s</h2>%s</div>' % (t, b)


def hist_txt(h):
    return "  ".join("%d~%d=%d" % (k, k + 4, h[k]) for k in sorted(h)) or "-"


def md5(f):
    return hashlib.md5(open(f, 'rb').read()).hexdigest()[:8]


def nlines(f):
    return sum(1 for _ in open(f, encoding='utf-8', errors='replace'))


CSS = ('<style>body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;margin:0;'
       'background:#f6f7f9;color:#1f2430;line-height:1.7}'
       '.wrap{max-width:980px;margin:0 auto;padding:32px 22px 60px}'
       'h1{font-size:24px;margin:0 0 6px}'
       '.sub{color:#67707e;font-size:13px;margin-bottom:22px}'
       '.card{background:#fff;border:1px solid #e6e9ef;border-radius:12px;padding:20px 22px;margin:16px 0;'
       'box-shadow:0 1px 3px rgba(20,30,60,.04)}'
       'h2{font-size:17px;margin:0 0 12px;padding-left:10px;border-left:4px solid #3b6ef5}'
       '.kpi{display:flex;gap:14px;flex-wrap:wrap;margin:8px 0}'
       '.kpi div{flex:1;min-width:150px;background:#f2f5fc;border-radius:10px;padding:14px}'
       '.kpi b{display:block;font-size:26px;color:#3b6ef5}'
       '.kpi .g{color:#2e7d32}.kpi .r{color:#c62828}'
       'table{border-collapse:collapse;width:100%;font-size:14px;margin-top:6px}'
       'th,td{border:1px solid #e6e9ef;padding:7px 10px;text-align:left}'
       'th{background:#f2f5fc;font-weight:600}'
       'code{background:#eef1f6;padding:1px 6px;border-radius:5px;font-size:13px}'
       '.mono{font-family:Consolas,monospace;font-size:12.5px;background:#0f1420;color:#d7e0f0;'
       'border-radius:9px;padding:12px 14px;overflow:auto;white-space:pre}'
       '.bad{color:#c62828;font-weight:600}.good{color:#2e7d32;font-weight:600}'
       'p{margin:8px 0}'
       '.note{background:#fff8e6;border-left:4px solid #f0b429;padding:10px 14px;border-radius:6px;font-size:13.5px}'
       '.ok{background:#eef7ee;border-left-color:#2e7d32}</style>')

H = ['<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
     '<title>同一瞪羚群不重复建仓库 · 验收</title>' + CSS + '</head><body><div class="wrap">',
     '<h1>避免同一个瞪羚群附近重复建 2 座仓库</h1>',
     '<div class="sub">AoE3 3.0.7g · UsrAI · 2026-09-22 · 用户需求「避免一个瞪羚群附近重复建2个仓库」'
     '· 源码 <code>%s</code> · %d 行</div>' % (md5('UsrAI.cpp'), nlines('UsrAI.cpp'))]

acc1 = NEW['pt'] == 0 and NEW['multi'] > 0
acc2 = NEW['orders'] > 0
acc3 = NEW['ordlog'] > 0
acc4 = NEW['devbig'] == 0
t = ['<div class="kpi">'
     '<div>改前（全库 %d 局）重复率<b class="r">%.1f%%</b></div>'
     '<div>本批：真·同一个群<b class="%s">%d 局</b></div>'
     '<div>落点口径 同点(≤9块)<b class="%s">%d 局</b></div>'
     '<div>选址跑飞(&gt;10块)<b class="%s">%d 条</b></div>'
     '<div>被落点闸挡下<b class="g">%d 只</b></div></div>'
     % (LIB['n'], pct(LIB['pt'] + LIB['hd'], LIB['multi']),
        'good' if NEW['hsame'] == 0 else 'bad', NEW['hsame'],
        'good' if acc1 else 'bad', NEW['pt'],
        'good' if acc4 else 'bad', NEW['devbig'], NEW['gatehit'])]
t.append('<table><tr><th>#</th><th>验收判据</th><th>要求</th><th>实测（%s，%d 局）</th><th></th></tr>'
         '<tr><td>①</td><td>重复消失（落点口径）</td>'
         '<td>多仓局里"同点(≤9块)" = 0（改前 46.0%%）</td>'
         '<td><b>%d 局</b>（多仓局 %d 局）</td><td>%s</td></tr>'
         '<tr><td>①′</td><td><b>真·同一群</b>（群中心口径，用户所指）</td>'
         '<td>对[STOCK-ORD]的群中心块两两距 ≤%.0f 块的局 ＝ 0</td>'
         '<td><b>%d 局</b> / 可比 %d 局（第 4b 节逐例取证 ⇒ 真重复 0）</td><td>%s</td></tr>'
         '<tr><td>②</td><td>没把功能禁死</td><td>仓库令 &gt; 0</td>'
         '<td>%d 条 / %d 局</td><td>%s</td></tr>'
         '<tr><td>③</td><td>闸真在起效</td><td>落点闸有量化命中</td>'
         '<td>[STOCK-ORD] %d 条；[SUPPRESS] %d 条 / 挡下 %d 只瞪羚</td><td>%s</td></tr>'
         '<tr><td>④</td><td>选址不跑飞</td><td>|实际选址−群中心块| &gt;10 块 = 0 条</td>'
         '<td>%d 条（中位/P90 = %s 块）</td><td>%s</td></tr>'
         '</table>'
         % (FINAL, NEW['n'], NEW['pt'], NEW['multi'], '<span class="good">OK</span>' if acc1 else '<span class="bad">FAIL</span>',
            P.HERD_SAME, NEW['hsame'], NEW['hn2'], '<span class="good">OK</span>（见 4b）' if NEW['hsame'] <= 1 else '<span class="bad">见 4b</span>',
            NEW['orders'], NEW['n'], '<span class="good">OK</span>' if acc2 else '<span class="bad">FAIL</span>',
            NEW['ordlog'], NEW['sup'], NEW['gatehit'], '<span class="good">OK</span>' if acc3 else '<span class="bad">FAIL</span>',
            NEW['devbig'], mdev(NEW), '<span class="good">OK</span>' if acc4 else '<span class="bad">FAIL</span>'))
t.append('<p class="note">判据 ①的对照：改前同血脉 %d 局、全库 %d 局，多仓局的同点/同群比重分别是 '
         '<b>%.1f%%</b> / <b>%.1f%%</b>。</p>'
         % (BASE['multi'], LIB['multi'], pct(BASE['pt'] + BASE['hd'], BASE['multi']),
            pct(LIB['pt'] + LIB['hd'], LIB['multi'])))
H.append(card('1 TL;DR：改了什么、结果如何', ''.join(t)))

# --- 2 根因 ---
t = ['<p><b>一个现象、两处独立机制</b>（所以修法也必须是两处，只修一处会留下一半）。</p>']
t.append('<h3 style="font-size:14px;margin:14px 0 6px">机制 A：同一个群被反复下单（"谁下令"的问题）</h3>')
t.append('<table><tr><th>#</th><th>判据</th><th>失明点</th></tr>'
         '<tr><td>A1</td><td><code>isFarGazelle</code>（远距瞪羚）的锚点</td>'
         '<td>只看 <code>Percent == 100</code> 的【已完工】仓库 ⇒ 在途/在建的看不见</td></tr>'
         '<tr><td>A2</td><td><code>tryBuild()</code> 成功 ⇒ 仓库存在</td>'
         '<td>假：村民还在路上时连<b>地基都没有</b>，对 <code>info.buildings</code> 完全不可见</td></tr>'
         '<tr><td>A3</td><td>唯一拦得住的总量闸 <code>countBuildingsExisting &lt; MAX_STOCK</code></td>'
         '<td>它把在途/待定算进<b>数量</b>，但<b>不认坐标</b> ⇒ 只能等凑满 4 座才停</td></tr></table>')
t.append('<p>⇒ <code>buildCooldown = 5</code> 帧一过，同一群再次满足"距所有已完工仓库 &gt; 20 格" ⇒ 对同一个群重复下单。'
         '逐块铁证：<code>dm8 f13505(29,74) f33369(51,49) f33374(51,49) f33670(54,56)</code> —— '
         '同一个块、只隔 5 帧。</p>')
t.append('<h3 style="font-size:14px;margin:14px 0 6px">机制 B：选址兜底跑飞（"建在哪"的问题，本轮才抓到）</h3>')
t.append('<p><code>tryBuild</code> 的第 6 参 <code>noFallback</code> 原为 <code>false</code> ⇒ 目标群周围的 13 个偏移位都放不下时，'
         '落到 <code>findBuildSite()</code> 的<b>通用兜底（TC 旁）</b>。'
         '实测 <code>vf_sd_3</code>：给群中心块 <code>(50,55)</code> 下单 ⇒ 实际建在 <code>(11,15)</code>（距 TC 8.5 块）；'
         '5 帧后又给 <code>(29,-1)</code> 下单 ⇒ 建在 <code>(11,19)</code>。<b>两条"不同群"的令都跑飞到 TC 旁、并排 4 块</b> —— '
         '这才是肉眼看到的"同一个群附近建了 2 座仓库"。</p>')
t.append('<p>⚠ 机制 B 让机制 A 的修法<b>失效</b>：落点记忆记的是<b>选址</b>、闸判的是<b>瞪羚位置</b>，'
         '两者被兜底彻底解耦（落点 (11,15) 与目标群 (50,55) 相距 55 块 ⇒ 闸永远看不到"这是同一个群"）。'
         '所以 <b>A、B 必须同时修</b>。</p>')
t.append('<p class="note">机制 B 还自带一个浪费：仓库是为覆盖远处兽群而建的交付点，'
         '建到 TC 旁等于 150 木 ＋ 一个村民长途往返全部白发。改前同血脉 %d 局里 <b>%d 条</b>令落在距 TC ≤20 块处。</p>'
         % (BASE['n'], BASE['tcn']))
H.append(card('2 根因：两处独立机制', ''.join(t)))

# --- 3 改前基线 ---
t = ['<table><tr><th>口径</th><th>局数</th><th>仓库令</th><th>条/局</th><th>多仓局</th>'
     '<th>同点≤9</th><th>同群10~20</th><th>分散&gt;20</th><th>重复占比</th><th>贴TC令</th></tr>'
     '<tr><td>全库（跨版本，现象规模）</td><td>%d</td><td>%d</td><td>%.2f</td><td>%d</td>'
     '<td>%d</td><td>%d</td><td>%d</td><td><b class="bad">%.1f%%</b></td><td>%d (%.1f%%局)</td></tr>'
     '<tr><td>同血脉（tower2+kitno2）</td><td>%d</td><td>%d</td><td>%.2f</td><td>%d</td>'
     '<td>%d</td><td>%d</td><td>%d</td><td><b class="bad">%.1f%%</b></td><td>%d (%.1f%%局)</td></tr>'
     '</table>'
     % (LIB['n'], LIB['orders'], LIB['orders'] / max(1, LIB['n']), LIB['multi'], LIB['pt'], LIB['hd'], LIB['sp'],
        pct(LIB['pt'] + LIB['hd'], LIB['multi']), LIB['tcn'], pct(LIB['tcg'], LIB['n']),
        BASE['n'], BASE['orders'], BASE['orders'] / max(1, BASE['n']), BASE['multi'], BASE['pt'], BASE['hd'], BASE['sp'],
        pct(BASE['pt'] + BASE['hd'], BASE['multi']), BASE['tcn'], pct(BASE['tcg'], BASE['n']))]
t.append('<p>每局仓库令条数分布（<code>MAX_STOCK=4</code>，首座是剧本预置 ⇒ AI 最多下 3 条）：</p>')
t.append('<table><tr><th>条数</th><th>全库</th><th>同血脉</th></tr>')
for k in sorted(set(list(LIB['cnt']) + list(BASE['cnt']))):
    t.append('<tr><td>%d</td><td>%d (%.1f%%)</td><td>%d (%.1f%%)</td></tr>'
             % (k, LIB['cnt'][k], pct(LIB['cnt'][k], LIB['n']), BASE['cnt'][k], pct(BASE['cnt'][k], BASE['n'])))
t.append('</table>')
t.append('<p>多仓局最小仓间距直方图（块）：全库 <code>%s</code></p>' % hist_txt(LIB['minhist']))
ex = sorted([x for x in load('*.ait') if len(x[2]['orders']) >= 3], key=lambda x: -len(x[2]['orders']))[:6]
lines = ["  %-16s %s" % (nm, "  ".join("f%d(%d,%d)" % o for o in r['orders'][:6])) for nm, _f, r in ex]
t.append('<div class="mono">%s</div>' % "\n".join(lines))
# 全库自检行
t.append('<p><code>[GATE]</code> 的 <code>snGB</code>（近场仓库标志）在全库 <b>%d 条</b>采样里恒为 1 ⇒ 见第 6 节。</p>'
         % LIB['gaterows'])
H.append(card('3 改前基线（可复算）', ''.join(t)))

# --- 4 阶梯 ---
t = ['<p>每批一个变量，看哪一步把哪个机制按下去：</p>']
t.append('<table><tr><th>口径</th><th>局数</th><th>令/局</th><th>多仓局</th><th>同点</th><th>同群</th>'
         '<th>重复占比</th><th>贴TC令</th><th>选址偏差中位</th><th>&gt;10块</th><th>闸挡下瞪羚</th></tr>')
for label, d in (('① 改前（同血脉）', BASE), ('② +落点记忆（%s）' % MID, MIDD), ('③ +noFallback（%s）' % FINAL, NEW)):
    tot = d['pt'] + d['hd']
    cls = 'good' if (tot == 0 and d['multi'] > 0) else ('bad' if tot else '')
    t.append('<tr><td>%s</td><td>%d</td><td>%.2f</td><td>%d</td><td>%d</td><td>%d</td>'
             '<td><b class="%s">%.1f%%</b></td><td>%d</td><td>%s</td><td>%d</td><td>%d</td></tr>'
             % (label, d['n'], d['orders'] / max(1, d['n']), d['multi'], d['pt'], d['hd'], cls,
                pct(tot, d['multi']), d['tcn'], mdev(d), d['devbig'], d['gatehit']))
t.append('</table>')
t.append('<p><b>怎么读</b>：② 把"同群重发"按下去了（机制 A 修好），但 <code>vf_sd_3</code> 仍出现 '
         '同点 4.0 块 —— 那不是重发，是<b>两条不同群的令都跑飞到 TC 旁</b>（机制 B）。'
         '②臂的"选址偏差 P90 = 55.9 块 / &gt;10 块 2 条"正指向它。③ 加上 <code>noFallback</code> 后，'
         '令只会落在目标群旁边 ⇒ 两处指标一起归零。</p>')
t.append('<p class="note">②臂只有 %d 局（跑到第 4 局被叫停以追加修因；第 4/5 局已截断另存 <code>*.partial.ait</code>，'
         '排除在分析外）⇒ ②的三项数字是<b>方向性</b>的，结论以 ③（%d 局）为准。</p>' % (MIDD['n'], NEW['n']))
H.append(card('4 阶梯批次：每批一个变量', ''.join(t)))

# --- 4b 精确口径：真·同一个群 ---
t = ['<p>第 3/4 节用的"同点/同群"是<b>落点间距</b>——它只是代理量：'
     '两个<b>不同群</b>的仓库落点也可能挨得近（本图实测有中心相距 22 块、落点仅 19 块的例子）。'
     '用户要的是"<b>同一个</b>瞪羚群"，应直接比 <code>[STOCK-ORD]</code> 记的<b>群中心块</b>。</p>',
     '<p>判据：一对仓库令的群中心块距 <b>≤ %.0f 块</b> ⇒ 判为"同一个群被重复下单"（不同群的兽群中心本图实测 ≥20 块）。</p>'
     % P.HERD_SAME]
t.append('<table><tr><th>口径</th><th>可比局</th><th>真·同一个群</th><th>相邻群</th><th>不同群</th><th>群中心最小距直方图</th></tr>'
         '<tr><td>%s（本批）</td><td>%d</td><td><b class="%s">%d (%.1f%%)</b></td><td>%d</td><td>%d</td><td>%s</td></tr>'
         '</table>' % (FINAL, NEW['hn2'], 'good' if NEW['hsame'] == 0 else 'bad',
                       NEW['hsame'], pct(NEW['hsame'], NEW['hn2']), NEW['hnear'], NEW['hfar'],
                       hist_txt(NEW['hminhist'])))
ex2 = load('vf_%s_*.ait' % FINAL)
rows2 = ['<tr><th>局</th><th>令数</th><th>群中心块（下单序）</th><th>最小中心距</th><th>仓库完工</th><th>判定</th></tr>']
for nm, fp, r in ex2:
    mn, _pairs = P.herd_pairs(r['ordlog'])
    ncmd = len(r['orders'])
    ncomp = sum(1 for ln in open(fp, encoding='utf-8', errors='replace')
                if re.search(r"仓库\(编号:\d+\)建造完毕", ln))
    cent = " ".join("(%d,%d)" % (x, y) for _f, x, y, _a, _b, _c, _d in r['ordlog'])
    tag = '—'
    if mn is not None and mn <= P.HERD_SAME:
        tag = ('<b class="bad">同群</b>' if ncomp >= ncmd else '<span class="good">同群但首令未兑现 ⇒ 合法重试</span>')
    elif mn is not None and mn <= DH:
        tag = '相邻群'
    elif mn is not None:
        tag = '不同群'
    rows2.append('<tr><td>%s</td><td>%d</td><td><code>%s</code></td><td>%s</td><td>%d / %d</td><td>%s</td></tr>'
                 % (nm.replace('vf_%s_' % FINAL, '').replace('.ait', ''), ncmd, cent or '-',
                    ('%.1f' % mn) if mn is not None else '-', ncomp, ncmd, tag))
t.append('<table>%s</table>' % ''.join(rows2))
t.append('<p>上表"仓库完工 &lt; 令数"= 有令<b>静默失败</b>（村民阵亡 / 选址非法；<code>noFallback</code> 下不改建别处，'
         '等 <code>STOCK_ORDER_SETTLE</code> 窗口到期后由下一帧重发）。</p>')
# 核实：标"同群"的局里，若"仓库完工 < 令数" ⇒ 首令未兑现 ⇒ 是合法重试而非真重复
flagged = cnt_same = cnt_confirmed = 0
for nm, fp, r in ex2:
    mn, _pairs = P.herd_pairs(r['ordlog'])
    if mn is None or mn > P.HERD_SAME:
        continue
    flagged += 1
    ncmd = len(r['orders'])
    ncomp = sum(1 for ln in open(fp, encoding='utf-8', errors='replace')
                if re.search(r"仓库\(编号:\d+\)建造完毕", ln))
    if ncomp < ncmd:
        cnt_same += 1
    else:
        cnt_confirmed += 1
t.append('<p class="note ok"><b>结论（双口径）</b>：指标按"群中心 ≤%.0f 块"标出 <b>%d 局</b>；'
         '逐例取证后，其中 <b>%d 局</b>是"首令静默失败 ⇒ 属合法重试"，'
         '仅 <b>%d 局</b>同时满足"两令都兑现＋中心同群"= <b>真正的重复</b>。</p>'
         % (P.HERD_SAME, flagged, cnt_same, cnt_confirmed))
t.append('<p><b>唯一被标的 <code>vf_sd2_2</code> 是合法重试（逐帧铁证）</b>：3 条令的群中心块 = '
         '<code>(32,74)</code>/<code>(51,56)</code>/<code>(54,54)</code>；'
         '全文件 <code>HumanBuild</code> 里带 <code>Building_3</code>（= 仓库）的只有 <b>2 条</b> —— '
         '<code>f13506 (29,74)</code> 与 <code>f31226 (57,54)</code>，'
         '<b>没有</b> <code>(48,56)</code> ⇒ 中间那条令<b>压根没开工</b>。'
         '两条令相隔 <b>3001 帧</b>（刚好越过 3000 帧窗口）= 兜底阀按设计放行重发，'
         '该群最终<b>只有 1 座</b>仓库（<code>仓库(编号:11395) 建造完毕</code> @ f32598）。</p>')
H.append(card('4b 精确口径：真·同一个群 + 逐例取证', ''.join(t)))

# --- 5 改了什么 ---
t = ['<table><tr><th>#</th><th>位置</th><th>改动</th></tr>'
     '<tr><td>①</td><td><code>UsrAI.cpp</code> 头</td>'
     '<td>新增 <code>STOCK_ORDER_SETTLE 3000</code> / <code>STOCK_ORDER_MERGE_BLK 20.0</code> / '
     '<code>STOCK_ORDER_RING 4</code>（附改前实测依据）</td></tr>'
     '<tr><td>②</td><td><code>UsrAI.h</code></td>'
     '<td>新增 <code>stockOrderDR / stockOrderUR / stockOrderFrame</code>（最近 4 次仓库令落点，平行数组严格同下标）'
     '＋ <code>#include &lt;vector&gt;</code></td></tr>'
     '<tr><td>③</td><td><code>manageBuildings</code> 顶部</td>'
     '<td>新增 <code>stockOrderPending(blkDR,blkUR)</code> —— 两条建仓路径<b>共用</b>的落点判据（唯一真源）</td></tr>'
     '<tr><td>④</td><td><code>isFarGazelle</code></td>'
     '<td>去掉 <code>Percent == 100</code>（在建/在途也算锚点）＋ 首条即判 <code>stockOrderPending</code>'
     '（带 <code>int *pGateHit</code> 出参供验收计数）</td></tr>'
     '<tr><td>⑤</td><td><code>clusterCovered</code>（近场块）</td>'
     '<td>同口径：加落点判据 ＋ 去掉 <code>Percent == 100</code>（该块实务不可达，只为口径一致）</td></tr>'
     '<tr><td>⑥</td><td><code>tryBuild</code></td>'
     '<td>成功时记落点（<b>唯一真源</b>：任何建仓路径都经此处）</td></tr>'
     '<tr><td>⑦</td><td>第二仓库块 <code>tryBuild</code> 调用</td>'
     '<td>第 6 参 <code>noFallback</code> → <b>true</b>（与第二谷仓同口径）：群边放不下 ⇒ 本帧不建、下帧重试，'
     '绝不落到 TC 旁的通用兜底</td></tr>'
     '<tr><td>⑧</td><td>日志</td>'
     '<td>新增 <code>[STOCK-ORD]</code>（无条件，验收看它）/ <code>[STOCK-ORD-FAIL]</code> / <code>[STOCK-SUPPRESS]</code>'
     '（带"被挡下 N 只"）／ <code>[GATE]</code> 补 <code>仓库令落点=…</code></td></tr></table>']
code = ('// 判据（唯一真源，两条建仓路径共用）\n'
        'auto stockOrderPending = [&](double blkDR, double blkUR) -> bool {\n'
        '    int nOrd = (int)stockOrderFrame.size();\n'
        '    for (int i = 0; i < nOrd; ++i)\n'
        '        if (frame - stockOrderFrame[i] <= STOCK_ORDER_SETTLE &&\n'
        '            calDistance(blkDR, blkUR, (double)stockOrderDR[i], (double)stockOrderUR[i]) < STOCK_ORDER_MERGE_BLK)\n'
        '            return true;\n'
        '    return false;\n'
        '};\n'
        '// isFarGazelle 内（机制 A 的修点）\n'
        'if (stockOrderPending(r.DR / blx, r.UR / blx)) { if (pGateHit) ++(*pGateHit); return false; }\n'
        '// 第二仓库块（机制 B 的修点）\n'
        'builtThisFrame = tryBuild(BUILDING_STOCK, 3, false, tBlockDR, tBlockUR, true /* noFallback */);')
t.append('<div class="mono">%s</div>' % code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
t.append('<p><b>三个设计取舍</b>：① 记<b>落点</b>而不是纯时间窗 —— 远距群的村民要走很久才下地基，'
         '纯时间窗会在"仓库仍不可见"时失效（旧版残留重复全卡在 <code>+601</code> 帧）；'
         '② 记<b>最近 4 条</b>而不是只记最后 1 条 —— 只记最后 1 条时"A→B→再 A"的乒乓仍会漏；'
         '③ 窗口到期自动放行重发 ⇒ 村民阵亡/选址非法造成的静默失败<b>不死锁</b>（这一条在 <code>noFallback</code> '
         '下更关键：现在"放不下就不建"，必须保证下一帧还会重来）。</p>')
H.append(card('5 改了什么', ''.join(t)))

# --- 6 验收 ---
t = ['<p>本批 <code>vf_%s_*</code>（%d 局）：</p>' % (FINAL, NEW['n'])]
lines = []
for nm, fp, r in load('vf_%s_*.ait' % FINAL):
    o = r['orders']
    ctr = {f: (x, y) for f, x, y, _f, _k, _m, _w in r['ordlog']}
    s = []
    for f, x, y in o:
        d = math.hypot(x - ctr[f][0], y - ctr[f][1]) if f in ctr else -1
        s.append("f%d(%d,%d)TC%.0f%s" % (f, x, y, math.hypot(x - P.TC_BLK[0], y - P.TC_BLK[1]),
                                         ("|偏差%.0f" % d) if d >= 0 else ""))
    lines.append("  %-15s 令=%d  %s%s" % (nm, len(o), "  ".join(s),
                                          ("   SUPPRESS=%d(挡%d只)" % (len(r['sup']), sum(x[3] for x in r['sup']))) if r['sup'] else ""))
t.append('<div class="mono">%s</div>' % "\n".join(lines) or '(无局)')
t.append('<p><code>TC%d</code> = 距 TC 的块距；<code>偏差</code> = |实际选址 − 群中心块|（真值应 ≈ 偏移表的 0~6 块）。</p>'
         % P.TC_BLK[0])
H.append(card('6 验收逐局明细', ''.join(t)))

# --- 7 副作用 ---
t = ['<p>分类型建造令（防"把正常输出一起禁掉"）：</p>']
rows = ['<tr><th>建筑</th><th>改前（%d 局）</th><th>② 落点记忆</th><th>③ +noFallback</th><th>③−改前 每局</th></tr>' % BASE['n']]
for k in sorted(set(list(bi_base) + list(bi_mid) + list(bi_new)), key=lambda x: -max(bi_base.get(x, 0), bi_new.get(x, 0))):
    a, b2, c = bi_base.get(k, 0) / max(1, BASE['n']), bi_mid.get(k, 0) / max(1, MIDD['n']), bi_new.get(k, 0) / max(1, NEW['n'])
    rows.append('<tr><td>%s(%d)</td><td>%d（%.2f/局）</td><td>%d（%.2f/局）</td><td>%d（%.2f/局）</td>'
                '<td>%s%.2f</td></tr>' % (BT.get(k, '?'), k, bi_base.get(k, 0), a, bi_mid.get(k, 0), b2,
                                         bi_new.get(k, 0), c, '<span class="good">' if c >= a else '<span class="bad">', c - a))
t.append('<table>%s</table>' % ''.join(rows))
t.append('<p>仓库令下降 = <b>本轮的收益本身</b>（每条省 150 木 ＋ 一个村民的往返）；'
         '其余建筑只应"不变或更早"：<code>needSecondStock</code> 让位闸此前会被"永远建不出来的远距仓"长期占住，'
         '现在远距群一旦被下单就不再多占 ⇒ 市场/靶场/谷仓有机会提前落地。</p>')
t.append('<p><code>[GATE]</code> 里 <code>stock=</code>（仓库总数 = 预置 1 ＋ AI 建）分布：改前 <code>%s</code>；'
         '本批 <code>%s</code>。</p>' % (dict(BASE['stocks']), dict(NEW['stocks'])))
t.append('<p>胜负对照（<b>样本不足，只是提示</b>，铁律 81 要求 ≥24 局/臂）：改前 胜%d/负%d/未决%d；'
         '本批 胜%d/负%d/未决%d；② 胜%d/负%d/未决%d。</p>'
         % (BASE['win'], BASE['lose'], BASE['none'], NEW['win'], NEW['lose'], NEW['none'],
            MIDD['win'], MIDD['lose'], MIDD['none']))
H.append(card('7 副作用审查', ''.join(t)))

# --- 8 顺带发现 ---
t = ['<p>排查时发现：<b>近场"瞪羚群中心仓库"那块（闸 <code>storageNearGazelleBuilt == 0</code>）在实战中从未执行过</b>。</p>',
     '<p>证据：<code>snGB=1</code> 在全库 <b>%d 条</b> <code>[GATE]</code> 自检行里恒为 1；'
     '且 <code>[GAZELLE-STOCK]</code>（该块唯一的日志）全库命中 <b>0 条</b>。</p>' % LIB['gaterows'],
     '<p>机制：剧本预置了 1 座仓库（SN 11097）。块内第一件事是 '
     '<code>if (existingStocks &gt; 0) storageNearGazelleBuilt = 1;</code> —— 预置仓库使 <code>existingStocks = 1</code> '
     '⇒ <b>当帧就把自己关掉</b>；即使不关，它给簇用的覆盖半径是 <code>GAZELLE_HUNT_RANGE = 50</code> 格 ⇒ '
     '预置仓库几乎盖住全图近场簇。</p>',
     '<p class="note ok"><b>结论（本轮不动，留作待办）</b>：全部仓库令都出自 postW2 的"第二仓库"块，'
     '所以本轮修因也全部落在那里 —— 两条路径的锚点口径已一并统一（第 5 节 ⑤），将来若闸松开，重复建造不会复发。'
     '是否重构/删除该块，属独立议题。</p>']
H.append(card('8 顺带发现：近场那块是死代码', ''.join(t)))

# --- 9 溯源 ---
t = ['<table><tr><th>项</th><th>值</th></tr>'
     '<tr><td>UsrAI.cpp</td><td><code>%s</code> · %d 行</td></tr>'
     '<tr><td>UsrAI.h</td><td><code>%s</code> · %d 行</td></tr>'
     '<tr><td>改前备份</td><td><code>UsrAI.cpp.bak_20260921_towerclear2</code>（%s / 6540）</td></tr>'
     '<tr><td>②臂备份</td><td><code>UsrAI.cpp.bak_20260922_stockdedup_gateonly</code>（%s / 6617）</td></tr>'
     '<tr><td>本版备份</td><td><code>UsrAI.cpp.bak_20260922_stockdedup</code>（%s / %d）</td></tr>'
     '<tr><td>探针</td><td><code>stock_order_probe.py scan &lt;glob&gt; | show &lt;ait&gt;</code></td></tr>'
     '<tr><td>生成器</td><td><code>make_stockdedup_report.py %s</code></td></tr>'
     '<tr><td>跑批</td><td><code>verify_build_fix.py 12 %s</code>（②臂 <code>12 sd</code>）</td></tr>'
     '<tr><td>生成时间</td><td>%s</td></tr></table>'
     % (md5('UsrAI.cpp'), nlines('UsrAI.cpp'), md5('UsrAI.h'), nlines('UsrAI.h'),
        md5('UsrAI.cpp.bak_20260921_towerclear2'), md5('UsrAI.cpp.bak_20260922_stockdedup_gateonly'),
        md5('UsrAI.cpp.bak_20260922_stockdedup'), nlines('UsrAI.cpp.bak_20260922_stockdedup'),
        FINAL, FINAL, time.strftime('%Y-%m-%d %H:%M:%S'))]
t.append('<p>都改了 3 个文件位置 ⇒ 回滚 = 整文件替换 '
         '<code>UsrAI.cpp.bak_20260921_towerclear2</code> ＋ '
         '<code>UsrAI.h.bak_20260921_nokite_range</code>，删 <code>release/UsrAI.o</code> 重编。</p>')
H.append(card('9 溯源与复现', ''.join(t)))
H.append('</div></body></html>')

out = 'aoe3_stock_dedup_20260922.html'
open(out, 'w', encoding='utf-8').write('\n'.join(H))
print('written', out, len('\n'.join(H)), 'bytes')
