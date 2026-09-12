# -*- coding: utf-8 -*-
"""
fixM 验证：W3(第三波) 把"祭司感化投石车"提前到 远程军队 之前

主判据（机制量）：
  ① 祭司把投石车设为感化目标的次数（分段：W3 / 反攻期）
  ② ★投石车归属"敌(flag=1)→我(flag=0)"翻转次数 = 感化成功（分段：首次被我方接管的帧）
  ③ 有投石车出现的局里，"感化到至少 1 辆"的局数占比
护栏：
  ④ W3 段祭司死亡数 / 崩盘率(mil_max<16) / Mil 首>4 / 胜率（次级）
  ⑤ 副作用面：W3 段敌方远程军队存量（若感化远程的窗口被抢，敌方远程应更多）
"""
import re, glob, os, collections, statistics as st

def med(v):
    return st.median(v) if v else float('nan')

def load(tag):
    rows = []
    for fn in sorted(glob.glob(f'{tag}_*_r0_*.ait')):
        t = open(fn, encoding='utf-8', errors='replace').read()
        if t.count('[BEAT') < 5:
            continue
        base = os.path.basename(fn).replace(tag + '_', '').replace('.ait', '')
        m = re.search(r'Counterattack! Frame=(\d+)', t)
        ca = int(m.group(1)) if m else -1
        ctg = []                       # 设置转换目标为 投石车
        stone = {}                     # sn -> {'t':set,'o':set} 投石车被 AI 提及时的 flag
        for L in t.splitlines():
            p = L.split('|')
            if len(p) < 5:
                continue
            try:
                f = int(p[1].strip()); fl = int(p[3].strip())
            except Exception:
                continue
            msg = p[4]
            if '设置转换目标为 投石车' in msg:
                ctg.append(f)
            mm = re.search(r'HumanAction:投石车 (\d+) 设置', msg)
            if mm:
                d = stone.setdefault(int(mm.group(1)), {'t': set(), 'o': set()})
                (d['t'] if fl == 1 else d['o']).add(f)
        conv = []                      # 感化成功：(sn, 敌方首帧, 我方首帧)
        for sn, d in stone.items():
            if d['t'] and d['o'] and min(d['o']) > min(d['t']):
                conv.append((sn, min(d['t']), min(d['o'])))
        if '被祭司转换,归属阵营1->0' in t:
            k = 'W'
        elif 'DEFEAT: Priest killed' in t:
            k = 'P'
        else:
            k = 'T'
        # ⚠ 2026-10-06 修正：字段两侧有空格（`| 15387 | black | 0 |`），
        #   旧写法 `\|(\d+)\|` 恒不命中 ⇒ dead_w3 恒 0（假绿护栏）。见 MEMORY.md §2 解析坑。
        md = re.search(r'\| (\d+) \| black \| 0 \|.*DEFEAT: Priest killed', t)
        dth = int(md.group(1)) if md else -1
        mils = [int(x) for x in re.findall(r'Mil=(\d+)', t)]
        beats = [(int(a), int(b)) for a, b in re.findall(r'\[BEAT f=(\d+)[^\n]*?Mil=(\d+)', t)]
        f5 = next((f for f, m2 in beats if m2 > 4), None)
        has_stone = bool(stone)
        rows.append(dict(base=base, ca=ca, ctg=ctg, conv=conv, k=k, dth=dth,
                         mil_max=max(mils) if mils else 0, f5=f5, has_stone=has_stone))
    return rows

def seg(f, ca):
    if ca > 0 and f >= ca:
        return 'CA'
    return 'W3' if f >= 21000 else 'PRE'

def report(tag, rows):
    if not rows:
        print(f'  {tag}: 无有效局'); return None
    n = len(rows)
    ctg = collections.Counter(); conv_seg = collections.Counter()
    nconv = 0; withconv = 0; hasstone = 0
    for r in rows:
        for f in r['ctg']:
            ctg[seg(f, r['ca'])] += 1
        for sn, ft, fo in r['conv']:
            conv_seg[seg(fo, r['ca'])] += 1
        nconv += len(r['conv'])
        if r['conv']: withconv += 1
        if r['has_stone']: hasstone += 1
    kc = collections.Counter(r['k'] for r in rows)
    dead_w3 = sum(1 for r in rows if 0 < r['dth'] <= 33000)
    crash = sum(1 for r in rows if r['mil_max'] < 16)
    print(f'  {tag:<6} n={n:>3} 胜={kc["W"]:>2}({100*kc["W"]/n:>3.0f}%) 祭死={kc["P"]:>2} 超时={kc["T"]:>2}'
          f' | 崩盘={crash:>2} 死在反攻前={dead_w3:>2} Mil首>4={med([r["f5"] for r in rows if r["f5"]]):.0f}')
    print(f'         ① 祭司设投石车为目标: 总={sum(ctg.values()):>4} {dict(ctg)}  有设过的局={sum(1 for r in rows if r["ctg"])}')
    print(f'         ② ★投石车被感化(敌→我): 总={nconv:>4} {dict(conv_seg)}  有成功的局={withconv}  出现投石车的局={hasstone}')
    print(f'            局级成功率 = {100*withconv/max(1,hasstone):.0f}%  (有投石车局中至少感化 1 辆)')
    return dict(ctg=ctg, conv=conv_seg, nconv=nconv, withconv=withconv, hasstone=hasstone, n=n, kc=kc)

for pair in [('fixI', 'fixM'), ('fixL', 'fixM')]:
    print('=' * 116)
    print(f'§ {pair[0]} vs {pair[1]}')
    print('=' * 116)
    a = report(pair[0], load(pair[0]))
    b = report(pair[1], load(pair[1]))
    if a and b:
        print(f'  Δ 投石车被感化: {a["nconv"]} → {b["nconv"]} ({b["nconv"]-a["nconv"]:+d})  '
              f'| 局级成功率 {100*a["withconv"]/max(1,a["hasstone"]):.0f}% → {100*b["withconv"]/max(1,b["hasstone"]):.0f}%')
        for k, lb in [('W3', 'W3段(14~22分)'), ('CA', '反攻期')]:
            print(f'    {lb:<14} 感化成功 {a["conv"].get(k,0):>3} → {b["conv"].get(k,0):>3}   '
                  f'设目标 {a["ctg"].get(k,0):>3} → {b["ctg"].get(k,0):>3}')
    print()
