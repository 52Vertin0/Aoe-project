# -*- coding: utf-8 -*-
"""OJ debug_19485（失败，得分 411）逐项归因。
仅解析 debug 日志（nodebug 版），不跑局、不改码。
口径：
  · 阵营 = HumanMove/HumanAction 出现的编号为【我方】（AI 下发）；编号段是混编的，不能按 91xxx 段判。
  · 时间 MM:SS:CC（CC=百分秒）→ 秒 = MM*60+SS+CC/100；帧 = 秒*25（25fps=1500帧/分）。
"""
import re, sys, collections

path = sys.argv[1] if len(sys.argv) > 1 else \
    r'C:\Users\ZhuanZ\Downloads\debug_19485_4625f111-a9dc-4f81-9edb-8abe38ad1428.log'
raw = open(path, encoding='utf-8', errors='replace').read().splitlines()

T = re.compile(r'^(\d\d):(\d\d):(\d\d)\s')
MV = re.compile(r'^\d\d:\d\d:\d\d\s+HumanMove:(\S+)\s+(\d+)\s+移动至\s+\(([\d.]+),([\d.]+)\)')
AC = re.compile(r'^\d\d:\d\d:\d\d\s+HumanAction:(\S+)\s+(\d+)\s+设置(?:攻击|转换|工作)目标为\s+(\S+)\s+(\d+)')
ATK = re.compile(r'^\d\d:\d\d:\d\d\s+(\S+)\(编号:(\d+)\)开始向(\S+)\(编号：(\d+)\)攻击')
DIE = re.compile(r'^\d\d:\d\d:\d\d\s+(\S+)\(编号(\d+)\)死亡')

BL = 35.777


def sec(line):
    m = T.match(line)
    return int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3)) / 100.0 if m else -1


mine = set()          # 我方编号（AI 下发过令）
mv_mine = []          # (sec, unit, sn, x, y)
ac_mine = []
priest_mv = []
priest_ac = []
die_mine = []
die_all = []
atk_on_priest = []

for ln in raw:
    m = MV.match(ln)
    if m:
        s = sec(ln); unit, sn, x, y = m.group(1), int(m.group(2)), float(m.group(3)), float(m.group(4))
        mine.add(sn); mv_mine.append((s, unit, sn, x, y))
        if unit == '祭司': priest_mv.append((s, x, y))
        continue
    m = AC.match(ln)
    if m:
        s = sec(ln); unit, sn = m.group(1), int(m.group(2))
        mine.add(sn); ac_mine.append((s, unit, sn, m.group(3), int(m.group(4))))
        if unit == '祭司': priest_ac.append((s, m.group(3), int(m.group(4))))
        continue
    m = ATK.match(ln)
    if m:
        s = sec(ln); a_sn = int(m.group(2)); t_sn = int(m.group(4))
        if t_sn == 91168: atk_on_priest.append((s, m.group(1), a_sn))
        continue
    m = DIE.match(ln)
    if m:
        s = sec(ln); die_all.append((s, m.group(1), int(m.group(2))))
        continue

for s, u, sn in die_all:
    if sn in mine: die_mine.append((s, u, sn))

print('=' * 100)
print('【0】基本盘')
print('  日志行数 %d ｜ 我方编号数 %d ｜ 祭司=91168 ｜ 地图=map（编号指纹与 arb1_map_r0_1 相同）' % (len(raw), len(mine)))
print('  结局：25:36:16 祭司死亡 → 25:37:40 游戏失败，得分 411')

print()
print('【1】祭司时间线（移动令 / 感化目标令）')
print('  HumanMove 共 %d 条；转换目标令共 %d 条' % (len(priest_mv), len(priest_ac)))
print('  -- 感化目标令（全部）--')
for s, tgt, sn in priest_ac:
    print('     %5.2f 分  → %s %d' % (s / 60, tgt, sn))
print('  -- 祭司移动令：按目标点聚合 --')
grp = collections.OrderedDict()
for s, x, y in priest_mv:
    key = (round(x / BL, 1), round(y / BL, 1))
    grp.setdefault(key, []).append(s)
for (bx, by), ss in list(grp.items()):
    if len(ss) >= 3 or ss[-1] > 1400:
        print('     块(%.1f,%.1f)  %d 次  时段 %.2f~%.2f 分' % (bx, by, len(ss), ss[0] / 60, ss[-1] / 60))

print()
print('【2】祭司 24:30 之后每一步')
ev = [(s, 'MOVE', (round(x / BL, 1), round(y / BL, 1))) for s, x, y in priest_mv if s >= 1470]
ev += [(s, 'CONV', (f'{t} {n}',)) for s, t, n in priest_ac if s >= 1470]
ev += [(s, 'HIT', (f'{u} {n}',)) for s, u, n in atk_on_priest if s >= 1470]
ev.sort()
for s, k, v in ev:
    if s < 1470: continue
    tag = {'MOVE': '移动', 'CONV': '感化', 'HIT': '被攻击'}[k]
    print('   %5.2f 分  %-4s %s' % (s / 60, tag, v[0]))

print()
print('【3】我方兵力曲线（按 2 分钟窗口统计"下过令"的独立单位数）')
wins = collections.OrderedDict()
for s, u, sn, x, y in mv_mine:
    w = int(s // 120); wins.setdefault(w, {}).setdefault(sn, set()).add(u)
for s, u, sn, t, n in ac_mine:
    w = int(s // 120); wins.setdefault(w, {}).setdefault(sn, set()).add(u)
for w in sorted(wins):
    units = wins[w]
    kinds = collections.Counter()
    for sn, us in units.items():
        for u in us: kinds[u] += 1
    top = ', '.join('%s×%d' % (k, v) for k, v in kinds.most_common(6))
    print('   %4.0f~%4.0f 分  活跃单位 %3d ｜ %s' % (w * 2, w * 2 + 2, len(units), top))

print()
print('【4】我方损失时间线（HumanMove/HumanAction 过的编号中，后来的死亡）')
if die_mine:
    for s, u, sn in die_mine:
        print('   %5.2f 分  %s %d' % (s / 60, u, sn))
else:
    print('   0 条（我方编号集合与死亡行无交集 —— 说明我方主力全程无损）')
print('   全部死亡行 %d 条，其中死亡者的种类分布：' % len(die_all))
cc = collections.Counter(u for _, u, _ in die_all)
print('   ', ', '.join('%s×%d' % (k, v) for k, v in cc.most_common()))

print()
print('【5】祭司死亡前的攻击者（谁打死的）')
atk_on_priest.sort()
for s, u, sn in atk_on_priest:
    print('   %5.2f 分  %s %d' % (s / 60, u, sn))
print('   合共 %d 次被攻击，来自 %d 个不同单位' % (len(atk_on_priest), len({n for _, _, n in atk_on_priest})))

print()
print('【6】祭司最后 5 分钟与"敌区"关系')
late = [(s, x, y) for s, x, y in priest_mv if s >= 1380]
if late:
    print('   祭司最后移动令 %d 条；首末：' % len(late))
    s0 = late[0]; s1 = late[-1]
    print('     %.2f 分 块(%.1f,%.1f) → %.2f 分 块(%.1f,%.1f)' %
          (s0[0] / 60, s0[1] / BL, s0[2] / BL, s1[0] / 60, s1[1] / BL, s1[2] / BL))
    uniq = {(round(x / BL, 1), round(y / BL, 1)) for _, x, y in late}
    print('   不同落点 %d 个：%s' % (len(uniq), sorted(uniq)[:8]))
    print('   ⚠ 最后一条移动令 %.2f 分，距死亡 %.1f 秒 —— 期间 0 条移动令' %
          (s1[0] / 60, 1536.16 - s1[0]))
