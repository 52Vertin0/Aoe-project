# -*- coding: utf-8 -*-
# 量化 armypush24 祭死局里「感化时集火死」：
# 扫描 LC-DBG 序列，找 dS<=12 且 ccd>0(正在感化) 的连续片段，
# 统计：是否发生感化尝试、感化开始 hp、是否在感化中死亡、感化片段长度(帧)、死亡前 hp 轨迹。
import re, glob, os

TAG = 'armypush24'

def parse_lc(line):
    m = re.search(r'\[LC-DBG f=(\d+)\].*?dS=([-\d.]+).*?hp=([\d.]+).*?ccd=(-?\d+).*?st=(\d+).*?seen=(-?\d+)', line)
    if not m: return None
    f = int(m.group(1)); dS = float(m.group(2)); hp = float(m.group(3))
    ccd = int(m.group(4)); st = int(m.group(5)); seen = int(m.group(6))
    if dS < 0: return None
    return dict(f=f, dS=dS, hp=hp, ccd=ccd, st=st, seen=seen)

def last_beat_priest(t):
    # 取最后一条 [BEAT] 的 pr@ 坐标与 bbox（像素），算距军心(格)
    pr=None; bb=None
    for l in t.splitlines():
        if '[BEAT' in l:
            p = re.search(r'pr@=\(([\d.]+),([\d.]+)\)', l)
            b = re.search(r'bbox=\(x([\d.]+)\.\.([\d.]+),y([\d.]+)\.\.([\d.]+)\)', l)
            if p: pr=(float(p.group(1)),float(p.group(2)))
            if b: bb=(float(b.group(1)),float(b.group(2)),float(b.group(3)),float(b.group(4)))
    if pr is None or bb is None: return None
    cx=(bb[0]+bb[1])/2; cy=(bb[2]+bb[3])/2
    import math
    d=math.hypot(pr[0]-cx,pr[1]-cy)/35.777
    inside = bb[0]<=pr[0]<=bb[1] and bb[2]<=pr[1]<=bb[3]
    return d, inside

nP=0; convert_attempt=0; died_in_convert=0
hp_start_list=[]; convert_frames_list=[]; last_hp_before_zero=[]
detail=[]
for fn in sorted(glob.glob(f'{TAG}_map_r0_*.ait')):
    t = open(fn, encoding='utf-8', errors='replace').read()
    if 'DEFEAT: Priest killed' not in t: continue
    nP += 1
    lcs = [x for x in (parse_lc(l) for l in t.splitlines() if '[LC-DBG' in l) if x]
    if not lcs: continue
    # 找 dS<=12 & ccd>0 的片段
    in_conv=False; conv_start_hp=None; conv_frames=0; conv_died=False
    prev_hp=None
    for x in lcs:
        if x['dS'] <= 12 and x['ccd'] > 0:
            if not in_conv:
                in_conv=True; conv_start_hp=x['hp']; conv_frames=0; convert_attempt+=1
            conv_frames+=1
            if x['hp'] <= 0.01:
                conv_died=True
        else:
            if in_conv:
                in_conv=False
                if conv_died: died_in_convert+=1
                if conv_start_hp is not None: hp_start_list.append(conv_start_hp)
                convert_frames_list.append(conv_frames)
            in_conv=False
    # 死亡前最后一次 hp 值（最后一条 LC-DBG 的 hp，若 <1 说明突然死）
    last=xs=lcs[-1]
    last_hp_before_zero.append(last['hp'])

print(f'[{TAG}] 祭死局 n={nP}')
print(f'  发生过感化尝试(dS<=12&ccd>0)的局次数 = {convert_attempt}')
print(f'  感化尝试中死亡的 = {died_in_convert}')
print(f'  感化开始 hp 中位 = {sorted(hp_start_list)[len(hp_start_list)//2] if hp_start_list else float("nan"):.2f}')
print(f'  感化片段长度(帧) 中位 = {sorted(convert_frames_list)[len(convert_frames_list)//2] if convert_frames_list else float("nan"):.0f}  (25fps: 700帧=28秒)')
print(f'  死亡前最后 hp(格? 实为比例) 中位 = {sorted(last_hp_before_zero)[len(last_hp_before_zero)//2] if last_hp_before_zero else float("nan"):.2f}')
print()
print('  结论指示：若 died_in_convert 高 => 死因是「感化引导中被集火」；')
print('           若感化片段很短(几十帧)且开始hp高、末hp=0 => 突然被集火带走；')
print('           若 convert_attempt 低 => 多数祭死局根本没进感化射程(仍是到不了)。')
