# -*- coding: utf-8 -*-
"""c1 批（2026-09-26 行军抱团闸 cohesion）—— 验证「反攻时士兵走在一起」。

三件事：
  ① 闸是否生效：[COH-PULL] 条数必须 ≠ 0（否则判据没命中，等于没改）
  ② 队伍到底多散：[COH] 每 300 帧打印的【施加闸之前】原始分散度（最大/平均距质心）
  ③ 胜率是否受影响：与 o1 批（改前，45.8%）做 Fisher 检验
"""
import io, json, os, re, glob, statistics
from math import comb

TAGS = ['c1%02d' % i for i in range(1, 25)]


def fisher(a, b, c, d):
    n = a + b + c + d
    lo = max(0, a + b - (b + d)); hi = min(a + b, a + c)
    def p(x): return comb(a + c, x) * comb(b + d, a + b - x) / comb(n, a + b)
    obs = p(a)
    return sum(p(x) for x in range(lo, hi + 1) if p(x) <= obs + 1e-12)


def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0)
    ph = k / n; d = 1 + z*z/n
    c = (ph + z*z/(2*n)) / d
    h = z * ((ph*(1-ph) + z*z/(4*n)) / n) ** 0.5 / d
    return (max(0.0, c-h), min(1.0, c+h))


def judge(tag):
    jf, af = tag + '.jsonl', tag + '.ait'
    if not (os.path.exists(jf) and os.path.exists(af)):
        return None
    win, last = False, 0
    for line in io.open(jf, encoding='utf-8', errors='ignore'):
        line = line.strip()
        if not line: continue
        try: o = json.loads(line)
        except Exception: continue
        last = max(last, o.get('frame', 0))
        if o.get('win') is True: win = True          # ★ 任一行 win:true 即胜
    txt = io.open(af, encoding='utf-8', errors='ignore').read()
    lose = 'DEFEAT:' in txt
    if win: return 'W', last
    if lose: return 'L', last
    return 'U', last


def coh_stats(tag):
    """返回 (pull条数, [最大距质心列表], [平均距质心列表], 最后一条 COH 里的拉回累计/机会累计)"""
    f = tag + '.ait'
    if not os.path.exists(f): return None
    pulls, mx, mean, pc, cc = 0, [], [], 0, 0
    for ln in io.open(f, encoding='utf-8', errors='ignore'):
        if '[COH-PULL' in ln: pulls += 1
        elif '[COH f=' in ln:
            m = re.search(r'最大距质心=([\d.]+) 平均距质心=([\d.]+)', ln)
            if m: mx.append(float(m.group(1))); mean.append(float(m.group(2)))
            m2 = re.search(r'拉回累计=(\d+) 机会累计=(\d+)', ln)
            if m2: pc, cc = int(m2.group(1)), int(m2.group(2))
    return pulls, mx, mean, pc, cc


def main():
    res = {}
    for t in TAGS:
        r = judge(t)
        if r: res[t] = r
    n = len(res)
    w = sum(1 for v in res.values() if v[0] == 'W')
    l = sum(1 for v in res.values() if v[0] == 'L')
    u = sum(1 for v in res.values() if v[0] == 'U')
    print('=' * 68)
    print('c1 批（行军抱团闸）n=%d' % n)
    assert w + l + u == n, '恒等式不成立！'
    lo, hi = wilson(w, n)
    print('  胜 %d (%.1f%%) CI %.1f~%.1f ｜ 负 %d (%.1f%%) ｜ 未决 %d (%.1f%%)'
          % (w, w/n*100, lo*100, hi*100, l, l/n*100, u, u/n*100))

    print('\n=== 抱团闸生效情况 ===')
    tot_pull, allmx, allmean = 0, [], []
    for t in TAGS:
        s = coh_stats(t)
        if not s: continue
        pulls, mx, mean, pc, cc = s
        tot_pull += pulls
        allmx += mx; allmean += mean
        print('  %s: 拉回日志=%2d  COH采样帧=%2d  最大距质心中位=%s  末次累计拉回=%d/机会%d'
              % (t, pulls, len(mx), ('%.1f' % statistics.median(mx)) if mx else '-', pc, cc))
    print('\n  合计拉回 %d 次' % tot_pull)
    if allmx:
        print('  【施加闸之前】原始分散度：最大距质心 中位=%.1f P90=%.1f 最大=%.1f ｜ 平均距质心 中位=%.1f'
              % (statistics.median(allmx), sorted(allmx)[int(len(allmx)*0.9)],
                 max(allmx), statistics.median(allmean)))
    else:
        print('  ⚠ 无 [COH] 采样 —— 闸没跑到')

    print('\n=== 与对照臂 Fisher 检验（胜率）===')
    arms = {'o1 批(改前 45.8%)': (11, 24), '旧码系 gsk+kb+kb2': (16, 36),
            '新码全侧(21.5%)': (17, 79), 'p 批(12.5%)': (3, 24)}
    for name, (k2, n2) in arms.items():
        print('  c1 %d/%d vs %-20s %d/%d  p=%.4f' % (w, n, name, k2, n2, fisher(w, n-w, k2, n2-k2)))
    print('\n=== 败率 / 未决率 ===')
    print('  c1 负 %d vs o1 负 10   p=%.4f' % (l, fisher(l, n-l, 10, 14)))
    print('  c1 未决 %d vs o1 未决 3  p=%.4f' % (u, fisher(u, n-u, 3, 21)))


if __name__ == '__main__':
    main()
