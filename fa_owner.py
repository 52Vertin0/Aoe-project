import io, re, glob, collections, sys

TAGS = sys.argv[1:] or ['fa']


def rows(tag):
    for f in sorted(glob.glob(tag + '*.ait')):
        for l in io.open(f, encoding='utf-8', errors='replace'):
            p = l.split(' | ')
            if len(p) < 5:
                continue
            yield f, p[1].strip(), p[3].strip(), p[4].strip()


def to_int(s):
    try:
        return int(s)
    except Exception:
        return None


print('=== A. 我方(flag=0) BuildAction 建筑类型 ===')
for tag in TAGS:
    c = collections.Counter()
    sns = collections.Counter()
    for f, fr, fl, m in rows(tag):
        mm = re.search(r'BuildAction:(\S+) (\d+)', m)
        if mm and fl == '0':
            c[mm.group(1)] += 1
            sns[mm.group(2)] += 1
    print('  %s: %s' % (tag, dict(c.most_common(14))))
    low = sorted(int(x) for x in sns if int(x) < 12000)
    print('     11xxx 段 SN = %s' % (low[:40] if low else '(无)'))

print()
print('=== B. 关键 SN 是否出现在我方 BuildAction ===')
KEY = ['11096', '11097', '11098', '11099', '11100', '11101', '11104', '11105', '11106', '11107']
for tag in TAGS:
    sns = collections.Counter()
    for f, fr, fl, m in rows(tag):
        mm = re.search(r'BuildAction:(\S+) (\d+)', m)
        if mm and fl == '0':
            sns[mm.group(2)] += 1
    print('  %-4s %s' % (tag, ' '.join('%s=%d' % (k, sns.get(k, 0)) for k in KEY)))

print()
print('=== C. 引擎事件「产生了新的X」的 flag（判定初始阵营）===')
for tag in TAGS:
    for kw in ['箭塔', '市镇中心', '武器厂', '攻城武器厂', '谷仓', '兵营', '靶场', '农场', '房屋']:
        fl = collections.Counter()
        for f, fr, fl2, m in rows(tag):
            mm = re.search(r'产生了新的' + kw + r'\(编号[：:](\d+)\)', m)
            if mm:
                fl[fl2] += 1
        if fl:
            print('  %-4s %-10s flag=%s' % (tag, kw, dict(fl)))

print()
print('=== D. 敌方建筑候选：出现在「我们下令攻击」中的 SN 段 ===')
RE_ATK = re.compile(r'HumanAction:(\S+) (\d+) 设置攻击目标为 (\S+) (\d+)')
for tag in TAGS:
    b = collections.Counter()
    u = collections.Counter()
    for f, fr, fl, m in rows(tag):
        mm = RE_ATK.search(m)
        if not mm or fl != '0':
            continue
        tgt = int(mm.group(4))
        (b if 10000 <= tgt < 12000 else u)[mm.group(3)] += 1
    print('  %-4s 建筑类目标 %s' % (tag, dict(b.most_common(12))))
    print('       单位类目标 %s' % (dict(u.most_common(8))))
