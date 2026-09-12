import glob, os, re, sys, math

PREFIXES = ['g1', 'n2', 'n4', 'n5', 'n6']


def collect(prefix):
    out = []
    for f in glob.glob(prefix + '*.ait'):
        base = os.path.basename(f)[:-4]
        rest = base[len(prefix):]
        if len(rest) == 2 and rest.isdigit():
            out.append(f)
    return sorted(out)


def fisher(a, b, c, d):
    # 2x2 [[a,b],[c,d]] two-sided
    n = a + b + c + d
    def p(x):
        return math.comb(a + c, x) * math.comb(b + d, a + b - x) / math.comb(n, a + b)
    p0 = p(a)
    tot = 0.0
    lo = max(0, a + b - (b + d))
    hi = min(a + b, a + c)
    for x in range(lo, hi + 1):
        px = p(x)
        if px <= p0 * (1 + 1e-9):
            tot += px
    return min(1.0, tot)


print("=== 逐局明细 ===")
acc = {}
for p in PREFIXES:
    fs = collect(p)
    if not fs:
        continue
    print("\n-- %s (%d 局) --" % (p, len(fs)))
    print("%-6s %-5s %-7s %5s %5s %6s %6s %6s" % ("tag", "verdict", "lastfrm", "BH", "MilM", "ADV", "Priest", "wav"))
    W = L = 0
    for f in fs:
        tag = os.path.basename(f)[:-4]
        j = f[:-4] + '.jsonl'
        txt = open(f, encoding='utf-8', errors='ignore').read()
        jt = open(j, encoding='utf-8', errors='ignore').read() if os.path.exists(j) else ''
        if '"win":true' in jt:
            v = 'WIN'; W += 1
        elif 'DEFEAT:' in txt:
            v = 'LOSS'; L += 1
        else:
            v = 'UND'
        lf = re.findall(r'time\|(\d+)\|', txt)
        lf = lf[-1] if lf else '?'
        bh = txt.count('BUILDER-HARD')
        ms = [int(x) for x in re.findall(r'Mil:(\d+)', txt)]
        mm = max(ms) if ms else 0
        adv = txt.count('ADV_SIEGE')
        pk = 'Y' if 'Priest killed' in txt else '-'
        wav = 'Y' if 'ALL WAVES DEFEATED' in txt else '-'
        print("%-6s %-7s %6s %5d %5d %6d %6s %6s" % (tag, v, lf, bh, mm, adv, pk, wav))
    acc[p] = (W, len(fs))

print("\n=== 显著性（Fisher 精确检验，双侧）===")
f6 = collect('n6')
w6 = acc['n6'][0]; n6 = acc['n6'][1]
for p in ['n5', 'n4', 'n2']:
    if p in acc:
        w, n = acc[p]
        t = [[w6, n6 - w6], [w, n - w]]
        print("n6(%d/%d) vs %s(%d/%d): p = %.4f" % (w6, n6, p, w, n, fisher(w6, n6 - w6, w, n - w)))

# n6 vs 所有 map2 无修复批（n2+n4+n5）合并
wsum = sum(acc[p][0] for p in ['n2', 'n4', 'n5'] if p in acc)
nsum = sum(acc[p][1] for p in ['n2', 'n4', 'n5'] if p in acc)
print("n6(%d/%d) vs n2+n4+n5(%d/%d): p = %.4f" % (
    w6, n6, wsum, nsum, fisher(w6, n6 - w6, wsum, nsum - wsum)))
