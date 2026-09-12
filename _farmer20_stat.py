# -*- coding: utf-8 -*-
"""农民上限 20 对照统计：结局分布 + 机制量（Frm/Mil 峰值、首达阈值帧）。
用法: python _farmer20_stat.py sc1 farmer20 [farmer20b ...]
口径: 伪U(截断, maxf<44000) 剔除；胜率用 Wilson CI。
机制量取自 [BEAT] 行（注意行前缀带 'UsrAI打印：'，勿用 startswith）。
"""
import glob, re, math, sys

FR = re.compile(r'^\d\d:\d\d:\d\d+\s*\|\s*(\d+)\s*\|')
BEAT = re.compile(r'\[BEAT f=(\d+) b=(\d+)\].*?Frm=(\d+).*?Mil=(\d+)')


def outcome(s):
    if '被祭司转换,归属阵营1->0' in s: return 'W'
    if 'DEFEAT: Priest killed' in s: return 'P'
    if 'DEFEAT: Town Center destroyed' in s: return 'T'
    if '敌方 摧毁主营' in s: return 'T'
    return 'U'


def wilson(k, n):
    if n == 0: return (0.0, 0.0, 0.0)
    p = k / n; z = 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, c - h, c + h)


def median(xs):
    if not xs: return 0.0
    xs = sorted(xs); m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def first_ge(seq, thr):
    """seq = [(frame, v)] 升序；返回首个 v>=thr 的 frame，无则 -1"""
    for f, v in seq:
        if v >= thr: return f
    return -1


for tag in sys.argv[1:]:
    files = sorted(glob.glob('%s_*_r0_*.ait' % tag))
    W = P = T = U = trunc = 0
    peaks = []           # (maxFrm, maxMil, f12, f25, fMil>4)
    for fn in files:
        s = open(fn, encoding='utf-8', errors='replace').read()
        fr = [int(m.group(1)) for m in (FR.match(l) for l in s.splitlines()) if m]
        mx = max(fr) if fr else 0
        r = outcome(s)
        if r == 'U' and mx < 44000:
            trunc += 1
            continue
        if r == 'W': W += 1
        elif r == 'P': P += 1
        elif r == 'T': T += 1
        else: U += 1
        seq = []
        for m in BEAT.finditer(s):
            seq.append((int(m.group(1)), int(m.group(3)), int(m.group(4))))
        seq.sort()
        if seq:
            mxFrm = max(v[1] for v in seq)
            mxMil = max(v[2] for v in seq)
            peaks.append((mxFrm, mxMil,
                          first_ge([(f, v) for f, _, v in seq], 12),
                          first_ge([(f, v) for f, _, v in seq], 25),
                          first_ge([(f, v) for f, _, v in seq], 5)))
        else:
            peaks.append((0, 0, -1, -1, -1))

    n = W + P + T + U
    p, lo, hi = wilson(W, n)
    print('=' * 96)
    print('[%s] n=%d (截断剔除 %d)' % (tag, n, trunc))
    print('  结局: W=%-3d P=%-3d T=%-3d U=%-3d   胜率 %.1f%%  95%%CI %.1f~%.1f%%'
          % (W, P, T, U, p * 100, lo * 100, hi * 100))
    print('  农民峰值 中位 %.1f (min %d / max %d)'
          % (median([x[0] for x in peaks]), min([x[0] for x in peaks] or [0]),
             max([x[0] for x in peaks] or [0])))
    print('  军队峰值 中位 %.1f (min %d / max %d)'
          % (median([x[1] for x in peaks]), min([x[1] for x in peaks] or [0]),
             max([x[1] for x in peaks] or [0])))

    def stat(idx, label, fmt='%.0f'):
        vals = [x[idx] for x in peaks if x[idx] >= 0]
        f = 'n=%d 中位=%s 中位分钟=%.1f' % (len(vals), fmt % median(vals),
                                            median(vals) / 1500) if vals else 'n=0'
        print('  %-16s %s' % (label, f))

    stat(2, 'Mil 首>=12')
    stat(3, 'Mil 首>=25')
    stat(4, 'Mil 首>4')
    # 农民是否真的到 20/22
    mx = [x[0] for x in peaks]
    for t in (18, 20, 22):
        print('  农民峰值 >= %-3d : %d/%d 局 (%.0f%%)'
              % (t, sum(1 for v in mx if v >= t), len(mx),
                 100 * sum(1 for v in mx if v >= t) / max(1, len(mx))))
