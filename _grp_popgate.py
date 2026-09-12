# -*- coding: utf-8 -*-
"""人口闸触发局 vs 未触发局的分组分析（club8n）。
⚠ 选择偏差：触发局=经济好到人口能到 50 的局，偏顺风，差异不可直接当因果。
"""
import glob, re, statistics, sys

TAG = sys.argv[1] if len(sys.argv) > 1 else 'club8n'
POP = re.compile(r'POP-FULL COUNTERATTACK! Frame=(\d+)')
CA  = re.compile(r'ALL WAVES DEFEATED! Counterattack! Frame=(\d+)')
FR  = re.compile(r'^\d\d:\d\d:\d\d+\s*\|\s*(\d+)\s*\|')

def out(s):
    if '被祭司转换,归属阵营1->0' in s: return 'W'
    if 'DEFEAT: Priest killed' in s: return 'P'
    if 'DEFEAT: Town Center destroyed' in s or '敌方 摧毁主营' in s: return 'T'
    return 'U'

def blank():
    return dict(W=0, P=0, T=0, U=0, n=0, early=0, pf=[], ca=[])

grp = {'触发': blank(), '未触发': blank()}
for fn in sorted(glob.glob(TAG + '_map_r0_*.ait')):
    s = open(fn, encoding='utf-8', errors='replace').read()
    fr = [int(x.group(1)) for x in (FR.match(l) for l in s.splitlines()) if x]
    mx = max(fr) if fr else 0
    r = out(s)
    mp = POP.search(s)
    ca = CA.search(s)
    g = grp['触发' if mp else '未触发']
    g['n'] += 1
    g[r] += 1
    if mp: g['pf'].append(int(mp.group(1)))
    # ★ 反攻时点：闸帧优先（触发局不会再打印 ALL WAVES），否则用强制帧
    cand = [int(x.group(1)) for x in (mp, ca) if x]
    atk = min(cand) if cand else None
    if atk is not None: g['ca'].append(atk)
    if r == 'P' and (atk is None or mx < atk):
        g['early'] += 1

print('=' * 90)
print(f'{TAG} 内部分组：人口闸触发 vs 未触发（map 单图）')
print('=' * 90)
for k, g in grp.items():
    n = g['n']
    print(f"[{k:<3}] n={n:<3} W={g['W']:<3} P={g['P']:<3} T={g['T']} U={g['U']}  "
          f"胜率={g['W']/n*100 if n else 0:5.1f}%  祭死={g['P']:<3} 反攻前早死={g['early']}  "
          f"反攻帧中位={statistics.median(g['ca']) if g['ca'] else 0:.0f}")
    if g['pf']:
        pfm = statistics.mean(g['pf'])
        print(f"       闸帧: 均={pfm:.0f} ({pfm/1500:.2f}分) 中位={statistics.median(g['pf']):.0f} "
              f"min={min(g['pf'])} ({min(g['pf'])/1500:.2f}分) max={max(g['pf'])}  "
              f"⇒ 比强制点 33000(22.00分) 提前 {(33000-pfm)/1500:.2f} 分")
print('=' * 90)
print('注：触发局=经济好到人口能到 50 的局，本身偏顺风，此处差异含选择偏差，不可直接当因果。')
