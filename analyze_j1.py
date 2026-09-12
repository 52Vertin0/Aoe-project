# -*- coding: utf-8 -*-
"""j1(方案1+2 祭司自保后撤) vs g1(无闸基线) 对比。"""
import glob, re, os, math

EARLY = 23253  # 复合弓首产中位帧；<此帧死亡 = 早死

def load(batch):
    rows = []
    for ait in sorted(glob.glob(batch + '*.ait')):
        b = os.path.basename(ait)[:-4]
        win = False
        jl = b + '.jsonl'
        if os.path.exists(jl):
            for l in open(jl, errors='replace'):
                if '"win":true' in l:
                    win = True; break
        death = None; retreat = 0; rear = 0; adv = 0; conv = 0; lastf = 0
        for l in open(ait, errors='replace'):
            m = re.match(r'[^|]*\|\s*(\d+)\s*\|', l)
            if m:
                f = int(m.group(1))
                if f > lastf: lastf = f
                if 'DEFEAT: Priest killed' in l and (death is None or f < death):
                    death = f
            if 'PRIEST RETREAT' in l: retreat += 1
            if 'PRST-REAR' in l: rear += 1
            if 'Priest ADVANCE to Siege' in l: adv += 1
            if 'Priest CONVERT(defense)' in l: conv += 1
        res = 'WIN' if win else ('LOSS' if death is not None else 'UND')
        rows.append(dict(g=b, res=res, death=death, retreat=retreat, rear=rear, adv=adv, conv=conv, lastf=lastf))
    return rows

def agg(rows):
    d = dict(WIN=0, LOSS=0, UND=0)
    deaths = [r['death'] for r in rows if r['death'] is not None]
    early = [r['death'] for r in rows if r['death'] is not None and r['death'] < EARLY]
    for r in rows: d[r['res']] += 1
    return dict(n=len(rows), win=d['WIN'], loss=d['LOSS'], und=d['UND'],
                wr=100.0*d['WIN']/len(rows), deaths=len(deaths), early=len(early),
                retreat=sum(r['retreat'] for r in rows),
                rear=sum(r['rear'] for r in rows), rear_games=sum(1 for r in rows if r['rear'] > 0),
                adv=sum(r['adv'] for r in rows), adv_games=sum(1 for r in rows if r['adv'] > 0),
                conv=sum(r['conv'] for r in rows))

def fisher(a, b, c, d):
    n = a+b+c+d
    def C(n, k): return math.comb(n, k) if 0 <= k <= n else 0
    r1, r2, c1 = a+b, c+d, a+c
    pcut = C(r1, a)*C(r2, c)/C(n, c1)
    p = 0.0
    for i in range(max(0, c1-r2), min(c1, r1)+1):
        pv = C(r1, i)*C(r2, c1-i)/C(n, c1)
        if pv <= pcut + 1e-15: p += pv
    return p

j = load('j1'); g = load('g1')
A, B = agg(j), agg(g)

print('== j1 逐局 ==')
print('%-6s %-5s %7s %8s %8s %6s %6s' % ('game', 'res', 'death', 'RETREAT', 'REAR', 'ADV', 'CONV'))
for r in j:
    print('%-6s %-5s %7s %8d %8d %6d %6d' % (r['g'], r['res'], r['death'] or '-', r['retreat'], r['rear'], r['adv'], r['conv']))

print()
print('== 汇总对比 ==')
print('%-26s %-18s %-18s' % ('指标', 'g1(无闸基线)', 'j1(方案1+2)'))
print('%-26s %-18s %-18s' % ('胜/负/未决', '%d/%d/%d' % (B['win'], B['loss'], B['und']), '%d/%d/%d' % (A['win'], A['loss'], A['und'])))
print('%-26s %-18s %-18s' % ('胜率', '%.1f%%' % B['wr'], '%.1f%%' % A['wr']))
print('%-26s %-18s %-18s' % ('祭司死亡', B['deaths'], A['deaths']))
print('%-26s %-18s %-18s' % ('早死(<%d帧)' % EARLY, B['early'], A['early']))
print('%-26s %-18s %-18s' % ('PRIEST RETREAT 触发', '-', A['retreat']))
print('%-26s %-18s %-18s' % ('PRST-REAR 次数(局数)', '%d(%d局)' % (B['rear'], B['rear_games']), '%d(%d局)' % (A['rear'], A['rear_games'])))
print('%-26s %-18s %-18s' % ('ADV_SIEGE 次数(局数)', '%d(%d局)' % (B['adv'], B['adv_games']), '%d(%d局)' % (A['adv'], A['adv_games'])))
print('%-26s %-18s %-18s' % ('CONVERT(defense)', B['conv'], A['conv']))

print()
print('== Fisher 精确检验 (g1 vs j1, 双侧) ==')
print('胜率   %d/%d vs %d/%d  p=%.4f' % (B['win'], B['n'], A['win'], A['n'],
      fisher(B['win'], B['n']-B['win'], A['win'], A['n']-A['win'])))
print('祭司死亡 %d/%d vs %d/%d  p=%.4f' % (B['deaths'], B['n'], A['deaths'], A['n'],
      fisher(B['deaths'], B['n']-B['deaths'], A['deaths'], A['n']-A['deaths'])))
print('早死   %d/%d vs %d/%d  p=%.4f' % (B['early'], B['n'], A['early'], A['n'],
      fisher(B['early'], B['n']-B['early'], A['early'], A['n']-A['early'])))
