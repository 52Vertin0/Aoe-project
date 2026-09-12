"""统计 ECO 判据行的工种实况：金工/木工/食物工 峰值与均值，以及四类门禁命中率。
用法: python goldstat.py [glob]
"""
import re, glob, os, sys

pat = re.compile(r'workers F(\d+) W(\d+) G(\d+) S(\d+) \|\| goldRich:(\d) woodStop:(\d) stoneStop:(\d) foodStop:(\d) woodTarget:(\d+)')
fpat = re.compile(r'\| (\d+) \|')

def collect(pattern):
    rows = []
    for p in sorted(glob.glob(pattern)):
        try:
            fh = open(p, encoding='utf-8', errors='replace')
        except OSError:
            continue
        for line in fh:
            m = pat.search(line)
            if not m:
                continue
            fm = fpat.search(line)
            f = int(fm.group(1)) if fm else -1
            F, W, G, S, gr, ws, ss, fs, wt = (int(x) for x in m.groups())
            rows.append((os.path.basename(p), f, F, W, G, S, gr, ws, ss, fs, wt))
        fh.close()
    return rows

def report(tag, rows, lo=0, hi=10**9):
    sel = [r for r in rows if lo <= r[1] < hi]
    if not sel:
        print('%s: 无样本' % tag)
        return
    n = len(sel)
    def st(idx, name):
        v = [r[idx] for r in sel]
        print('   %-6s max=%2d  mean=%.2f' % (name, max(v), sum(v) / n))
    print('%s: n=%d' % (tag, n))
    st(2, 'F食物')
    st(3, 'W木')
    st(4, 'G金')
    st(5, 'S石')
    print('   门禁命中: goldRich=%d woodStop=%d stoneStop=%d foodStop=%d  (占比 %.1f%%/%.1f%%/%.1f%%/%.1f%%)' % (
        sum(r[6] for r in sel), sum(r[7] for r in sel), sum(r[8] for r in sel), sum(r[9] for r in sel),
        100.0 * sum(r[6] for r in sel) / n, 100.0 * sum(r[7] for r in sel) / n,
        100.0 * sum(r[8] for r in sel) / n, 100.0 * sum(r[9] for r in sel) / n))
    st(10, 'woodTg')

if __name__ == '__main__':
    g = sys.argv[1] if len(sys.argv) > 1 else 'v1*.ait'
    rows = collect(g)
    print('glob=%s  总样本=%d' % (g, len(rows)))
    report('全体', rows)
    report('前期 frame<20000', rows, 0, 20000)
    report('铜器后 frame>=20000', rows, 20000)
    report('后期 frame>=33000', rows, 33000)
