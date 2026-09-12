# -*- coding: utf-8 -*-
"""popfull 抽检：结局 + 新闸(POP-FULL COUNTERATTACK)触发帧 + 引擎反攻帧 + [GATHER] 首 ready=1。"""
import glob, re, os, sys

TAG = sys.argv[1] if len(sys.argv) > 1 else 'popfull'
FRAME_RE = re.compile(r'^\d\d:\d\d:\d\d+\s*\|\s*(\d+)\s*\|')

def outcome(s):
    if '被祭司转换,归属阵营1->0' in s: return 'W'
    if 'DEFEAT: Priest killed' in s: return 'P'
    if 'DEFEAT: Town Center destroyed' in s: return 'T'
    if '敌方 摧毁主营' in s: return 'T'   # ★ 我方 TC 被毁（AI 自身 defeat 打印可能来不及）
    return 'U'

def frac(f):
    return f'{f}({f/1500:.0f}分)'

print('=' * 118)
print(f'抽检 TAG={TAG}   （POPFULL触发帧 < 引擎33000 ⇒ 新闸生效、提前反攻）')
print('=' * 118)
hdr = f'{"文件":<24}{"结局":<5}{"最大帧":<14}{"POPFULL触发":<16}{"引擎反攻帧":<16}{"首[GATHER]ready=1":<18}'
print(hdr); print('-' * 118)

rows = []
for fn in sorted(glob.glob(f'{TAG}_*_r0_*.ait')):
    s = open(fn, encoding='utf-8', errors='replace').read()
    fr = [int(m.group(1)) for m in (FRAME_RE.match(l) for l in s.splitlines()) if m]
    maxf = max(fr) if fr else 0
    pf = re.search(r'POP-FULL COUNTERATTACK! Frame=(\d+)', s)
    ca = re.search(r'ALL WAVES DEFEATED! Counterattack! Frame=(\d+)', s)
    g1 = re.search(r'\[GATHER f=(\d+)\][^\n]*ready=1', s)
    nm = os.path.basename(fn).replace(f'{TAG}_', '').replace('_r0_', ' /r0_')
    a = frac(int(pf.group(1))) if pf else '-'
    b = frac(int(ca.group(1))) if ca else '-'
    c = frac(int(g1.group(1))) if g1 else '-'
    print(f'{nm:<24}{outcome(s):<5}{frac(maxf):<14}{a:<16}{b:<16}{c:<18}')
    rows.append((nm, outcome(s), pf, ca))

print('=' * 118)
# 汇总
by_map = {}
for nm, r, pf, ca in rows:
    mp = nm.split()[0]
    by_map.setdefault(mp, []).append(r)
for mp, rs in sorted(by_map.items()):
    print(f'  {mp:<8} 结局={"".join(rs)}')
pf_n = sum(1 for _, _, pf, _ in rows if pf)
print(f'  POP-FULL 闸触发局数 = {pf_n}/{len(rows)}')
print('=' * 118)

# 打印一局的 [GATHER] 时间线
demo = sorted(glob.glob(f'{TAG}_*_r0_*.ait'))
if demo:
    f0 = next((f for f in demo if f'[GATHER' in open(f, encoding='utf-8', errors='replace').read()), demo[0])
    print(f'=== [GATHER] 时间线样例：{os.path.basename(f0)} ===')
    for l in open(f0, encoding='utf-8', errors='replace').read().splitlines():
        if '[GATHER ' in l:
            print('   ', l.strip()[:160])
