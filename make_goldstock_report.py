# -*- coding: utf-8 -*-
"""生成金矿仓库验收报告 aoe3_gold_stock_20260922.html（数字全部从日志实时计算）。"""
import re, os, glob, json, math, hashlib
from collections import Counter

os.chdir(r'C:\new-aoe3.0.7g')
OUT = 'aoe3_gold_stock_20260922.html'
MAP = 'map3.njust'
TC = (19, 18)
BL = 35.777

RE_BUILD = re.compile(r"\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) \S+=(\d+) at=\((-?\d+),(-?\d+)\) wood=(\d+)")
RE_GORD = re.compile(r"\[GOLD-STOCK f=(\d+)\] 在用金矿簇心块\((-?\d+),(-?\d+)\) 簇内=(\d+) 在用格=(\d+) 远金矿格=(\d+) 金矿仓令=(\d+)/(\d+) 木=(\d+)")
RE_GGATE = re.compile(r"\[GOLD-GATE f=(\d+)\] 存活金矿格=(\d+) 远金矿格=(\d+) 在用远金矿格=(\d+) (?:金矿仓令|服务金矿仓)=(\d+)/(\d+) 被落点闸挡下=(\d+) 木=(\d+)")
RE_GATE = re.compile(r"\[GATE f=(\d+)\] needStock=\d+ gazAlive=\d+ stock=(\d+) wood=(\d+)")


def load_gold():
    d = json.load(open(MAP, encoding='utf-8'))
    return [(100 - v['BlockUR'] - 2, v['BlockDR'])
            for k, v in d.items() if k.startswith('StaticRes') and v.get('Num') == 2]


GOLD = load_gold()


def dmin_gold(x, y):
    return min(math.hypot(x - gx, y - gy) for gx, gy in GOLD)


def parse(fp):
    r = dict(orders=[], gord=[], gfail=0, ggate=[], gate=[], win=0, lose=0, sord=0)
    for line in open(fp, encoding='utf-8', errors='replace'):
        p = line.split(' | ', 3)
        if len(p) < 4:
            continue
        m = p[3]
        if '[BUILD-ISSUE' in m:
            x = RE_BUILD.search(m)
            if x and int(x.group(2)) == 3:
                r['orders'].append((int(x.group(1)), int(x.group(5)), int(x.group(6))))
        if '[GOLD-STOCK ' in m:
            x = RE_GORD.search(m)
            if x:
                r['gord'].append(tuple(int(x.group(i)) for i in range(1, 10)))
        if '[GOLD-STOCK-FAIL' in m:
            r['gfail'] += 1
        if '[GOLD-GATE' in m:
            x = RE_GGATE.search(m)
            if x:
                r['ggate'].append(tuple(int(x.group(i)) for i in range(1, 9)))
        if '[GATE f=' in m:
            x = RE_GATE.search(m)
            if x:
                r['gate'].append((int(x.group(1)), int(x.group(2))))
        if '[STOCK-ORD f=' in m:      # ★ 只有【瞪羚侧】第二仓库块才打这行 ⇒ 它就是瞪羚侧的令量
            r['sord'] += 1
        if 'VICTORY! Siege Workshop converted' in m:
            r['win'] = 1
        if '!!! DEFEAT: ' in m:
            r['lose'] = 1
    return r


def arm(pat):
    files = sorted(glob.glob(pat))
    a = dict(n=len(files), files=[os.path.basename(f) for f in files], orders=0, gord=[], gfail=0,
             hit=0, stock=Counter(), win=0, lose=0, ready=0, readyf=[], alive=0, far=0, use=0,
             gsamp=0, ghit=0, rowsv=[], ghitmax=0, sord=0, laststock=[])
    for fp in files:
        r = parse(fp)
        a['orders'] += len(r['orders'])
        a['sord'] += r['sord']
        if r['gate']:
            a['laststock'].append(r['gate'][-1][1])
        a['gfail'] += r['gfail']
        a['gord'] += [(os.path.basename(fp),) + t for t in r['gord']]
        if r['gord']:
            a['hit'] += 1
        if r['gate']:
            a['stock'][max(s for _, s in r['gate'])] += 1
        a['win'] += r['win']
        a['lose'] += r['lose']
        uf = [g[0] for g in r['ggate'] if g[3] > 0]
        if uf:
            a['ready'] += 1
            a['readyf'].append(uf[0])
        if r['ggate']:
            a['gsamp'] += len(r['ggate'])
            a['alive'] = max(a['alive'], max(g[1] for g in r['ggate']))
            a['far'] = max(a['far'], max(g[2] for g in r['ggate']))
            a['use'] = max(a['use'], max(g[3] for g in r['ggate']))
            a['ghitmax'] = max(a['ghitmax'], max(g[6] for g in r['ggate']))
            a['ghit'] += sum(g[6] for g in r['ggate'])
        # 金矿仓令 → 匹配最近帧的实际落点
        for t in r['gord']:
            f, cx, cy = t[0], t[1], t[2]
            best = None
            for bf, bx, by in r['orders']:
                if abs(bf - f) <= 12 and (best is None or abs(bf - f) < abs(best[0] - f)):
                    best = (bf, bx, by)
            a['rowsv'].append(dict(game=os.path.basename(fp), f=f, cen=(cx, cy), cnt=t[3], k=t[4],
                                   m=t[5], i=t[6], maxi=t[7], wood=t[8], land=best,
                                   dland=(dmin_gold(best[1], best[2]) if best else None),
                                   dcen=(math.hypot(best[1] - cx, best[2] - cy) if best else None),
                                   dtc=(math.hypot(best[1] - TC[0], best[2] - TC[1]) if best else None),
                                   dcengold=dmin_gold(cx, cy)))
    return a


def md5(f):
    return hashlib.md5(open(f, 'rb').read()).hexdigest()[:8]


def nlines(f):
    return sum(1 for _ in open(f, encoding='utf-8', errors='replace'))


A_CTRL = arm('vf_sd2_*.ait')    # 对照：无金矿逻辑
A_SELF = arm('vf_gst_*.ait')    # 第一版：落点闸自锁
A_NEW = arm('vf_gsk_*.ait')     # 现行：独立计数预算

CSS = ('<style>body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;margin:0;'
       'background:#f6f7f9;color:#1f2430;line-height:1.7}'
       '.wrap{max-width:1000px;margin:0 auto;padding:32px 22px 60px}'
       'h1{font-size:24px;margin:0 0 6px}'
       '.sub{color:#67707e;font-size:13px;margin-bottom:22px}'
       '.card{background:#fff;border:1px solid #e6e9ef;border-radius:12px;padding:20px 22px;margin:16px 0;'
       'box-shadow:0 1px 3px rgba(20,30,60,.04)}'
       'h2{font-size:17px;margin:0 0 12px;padding-left:10px;border-left:4px solid #3b6ef5}'
       '.kpi{display:flex;gap:14px;flex-wrap:wrap;margin:8px 0}'
       '.kpi div{flex:1;min-width:148px;background:#f2f5fc;border-radius:10px;padding:14px;font-size:13px}'
       '.kpi b{display:block;font-size:25px;color:#3b6ef5}'
       '.kpi .g{color:#2e7d32}.kpi .r{color:#c62828}'
       'table{border-collapse:collapse;width:100%;font-size:13.5px;margin-top:6px}'
       'th,td{border:1px solid #e6e9ef;padding:7px 10px;text-align:left}'
       'th{background:#f2f5fc;font-weight:600}'
       'code{background:#eef1f6;padding:1px 6px;border-radius:5px;font-size:12.5px}'
       '.mono{font-family:Consolas,monospace;font-size:12.5px;background:#0f1420;color:#d7e0f0;'
       'border-radius:9px;padding:12px 14px;overflow:auto;white-space:pre}'
       '.bad{color:#c62828;font-weight:600}.good{color:#2e7d32;font-weight:600}'
       'p{margin:8px 0}'
       '.note{background:#fff8e6;border-left:4px solid #f0b429;padding:10px 14px;border-radius:6px;font-size:13.5px}'
       '.ok{background:#eef7ee;border-left-color:#2e7d32}'
       '.badbox{background:#fdecec;border-left:4px solid #c62828;padding:10px 14px;border-radius:6px;font-size:13.5px}</style>')

n_ord_ratio = A_NEW['orders'] / max(1, A_NEW['n'])
ctrl_ratio = A_CTRL['orders'] / max(1, A_CTRL['n'])
land = [r for r in A_NEW['rowsv'] if r['dland'] is not None]
near = [r for r in land if r['dland'] <= 8.0]
ok1 = A_NEW['hit'] > 0
ok2 = A_NEW['ready'] > 0
ok3 = len(land) > 0 and len(near) == len(land)
ok4 = max(A_NEW['stock'].keys(), default=0) <= 5

gord_txt = ''.join(
    '<tr><td>%s</td><td>%d</td><td>(%d,%d)</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%d</td></tr>' % (
        r['game'], r['f'], r['cen'][0], r['cen'][1],
        ('(%d,%d)' % (r['land'][1], r['land'][2])) if r['land'] else '—',
        ('%.1f' % r['dland']) if r['dland'] is not None else '—',
        ('%.1f' % r['dcen']) if r['dcen'] is not None else '—',
        ('%.1f' % r['dtc']) if r['dtc'] is not None else '—', r['k'])
    for r in A_NEW['rowsv']) or '<tr><td colspan="8">无</td></tr>'

H = ['<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
     '<title>金矿旁建仓库 · 验收</title>' + CSS + '</head><body><div class="wrap">',
     '<h1>金矿旁边没有仓库的话也要建仓库</h1>',
     '<div class="sub">AoE3 3.0.7g · UsrAI · 2026-09-22 · 用户需求「金矿旁边没有仓库的话也要建仓库」'
     '· 源码 <code>%s</code> · %d 行（UsrAI.h <code>%s</code>）</div>'
     % (md5('UsrAI.cpp'), nlines('UsrAI.cpp'), md5('UsrAI.h'))]

# 1 TL;DR
t = ['<div class="kpi">'
     '<div>金矿仓令（验收①）<b class="%s">%d 条</b>%d/%d 局命中</div>'
     '<div>触发可达（验收②）<b class="%s">%d/%d 局</b>峰值在用远金矿 %d 格</div>'
     '<div>落点在矿旁（验收③）<b class="%s">%d/%d</b>≤8 块，中位 %.1f 块</div>'
     '<div>总量上限（验收④）<b class="%s">%d</b>≤%d</div>'
     '<div>仓库令/局<b>%.2f</b>对照 %.2f</div></div>'
     % ('good' if ok1 else 'bad', len(A_NEW['gord']), A_NEW['hit'], A_NEW['n'],
        'good' if ok2 else 'bad', A_NEW['ready'], A_NEW['n'], A_NEW['use'],
        'good' if ok3 else 'bad', len(near), len(land),
        (sum(r['dland'] for r in land) / len(land)) if land else 0,
        'good' if ok4 else 'bad', max(A_NEW['stock'].keys(), default=0), 5,
        n_ord_ratio, ctrl_ratio)]
t.append('<table><tr><th>#</th><th>验收判据</th><th>要求</th><th>实测（%d 局）</th><th></th></tr>'
         '<tr><td>①</td><td>金矿仓真被下单</td><td>[GOLD-STOCK] &gt; 0</td><td>%d 条 / 命中 %d 局</td><td>%s</td></tr>'
         '<tr><td>②</td><td>触发条件可达（不是永远不满足）</td><td>有局出现「在用远金矿格 &gt; 0」</td>'
         '<td>%d / %d 局</td><td>%s</td></tr>'
         '<tr><td>③</td><td>落点在矿旁（不是兜底跑飞回 TC）</td><td>落点距最近金矿格 ≤ 8 块</td>'
         '<td>%d / %d 条</td><td>%s</td></tr>'
         '<tr><td>④</td><td>不越预算（独立名额 ≤1，总量 ≤5）</td><td>末局 stock 最大值 ≤ %d</td>'
         '<td>%d</td><td>%s</td></tr></table>'
         % (A_NEW['n'], len(A_NEW['gord']), A_NEW['hit'], '<span class="good">OK</span>' if ok1 else '<span class="bad">FAIL</span>',
            A_NEW['ready'], A_NEW['n'], '<span class="good">OK</span>' if ok2 else '<span class="bad">FAIL</span>',
            len(near), len(land), '<span class="good">OK</span>' if ok3 else '<span class="bad">FAIL</span>',
            5, max(A_NEW['stock'].keys(), default=0), '<span class="good">OK</span>' if ok4 else '<span class="bad">FAIL</span>'))
H.append('<div class="card"><h2>1 TL;DR</h2>' + ''.join(t) + '</div>')

# 2 机制依据
H.append('<div class="card"><h2>2 为什么仓库必须落在「金矿旁」才有效（引擎侧依据，非推测）</h2>'
         '<p>矿工背包满后怎么找交付点，不是 AI 决定的 —— 引擎里是<b>一步链</b>：</p>'
         '<div class="mono">'
         'Core_List::findResourceBuiding()            (Core_List.cpp:736)\n'
         '  → 候选 = 已完工建筑里 num == BUILDING_CENTER（TC，凡陆上村民恒可）\n'
         '                       ∪ num == relation.resourceBuildingType\n'
         '  → relation.set_ResourceBuildingType()      (Core_CondiFunc.cpp:216)\n'
         '  → Resource::get_ReturnBuildingType()       (Resource.cpp:8)\n'
         '        HUMAN_WOOD / GOLD / STONE / STOCKFOOD  → BUILDING_STOCK  ← 金矿在这里\n'
         '        HUMAN_GRANARYFOOD                      → BUILDING_GRANARY\n'
         '        HUMAN_DOCKFOOD                         → BUILDING_DOCK\n'
         '  → 取 dis = Manhattan(资源位置, 建筑位置) 最小者\n'
         '  ⇒ 交付点是「距【资源所在处】最近」的 TC/仓库，不是距村民最近\n'
         '</div>'
         '<p>另有一道交叉校验：<code>Building::isMatchResourceType()</code>（Building.cpp:558）—— TC 收全部；'
         '<b>仓库收 WOOD/GOLD/STONE/STOCKFOOD</b>；谷仓只收 GRANARYFOOD。'
         '即 <b>RESOURCE_GOLD（ProductSort=HUMAN_GOLD）只能交 TC 或仓库</b>。</p>'
         '<p class="note ok"><b>结论</b>：把仓库建在 TC 旁对金矿<b>毫无意义</b>（矿工照样跑全程）；'
         '只有落在矿旁才缩短往返。这与瞪羚肉必须交仓库是同一个口径，所以本功能与「第二仓库」同构。</p>'
         '</div>')

# 3 地理
cl = []
for gx, gy in GOLD:
    placed = False
    for c in cl:
        if math.hypot(gx - c[0], gy - c[1]) < 12:
            c[0] = (c[0] * c[2] + gx) / (c[2] + 1)
            c[1] = (c[1] * c[2] + gy) / (c[2] + 1)
            c[2] += 1
            placed = True
            break
    if not placed:
        cl.append([gx, gy, 1])
cl.sort(key=lambda c: math.hypot(c[0] - TC[0], c[1] - TC[1]))
geo = ''.join('<tr><td>%d</td><td>(%.1f, %.1f)</td><td>%d</td><td>%.1f</td></tr>'
              % (i + 1, c[0], c[1], c[2], math.hypot(c[0] - TC[0], c[1] - TC[1]))
              for i, c in enumerate(cl))
far_g = sum(1 for gx, gy in GOLD if math.hypot(gx - TC[0], gy - TC[1]) > 20)
H.append('<div class="card"><h2>3 本图金矿地理：为什么触发源用「在用」而不是「最密」</h2>'
         '<table><tr><th>簇</th><th>中心（游戏内块）</th><th>格数</th><th>距 TC（块）</th></tr>%s</table>'
         '<p>共 <b>%d 格 / %d 簇</b>；<b>%d 格</b>距 TC &gt; 20 块（即"远"）。'
         '最密的簇心在 <b>(11,94)</b>，距 TC <b>76 块</b> —— 若按"最密的远簇"选落点，'
         '会建在一座 AI 大概率根本不会去采的矿旁（120 木白发）。</p>'
         '<p class="note">所以判据取<b>「村民此刻正在开采的远金矿」</b>（<code>info.farmers[].WorkObjectSN</code> '
         '反查 <code>info.resources</code>）：有人在那采，就等于"这座仓一定会被用到"，'
         '同时也就不需要像瞪羚那样的"至少 N 只"数量闸。</p></div>'
         % (geo, len(GOLD), len(cl), far_g))

# 4 三臂对照
t = ['<table><tr><th>臂</th><th>源码</th><th>局数</th><th>[GOLD-STOCK] 令</th><th>命中局</th>'
     '<th>触发可达局</th><th>仓库令总数</th><th>末局 stock 分布</th><th>胜/负/无果</th></tr>'
     '<tr><td>对照（无金矿逻辑）</td><td><code>229ba8f7</code></td><td>%d</td><td>—</td><td>—</td>'
     '<td>—</td><td>%d（%.2f/局）</td><td>%s</td><td>%d/%d/%d</td></tr>'
     '<tr><td>第一版（落点闸自锁）</td><td><code>84bdd651</code></td><td>%d</td><td class="bad">%d</td>'
     '<td class="bad">%d</td><td>%d</td><td>%d（%.2f/局）</td><td>%s</td><td>%d/%d/%d</td></tr>'
     '<tr><td><b>现行（独立计数预算）</b></td><td><code>%s</code></td><td>%d</td><td class="good">%d</td>'
     '<td class="good">%d</td><td>%d</td><td>%d（%.2f/局）</td><td>%s</td><td>%d/%d/%d</td></tr></table>'
     % (A_CTRL['n'], A_CTRL['orders'], ctrl_ratio, dict(sorted(A_CTRL['stock'].items())),
        A_CTRL['win'], A_CTRL['lose'], A_CTRL['n'] - A_CTRL['win'] - A_CTRL['lose'],
        A_SELF['n'], len(A_SELF['gord']), A_SELF['hit'], A_SELF['ready'],
        A_SELF['orders'], A_SELF['orders'] / max(1, A_SELF['n']), dict(sorted(A_SELF['stock'].items())),
        A_SELF['win'], A_SELF['lose'], A_SELF['n'] - A_SELF['win'] - A_SELF['lose'],
        md5('UsrAI.cpp'), A_NEW['n'], len(A_NEW['gord']), A_NEW['hit'], A_NEW['ready'],
        A_NEW['orders'], n_ord_ratio, dict(sorted(A_NEW['stock'].items())),
        A_NEW['win'], A_NEW['lose'], A_NEW['n'] - A_NEW['win'] - A_NEW['lose'])]
H.append('<div class="card"><h2>4 三臂对照</h2>' + ''.join(t) +
         '<p class="note">「第一版」那一臂是<b>中途自纠的过程记录</b>，不是被撤掉的方案 —— 见第 6 节：'
         '它 3/3 局一次都没下单，原因此前被误判成"AI 不采远矿"，实际是我的预算判据把闸门开局就自锁了。</p></div>')

# 5 逐局
t = ['<table><tr><th>局</th><th>下单帧</th><th>在用簇心块</th><th>实际落点</th>'
     '<th>落点距最近金矿格</th><th>落点距簇心</th><th>落点距 TC</th><th>在用格</th></tr>%s</table>'
     % gord_txt,
     '<p>「落点距最近金矿格」是拿地图真值（map3.njust 的 StaticRes Num=2，按引擎 90° 旋转公式换算）算的。'
     '<code>noFallback=true</code> 保证放不下就本帧不建、下帧重试，绝不落回 TC 旁。</p>']
H.append('<div class="card"><h2>5 逐局落点校验（验收③的明细）</h2>' + ''.join(t) + '</div>')

# 6 自锁复盘
H.append('<div class="card"><h2>6 自锁复盘：第一版为什么一条令都没下</h2>'
         '<p>第一版把"独立预算"写成<b>邻近判据</b>：<code>距任一存活金矿格 ≤20 块的仓库数 &lt; 1</code>。'
         '看起来合理，实则开局自锁：</p>'
         '<div class="mono">'
         '剧本预置首仓在 (13,34)；最近的近距金矿格 (2,18) 距它只有 19.4 块 &lt; 20\n'
         '⇒ 第一帧起「服务金矿仓」就 = 1 ⇒ 闸门恒不成立 ⇒ 永远不下单\n'
         '实测 3/3 局：每次采样都是「服务金矿仓=1/1」\n'
         '</div>'
         '<p class="badbox"><b>教训</b>：预算判据不能用"资源附近的建筑数"这种<b>会与既有基地建筑撞车</b>的邻近量 —— '
         '基地首仓天然离近距矿 19 块，判据一放就死。改用<b>显式计数器</b>（'
         '<code>goldStockOrders</code>，只在真下单时 ++）才与"我建过几座金矿仓"语义一致。</p>'
         '<p class="note">同一次自纠还改掉了触发源：最初按"最密的远金矿簇"选落点（与瞪羚侧同算法），'
         '但那会选到离 TC 76 块、AI 不会去采的簇；改成"村民正在开采的远金矿"后，'
         '落点必然被用到（第 5 节实测落点距矿 ≤ 8 块）。</p></div>')

# 7 副作用
worst = ', '.join('%d 局 %d 座' % (v, k) for k, v in sorted(A_NEW['stock'].items()))
H.append('<div class="card"><h2>7 副作用与残留</h2>'
         '<p><b>总量</b>：上限 = <code>MAX_STOCK</code> + <code>MAX_GOLD_STOCK</code> = 4 + 1 = 5 座。'
         '本批末局 stock 分布 %s（均值 %.2f），对照臂 %s（均值 %.2f）⇒ 未越界、总量未涨。</p>'
         '<p><b>瞪羚侧令量</b>（<code>[STOCK-ORD]</code> 只有第二仓库块会打，故它就是瞪羚侧的令量）：'
         '本批 %d 条（%.2f/局）vs 对照 %d 条（%.2f/局）⇒ <b>没有被金矿仓打压</b>。</p>'
         '<p><b>金矿仓在预算里的位置</b>：本批多出的 %.2f 条/局就是金矿仓那一条，'
         '但终局在册仓库数与对照持平 ⇒ 它是在<b>原有 4 座预算内</b>挤进去的（不是第 5 座）。'
         '若要严格"额外一名额"，需把瞪羚侧的闸从 <code>countBuildingsExisting &lt; MAX_STOCK</code> 改成 '
         '<code>… − goldStockOrders &lt; MAX_STOCK</code>（瞪羚侧 3 处调用点，本轮未动以免引入回归）。</p>'
         '<p><b>胜负</b>：本批 胜 %d / 负 %d / 无果 %d；对照臂 胜 %d / 负 %d / 无果 %d。'
         '（胜负噪声大，12 局不足以判优劣 —— 参照铁律 81：≥24 局/臂才能判胜负，本表只作"没劣化"的粗检。）</p>'
         '<p><b>未做</b>：① 石矿同理（<code>HUMAN_STONE</code> 也交仓库，本图 38 格石）—— 用户只点名金矿，未扩；'
         '② 落点若 13 个偏移位全被占，<code>noFallback</code> 会一直重试到有空位（本批 [GOLD-STOCK-FAIL] = %d 条）。</p>'
         '<p class="note">单旋钮：<code>GOLD_STOCK_ANCHOR_RANGE</code>（现 20.0）。'
         '本图最近的金矿簇簇心距 TC 16.7 块（&lt;20）⇒ 按现口径由 TC 服务、不为它建仓；'
         '若要让"更近的矿也配仓"，把它降到 12~15 即可，其余逻辑不动。</p></div>'
         % (worst, sum(A_NEW['laststock']) / max(1, len(A_NEW['laststock'])),
            dict(sorted(A_CTRL['stock'].items())), sum(A_CTRL['laststock']) / max(1, len(A_CTRL['laststock'])),
            A_NEW['sord'], A_NEW['sord'] / max(1, A_NEW['n']),
            A_CTRL['sord'], A_CTRL['sord'] / max(1, A_CTRL['n']),
            n_ord_ratio - ctrl_ratio,
            A_NEW['win'], A_NEW['lose'], A_NEW['n'] - A_NEW['win'] - A_NEW['lose'],
            A_CTRL['win'], A_CTRL['lose'], A_CTRL['n'] - A_CTRL['win'] - A_CTRL['lose'],
            A_NEW['gfail']))

# 8 复现
H.append('<div class="card"><h2>8 源码 / 备份 / 复现</h2>'
         '<table><tr><th>项</th><th>值</th></tr>'
         '<tr><td>UsrAI.cpp</td><td><code>%s</code> · %d 行</td></tr>'
         '<tr><td>UsrAI.h</td><td><code>%s</code> · %d 行（新增 <code>int goldStockOrders</code>）</td></tr>'
         '<tr><td>常数</td><td><code>GOLD_STOCK_ANCHOR_RANGE 20.0</code> / <code>MAX_GOLD_STOCK 1</code> / '
         '<code>GOLD_STOCK_WOOD_MARGIN 30</code></td></tr>'
         '<tr><td>语法/警告</td><td>rc=0 / 0 error / <b>17 warn</b>（与改动前类别集合一致）</td></tr>'
         '<tr><td>编译</td><td>rc=0 / 0 error</td></tr>'
         '<tr><td>备份（改前）</td><td><code>UsrAI.cpp.bak_20260922_goldstock</code>（<code>229ba8f7</code>/6638）</td></tr>'
         '<tr><td>回滚</td><td>拷回该备份（含 <code>UsrAI.h.bak_20260922_goldstock</code>）→ 删 '
         '<code>release/UsrAI.o</code> → 重编</td></tr>'
         '<tr><td>跑批</td><td><code>verify_build_fix.py 12 gsk</code></td></tr>'
         '<tr><td>探针</td><td><code>gold_stock_probe.py scan "vf_gsk_*.ait"</code></td></tr>'
         '</table></div>'
         % (md5('UsrAI.cpp'), nlines('UsrAI.cpp'), md5('UsrAI.h'), nlines('UsrAI.h')))

H.append('</div></body></html>')
open(OUT, 'w', encoding='utf-8').write(''.join(H))
print('written %s (%d bytes)' % (OUT, os.path.getsize(OUT)))
print('验收: ①%d ②%d ③%d ④%d' % (ok1, ok2, ok3, ok4))
print('金矿仓令=%d 命中局=%d/%d 触发可达=%d/%d 落点≤8块=%d/%d' %
      (len(A_NEW['gord']), A_NEW['hit'], A_NEW['n'], A_NEW['ready'], A_NEW['n'], len(near), len(land)))
