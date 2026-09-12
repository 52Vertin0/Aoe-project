# -*- coding: utf-8 -*-
"""Raider 突击者策略观测脚本
口径：
  - RAIDER-PICK 选出突击者(记录 RaiderLoc / D)
  - RAIDER-ADV  向 D 推进(只发一次)
  - RAIDER-RET  被攻击/6格内有敌 → 撤回 RaiderLoc(只发一次)
  - RAIDER-ESC  编队(闲置复合弓兵+祭司)朝敌方角落移动 2 格(只发一次)
  - 胜负只认 DebugText: VICTORY / DEFEAT
"""
import re, sys, os, glob

def parse(path):
    txt = open(path, encoding='utf-8', errors='replace').read()
    r = {}
    r['file'] = os.path.basename(path)
    r['pick'] = len(re.findall(r'RAIDER-PICK', txt))
    r['adv']  = len(re.findall(r'RAIDER-ADV', txt))
    r['ret']  = len(re.findall(r'RAIDER-RET', txt))
    r['esc']  = len(re.findall(r'RAIDER-ESC', txt))
    # 胜/负（判定必须带冒号语义）
    r['win']  = len(re.findall(r'VICTORY! Siege Workshop converted', txt))
    r['lose_pr'] = len(re.findall(r'DEFEAT: Priest killed', txt))
    r['lose_tc'] = len(re.findall(r'DEFEAT: Town Center destroyed', txt))
    r['conv'] = len(re.findall(r'设置转换目标为 攻城武器厂', txt))
    # 编队 n 的分布
    ns = [int(x) for x in re.findall(r'RAIDER-ESC f=\d+ 编队朝角落移动2格 n=(\d+)', txt)]
    r['esc_n_max'] = max(ns) if ns else 0
    r['esc_n_avg'] = (sum(ns) / len(ns)) if ns else 0.0
    # 最后帧
    frames = [int(x) for x in re.findall(r'\[RAIDER-\w+ f=(\d+)\]', txt)]
    r['lastF'] = max(frames) if frames else 0
    # 复合弓兵数量（末尾 st 日志）
    return r

def main(files):
    rows = [parse(f) for f in files]
    print('%-10s %5s %5s %5s %5s %5s | %4s %4s | %5s %5s' % (
        'file', 'PICK', 'ADV', 'RET', 'ESC', 'escN', 'WIN', 'LOSE', 'conv', 'lastF'))
    print('-' * 84)
    W = L = 0
    for r in rows:
        lose = r['lose_pr'] + r['lose_tc']
        if r['win']: W += 1
        if lose: L += 1
        print('%-10s %5d %5d %5d %5d %5.1f | %4d %4d | %5d %5d' % (
            r['file'], r['pick'], r['adv'], r['ret'], r['esc'], r['esc_n_avg'],
            r['win'], lose, r['conv'], r['lastF']))
    print('-' * 84)
    print('汇总: 局数=%d  胜=%d  负=%d  平/超时=%d' % (len(rows), W, L, len(rows) - W - L))
    print('均值: PICK=%.1f ADV=%.1f RET=%.1f ESC=%.1f' % (
        sum(r['pick'] for r in rows) / len(rows),
        sum(r['adv'] for r in rows) / len(rows),
        sum(r['ret'] for r in rows) / len(rows),
        sum(r['esc'] for r in rows) / len(rows)))

if __name__ == '__main__':
    fs = []
    for a in sys.argv[1:]:
        fs.extend(sorted(glob.glob(a)))
    main(fs)
