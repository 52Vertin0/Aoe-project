# -*- coding: utf-8 -*-
"""
shrink_sr_compare.py —— 2026-09-20「代码精简」轮 A/B(/C) 双批对照

  A 臂 = t2_1..t2_8（精简前源码 045cab28/7000 行的二进制）
  B 臂 = sr_1..sr_8（精简后源码的二进制：注释压缩 + Tier B 去重 + 注释重排）
  C 臂 = srC_1..srC_8（★同 B 二进制重跑 —— 噪声标尺，缺它则任何"差异"都无法判读）

判读纪律（沿用项目既有）：
  · 计数型量一律【按时长归一化】（每万帧）——铁律 29
  · 只取【满时长局】(末帧 >= 44000) 做中位——早崩局资源天然偏低会伪造"退化"
  · 结局/胜率在 8 局下只作参考，永不作结论
  · 主判据 = 机制量：B−A 的差 是否大于 C−B 的差（同一二进制重跑）
"""
import io, re, sys, statistics as st

RE_CH = re.compile(r'TOWER-CHANCE f=(\d+)\] 累计兵帧=(\d+) 塔<=12格=(\d+)\(([\d.]+)%\) '
                   r'塔<=30格=(\d+)\(([\d.]+)%\)(?:.*Tier2偏置=(\d+))?')
RE_TOWER_DONE = re.compile(r'\|\s*(\d+)\s*\|\s*blue\s*\|\s*0\s*\|\s*箭塔\(编号[：:]\d+\)建造完毕')


def last_frame(lines):
    last = 0
    for raw in lines:
        q = raw.rstrip('\r\n').split(' | ')
        if len(q) >= 2:
            try:
                last = max(last, int(q[1]))
            except ValueError:
                pass
    return last


def probe(nm):
    try:
        lines = io.open(nm + '.ait', encoding='utf-8', errors='replace').readlines()
    except IOError:
        return None
    txt = ''.join(lines)
    lf = last_frame(lines)
    dur = max(1, lf - 33000)                    # 反攻期起点 = COUNTER_ATTACK_FORCE_TIME
    d = {'nm': nm, 'lf': lf, 'dur': dur}
    d['tgt'] = txt.count('[TOWER-TGT')
    d['app'] = txt.count('[TOWER-APPROACH')
    d['kitr'] = txt.count('[KIT-R')
    d['kit'] = txt.count('[KIT-')
    d['farmer'] = txt.count('[FARMER-ATK')
    d['priest'] = txt.count('[PRIEST')
    atk = len(re.findall(r'设置攻击目标为', txt))
    bld = len(re.findall(r'设置攻击目标为\s*(箭塔|农场|谷仓|房屋|仓库|武器厂|城镇中心|兵营|靶场|马厩)', txt))
    d['atk'], d['bld'] = atk, bld
    d['bldpct'] = 100.0 * bld / max(1, atk)
    d['tgt10k'] = 10000.0 * d['tgt'] / dur
    d['atk10k'] = 10000.0 * atk / dur
    m = None
    for m in RE_CH.finditer(txt):
        pass
    if m:
        d['c12'], d['c30'] = float(m.group(4)), float(m.group(6))
        d['bias'] = int(m.group(7)) if m.group(7) else 0
    else:
        d['c12'] = d['c30'] = float('nan'); d['bias'] = 0
    m2 = re.search(r'TOWER-TGT f=(\d+)', txt)
    d['first'] = int(m2.group(1)) if m2 else -1
    m3 = re.findall(r'(VICTORY!.*|DEFEATED!.*|DEFEAT:.*)', txt)
    d['end'] = (m3[-1][:26] if m3 else '(未结束/满时长)')
    d['win'] = bool(m3 and m3[-1].startswith('VICTORY'))
    d['towers'] = RE_TOWER_DONE.findall(txt)
    return d


def arm(label, names):
    rows = [r for r in (probe(n) for n in names) if r]
    print('=' * 104)
    print('### %s   n=%d' % (label, len(rows)))
    if not rows:
        print('   （无数据）'); return rows
    print('%-7s %7s %7s %7s %9s %7s %8s %8s %7s %7s %s' % (
        '局', '末帧', 'TGT', 'APP', 'TGT/万帧', 'KIT-R', '建筑令%', '12格%', '30格%', '偏置', '结局'))
    for r in rows:
        print('%-7s %7d %7d %7d %9.2f %7d %8.2f %8.1f %7.1f %7d %s' % (
            r['nm'], r['lf'], r['tgt'], r['app'], r['tgt10k'], r['kitr'],
            r['bldpct'], r['c12'], r['c30'], r['bias'], r['end']))
    full = [r for r in rows if r['lf'] >= 44000]
    med = lambda k, rs: (st.median([r[k] for r in rs]) if rs else float('nan'))
    print('  └ 满时长局 n=%d ｜ 末帧中位=%.0f  TGT中位=%.0f  TGT/万帧中位=%.2f  攻令/万帧中位=%.1f  '
          '建筑令%%中位=%.2f  12格%%中位=%.1f  30格%%中位=%.1f  KIT-R中位=%.0f  首令中位=%.0f' % (
              len(full), med('lf', rows), med('tgt', full), med('tgt10k', full), med('atk10k', full),
              med('bldpct', full), med('c12', full), med('c30', full), med('kitr', full),
              st.median([r['first'] for r in full if r['first'] > 0] or [0])))
    print('  └ APPROACH 合计=%-4d  Tier2偏置合计=%-4d  我方箭塔落成帧=%s  胜=%d/%d' % (
        sum(r['app'] for r in rows), sum(r['bias'] for r in rows),
        [r['towers'] for r in rows], sum(1 for r in rows if r['win']), len(rows)))
    return rows


def main():
    arms = []
    def names(pref, n=8):
        return ['%s%d' % (pref, i) for i in range(1, n + 1)]
    for label, pref in (('A 臂：精简前（t2，源码 7000 行）', 't2_'),
                        ('A′臂：精简前同源码重跑（t2b，噪声标尺）', 't2b_'),
                        ('B 臂：精简后（sr，源码 6462 行）', 'sr_'),
                        ('C 臂：同 B 二进制重跑（srC，噪声标尺）', 'srC_')):
        rows = arm(label, names(pref))
        if rows:
            arms.append((label[0], label, rows))
    if len(arms) < 2:
        return
    print('=' * 104)
    print('### 判读表（只取满时长局；中位）')
    keys = (('lf', '末帧'), ('tgt', '攻塔令数'), ('tgt10k', '攻塔令/万帧'), ('atk10k', '攻击令/万帧'),
            ('bldpct', '建筑令%'), ('c12', '塔≤12格%'), ('c30', '塔≤30格%'), ('kitr', 'KIT-R条数'),
            ('app', 'Tier2偏置次数'), ('first', '首攻塔令帧'))
    hdr = '%-16s' % '指标' + ''.join('%14s' % ('%s' % a[1][:6]) for a in arms)
    if len(arms) >= 2:
        hdr += '%14s%14s' % ('B−A', 'C−B' if len(arms) >= 3 else '-')
    print(hdr)
    for k, nm in keys:
        vals = []
        for _, _, rows in arms:
            full = [r for r in rows if r['lf'] >= 44000]
            if k == 'first':
                vals.append(st.median([r['first'] for r in full if r['first'] > 0] or [0]))
            else:
                vals.append(st.median([r[k] for r in full]) if full else float('nan'))
        line = '%-16s' % nm + ''.join('%14.2f' % v for v in vals)
        if len(vals) >= 2:
            line += '%14.2f' % (vals[1] - vals[0])
        if len(vals) >= 3:
            line += '%14.2f' % (vals[2] - vals[1])
        print(line)


main()
