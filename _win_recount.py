# -*- coding: utf-8 -*-
"""批量重数胜负（判胜口径见下）。

用法:
  python _win_recount.py                      # 默认重数内置四批
  python _win_recount.py pp:24 "pp 批(P0+P2b)" cur:12 "cur 基线"

判胜口径（2026-09-24 二次修正，血泪版）:
  ★ 胜 = jsonl 中【存在任意一行】win==true（扫全文件，不能只看最后一行！）
    引擎在胜帧之后还会再写一帧 win==false，只看末行会漏判 —— pp10/pp13/pp21
    三局胜局就是这么被误判成 0 胜的。
    AIText 的 "VICTORY! Siege Workshop converted" 只作交叉验证：感化成功那帧
    游戏即结束，VICTORY 文本可能来不及落盘（cur6 实例）。
  ★ 负 = AIText 含 "DEFEAT:"。
  ★ 其余 = 打满 45000 帧未决。
  恒等式自检：胜 + 负 + 未决 == 该批实际局数。
"""
import json, io, glob, os, re, sys


def jsonl_win(tag):
    """返回 (首次/末次 win 帧, 末帧, 全文件是否有 win:true)"""
    fn = tag + '.jsonl'
    if not os.path.exists(fn):
        return None, None, False
    win_frames = []
    frames = []
    for line in io.open(fn, encoding='utf-8', errors='ignore'):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        frames.append(o.get('frame', 0))
        if o.get('win'):
            win_frames.append(o.get('frame'))
    return (win_frames[0] if win_frames else None), (frames[-1] if frames else None), bool(win_frames)


def ait_res(tag):
    fn = tag + '.ait'
    if not os.path.exists(fn):
        return None
    w = d = False
    last = 0
    for line in io.open(fn, encoding='utf-8', errors='ignore'):
        p = line.split(' | ', 3)
        if len(p) < 4:
            continue
        try:
            last = int(p[1])
        except ValueError:
            continue
        if 'VICTORY! Siege Workshop converted' in p[3]:
            w = True
        if re.search(r'DEFEAT: [A-Za-z ]+', p[3]):
            d = True
    return w, d, last


def report(prefix, n, label):
    print('=== %s (%d 局) ===' % (label, n))
    W = L = U = 0
    Aonly = []   # 只有 ait 报胜、jsonl 无
    Jonly = []   # 只有 jsonl 报胜、ait 无
    for i in range(1, n + 1):
        tag = '%s%d' % (prefix, i)
        if not os.path.exists(tag + '.ait'):
            continue
        jw, jf, jhas = jsonl_win(tag)
        a = ait_res(tag)
        aw, ad, alast = a
        if jhas or aw:
            res = '胜'; W += 1
        elif ad:
            res = '负'; L += 1
        else:
            res = '未决'; U += 1
        if jhas and not aw:
            Jonly.append((tag, jw, alast))
        if aw and not jhas:
            Aonly.append((tag, alast))
        print('  %-16s jsonl_win=%-7s ait_win=%-5s ait_last=%-7s => %s' %
              (tag, jw, aw, alast, res))
    tot = W + L + U
    print('  >>> 胜=%d 负=%d 未决=%d  n=%d  胜率=%.1f%%   [自检 胜+负+未决==n : %s]' %
          (W, L, U, tot, 100.0 * W / tot if tot else 0.0, 'OK' if tot == n else 'MISMATCH'))
    if Jonly:
        print('  ⚠ 仅 jsonl 报到胜（ait 无 VICTORY，胜帧即结束、文本未落盘）:', Jonly)
    if Aonly:
        print('  ⚠ 仅 ait 报到胜（jsonl 无 win:true，需人工复核）:', Aonly)
    print()
    return W, L, U


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        jobs = [('cur', 12, 'cur 批（09-23 现行版）'),
                ('pp', 24, 'pp 批（09-24 P0+P2b）'),
                ('vf_kb2_', 12, 'vf_kb2 批（09-22 末次完整批）'),
                ('vf_kb_', 12, 'vf_kb 批'),
                ('vf_gsk_', 12, 'vf_gsk 批')]
    else:
        # 形式: pre:n  ["可读标签"]  pre2:n2 ...
        jobs = []
        for a in args:
            if ':' in a:
                pre, n = a.split(':', 1)
                jobs.append([pre, int(n), pre])
            elif jobs:
                jobs[-1][2] = a          # 紧跟其后的无冒号参数 = 上一批的标签
            else:
                jobs.append([a, 12, a])
    for pre, n, lab in jobs:
        report(pre, n, lab)
