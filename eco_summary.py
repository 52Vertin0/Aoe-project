#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全部 5 批实测汇总（40 局）。"""
import os, re, statistics

BATCHES = [
    ('pu', '基线（pullkite 终版）', '未改动'),
    ('ev', '悲观集', '双重计数修复+滞回带+采石解绑+woodTarget人口相关'),
    ('ew', '回退版', '回退 woodTarget + 新增缺口回补'),
    ('ex', '激进集', '再加 goldTarget 基数(totalFarmers×2/5)'),
    ('ey', '最小修复集', '双重计数修复+goldTarget基数+findAnyFarmer'),
    ('ez', '基线复现', '纯基线，验证方差'),
]

V2 = re.compile(r"ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+)(?!\d)")


def one(b):
    w = l = t = 0
    cb = pf = 0
    priest = 0
    fd, wd = [], []
    farms = 0
    for i in range(1, 9):
        f = f"{b}{i}.ait"
        if not os.path.exists(f):
            continue
        t += 1
        vicF = defF = 0
        rea = ''
        for line in open(f, encoding='utf-8', errors='replace'):
            p = line.split('|', 4)
            if len(p) < 5:
                continue
            fr_s = p[1].strip()
            if not fr_s.isdigit():
                continue
            fr = int(fr_s)
            msg = p[4]
            own = p[3].strip() == '0'
            if own and '产生了新的复合弓兵' in msg:
                cb += 1
            if own and '产生了新的方阵兵' in msg:
                pf += 1
            if 'BUILD-ISSUE' in msg and 'type=4' in msg:
                farms += 1
            low = msg.lower()
            if 'victory' in low and vicF == 0:
                vicF = fr
            if 'defeat:' in low and defF == 0:
                defF = fr
                rea = msg.split('DEFEAT:')[-1].replace('!', '').strip()
            m = V2.search(msg)
            if m:
                fd.append(int(m.group(1))); wd.append(int(m.group(2)))
        if 'Priest' in rea:
            priest += 1
        if vicF and (not defF or vicF <= defF):
            w += 1
        elif defF:
            l += 1
    # 锯齿
    def saw(v, hi, lo):
        c = 0; ab = False
        for x in v:
            if x >= hi:
                ab = True
            elif x <= lo and ab:
                c += 1; ab = False
        return c
    return dict(w=w, l=l, d=t-w-l, t=t, cb=cb, pf=pf, priest=priest, farms=farms,
                fdM=statistics.mean(fd) if fd else 0, wdM=statistics.mean(wd) if wd else 0,
                sawW=saw(wd, 150, 30), sawF=saw(fd, 300, 50))


if __name__ == '__main__':
    print(f"{'批次':<8}{'改动':<44}{'胜/负/平':>10}{'复合弓':>8}{'方阵':>6}{'农场令':>7}{'祭司死':>7}{'木均':>7}{'木锯齿':>7}")
    rows = []
    for b, name, chg in BATCHES:
        s = one(b)
        rows.append((b, name, chg, s))
        wld = f"{s['w']}/{s['l']}/{s['d']}"
        print(f"{b:<8}{chg:<44}{wld:>10}{s['cb']:>8}{s['pf']:>6}"
              f"{s['farms']:>7}{s['priest']:>7}{s['wdM']:>7.0f}{s['sawW']:>7}")
    # 基线合并
    base_w = rows[0][3]['w'] + rows[5][3]['w']
    base_t = rows[0][3]['t'] + rows[5][3]['t']
    print(f"\n基线合并（pu+ez）：{base_w} 胜 / {base_t} 局 = {100.0*base_w/base_t:.1f}%")
    # Fisher 精确检验（基线合并 vs ey）
    import math
    ey = rows[4][3]
    n1, n2 = base_t, ey['t']
    k1, k2 = base_w, ey['w']
    N, K = n1 + n2, k1 + k2
    def comb(a, b):
        return math.comb(a, b)
    tot = comb(N, K)
    p = 0
    for x in range(k1, min(n1, K) + 1):
        if K - x <= n2:
            p += comb(n1, x) * comb(n2, K - x)
    for x in range(0, k1 + 1):
        if K - x <= n2:
            p += comb(n1, x) * comb(n2, K - x)
    print(f"Fisher 精确检验（双尾，基线合并 vs ey）：p ≈ {min(1.0, p/tot):.3f}")
