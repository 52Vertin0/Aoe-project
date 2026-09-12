import re, os, sys, collections, statistics

# 护驾粘滞修复：批次对比（祭司存活 / 全军攻击效率 / 护驾目标粘滞度）
BATCHES = [
    ('pu', '基线（复现A）', ['pu%d.ait' % i for i in range(1, 9)]),
    ('ez', '基线（复现B）', ['ez%d.ait' % i for i in range(1, 9)]),
    ('pg', '护驾粘滞修复', ['pg%d.ait' % i for i in range(1, 9)]),
]


def one(f):
    if not os.path.exists(f):
        return None
    s = dict(vicF=0, defF=0, reason='', endF=0, guardAge=[], cmds=0, atks=0,
             thrashUnits=0, units=set(), guardN=0, ageGt50=0,
             seq=[], flips=0, stuckUnits=0)
    cmd = collections.Counter()
    atk = collections.Counter()
    tgt = collections.defaultdict(set)
    for line in open(f, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) < 5:
            continue
        fr, color, flag, msg = p[1].strip(), p[2].strip(), p[3].strip(), p[4].strip()
        if not fr.isdigit():
            continue
        fr = int(fr)
        s['endF'] = max(s['endF'], fr)
        if 'VICTORY' in msg and s['vicF'] == 0:
            s['vicF'] = fr
        if 'DEFEAT:' in msg and s['defF'] == 0:
            s['defF'] = fr
            s['reason'] = re.sub(r'\s*!!!.*', '', re.sub(r'^.*DEFEAT:\s*', '', msg))
        if fr < 33000:
            continue
        m = re.match(r'^HumanAction:(?!祭司)(\D+?) (\d+) 设置攻击目标为 (\S+?) (\d+)', msg)
        if m and flag == '0':
            cmd[m.group(2)] += 1
            tgt[m.group(2)].add(m.group(4))
            s['units'].add(m.group(2))
            continue
        m = re.match(r'^(\D+?)\(编号[:：](\d+)\)开始向(\S+?)\(编号[:：](\d+)\)攻击', msg)
        if m and m.group(1) != '祭司' and m.group(4) != '祭司':
            atk[m.group(2)] += 1
            continue
        if '[PRIEST GUARD]' in msg:
            s['guardN'] += 1
            tm = re.search(r'SN=(\d+)', msg)
            if tm:
                s['seq'].append(tm.group(1))
            am = re.search(r'age=(\d+)', msg)
            if am:
                s['guardAge'].append(int(am.group(1)))
                if int(am.group(1)) >= 50:
                    s['ageGt50'] += 1
    # 护驾目标「翻转率」：相邻 50 帧采样之间目标 SN 发生变化的比例（基线 pu5 实测≈100%）
    s['flips'] = sum(1 for a, b in zip(s['seq'], s['seq'][1:]) if a != b)
    s['seqN'] = len(s['seq'])
    s['cmds'] = sum(cmd.values())
    s['atks'] = sum(atk.values())
    # 卡死单位：发令 ≥20 且 出手/发令 < 0.1（每一条令都没换来出手）
    s['thrashUnits'] = sum(1 for sn, c in cmd.items() if c >= 20 and atk.get(sn, 0) < c * 0.1)
    # 重度卡死：发令 ≥50 且 出手 == 0（整局一条攻击都没打出去）
    s['stuckUnits'] = sum(1 for sn, c in cmd.items() if c >= 50 and atk.get(sn, 0) == 0)
    s['unitN'] = len(s['units'])
    return s


def pct(a, b):
    return f"{100.0*a/b:.0f}%" if b else '-'


print('=' * 118)
print(f'{"批次":<6}{"胜/负":>8}{"祭司死":>7}{"单位数":>7}{"发令":>8}{"出手":>8}{"出手/令":>9}{"卡死单位":>9}{"重度卡死":>9}{"护驾翻转率":>12}')
SUMM = {}
for b, name, files in BATCHES:
    rows = [one(f) for f in files]
    rows = [r for r in rows if r]
    if not rows:
        continue
    w = sum(1 for r in rows if r['vicF'] > 0 and (r['defF'] == 0 or r['vicF'] <= r['defF']))
    l = sum(1 for r in rows if r['defF'] > 0)
    pd = sum(1 for r in rows if 'Priest' in r['reason'])
    cmds = sum(r['cmds'] for r in rows)
    atks = sum(r['atks'] for r in rows)
    un = sum(r['unitN'] for r in rows)
    th = sum(r['thrashUnits'] for r in rows)
    st = sum(r['stuckUnits'] for r in rows)
    sq = sum(r['seqN'] for r in rows)
    fl = sum(r['flips'] for r in rows)
    SUMM[b] = dict(w=w, l=l, pd=pd, n=len(rows), cmds=cmds, atks=atks, un=un, th=th,
                   st=st, seqN=sq, flips=fl)
    print(f'{b:<6}{f"{w}/{l}":>8}{f"{pd}/{len(rows)}":>7}{un:>7}{cmds:>8}{atks:>8}'
          f'{pct(atks,cmds):>9}{th:>9}{st:>9}{pct(fl,sq):>12}')

print()
print('=' * 112)
print('逐局明细（pg 批次）')
print(f'{"局":<8}{"末帧":>8}{"胜":>3}{"负":>3}{"死因":<22}{"单位":>5}{"发令":>7}{"出手":>7}{"比":>7}{"卡死":>5}')
for f in ['pg%d.ait' % i for i in range(1, 9)]:
    r = one(f)
    if not r:
        continue
    print(f'{f:<8}{r["endF"]:>8}{("Y" if r["vicF"] else ""):>3}{("Y" if r["defF"] else ""):>3}'
          f'{r["reason"][:20]:<22}{r["unitN"]:>5}{r["cmds"]:>7}{r["atks"]:>7}'
          f'{pct(r["atks"],r["cmds"]):>7}{r["thrashUnits"]:>5}')

print()
print('=' * 118)
print('改动前后对比')
A = SUMM.get('pu'); C = SUMM.get('pg')
if A and C:
    rows = [
        ('祭司死亡局数', A['pd'], C['pd'], 'min'),
        ('胜局数', A['w'], C['w'], 'max'),
        ('反攻期总发令', A['cmds'], C['cmds'], 'min'),
        ('反攻期总出手', A['atks'], C['atks'], 'max'),
        ('出手/发令 %', 100.0*A['atks']/max(1,A['cmds']), 100.0*C['atks']/max(1,C['cmds']), 'max'),
        ('卡死单位数', A['th'], C['th'], 'min'),
        ('重度卡死单位数(令≥50/出手0)', A['st'], C['st'], 'min'),
        ('护驾目标翻转率 %', 100.0*A['flips']/max(1,A['seqN']), 100.0*C['flips']/max(1,C['seqN']), 'min'),
    ]
    print(f'{"指标":<30}{"pu基线":>12}{"pg修复":>12}{"变化":>14}')
    for n, a, b, want in rows:
        d = b - a
        mark = '↑' if d > 0 else ('↓' if d < 0 else '=')
        good = (d > 0) if want == 'max' else (d < 0)
        print(f'{n:<30}{a:>12.1f}{b:>12.1f}{(mark+abs(d).__format__(".1f")):>14}{"  ✓" if good else ("  ✗" if d else "")}')
