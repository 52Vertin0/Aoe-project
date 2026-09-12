# -*- coding: utf-8 -*-
"""祭司「移动令振荡率」量化（基线/修复都能跑 —— 只依赖引擎侧 HumanMove 日志）

判据：按时间序取祭司每一条 HumanMove 落点，算相对【祭司当前实际位置】的方位角；
相邻两条落点方位角差 > 120° 记一次「翻转」。振荡率 = 翻转次数 / 有效步数。
  • 健康推进：落点方位角稳定（都朝武器厂）⇒ 翻转率接近 0。
  • 两点往返极限环：(37,70)⇄(53,62) ⇒ 每隔一步就翻 ⇒ 翻转率 ≈ 50%。
用法: python _osc.py base0_map_r0_*.ait | python _osc.py fix1_map_r0_*.ait
"""
import re, sys, glob, math, collections

BL = 35.777


def analyze(path):
    # 祭司 SN
    txt = open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'产生了新的祭司\(编号:(\d+)\)', txt)
    if not m:
        return None
    psn = m.group(1)
    # 引擎侧的祭司位置（用 BEAT 的 pr@）与移动令
    beats = [(int(b), float(x), float(y)) for b, x, y in
             re.findall(r'\[BEAT f=\d+ b=(\d+)\].*?pr@=\(([\d.]+),([\d.]+)\)', txt)]
    mv = [(int(f), float(x) / BL, float(y) / BL) for f, x, y in
          re.findall(r'\|\s*(\d+)\s*\|.*?HumanMove:祭司 %s 移动至 \(([\d.]+),([\d.]+)\)' % psn, txt)]
    if len(mv) < 10:
        return dict(n=len(mv), flip=0, rate=0.0, per=[])
    # 用 BEAT 插值祭司位置（最近的桶）
    def posat(f):
        lo = None
        for b, x, y in beats:
            if b * 150 <= f:
                lo = (x, y)
            else:
                break
        return lo or (beats[0][1], beats[0][2])
    angs = []
    for f, x, y in mv:
        px, py = posat(f)
        dx, dy = x - px, y - py
        if dx * dx + dy * dy < 1.0:      # 落点≈原地（无方向信息）
            continue
        angs.append(math.atan2(dy, dx))
    flip = 0
    for i in range(1, len(angs)):
        d = abs(angs[i] - angs[i - 1])
        if d > math.pi:
            d = 2 * math.pi - d
        if d > math.radians(120):
            flip += 1
    return dict(n=len(angs), flip=flip, rate=(flip / max(1, len(angs) - 1)))


def main():
    files = []
    for a in sys.argv[1:]:
        files += sorted(glob.glob(a))
    agg = collections.defaultdict(list)
    print('%-30s %6s %6s %8s' % ('file', 'steps', 'flips', 'osc%'))
    for f in files:
        r = analyze(f)
        if not r:
            continue
        key = re.search(r'(map\d?)_r(\d+)_', f)
        key = key.group(1) if key else '?'
        agg[key].append(r['rate'])
        print('%-30s %6d %6d %7.0f%%' % (f.split('/')[-1], r['n'], r['flip'], 100 * r['rate']))
    print()
    print('%-8s %6s %8s %8s' % ('map', 'n', 'osc均值', 'osc最大'))
    for k in sorted(agg):
        v = agg[k]
        print('%-8s %6d %7.0f%% %7.0f%%' % (k, len(v), 100 * sum(v) / len(v), 100 * max(v)))


if __name__ == '__main__':
    main()
