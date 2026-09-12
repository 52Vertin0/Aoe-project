#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_milseries.py —— 军队存亡时间序列（口径：只用 [BEAT] 桶采样，免疫 frame 跳号）
用法: python _milseries.py fixG_map_r0_3.ait [fixG_map_r0_4.ait ...]
输出: 每局每 10 桶（=1500 帧 = 1 分钟）抽样一行: 分钟 | Mil | nMy | nEA | arch | hp | 事件
自查: 先用已知末态核对（r0_3 末桶应 Mil=0 nMy=2）
"""
import re, sys, os

BEAT = re.compile(r'\[BEAT f=(\d+) b=(\d+)\]')
def g(pat, s, d=None, cast=float):
    m = re.search(pat, s)
    if not m: return d
    return cast(m.group(1))

def series(path):
    rows = {}
    order = []
    for L in open(path, encoding='utf-8', errors='replace'):
        if '[BEAT' not in L: continue
        m = BEAT.search(L)
        if not m: continue
        f, b = int(m.group(1)), int(m.group(2))
        body = L[m.end():]
        row = dict(
            f=f, b=b,
            st=g(r'st=(\w+)', body, '?', str),
            Frm=g(r'Frm=(-?\d+)', body, 0, int),
            Mil=g(r'Mil=(\d+)', body, 0, int),
            nMy=g(r'nMy=(\d+)', body, None, int),
            nEA=g(r' nEA=(\d+)', body, None, int),
            nEB=g(r'nEB=(\d+)', body, None, int),
            arch=g(r'arch=(\d+)', body, None, int),
            hop=g(r'hop=(\d+)', body, None, int),
            php=g(r'hp(\d+)/(\d+)', body, None, int),
        )
        rows[b] = row          # 同桶后者覆盖（跳号导致重复打）
        if b not in order: order.append(b)
    return [rows[b] for b in sorted(order)]

def main():
    for p in sys.argv[1:]:
        if not os.path.exists(p):
            print(f'!! 缺文件 {p}'); continue
        S = series(p)
        if not S:
            print(f'== {p}: 无 [BEAT] 行 =='); continue
        print(f'== {os.path.basename(p)}  桶数={len(S)}  末桶 b={S[-1]["b"]} f={S[-1]["f"]}')
        print('  分钟 |  Mil |  Frm | nMy | nEA | arch | prhp | st')
        prev = None
        for r in S:
            if r['b'] % 10: continue                     # 每 10 桶 = 1500 帧 = 1 分钟
            mark = ''
            if prev is not None:
                if prev['Frm'] > 5 and r['Frm'] < prev['Frm'] * 0.7: mark += '  <<< 村民锐减'
                if prev['Mil'] > 0 and r['Mil'] == 0: mark += '  <<< 军队归零'
                elif prev['Mil'] > 0 and r['Mil'] < prev['Mil'] * 0.5: mark += '  <<< 军队腰斩'
            print(f'  {r["f"]//1500:3d}  | {r["Mil"]:4d} | {r["Frm"]:4d} | {str(r["nMy"]):>3} | {str(r["nEA"]):>3} | {str(r["arch"]):>4} | {str(r["php"]):>4} | {r["st"]}{mark}')
            prev = r

if __name__ == '__main__':
    main()
