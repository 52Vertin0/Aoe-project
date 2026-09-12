#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提取 ECO 采样行。
v3 格式(2026-09-14): ECO | Fd:X Wd:X St:X Gd:X || workers Fx Wx Gx Sx tot:T || rich:r wStop:.. sStop:.. fStop:.. wT:N gT:M twr:N/M
v2 格式: ECO | Fd:X Wd:X St:X Gd:X || workers Fx Wx Gx Sx || goldRich:.. woodStop:.. stoneStop:.. foodStop:.. woodTarget:N twr:N/M
v1 格式: [frame] ECO | Fd:X Wd:X St:X Gd:X | Frm:N Idle:n(Carry:n) Walk:n Work:n Atk:n | Mil:n E:n
"""
import sys, re, os

V3 = re.compile(
    r"ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+) tot:(\d+) "
    r"\|\| rich:(\d) wStop:(\d) sStop:(\d) fStop:(\d) wT:(\d+) gT:(\d+) twr:(\d+)/(\d+)"
)
V2 = re.compile(
    r"ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+) "
    r"\|\| goldRich:(\d) woodStop:(\d) stoneStop:(\d) foodStop:(\d) woodTarget:(\d) twr:(\d+)/(\d+)"
)
V1 = re.compile(
    r"ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \| Frm:(\d+) Idle:(\d+)\(Carry:(\d+)\) Walk:(\d+) Work:(\d+) Atk:(\d+)"
)

def one(path):
    rows, v1, viol = [], [], []
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            p = line.split('|', 4)
            if len(p) < 5:
                continue
            fr = p[1].strip()
            if not fr.isdigit():
                continue
            fr = int(fr)
            msg = p[4]
            m = V3.search(msg)
            if m:
                g = tuple(int(x) for x in m.groups())
                rows.append((fr,) + g)
                # 一致性自检：工人数之和不得 > 村民总数（双重计数会违反）
                if sum(g[4:8]) > g[8]:
                    viol.append((fr, sum(g[4:8]), g[8]))
                continue
            m = V2.search(msg)
            if m:
                rows.append((fr,) + tuple(int(x) for x in m.groups()))
                continue
            m = V1.search(msg)
            if m:
                v1.append((fr,) + tuple(int(x) for x in m.groups()))
    return rows, v1, viol

def main():
    for f in sys.argv[1:]:
        if not os.path.exists(f):
            continue
        nr, orr, viol = one(f)
        print(f"\n######## {os.path.basename(f)}  新版采样={len(nr)} 旧版采样={len(orr)}")
        if viol:
            print(f"  !! 双重计数告警 {len(viol)} 条（工人和 > 村民数）：{viol[:3]}")
        elif nr:
            print("  √ 工人计数自检通过：全程 工人和 ≤ 村民总数")
        if not nr:
            continue
        print("  帧  (分) | 肉  木  石  金 | 工 F  W  G  S 总 | r/w/s/f wT gT twr")
        step = max(1, len(nr) // 14)
        for r in nr[::step]:
            fr, fd, wd, st, gd, F, W, G, S, T, rich, ws, ss, fs, wt, gt, twr, twrmax = r
            flag = ''
            if wd <= 10 and W >= 4: flag += ' <<木枯'
            if fd <= 20 and F >= 6: flag += ' <<食枯'
            print(f"{fr:6d} ({fr/1500:5.1f}) | {fd:4d} {wd:4d} {st:4d} {gd:4d} | "
                  f" {F:2d} {W:2d} {G:2d} {S:2d} {T:2d} | {rich} {ws} {ss} {fs} {wt:2d} {gt:2d} {twr}/{twrmax}{flag}")
        print("  --- 末 5 条 ---")
        for r in nr[-5:]:
            fr, fd, wd, st, gd, F, W, G, S, T, rich, ws, ss, fs, wt, gt, twr, twrmax = r
            print(f"{fr:6d} ({fr/1500:5.1f}) | {fd:4d} {wd:4d} {st:4d} {gd:4d} | "
                  f" {F:2d} {W:2d} {G:2d} {S:2d} {T:2d} | {rich} {ws} {ss} {fs} {wt:2d} {gt:2d} {twr}/{twrmax}")

if __name__ == '__main__':
    main()
