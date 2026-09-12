# -*- coding: utf-8 -*-
"""
[BEAT] 逐帧行为心跳对拍器 —— 回答「OJ 上 AI 每帧的行为，和本地跑得差不多吗？」

用法：
    python _beat_diff.py <基线文件> <待比文件> [--label=A,B] [--max=40]

两个输入可以是：
  · 本地 AIText.log（beat_N.ait）
  · OJ 的 debug_<提交号>_*.log
两者都含 `UsrAI打印：[BEAT f=NNN b=MMM] ...` 行；本脚本剥掉 message 前缀后按**采样桶 b** 对齐。

-------------------------------------------------- 采样口径（为什么要 b）--------------------------------------------------
`[BEAT]` 的采样规则是「按 150 帧分桶，每桶首次进入时打一行」（见 UsrAI.cpp 的 BEAT_PERIOD）。
**不能按 f 对齐**，因为：
  ① AI 并非每帧都被调用 —— 实测 frame 会跳号（…300, 600, 750, 900…），
     所以 "frame % 150 == 0" 命中的是各局**不同的子集**（两次试着按 f 对齐，覆盖率只有 3.3% 和 48%）。
  ② 同一个桶内的采样帧在各局之间会差 1~2 帧（wall-clock 漂移）。
只有**桶号 b** 是两侧都精确相等的维度 —— 实测对齐率 100%。所以差异一律按 b 报。

判读门槛（先看【1】再看【5】）：
  · 【1】状态跃迁时间线 Δ —— ECO / W1 / W3 / ATK 若 Δ<50 帧，说明阶段机是确定性的、
    环境（地图/朝向/引擎版本/接线）没问题；此时若还输，败因就在**策略**里，不在环境里。
  · 【5】差异桶占比 —— ≤10% 属正常跑局抖动（同 exe 复跑胜负都会翻转，见记忆铁律）。
"""
import re, sys, os

# ------------------------------------------------------------------ 解析
BEAT_RE = re.compile(r'\[BEAT f=(\d+)(?:\s+b=(\d+))?\](.*)$')

NUM = r'(-?\d+)'
FNUM = r'(-?[\d.]+)'
PAYLOAD_RE = re.compile(
    r'st=(?P<st>[A-Z][A-Z0-9]*)(?P<stchg>\*)?\s+'
    r'Frm=' + NUM + r'\s+Idle=' + NUM + r'\s+Walk=' + NUM + r'\s+Work=' + NUM + r'\s+Atk=' + NUM + r'\s+Mil=' + NUM +
    r'\s*\|\s*Fd=' + NUM + r'\s+Wd=' + NUM + r'\s+St=' + NUM + r'\s+Gd=' + NUM +
    r'\s*\|\s*a=' + NUM + r'\s+hop=' + NUM + r'\s+arch=' + NUM + r'\s+oth=' + NUM +
    r'\s+pr=\(sn' + NUM + r'\s+st' + NUM + r'\s+hp' + NUM + r'/' + NUM + r'\s+ccd' + NUM + r'\)' +
    r'\s*\|\s*nEB=' + NUM + r'\s+nEA=' + NUM + r'\s+nMy=' + NUM +
    r'\s+bbox=\(x?' + FNUM + r'\.\.' + FNUM + r',y?' + FNUM + r'\.\.' + FNUM + r'\)'
    r'\s+pr@=\(' + FNUM + r',' + FNUM + r'\)' +
    r'\s*\|\s*ins=' + NUM + r'\s+drop=' + NUM + r'\s+adopt=' + NUM + r'\s+objMv=' + NUM + r'\s+gObj=' + NUM
)

KEYS = ['st', 'stchg', 'Frm', 'Idle', 'Walk', 'Work', 'Atk', 'Mil',
        'Fd', 'Wd', 'St', 'Gd', 'a', 'hop', 'arch', 'oth',
        'prSN', 'prSt', 'prHp', 'prMax', 'prCcd',
        'nEB', 'nEA', 'nMy', 'bminx', 'bminy', 'bmaxx', 'bmaxy', 'prDR', 'prUR',
        'ins', 'drop', 'adopt', 'objMv', 'gObj']
STR_KEYS = {'st'}
FLOAT_KEYS = {'bminx', 'bminy', 'bmaxx', 'bmaxy', 'prDR', 'prUR'}


def parse(path):
    """返回 (bucket -> fields, [(frame, state)...] 状态跃迁, 总行数, beat 行数)"""
    if not os.path.exists(path):
        return None, [], 0, 0
    raw = open(path, 'rb').read().decode('utf-8', 'replace')
    out, tl, nline, nbeat = {}, [], 0, 0
    for line in raw.splitlines():
        nline += 1
        m = BEAT_RE.search(line)
        if not m:
            continue
        nbeat += 1
        f = int(m.group(1))
        b = int(m.group(2)) if m.group(2) is not None else f // 150
        pm = PAYLOAD_RE.search(m.group(3).strip())
        if not pm:
            continue
        d = {}
        for k, v in zip(KEYS, pm.groups()):
            if k in STR_KEYS:
                d[k] = v
            elif k == 'stchg':
                d[k] = (v == '*')
            elif k in FLOAT_KEYS:
                try:
                    d[k] = float(v)
                except (TypeError, ValueError):
                    d[k] = None
            else:
                try:
                    d[k] = int(v)
                except (TypeError, ValueError):
                    d[k] = None
        d['f'] = f
        # 状态跃迁单独留档：它可能有**亚桶精度**（早期状态全落在桶 0，会被桶条目吞掉）
        if d.get('stchg'):
            tl.append((f, d['st']))
        prev = out.get(b)
        if prev is None or f < prev['f']:
            out[b] = d
    return out, tl, nline, nbeat


def fmt_tl(tl):
    out, prev = [], None
    for f, s in sorted(tl):
        if s != prev:
            out.append('%s@f%d(%.1f分)' % (s, f, f / 1500.0))
            prev = s
    return ' → '.join(out)


# ------------------------------------------------------------------ 主
def main():
    raw = sys.argv[1:]
    opts, args = {}, []
    for a in raw:
        if a.startswith('--'):
            k, _, v = a.partition('=')
            opts[k] = v
        else:
            args.append(a)
    if len(args) < 2:
        print(__doc__)
        return 1
    labels = opts.get('--label', 'A,B').split(',')
    labelA = labels[0] if len(labels) > 0 else 'A'
    labelB = labels[1] if len(labels) > 1 else 'B'
    maxrows = int(opts.get('--max', '40'))

    A, tlA, la, ba = parse(args[0])
    B, tlB, lb, bb = parse(args[1])
    if A is None or B is None:
        print('!! 文件不存在：', args[0] if A is None else args[1])
        return 2

    print('=' * 104)
    print('A(%s) = %s' % (labelA, args[0]))
    print('B(%s) = %s' % (labelB, args[1]))
    print('-' * 104)
    print('A: 总行 %d / [BEAT] 行 %d / 有效桶 %d' % (la, ba, len(A)))
    print('B: 总行 %d / [BEAT] 行 %d / 有效桶 %d' % (lb, bb, len(B)))
    if ba == 0 or bb == 0:
        print('\n>>> 结论：其中一侧**没有 [BEAT] 行** —— 该侧用的不是带插桩的版本，无法对拍。')
        print('    （OJ 侧出现 ⇒ 提交的是旧源码；本地侧 ⇒ exe 没重编）')
        return 3
    if not A or not B:
        print('\n!! 有 [BEAT] 行但一行都没解析成功 ⇒ 格式变了，先检查 PAYLOAD_RE。')
        for p in args:
            for line in open(p, 'rb').read().decode('utf-8', 'replace').splitlines():
                if '[BEAT f=' in line:
                    print('   样例行：', line[:400])
                    break
            break
        return 4

    # 1) 状态跃迁
    print('\n【1】状态跃迁时间线（最能区分"环境差"与"逻辑差"的单一指标）')
    print('  A: %s' % (fmt_tl(tlA) or '(无跃迁标记)'))
    print('  B: %s' % (fmt_tl(tlB) or '(无跃迁标记)'))
    fa = {s: f for f, s in sorted(tlA)}
    fb = {s: f for f, s in sorted(tlB)}
    for s in ('INIT', 'ECO', 'UPG', 'PREP', 'W1', 'W2', 'W3', 'ATK', 'WIN', 'LOSE'):
        if s in fa or s in fb:
            x, y = fa.get(s), fb.get(s)
            d = ('%+d' % (y - x)) if (x is not None and y is not None) else '—'
            print('    %-5s A=%-9s B=%-9s Δ=%-8s' %
                  (s, ('f%d' % x) if x is not None else '未出现',
                   ('f%d' % y) if y is not None else '未出现', d))

    # 2) 桶对齐
    common = sorted(set(A) & set(B))
    drift = sorted(abs(A[b]['f'] - B[b]['f']) for b in common)
    print('\n【2】采样桶对齐（按 b，不按 f）')
    print('  A 桶=%d  B 桶=%d  共同桶=%d（%.1f%% / %.1f%%）' %
          (len(A), len(B), len(common),
           100.0 * len(common) / max(1, len(A)), 100.0 * len(common) / max(1, len(B))))
    if drift:
        print('  桶内 frame 漂移：中位 %d，最大 %d 帧（%s）' %
              (drift[len(drift) // 2], drift[-1],
               '正常（AI 并非每帧都被调用）' if drift[-1] <= 40 else '★ 偏大，疑两侧非同一引擎'))
    if len(common) < 5:
        print('  !! 共同桶太少 ⇒ 两侧不是同一采样口径，先确认都用带 [BEAT b=] 的版本。')
        return 5

    # 3) 逐桶差异（默认只看**结构性**字段：村民数/军队数/兵种/敌情/指令提交）
    #    Idle/Walk/Work/Atk/nMy 是**逐帧抖动量**（引擎每帧随机打乱村民列表再派工），
    #    拿它们当判据会把"同环境"误判成"不同环境"（实测同机两局这几个字段差异占 80%+）。
    showAll = ('--all' in opts)
    KEYS_STRUCT = ('Frm', 'a', 'hop', 'arch', 'oth', 'Mil', 'nEB', 'nEA', 'ins', 'drop', 'adopt')
    KEYS_ALL = KEYS_STRUCT + ('Idle', 'Walk', 'Work', 'Atk', 'nMy')
    useKeys = KEYS_ALL if showAll else KEYS_STRUCT
    print('\n【3】共同桶上的差异（%s，按相对偏差降序，只列前 %d 条）'
          % ('全部字段（含抖动量）' if showAll else '仅结构性字段（已滤掉 Idle/Walk/Work/Atk/nMy 抖动量）', maxrows))
    rows = []
    for b in common:
        da, db = A[b], B[b]
        diffs = {}
        for k in useKeys:
            x, y = da.get(k), db.get(k)
            if x is None or y is None or x == y:
                continue
            diffs[k] = (x, y)
        if diffs:
            score = max(abs(x - y) / max(1, max(abs(x), abs(y))) for x, y in diffs.values())
            rows.append((score, b, diffs))
    rows.sort(reverse=True)
    if not rows:
        print('  共同桶上**没有任何差异** ⇒ 两侧行为在 [BEAT] 口径下完全一致。')
    for score, b, diffs in rows[:maxrows]:
        txt = '  '.join('%s %s→%s' % (k, diffs[k][0], diffs[k][1]) for k in diffs)
        print('  b=%-4d (fA=%-6d fB=%-6d %.1f分) 偏差%.0f%%  %s' %
              (b, A[b]['f'], B[b]['f'], A[b]['f'] / 1500.0, 100 * score, txt))

    # 4) 固定网格趋势
    print('\n【4】固定网格趋势（每 1500 帧≈1 分钟一行；— 表示该桶缺失）')
    hdr = ['b', 'stA', 'vA', 'aA', 'hopA', 'MilA', 'nEBA', '|', 'stB', 'vB', 'aB', 'hopB', 'MilB', 'nEBB']
    print('  ' + ' '.join('%-6s' % h for h in hdr))
    for g in range(0, 302, 10):
        ra, rb = A.get(g), B.get(g)

        def cell(r, k):
            return str(r[k]) if r and r.get(k) is not None else '—'
        print('  ' + ' '.join('%-6s' % c for c in [
            g, cell(ra, 'st'), cell(ra, 'Frm'), cell(ra, 'a'), cell(ra, 'hop'), cell(ra, 'Mil'), cell(ra, 'nEB'),
            '|',
            cell(rb, 'st'), cell(rb, 'Frm'), cell(rb, 'a'), cell(rb, 'hop'), cell(rb, 'Mil'), cell(rb, 'nEB')]))

    # 5) 结论
    nz = len(rows)
    print('\n【5】机器判据')
    print('  共同桶 %d 个，其中结构性字段有差异 %d 个（%.1f%%）' % (len(common), nz, 100.0 * nz / len(common)))
    print('  ⚠ **噪声底线（实测）**：同机同二进制跑两局 —— 结构性差异 前 9 分钟 23%%、全程 76%%。')
    print('    所以"差异率高"本身**不构成**环境不同的证据；后期战场随机性极大。判据取下面两条：')
    # 5a 确定性阶段的时间戳是否对得上（最强的单一判据）
    DET = ('INIT', 'ECO', 'W1', 'W3', 'ATK')
    detMax, detTxt = 0, []
    for s in DET:
        x, y = fa.get(s), fb.get(s)
        if x is None or y is None:
            detTxt.append('%s=缺' % s)
            continue
        dd = abs(y - x)
        detMax = max(detMax, dd)
        detTxt.append('%sΔ%+d' % (s, y - x))
    print('  (a) 确定性阶段时间戳：%s  ⇒ 最大偏差 %d 帧' % (' '.join(detTxt), detMax))
    # 5b 前半程结构性差异率
    early = [b for b in common if b <= 90]
    eSet = set(b for _, b, _ in rows)
    earlyBad = sum(1 for b in early if b in eSet)
    er = (100.0 * earlyBad / len(early)) if early else 0.0
    print('  (b) 前半程 b≤90（前 9 分钟）结构性差异桶：%d/%d = %.1f%%（噪声底线 ≈23%%）'
          % (earlyBad, len(early), er))
    if common:
        half = max(common) // 2
        e2 = sum(1 for b in eSet if b <= half)
        print('  (c) 分段：前半程 %d 个差异桶 / 后半程 %d 个（噪声底线 113/150）' % (e2, nz - e2))

    if detMax <= 20 and er <= 35.0:
        print('  >>> 结论：**环境同源**。阶段机时间戳几乎逐帧吻合、前半程结构性差异在噪声范围内 ⇒')
        print('      OJ 与本地是同一套地图/朝向/引擎接线；若还输，败因在**策略**里，不在环境里。')
    elif detMax <= 60 and er <= 50.0:
        print('  >>> 结论：**基本同源，但有偏移** ⇒ 盯住【1】里 Δ 大的那个阶段，与【3】前段偏差最大的量。')
    else:
        print('  >>> 结论：**可疑**。阶段机时间戳或前半程行为对不上 ⇒ 先核对地图/朝向（`-map`/`-rotate`）、')
        print('      引擎版本（[OJ-ENV] 的 engine=）、以及是否真用了带插桩的提交件。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
