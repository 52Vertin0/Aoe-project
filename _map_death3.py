# -*- coding: utf-8 -*-
"""earlyclub8 版 map 图：祭死局死亡前 LC-DBG 序列。
LC-DBG 行：siegeSN dS(到武器厂距离,格) hp(0-1) ccd(感化冷却) st seen nearT(到最近箭塔距离)
判定死亡位置：
  - dS 小(<15 格=感化射程边缘) ⇒ 死在武器厂旁（感化尝试中/刚完成）
  - dS 大 ⇒ 死在接近/撤退途中
同时看 hp 轨迹与 ccd（是否正在/刚感化）。
"""
import re, glob, os, collections

TAG = 'earlyclub8'
files = sorted(glob.glob(f'{TAG}_map_r0_*.ait'))
WIN = 25

def parse_lc(line):
    m = re.search(r'\[LC-DBG f=(\d+)\].*?siegeSN=(-?\d+).*?dS=([-\d.]+).*?hp=([\d.]+).*?ccd=(-?\d+).*?st=(\d+).*?seen=(-?\d+).*?nearT=([-\d.]+)', line)
    if not m: return None
    return dict(f=int(m.group(1)), siegeSN=int(m.group(2)), dS=float(m.group(3)),
                hp=float(m.group(4)), ccd=int(m.group(5)), st=int(m.group(6)),
                seen=int(m.group(7)), nearT=float(m.group(8)))

rows = []
for fn in files:
    t = open(fn, encoding='utf-8', errors='replace').read()
    if 'DEFEAT: Priest killed' not in t:
        continue
    buf = []
    for line in t.splitlines():
        if '[LC-DBG' in line:
            p = parse_lc(line)
            if p:
                buf.append(p)
                if len(buf) > WIN: buf.pop(0)
        elif 'DEFEAT: Priest killed' in line:
            if buf:
                rows.append((os.path.basename(fn), list(buf)))
            break

def summ(fn, buf):
    dSs = [b['dS'] for b in buf]
    hps = [b['hp'] for b in buf]
    ccd = [b['ccd'] for b in buf]
    sts = [b['st'] for b in buf]
    seen = [b['seen'] for b in buf]
    nearT = [b['nearT'] for b in buf]
    last = buf[-1]
    dS_last = last['dS']
    # 死在武器厂旁：最后若干帧 dS 持续 < 15 且 seen>=0（已发现）
    atSiege = (dS_last >= 0 and dS_last < 15)
    # 是否曾尝试感化：ccd 出现过 >0 且 dS<15
    triedConv = any((b['dS'] >= 0 and b['dS'] < 15 and b['ccd'] > 0) for b in buf)
    seenEver = any(s >= 0 for s in seen)
    return dict(fn=fn, n=len(buf), dS_last=dS_last, hp_last=last['hp'],
                hp0=hps[0], st_last=last['st'], nearT_last=last['nearT'],
                atSiege=atSiege, triedConv=triedConv, seenEver=seenEver,
                st_counts=dict(collections.Counter(sts)))

S = [summ(fn, buf) for fn, buf in rows]
print('='*100)
print(f'{TAG} 祭死局死亡位置判定（n={len(S)} 局，每局最后 {WIN} 个 LC-DBG，步长约300帧）')
print('='*100)
atSiege_n = sum(1 for s in S if s['atSiege'])
tried_n = sum(1 for s in S if s['triedConv'])
seen_n = sum(1 for s in S if s['seenEver'])
for s in S:
    tag = '武器厂旁' if s['atSiege'] else '他处'
    print(f"{s['fn'][-22]:22} | {tag:7} | dS末={s['dS_last']:6.1f} hp末={s['hp_last']:.2f} hp0={s['hp0']:.2f} "
          f"st末={s['st_last']} nearT末={s['nearT_last']:6.1f} 曾感化={s['triedConv']} 曾发现={s['seenEver']} st={s['st_counts']}")
print('-'*100)
print(f"死在武器厂旁(dS末<15)      = {atSiege_n}/{len(S)}")
print(f"曾尝试感化(dS<15且ccd>0)   = {tried_n}/{len(S)}")
print(f"武器厂曾被我发现(seen>=0)   = {seen_n}/{len(S)}")
print('='*100)
