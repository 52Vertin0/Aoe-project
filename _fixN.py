# -*- coding: utf-8 -*-
"""_fixN.py —— fixN（反攻前腾人口：人口满时让农民自杀给军队让位）验证

主判据（**机制量**，胜率只作次级端点）：
  ① [POP-SAC] 触发：有触发的局数 / 总次数 / 每次的农民 SN·人口·军队
  ② 农民数 Frm 是否真降到 POP_SAC_FARMER_FLOOR(16)   —— 基线 fixM 恒 22
  ③ ★ Mil 是否突破 27 —— 27 = 50(人口硬顶) − 22(农民) − 1(祭司) 的算术锁
  ④ nMy 是否仍 ≤ 50（人口没被"超卖"）

护栏：
  ⑤ 崩盘率(mil_max<16) / 胜率 / 祭司死 / 超时 / 反攻起点帧

用法：python _fixN.py [tagA] [tagB] ...
"""
import re, glob, os, statistics as st, sys

def load(tag):
    per = []
    for fn in sorted(glob.glob(f'{tag}_*_r0_*.ait')):
        t = open(fn, encoding='utf-8', errors='replace').read()
        if t.count('[BEAT') < 5: continue
        base = os.path.basename(fn).replace(tag + '_', '').replace('.ait', '')
        mp = base.split('_r0_')[0]
        m = re.search(r'Counterattack! Frame=(\d+)', t)
        sac = []
        for L in t.splitlines():
            mm = re.search(r'\[POP-SAC f=(\d+)\] 农民 SN=(\d+) 自杀腾位 \| 农民 (\d+)→(\d+)'
                           r' pop=(\d+)/(\d+) 军队=(\d+) 累计=(\d+)', L)
            if mm:
                sac.append(tuple(int(mm.group(i)) for i in range(1, 9)))
        rows = []
        for L in t.splitlines():
            if '[BEAT' not in L: continue
            try:
                f   = int(re.search(r'f=(\d+)',   L).group(1))
                Frm = int(re.search(r'Frm=(\d+)', L).group(1))
                Mil = int(re.search(r'Mil=(\d+)', L).group(1))
                nMy = int(re.search(r'nMy=(\d+)', L).group(1))
            except Exception:
                continue
            rows.append((f, Frm, Mil, nMy))
        per.append(dict(mp=mp, fn=base, win=('被祭司转换,归属阵营1->0' in t),
                        pdeath=('DEFEAT: Priest killed' in t),
                        tclost=('DEFEAT: Town Center destroyed' in t),
                        ca=(int(m.group(1)) if m else -1), sac=sac, rows=rows))
    return per


def report(tag, show_sac=6):
    per = load(tag)
    n = len(per)
    if not n:
        print(f'{tag:<8}: 无有效局'); return None
    W = sum(1 for p in per if p['win'])
    nSacG = sum(1 for p in per if p['sac'])
    nSac  = sum(len(p['sac']) for p in per)
    frmMin = [min((r[1] for r in p['rows']), default=-1) for p in per]
    milMax = [max((r[2] for r in p['rows']), default=-1) for p in per]
    nMyMax = [max((r[3] for r in p['rows']), default=-1) for p in per]
    milMaxPreCA = []
    frmMinPreCA = []
    for p in per:
        cap = p['ca'] if p['ca'] > 0 else 33000
        v = [r[2] for r in p['rows'] if r[0] < cap]
        milMaxPreCA.append(max(v) if v else -1)
        # ⚠ 口径修正(10-06)：农民数必须限定在【农民已铺满之后】的窗口再取最小值。
        #   开局 Frm 恒为 8（初始村民数），若把开局帧也算进来，min 会恒等于 8 ⇒ 假信号。
        #   取 f>=27000（反攻前白等期，农民早已打满 22）到反攻起点之间。
        w = [r[1] for r in p['rows'] if 27000 <= r[0] < cap]
        frmMinPreCA.append(min(w) if w else -1)
    crash = sum(1 for x in [max((r[2] for r in p['rows']), default=0) for p in per] if x < 16)
    # 只在"有自杀"的局里看 Mil 突破（无自杀的局本就不该变）
    sacG = [p for p in per if p['sac']]
    milMaxSac = [max((r[2] for r in p['rows']), default=-1) for p in sacG]
    milMaxNoSac = [max((r[2] for r in p['rows']), default=-1) for p in per if not p['sac']]

    print(f'{"="*78}')
    print(f'{tag}: n={n}  胜={W}({100*W/n:.1f}%)  祭死={sum(1 for p in per if p["pdeath"])}'
          f'  TC毁={sum(1 for p in per if p["tclost"])}')
    print(f'  【① 触发】有自杀的局 = {nSacG}/{n}   自杀总次数 = {nSac}')
    print(f'  【② 农民】Frm 全局最小 : 中位 {st.median(frmMin):.0f}  区间 {min(frmMin)}~{max(frmMin)}'
          f'   ≤16 的局 = {sum(1 for x in frmMin if 0 <= x <= 16)}')
    print(f'         ★反攻前 Frm 最小 : 中位 {st.median(frmMinPreCA):.0f}  区间 {min(frmMinPreCA)}~{max(frmMinPreCA)}'
          f'   ≤16 的局 = {sum(1 for x in frmMinPreCA if 0 <= x <= 16)}   ← 反攻前农民不会战死 ⇒ 降必为自杀')
    print(f'  【③ 军队】Mil 全局最大 : 中位 {st.median(milMax):.0f}  区间 {min(milMax)}~{max(milMax)}'
          f'   >27 的局 = {sum(1 for x in milMax if x > 27)}')
    print(f'         反攻前 Mil 最大 : 中位 {st.median(milMaxPreCA):.0f}  区间 {min(milMaxPreCA)}~{max(milMaxPreCA)}')
    if sacG:
        print(f'         有自杀局 Mil 最大 : 中位 {st.median(milMaxSac):.0f}  区间 {min(milMaxSac)}~{max(milMaxSac)}')
    if milMaxNoSac:
        print(f'         无自杀局 Mil 最大 : 中位 {st.median(milMaxNoSac):.0f}  区间 {min(milMaxNoSac)}~{max(milMaxNoSac)}')
    print(f'  【④ 人口】nMy 全局最大 : 中位 {st.median(nMyMax):.0f}  区间 {min(nMyMax)}~{max(nMyMax)}'
          f'   >50 的局 = {sum(1 for x in nMyMax if x > 50)}')
    print(f'  【⑤ 护栏】崩盘(mil_max<16) = {crash}/{n}')
    if show_sac:
        print(f'  ---- 自杀事件样本（最多 {show_sac} 条）----')
        cnt = 0
        for p in per:
            for s in p['sac']:
                print(f'     {p["mp"]:<5} {p["fn"]:<22} f={s[0]:<6} SN={s[1]:<6} '
                      f'农民 {s[2]}→{s[3]}  pop={s[4]}/{s[5]}  军队={s[6]}  第{s[7]}次')
                cnt += 1
                if cnt >= show_sac: break
            if cnt >= show_sac: break
    # 每局农民/军队轨迹（有自杀的局，前 3 局）
    if sacG:
        print(f'  ---- 轨迹（有自杀局，最多 3 局）----')
        for p in sacG[:3]:
            tr = [(r[0], r[1], r[2]) for r in p['rows'] if r[0] >= 26000]
            step = max(1, len(tr)//12)
            print(f'     {p["fn"]:<24} win={int(p["win"])} ca={p["ca"]}')
            print('       f/Frm/Mil: ' + '  '.join(f'{a//1000}k:{b}/{c}' for a, b, c in tr[::step][:12]))
    return per


if __name__ == '__main__':
    tags = sys.argv[1:] or ['fixM', 'fixN']
    for t in tags:
        report(t)
