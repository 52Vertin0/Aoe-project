import re, sys, os, collections

# 统计某局在时间窗内：我方各兵种存活数（产出-阵亡）+ 祭司位置线索
FILES = sys.argv[1:] or ['pu7.ait']

for f in FILES:
    if not os.path.exists(f):
        continue
    print('=' * 105)
    print(f'### {f}')
    born = collections.Counter()      # (sort, sn) -> frame
    dead = {}                          # sn -> frame
    priest_sn = None
    rows = []
    for line in open(f, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) < 5:
            continue
        fr, color, flag, msg = p[1].strip(), p[2].strip(), p[3].strip(), p[4].strip()
        if not fr.isdigit():
            continue
        fr = int(fr)
        if 'DEFEAT: Priest killed' in msg:
            rows.append((fr, 'DEATH', msg))
            break
        m = re.match(r'^HumanAction:祭司 (\d+) ', msg)
        if m:
            priest_sn = m.group(1)
        m = re.search(r'产生了新的(\S+?)\(编号[:：](\d+)\)', msg)
        if m and flag == '0':
            born[(m.group(1), m.group(2))] = fr
        m = re.search(r'^(\S+?)\(编号[:：](\d+)\)被摧毁', msg)
        if m:
            dead[m.group(2)] = fr
        rows.append((fr, '', msg))

    print(f'  祭司 SN = {priest_sn}')
    # 反攻起点
    def firstframe(pat):
        for fr, _, msg in rows:
            if re.search(pat, msg):
                return fr
        return None
    cf = firstframe(r'Force COUNTERATTACK|COUNTERATTACK')
    print(f'  反攻发起帧 = {cf}')

    # 军种
    MIL = ['复合弓兵', '方阵兵', '刀斧兵', '弓箭手', '战车', '战车弓兵', '投石车', '祭司']
    print(f'\n  {"时点帧":>8} {"复合弓":>6} {"方阵":>5} {"刀斧":>5} {"祭司":>5}  说明')
    checkpoints = [cf] if cf else []
    checkpoints += list(range(33000, 45000, 1000))
    for cp in checkpoints:
        if cp is None:
            continue
        cnt = collections.Counter()
        for (sort, sn), bf in born.items():
            if bf <= cp and (sn not in dead or dead[sn] > cp):
                cnt[sort] += 1
        print(f'  {cp:>8} {cnt["复合弓兵"]:>6} {cnt["方阵兵"]:>5} {cnt["刀斧兵"]:>5} {cnt["祭司"]:>5}')
    # 阵亡明细（反攻期）
    print(f'\n  反攻期(>={cf}) 我方阵亡明细:')
    dc = collections.Counter()
    for sn, df in dead.items():
        if cf and df >= cf:
            for (sort, s2), bf in born.items():
                if s2 == sn:
                    dc[sort] += 1
                    break
    for k, v in dc.most_common():
        print(f'    {k}: {v}')
