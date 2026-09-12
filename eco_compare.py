#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资源采集分配：改前(pu) vs 改后(ev) 对比。
核心指标：
  · 资源谷底率  —— 肉≤30 / 木≤15 的采样占比（越低越好：说明不再"榨干见底"）
  · 资源均值    —— 肉/木/金的平均水位（越高越好：说明供给跟得上）
  · 锯齿次数    —— 肉/木从高位(>300/>150)跌到低位(<50/<30)的次数（越少越好）
  · 采石覆盖率  —— 采石工 S>0 的采样占比（改前因"14分钟后永久停采"应为 0）
  · 计数自检    —— 工人数之和 > 村民总数的采样条数（双重计数会违规，改后应为 0）
  · 胜负        —— 需 DEFEAT: 带冒号（ALL WAVES DEFEATED! 含 'DEFEAT' 子串会误判）
"""
import sys, re, os, glob
from collections import defaultdict

V3 = re.compile(
    r"ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+) tot:(\d+) "
    r"\|\| rich:(\d) wStop:(\d) sStop:(\d) fStop:(\d) wT:(\d+) gT:(\d+) twr:(\d+)/(\d+)")
V2 = re.compile(
    r"ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+) "
    r"\|\| goldRich:(\d) woodStop:(\d) stoneStop:(\d) foodStop:(\d) woodTarget:(\d) twr:(\d+)/(\d+)")


def load(path):
    st = dict(fd=[], wd=[], st_=[], gd=[], F=[], W=[], G=[], S=[], T=[],
              viol=0, stoneCov=0, n=0, vicF=0, defF=0, vill=0)
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            p = line.split('|', 4)
            if len(p) < 5:
                continue
            fr_s = p[1].strip()
            if not fr_s.isdigit():
                continue
            fr = int(fr_s)
            msg = p[4]
            m = V3.search(msg)
            if m:
                g = [int(x) for x in m.groups()]
                st['fd'].append(g[0]); st['wd'].append(g[1]); st['st_'].append(g[2]); st['gd'].append(g[3])
                st['F'].append(g[4]); st['W'].append(g[5]); st['G'].append(g[6]); st['S'].append(g[7])
                st['T'].append(g[8]); st['n'] += 1
                if sum(g[4:8]) > g[8]:
                    st['viol'] += 1
                if g[7] > 0:
                    st['stoneCov'] += 1
                continue
            m = V2.search(msg)
            if m:
                g = [int(x) for x in m.groups()]
                st['fd'].append(g[0]); st['wd'].append(g[1]); st['st_'].append(g[2]); st['gd'].append(g[3])
                st['F'].append(g[4]); st['W'].append(g[5]); st['G'].append(g[6]); st['S'].append(g[7])
                st['n'] += 1
                if g[7] > 0:
                    st['stoneCov'] += 1
                continue
            low = msg.lower()
            if '产生了新的村民' in msg and p[3].strip() == '0':
                st['vill'] += 1
            if 'victory' in low and st['vicF'] == 0:
                st['vicF'] = fr
            # ★ 必须带冒号：'ALL WAVES DEFEATED!' 含 'DEFEAT' 子串
            if 'defeat:' in low and st['defF'] == 0:
                st['defF'] = fr
    return st


def sawtooth(v, hi, lo):
    """统计"从高位跌破低位"的次数（跨越下降沿）。"""
    c = 0; above = False
    for x in v:
        if x >= hi:
            above = True
        elif x <= lo and above:
            c += 1; above = False
    return c


def summ(files):
    agg = dict(fd=[], wd=[], gd=[], S=[], W=[], F=[], n=0, viol=0, stoneCov=0,
               vill=[], wins=0, losses=0, lowF=0, lowW=0, sawF=0, sawW=0, ndone=0)
    for f in files:
        if not os.path.exists(f):
            continue
        s = load(f)
        if s['n'] == 0:
            continue
        agg['ndone'] += 1
        agg['fd'] += s['fd']; agg['wd'] += s['wd']; agg['gd'] += s['gd']
        agg['S'] += s['S']; agg['W'] += s['W']; agg['F'] += s['F']
        agg['n'] += s['n']; agg['viol'] += s['viol']; agg['stoneCov'] += s['stoneCov']
        agg['vill'].append(s['vill'])
        agg['wins'] += 1 if s['vicF'] and (not s['defF'] or s['vicF'] <= s['defF']) else 0
        agg['losses'] += 1 if (s['defF'] and (not s['vicF'] or s['defF'] < s['vicF'])) else 0
        agg['lowF'] += sum(1 for x in s['fd'] if x <= 30)
        agg['lowW'] += sum(1 for x in s['wd'] if x <= 15)
        agg['sawF'] += sawtooth(s['fd'], 300, 50)
        agg['sawW'] += sawtooth(s['wd'], 150, 30)
    return agg


def mean(v):
    return sum(v) / len(v) if v else 0.0


def extra(path):
    """补充指标：复合弓产出 / 农场建造令数 / 建造令总数 / 祭司死亡帧 / 胜负帧。"""
    cb = farm = build = 0
    vicF = defF = 0
    rea = ''
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
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
            if 'BUILD-ISSUE' in msg:
                build += 1
                if 'type=4' in msg:
                    farm += 1
            low = msg.lower()
            if 'victory' in low and vicF == 0:
                vicF = fr
            if 'defeat:' in low and defF == 0:
                defF = fr
                rea = msg.split('DEFEAT:')[-1].replace('!', '').strip()
    return cb, farm, build, vicF, defF, rea


def show(tag, files):
    a = summ(files)
    if a['n'] == 0:
        print(f"\n=== {tag}: 无数据")
        return a
    n = a['n']
    # 补充指标
    ex = dict(cb=0, farm=0, build=0, priest=0, tc=0, nd=0)
    for f in files:
        if not os.path.exists(f):
            continue
        cb, farm, build, vicF, defF, rea = extra(f)
        ex['nd'] += 1
        ex['cb'] += cb; ex['farm'] += farm; ex['build'] += build
        if 'Priest' in rea:
            ex['priest'] += 1
        if 'Town Center' in rea:
            ex['tc'] += 1
    a.update(ex)
    print(f"\n{'='*100}\n{tag}   有效局={a['ndone']}  采样={n}  村民总数均值={mean(a['vill']):.1f}")
    print(f"  胜/负 = {a['wins']} / {a['losses']}   失败构成：祭司被杀 {ex['priest']} / TC 被毁 {ex['tc']}")
    print(f"  {'指标':<26}{'值':>12}")
    print(f"  {'肉·均值':<26}{mean(a['fd']):>12.1f}")
    print(f"  {'肉·谷底率(≤30)':<24}{100.0*a['lowF']/n:>11.1f}%")
    print(f"  {'肉·锯齿次数(300→50)':<22}{a['sawF']:>12d}")
    print(f"  {'木·均值':<26}{mean(a['wd']):>12.1f}")
    print(f"  {'木·谷底率(≤15)':<24}{100.0*a['lowW']/n:>11.1f}%")
    print(f"  {'木·锯齿次数(150→30)':<22}{a['sawW']:>12d}")
    print(f"  {'金·均值':<26}{mean(a['gd']):>12.1f}")
    print(f"  {'采石工覆盖率(S>0)':<22}{100.0*a['stoneCov']/n:>11.1f}%")
    print(f"  {'伐木工均值(统计口径)':<22}{mean(a['W']):>12.1f}")
    print(f"  {'食物工均值(统计口径)':<22}{mean(a['F']):>12.1f}")
    print(f"  {'计数违规条数(须为0)':<21}{a['viol']:>12d}")
    print(f"  {'复合弓产出(累计)':<22}{ex['cb']:>12d}")
    print(f"  {'农场建造令(type=4)':<21}{ex['farm']:>12d}")
    print(f"  {'建造令总数':<26}{ex['build']:>12d}")
    return a


BEFORE = ['pu1.ait', 'pu2.ait', 'pu3.ait', 'pu4.ait', 'pu5.ait', 'pu6.ait', 'pu7.ait', 'pu8.ait']
MID = ['ez1.ait', 'ez2.ait', 'ez3.ait', 'ez4.ait', 'ez5.ait', 'ez6.ait', 'ez7.ait', 'ez8.ait']
AFTER = ['ey1.ait', 'ey2.ait', 'ey3.ait', 'ey4.ait', 'ey5.ait', 'ey6.ait', 'ey7.ait', 'ey8.ait']

if __name__ == '__main__':
    A = show('pu（基线·第一批）', BEFORE)
    B = show('ez（基线·复现批）', MID)
    C = show('ey（最小修复集）', AFTER)
    for tag, X, Y in (('pu → ez（同代码两批，看方差）', A, B),
                      ('ez → ey（基线 → 最小修复集）', B, C),
                      ('pu → ey', A, C)):
        if not X['n'] or not Y['n']:
            continue
        print(f"\n{'='*100}\n{tag}\n")
        rows = [
            ('肉·均值', mean(X['fd']), mean(Y['fd']), True, '{:.1f}'),
            ('肉·谷底率 %', 100.0*X['lowF']/X['n'], 100.0*Y['lowF']/Y['n'], False, '{:.1f}'),
            ('木·均值', mean(X['wd']), mean(Y['wd']), True, '{:.1f}'),
            ('木·谷底率 %', 100.0*X['lowW']/X['n'], 100.0*Y['lowW']/Y['n'], False, '{:.1f}'),
            ('木·锯齿次数', X['sawW'], Y['sawW'], False, '{:.0f}'),
            ('金·均值', mean(X['gd']), mean(Y['gd']), True, '{:.1f}'),
            ('采石覆盖率 %', 100.0*X['stoneCov']/X['n'], 100.0*Y['stoneCov']/Y['n'], True, '{:.1f}'),
            ('复合弓产出', X['cb'], Y['cb'], True, '{:.0f}'),
            ('农场建造令', X['farm'], Y['farm'], True, '{:.0f}'),
            ('建造令总数', X['build'], Y['build'], True, '{:.0f}'),
        ]
        print(f"  {'指标':<20}{'前者':>10}{'后者':>10}{'变化':>12}")
        for name, a, b, up, fmt in rows:
            d = b - a
            mark = '↑' if d > 0 else ('↓' if d < 0 else '=')
            good = (d > 0) if up else (d < 0)
            tag2 = ' 好' if good else (' 差' if d != 0 else '')
            print(f"  {name:<20}{fmt.format(a):>10}{fmt.format(b):>10}{(mark + fmt.format(abs(d))):>12}{tag2}")
        print(f"  {'胜/负':<20}{str(X['wins'])+'/'+str(X['losses']):>10}{str(Y['wins'])+'/'+str(Y['losses']):>10}"
              f"{'  祭司死 ' + str(X['priest']) + '→' + str(Y['priest']):>16}")
