#!/usr/bin/env python3
# 检查：① 反攻前军队是否集结在同处附近且不重叠 ② 反攻路线是否相近（抱团）③ 是否会被海隔开
# 两段：集结期 frame<33000（COUNTER_ATTACK_FORCE_TIME）vs 反攻期 >=33000。只统计 n>=峰值50% 的有效桶。
import json, re, math, statistics, os, random
from collections import defaultdict

BL = 35.777
MAP = 3600.0
SCALE = 0.15
BUCKET = 1500
FORCE = 33000
UNIT_TYPES = {'复合弓兵','方阵兵','阔剑兵','棍棒兵','刀斧兵','战车','投石','长矛兵','剑士','火枪手','骑兵','弓兵','散兵','枪兵','攻城','火炮','骆驼','轻骑兵'}

def load_sea(mp):
    data = json.loads(open(mp+'.njust', encoding='utf-8', errors='replace').read())
    cells = [(v['BlockDR'], v['BlockUR']) for v in data.values()
             if isinstance(v, dict) and v.get('Type') == 14]
    return cells, set(cells)

def parse_ait(tag):
    unit_traj = defaultdict(list); asm_last = None; asm_cnt = 0
    re_m = re.compile(r'HumanMove:(\S+?)\s+(\d+)\s+移动至\s+\(([\d.]+),([\d.]+)\)')
    with open(tag+'.ait', encoding='utf-8', errors='replace') as f:
        for line in f:
            p = line.split(' | ', 3)
            if len(p) < 4: continue
            try: fr = int(p[1])
            except: continue
            msg = p[3]
            m = re_m.search(msg)
            if m and m.group(1) in UNIT_TYPES:
                unit_traj[int(m.group(2))].append((fr, float(m.group(3)), float(m.group(4)), m.group(1)))
            if '[ASM' in msg:
                asm_last = fr; asm_cnt += 1
    return unit_traj, asm_last, asm_cnt

def bucket_stats(unit_traj):
    buckets = defaultdict(lambda: defaultdict(list))
    for sn, tr in unit_traj.items():
        for pt in tr:
            buckets[pt[0]//BUCKET][sn].append((pt[1], pt[2]))
    stats = []
    for k in sorted(buckets):
        rep = {}
        for sn, pts in buckets[k].items():
            xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
            rep[sn]=(statistics.mean(xs), statistics.mean(ys))
        if len(rep) < 2: continue
        xs=[p[0] for p in rep.values()]; ys=[p[1] for p in rep.values()]
        cx=statistics.mean(xs); cy=statistics.mean(ys)
        dd=[math.hypot(x-cx, y-cy) for x,y in rep.values()]
        dps=0
        ks=list(rep.values())
        for i in range(len(ks)):
            for j in range(i+1, len(ks)):
                if math.hypot(ks[i][0]-ks[j][0], ks[i][1]-ks[j][1]) < 2*BL: dps+=1
        stats.append(dict(k=k, f0=k*BUCKET, Dmax=max(dd)/BL, Dmean=statistics.mean(dd)/BL,
                          n=len(rep), cx=cx, cy=cy, dup=dups if False else dps, pts=list(rep.values())))
    return stats

def seg(ss):
    if not ss: return None
    v=[s for s in ss if s['n'] >= 0.5*max(x['n'] for x in ss)]
    if not v: return None
    Dmaxs=[s['Dmax'] for s in v]; dups=[s['dup'] for s in v]
    return dict(Dmin=min(Dmaxs), Dmed=statistics.median(Dmaxs), Dmax=max(Dmaxs),
                dup_sum=sum(dups), n_buckets=len(v))

def analyze(tag, mp):
    sea, sea_set = load_sea(mp)
    unit_traj, asm_last, asm_cnt = parse_ait(tag)
    if not unit_traj: return None
    stats = bucket_stats(unit_traj)
    if not stats: return None
    peak_n = max(s['n'] for s in stats)
    assemble = [s for s in stats if s['f0'] < FORCE]
    attack   = [s for s in stats if s['f0'] >= FORCE]
    aseg = seg(assemble); atk = seg(attack)
    # 早期(<33000)所有桶（不限 n）：判断早期是聚集还是已散开推进
    aall = None
    if assemble:
        Dmx=[s['Dmax'] for s in assemble]; dp=[s['dup'] for s in assemble]
        aall = dict(Dmed=statistics.median(Dmx), Dmax=max(Dmx), dup_sum=sum(dp), nb=len(assemble))
    atk_D = [s['Dmax'] for s in attack]
    atk_dup_all = sum(s['dup'] for s in attack)
    atk_rmax = max(atk_D) if atk_D else 0
    atk_rmean = statistics.mean(atk_D) if atk_D else 0
    in_sea = 0
    for sn, tr in unit_traj.items():
        for pt in tr:
            if pt[0] >= FORCE and (int(round(pt[1]/BL)), int(round(pt[2]/BL))) in sea_set:
                in_sea += 1
    min_sea = 1e9
    for s in attack:
        for dr,ur in sea:
            d = math.hypot(s['cx']-dr*BL, s['cy']-ur*BL)/BL
            if d < min_sea: min_sea = d
    g_pts = (max(assemble, key=lambda s:s['n'])['pts'] if assemble
             else (max(stats, key=lambda s:s['n'])['pts'] if stats else []))
    return dict(tag=tag, mp=mp, n=len(unit_traj), asm_last=asm_last, asm_cnt=asm_cnt, peak_n=peak_n,
                aseg=aseg, atk=atk, aall=aall, atk_rmax=atk_rmax, atk_rmean=atk_rmean, atk_dup=atk_dup_all,
                in_sea=in_sea, min_sea_dist=min_sea, g_pts=g_pts,
                unit_traj=unit_traj, sea=sea)

def svg_for(r):
    W = int(MAP*SCALE)
    sea_rects = ''.join(
        f'<rect x="{dr*BL*SCALE:.1f}" y="{ur*BL*SCALE:.1f}" width="{BL*SCALE:.1f}" height="{BL*SCALE:.1f}" fill="#3a6ea5" opacity="0.5"/>'
        for dr, ur in r['sea'])
    g_dots = ''.join(
        f'<circle cx="{x*SCALE:.1f}" cy="{y*SCALE:.1f}" r="3.5" fill="#e63946" opacity="0.8"/>'
        for x,y in r['g_pts'])
    random.seed(7)
    traj = ''
    for sn in r['unit_traj']:
        tr = [p for p in r['unit_traj'][sn] if p[0] >= 33000]
        if len(tr) < 2: continue
        hue = random.randint(0, 360)
        traj += ''.join(
            f'<line x1="{tr[i-1][1]*SCALE:.1f}" y1="{tr[i-1][2]*SCALE:.1f}" x2="{tr[i][1]*SCALE:.1f}" y2="{tr[i][2]*SCALE:.1f}" stroke="hsl({hue},65%,45%)" stroke-width="1" opacity="0.4"/>'
            for i in range(1, len(tr)))
    return (f'<svg width="{W}" height="{W}" viewBox="0 0 {W} {W}">'
            f'{sea_rects}{traj}{g_dots}</svg>')

BATCH = {
    'asm2': [('asm201','map2'),('asm202','map2'),('asm203','map2'),
             ('asm205','map3'),('asm206','map3'),('asm207','map3')],
    'asm3': [('asm301','map2'),('asm302','map2'),('asm303','map2'),
             ('asm305','map3'),('asm306','map3'),('asm307','map3')],
    'asm5': [('asm501','map2'),('asm502','map2'),('asm503','map2'),
             ('asm505','map3'),('asm506','map3'),('asm507','map3')],
    'asm6': [('asm601','map2'),('asm602','map2'),('asm603','map2'),
             ('asm605','map3'),('asm606','map3'),('asm607','map3')],
    'asm7': [('asm701','map2'),('asm702','map2'),('asm703','map2'),
             ('asm705','map3'),('asm706','map3'),('asm707','map3')],
    'asm8': [('asm801','map2'),('asm802','map2'),('asm803','map2'),
             ('asm805','map3'),('asm806','map3'),('asm807','map3')],
    'asm9': [('asm901','map2'),('asm902','map2'),('asm903','map2'),
             ('asm905','map3'),('asm906','map3'),('asm907','map3')],
}

def run_batch(name):
    rows = []
    for tag, mp in BATCH[name]:
        if not os.path.exists(tag+'.ait'):
            print('缺失', tag); continue
        r = analyze(tag, mp)
        if r: rows.append(r)
        else: print(tag, '无军事单位轨迹')
    return rows

def agg(rows):
    """批次聚合：早期Dmed均值 / 早期dup均值 / [ASM]总数 / 反攻Dmax均值 / 进海总数"""
    if not rows: return None
    eD = [r['aall']['Dmed'] for r in rows if r['aall']]
    eP = [r['aall']['dup_sum'] for r in rows if r['aall']]
    aD = [r['atk_rmax'] for r in rows]
    return dict(n=len(rows),
                eDmed=statistics.mean(eD) if eD else 0,
                eDup=statistics.mean(eP) if eP else 0,
                asm=sum(r['asm_cnt'] for r in rows),
                asm_runs=sum(1 for r in rows if r['asm_cnt'] > 0),
                atkD=statistics.mean(aD) if aD else 0,
                sea=sum(r['in_sea'] for r in rows))

def cards_for(rows, title):
    out = f'<h2>{title}</h2>'
    svgs = []
    for r in rows:
        aa = r['aall']
        aaDmed = aa['Dmed'] if aa else 999; aaDup = aa['dup_sum'] if aa else 0
        v_as = ('✓聚且基本不重叠' if (aa and aaDmed < 15 and aaDup < 20) else
                ('△过度聚集+重叠(位置重复)' if (aa and aaDup >= 20) else ('✗散开' if aa else '◌无桶')))
        v_ro = ('✓抱团走' if r['atk_rmax'] < 40 else ('△局部拉开' if r['atk_rmax'] < 70 else '✗被扯开'))
        v_se = ('⚠进海' if r['in_sea'] > 0 else ('✓远离海' if r['min_sea_dist'] > 20 else '△近海'))
        out += (f'<div class="card"><b>{r["tag"]}</b> ({r["mp"]}) · 军事 {r["n"]} · 峰值桶 {r["peak_n"]} · '
                f'[ASM]集结令 <b>{r["asm_cnt"]}</b> 条<br>'
                f'①反攻前集结(早期&lt;33k): {"Dmax中位%.1f格 重叠对%d"%(aa["Dmed"],aa["dup_sum"]) if aa else "无桶"} → {v_as}<br>'
                f'②反攻路线: 散开峰{r["atk_rmax"]:.1f}/均{r["atk_rmean"]:.1f} 重叠对{r["atk_dup"]} → {v_ro}<br>'
                f'③海隔断: 进海 {r["in_sea"]}次 · 质心最近海 {r["min_sea_dist"]:.1f}格 → {v_se}</div>')
        svgs.append(f'<div class="card"><h3>{r["tag"]}（红点=反攻前全军最多时落点；彩线=反攻轨迹）</h3>{svg_for(r)}</div>')
    return out, ''.join(svgs)

def main():
    import sys
    args = sys.argv[1:] or ['asm3']
    batches = [(a, run_batch(a)) for a in args if a in BATCH]

    print('\n=== 逐局指标（格=35.777px；dup=两两<2格重叠对）===')
    for name, rows in batches:
        for r in rows:
            aa = r['aall']
            aaD = f"D中{aa['Dmed']:.1f}/峰{aa['Dmax']:.1f} dup{aa['dup_sum']}" if aa else "无桶"
            print(f"[{name}] {r['tag']:6s} {r['mp']:4s} 军事={r['n']:3d} 峰值桶={r['peak_n']:3d} | "
                  f"早期[{aaD}] | [ASM]={r['asm_cnt']:4d} | 反攻峰{r['atk_rmax']:.1f}/均{r['atk_rmean']:.1f} "
                  f"| 进海{r['in_sea']} 质心海{r['min_sea_dist']:.1f}")

    print('\n=== 批次聚合对比 ===')
    aggs = [(n, agg(rows)) for n, rows in batches]
    for n, g in aggs:
        if g: print(f"{n}: 局数{g['n']} | 早期D中位均值={g['eDmed']:.1f}格 重叠对均值={g['eDup']:.1f} | "
                    f"[ASM]总{g['asm']}条(命中局{g['asm_runs']}/{g['n']}) | 反攻散开峰值均值={g['atkD']:.1f}格 | 进海总{g['sea']}")
    if len(aggs) == 2 and aggs[0][1] and aggs[1][1]:
        a, b = aggs[0][1], aggs[1][1]
        print(f"\n--- 差异（{aggs[0][0]} → {aggs[1][0]}）---")
        print(f"  早期重叠对均值: {a['eDup']:.1f} → {b['eDup']:.1f}  ({'↓改善' if b['eDup']<a['eDup'] else '↑恶化'})")
        print(f"  早期D中位均值 : {a['eDmed']:.1f} → {b['eDmed']:.1f} 格")
        print(f"  [ASM]命中局数 : {a['asm_runs']}/{a['n']} → {b['asm_runs']}/{b['n']}")
        print(f"  反攻散开峰值  : {a['atkD']:.1f} → {b['atkD']:.1f} 格")

    cards = ''; svghtml = ''
    for name, rows in batches:
        c, s = cards_for(rows, f'批次 {name}（{len(rows)} 局）')
        cards += c; svghtml += s
    cmp_row = ''
    if len(aggs) == 2 and aggs[0][1] and aggs[1][1]:
        a, b = aggs[0][1], aggs[1][1]
        cmp_row = (f'<div class="card"><h2>A/B 汇总</h2><table>'
                   f'<tr><th>指标</th><th>{aggs[0][0]}（改动前）</th><th>{aggs[1][0]}（改动后）</th><th>结论</th></tr>'
                   f'<tr><td>早期重叠对均值（位置重复）</td><td>{a["eDup"]:.1f}</td><td><b>{b["eDup"]:.1f}</b></td>'
                   f'<td>{"<b>↓ 改善</b>" if b["eDup"]<a["eDup"] else "↑ 恶化"}</td></tr>'
                   f'<tr><td>早期散开 D 中位均值</td><td>{a["eDmed"]:.1f}格</td><td><b>{b["eDmed"]:.1f}格</b></td><td>越小越抱团</td></tr>'
                   f'<tr><td>[ASM] 集结令命中局数</td><td>{a["asm_runs"]}/{a["n"]}</td><td><b>{b["asm_runs"]}/{b["n"]}</b></td>'
                   f'<td>{"槽位已生效" if b["asm_runs"]>a["asm_runs"] else "仍未触发"}</td></tr>'
                   f'<tr><td>反攻散开峰值均值</td><td>{a["atkD"]:.1f}格</td><td><b>{b["atkD"]:.1f}格</b></td><td>②路线相近度</td></tr>'
                   f'<tr><td>进海总次数</td><td>{a["sea"]}</td><td><b>{b["sea"]}</b></td><td>③海隔断</td></tr></table></div>')
    html = f'''<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><title>军队集结与反攻轨迹检查</title>
<style>body{{font-family:-apple-system,'Microsoft Yahei',sans-serif;margin:20px;background:#f6f7f9;color:#1a1a1a}}
.card{{background:#fff;border:1px solid #e3e6ea;border-radius:8px;padding:12px 16px;margin:10px 0}}
svg{{background:#dfe7d8;border:1px solid #c9d2c0}}h1{{font-size:20px}}h2{{font-size:17px;margin:16px 0 6px}}h3{{font-size:14px;margin:6px 0}}
.note{{color:#666;font-size:12px}}table{{border-collapse:collapse;font-size:13px}}td,th{{border:1px solid #e3e6ea;padding:5px 8px;text-align:left}}</style></head><body>
<h1>军队集结 / 反攻路线 / 海隔断 —— 改动前后对比</h1>
{cmp_row}
{cards}
<h2>每局轨迹图</h2>
{svghtml}
<p class="note">口径：D=各单位到该时刻大部队质心的最远距离(格)，越小越抱团；dup=两两距离&lt;2格的重叠对（位置重复）。
[ASM]=新加的槽位集结令（节流 300 帧/单位）。红点=反攻前(帧&lt;33000)全军最多时的落点，重合即重叠；彩线=反攻推进轨迹，分叉=小股被扯开。蓝块=地形海(Type=14)。</p>
</body></html>'''
    open('aoe3_asm_check_20260929.html','w',encoding='utf-8').write(html)
    print('\n生成 aoe3_asm_check_20260929.html')

if __name__ == '__main__':
    main()
