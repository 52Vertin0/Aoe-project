import re, glob, os, collections, statistics

# 每局：护驾日志数 / 反攻期单位平均发令密度 / 祭司死否
G = ['pu%d.ait' % i for i in range(1, 9)] + ['ez%d.ait' % i for i in range(1, 9)]
print(f'{"局":<8}{"护驾日志":>8}{"反攻期指令":>10}{"单位数":>7}{"密度(/100帧)":>13}{"祭司死":>7}')
rows = []
for f in G:
    if not os.path.exists(f):
        continue
    guard = 0
    cmds = collections.Counter()
    units = set()
    death = 0
    fr_max = 0
    for line in open(f, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) < 5:
            continue
        fr, color, flag, msg = p[1].strip(), p[2].strip(), p[3].strip(), p[4].strip()
        if not fr.isdigit():
            continue
        fr = int(fr)
        if 'DEFEAT: Priest killed' in msg:
            death = 1
        if '[PRIEST GUARD]' in msg:
            guard += 1
        if fr < 33000:
            continue
        fr_max = max(fr_max, fr)
        m = re.match(r'^HumanAction:(\D+?) (\d+) 设置攻击目标为', msg)
        if m and flag == '0' and m.group(1) != '祭司':
            cmds[m.group(2)] += 1
            units.add(m.group(2))
    span = max(1, fr_max - 33000)
    nu = max(1, len(units))
    dens = sum(cmds.values()) / nu / (span / 100.0)
    rows.append((f, guard, sum(cmds.values()), nu, dens, death))
    print(f'{f:<8}{guard:>8}{sum(cmds.values()):>10}{nu:>7}{dens:>13.1f}{"是" if death else "":>7}')

print()
d = [r[4] for r in rows if r[5]]
s = [r[4] for r in rows if not r[5]]
print(f'祭司死亡局 平均指令密度 = {statistics.mean(d):.1f} (n={len(d)})')
print(f'祭司存活局 平均指令密度 = {statistics.mean(s):.1f} (n={len(s)})')
