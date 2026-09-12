# -*- coding: utf-8 -*-
"""农民上限 20 对照：Fisher 精确检验 + 军队峰值分布 + U 局细查 + exit 码关联。"""
import glob, re, sys, math

BEAT = re.compile(r'\[BEAT f=(\d+) b=(\d+)\].*?Frm=(\d+).*?Mil=(\d+)')
FR = re.compile(r'^\d\d:\d\d:\d\d+\s*\|\s*(\d+)\s*\|')


def outcome(s):
    if '被祭司转换,归属阵营1->0' in s: return 'W'
    if 'DEFEAT: Priest killed' in s: return 'P'
    if 'DEFEAT: Town Center destroyed' in s: return 'T'
    if '敌方 摧毁主营' in s: return 'T'
    return 'U'


def fisher_two_tail(a, b, c, d):
    """[[a,b],[c,d]] 双尾 Fisher"""
    from math import comb
    n = a + b + c + d
    r1, c1 = a + b, a + c
    def p(k):
        return comb(c1, k) * comb(n - c1, r1 - k) / comb(n, r1)
    obs = p(a)
    tot = 0.0
    for k in range(max(0, r1 - (n - c1)), min(r1, c1) + 1):
        pk = p(k)
        if pk <= obs * (1 + 1e-12):
            tot += pk
    return min(1.0, tot)


def load(tag):
    res = []
    for fn in sorted(glob.glob('%s_*_r0_*.ait' % tag)):
        s = open(fn, encoding='utf-8', errors='replace').read()
        fr = [int(m.group(1)) for m in (FR.match(l) for l in s.splitlines()) if m]
        mx = max(fr) if fr else 0
        r = outcome(s)
        trunc = (r == 'U' and mx < 44000)
        seq = sorted((int(m.group(1)), int(m.group(3)), int(m.group(4))) for m in BEAT.finditer(s))
        res.append(dict(fn=fn, r=r, mx=mx, trunc=trunc,
                        mxFrm=max((v[1] for v in seq), default=0),
                        mxMil=max((v[2] for v in seq), default=0),
                        endf=mx))
    return res


A = load('sc1')      # 基线 48 局
B = load('f20')      # 农民上限 20

def valid(rs): return [x for x in rs if not x['trunc']]

va, vb = valid(A), valid(B)
Wa = sum(1 for x in va if x['r'] == 'W'); na = len(va)
Wb = sum(1 for x in vb if x['r'] == 'W'); nb = len(vb)
p = fisher_two_tail(Wb, nb - Wb, Wa, na - Wa)
print('=' * 90)
print('Fisher 精确检验（农民20 vs 基线22，map.njust rot0）')
print('  基线(22): W=%d/%d = %.1f%%' % (Wa, na, 100 * Wa / na))
print('  农民20  : W=%d/%d = %.1f%%' % (Wb, nb, 100 * Wb / nb))
print('  双尾 p = %.4f  (Δ = %+.1f pp)' % (p, 100 * (Wb / nb - Wa / na)))
print('  ⚠ n=%d 时 95%%CI 半宽 ≈ ±%.0f pp ⇒ 本对比不可判读胜负，只看机制量'
      % (nb, 100 * 1.96 * math.sqrt(0.25 / nb)))

print()
print('结局构成：')
for label, rs in (('基线22', va), ('农民20', vb)):
    c = {k: sum(1 for x in rs if x['r'] == k) for k in 'WPTU'}
    print('  %-8s W=%-3d P=%-3d T=%-3d U=%-3d' % (label, c['W'], c['P'], c['T'], c['U']))

print()
print('军队峰值（Mil_max）分布：')
for label, rs in (('基线22', va), ('农民20', vb)):
    vals = sorted(x['mxMil'] for x in rs)
    import collections
    cc = collections.Counter(vals)
    print('  %-8s 中位=%.0f  各值: %s' % (label, vals[len(vals) // 2],
          ', '.join('%d×%d' % (k, cc[k]) for k in sorted(cc))))
    for t in (27, 29):
        print('       峰值 >= %d : %d/%d (%.0f%%)' % (t, sum(1 for v in vals if v >= t),
              len(vals), 100 * sum(1 for v in vals if v >= t) / len(vals)))

print()
print('农民峰值（Frm_max）分布：')
for label, rs in (('基线22', va), ('农民20', vb)):
    vals = sorted(x['mxFrm'] for x in rs)
    import collections
    cc = collections.Counter(vals)
    print('  %-8s 中位=%.0f  各值: %s' % (label, vals[len(vals) // 2],
          ', '.join('%d×%d' % (k, cc[k]) for k in sorted(cc))))

print()
print('U 局细查（超时/截断）：')
for label, rs in (('基线22', va), ('农民20', vb)):
    us = [x for x in rs if x['r'] == 'U']
    print('  %-8s U=%d 局，末帧: %s' % (label, len(us),
          ', '.join('%.1f分' % (x['endf'] / 1500) for x in sorted(us, key=lambda y: y['endf']))))

print()
print('农民20 逐局：')
for x in vb:
    print('  %-22s %s 末帧=%.1f分 农民峰=%-3d 军队峰=%-3d' %
          (x['fn'].split('\\')[-1], x['r'], x['endf'] / 1500, x['mxFrm'], x['mxMil']))
