import re, sys, os, collections

# 量化：我方单位在死亡窗口内的 发令数 vs 引擎实际"开始攻击"事件数
FILES = sys.argv[1:] or ['pu5.ait', 'pu7.ait', 'ez3.ait']
WIN = 400

for f in FILES:
    if not os.path.exists(f):
        continue
    cmds = collections.Counter()   # sn -> 命令数
    atks = collections.Counter()   # sn -> 引擎开始攻击次数
    tgt_of = collections.defaultdict(collections.Counter)
    rows = []
    death = None
    for line in open(f, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) < 5:
            continue
        fr, color, flag, msg = p[1].strip(), p[2].strip(), p[3].strip(), p[4].strip()
        if not fr.isdigit():
            continue
        fr = int(fr)
        rows.append((fr, flag, msg))
        if 'DEFEAT: Priest killed' in msg and death is None:
            death = fr
    if death is None:
        print(f'{f}: 无祭司死亡')
        continue
    lo = death - WIN
    for fr, flag, msg in rows:
        if fr < lo or fr > death:
            continue
        m = re.match(r'^HumanAction:(\D+?) (\d+) 设置攻击目标为 (\S+?) (\d+)', msg)
        if m and flag == '0':
            cmds[m.group(2)] += 1
            tgt_of[m.group(2)][m.group(3) + ' ' + m.group(4)] += 1
            continue
        m = re.match(r'^(\D+?)\(编号[:：](\d+)\)开始向(\S+?)\(编号[:：](\d+)\)攻击', msg)
        if m and m.group(1) != '祭司':
            atks[m.group(2)] += 1
    print('=' * 100)
    print(f'### {f}  祭司死亡帧={death}  窗口={WIN}帧')
    print(f'  {"单位SN":>9} {"发令数":>6} {"出手数":>6} {"不同目标数":>10}  目标分布')
    tot_c = tot_a = 0
    for sn, c in cmds.most_common(8):
        tot_c += c; tot_a += atks.get(sn, 0)
        tg = tgt_of[sn]
        top = ', '.join(f'{k}×{v}' for k, v in tg.most_common(3))
        print(f'  {sn:>9} {c:>6} {atks.get(sn,0):>6} {len(tg):>10}  {top}')
    print(f'  {"合计":>9} {tot_c:>6} {tot_a:>6}')
