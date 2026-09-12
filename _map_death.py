# -*- coding: utf-8 -*-
"""earlyclub8 版 map 图：祭死(W vs P) 死前态势对比。
提取每局祭司死亡前最后一条 BEAT：pr@(祭司坐标) / bbox(我军包围盒) / nMy / nEA / Mil / pr hp。
判断：祭司是否脱离军队独自推进(H2)，还是随军但被集火(H1)。
"""
import re, glob, os, collections, math

TAG = 'earlyclub8'
files = sorted(glob.glob(f'{TAG}_map_r0_*.ait'))

def parse_beat(line):
    d = {}
    m = re.search(r'\[BEAT f=(\d+)', line)
    if not m: return None
    d['f'] = int(m.group(1))
    for key in ['Mil', 'nMy', 'nEA']:
        mm = re.search(r'\b%s=(\d+)' % key, line)
        if mm: d[key] = int(mm.group(1))
    mm = re.search(r'pr=\(sn\d+ st(\d+) hp(\d+)/100 ccd(-?\d+)\)', line)
    if mm: d['prst'], d['prhp'], d['prccd'] = int(mm.group(1)), int(mm.group(2)), int(mm.group(3))
    mm = re.search(r'bbox=\(x([\d.]+)\.\.([\d.]+),y([\d.]+)\.\.([\d.]+)\)', line)
    if mm: d['bx0'], d['bx1'], d['by0'], d['by1'] = map(float, mm.groups())
    mm = re.search(r'pr@=\(([\d.]+),([\d.]+)\)', line)
    if mm: d['prx'], d['pry'] = map(float, mm.groups())
    return d

def in_bbox(d):
    if 'prx' not in d or 'bx0' not in d: return None
    return (d['bx0'] <= d['prx'] <= d['bx1']) and (d['by0'] <= d['pry'] <= d['by1'])

def dist_to_bbox(d):
    if 'prx' not in d or 'bx0' not in d: return None
    cx = (d['bx0'] + d['bx1']) / 2; cy = (d['by0'] + d['by1']) / 2
    return math.hypot(d['prx'] - cx, d['pry'] - cy)

rows = []
for fn in files:
    t = open(fn, encoding='utf-8', errors='replace').read()
    if t.count('[BEAT') < 5: continue
    if '被祭司转换,归属阵营1->0' in t: res = 'W'
    elif 'DEFEAT: Priest killed' in t: res = 'P'
    elif 'DEFEAT: Town Center destroyed' in t: res = 'T'
    else: res = 'U'
    # 死亡帧
    df = None
    if res == 'P':
        mm = re.search(r'DEFEAT: Priest killed', t)
        # 取最后一个 BEAT 的帧作为近似死亡帧上下文
    # 祭司最后一条 BEAT（全场，或死亡前）
    beats = [parse_beat(l) for l in t.splitlines() if '[BEAT' in l]
    beats = [b for b in beats if b]
    if not beats: continue
    last = beats[-1]
    rows.append(dict(fn=os.path.basename(fn), res=res, last=last,
                     inbb=in_bbox(last), dbb=dist_to_bbox(last)))

byres = collections.defaultdict(list)
for r in rows: byres[r['res']].append(r)

def med(xs):
    xs = sorted(xs)
    m = len(xs)
    if m == 0: return 0
    return xs[m//2] if m%2 else (xs[m//2-1]+xs[m//2])/2

print('=' * 96)
print(f'{TAG} 祭死 vs 胜 死前态势对比（n 局，每局取最后一条 BEAT）')
print('=' * 96)
for res in ['W', 'P', 'U']:
    sub = byres[res]
    if not sub: continue
    nmy = [r['last'].get('nMy',0) for r in sub]
    nmil = [r['last'].get('Mil',0) for r in sub]
    hp = [r['last'].get('prhp',-1) for r in sub]
    dbb = [r['dbb'] for r in sub if r['dbb'] is not None]
    inbb = sum(1 for r in sub if r['inbb'])
    print(f'\n[{res}] n={len(sub)}')
    print(f'  祭司死前 nMy(我军总数) 中位 {med(nmy):.0f} | Mil(军队) 中位 {med(nmil):.0f} | pr hp 中位 {med(hp):.0f}')
    if dbb:
        print(f'  祭司→我军包围盒中心距离 中位 {med(dbb):.1f} 格 | 在盒内 {inbb}/{len(sub)}')
        # 距离分层
        near = sum(1 for x in dbb if x <= 10)
        far = sum(1 for x in dbb if x > 20)
        print(f'  近(≤10格) {near}  远(>20格) {far}  （近=随军 H1，远=脱队 H2）')
print('=' * 96)
