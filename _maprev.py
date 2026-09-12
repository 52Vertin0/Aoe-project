#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_maprev.py —— 反推 OJ 抽到的地图与朝向
============================================================================================
用法：
    python _maprev.py                          # 只列出四张图的双方建筑坐标（速查表）
    python _maprev.py "<OJ 日志路径>"            # 自动从日志反推 OJ 用的是哪张图

原理：
    `-map` / `-rotate` 未指定时【每局随机】（GlobalVariate.cpp:734 / 793-806）。
    OJ 日志里必留两类线索 ——
      ① 地图名字符串本身（`map3.njust` 之类，常有）
      ② `>> Enemy Siege Workshop found at (x,y)!` 的敌方武器厂块坐标（Num=11 那座）
    把 ② 与各 map*.njust 的 Building_*(BlockDR/BlockUR/Num=11) 逐位比对即可锁定。
============================================================================================
"""
import json, glob, os, re, sys

WEAPON_NUM = 11          # BUILDING_* 里 Num=11 = 攻城武器厂（BuildDisplayName[11]="攻城武器厂"）


def load_maps(dirpath='.'):
    out = []
    for p in sorted(glob.glob(os.path.join(dirpath, '*.njust'))):
        try:
            j = json.load(open(p, encoding='utf-8', errors='replace'))
        except Exception as e:
            print('%s 解析失败: %s' % (p, e)); continue
        mine, foe = [], []
        for k, v in j.items():
            if not k.startswith('Building_'):
                continue
            try:
                dr = int(v.get('BlockDR')); ur = int(v.get('BlockUR'))
                num = int(v.get('Num')); own = str(v.get('Own', ''))
            except Exception:
                continue
            (mine if own == 'WLH' else foe if own == 'LZ' else []).append((dr, ur, num))
        w = [b for b in foe if b[2] == WEAPON_NUM]
        out.append(dict(path=p, name=os.path.basename(p), mine=mine, foe=foe, weapon=w[0] if w else None))
    return out


def rng(a, i):
    return '%d..%d' % (min(x[i] for x in a), max(x[i] for x in a)) if a else '—'


def show(maps):
    print('%-16s %-22s %-22s %s' % ('地图', '我方 6 建筑 (x / y)', '敌方 6 建筑 (x / y)', '敌武器厂'))
    print('-' * 88)
    for m in maps:
        print('%-16s x%-10s y%-11s x%-10s y%-11s %s' % (
            m['name'], rng(m['mine'], 0), rng(m['mine'], 1),
            rng(m['foe'], 0), rng(m['foe'], 1),
            str(m['weapon'][:2]) if m['weapon'] else '—'))


def guess(maps, logpath):
    raw = open(logpath, encoding='utf-8', errors='replace').read()
    print('=== 日志 %s ===' % os.path.basename(logpath))
    names = sorted(set(re.findall(r'map\d*\.njust', raw)))
    if names:
        print('  ① 日志中直接出现的地图名: %s' % ', '.join(names))
    shots = re.findall(r'Enemy Siege Workshop found at \((\d+),(\d+)\)', raw)
    if not shots:
        print('  ② 未找到 "Enemy Siege Workshop found at" ⇒ 只能依赖 ① 或开局包围盒人工比对。')
        return
    dr, ur = int(shots[0][0]), int(shots[0][1])
    print('  ② 日志中敌方武器厂块坐标 = (%d,%d)（出现 %d 次）' % (dr, ur, len(shots)))
    hit = [m for m in maps if m['weapon'] and m['weapon'][0] == dr and m['weapon'][1] == ur]
    if len(hit) == 1:
        m = hit[0]
        print('\n  >>> 反推结论: 地图 = %s（未旋转，坐标为原始值）' % m['name'])
        print('      我方建筑 x%-10s y%-10s | 敌方建筑 x%-10s y%-10s' % (
            rng(m['mine'], 0), rng(m['mine'], 1), rng(m['foe'], 0), rng(m['foe'], 1)))
        print('      ⚠ 若开局村民包围盒与上表「我方」范围差得很远 ⇒ 需再试 90/180/270 旋转。')
        print('      运行方式: MAP=%s ROT=0 N=3 bash _beat_run.sh' % m['name'])
    elif not hit:
        print('\n  >>> 无匹配 —— 该坐标可能是【旋转后】的，需要按 90/180/270 变换后再比对。')
        for m in maps:
            if not m['weapon']:
                continue
            x, y = m['weapon'][0], m['weapon'][1]
            print('      %-16s 原始(%-3d,%-3d)  180°->(%-3d,%-3d)  镜像x->(%-3d,%-3d)  镜像y->(%-3d,%-3d)' % (
                m['name'], x, y, 99 - x, 99 - y, 99 - x, y, x, 99 - y))
    else:
        print('\n  >>> 多张图命中: %s ⇒ 用开局包围盒人工区分。' % ', '.join(m['name'] for m in hit))


if __name__ == '__main__':
    HERE = os.path.dirname(os.path.abspath(__file__))
    maps = load_maps(HERE or '.')
    show(maps)
    if len(sys.argv) > 1:
        print()
        guess(maps, sys.argv[1])
