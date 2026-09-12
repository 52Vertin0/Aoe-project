# -*- coding: utf-8 -*-
"""code_metrics 对比：pre_shrink（精简前） vs shrink（精简后）。
输出：函数级行数/注释占比 变化表 + 全文件汇总。"""
import re, collections

FUNC_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_:<>,&\*\s]*\s+UsrAI::(\w+)\s*\(')


def scan(path):
    L = open(path, encoding='utf-8').read().split('\n')
    N = len(L)
    defs = [(i, m.group(1)) for i, ln in enumerate(L) for m in [FUNC_RE.match(ln)] if m]
    funcs = []
    for k, (i, name) in enumerate(defs):
        end = defs[k + 1][0] - 1 if k + 1 < len(defs) else N - 1
        last = end
        while last > i and not L[last].strip():
            last -= 1
        cmt = sum(1 for s in L[i:last + 1] if s.strip().startswith('//'))
        funcs.append(dict(name=name, span=end - i + 1, body=last - i + 1, cmt=cmt))
    blank = code = cmt = 0
    for s in L:
        t = s.strip()
        if not t:
            blank += 1
        elif t.startswith('//'):
            cmt += 1
        else:
            code += 1
    return funcs, dict(N=N, blank=blank, code=code, cmt=cmt)


A, sa = scan('bak_20260915_pre_shrink_UsrAI.cpp')
B, sb = scan('bak_20260915_shrink_UsrAI.cpp')

print('=' * 96)
print('UsrAI.cpp 结构对比：pre_shrink（精简前） vs shrink（精简后）')
print('=' * 96)
print('%-12s %10s %10s %10s %10s' % ('', '精简前', '精简后', '变化', '降幅'))
print('%-12s %10d %10d %+10d %9.1f%%' % ('总行数', sa['N'], sb['N'], sb['N'] - sa['N'],
                                        100.0 * (sa['N'] - sb['N']) / sa['N']))
print('%-12s %10d %10d %+10d %9.1f%%' % ('注释行', sa['cmt'], sb['cmt'], sb['cmt'] - sa['cmt'],
                                        100.0 * (sa['cmt'] - sb['cmt']) / max(1, sa['cmt'])))
print('%-12s %10d %10d %+10d %9.1f%%' % ('代码行', sa['code'], sb['code'], sb['code'] - sa['code'],
                                        100.0 * (sa['code'] - sb['code']) / max(1, sa['code'])))
print('%-12s %10d %10d %+10d' % ('空行', sa['blank'], sb['blank'], sb['blank'] - sa['blank']))

ma = dict((f['name'], f) for f in A)
mb = dict((f['name'], f) for f in B)
print('\n【按精简幅度排序（前 20）】')
print('%-28s %8s %8s %8s %8s %9s' % ('函数', '前体量', '后体量', '净减', '前注释', '注释降幅'))
rows = []
for n in ma:
    if n in mb:
        d = ma[n]['body'] - mb[n]['body']
        cd = (ma[n]['cmt'] - mb[n]['cmt']) / max(1, ma[n]['cmt']) * 100.0
        rows.append((d, n, ma[n], mb[n], cd))
rows.sort(reverse=True)
for d, n, a, b, cd in rows[:20]:
    if d == 0 and cd == 0:
        continue
    print('%-28s %8d %8d %+8d %8d %8.1f%%' % (n, a['body'], b['body'], -d, a['cmt'], cd))

print('\n【四个目标函数】')
for n in ('manageBuildings', 'managePriest', 'manageMilitary', 'manageCounterAttack'):
    if n in ma and n in mb:
        a, b = ma[n], mb[n]
        print('%-24s 体量 %4d → %4d (%+d, %.1f%%)   注释 %4d → %4d (%.1f%%)   注释占比 %.0f%% → %.0f%%'
              % (n, a['body'], b['body'], b['body'] - a['body'],
                 100.0 * (b['body'] - a['body']) / a['body'],
                 a['cmt'], b['cmt'], 100.0 * (b['cmt'] - a['cmt']) / max(1, a['cmt']),
                 100.0 * a['cmt'] / a['body'], 100.0 * b['cmt'] / b['body']))
print('=' * 96)
