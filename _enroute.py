# -*- coding: utf-8 -*-
"""_enroute.py —— 「发现了敌方武器厂，却没起手」的局：祭司在途中/在射程内是怎么死的。

背景（本工程唯一胜利条件 = 祭司感化敌武器厂）：
    P(胜) = P(起手) × 0.76，而 起手 必须 ① 先发现武器厂 ② 祭司活到距武器厂 ≤12 格。
本脚本只问第二道闸：在 ① 成立的局里，祭司为什么没起手。

只用 [BEAT]（按 150 帧分桶，免疫 frame 跳号的取模判据）。
每桶可读：pr@=(x,y) 祭司块坐标 / bbox=(x1..x2,y1..y2) 我全体单位包围盒 /
          pr=(sn.. st.. hp../MAX ccd..) / Mil / nEB / nEA / pm f.. ca.. h.. cnt.. o..

派生量（本脚本的核心）：
  dS   = 祭司距武器厂(块)          —— 与 [LC-DBG] 的 dS 同源（(WSx+1, WSy+1)）
  inBox= 祭司是否在我军包围盒内    —— "祭司有没有人陪"的直接读数
  dBox = 在盒外时到盒边的距离(块)
用法: python _enroute.py fix1 fix2 fix4 fix5
"""
import re, sys, glob, os, collections, statistics as st

MAP_WS = {'map': (11, 86), 'map1': (93, 11), 'map2': (24, 6), 'map3': (82, 20)}


def which_map(bn):
    for k in ('map1', 'map2', 'map3'):
        if ('_' + k + '_') in bn:
            return k
    return 'map'


def outcome(t):
    win = bool(re.search(r'攻城武器厂\(编号:\d+\)被祭司转换', t)) or ('VICTORY! Siege Workshop converted' in t)
    pd = 'DEFEAT: Priest killed' in t
    tcl = bool(re.search(r'市镇中心\(编号:\d+\)被摧毁', t))
    return '胜' if win else ('祭死' if pd else ('TC毁' if tcl else '超时'))


def rows_of(path):
    mp = which_map(os.path.basename(path))
    wx, wy = MAP_WS[mp]
    tx, ty = wx + 1.0, wy + 1.0
    out = []
    for L in open(path, encoding='utf-8', errors='replace'):
        if '[BEAT' not in L:
            continue
        mb = re.search(r'\bb=(\d+)\]', L)
        mp_ = re.search(r'pr@=\(([-0-9.]+),([-0-9.]+)\)', L)
        mh = re.search(r'pr=\(sn(-?\d+) st(-?\d+) hp(-?\d+)/(\d+) ccd(-?\d+)\)', L)
        bb = re.search(r'bbox=\(x([-0-9.]+)\.\.([-0-9.]+),y([-0-9.]+)\.\.([-0-9.]+)\)', L)
        mm = re.search(r'\bMil=(\d+)', L)
        ne = re.search(r'nEB=(\d+) nEA=(\d+)', L)
        if not (mb and mp_ and mh and bb):
            continue
        px, py = float(mp_.group(1)), float(mp_.group(2))
        x1, x2, y1, y2 = [float(g) for g in bb.groups()]
        hp = int(mh.group(3)); mx = int(mh.group(4))
        if hp < 0 or mx <= 0:
            continue
        # 到包围盒的距离（0 = 盒内）
        dx = max(x1 - px, 0.0, px - x2)
        dy = max(y1 - py, 0.0, py - y2)
        dBox = (dx * dx + dy * dy) ** 0.5
        out.append(dict(b=int(mb.group(1)), dS=((px - tx) ** 2 + (py - ty) ** 2) ** 0.5,
                        hp=hp / mx, st=int(mh.group(2)), ccd=int(mh.group(5)),
                        inBox=(dBox <= 0.0), dBox=dBox,
                        mil=int(mm.group(1)) if mm else -1,
                        nEB=int(ne.group(1)) if ne else -1, nEA=int(ne.group(2)) if ne else -1,
                        prx=px, pry=py))
    return mp, out


def main(tags):
    G = collections.defaultdict(list)
    for tag in tags:
        for f in sorted(glob.glob('%s_*_r0_*.ait' % tag)):
            t = open(f, encoding='utf-8', errors='replace').read()
            mp, rs = rows_of(f)
            if not rs:
                continue
            res = outcome(t)
            found = ('Enemy Siege Workshop found' in t)
            qi = sum(1 for L in t.splitlines() if 'converting Siege Workshop' in L)
            G[(tag, mp)].append(dict(f=os.path.basename(f), res=res, found=found, qi=qi, rs=rs, mp=mp))

    for tag in tags:
        print('=' * 96)
        print('tag = %s' % tag)
        print('%-5s %4s %8s %8s %8s | %-34s | %s' % ('map', 'n', '找到WS', '起手局', '胜率', '败因(胜/祭死/超时)', '起手局 起手次数中位'))
        for mp in ('map', 'map1', 'map2', 'map3'):
            gs = G.get((tag, mp))
            if not gs:
                continue
            n = len(gs)
            fo = sum(1 for g in gs if g['found'])
            qn = sum(1 for g in gs if g['qi'] > 0)
            wn = sum(1 for g in gs if g['res'] == '胜')
            co = collections.Counter(g['res'] for g in gs)
            qmd = st.median([g['qi'] for g in gs if g['qi'] > 0]) if qn else 0
            print('%-5s %4d %7d%% %7d%% %7d%% | 胜%d 祭死%d 超时%d TC毁%d | %.0f' % (
                mp, n, 100 * fo / n, 100 * qn / n, 100 * wn / n,
                co.get('胜', 0), co.get('祭死', 0), co.get('超时', 0), co.get('TC毁', 0), qmd))

        # 第二道闸：找到 WS 但没起手
        bad = [g for mp in ('map', 'map1', 'map2', 'map3') for g in G.get((tag, mp), []) if g['found'] and g['qi'] == 0]
        good = [g for mp in ('map', 'map1', 'map2', 'map3') for g in G.get((tag, mp), []) if g['qi'] > 0]
        print()
        print('  —— 第二道闸：找到WS却【从未起手】(%d 局) vs 【起手过】( %d 局) ——' % (len(bad), len(good)))

        def desc(gs, lab):
            if not gs:
                return
            minDs = [min(r['dS'] for r in g['rs']) for g in gs]
            lastB = [g['rs'][-1] for g in gs]
            inB = [sum(1 for r in g['rs'] if r['inBox']) / len(g['rs']) for g in gs]
            co = collections.Counter(g['res'] for g in gs)
            print('    %-14s n=%-3d 结局(胜%d/祭死%d/超时%d/%s) | 距WS最近中位 %5.1f | 末桶 dS %5.1f hp %.2f Mil %4.1f nEA %4.1f | 在盒内桶占比中位 %.0f%%' % (
                lab, len(gs), co.get('胜', 0), co.get('祭死', 0), co.get('超时', 0),
                'TC毁%d' % co.get('TC毁', 0) if co.get('TC毁') else '',
                st.median(minDs), st.median([r['dS'] for r in lastB]), st.median([r['hp'] for r in lastB]),
                st.median([r['mil'] for r in lastB]), st.median([r['nEA'] for r in lastB]),
                100 * st.median(inB)))
        desc(bad, '从未起手')
        desc(good, '起手过')
        print()

        if bad:
            print('    —— 从未起手局：末 6 桶 (dS/hp/st/inBox/dBox/Mil/nEA) ——')
            for g in sorted(bad, key=lambda g: min(r['dS'] for r in g['rs']))[:14]:
                tail = g['rs'][-6:]
                s = ' '.join('%.0f/%.2f/%d/%s/%.1f/%d/%d' % (r['dS'], r['hp'], r['st'], 'in' if r['inBox'] else 'OUT', r['dBox'], r['mil'], r['nEA']) for r in tail)
                print('      %-26s %-4s %s' % (g['f'], g['res'], s))
        print()


if __name__ == '__main__':
    main(sys.argv[1:] or ['fix1'])
