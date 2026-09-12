# -*- coding: utf-8 -*-
"""_holdlock.py —— 量化「SIEGE-HOLD 残血死锁」签名（用 [BEAT] 按桶采样，免疫 frame 跳号）。

签名（充分判据，从 [BEAT] 可读）：
    祭司【已到感化射程内】(dS <= 12 格) 且【血 < PRIEST_SIEGE_GUARD_HP(0.45)】且【本桶无任何移动令】(pm 全 0)
  ⇒ 该桶祭司被 [SIEGE-HOLD]（:5166 `pHp0 < GUARD_HP && nearT0 <= 14*BL`）拦下 ⇒ 干坐。
  闸的语义是"撤出塔射程后再来"，但 ① 祭司无自愈 ⇒ hp 判据永不翻转；② 谁都不移动它 ⇒ 永不脱离。
  ⇒ 一旦持续 = 本局必超时（唯一胜利条件做不到）。

⚠ 口径说明：
  - pr@= 与 dS 同源：dS = dist(pr@, (WSx+1, WSy+1))；WS 取 _maprev.py 的四图块坐标。
  - 用【桶】而不是 frame%N==0：AI 的 frame 会跳号 ⇒ 取模判据会静默失效（见 UsrAI.cpp:972-977）。
  - hp_max 取 pr=(sn.. hp../MAX ..) 的 MAX（本 mod =100）。

用法: python _holdlock.py base0 fix1 fix2 fix3 fix4 fix5
"""
import re, sys, glob, os, collections

BL = 35.777
MAP_WS = {'map': (11, 86), 'map1': (93, 11), 'map2': (24, 6), 'map3': (82, 20)}
GUARD_HP = 0.45
RANGE_BL = 12.0
RUN_MIN = 4          # >=4 桶 = 600 帧 = 24 秒


def which_map(bn):
    for k in ('map1', 'map2', 'map3'):
        if ('_' + k + '_') in bn:
            return k
    return 'map'


def outcome(t):
    win = bool(re.search(r'攻城武器厂\(编号:\d+\)被祭司转换', t)) or ('VICTORY! Siege Workshop converted' in t)
    pd = 'DEFEAT: Priest killed' in t
    tcl = bool(re.search(r'市镇中心\(编号:\d+\)被摧毁', t))
    fs = [int(x) for x in re.findall(r'\|\s*(\d+)\s*\|\s*(?:red|green|blue|black)', t)]
    endf = max(fs) if fs else 0
    if win: return '胜', endf
    if pd: return '祭死', endf
    if tcl: return 'TC毁', endf
    return '超时', endf


def buckets(t, mp):
    wsx, wsy = MAP_WS[mp]
    tx, ty = wsx + 1.0, wsy + 1.0
    out = []
    for L in t.splitlines():
        if '[BEAT' not in L:
            continue
        mb = re.search(r'\bb=(\d+)\]', L)
        mp_ = re.search(r'pr@=\(([-0-9.]+),([-0-9.]+)\)', L)
        mh = re.search(r'pr=\(sn(-?\d+) st(-?\d+) hp(-?\d+)/(\d+) ccd(-?\d+)\)', L)
        if not (mb and mp_ and mh):
            continue
        b = int(mb.group(1))
        px, py = float(mp_.group(1)), float(mp_.group(2))
        hp = int(mh.group(3)); mx = int(mh.group(4))
        if hp < 0 or mx <= 0:
            continue
        st = int(mh.group(2))
        ccd = int(mh.group(5))
        dS = ((px - tx) ** 2 + (py - ty) ** 2) ** 0.5
        pmm = re.search(r'pm f(\d+) ca(\d+) h(\d+) cnt(\d+) o(\d+)', L)
        # ⚠ pm 字段是较新版本才有的（base0 没有）⇒ 缺失记 None，该局整局不可判（不与其它臂混比）
        moves = sum(int(g) for g in pmm.groups()) if pmm else None
        out.append((b, dS, hp / mx, moves, st, ccd))
    return out


def main(tags):
    rows = []
    for tag in tags:
        for f in sorted(glob.glob('%s_*_r0_*.ait' % tag)):
            t = open(f, encoding='utf-8', errors='replace').read()
            mp = which_map(os.path.basename(f))
            res, endf = outcome(t)
            bk = buckets(t, mp)
            # 锁桶（死锁充分判据）：
            #   到射程内 dS<=12  +  残血 hp<0.45（SIEGE-HOLD 判据）  +  本桶零移动令  +  st==IDLE  +  非施法冷却
            #   ⚠ st==IDLE 必须判：正在施法(WORKING=2) 时同样"零移动令"⇒ 只靠 moves==0 会把"正在转化"误判成"被拦"。
            #   ⚠ ccd==0 必须判：转化后 lockout 期内也是零移动令。
            known = all(x[3] is not None for x in bk) if bk else False
            flags = [(b, (dS <= RANGE_BL and hp < GUARD_HP and mv == 0 and st == 0 and ccd == 0))
                     for b, dS, hp, mv, st, ccd in bk]
            best = cur = 0; first_b = -1; cur_b = -1
            for b, f_ in flags:
                if f_:
                    if cur == 0: cur_b = b
                    cur += 1
                    if cur > best: best = cur; first_b = cur_b
                else:
                    cur = 0
            rows.append(dict(tag=tag, f=os.path.basename(f), map=mp, res=res, endf=endf,
                             nb=len(bk), best=best, first_b=first_b, known=known))
    print('=== ① 逐局：连续"锁桶"最长段 ===')
    print('%-30s %-5s %-4s %-7s %6s %8s %s' % ('file', 'map', '结局', 'endf', '桶数', '最长锁桶', '起始桶'))
    for r in sorted(rows, key=lambda r: -r['best']):
        if r['best'] >= 1:
            print('%-30s %-5s %-4s %-7d %6d %8d %8d' % (r['f'], r['map'], r['res'], r['endf'], r['nb'], r['best'], r['first_b']))
    unk = [r for r in rows if not r['known']]
    if unk:
        print('  ⚠ 无 pm 字段（不可判，已剔除）：%d 局 %s' % (len(unk), sorted(set(r['tag'] for r in unk))))

    print()
    print('=== ② 按 tag 汇总（仅可判局）===')
    print('%-8s %4s %8s %8s %8s | %s' % ('tag', 'n', '锁>=1', '锁>=%d' % RUN_MIN, '锁>=8', '结局分布(胜/祭死/超时/TC毁)'))
    for tag in tags:
        rs = [r for r in rows if r['tag'] == tag and r['known']]
        if not rs:
            print('%-8s  —  不可判（无 pm 字段）' % tag)
            continue
        n = len(rs)
        c1 = sum(1 for r in rs if r['best'] >= 1)
        cm = sum(1 for r in rs if r['best'] >= RUN_MIN)
        c8 = sum(1 for r in rs if r['best'] >= 8)
        co = collections.Counter(r['res'] for r in rs)
        print('%-8s %4d %8d %8d %8d | 胜%d 祭死%d 超时%d TC毁%d' % (
            tag, n, c1, cm, c8, co.get('胜', 0), co.get('祭死', 0), co.get('超时', 0), co.get('TC毁', 0)))

    print()
    print('=== ③ 死锁(=连续锁桶>=%d) × 结局  [仅可判局合并] ===' % RUN_MIN)
    ok = [r for r in rows if r['known']]
    for lo, hi, lab in ((0, 1, '无锁'), (1, RUN_MIN, '1~%d 桶(短暂)' % (RUN_MIN - 1)), (RUN_MIN, 10 ** 9, '>=%d 桶(死锁)' % RUN_MIN)):
        rs = [r for r in ok if lo <= r['best'] < hi]
        if not rs:
            continue
        co = collections.Counter(r['res'] for r in rs)
        print('  %-16s n=%-4d 胜%-3d 祭死%-3d 超时%-3d TC毁%-3d | 超时率 %.0f%%' % (
            lab, len(rs), co.get('胜', 0), co.get('祭死', 0), co.get('超时', 0), co.get('TC毁', 0),
            100.0 * co.get('超时', 0) / len(rs)))
    return rows


if __name__ == '__main__':
    main(sys.argv[1:] or ['base0', 'fix1'])
