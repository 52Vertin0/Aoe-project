import re, glob, os, sys

def parse(fn):
    r = dict(fn=fn, last=0, waves=None, first_conf=None, ws_orders=0,
             priest_death=None, wins=0, defeats=[], tower_orders=0,
             kit=0, ct=0)
    frames = []
    for line in open(fn, encoding='utf-8', errors='ignore'):
        p = line.split(' | ', 3)
        if len(p) < 4:
            continue
        try:
            fr = int(p[1])
        except ValueError:
            continue
        frames.append(fr)
        msg = p[3]
        if 'ALL WAVES DEFEATED' in msg and r['waves'] is None:
            r['waves'] = fr
        if '设置转换目标' in msg and r['first_conf'] is None:
            r['first_conf'] = fr
        if '攻城武器厂' in msg and ('转换' in msg or '设置转换目标' in msg):
            r['ws_orders'] += 1
        if '祭司' in msg and '死亡' in msg and r['priest_death'] is None:
            r['priest_death'] = fr
        if 'VICTORY! Siege Workshop converted' in msg:
            r['wins'] = 1
        m = re.search(r'DEFEAT: ([A-Za-z ]+)', msg)
        if m:
            r['defeats'].append((fr, m.group(1).strip()))
        if '[KIT-R' in msg:
            r['kit'] += 1
        if '[TOWER-APPROACH' in msg:
            r['tower_orders'] += 1
        if '开始向' in msg and '攻击' in msg:
            r['ct'] += 1
    r['last'] = frames[-1] if frames else 0
    return r

rows = []
for i in range(1, 13):
    fn = 'cur%d.ait' % i
    if os.path.exists(fn):
        rows.append(parse(fn))

W = sum(r['wins'] for r in rows)
U = sum(1 for r in rows if not r['wins'] and not r['defeats'])
L = sum(1 for r in rows if r['defeats'])
print('n=%d 胜=%d 负=%d 未决=%d  胜率=%.1f%%' % (len(rows), W, L, U, 100.0*W/len(rows)))
print()
hdr = '%-7s %-7s %-7s %-7s %-8s %-9s %-8s %-7s %-7s'
print(hdr % ('局','末帧','反攻','首感化','感化WS令','祭司亡帧','KIT-R','TOWER-AP','攻击令'))
for r in rows:
    print(hdr % (r['fn'][:-4], r['last'], r['waves'] or '-', r['first_conf'] or '-',
                 r['ws_orders'], r['priest_death'] or '-', r['kit'], r['tower_orders'], r['ct']))

print()
print('败因汇总:', {})
from collections import Counter
c = Counter()
for r in rows:
    for fr, why in r['defeats']:
        c[why] += 1
print(dict(c))
print()
print('祭司亡帧:', sorted(r['priest_death'] for r in rows if r['priest_death']))
print('首感化令帧:', sorted(r['first_conf'] for r in rows if r['first_conf']))
print('反攻帧:', sorted(r['waves'] for r in rows if r['waves']))
