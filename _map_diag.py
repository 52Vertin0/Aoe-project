# -*- coding: utf-8 -*-
"""map 图败因归因：结局 × 军队(Mil)峰值 × 村民(Frm)峰值 × 起手/祭死。
针对 current_map_r0_*.ait（24 局）。
"""
import re, glob, os, collections

TAG = 'current_map'
files = sorted(glob.glob(f'{TAG}_r0_*.ait'))
if not files:
    files = sorted(glob.glob('current_map_r0_*.ait'))

rows = []
for fn in files:
    t = open(fn, encoding='utf-8', errors='replace').read()
    if t.count('[BEAT') < 5:
        continue
    # 结局
    if '被祭司转换,归属阵营1->0' in t:
        res = 'W'
    elif 'DEFEAT: Priest killed' in t:
        res = 'P'
    elif 'DEFEAT: Town Center destroyed' in t:
        res = 'T'
    else:
        res = 'U'
    # Mil / Frm 峰值（BEAT 行）
    mpeak = 0
    fpeak = 0
    for m in re.finditer(r'\[BEAT[^\n]*\bMil=(\d+)', t):
        v = int(m.group(1))
        if v > mpeak:
            mpeak = v
    for m in re.finditer(r'\[BEAT[^\n]*\bFrm=(\d+)', t):
        v = int(m.group(1))
        if v > fpeak:
            fpeak = v
    # 起手：祭司推进武器厂 或 设置转换目标为 攻城武器厂 或 已完成转换
    adv = re.search(r'Priest ADVANCE to Siege f=(\d+)', t)
    conv_target = '设置转换目标为 攻城武器厂' in t
    done = '被祭司转换,归属阵营1->0' in t
    has_start = (adv is not None) or conv_target or done
    start_f = int(adv.group(1)) if adv else None
    # 反攻起点
    ca = re.search(r'Counterattack! Frame=(\d+)', t)
    ca_f = int(ca.group(1)) if ca else None
    # 祭死帧
    pf = re.search(r'DEFEAT: Priest killed', t)
    # 末帧
    beats = [int(x) for x in re.findall(r'\[BEAT f=(\d+)', t)]
    last_f = max(beats) if beats else 0
    rows.append(dict(fn=os.path.basename(fn), res=res, mpeak=mpeak, fpeak=fpeak,
                     has_start=has_start, start_f=start_f, ca_f=ca_f, last_f=last_f))

print('=' * 100)
print(f'map 图败因归因（{len(rows)} 局，TAG=current，fixM 等价版）')
print('=' * 100)
print(f'{"局":<26}{"结局":>4}{"Mil峰":>6}{"Frm峰":>6}{"起手":>5}{"起手帧":>8}{"反攻帧":>8}{"末帧":>8}')
print('-' * 100)
byres = collections.defaultdict(list)
for r in sorted(rows, key=lambda x: x['res']):
    print(f'{r["fn"]:<26}{r["res"]:>4}{r["mpeak"]:>6}{r["fpeak"]:>6}{("Y" if r["has_start"] else "-"):>5}'
          f'{str(r["start_f"] or "-"):>8}{str(r["ca_f"] or "-"):>8}{r["last_f"]:>8}')
    byres[r['res']].append(r)

print('=' * 100)
print('分组汇总（结局 → Mil峰中位/Mil峰均值 | Frm峰均值 | 起手率 | 末帧均值）')
print('-' * 100)
def med(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return 0
    if n % 2:
        return xs[n // 2]
    return (xs[n // 2 - 1] + xs[n // 2]) / 2

for res in ['W', 'P', 'T', 'U']:
    sub = byres[res]
    if not sub:
        continue
    mp = [r['mpeak'] for r in sub]
    fp = [r['fpeak'] for r in sub]
    st = sum(1 for r in sub if r['has_start'])
    lf = [r['last_f'] for r in sub]
    print(f'{res} (n={len(sub)}): Mil峰 中位{med(mp):.0f} 均值{sum(mp)/len(mp):.1f} | '
          f'Frm峰均值{sum(fp)/len(fp):.1f} | 起手率{100*st/len(sub):.0f}% | 末帧均值{sum(lf)/len(lf):.0f}')

print('-' * 100)
# 全局：起手率 × 结局
print('起手 vs 结局：')
for hs in [True, False]:
    sub = [r for r in rows if r['has_start'] == hs]
    if not sub:
        continue
    wc = collections.Counter(r['res'] for r in sub)
    print(f'  起手={hs}: n={len(sub)} W{wc["W"]} P{wc["P"]} T{wc["T"]} U{wc["U"]}')
print('=' * 100)
