import re, os, collections

# 祭司阵亡构成分析（全部批次）：塔是不是主因？
BATCHES = ['pu', 'ez', 'pg', 'tl', 'tm', 'lc', 'll', 'lm', 'ln', 'lj']
WIN = 1500   # 死前 1500 帧(=1 分钟)内的攻击事件算作"致死圈"

def one(f):
    d = dict(game=f, deathF=0, wsF=0, endF=0, vic=False,
             tower=[], atk=[], conv=[], killerSN='')
    for line in open(f, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) < 5:
            continue
        fr, msg = p[1].strip(), p[4].strip()
        if not fr.isdigit():
            continue
        fr = int(fr)
        d['endF'] = max(d['endF'], fr)
        if 'VICTORY' in msg:
            d['vic'] = True
        if 'DEFEAT: Priest killed' in msg and not d['deathF']:
            d['deathF'] = fr
        if 'Enemy Siege Workshop found' in msg and not d['wsF']:
            d['wsF'] = fr
        if re.search(r'HumanAction:箭塔 \d+ 设置攻击目标为 祭司 \d+', msg):
            d['tower'].append(fr)
        m = re.search(r'(\D+?)\(编号[:：](\d+)\)开始向祭司\(编号[:：]\d+\)攻击', msg)
        if m:
            d['atk'].append((m.group(1).strip(), fr))
        m = re.search(r'HumanAction:祭司 \d+ 设置转换目标为 (\S+?) (\d+)', msg)
        if m:
            d['conv'].append((m.group(1), fr, m.group(2)))
    return d


tot = dict(games=0, deaths=0, tower=0, unit=0, both=0, none=0, pre33000=0, wsBefore=0,
           convAtDeath=0, towerOnly=0, unitOnly=0)
kinds = collections.Counter()
det = []
for b in BATCHES:
    for i in range(1, 9):
        f = '%s%d.ait' % (b, i)
        if not os.path.exists(f):
            continue
        d = one(f)
        tot['games'] += 1
        if d['deathF'] == 0:
            continue
        tot['deaths'] += 1
        df = d['deathF']
        tw = [x for x in d['tower'] if 0 <= df - x <= WIN]
        at = [(n, x) for n, x in d['atk'] if 0 <= df - x <= WIN]
        hasT = len(tw) > 0
        hasU = len(at) > 0
        if hasT and hasU:
            tot['both'] += 1
        elif hasT:
            tot['towerOnly'] += 1
        elif hasU:
            tot['unitOnly'] += 1
        else:
            tot['none'] += 1
        if df < 33000:
            tot['pre33000'] += 1
        if d['wsF'] and d['wsF'] < df:
            tot['wsBefore'] += 1
        cv = [c for c in d['conv'] if 0 <= df - c[1] <= WIN]
        if cv:
            tot['convAtDeath'] += 1
        for n, _ in at:
            kinds[n] += 1
        det.append((f, df, d['wsF'], 'T' if hasT else '-', 'U' if hasU else '-',
                    len(tw), len(at), (cv[-1][0] if cv else '-'),
                    d['vic'], (df < 33000)))

print('=' * 118)
print('祭司阵亡构成（全批次，死前 %d 帧窗）' % WIN)
print('=' * 118)
print('总局数 %d，祭司阵亡 %d 局（%.0f%%）' % (tot['games'], tot['deaths'], 100.0*tot['deaths']/tot['games']))
print('  ① 死前有【敌箭塔】向祭司开火            : %d 局' % (tot['both'] + tot['towerOnly']))
print('       其中"只有塔"(无单位近身攻击)      : %d 局' % tot['towerOnly'])
print('  ② 死前有【敌方单位】向祭司发起攻击      : %d 局' % (tot['both'] + tot['unitOnly']))
print('       其中"只有单位"                    : %d 局' % tot['unitOnly'])
print('       两者都有                          : %d 局' % tot['both'])
print('  ③ 死前窗口内没有任何攻击事件(猝死/毒)   : %d 局' % tot['none'])
print('  ④ 反攻未发起就死(deathF < 33000)        : %d 局 (%.0f%% of deaths)' % (tot['pre33000'], 100.0*tot['pre33000']/max(1,tot['deaths'])))
print('  ⑤ 死前已发现武器厂                      : %d 局' % tot['wsBefore'])
print('  ⑥ 死前 1 分钟内在施法感化(单位/建筑)    : %d 局' % tot['convAtDeath'])
print()
print('死前窗口内"向祭司发起攻击"的敌方兵种计数（Top）:')
for n, c in kinds.most_common(8):
    print('   %-14s %d' % (n, c))
print()
print('逐局明细（deathF<33000 标 EARLY；T=塔参与 U=单位参与）')
print('%-9s%8s%8s%4s%4s%5s%5s%-12s%4s%6s' % ('局', '死亡帧', 'WS帧', 'T', 'U', '塔次', '攻次', '死前感化目标', '胜', 'EARLY'))
for r in sorted(det, key=lambda x: x[1]):
    print('%-9s%8d%8s%4s%4s%5d%5d%-12s%4s%6s' % (
        r[0], r[1], r[2] or '-', r[3], r[4], r[5], r[6], r[7][:10], 'Y' if r[8] else '', 'Y' if r[9] else ''))
