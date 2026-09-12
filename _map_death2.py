# -*- coding: utf-8 -*-
"""earlyclub8 版 map 图：祭死局死亡前 30 个 BEAT 的 hp 轨迹 + 状态 + 位移。
目标：判定死因机制
  - 站桩感化被集火：位移≈0、hp 单调降、状态多为 WORKING(2)
  - 逃跑落点仍在火力内：位移大、状态在逃/走、但 hp 仍归零
字段口径：pr=(sn\d+ st(\d+) hp(\d+)/100 ccd(-?\d+))；pr@=(x,y)
状态映射（引擎标准）：0=IDLE 1=WALKING 2=WORKING(引导/感化/治疗) 3=ATTACKING
"""
import re, glob, os, collections, math

TAG = 'earlyclub8'
files = sorted(glob.glob(f'{TAG}_map_r0_*.ait'))
WIN = 30

def parse_pr(line):
    m = re.search(r'pr=\(sn\d+ st(\d+) hp(\d+)/100 ccd(-?\d+)\)', line)
    if not m: return None
    x = re.search(r'pr@=\(([\d.]+),([\d.]+)\)', line)
    d = dict(st=int(m.group(1)), hp=int(m.group(2)), ccd=int(m.group(3)))
    if x: d['x'], d['y'] = float(x.group(1)), float(x.group(2))
    return d

rows = []
for fn in files:
    t = open(fn, encoding='utf-8', errors='replace').read()
    if 'DEFEAT: Priest killed' not in t:
        continue
    # 滚动缓冲：最后 WIN 个 pr 条目
    buf = []
    for line in t.splitlines():
        if '[BEAT' in line:
            p = parse_pr(line)
            if p:
                buf.append(p)
                if len(buf) > WIN: buf.pop(0)
        elif 'DEFEAT: Priest killed' in line:
            if buf:
                rows.append((os.path.basename(fn), list(buf)))
            break

def summarize(fn, buf):
    # buf: 死亡前 WIN 个 pr 条目（时间升序）
    hps = [b['hp'] for b in buf]
    sts = [b['st'] for b in buf]
    # 位移总量
    move = 0.0
    for i in range(1, len(buf)):
        if 'x' in buf[i] and 'x' in buf[i-1]:
            move += math.hypot(buf[i]['x']-buf[i-1]['x'], buf[i]['y']-buf[i-1]['y'])
    # 状态占比
    from collections import Counter
    sc = Counter(sts)
    # 站桩判据：最后 15 帧位移 < 5 格
    tail = buf[-15:]
    tail_move = 0.0
    for i in range(1, len(tail)):
        if 'x' in tail[i] and 'x' in tail[i-1]:
            tail_move += math.hypot(tail[i]['x']-tail[i-1]['x'], tail[i]['y']-tail[i-1]['y'])
    # hp 起点（窗口首帧）
    hp_start = hps[0] if hps else -1
    # 在 60% / 25% 以下的帧数占比
    below60 = sum(1 for h in hps if h < 60)
    below25 = sum(1 for h in hps if h < 25)
    # 是否单调降（站桩集火特征）
    mono = all(hps[i] >= hps[i+1] for i in range(len(hps)-1))
    return dict(fn=fn, n=len(buf), hp0=hp_start, hp_min=min(hps),
                move_total=move, tail_move=tail_move,
                st_mode=sc.most_common(1)[0][0], st_counts=dict(sc),
                below60=below60, below25=below25, mono=mono)

summ = [summarize(fn, buf) for fn, buf in rows]
print('=' * 110)
print(f'{TAG} 祭死局死亡前态势（n={len(summ)} 局，每局最后 {WIN} 个 BEAT 采样）')
print('=' * 110)
standing = 0   # 站桩感化型
fleeing = 0    # 逃跑型
for s in summ:
    stand = (s['tail_move'] < 5.0) and (s['st_mode'] == 2)
    if stand: standing += 1
    elif s['tail_move'] >= 5.0: fleeing += 1
    tag = '站桩感化' if stand else ('逃跑中' if s['tail_move']>=5.0 else '混合')
    print(f"{s['fn'][-22]:22} | {tag:7} | hp0={s['hp0']:3} hp末={s['hp_min']:3} "
          f"尾位移={s['tail_move']:5.1f} 总位移={s['move_total']:6.1f} "
          f"st_mode={s['st_mode']}({s['st_counts']}) 单调降={s['mono']} "
          f"<60%帧={s['below60']}/{s['n']} <25%帧={s['below25']}/{s['n']}")
print('-' * 110)
print(f"机制判定：站桩感化被集火(尾位移<5且状态=WORKING) = {standing} 局")
print(f"          逃跑中(尾位移>=5)                       = {fleeing} 局")
print(f"          其余(混合/数据不全)                     = {len(summ)-standing-fleeing} 局")
# 平均 hp 轨迹（按窗口位置）略；逐局首尾已在上表
print('=' * 110)
