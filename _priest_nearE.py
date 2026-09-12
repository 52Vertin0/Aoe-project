# -*- coding: utf-8 -*-
"""_priest_nearE.py —— 用 Priest st= 诊断行（含 nearE/threat/mode/nearAlly/mvcd）剖析
「反攻期祭司为什么落在 12 格感化射程之外」。

Priest st=%1 hp=%2 nearE=%3 threat=%4 mode=%5 | ally=%6 wound25=%7 nearAlly=%8BL cd=%9
  st = NowState(0 idle/1 walking/2 working/3 attacking)
  nearE = 到最近敌(军队+箭塔)距离(格)；threat 同上但含威胁射程修正
  mode  = priestMode（0 非逃 / 1 逃）  cd = priestMoveCooldown
用法： python _priest_nearE.py <TAG> [TAG2 ...]
"""
import glob
import re
import statistics as st
import sys

POP = re.compile(r'POP-FULL COUNTERATTACK! Frame=(\d+)')
CA = re.compile(r'ALL WAVES DEFEATED! Counterattack! Frame=(\d+)')
PST = re.compile(r'Priest st=(\d+) hp=([\d.]+) nearE=([-\d.e]+) threat=([-\d.e]+) mode=(\d+) \| ally=(\d+) wound25=(\d+) nearAlly=([-\d.e]+)BL cd=(\d+)')


def outcome(t):
    if '被祭司转换,归属阵营1->0' in t:
        return '胜'
    if 'DEFEAT: Priest killed' in t:
        return '祭死'
    if 'DEFEAT: Town Center destroyed' in t or '敌方 摧毁主营' in t:
        return 'TC毁'
    return '超时'


def fv(s):
    try:
        v = float(s)
    except ValueError:
        return None
    return None if v > 1e4 else v


def main(tags):
    print('=' * 100)
    print('反攻期祭司「距最近敌」剖析（源：Priest st= 诊断行，每 100 帧一行）')
    print('=' * 100)
    for tag in tags:
        rows = []
        for f in sorted(glob.glob('%s_*_r0_*.ait' % tag)):
            t = open(f, encoding='utf-8', errors='replace').read()
            cand = [int(x.group(1)) for x in (POP.search(t), CA.search(t)) if x]
            atk = min(cand) if cand else 33000
            res = outcome(t)
            for L in t.splitlines():
                p = L.split(' | ', 3)
                if len(p) < 2:
                    continue
                try:
                    fr = int(p[1])
                except ValueError:
                    continue
                if fr < atk:
                    continue
                m = PST.search(L)
                if not m:
                    continue
                ne = fv(m.group(3))
                if ne is None:
                    ne = 999.0          # 视野内无敌 → 记为极远
                rows.append(dict(ne=ne, hp=float(m.group(2)), mode=int(m.group(5)),
                                 ally=int(m.group(6)), wound=int(m.group(7)),
                                 na=fv(m.group(8)), cd=int(m.group(9)), res=res))
        if not rows:
            print('[%s] 无数据' % tag)
            continue
        N = len(rows)
        print()
        print('### %s  反攻期样本=%d 行' % (tag, N))
        for lab, sel in (('nearE<=12 (可感化窗口)', lambda r: r['ne'] <= 12),
                         ('12<nearE<=18', lambda r: 12 < r['ne'] <= 18),
                         ('18<nearE<=28', lambda r: 18 < r['ne'] <= 28),
                         ('nearE>28', lambda r: r['ne'] > 28),
                         ('nearE=999(视野无敌)', lambda r: r['ne'] >= 999)):
            g = [r for r in rows if sel(r)]
            if not g:
                continue
            print('  %-24s %6.1f%%  n=%5d | mode=1(逃)占%5.1f%%  cd中位=%3.0f  cd>0占%5.1f%%  hp中位=%.2f  nearAlly中位=%s  wound25中位=%.0f'
                  % (lab, 100.0 * len(g) / N, len(g),
                     100.0 * sum(1 for r in g if r['mode'] == 1) / len(g),
                     st.median([r['cd'] for r in g]),
                     100.0 * sum(1 for r in g if r['cd'] > 0) / len(g),
                     st.median([r['hp'] for r in g]),
                     ('%.1f' % st.median([r['na'] for r in g if r['na'] is not None])) if any(r['na'] is not None for r in g) else 'n/a',
                     st.median([r['wound'] for r in g])))
        print()
        print('  按结局：')
        for res in ('胜', '祭死', '超时', 'TC毁'):
            g = [r for r in rows if r['res'] == res]
            if not g:
                continue
            le12 = 100.0 * sum(1 for r in g if r['ne'] <= 12) / len(g)
            print('   %-6s n=%5d  nearE中位=%6.1f  <=12格占%5.1f%%  mode=1占%5.1f%%  cd>0占%5.1f%%  hp中位=%.2f'
                  % (res, len(g), st.median([r['ne'] for r in g]), le12,
                     100.0 * sum(1 for r in g if r['mode'] == 1) / len(g),
                     100.0 * sum(1 for r in g if r['cd'] > 0) / len(g),
                     st.median([r['hp'] for r in g])))


if __name__ == '__main__':
    main(sys.argv[1:] or ['club8n'])
