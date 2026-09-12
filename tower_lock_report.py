import re, os, sys, collections, statistics

# 2026-09-14 箭塔迟滞闩锁报告：tl(v1, 13格+1格带) / tm(v2, 12格危险线+18格放行线)
# 核心指标：
#  ① 祭司死亡 / 胜局
#  ② 顶着敌塔感化 = 下发武器厂感化令时，敌塔在最近 150 帧内刚把祭司设为目标（= 正在挨塔打）
#  ③ 空转 = 已发现武器厂但整局 0 条感化令（被闸挡死）/ 死前 900 帧内 dS 几乎不变
#  ④ 抖动 = [PRST-TOWER-ABORT] 次数 + 反攻期 HumanMove:祭司 条数
TOWER_NEAR = 150
BATCHES = [
    ('pu', '基线复现A', ['pu%d.ait' % i for i in range(1, 9)]),
    ('ez', '基线复现B', ['ez%d.ait' % i for i in range(1, 9)]),
    ('tb', '基线复现C(本轮对照)', ['tb%d.ait' % i for i in range(1, 9)]),
    ('tn', 'v2 复现(12/18)', ['tn%d.ait' % i for i in range(1, 9)]),
    ('tl', 'v1: 13格/1格带', ['tl%d.ait' % i for i in range(1, 9)]),
    ('tm', 'v2: 12格/18格闩锁', ['tm%d.ait' % i for i in range(1, 9)]),
]


def one(f):
    if not os.path.exists(f):
        return None
    s = dict(vicF=0, defF=0, reason='', endF=0, wsF=0, priestDeathF=0,
             towerOnPriest=[], convSiege=[], tAbort=0, tAbortFirst=0,
             lockBad=0, lockOn=0, lcN=0, holdN=0, tDmin=[], moves=0, wsCount=0)
    for line in open(f, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) < 5:
            continue
        fr, flag, msg = p[1].strip(), p[3].strip(), p[4].strip()
        if not fr.isdigit():
            continue
        fr = int(fr)
        s['endF'] = max(s['endF'], fr)
        if 'VICTORY' in msg:
            s['vicF'] = s['vicF'] or fr
        if 'DEFEAT:' in msg and s['defF'] == 0:
            s['defF'] = fr
            s['reason'] = re.sub(r'\s*!!!.*', '', re.sub(r'^.*DEFEAT:\s*', '', msg))
            if 'Priest' in s['reason']:
                s['priestDeathF'] = fr
        if 'Enemy Siege Workshop found' in msg:
            s['wsCount'] += 1
            if s['wsF'] == 0:
                s['wsF'] = fr
        if re.search(r'HumanAction:箭塔 \d+ 设置攻击目标为 祭司 \d+', msg):
            s['towerOnPriest'].append(fr)
        m = re.search(r'HumanAction:祭司 (\d+) 设置转换目标为 (\S+?) (\d+)', msg)
        if m and '攻城武器厂' in m.group(2):
            s['convSiege'].append(fr)
        if fr >= 33000 and 'HumanMove:祭司' in msg:
            s['moves'] += 1
        if '[PRST-TOWER-ABORT' in msg:
            s['tAbort'] += 1
            if s['tAbortFirst'] == 0:
                s['tAbortFirst'] = fr
        if '[LC-DBG' in msg:
            s['lcN'] += 1
            td = re.search(r'tD=([-\d.]+)', msg)
            dg = re.search(r'tDgr=(\d)', msg)
            lk = re.search(r'lock=(\d)', msg)
            hd = re.search(r'hold=(\d)', msg)
            if td and float(td.group(1)) >= 0:
                s['tDmin'].append(float(td.group(1)))
            if dg and lk and lk.group(1) == '1':
                s['lockOn'] += 1
                if dg.group(1) == '1':
                    s['lockBad'] += 1
            if hd and hd.group(1) == '1':
                s['holdN'] += 1
    s['convUnderFire'] = sum(1 for cf in s['convSiege']
                             if any(0 <= cf - tf <= TOWER_NEAR for tf in s['towerOnPriest']))
    s['fireN'] = len(s['towerOnPriest'])
    s['fireFirst'] = s['towerOnPriest'][0] if s['towerOnPriest'] else 0
    s['stall'] = 1 if (s['wsF'] and not s['convSiege']) else 0
    return s


def pct(a, b):
    return f"{100.0*a/b:.0f}%" if b else '-'


def med(v):
    return f"{statistics.median(v):.0f}" if v else '-'


def load(files):
    return [r for r in (one(f) for f in files) if r]


print('=' * 128)
print(f'{"批次":<20}{"胜":>6}{"祭司死":>8}{"WS发现":>8}{"WS中位":>7}{"塔打祭司":>9}'
      f'{"顶塔感化":>9}{"感化令":>7}{"空转局":>7}{"ABORT":>7}{"祭司移动令":>11}')
SUMM = dict()
for b, name, files in BATCHES:
    rows = load(files)
    if not rows:
        continue
    w = sum(1 for r in rows if r['vicF'] > 0 and (r['defF'] == 0 or r['vicF'] <= r['defF']))
    SUMM[b] = dict(rows=rows, n=len(rows), w=w,
                   pd=sum(1 for r in rows if r['priestDeathF']),
                   wsn=sum(1 for r in rows if r['wsF']),
                   wsf=[r['wsF'] for r in rows if r['wsF']],
                   fg=sum(1 for r in rows if r['fireN']),
                   cuf=sum(r['convUnderFire'] for r in rows),
                   cv=sum(len(r['convSiege']) for r in rows),
                   st=sum(r['stall'] for r in rows),
                   ab=sum(r['tAbort'] for r in rows),
                   mv=sum(r['moves'] for r in rows))
    S = SUMM[b]
    n = S['n']
    print('%-20s%6s%8s%8s%7s%9s%9s%7s%7s%7s%11s' % (
        b + '/' + name, '%d/%d' % (w, n), '%d/%d' % (S['pd'], n), '%d/%d' % (S['wsn'], n),
        med(S['wsf']), '%d/%d' % (S['fg'], n), S['cuf'], S['cv'], S['st'], S['ab'], S['mv']))

for b in ('tl', 'tm'):
    if b not in SUMM:
        continue
    print()
    print('=' * 128)
    print(f'逐局明细（{b}）')
    print(f'{"局":<7}{"末帧":>7}{"胜":>3}{"负":>3}{"死因":<22}{"WS帧":>7}{"祭司死帧":>9}'
          f'{"塔首打祭司":>11}{"感化令":>7}{"顶塔":>5}{"ABORT":>7}{"移动令":>7}{"hold采样":>9}')
    for r, f in zip(load(['%s%d.ait' % (b, i) for i in range(1, 9)]),
                    ['%s%d.ait' % (b, i) for i in range(1, 9)]):
        print('%-7s%7s%3s%3s%-22s%7s%9s%11s%7s%5s%7s%7s%9s' % (
            f, r['endF'], 'Y' if r['vicF'] else '', 'Y' if r['defF'] else '',
            r['reason'][:20], r['wsF'] or '-', r['priestDeathF'] or '-',
            r['fireFirst'] or '-', len(r['convSiege']), r['convUnderFire'],
            r['tAbort'], r['moves'], r['holdN']))

print()
print('=' * 128)
print('机制证据')
for b in ('pu', 'pg', 'tl', 'tm'):
    if b not in SUMM:
        continue
    rows = SUMM[b]['rows']
    lb = sum(r['lockBad'] for r in rows)
    hm = sum(r['holdN'] for r in rows)
    lc = sum(r['lcN'] for r in rows)
    tdm = [min(r['tDmin']) for r in rows if r['tDmin']]
    print('%-5s%3d 局   LC-DBG采样=%5d  hold=1采样=%5d  lock=1且tDgr=1(顶着塔仍持锁)=%4d   最近塔距最小值中位=%5s 格'
          % (b, SUMM[b]['n'], lc, hm, lb, med(tdm)))
