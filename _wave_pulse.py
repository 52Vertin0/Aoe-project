# -*- coding: utf-8 -*-
"""提取敌方(脚本部队)行动脉冲帧，验证三波实际发动帧。

用法: python _wave_pulse.py p1 p2 ...   (不带参数则默认 p1..p24)
判据: flag=1 且 message 含 HumanAction/Move 的行 -> 敌方行动帧。
"""
import io, os, re, sys
from collections import Counter, defaultdict

PAT = re.compile(r'^\s*([\d:]+)\s*\|\s*(\d+)\s*\|\s*(\w+)\s*\|\s*(\d+)\s*\|\s*(.*?)\s*$')
ACT = ('HumanAction', 'Move', '移动至', '设置攻击目标', '转换目标', '设置工作目标')


def first_action_frame(fn):
    """返回 (该局敌方首条行动帧, 帧直方图 Counter, 前若干条明细)"""
    if not os.path.exists(fn):
        return None, None, []
    hist = Counter()
    detail = []
    first = None
    for line in io.open(fn, encoding='utf-8', errors='ignore'):
        m = PAT.match(line)
        if not m:
            continue
        frame = int(m.group(2))
        flag = m.group(4)
        msg = m.group(5)
        if flag != '1':
            continue
        if not any(k in msg for k in ACT):
            continue
        hist[frame] += 1
        if first is None:
            first = frame
        if len(detail) < 6:
            detail.append((frame, msg[:60]))
    return first, hist, detail


def cluster(firsts):
    """把各局首帧聚成 3 簇（±150 帧容差）"""
    out = []
    for f in sorted(x for x in firsts if x is not None):
        if out and f - out[-1][-1] <= 200:
            out[-1].append(f)
        else:
            out.append([f])
    return out


def main():
    tags = sys.argv[1:] or ['p%d' % i for i in range(1, 25)]
    rows = []
    all_hist = Counter()
    for t in tags:
        first, hist, det = first_action_frame(t + '.ait')
        rows.append((t, first, det))
        if hist:
            all_hist.update(hist)

    print('=== 逐局：敌方首条行动帧 ===')
    for t, first, det in rows:
        print('  %-6s first=%-7s | %s' % (t, first, det[0][1] if det else '-'))

    firsts = [r[1] for r in rows if r[1] is not None]
    if firsts:
        print('\n=== 首帧簇 ===')
        for c in cluster(firsts):
            print('  帧 %d~%d  共 %d 局' % (min(c), max(c), len(c)))

    # 三波窗口内的行动帧总量（第一波 6000 附近 / 第二波 13500 / 第三波 21000）
    print('\n=== 行动帧分布（每 500 帧一桶，仅显示帧 >= 4000）===')
    buckets = Counter()
    for f, n in all_hist.items():
        if f >= 4000:
            buckets[(f // 500) * 500] += n
    for b in sorted(buckets):
        print('  %6d~%6d : %d' % (b, b + 499, buckets[b]))

    # 5000~6100 之间有没有动作（判断 5000 是否也是真实发起点）
    for lo, hi, name in ((5000, 6000, '5000~5999'), (6000, 6100, '6000~6099')):
        n = sum(v for k, v in all_hist.items() if lo <= k < hi)
        print('\n  [%s] 敌方行动帧数 = %d' % (name, n))


if __name__ == '__main__':
    main()
