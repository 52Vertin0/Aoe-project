# -*- coding: utf-8 -*-
"""
tower_atk_probe.py — 统计「反攻时攻击箭塔，部分士兵不攻击」的现场分布。
口径：ait 真格式 = time | frame | color | flag | message
  p = line.split(' | ', 3) -> p[0]=time, p[1]=frame, p[2]=color, p[3]='flag | message'
  注意 message 里还有一层 ' | '，故必须先切 3 刀。
关键约定（来自工作记忆）：
  - HumanAction/HumanMove 的 flag = 指令来源阵营：0=我方AI，1=敌方(脚本)
  - 「产生了新的X」的 flag = 单位初始阵营，不能用来过滤单位归属
用法：python tower_atk_probe.py rec1.ait [反攻帧=33000]
"""
import sys, re, io
from collections import defaultdict, Counter

RE_ATK = re.compile(r'设置攻击目标为\s*([\u4e00-\u9fa5A-Za-z.]+)\s+(\d+)')
RE_MOVE = re.compile(r'HumanMove:([\u4e00-\u9fa5A-Za-z.]+)\s+(\d+)')
RE_NEW = re.compile(r'产生了新的([\u4e00-\u9fa5A-Za-z.]+)\(编号:(\d+)\)')
RE_DEATH = re.compile(r'([\u4e00-\u9fa5A-Za-z.]+)\(编号:(\d+)\)死亡')
RE_ACTOR = re.compile(r'HumanAction:([\u4e00-\u9fa5A-Za-z.]+)\s+(\d+)')

def parse(path):
    rows = []
    for raw in io.open(path, encoding='utf-8', errors='replace'):
        raw = raw.rstrip('\n').rstrip('\r')
        p = raw.split(' | ', 3)
        if len(p) < 4:
            continue
        try:
            fr = int(p[1])
        except ValueError:
            continue
        seq = p[3].split(' | ')
        flag = seq[0].strip()
        msg = seq[-1] if len(seq) > 1 else ''
        rows.append((fr, p[2].strip(), flag, msg.strip(), raw))
    return rows

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'rec1.ait'
    CA = int(sys.argv[2]) if len(sys.argv) > 2 else 33000
    rows = parse(path)
    print('=== 文件 %s  总行 %d  反攻阈值 f>=%d ===' % (path, len(rows), CA))

    # ---------- 1. 攻击令按 (flag, 目标类型) 分离 ----------
    atk_by_flag = defaultdict(Counter)     # flag -> Counter(target type)
    atk_actor_flag = defaultdict(Counter)  # flag -> Counter(actor type)
    tower_orders = []                      # (fr, flag, actor, actorSN, tgtSN)
    for fr, color, flag, msg, raw in rows:
        m = RE_ATK.search(msg)
        if not m:
            continue
        tgt, tsn = m.group(1), int(m.group(2))
        atk_by_flag[flag][tgt] += 1
        ma = RE_ACTOR.search(msg)
        actor, asn = (ma.group(1), int(ma.group(2))) if ma else ('?', -1)
        atk_actor_flag[flag][actor] += 1
        if tgt == '箭塔':
            tower_orders.append((fr, flag, actor, asn, tsn))

    for flag in sorted(atk_by_flag):
        print('\n--- 攻击令目标分布  指令来源flag=%s  (共 %d) ---' %
              (flag, sum(atk_by_flag[flag].values())))
        for t, c in atk_by_flag[flag].most_common(12):
            print('   %-12s %6d' % (t, c))

    print('\n=== 「设置攻击目标为 箭塔」共 %d 条 ===' % len(tower_orders))
    by_flag = Counter(o[1] for o in tower_orders)
    print('   按指令来源 flag:', dict(by_flag))
    my_tower = [o for o in tower_orders if o[1] == '0']
    print('   我方(flag=0) 攻塔令: %d 条' % len(my_tower))
    if my_tower:
        print('   前 12 条:')
        for fr, flag, actor, asn, tsn in my_tower[:12]:
            print('      f=%-6d %s SN=%-6d -> 塔 SN=%d' % (fr, actor, asn, tsn))
        c_actor = Counter(o[2] for o in my_tower)
        print('   按兵种:', dict(c_actor))
        print('   帧分布（千帧桶）:',
              dict(Counter(o[0] // 1000 * 1000 for o in my_tower)))
        en = [o for o in my_tower if o[0] >= CA]
        print('   其中反攻期(f>=%d): %d 条' % (CA, len(en)))

    # ---------- 2. 我方军队构成 ----------
    #  ⚠ 归属判据：SN 数值区间不可靠（本局我方 army 是 91xxx、村民 41xxx，敌方预置也是 91xxx）。
    #    唯一可靠来源 = 「产生了新的X」且 flag==0（单位初始阵营）。被感化的敌方单位 flag 仍为 1，
    #    故我方军队里"感化来的兵"会漏掉 —— 对本问题无影响（攻塔主体是自产复合弓兵）。
    print('\n=== 我方单位（flag=0 的产生事件，按兵种）===')
    mine = defaultdict(list)   # type -> [SN]
    my_sns = set()
    for fr, color, flag, msg, raw in rows:
        m = RE_NEW.search(msg)
        if m and flag == '0':
            mine[m.group(1)].append(int(m.group(2)))
            my_sns.add(int(m.group(2)))
    for t, sns in sorted(mine.items(), key=lambda kv: -len(kv[1])):
        print('   %-14s %3d 个  SN %d~%d' % (t, len(sns), min(sns), max(sns)))
    print('   (我方 SN 总数 %d)' % len(my_sns))

    # ---------- 3. 反攻期：每个我方军队单位是否拿到过攻塔令 ----------
    army_sorts = [t for t in mine if t not in ('村民', '祭司')]
    print('\n=== 反攻期(f>=%d) 我方军队单位 vs 攻塔令 ===' % CA)
    got = set(o[3] for o in my_tower if o[0] >= CA)
    for t in sorted(army_sorts):
        sns = sorted(set(mine[t]))
        if not sns:
            continue
        g = [s for s in sns if s in got]
        print('   %-14s 共%3d 个, 拿到攻塔令 %3d 个 (%.0f%%)' %
              (t, len(sns), len(g), 100.0 * len(g) / len(sns)))
        if 0 < len(g) < len(sns):
            print('        未拿到: %s' % sorted(set(sns) - got)[:20])

    # ---------- 3b. 反攻期我方对【建筑类】目标的攻击令 ----------
    BLD = {'箭塔', '农场', '谷仓', '房屋', '仓库', '武器厂', '城镇中心', '兵营', '靶场', '马厩'}
    print('\n=== 反攻期(f>=%d) 我方(flag=0) 攻击令中【建筑类】目标 ===' % CA)
    bcnt = Counter(); bsample = []
    for fr, color, flag, msg, raw in rows:
        if fr < CA or flag != '0':
            continue
        m = RE_ATK.search(msg)
        if not m or m.group(1) not in BLD:
            continue
        bcnt[m.group(1)] += 1
        if len(bsample) < 8:
            ma = RE_ACTOR.search(msg)
            bsample.append((fr, ma.group(1) if ma else '?', ma.group(2) if ma else '?',
                            m.group(1), m.group(2)))
    print('   类型分布:', dict(bcnt) if bcnt else '(空 —— 反攻期我军对建筑 0 条攻击令)')
    for s in bsample:
        print('      f=%-6d %s SN=%s -> %s SN=%s' % s)

    # ---------- 3c. 攻塔诊断日志命中 ----------
    for tag in ('[TOWER-TGT', '[TOWER-SKIP'):
        n = sum(1 for r in rows if tag in r[3])
        print('   %s 命中 %d 条' % (tag, n))

    # ---------- 4. 反攻期移动令 / 攻击令 总量（看站桩 vs 空转） ----------
    print('\n=== 反攻期 我方(flag=0) 指令总量 ===')
    mv = Counter(); ac = Counter()
    for fr, color, flag, msg, raw in rows:
        if fr < CA or flag != '0':
            continue
        if 'HumanMove:' in msg:
            m = RE_MOVE.search(msg)
            if m: mv[m.group(1)] += 1
        if 'HumanAction:' in msg:
            m = RE_ACTOR.search(msg)
            if m: ac[m.group(1)] += 1
    print('   移动令:', dict(mv.most_common(10)))
    print('   攻击令:', dict(ac.most_common(10)))

    # ---------- 5. 存活/阵亡 ----------
    print('\n=== 我方单位阵亡（按兵种，仅统计 flag=0 产生过的 SN）===')
    dead = Counter()
    for fr, color, flag, msg, raw in rows:
        m = RE_DEATH.search(msg)
        if m and int(m.group(2)) in my_sns:
            dead[m.group(1)] += 1
    print('  ', dict(dead.most_common(12)) if dead else '(无)')

    # ---------- 6. 反攻期每个复合弓兵的指令画像（看"部分不攻击"） ----------
    print('\n=== 反攻期复合弓兵逐兵指令画像（前 20 个）===')
    per = defaultdict(lambda: {'atk': 0, 'mv': 0, 'firstAtk': None, 'lastAtk': None})
    for fr, color, flag, msg, raw in rows:
        if fr < CA or flag != '0':
            continue
        ma = RE_ACTOR.search(msg) if 'HumanAction:' in msg else None
        mm = RE_MOVE.search(msg) if 'HumanMove:' in msg else None
        if ma and ma.group(1) == '复合弓兵':
            sn = int(ma.group(2)); d = per[sn]
            d['atk'] += 1
            if d['firstAtk'] is None: d['firstAtk'] = fr
            d['lastAtk'] = fr
        elif mm and mm.group(1) == '复合弓兵':
            per[int(mm.group(2))]['mv'] += 1
    lst = sorted(per.items(), key=lambda kv: -kv[1]['atk'])
    print('   %-8s %6s %6s %9s %9s  %s' % ('SN', 'atk', 'mv', 'first', 'last', '兵种存活'))
    for sn, d in lst[:20]:
        print('   %-8d %6d %6d %9s %9s' % (sn, d['atk'], d['mv'], d['firstAtk'], d['lastAtk']))
    zero = [sn for sn, d in per.items() if d['atk'] == 0]
    print('   反攻期【零攻击令】的复合弓兵: %d 个 %s' % (len(zero), sorted(zero)[:20]))

if __name__ == '__main__':
    main()
