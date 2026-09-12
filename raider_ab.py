# -*- coding: utf-8 -*-
"""突击者策略 A/B 机制量对拍：复合弓兵推进深度 + 伤亡 + 祭司存活
口径：
  - HumanMove:复合弓兵 <SN> 移动至 (x,y)  → 我方下发的移动目标（引擎日志，不受采样影响）
  - 推进深度代理 = x+y（本图我方 TC 在左下 (≈19,18)，敌方角落在右上 (≈97,97)，x+y 越大越靠前）
  - 只统计反攻期 f>=33000
"""
import re, sys, os, glob
from collections import defaultdict

FRAME_START = 33000

def parse(path):
    txt = open(path, encoding='utf-8', errors='replace').read()
    r = {'file': os.path.basename(path)}
    xs = []
    for m in re.finditer(r'HumanMove:复合弓兵 (\d+) 移动至 \(([-\d.]+),([-\d.]+)\)', txt):
        # 需要帧号：取该行
        pass
    # 逐行处理（拿帧号）
    for line in txt.split('\n'):
        if 'HumanMove:复合弓兵' not in line:
            continue
        mf = re.search(r'\|\s*(\d+)\s*\|', line)
        if not mf:
            continue
        f = int(mf.group(1))
        if f < FRAME_START:
            continue
        m = re.search(r'移动至 \(([-\d.]+),([-\d.]+)\)', line)
        if m:
            xs.append(float(m.group(1)) + float(m.group(2)))
    xs.sort()
    r['n_move'] = len(xs)
    r['max_xy'] = xs[-1] if xs else 0.0
    r['p50_xy'] = xs[len(xs)//2] if xs else 0.0
    r['p90_xy'] = xs[int(len(xs)*0.9)] if xs else 0.0
    # 胜负
    r['win'] = len(re.findall(r'VICTORY! Siege Workshop converted', txt))
    r['lose'] = 1 if re.search(r'DEFEAT:', txt) else 0
    r['conv'] = len(re.findall(r'设置转换目标为 攻城武器厂', txt))
    # 我方可感化/祭司相关：祭司阵亡帧
    mp = re.search(r'\| (\d+) \|[^\n]*DEFEAT: Priest killed', txt)
    r['priestDeadF'] = int(mp.group(1)) if mp else -1
    # 我方单位阵亡总数（任何 (编号:N)被摧毁 且 第4列=0）
    dead_us = 0
    for line in txt.split('\n'):
        if '被摧毁' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 4 and parts[3] == '0':
                dead_us += 1
    r['dead_us'] = dead_us
    r['lastF'] = 0
    mf = re.findall(r'\|\s*(\d+)\s*\|', txt)
    if mf:
        r['lastF'] = max(int(x) for x in mf)
    return r

def tab(rows, title):
    print('== ' + title)
    print('%-8s %6s %9s %9s %9s | %4s %4s %5s %6s' % (
        'file', 'nMove', 'p50(x+y)', 'p90(x+y)', 'max(x+y)', 'WIN', 'LOSE', 'conv', '我方阵亡'))
    for r in rows:
        print('%-8s %6d %9.0f %9.0f %9.0f | %4d %4d %5d %6d' % (
            r['file'], r['n_move'], r['p50_xy'], r['p90_xy'], r['max_xy'],
            r['win'], r['lose'], r['conv'], r['dead_us']))
    n = len(rows)
    if n:
        print('-- 均值: nMove=%.0f p50=%.0f p90=%.0f max=%.0f 胜=%d 负=%d 起手=%d 我方阵亡=%.1f' % (
            sum(x['n_move'] for x in rows)/n, sum(x['p50_xy'] for x in rows)/n,
            sum(x['p90_xy'] for x in rows)/n, sum(x['max_xy'] for x in rows)/n,
            sum(x['win'] for x in rows), sum(x['lose'] for x in rows),
            sum(x['conv'] for x in rows), sum(x['dead_us'] for x in rows)/n))
    print()

if __name__ == '__main__':
    rd = [parse(f) for f in sorted(glob.glob('rd?.ait'))]
    pe = [parse(f) for f in sorted(glob.glob('pe?.ait'))]
    tab(rd, 'rd1-8（突击者版）')
    tab(pe, 'pe1-8（基线，同逻辑）')
