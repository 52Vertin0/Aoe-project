# -*- coding: utf-8 -*-
"""
fixL 验证：W3(第三波) 不让士兵打敌方投石车、留给祭司感化

主判据（机制量，非胜率）：
  ① 我方(flag=0)对投石车下攻击令的条数 —— 分段：W3 前 / W3~反攻前 / 反攻期
     ⚠ flag 语义已用祭司指令(必为我方)标定为 flag=0。
  ② 祭司把投石车设为感化目标的次数（分段）
  ③ 祭司感化成功量（"转换高级敌人"）
护栏：
  ④ Mil 首>4 中位帧 / mil_max / 崩盘率(mil_max<16)
  ⑤ 祭司是否活过 W3、胜率（次级端点）
"""
import re, glob, os, collections, statistics as st, sys

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
        atk, ctg, hi = [], [], 0
        for L in t.splitlines():
            p = L.split('|')
            if len(p) < 5:
                continue
            try:
                f = int(p[1].strip()); fl = int(p[3].strip())
            except Exception:
                continue
            msg = p[4]
            if fl == 0 and '设置攻击目标为 投石车' in msg:
                atk.append(f)
            if '设置转换目标为 投石车' in msg:
                ctg.append(f)
            if '转换高级敌人' in msg:
                hi += 1
        if '被祭司转换,归属阵营1->0' in t:
            k = 'W'
        elif 'DEFEAT: Priest killed' in t:
            k = 'P'
        else:
            k = 'T'
        dth = -1
        md = re.search(r'\|(\d+)\|.*DEFEAT: Priest killed', t)
        if md:
            dth = int(md.group(1))
        mils = [int(x) for x in re.findall(r'Mil=(\d+)', t)]
        beats = [(int(a), int(b)) for a, b in re.findall(r'\[BEAT f=(\d+)[^\n]*?Mil=(\d+)', t)]
        f5 = next((f for f, mm in beats if mm > 4), None)
        endf = max([f for f, _ in beats], default=0)
        rows.append(dict(base=base, ca=ca, atk=atk, ctg=ctg, hi=hi, k=k,
                         mil_max=max(mils) if mils else 0, f5=f5, dth=dth, endf=endf))
    return rows

def seg(f, ca):
    if ca > 0 and f >= ca:
        return 'CA'
    if f >= 21000:
        return 'W3'
    return 'PRE'

def report(tag, rows):
    if not rows:
        print(f'  {tag}: 无有效局')
        return None
    s_atk = collections.Counter(); s_ctg = collections.Counter()
    tot_atk = tot_ctg = 0
    per_game_atk = []
    for r in rows:
        a = 0
        for f in r['atk']:
            s_atk[seg(f, r['ca'])] += 1
            if seg(f, r['ca']) != 'CA':
                a += 1
        for f in r['ctg']:
            s_ctg[seg(f, r['ca'])] += 1
        tot_atk += len(r['atk']); tot_ctg += len(r['ctg'])
        per_game_atk.append(a)
    kc = collections.Counter(r['k'] for r in rows)
    n = len(rows)
    # 祭司活过 W3 的人数：死亡帧 > 21000 或未死
    alive_w3 = sum(1 for r in rows if r['dth'] < 0 or r['dth'] > 21000)
    crash = sum(1 for r in rows if r['mil_max'] < 16)
    print(f'  {tag:<6} n={n:>3}  胜={kc["W"]:>2}({100*kc["W"]/n:>3.0f}%) 祭死={kc["P"]:>2} 超时={kc["T"]:>2}'
          f'  | 崩盘={crash:>2}({100*crash/n:>2.0f}%) 活过W3={alive_w3:>2}')
    print(f'         ① 我方打投石车: 总={tot_atk:>6}  [{dict(s_atk)}]  有令局数={sum(1 for x in per_game_atk if x>0)}'
          f'  非反攻段条数中位={med([x for x in per_game_atk if x>0]):.0f}')
    print(f'         ② 祭司设投石车为目标: 总={tot_ctg:>5}  [{dict(s_ctg)}]  有设过的局={sum(1 for r in rows if r["ctg"])}')
    print(f'         ③ 转换高级敌人: 总={sum(r["hi"] for r in rows):>5}  中位/局={med([r["hi"] for r in rows]):.0f}')
    print(f'         ④ 护栏: Mil首>4 中位={med([r["f5"] for r in rows if r["f5"]]):.0f}'
          f'  mil_max中位={med([r["mil_max"] for r in rows]):.0f}')
    return dict(atk=s_atk, ctg=s_ctg, tot_atk=tot_atk, n=n, kc=kc)

base = 'fixI'; new = 'fixL'
print('=' * 112)
print(f'§1 总览：{base}（基线） vs {new}（fixL：W3 护驾对象排除投石车）')
print('=' * 112)
rb = report(base, load(base))
rN = report(new, load(new))

if rb and rN:
    print()
    print('=' * 112)
    print('§2 主判据对比（★ 期望：W3 段"我方打投石车"显著下降；反攻期(CA)基本不变）')
    print('=' * 112)
    for k, label in [('PRE', 'W3 之前(<=14分)'), ('W3', 'W3~反攻前(14~22分)'), ('CA', '反攻期(22分+)')]:
        b = rb['atk'].get(k, 0); n2 = rN['atk'].get(k, 0)
        d = n2 - b
        pct = (100.0 * d / b) if b else float('nan')
        flag = '  ← 目标段' if k == 'W3' else ('  ← 应基本不变' if k == 'CA' else '')
        print(f'  {label:<20} {base}={b:>6}  {new}={n2:>6}  Δ={d:>+7} ({pct:>+6.1f}%){flag}')
    print()
    print(f'  祭司把投石车设为感化目标：{base}={rb["tot_ctg"] if False else sum(rb["ctg"].values()):>4}  '
          f'{new}={sum(rN["ctg"].values()):>4}')
    for k, label in [('W3', 'W3~反攻前'), ('CA', '反攻期')]:
        print(f'    {label:<12} {base}={rb["ctg"].get(k,0):>4}  {new}={rN["ctg"].get(k,0):>4}')
