#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比金工实际数与黄金产出。"""
import re, sys, statistics

V3 = re.compile(r"ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+) tot:(\d+)")
V2 = re.compile(r"ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+)(?!\d)")


def scan(f):
    """返回 (肉,木,金, F,W,G,S, tot, gT)。"""
    out = []
    for line in open(f, encoding='utf-8', errors='replace'):
        p = line.split('|', 4)
        if len(p) < 5:
            continue
        fr = p[1].strip()
        if not fr.isdigit():
            continue
        msg = p[4]
        m = V3.search(msg)
        if m:
            g = [int(x) for x in m.groups()]
            mt = re.search(r"gT:(\d+)", msg)
            out.append((int(fr), g[0], g[1], g[3], g[4], g[5], g[6], g[7], g[8],
                        int(mt.group(1)) if mt else -1))
            continue
        m = V2.search(msg)
        if m:
            g = [int(x) for x in m.groups()]
            out.append((int(fr), g[0], g[1], g[3], g[4], g[5], g[6], g[7], -1, -1))
    return out


def run(files, label):
    G, GD, T, GT, F = [], [], [], [], []
    for f in files:
        for r in scan(f):
            G.append(r[6]); GD.append(r[2]); F.append(r[4])
            if r[8] > 0:
                T.append(r[8])
            if r[9] >= 0:
                GT.append(r[9])
    m = lambda v: statistics.mean(v) if v else 0
    print(f"{label:22} 金工统计 G 均值={m(G):6.1f} 峰值={max(G) if G else 0:3d} | "
          f"食物工 F 均值={m(F):5.1f} | 黄金 均值={m(GD):6.1f} 峰值={max(GD) if GD else 0:4d} | "
          f"tot={m(T):5.1f} | gT={m(GT):5.1f}")


if __name__ == '__main__':
    run(['pu%d.ait' % i for i in range(1, 9)], 'pu 基线(虚高口径)')
    run(['ex%d.ait' % i for i in range(1, 9)], 'ex 激进集')
    run(['ey%d.ait' % i for i in range(1, 9)], 'ey 最小修复集')
    print("\n=== ey1 逐包曲线（只看偶数包）===")
    for r in scan('ey1.ait'):
        if r[0] % 1200 == 0:
            print(f"  f={r[0]:>6} 肉{r[1]:5d} 木{r[2]:5d} 金{r[3]:5d} | "
                  f"F{r[4]:2d} W{r[5]:2d} G{r[6]:2d} S{r[7]:2d} tot{r[8]:2d} | gT{r[9]:2d}")
