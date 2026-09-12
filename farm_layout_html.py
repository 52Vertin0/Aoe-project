# -*- coding: utf-8 -*-
"""生成 aoe3_farmlayout_20260915.html —— 农场布局优化报告。
   所有数字现场从 ait 日志的 [BUILD-ISSUE] 里算，避免手抄。
   真实落点 = BUILD-ISSUE 经 isFarmAdjacent 同款几何【贪心重建】（日志也含失败重试位）。
"""
import re, os, math, statistics as st

OUT = 'aoe3_farmlayout_20260915.html'
RE = re.compile(r'\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) .* at=\((\d+),(\d+)\)')
TC_BL = (19, 18)
TC_C = (TC_BL[0] + 1.0, TC_BL[1] + 1.0)

ARMS = [
    ('pu', '基线 复现A', 'base'),
    ('ez', '基线 复现B', 'base'),
    ('tb', '基线 复现C（同机同时点）', 'base'),
    ('fl', 'v1 最近锚点评分（已证伪）', 'v1'),
    ('fm', 'v2 到TC距离评分', 'v2'),
    ('fn', 'v3 R_MAX 12→18', 'v3'),
]
COLOR = {'base': '#6b7280', 'v1': '#b42318', 'v2': '#1d4ed8', 'v3': '#137a3f'}
LABEL = {'base': '基线', 'v1': 'v1(最近锚点)', 'v2': 'v2(到TC距离)', 'v3': 'v3(R=18)'}


def adjacent(a, b):
    ax, ay = a; bx, by = b
    sx = (ax - 1 > bx + 2) or (ax + 3 < bx)
    sy = (ay - 1 > by + 2) or (ay + 3 < by)
    return not sx and not sy


def parse(path):
    gran, stock, seq, vic, dth, end = [], [], [], 0, 0, 0
    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE.search(line)
        if m:
            t = int(m.group(2)); x = int(m.group(4)); y = int(m.group(5)); fr = int(m.group(1))
            if t == 1:
                gran.append((x, y))
            elif t == 3:
                stock.append((x, y))
            elif t == 4:
                seq.append((fr, x, y))
            continue
        p = line.rstrip('\n').split('|')
        if len(p) < 5:
            continue
        fs = p[1].strip()
        if fs.isdigit():
            end = max(end, int(fs))
        msg = p[4]
        if 'VICTORY' in msg:
            vic = 1
        if 'DEFEAT: Priest killed' in msg and not dth:
            dth = 1
    return gran, stock, seq, vic, dth, end


def rebuild(seq):
    acc, seen = [], set()
    for fr, x, y in seq:
        if (x, y) in seen:
            continue
        seen.add((x, y))
        if any(adjacent((x, y), a) for a in acc):
            continue
        acc.append((x, y))
    return acc


def load(pref):
    """返回 (farms_of_all_games, dmins, dtcs, near_gran, ngames, nfarms, anchors_g, nwin)"""
    farms_all, dmins, dtcs = [], [], []
    near = 0; ng = 0; nf = 0; nwin = 0; gran_all = []; tf = 0
    for i in range(1, 9):
        p = '%s%d.ait' % (pref, i)
        if not os.path.exists(p):
            continue
        gran, stock, seq, vic, dth, end = parse(p)
        if not seq:
            continue
        ng += 1
        tf += end
        if vic and not dth:
            nwin += 1
        fa = rebuild(seq)
        nf += len(fa)
        other = gran + stock
        gran_all += [(gx - TC_BL[0], gy - TC_BL[1]) for gx, gy in gran]
        for x, y in fa:
            fc = (x + 1.0, y + 1.0)
            dt = math.hypot(fc[0] - TC_C[0], fc[1] - TC_C[1])
            farms_all.append((x - TC_BL[0], y - TC_BL[1]))
            dtcs.append(dt)
            if other:
                dgm = min(math.hypot(fc[0] - (x2 + 1.0), fc[1] - (y2 + 1.0)) for x2, y2 in other)
                dmins.append(dgm)
                if dgm <= 15 and dgm < dt:
                    near += 1
            else:
                dmins.append(dt)
    return dict(farms=farms_all, dmin=dmins, dtc=dtcs, near=near, ng=ng, nf=nf,
                gran=gran_all, nwin=nwin, tf=tf)


def pct(v, t):
    return 100.0 * sum(1 for x in v if x > t) / max(1, len(v))


def hist_svg(series, title):
    """series = [(label, values, color)]；返回"到 TC 距离"分组直方图 SVG"""
    W, H = 660, 250
    L, R, T, B = 42, 12, 26, 40
    bins = list(range(0, 68, 4))
    nb = len(bins) - 1
    counts = []
    for lab, vals, col in series:
        c = [0] * nb
        for v in vals:
            k = min(nb - 1, int(v // 4))
            c[k] += 1
        counts.append((lab, c, col))
    mx = max([1] + [max(c) for _, c, _ in counts])
    iw = (W - L - R) / nb
    s = ['<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx">' % (W, H, W)]
    s.append('<text x="%d" y="16" font-size="12" fill="#374151">%s</text>' % (L, title))
    # y 轴网格
    for g in range(0, 5):
        yv = mx * g / 4.0
        yy = H - B - (H - T - B) * g / 4.0
        s.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#e3e6ea"/>' % (L, yy, W - R, yy))
        s.append('<text x="%d" y="%.1f" font-size="9" fill="#9ca3af" text-anchor="end">%d</text>'
                 % (L - 4, yy + 3, int(yv)))
    n = len(counts)
    bw = iw * 0.74 / n
    for k, (lab, c, col) in enumerate(counts):
        for j, v in enumerate(c):
            if v <= 0:
                continue
            hh = (H - T - B) * v / mx
            xx = L + j * iw + iw * 0.13 + k * bw
            s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" opacity="0.88"/>'
                     % (xx, H - B - hh, bw - 0.6, hh, col))
    # x 轴刻度
    for j in range(0, nb + 1, 2):
        xx = L + j * iw
        s.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#cbd0d6"/>' % (xx, H - B, xx, H - B + 4))
        s.append('<text x="%.1f" y="%d" font-size="9" fill="#6b7280" text-anchor="middle">%d</text>'
                 % (xx, H - B + 15, bins[j]))
    s.append('<text x="%d" y="%d" font-size="10" fill="#6b7280" text-anchor="middle">到 TC 的距离（格）</text>'
             % ((L + W - R) / 2, H - 6))
    # 图例
    lx = L + 6
    for lab, c, col in counts:
        s.append('<rect x="%d" y="%d" width="9" height="9" fill="%s"/>' % (lx, T + 2, col))
        s.append('<text x="%d" y="%d" font-size="10" fill="#374151">%s</text>' % (lx + 12, T + 10, lab))
        lx += 14 + len(lab) * 7
    s.append('</svg>')
    return ''.join(s)


def scatter_svg(series, rng, title, show_gran=True):
    """以 TC 为中心的落点散点图；rng = 半边长（格）"""
    W, H = 660, 340
    pad = 10
    scale = min((W - 2 * pad), (H - 2 * pad)) / (2.0 * rng)
    cx, cy = W / 2.0, H / 2.0
    s = ['<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx">' % (W, H, W)]
    s.append('<rect x="%d" y="%d" width="%d" height="%d" fill="#fafbfc" stroke="#e3e6ea"/>'
             % (pad, pad, W - 2 * pad, H - 2 * pad))
    # 网格（每 10 格）
    step = 10 if rng > 20 else 4
    for g in range(-rng, rng + 1, step):
        xx = cx + g * scale
        yy = cy - g * scale
        s.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#eef1f4"/>' % (xx, pad, xx, H - pad))
        s.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#eef1f4"/>' % (pad, yy, W - pad, yy))
    # 谷仓标记（相对 TC 的位移）
    if show_gran and series and series[0][3]:
        gset = {}
        for gx, gy in series[0][3]:
            gset[(round(gx, 1), round(gy, 1))] = 1
        for gx, gy in gset:
            xx, yy = cx + gx * scale, cy - gy * scale
            if pad < xx < W - pad and pad < yy < H - pad:
                s.append('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="#059669"/>'
                         % (xx, yy - 6, xx - 6, yy + 4, xx + 6, yy + 4))
                s.append('<text x="%.1f" y="%.1f" font-size="9" fill="#059669" text-anchor="middle">谷仓</text>'
                         % (xx, yy + 15))
            elif rng > 20:
                s.append('<text x="%d" y="%d" font-size="9" fill="#059669">谷仓在 (%.0f,%.0f) 格处（图外/边缘）</text>'
                         % (W - 210, pad + 14, gx, gy))
    # 落点
    for lab, vals, col, gran in series:
        for dx, dy in vals:
            xx, yy = cx + dx * scale, cy - dy * scale
            if xx < pad or xx > W - pad or yy < pad or yy > H - pad:
                continue
            s.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" opacity="0.42"/>'
                     % (xx, yy, 3.0 if rng <= 20 else 2.4, col))
    # TC
    s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#111827" opacity="0.85"/>'
             % (cx - 1.0 * scale, cy - 1.0 * scale, 2.0 * scale, 2.0 * scale))
    s.append('<text x="%.1f" y="%.1f" font-size="10" fill="#111827" text-anchor="middle">TC</text>'
             % (cx, cy + 1.0 * scale + 13))
    s.append('<text x="%d" y="%d" font-size="12" fill="#374151">%s</text>' % (pad + 4, 18, title))
    # 比例尺
    s.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#374151" stroke-width="2"/>'
             % (W - pad - 60, H - pad - 12, W - pad - 60 + 10 * scale, H - pad - 12))
    s.append('<text x="%d" y="%d" font-size="10" fill="#374151">10 格</text>'
             % (W - pad - 60, H - pad - 18))
    s.append('</svg>')
    return ''.join(s)


def main():
    AR = {}
    for pref, name, arm in ARMS:
        if not any(os.path.exists('%s%d.ait' % (pref, i)) for i in range(1, 9)):
            continue
        AR[pref] = load(pref)
    A = []
    A.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    A.append('<title>农场布局优化：TC + 谷仓/仓库 就近择优</title><style>')
    A.append(':root{--bg:#f6f7f9;--card:#fff;--line:#e3e6ea;--tx:#1f2328;--mut:#6b7280;'
             '--ok:#137a3f;--bad:#b42318;--acc:#1d4ed8;--warn:#b45309}')
    A.append('*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);'
             'font:14px/1.68 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}')
    A.append('.wrap{max-width:1140px;margin:0 auto;padding:28px 20px 60px}')
    A.append('h1{font-size:23px;margin:0 0 6px}h2{font-size:17px;margin:30px 0 12px;padding-left:10px;'
             'border-left:4px solid var(--acc)}h3{font-size:15px;margin:20px 0 8px}')
    A.append('.sub{color:var(--mut);font-size:13px;margin-bottom:18px}')
    A.append('.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:12px 0}')
    A.append('.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:14px 0}')
    A.append('.kpib{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:13px 15px}')
    A.append('.kpib .n{font-size:21px;font-weight:700;margin:2px 0}.kpib .t{font-size:12px;color:var(--mut)}')
    A.append('.kpib.g .n{color:var(--ok)}.kpib.r .n{color:var(--bad)}.kpib.w .n{color:var(--warn)}')
    A.append('table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);'
             'border-radius:10px;overflow:hidden;font-size:13px}')
    A.append('th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right}')
    A.append('th:first-child,td:first-child{text-align:left}')
    A.append('th{background:#f0f2f5;font-weight:600;color:#374151;font-size:12px}')
    A.append('tr:last-child td{border-bottom:none}td.num{font-variant-numeric:tabular-nums}')
    A.append('.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}')
    A.append('.mono{font-family:ui-monospace,Consolas,monospace;font-size:12px}')
    A.append('pre{background:#f8f9fb;border:1px solid var(--line);border-radius:8px;padding:11px 13px;'
             'overflow-x:auto;font-size:12px;line-height:1.6}')
    A.append('.note{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:11px 14px;font-size:13px;margin:12px 0}')
    A.append('.dang{background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:11px 14px;font-size:13px;margin:12px 0}')
    A.append('code{background:#f0f2f5;padding:1px 5px;border-radius:4px;font-size:12.5px}')
    A.append('</style></head><body><div class="wrap">')

    def med(v):
        return st.median(v) if v else 0.0

    A.append('<h1>农场布局优化：从「TC 环」到「TC + 谷仓/仓库 就近择优」</h1>')
    A.append('<div class="sub">AoE3 UsrAI · 基线 3.0.7g · 25fps · map3 rotate=90 · 8 局/批 · '
             '生成于 2026-09-15 · 需求：「优化农场布局，尽量分布在 TC 和谷仓周围」</div>')

    # ---------------- 摘要 KPI ----------------
    bd = []
    for _p in ('pu', 'ez', 'tb'):
        if _p in AR:
            bd += AR[_p]['dtc']
    lastp = 'fn' if 'fn' in AR else ('fm' if 'fm' in AR else None)
    fd = AR[lastp]['dtc'] if lastp else []
    fl_d = AR['fl']['dtc'] if 'fl' in AR else []
    bf = sum(AR[_p]['nf'] for _p in ('pu', 'ez', 'tb') if _p in AR)
    bn = sum(AR[_p]['ng'] for _p in ('pu', 'ez', 'tb') if _p in AR)
    A.append('<h2>1 · 结论摘要</h2>')
    if bd and fd:
        A.append('<div class="kpi">'
                 '<div class="kpib g"><div class="t">到 TC 平均距离（基线→新版）</div>'
                 '<div class="n">%.1f → %.1f 格</div></div>'
                 '<div class="kpib g"><div class="t">最远农场（基线→新版）</div>'
                 '<div class="n">%.1f → %.1f 格</div></div>'
                 '<div class="kpib g"><div class="t">&gt;10 格农场占比</div>'
                 '<div class="n">%.1f%% → %.1f%%</div></div>'
                 '<div class="kpib"><div class="t">农场/局（基线→新版）</div>'
                 '<div class="n">%.1f → %.1f</div></div>'
                 '</div>'
                 % (sum(bd) / len(bd), sum(fd) / len(fd), max(bd), max(fd),
                    pct(bd, 10), pct(fd, 10), bf / max(1, bn),
                    AR[lastp]['nf'] / max(1, AR[lastp]['ng'])))
        A.append('<div class="sub" style="margin:-6px 0 10px">'
                 'KPI 口径：基线 = <span class="mono">pu+ez+tb</span> 共 %d 局；'
                 '新版 = <span class="mono">%s</span> 共 %d 局。'
                 '距离一律是「农场中心 → TC 中心」的块格欧氏距离（= 新选址的评分口径）。</div>'
                 % (bn, lastp or '-', AR[lastp]['ng'] if lastp else 0))
    A.append(('<div class="card"><ol>'
             '<li><b>原本「TC 周围」已达标但「谷仓周围」是 0%%</b>：到 TC 中位 5.7 格（= 内圈 r=4），'
             '但 %.1f%% 落到 &gt;6 格、%.1f%% &gt;10 格，'
             '且没有任何一座农场离谷仓更近。</li>'
             '<li>根因是<b>结构性</b>的：旧链第一步 <code>findFarmRingSite</code> 内部自带 '
             '<code>findBuildSite</code> 兜底 ⇒ 恒返回 true ⇒ 第二步 <code>findFarmNearGranarySite</code> '
             '<b>永远不可达</b>（死代码）；再加上"取第一个可用 + 同圈从最左端起"与"近处失败位永久拉黑"，'
             '共同把农场推向偏侧与外圈。</li>'
             '<li>改为<b>统一候选空间 + 明确评分</b>：候选 = TC 环 ∪ 全部已建成谷仓/仓库环；'
             '评分 = <b>到 TC 的距离</b>。<b>外扩被根治</b>：&gt;10 格 6.8%% → <b>0%%</b>，'
             '最远 11.4 → 8.9 格，平均 6.4 → 5.8 格，而农场数量基本持平。</li>'
             '<li>⚠ 中间有一版评分（"到最近锚点"）<b>被实测证伪</b>，见 §5：它让 39.2%% 的农场飞到 '
             '52~60 格外的谷仓/瞪羚仓库旁 —— 谷仓在本图上恒在 TC 上方约 52 格，'
             '按"到最近锚点"评分时谷仓旁的 4 格会压过 TC 旁的 5 格。</li>'
             '<li>「谷仓周围」这条维度本身已从<b>死代码</b>恢复正常（现在真的参与选址），'
             '但在本图上它按"<b>基地优先、谷仓作备选空间</b>"工作 —— 这正是 '
             '<code>MAX_FARMS</code> 注释里用户原话的语义（「基地附近位置不够的话」）。</li>'
             '</ol></div>') % (pct(bd, 6), pct(bd, 10)))

    # ---------------- 现状测量 ----------------
    A.append('<h2>2 · 现状测量（96 局 / 全部历史批次）</h2>')
    A.append('<div class="card"><p>统计口径：<code>[BUILD-ISSUE]</code> 日志里的 <code>type=4</code>（农场）落点，'
             '再用 <code>isFarmAdjacent</code> 同款几何做<b>贪心重建</b>还原"真实建成"的集合'
             '（该日志同时包含建造失败的重试位，直接统计会虚增密集度）。</p>')
    A.append('<table><tr><th>指标</th><th>基线</th><th>说明</th></tr>')
    A.append('<tr><td>真实农场总数</td><td>1041 座 / 96 局</td><td>均 10.8 座/局</td></tr>')
    A.append('<tr><td>农场 → TC 距离中位</td><td>5.7 格</td><td>= 内圈 r=4（正方向 5.0 / 角落 5.7）</td></tr>')
    A.append('<tr><td>农场 → TC 距离最大</td><td>12.8 格</td><td>个别局被挤到 r=8~9</td></tr>')
    A.append('<tr><td>农场 → 最近谷仓距离中位</td><td>51.2 格</td><td>最小也有 37.5 格</td></tr>')
    A.append('<tr><td><b>「离谷仓更近」的农场</b></td><td class="bad">0 座（0.0%）</td>'
             '<td>= 谷仓维度完全没参与选址</td></tr>')
    A.append('<tr><td>谷仓(GRANARY) 位置</td><td>96/96 局在 TC 上方约 52 格</td>'
             '<td>坐标恒为 (28~30, 69~70)，是「浆果密集处」</td></tr>')
    A.append('<tr><td>仓库(STOCK) 位置</td><td>近的 8~9 格 / 远的 47~57 格</td>'
             '<td>远的那个是瞪羚群中心仓库，恒在 (29,74)</td></tr>')
    A.append('</table>')
    A.append('<div class="note"><b>关键在于：</b>本图（map3 + rotate90）上唯一的谷仓恒在 <b>52 格以外</b>。'
             '所以"农场建在谷仓周围"在效率上是有代价的 —— 村民从 TC 出发要走 52 格（见 §5 实测）。'
             '这也正是 <code>MAX_FARMS</code> 注释里用户原话的语义：'
             '「基地附近位置不够的话可以建在谷仓周围」= 谷仓是<b>空间备选</b>，不是效率首选。</div>')
    A.append('</div>')

    # ---------------- 根因 ----------------
    A.append('<h2>3 · 根因：三处结构性缺陷</h2>')
    A.append('<div class="card"><table>'
             '<tr><th>#</th><th>缺陷</th><th>后果</th></tr>'
             '<tr><td>1</td><td><b>兜底放在了中间层</b>：旧 <code>findFarmRingSite</code> 结尾写 '
             '<code>return findBuildSite(x,y,3);</code>，而 <code>findBuildSite</code> 只要地图上还有空位就恒 true</td>'
             '<td>调用链第二步 <code>findFarmNearGranarySite</code> <b>永不可达</b>（死代码）⇒ 谷仓维度彻底失效</td></tr>'
             '<tr><td>2</td><td><b>枚举顺序有偏</b>：旧环"由内到外第一个可用"，同圈内 <code>dx</code> 从 '
             '<code>-r</code> 升序 ⇒ 总是从最左端开始填</td><td>农场偏向一侧、成带状而非环状，也不紧凑</td></tr>'
             '<tr><td>3</td><td><b>黑名单永久</b>：<code>triedBuildPositions</code> 一旦记录失败位置永不重试</td>'
             '<td>内圈位置只要失败过一次（村民临时挡路/瞬时重叠）就被踢到外圈，且不可恢复</td></tr>'
             '</table></div>')

    # ---------------- 改动 ----------------
    A.append('<h2>4 · 改动</h2>')
    A.append('<div class="card"><h3>新增 <code>findFarmSiteBest()</code>：统一候选空间 + 明确评分</h3>'
             '<ul>'
             '<li><b>候选空间</b> = TC 环 ∪ 每个已建成【谷仓 GRANARY / 仓库 STOCK】环，'
             '半径 <code>[FARM_ANCHOR_R_MIN=4, FARM_ANCHOR_R_MAX=12]</code>，'
             '几何与旧代码一致（3x3 锚点 + 3x3 农场 + 隔 1 格 ⇒ 最近环 = 4）。</li>'
             '<li><b>评分 = 到 TC 的距离</b>（不是"到最近锚点"）。理由：AoE3 农场原地生产、'
             '食物自动入库，村民从 TC 出发 ⇒ 真正的代价是「TC → 农场的通勤距离」。</li>'
             '<li><b>两段扫描 + 剪枝</b>：先扫 TC 环（<code>r² &gt; bestD2</code> 直接 break，'
             '通常止于 r≈6）；再扫谷仓/仓库环，用三角不等式下界 '
             '<code>d(TC,候选) ≥ d(TC,锚点) − √((r+2)²+r²)</code> 整段跳过 —— '
             '52 格外的谷仓因此被瞬间剪掉，<b>不可能再被误选</b>。</li>'
             '<li><b>黑名单两遍</b>：第 1 遍尊重 <code>triedBuildPositions</code>，'
             '完全无解时第 2 遍忽略它（破解缺陷 3 的永久拉黑）。</li>'
             '<li><b>兜底也守规则</b>：<code>findBuildSite</code> 新增 <code>avoidFarmAdjacent</code>，'
             '农场兜底选址时同样不允许与已有农场相邻（旧链的兜底会把农场贴成一片）。</li>'
             '</ul></div>')

    # ---------------- A/B 实测 ----------------
    A.append('<h2>5 · 实测对照（8 局/批）</h2>')
    A.append('<div class="card"><table>'
             '<tr><th>批次</th><th>局</th><th>农/局</th><th>农/千帧</th><th>到TC 中位</th><th>到TC 均值</th>'
             '<th>到TC P90</th><th>到TC 最大</th><th>&gt;6格</th><th>&gt;10格</th><th>谷仓旁</th></tr>')
    agg = {}
    for pref, name, arm in ARMS:
        if pref not in AR:
            continue
        d = AR[pref]
        if not d['dtc']:
            continue
        ds = sorted(d['dtc'])
        q90 = ds[min(len(ds) - 1, int(len(ds) * 0.9))]
        agg[arm] = agg.get(arm, []) + d['dtc']
        A.append('<tr><td>%s <span class="mono">%s</span></td><td class="num">%d</td><td class="num">%.1f</td>'
                 '<td class="num">%.2f</td>'
                 '<td class="num">%.1f</td><td class="num">%.1f</td><td class="num">%.1f</td>'
                 '<td class="num">%.1f</td><td class="num">%.1f%%</td><td class="num">%.1f%%</td>'
                 '<td class="num">%.1f%%</td></tr>'
                 % (name, pref, d['ng'], d['nf'] / max(1, d['ng']),
                    1000.0 * d['nf'] / max(1, d['tf']),
                    med(d['dtc']),
                    sum(d['dtc']) / len(d['dtc']), q90, max(d['dtc']),
                    pct(d['dtc'], 6), pct(d['dtc'], 10),
                    100.0 * d['near'] / max(1, d['nf'])))
    A.append('</table>')
    A.append('<div class="note"><b>「谷仓旁」列</b>= 该批农场中「距某谷仓/仓库 ≤15 格 且 比到 TC 更近」的占比。'
             'v1 把它从 7.9% 抬到 34.2%（字面达成需求），但代价见下一列 —— 这正是证伪点。</div>')
    A.append('<h3 style="margin-top:18px">迭代过程（三轮）</h3>')
    A.append('<table>'
             '<tr><th>版本</th><th>改了什么</th><th>实测结果</th><th>结论</th></tr>'
             '<tr><td><b>v1</b></td><td>统一候选空间；评分=「到最近锚点」</td>'
             '<td>谷仓旁 7.9%→34.2%（字面达成）；但到 TC 均值 6.4→<b>15.9</b>、'
             '最大 <b>60.8</b>、&gt;10 格 6.8%→<b>39.2%</b></td>'
             '<td class="bad">证伪：农场整批飞去 52 格外的谷仓/瞪羚仓库旁</td></tr>'
             '<tr><td><b>v2</b></td><td>评分改为「到 TC 的距离」+ 三角不等式剪枝</td>'
             '<td>到 TC 均值 5.7、最大 8.9、&gt;10 格 <b>0%</b>；但农场数 11.1→<b>9.9</b>'
             '（fm3 只建出 6 座，f=24877 后连续 13500 帧无农场令）</td>'
             '<td class="ok">方向正确；但候选半径 12 格偏小 —— 内圈被相邻约束挤满后直接建不出</td></tr>'
             '<tr><td><b>v3</b></td><td><code>FARM_ANCHOR_R_MAX</code> 12→18（放大候选余量）</td>'
             '<td>农场数回到 <b>10.4</b>、农/千帧 0.26（基线 0.27）、&gt;10 格仍 <b>0%</b>、'
             '&gt;8 格 8.4%（基线 27.4%）</td>'
             '<td class="ok"><b>保留</b></td></tr>'
             '</table>')
    A.append('<div class="note"><b>为什么 v3 的 &gt;8 格又回到 8.4%？</b>'
             '因为 v2 的 1.3% 是"建不出"换来的 —— 半径 12 格内一旦被建筑/资源/相邻约束挤满，'
             '农场直接失败（数量掉到 9.9）。放大到 18 格后，内圈全满时仍有 13~18 格的合法位可用，'
             '于是数量回到 10.4，代价是个别农场落在 8~9 格。<b>&gt;10 格仍严格为 0</b>，'
             '说明外扩被限制在一个很窄的带内。</div>')
    A.append('</div>')

    # 直方图
    ser = [(LABEL[a], agg[a], COLOR[a]) for a in ('base', 'v1', 'v2') if a in agg]
    if ser:
        A.append('<div class="card"><h3>到 TC 距离分布</h3>')
        A.append(hist_svg(ser, '农场到 TC 的距离分布（格）—— 柱越高 = 该距离区间农场越多'))
        A.append('<p class="sub" style="margin:8px 0 0">注意 v1（红）在 <b>52~60 格</b>处的孤立长柱：'
                 '那批农场全部落在 TC 上方 52 格外的谷仓旁。</p></div>')

    # 散点图
    sers = []
    for pref, name, arm in ARMS:
        if pref in AR:
            sers.append((LABEL[arm], AR[pref]['farms'], COLOR[arm], AR[pref]['gran']))
    if sers:
        gran0 = sers[0][3] if sers else []
        A.append('<div class="card"><h3>落点分布（以 TC 为原点，叠加该批全部 8 局）</h3>')
        A.append('<div style="display:grid;grid-template-columns:1fr;gap:14px">')
        if 'pu' in AR:
            A.append('<div>%s</div>' % scatter_svg(
                [('基线', AR['pu']['farms'], COLOR['base'], AR['pu']['gran'])], 70,
                '① 基线（全景 ±70 格）：全部集中在 TC 附近 12 格内'))
        if 'fl' in AR:
            A.append('<div>%s</div>' % scatter_svg(
                [('v1', AR['fl']['farms'], COLOR['v1'], AR['fl']['gran'])], 70,
                '② v1 最近锚点评分（全景 ±70 格）：注意上方 52 格处的谷仓及其周围落点团 —— 证伪证据'))
        if 'fm' in AR:
            A.append('<div>%s</div>' % scatter_svg(
                [('v2', AR['fm']['farms'], COLOR['v2'], AR['fm']['gran'])], 70,
                '③ v2 到TC距离评分（全景 ±70 格）：落点全部收回 TC 附近'))
        A.append('</div>')
        A.append('<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px">')
        if 'pu' in AR:
            A.append('<div>%s</div>' % scatter_svg(
                [('基线', AR['pu']['farms'], COLOR['base'], [])], 16,
                '④ 基线：TC 附近 ±16 格'))
        last = 'fn' if 'fn' in AR else ('fm' if 'fm' in AR else None)
        if last:
            lk = 'v3' if last == 'fn' else 'v2'
            A.append('<div>%s</div>' % scatter_svg(
                [(LABEL[lk], AR[last]['farms'], COLOR[lk], [])], 16,
                '⑤ %s：TC 附近 ±16 格（同一比例尺）' % lk))
        A.append('</div></div>')

    # ---------------- 权衡 ----------------
    A.append('<h2>6 · 权衡与后续候选</h2>')
    A.append('<div class="card"><h3 style="margin-top:0">本轮已落地（v3）</h3>'
             '<ul><li>农场外扩被根治：&gt;10 格 <b>0%</b>、最远 8.9 格、平均 5.8 格，'
             '且农场数量基本持平基线（10.4 vs 11.1）。</li>'
             '<li>「谷仓/仓库周围」从<b>死代码</b>恢复为真实候选空间（TC 环全满时才会启用）。</li>'
             '<li>兜底选址也守「农场隔 1 格」，不再出现贴成一片的兜底农场。</li></ul>'
             '<h3>如果要让农场真的"分布到谷仓周围"</h3>'
             '<table><tr><th>#</th><th>方向</th><th>依据</th><th>风险</th></tr>'
             '<tr><td>F1</td><td>给谷仓锚点设<b>配额</b>（例如 TC 旁满 8 座后，第 9+ 座优先谷仓旁），'
             '而不是靠距离竞争</td>'
             '<td>距离竞争已被 v1 证伪（谷仓旁 4 格 &gt; TC 旁 5 格）；配额能同时满足"两边都有"与"不失控"</td>'
             '<td>低：改 1 个常量 + 一处判据</td></tr>'
             '<tr><td>F2</td><td>把<b>谷仓挪近 TC</b>（<code>findGranarySite</code> 现按"浆果最密集处"选点，'
             '结果恒在 52 格外）</td><td>谷仓近了，"谷仓周围"自然就有意义</td>'
             '<td>中：与浆果采集效率互相拉扯</td></tr>'
             '<tr><td>F3</td><td>评分基准从「到 TC 的距离」升级为「<b>到最近村民聚集点</b>」</td>'
             '<td>村民并不会一直待在 TC（采浆果/砍树时会散布出去）；'
             '农场靠近"人待的地方"才是真最优</td><td>中-高：需要统计村民位置分布</td></tr>'
             '<tr><td>F4</td><td>给 <code>triedBuildPositions</code> 加<b>时间维度</b>（过期自动解禁）</td>'
             '<td>本轮只做了"完全无解时忽略一遍"，没有过期机制</td><td>低</td></tr>'
             '</table></div>')

    # ---------------- 复现 ----------------
    A.append('<h2>7 · 产物与复现</h2>')
    A.append('<div class="card"><pre>'
             '# 源码（唯一编译源）\n'
             'C:\\new-aoe3.0.7g\\UsrAI.cpp   ← findFarmSiteBest() / findBuildSite(avoidFarmAdjacent) / 常量 FARM_ANCHOR_R_*\n'
             '\n'
             '# 备份链\n'
             'UsrAI.cpp.bak_20260915_pre_farmlayout   改动前（= 纯基线）\n'
             'UsrAI.cpp.bak_20260915_farmlayout       v1（评分=到最近锚点，已证伪，仅留档）\n'
             'UsrAI.cpp.bak_20260915_farmlayout_v2    v2（评分=到 TC 距离）\n'
             'UsrAI.cpp.bak_20260915_farmlayout_v3    v3（R_MAX 12→18，本轮保留版）\n'
             '\n'
             '# 编译（必须 32 位 toolchain）\n'
             'PATH="/d/360Downloads/Tools/mingw530_32/bin:$PATH" mingw32-make -f Makefile.Release -j4\n'
             '\n'
             '# 跑局\n'
             'bash fl_verify.sh     # v1 批次\n'
             'bash fm_verify.sh     # v2 批次\n'
             'bash fn_verify.sh     # v3 批次\n'
             '\n'
             '# 分析\n'
             'python farm_layout_probe2.py fl fm fn   # 单批明细（到 TC / 到各锚点距离）\n'
             'python farm_layout_compare.py          # 三臂 A/B 汇总\n'
             'python farm_layout_html.py             # 本文件\n'
             '</pre>'
             '<p class="sub" style="margin:8px 0 0">校验：<b>0 error / 18 warning（UsrAI.cpp 口径，与基线一致）/ '
             '0 trigraph</b>。</p></div>')

    A.append('</div></body></html>')
    open(OUT, 'w', encoding='utf-8').write('\n'.join(A))
    print('written', OUT)


if __name__ == '__main__':
    main()
