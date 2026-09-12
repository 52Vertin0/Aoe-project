import re, sys, os

# 提取祭司死亡局的前后上下文：祭司指令、护卫指令、祭司受伤、附近敌人
FILES = sys.argv[1:] or ['pu5.ait', 'pu7.ait', 'ez3.ait']

for f in FILES:
    if not os.path.exists(f):
        continue
    print('=' * 110)
    print(f'### {f}')
    rows = []
    for line in open(f, encoding='utf-8', errors='replace'):
        p = line.rstrip('\n').split('|')
        if len(p) < 5:
            continue
        t, fr, color, flag, msg = p[0], p[1].strip(), p[2].strip(), p[3].strip(), p[4]
        if not fr.isdigit():
            continue
        rows.append((int(fr), color, flag.strip(), msg.strip(), t))

    # 找死亡帧
    death = None
    for fr, c, fl, m, t in rows:
        if 'DEFEAT: Priest killed' in m:
            death = fr
            break
    if death is None:
        print('  无祭司死亡记录')
        continue
    print(f'  祭司死亡帧 = {death}  ({death/1500:.1f} 分钟)')

    # 祭司 SN
    psn = set()
    for fr, c, fl, m, t in rows:
        mm = re.search(r'祭司\(编号[:：](\d+)\)', m)
        if mm:
            psn.add(mm.group(1))
    print(f'  祭司 SN = {sorted(psn)}')

    lo = death - 900
    print(f'\n--- 死前 {lo}~{death} 帧内的祭司/护卫/受伤/附近敌 事件 ---')
    n = 0
    for fr, c, fl, m, t in rows:
        if fr < lo:
            continue
        if 'DEFEAT' in m:
            print(f'  {fr:>6} [{fl}] {m[:100]}')
            continue
        # 祭司自己的指令
        if '祭司' in m and ('HumanMove' in m or 'HumanAction' in m or 'GUARD' in m):
            print(f'  {fr:>6} [{fl}] {m[:110]}')
            n += 1
        elif '祭司' in m and ('被' in m or 'hp' in m.lower() or '受伤' in m or '攻击' in m):
            print(f'  {fr:>6} [{fl}] {m[:110]}')
            n += 1
        if n > 70:
            print('  ...(截断)')
            break
