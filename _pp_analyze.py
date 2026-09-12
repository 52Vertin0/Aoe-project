# -*- coding: utf-8 -*-
"""pp 批（P0+P2b）综合验证脚本。
1) 胜负（jsonl.win 为准，AIText 交叉验证）
2) 逐局：祭司最后一条感化令目标 + 起手帧 + 死亡帧 + 间隔
3) 反攻期(帧>33000) 感化目标兵种分布（与 cur 批对照）
4) 箭塔目标切换：每座塔的目标 SN 序列（>1 个不同目标 ⇒ 发生过切换）
5) P2b 因果链：敌方单位"设置攻击目标为 箭塔 T"的次数（仇恨被拉上塔）
"""
import json, io, glob, os, re, sys, collections
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PRIEST = '91166'
COUNTER_FRAME = 33000

ARMY_KINDS = ['攻城武器厂', '战车弓兵', '复合弓兵', '方阵兵', '投石车', '斧头兵', '刀斧兵',
              '棍棒兵', '弓兵', '投石兵', '骑兵', '村民', '箭塔']
MELEE_KINDS = {'刀斧兵', '斧头兵', '棍棒兵', '阔剑兵', '方阵兵', '长枪兵'}

def kind_of(txt):
    for k in ARMY_KINDS:
        if k in txt:
            return k
    return txt.strip()[:8]

def load(tag):
    fn = tag + '.ait'
    if not os.path.exists(fn):
        return None
    return io.open(fn, encoding='utf-8', errors='ignore').read().split('\n')

def jsonl_win(tag):
    fn = tag + '.jsonl'
    if not os.path.exists(fn):
        return None, None
    lastwin, lastframe = None, None
    for line in io.open(fn, encoding='utf-8', errors='ignore'):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        lastframe = o.get('frame', lastframe)
        if o.get('win'):
            lastwin = o.get('frame')
    return lastwin, lastframe

def fr_of(ln):
    m = re.search(r'\|\s*(\d+)\s*\|', ln)
    return int(m.group(1)) if m else None

def scan(tag):
    ls = load(tag)
    if ls is None:
        return None
    d = {'lines': ls}
    # 结局
    jw, jf = jsonl_win(tag)
    txt = '\n'.join(ls)
    d['jsonl_win'] = jw
    d['ait_victory'] = 'VICTORY! Siege Workshop converted' in txt
    d['ait_defeat'] = bool(re.search(r'DEFEAT: [A-Za-z ]+', txt))
    d['lastframe'] = jf
    # 最后一条感化令
    d['last_conv'] = d['last_conv_fr'] = None
    d['counter_conv_kinds'] = collections.Counter()
    d['conv_pick'] = collections.Counter()
    for ln in ls:
        if '设置转换目标为' in ln:
            fr = fr_of(ln)
            tgt = ln.split('设置转换目标为', 1)[1].strip()
            d['last_conv'], d['last_conv_fr'] = tgt, fr
            if fr and fr > COUNTER_FRAME:
                d['counter_conv_kinds'][kind_of(tgt)] += 1
        if 'pick=' in ln:
            m = re.search(r'pick=(-?\d+)', ln)
            if m:
                d['conv_pick'][m.group(1)] += 1
    # 祭司死亡帧
    d['death_fr'] = None
    for ln in ls:
        if re.search(r'祭司\(编号[:：]?\s*' + PRIEST + r'\)死亡', ln):
            d['death_fr'] = fr_of(ln)
            break
    # P2b：每座塔的目标集合 + 敌方目标为塔的次数
    # ★ 口径关键：AIText 的"HumanAction:X 设置攻击目标为 Y"第 4 字段 = 来源阵营(0=我/1=敌)。
    #   敌方建筑编号同样是 11xxx 段（每局独立分配）⇒ 不按 flag 过滤会把敌方箭塔混进来，验证全错。
    #   P2b 只看 flag=0（本 AI 下发的塔令）；"敌方→祭司"因祭司 SN 唯一(91166)天然可靠，无需过滤。
    d['tower_targets'] = collections.defaultdict(list)   # 我方塔SN → [(frame, 目标kind, 目标SN)]
    d['tower_issue'] = [0, 0]       # [防御期, 反攻期] 我方对塔下发攻击令的次数
    d['tower_short_gap'] = 0        # ★ P2b 判据：同塔相邻两条令间隔 <20 帧的次数（旧代码 Project!=-1 就 skip ⇒ 应≈0）
    d['tower_min_gap'] = None       # 同塔相邻令的最小帧间隔（旧代码应 ≈ 塔攻击周期 52 帧）
    d['enemy_to_priest'] = [0, 0]
    d['priest_atk_by'] = collections.Counter()   # 敌方哪些兵种把目标设为祭司
    d['melee_to_priest'] = [0, 0]                # 其中近战兵（P2b 应把它们拉去塔）
    d['enemy_to_tower'] = [0, 0]    # 仅作参考（无法分辨塔的阵营，不可单独作判据）
    for ln in ls:
        fr = fr_of(ln)
        seg = 0 if (fr is None or fr <= COUNTER_FRAME) else 1
        parts = ln.split('|')
        flag = parts[3].strip() if len(parts) >= 4 else '?'
        m = re.search(r'HumanAction:箭塔\s+(\d+)\s+设置攻击目标为\s+(\S+)\s+(\d+)', ln)
        if m and flag == '0':
            d['tower_targets'][int(m.group(1))].append((fr, m.group(2), int(m.group(3))))
            d['tower_issue'][seg] += 1
        if re.search(r'设置攻击目标为\s+箭塔\s+\d+', ln):
            d['enemy_to_tower'][seg] += 1
        mp = re.search(r'HumanAction:(\S+?)\s+\d+\s+设置攻击目标为\s+祭司\s+' + PRIEST, ln)
        if mp:
            nm = mp.group(1)
            d['enemy_to_priest'][seg] += 1
            d['priest_atk_by'][nm] += 1
            if nm in MELEE_KINDS:
                d['melee_to_priest'][seg] += 1
    for t, seq in d['tower_targets'].items():
        seq.sort()
        for a, b in zip(seq, seq[1:]):
            gap = b[0] - a[0]
            if gap < 20:      # 同塔相邻两条令间隔 <20 帧 ⇒ 只可能是"Project!=-1 时的主动纠偏"
                d['tower_short_gap'] += 1
            if d['tower_min_gap'] is None or gap < d['tower_min_gap']:
                d['tower_min_gap'] = gap
    return d

def main(prefix, n, label):
    print('=' * 96)
    print('=== %s (%d 局) ===' % (label, n))
    print('=' * 96)
    W = L = U = 0
    rows = []
    for i in range(1, n + 1):
        tag = '%s%d' % (prefix, i)
        d = scan(tag)
        if d is None:
            continue
        if d['jsonl_win'] is not None:
            res = '胜'; W += 1
        elif d['ait_defeat']:
            res = '负'; L += 1
        else:
            res = '未决'; U += 1
        print('%-7s %-5s lastframe=%-7s 祭司亡帧=%-7s 最后感化=%-10s 起手帧=%-7s 反攻期感化档=%s' % (
            tag, res, d['lastframe'], d['death_fr'] or '-',
            kind_of(d['last_conv']) if d['last_conv'] else '(无)',
            d['last_conv_fr'] or '-',
            dict(d['counter_conv_kinds']) or '{}'))
        # ★ P2b 判据：我方(flag=0)塔令的目标序列 + 短间隔换目标次数
        print('        我方塔令: %s | 换过目标的塔=%s | 短间隔(<20f)换目标=%d' % (
            {t: len(v) for t, v in d['tower_targets'].items()} or '{}',
            {t: len({x[2] for x in v}) for t, v in d['tower_targets'].items() if len({x[2] for x in v}) > 1} or '无',
            d['tower_short_gap']))
        print('        (参考) 敌方→祭司(D/A)=%d/%d 其中近战=%d/%d | 敌方兵种=%s' % (
            d['enemy_to_priest'][0], d['enemy_to_priest'][1],
            d['melee_to_priest'][0], d['melee_to_priest'][1],
            dict(d['priest_atk_by'])))
        rows.append((tag, res, d))
    tot = W + L + U
    print('-' * 96)
    print('>>> 胜=%d 负=%d 未决=%d  n=%d  胜率=%.1f%%' % (W, L, U, tot, 100.0 * W / tot if tot else 0))
    # 汇总：反攻期感化目标分布
    agg = collections.Counter()
    for _, _, d in rows:
        agg.update(d['counter_conv_kinds'])
    print('>>> 反攻期(>33000)感化目标兵种合计:', dict(agg))
    # ★ P0 核心判据：反攻期感化目标里"远程兵"的占比（战车弓兵/复合弓兵/弓兵/投石兵）
    RANGED = ('战车弓兵', '复合弓兵', '弓兵', '投石兵')
    ranged_n = sum(v for k, v in agg.items() if k in RANGED)
    total_n = sum(agg.values())
    print('>>> ★ 反攻期感化目标中【远程兵】= %d / %d (%.1f%%)  ← P0 应把这里压到 0' % (
        ranged_n, total_n, 100.0 * ranged_n / total_n if total_n else 0))
    picks = collections.Counter()
    for _, _, d in rows:
        picks.update(d['conv_pick'])
    print('>>> Priest CONVERT 日志 pick 分布:', dict(picks))
    # ★ P2b 判据合计
    et = [0, 0]; ep = [0, 0]; ti = [0, 0]; sg = 0; tgt_sets = collections.Counter()
    for _, _, d in rows:
        for k in range(2):
            et[k] += d['enemy_to_tower'][k]; ep[k] += d['enemy_to_priest'][k]; ti[k] += d['tower_issue'][k]
        sg += d['tower_short_gap']
        for t, v in d['tower_targets'].items():
            tgt_sets[len({x[2] for x in v})] += 1
    mg = [d['tower_min_gap'] for _, _, d in rows if d['tower_min_gap'] is not None]
    print('>>> ★ P2b：我方塔令 = %d 条（防御期 %d / 反攻期 %d）｜ 同塔目标数分布 = %s' % (
        ti[0] + ti[1], ti[0], ti[1], dict(sorted(tgt_sets.items()))))
    print('>>> ★ P2b：短间隔(<20f)换目标 = %d ｜ 各局最小相邻间隔 = %s' % (sg, mg))
    mpa = [0, 0]
    for _, _, d in rows:
        for k in range(2):
            mpa[k] += d['melee_to_priest'][k]
    print('>>> ★ P2b：敌方→祭司 = %d/%d（近战 %d/%d ← 应被塔拉走而下降）' % (
        ep[0], ep[1], mpa[0], mpa[1]))
    # 死亡帧分布
    deaths = sorted(d['death_fr'] for _, _, d in rows if d['death_fr'])
    if deaths:
        print('>>> 祭司死亡帧: n=%d min=%d max=%d 极差=%d' % (len(deaths), deaths[0], deaths[-1], deaths[-1] - deaths[0]))
    return W, L, U

if __name__ == '__main__':
    pre = sys.argv[1] if len(sys.argv) > 1 else 'pp'
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    lab = sys.argv[3] if len(sys.argv) > 3 else 'pp 批（P0+P2b）'
    main(pre, n, lab)
