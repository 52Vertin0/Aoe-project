# -*- coding: utf-8 -*-
"""o1 批（2026-09-26 现行版 6607 行 0e26e560）机制体检 —— 找优化方向用。

判胜口径（全项目一致）：
  胜 = jsonl 中【任一行】win==true（★必须扫全文件：引擎胜帧后会再写一帧 win:false）
  负 = AIText 含 "DEFEAT:"
  其余 = 未决
  恒等式自检：胜 + 负 + 未决 == 局数

SN 段约定（★ 关键，否则会把敌方预生成单位算成我方的产能）：
  敌方脚本部队 = 91000~91199（全 frame=0 预生成）
  我方军事     = 91300+（造兵 SN 递增）
  我方村民     = 41000+（41xxx）
"""
import io, json, os, re
from math import comb

TAGS = ['o1%02d' % i for i in range(1, 25)]
OUR_SPAWN = re.compile(r'产生了新的(.+?)\(编号:(\d+)\)')


def frame_of(line):
    p = line.split('|')
    if len(p) < 2:
        return 0
    try:
        return int(p[1].strip())
    except Exception:
        return 0


def judge(tag):
    jf, af = tag + '.jsonl', tag + '.ait'
    if not (os.path.exists(jf) and os.path.exists(af)):
        return None
    win, last_frame = False, 0
    for line in io.open(jf, encoding='utf-8', errors='ignore'):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        f = o.get('frame', 0)
        if f > last_frame:
            last_frame = f
        if o.get('win'):
            win = True
    defeat = victory_text = False
    for line in io.open(af, encoding='utf-8', errors='ignore'):
        if 'DEFEAT:' in line:
            defeat = True
        if 'VICTORY' in line:
            victory_text = True
    if win:
        return ('胜', last_frame, 'win:true' + ('+VICTORY' if victory_text else ''))
    if defeat:
        return ('负', last_frame, 'DEFEAT:')
    return ('未决', last_frame, '无终局标记')


def scan_ait(tag):
    """抽取一局的机制量。"""
    af = tag + '.ait'
    if not os.path.exists(af):
        return None
    lines = io.open(af, encoding='utf-8', errors='ignore').readlines()
    d = {
        'counter_frame': 0,          # ALL WAVES DEFEATED（进反攻期）
        'defeat_text': '',
        'spawn': {},                 # 我方产能（兵种 -> 帧列表）
        'enemy_spawn': 0,
        'priest_targets': [],        # (帧, 目标描述)
        'priest_convert': [],
        'guard_halt': 0,
        'snap_main': 0, 'snap_fallback': 0, 'snap_skip': 0,
        'towers_built': 0, 'farms_built': 0,
        'victory_frame': 0,
        'kit_no': 0, 'kit_s': 0,
    }
    for ln in lines:
        f = frame_of(ln)
        if 'ALL WAVES DEFEATED' in ln:
            d['counter_frame'] = f
        if 'VICTORY' in ln:
            d['victory_frame'] = f
        if 'DEFEAT:' in ln and not d['defeat_text']:
            d['defeat_text'] = ln.split('|')[-1].strip()[:60]
        if '[PRIEST GUARD] counterattack HALT' in ln:
            d['guard_halt'] += 1
        if '[KIT-NO' in ln:
            d['kit_no'] += 1
        if '[KIT-S' in ln:
            d['kit_s'] += 1
        m = OUR_SPAWN.search(ln)
        if m:
            kind, sn = m.group(1), int(m.group(2))
            if sn >= 91300:            # 我方军事单位
                d['spawn'].setdefault(kind, []).append(f)
            elif 91100 <= sn < 91200:  # 敌方预生成
                d['enemy_spawn'] += 1
            continue
        if 'Priest ADVANCE to' in ln or 'Priest converting' in ln:
            tgt = ln.split('|')[-1].strip()
            tgt = re.sub(r'f=\d+', 'f=N', tgt)
            tgt = re.sub(r'\d+\.\d+', 'N.N', tgt)
            tgt = re.sub(r'SN=\d+', 'SN=N', tgt)
            d['priest_targets'].append((f, tgt[:70]))
        m = re.search(r'main=(\d+) fallback=(\d+) skip=(\d+)', ln)
        if m:
            d['snap_main'] = int(m.group(1))
            d['snap_fallback'] = int(m.group(2))
            d['snap_skip'] = int(m.group(3))
    return d


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    dd = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - s) / dd * 100, (c + s) / dd * 100)


def fisher(a, b, c, d):
    n = a + b + c + d
    lo = max(0, a + b - (b + d))
    hi = min(a + b, a + c)

    def pr(x):
        return comb(a + c, x) * comb(b + d, a + b - x) / comb(n, a + b)

    obs = pr(a)
    return sum(pr(x) for x in range(lo, hi + 1) if pr(x) <= obs + 1e-12)


def main():
    print('=' * 78)
    print('o1 批 机制体检（现行版 6607 行 0e26e560，2026-09-26）')
    print('=' * 78)
    res, scans = {}, {}
    for t in TAGS:
        r = judge(t)
        if r is None:
            continue
        res[t] = r
        scans[t] = scan_ait(t)
    n = len(res)
    if n == 0:
        print('无数据')
        return
    w = sum(1 for r in res.values() if r[0] == '胜')
    l = sum(1 for r in res.values() if r[0] == '负')
    u = sum(1 for r in res.values() if r[0] == '未决')

    print('\n【1】逐局判决')
    for t in TAGS:
        if t not in res:
            continue
        r, s = res[t], scans[t]
        sp = s['spawn'] if s else {}
        nbow = len(sp.get('复合弓兵', []))
        narch = len(sp.get('弓箭手', []))
        print('  %-5s %-3s f=%-6d 反攻@%-6s 复合弓%-3d 弓箭手%-2d 护卫停%d %s'
              % (t, r[0], r[1], (s['counter_frame'] or '-'), nbow, narch,
                 s['guard_halt'], r[2]))

    print('\n【2】三率')
    print('  n=%d  胜=%d  负=%d  未决=%d   恒等式: %s'
          % (n, w, l, u, 'OK' if w + l + u == n else 'FAILED!'))
    lo, hi = wilson(w, n)
    print('  胜率 = %.1f%%  (95%% Wilson %.1f~%.1f)' % (w / n * 100, lo, hi))
    print('\n  与对照批 Fisher 双尾：')
    for name, (k, m) in {
        'p 批  (6000+P0)': (3, 24),
        'pp 批 (6000+P0+P2b)': (6, 24),
        'cur 批(6000)': (3, 12),
        'w1 批 (5000，本码前身)': (5, 19),
        '旧码系 gsk+kb+kb2 (5000)': (16, 36),
    }.items():
        print('    vs %-24s %d/%d (%5.1f%%)  p=%.4f'
              % (name, k, m, k / m * 100, fisher(w, n - w, k, m - k)))
    k0, m0 = 3 + 6 + 3 + 5, 24 + 24 + 12 + 19
    print('    ★ vs 新码全侧合并      %d/%d (%5.1f%%)  p=%.4f'
          % (k0, m0, k0 / m0 * 100, fisher(w, n - w, k0, m0 - k0)))
    # 败率 / 未决率（w1 批的教训：胜率无差异不代表机制无效）
    print('\n  败率 %.1f%%  未决率 %.1f%%' % (l / n * 100, u / n * 100))
    print('    vs p 批败率 19/24(79.2%%)  p=%.4f' % fisher(l, n - l, 19, 5))
    print('    vs w1批败率  8/19(42.1%%)  p=%.4f' % fisher(l, n - l, 8, 11))

    # ---- 漏斗 ----
    counter = sum(1 for t in res if scans[t] and scans[t]['counter_frame'] > 0)
    print('\n【3】漏斗')
    print('  ① 总局                %d' % n)
    print('  ② 进反攻期(ALL WAVES) %d  (%.1f%%)' % (counter, counter / n * 100))
    conv_issued = sum(1 for t in res if scans[t] and scans[t]['priest_targets'])
    print('  ③ 反攻期祭司有目标    %d  (%.1f%%)' % (conv_issued, conv_issued / n * 100))
    print('  ④ 胜                  %d  (③→④ = %.1f%%)'
          % (w, (w / conv_issued * 100) if conv_issued else 0))

    # ---- 产能 ----
    print('\n【4】我方产能（SN>=91300）')
    tot = {}
    for t in res:
        for k, v in (scans[t]['spawn'] if scans[t] else {}).items():
            tot[k] = tot.get(k, 0) + len(v)
    for k, v in sorted(tot.items(), key=lambda x: -x[1]):
        print('    %-10s %4d 个（每局均 %.1f）' % (k, v, v / n))
    print('    ★ 普通弓箭手 = %d（删除兜底后预期 0）' % tot.get('弓箭手', 0))
    # 复合弓兵首产帧分布（判断反攻期前是否空转）
    firsts = []
    for t in res:
        v = (scans[t]['spawn'] if scans[t] else {}).get('复合弓兵', [])
        if v:
            firsts.append(min(v))
    if firsts:
        firsts.sort()
        print('    复合弓兵首产帧：中位 %d  最小 %d  最大 %d  (n=%d)'
              % (firsts[len(firsts) // 2], firsts[0], firsts[-1], len(firsts)))
        early = sum(1 for f in firsts if f < 21000)
        print('    ⚠ 首产帧 < WAVE3(21000) 的局数 = %d/%d' % (early, len(firsts)))

    # ---- 祭司 ----
    print('\n【5】祭司')
    print('  护卫令 HALT 总数 %d（每局均 %.1f）'
          % (sum(scans[t]['guard_halt'] for t in res),
             sum(scans[t]['guard_halt'] for t in res) / n))
    last_tgt = {}
    for t in res:
        if scans[t]['priest_targets']:
            last_tgt[t] = scans[t]['priest_targets'][-1][1]
    freq = {}
    for t, s in last_tgt.items():
        key = re.sub(r'\s+', ' ', s)[:56]
        freq[key] = freq.get(key, 0) + 1
    for k, v in sorted(freq.items(), key=lambda x: -x[1])[:8]:
        print('    末条目标 x%-3d %s' % (v, k))
    # 胜负分组
    win_t, lose_t = {}, {}
    for t, s in last_tgt.items():
        d = win_t if res[t][0] == '胜' else lose_t
        key = re.sub(r'\s+', ' ', s)[:52]
        d[key] = d.get(key, 0) + 1
    print('    --- 胜局末条目标 ---')
    for k, v in sorted(win_t.items(), key=lambda x: -x[1])[:5]:
        print('      x%-3d %s' % (v, k))
    print('    --- 负局末条目标 ---')
    for k, v in sorted(lose_t.items(), key=lambda x: -x[1])[:6]:
        print('      x%-3d %s' % (v, k))
    # 死因
    causes = {}
    for t in res:
        if res[t][0] == '负':
            c = (scans[t]['defeat_text'] or '?')[:40]
            causes[c] = causes.get(c, 0) + 1
    print('    --- 负局死因 ---')
    for k, v in sorted(causes.items(), key=lambda x: -x[1]):
        print('      x%-3d %s' % (v, k))

    # ---- 快照机制 ----
    print('\n【6】快照机制（加固后不得退化）')
    bad = []
    for t in res:
        s = scans[t]
        if s['snap_fallback'] or s['snap_skip']:
            bad.append((t, s['snap_main'], s['snap_fallback'], s['snap_skip']))
    print('  main 总和 %d ｜ fallback≠0 或 skip≠0 的局：%d'
          % (sum(scans[t]['snap_main'] for t in res), len(bad)))
    for b in bad:
        print('    ⚠ %s main=%d fallback=%d skip=%d' % b)

    # ---- 拉扯 ----
    print('\n【7】拉扯诊断')
    print('  [KIT-S] 采样 %d ｜ [KIT-NO] 无目标 %d（每局均 %.1f / %.1f）'
          % (sum(scans[t]['kit_s'] for t in res), sum(scans[t]['kit_no'] for t in res),
             sum(scans[t]['kit_s'] for t in res) / n,
             sum(scans[t]['kit_no'] for t in res) / n))


if __name__ == '__main__':
    main()
