import glob, os, re, sys

# 批号前缀（显式，避免正则贪婪把 "n501" 拆成前缀 "n"）
PREFIXES = ['g1', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7', 'n8']


def collect(prefix):
    out = []
    for f in glob.glob(prefix + '*.ait'):
        base = os.path.basename(f)[:-4]
        # 前缀后必须恰好是 2 位序号（g101 / n501）
        rest = base[len(prefix):]
        if len(rest) == 2 and rest.isdigit():
            out.append(f)
    return sorted(out)


print("batch   N   W   L   U    win%  BHtot  BHmax  MilAvg  MilMin  PkTot")
for p in PREFIXES:
    fs = collect(p)
    if not fs:
        print("%-6s NO DATA" % p)
        continue
    W = L = U = BH = 0
    BHmax = 0
    mls = []
    pktot = 0
    for f in fs:
        j = f[:-4] + '.jsonl'
        txt = open(f, encoding='utf-8', errors='ignore').read()
        jt = open(j, encoding='utf-8', errors='ignore').read() if os.path.exists(j) else ''
        if '"win":true' in jt:
            W += 1
        elif 'DEFEAT:' in txt:
            L += 1
        else:
            U += 1
        b = txt.count('BUILDER-HARD')
        BH += b
        BHmax = max(BHmax, b)
        ms = [int(x) for x in re.findall(r'Mil:(\d+)', txt)]
        mls.append(max(ms) if ms else 0)
        pktot += txt.count('Priest killed')
    n = len(fs)
    print("%-6s%3d%4d%4d%4d%8.1f%7d%7d%8.1f%8d%6d" % (
        p, n, W, L, U, W * 100.0 / n, BH, BHmax, sum(mls) / float(n), min(mls), pktot))
