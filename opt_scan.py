import io, re, glob, collections, sys, statistics

def frame_of(line):
    p = line.split(' | ')
    for x in p:
        x = x.strip()
        if x.isdigit():
            return int(x)
    return None

def scan(tag, since=33001):
    after = collections.Counter(); before = collections.Counter()
    nA = nB = 0
    for f in sorted(glob.glob(tag + '*.ait')):
        for l in io.open(f, encoding='utf-8', errors='replace'):
            m = re.search(r'HumanAction:(\S+?) (\d+) 设置攻击目标为 (\S+) (\d+)', l)
            if not m:
                continue
            fr = frame_of(l)
            if fr is None:
                continue
            if fr >= since:
                after[m.group(3)] += 1; nA += 1
            else:
                before[m.group(3)] += 1; nB += 1
    return before, after, nB, nA

if __name__ == '__main__':
    for tag in ['gi', 'kd']:
        b, a, nb, na = scan(tag)
        print('==== %s ====' % tag)
        print('  反攻前攻击令 %d 条, 其中指向建筑(非单位名) = ?' % nb)
        print('  反攻前 top8: %s' % dict(b.most_common(8)))
        print('  反攻后攻击令 %d 条' % na)
        print('  反攻后 top12: %s' % dict(a.most_common(12)))
        print()
