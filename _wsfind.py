#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_wsfind.py —— 「武器厂发现时刻」是否决定胜负（口径：AIText 事件 + [BEAT] 桶）
用法: python _wsfind.py fixG_map_r0_*.ait
判据:
  胜 = '被祭司转换,归属阵营1->0'
  负 = 'DEFEAT: Priest killed' 或 'DEFEAT: Town Center destroyed'
       ⚠⚠ 口径陷阱（2026-10-06）：**裸 'DEFEAT' 会把 `>> ALL WAVES DEFEATED! Counterattack!` 误判成失败**
       （那是【反攻触发日志】，`UsrAI.cpp:1354`）。实测 base1 96 局里 **79 局含该串（82%）** ⇒
       裸用会让 8 成局凭空变"负"。**必须以 "DEFEAT:" 冒号形式精确匹配失败事件。**
  超时 = 两者皆无（帧到 44951 附近）
输出: 每局 t_ws / 结局 / 结束帧 / 发现→结束余量 / 感化起手时刻
自查: 已知 r0_4 发现 f=39187、胜、结束 42301 ⇒ 余量 3114 帧
"""
import re, sys, os, statistics as st

WS   = re.compile(r'Enemy Siege Workshop found at \((\d+),(\d+)\)')
CONV = re.compile(r'>> Priest converting Siege Workshop! f=(\d+)')
ADV  = re.compile(r'Priest ADVANCE to Siege f=(\d+) d=([\d.]+)')
BEAT = re.compile(r'\[BEAT f=(\d+) b=(\d+)\]')

def parse(p):
    t_ws = t_conv = None
    endf = 0
    dmin = 1e9
    wsxy = None
    for L in open(p, encoding='utf-8', errors='replace'):
        m = BEAT.search(L)
        if m: endf = max(endf, int(m.group(1)))
        m = WS.search(L)
        if m and t_ws is None:
            t_ws = int(L.split('|')[1]); wsxy = (int(m.group(1)), int(m.group(2)))
        m = CONV.search(L)
        if m and t_conv is None:
            t_conv = int(m.group(1))
        m = ADV.search(L)
        if m: dmin = min(dmin, float(m.group(2)))
    raw = open(p, encoding='utf-8', errors='replace').read()
    if '被祭司转换,归属阵营1->0' in raw: out = 'W'
    # ⚠ 精确匹配：裸 'DEFEAT' 会命中 'ALL WAVES DEFEATED!'(反攻触发日志，占 82% 的局)
    elif 'DEFEAT: Priest killed' in raw or 'DEFEAT: Town Center destroyed' in raw: out = 'L'
    else: out = 'T'
    return dict(t_ws=t_ws, t_conv=t_conv, endf=endf, dmin=dmin, out=out, wsxy=wsxy)

def main():
    rows = []
    for p in sys.argv[1:]:
        if not os.path.exists(p): continue
        r = parse(p); r['f'] = os.path.basename(p); rows.append(r)
    rows.sort(key=lambda r: (r['out'], r['t_ws'] or 99999))
    print(f'{"局":<26}{"结局":<5}{"发现WS":>9}{"分钟":>7}{"起手":>8}{"结束帧":>8}{"余量帧":>8}')
    for r in rows:
        tw = r['t_ws']
        conv = r['t_conv']
        print(f'{r["f"]:<26}{r["out"]:<5}{str(tw):>9}{(f"{tw/1500:.1f}" if tw else "-"):>7}'
              f'{str(conv):>8}{r["endf"]:>8}{(str(r["endf"]-tw) if tw else "-"):>8}')
    print()
    for o in ('W','L','T'):
        sub = [r for r in rows if r['out'] == o]
        if not sub: continue
        tw = [r['t_ws'] for r in sub if r['t_ws']]
        # 余量：结束帧 - 发现帧
        sl = [r['endf'] - r['t_ws'] for r in sub if r['t_ws']]
        mtw = st.median(tw) if tw else None
        msl = st.median(sl) if sl else None
        s_tw = f'{mtw:.0f}帧({mtw/1500:.1f}分)' if mtw is not None else '-'
        s_sl = f'{msl:.0f}帧({msl/1500:.1f}分)' if msl is not None else '-'
        print(f'结局 {o}: n={len(sub):2d}  有发现={len(tw):2d}  发现中位={s_tw}  余量中位={s_sl}')

if __name__ == '__main__':
    main()
