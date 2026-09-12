# -*- coding: utf-8 -*-
"""四处改动验证脚本
① 末段钉死（锚点退化）：[PRST-NOARMY] 是否出现 + 祭司末段是否恢复移动
② 反攻期农民被误判采集卡死：[STUCK] 中目标为敌建筑/敌单位（SN 11xxx/91xxx）的记录
③ 经济改派覆盖攻塔令：农民收到攻击令后 <=2 帧又被下发工作令的次数
④ 浆果每丛上限：[STUCK] 中"在采N人" >= 2 的记录（超派旁证）
用法: python _quadfix_verify.py <AIText.log> [<AIText2> ...]
"""
import re, sys, collections

FARMER_ATK_FRAME = 40500  # 27 分钟


def rows_of(p):
    out = []
    for ln in open(p, encoding='utf-8', errors='replace'):
        parts = ln.rstrip('\n').split(' | ')
        if len(parts) < 5:
            continue
        try:
            fr = int(parts[1])
        except ValueError:
            continue
        msg = ' | '.join(parts[4:]).strip()
        msg = re.sub(r'^UsrAI打印[：:]', '', msg)   # ⚠ 必剥前缀，否则 startswith 判据对 [STUCK]/[FARMER-ATK] 全失效
        out.append((fr, parts[3], msg))
    return out


def analyze(p):
    R = rows_of(p)
    print('=' * 74)
    print('日志:', p, ' 有效行:', len(R))
    if not R:
        return
    last = R[-1][0]
    print('末帧:', last)

    # ---------- ① 锚退化 ----------
    noarmy = [r for r in R if r[2].startswith('[PRST-NOARMY')]
    rear = [r for r in R if r[2].startswith('[PRST-REAR')]
    adv = [r for r in R if r[2].startswith('>> Priest ADVANCE')]
    conv = [r for r in R if 'converting Siege Workshop' in r[2]]
    moves = []
    for f, fl, m in R:
        mm = re.match(r'HumanMove:祭司 (\d+) 移动至 \(([-\d.]+),([-\d.]+)\)', m)
        if mm:
            moves.append((f, int(mm.group(1)), float(mm.group(2)), float(mm.group(3))))
    print('① [PRST-NOARMY]=%d  [PRST-REAR]=%d  ADVANCE=%d  converting=%d  祭司Move=%d'
          % (len(noarmy), len(rear), len(adv), len(conv), len(moves)))
    if moves:
        fmax = moves[-1][0]
        print('   祭司最后 Move f=%d（之后 %d 帧无移动令）' % (fmax, last - fmax))
        # ★ ①b 锚退化【真】判据：旧行为在 Mil=0 时会【每帧发同一个目标点】⇒ 不是"无 Move"而是"Move 到同一坐标"。
        #   （10-03 实机局铁证：f44849~44999 六次 Move 坐标全 = (3219.94,608.21)）
        best = (0, None, None, None)
        cur = 1; start = moves[0][0]; prev = (moves[0][2], moves[0][3])
        for i in range(1, len(moves)):
            c = (moves[i][2], moves[i][3])
            if c == prev:
                cur += 1
            else:
                if cur > best[0]: best = (cur, start, moves[i - 1][0], prev)
                cur = 1; start = moves[i][0]; prev = c
        if cur > best[0]: best = (cur, start, moves[-1][0], prev)
        print('   ①b 最长「连续同坐标 Move」段 = %d 次 (f=%s~%s 坐标=%s)' % (best[0], best[1], best[2],
              ('(%.0f,%.0f)' % best[3]) if best[3] else '?'))
        # 逐条列出 [PRST-NOARMY]（含坐标，验证真的在推进）
        for f, fl, m in noarmy[:6]:
            print('   NOARMY f=%d  %s' % (f, m[:96]))
        # 末段最后一次移动坐标 + 结束坐标
        print('   末 3 次 Move: %s' % [('%d:(%.0f,%.0f)' % (a, b, c)) for a, _, b, c in moves[-3:]])

    # ---------- ② 反攻期误判采集卡死 ----------
    stuck = [r for r in R if r[2].startswith('[STUCK')]
    stuck_late = [r for r in stuck if r[0] >= FARMER_ATK_FRAME]
    foe_stuck = [r for r in stuck_late
                 if re.search(r'目标SN=(11\d{3}|9[0-9]{4})', r[2])]
    print('② [STUCK] 总=%d  反攻期=%d  反攻期且目标为敌建筑/敌单位 SN=%d'
          % (len(stuck), len(stuck_late), len(foe_stuck)))
    for f, fl, m in foe_stuck[:8]:
        print('   ⚠ f=%d %s' % (f, m[:104]))

    # ---------- ③ 攻塔令被经济改派覆盖 ----------
    seq = collections.defaultdict(list)
    for f, fl, m in R:
        a = re.match(r'HumanAction:(\S+) (\d+) 设置攻击目标为 (\S+) (\d+)', m)
        if a:
            seq[int(a.group(2))].append((f, 'ATK', a.group(3), int(a.group(4))))
        b = re.match(r'HumanAction:(\S+) (\d+) 设置工作目标为 (\S+) (\d+)', m)
        if b and int(b.group(2)) >= 40000:   # 只关心村民
            seq[int(b.group(2))].append((f, 'WORK', b.group(3), int(b.group(4))))
    ov2 = ov90 = 0
    ovlist = []
    for sn, lst in seq.items():
        for i in range(len(lst) - 1):
            if lst[i][1] == 'ATK' and lst[i + 1][1] == 'WORK':
                gap = lst[i + 1][0] - lst[i][0]
                if gap <= 2:
                    ov2 += 1
                    ovlist.append((sn, lst[i][0], lst[i][2], lst[i + 1][2], gap))
                if gap <= 90:
                    ov90 += 1
    print('③ 攻击令后 <=2 帧被工作令覆盖=%d 次 | <=90 帧=%d 次' % (ov2, ov90))
    for sn, f, tg, w, g in ovlist[:8]:
        print('   ⚠ 村民%d f=%d 攻%s → %d帧后改%s' % (sn, f, tg, g, w))

    # ---------- ④ 浆果每丛上限 ----------
    onb = []
    for f, fl, m in stuck:
        mm = re.search(r'在采(\d+)人', m)
        if mm:
            onb.append((f, int(mm.group(1)), m))
    over = [x for x in onb if x[1] >= 3]
    print('④ [STUCK] 带"在采N人"=%d  其中 N>=3(超派) = %d' % (len(onb), len(over)))
    for f, n, m in over[:6]:
        print('   ⚠ f=%d 在采%d人  %s' % (f, n, m[:96]))

    # ---------- 胜负 ----------
    win = any('被祭司转换' in r[2] for r in R)
    print('★ 胜(武器厂被祭司转换)=%s' % win)


if __name__ == '__main__':
    for p in sys.argv[1:]:
        try:
            analyze(p)
        except Exception as e:
            print('!! %s 解析失败: %s' % (p, e))
