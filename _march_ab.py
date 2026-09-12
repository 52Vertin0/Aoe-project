import re, sys
runs = ['_n0_1','_n0_2','_n0_3','_fix_1','_fix_2','_fix_3']
BL = 35.777
for r in runs:
    try:
        txt = open(r+'.dbg', encoding='utf-8', errors='replace').read()
    except FileNotFoundError:
        print(r, 'MISSING'); continue
    lines = txt.splitlines()
    # 1) hoplite SNs
    hop = set()
    for l in lines:
        m = re.search(r'产生了新的方阵兵\(编号:(\d+)\)', l)
        if m: hop.add(int(m.group(1)))
        m = re.search(r'方阵兵 (\d+) 移动至', l)
        if m: hop.add(int(m.group(1)))
    tot = en = 0
    for l in lines:
        m = re.search(r'HumanMove:方阵兵 (\d+) 移动至 \(([-\d.]+),([-\d.]+)\)', l)
        if not m: continue
        sn = int(m.group(1)); x = float(m.group(2)); y = float(m.group(3))
        tot += 1
        if y > 50*BL: en += 1
    # 2) 首次 nEB>0
    firstEB = None
    for l in lines:
        m = re.search(r'\[EB f=(\d+)\] nEB=(\d+)', l)
        if m and int(m.group(2)) > 0:
            firstEB = int(m.group(1)); break
    # 3) 转换
    conv = [l for l in lines if '被祭司转换' in l]
    # 4) 结局
    defeat = any('DEFEAT:' in l for l in lines)   # ⚠ 必须带冒号：裸 'DEFEAT' 会命中 'ALL WAVES DEFEATED!'（反攻触发日志）
    print('%-8s hopSN=%2d 方阵兵移动令=%5d 落敌区=%5d (%5.1f%%) | 首次nEB>0=%s | 转换=%d | DEFEAT=%s' %
          (r, len(hop), tot, en, (100.0*en/tot if tot else 0), firstEB if firstEB else '—', len(conv), defeat))
