# -*- coding: utf-8 -*-
"""w1 批（WAVE1_TIME=5000 单行对照臂）胜负统计 + 与对照批的 Fisher 精确检验。

判胜口径（与全项目一致）：
  ★ 胜 = jsonl 中【任一行】win==true（必须扫全文件：引擎在胜帧后会再写一帧 win:false）
  ★ 负 = AIText 含 "DEFEAT:"
  ★ 其余 = 打满 45000 帧未决
  恒等式自检：胜 + 负 + 未决 == 实际局数
"""
import io, json, os, sys
from math import comb

TAGS = ['w1%02d' % i for i in range(1, 20)]   # w101..w119（w120 为被中断的半局，不计）


def judge(tag):
    jf, af = tag + '.jsonl', tag + '.ait'
    if not (os.path.exists(jf) and os.path.exists(af)):
        return None
    win = False
    last_frame = 0
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
        return ('胜', last_frame, 'jsonl win:true' + (' +VICTORY' if victory_text else ''))
    if defeat:
        return ('负', last_frame, 'AIText DEFEAT:')
    return ('未决', last_frame, '打满/无终局标记')


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - s) / d * 100, (c + s) / d * 100)


def fisher(a, b, c, d):
    """2x2 精确检验（双尾），表 = [[a,b],[c,d]]。"""
    n = a + b + c + d
    lo = max(0, a + b - (b + d))
    hi = min(a + b, a + c)

    def p(x):
        return comb(a + c, x) * comb(b + d, a + b - x) / comb(n, a + b)

    obs = p(a)
    return sum(p(x) for x in range(lo, hi + 1) if p(x) <= obs + 1e-12)


def main():
    print('=== w1 批逐局判决（WAVE1_TIME = 5000）===')
    res = {}
    for t in TAGS:
        r = judge(t)
        if r is None:
            print('  %-6s 缺文件' % t)
            continue
        res[t] = r
        print('  %-6s %-3s last=%-6d %s' % (t, r[0], r[1], r[2]))

    n = len(res)
    w = sum(1 for r in res.values() if r[0] == '胜')
    l = sum(1 for r in res.values() if r[0] == '负')
    u = sum(1 for r in res.values() if r[0] == '未决')
    print('\n=== 汇总 ===')
    print('  n=%d  胜=%d  负=%d  未决=%d   恒等式自检: %s'
          % (n, w, l, u, 'OK' if w + l + u == n else 'FAILED!'))
    lo, hi = wilson(w, n)
    print('  胜率 = %.1f%%  (95%% Wilson CI %.1f~%.1f)' % (w / n * 100, lo, hi))

    print('\n=== 与对照批的 Fisher 精确检验（双尾）===')
    arms = {
        'p 批 (WAVE1=6000 +P0, 09-24)': (3, 24),
        'pp 批(WAVE1=6000 +P0+P2b)': (6, 24),
        'cur 批(WAVE1=6000, 09-24)': (3, 12),
        '旧码系 gsk+kb+kb2 (WAVE1=5000)': (16, 36),
    }
    for name, (k, m) in arms.items():
        p = fisher(w, n - w, k, m - k)
        print('  w1 %d/%d (%.1f%%)  vs  %-34s %d/%d (%.1f%%)   p = %.4f'
              % (w, n, w / n * 100, name, k, m, k / m * 100, p))

    # WAVE1 单变量净效果：w1 批 vs w 前所有 6000 批合并
    k0, m0 = 3 + 6 + 3, 24 + 24 + 12
    p = fisher(w, n - w, k0, m0 - k0)
    print('\n  ★ 合并对照（所有 WAVE1=6000 批）: %d/%d (%.1f%%)   p = %.4f'
          % (k0, m0, k0 / m0 * 100, p))

    # 漏斗：进反攻期（末帧 >= 33000）比例
    deep = sum(1 for r in res.values() if r[1] >= 33000)
    print('\n  ★ 进反攻期(末帧>=33000) = %d/%d = %.1f%%' % (deep, n, deep / n * 100))


if __name__ == '__main__':
    main()
