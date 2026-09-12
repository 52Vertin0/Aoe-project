# -*- coding: utf-8 -*-
"""稳健对拍：忽略「同帧内日志先后」与「帧号平移」，比较：
   ① 结局（末帧 / 胜负 / 祭司阵亡 / 发现 WS / 发起反攻）
   ② 逐条消息的出现次数分布（多重集）—— 差异条数 / 差异量
   ③ 每帧内容多集（帧号归一化后）
用法：python sz_replay_check.py
"""
import os, re, collections, statistics as st

OFF_RE = re.compile(r'\bf=(\d+)\b')


def load(path):
    """返回 [(frame, flag, msg)]，按文件顺序。"""
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        q = line.rstrip('\n').split('|')
        if len(q) < 5:
            continue
        fs = q[1].strip()
        if not fs.isdigit():
            continue
        out.append((int(fs), q[3].strip(), q[4]))
    return out


def counter(ev):
    c = collections.Counter()
    for fr, fl, m in ev:
        c[re.sub(r'\d+', '#', m)] += 1     # 数字归一化（帧号/SN 都变 #），只比"模板+次数"
    return c


def outcome(ev):
    end = ev[-1][0] if ev else 0
    win = any('VICTORY! Siege Workshop converted' in m for _, _, m in ev)
    pdead = any('DEFEAT: Priest killed' in m for _, _, m in ev)
    tcdead = any('DEFEAT: Town Center destroyed' in m for _, _, m in ev)
    ws = next((fr for fr, _, m in ev if 'Enemy Siege Workshop found' in m), 0)
    ca = next((fr for fr, _, m in ev if 'Force COUNTERATTACK' in m), 0)
    return end, win, pdead, tcdead, ws, ca


def main():
    print('=' * 104)
    print('shrink 轮 · 确定性重放对拍（忽略同帧内顺序 / 帧号平移）')
    print('=' * 104)
    print('%-8s %8s %8s %10s %10s %8s %10s %10s' %
          ('局', 'A末帧', 'B末帧', 'A胜/死TC', 'B胜/死TC', '差异类', 'A异量', 'B异量'))
    agg = []
    for i in range(1, 9):
        pa, pb = 'tc%d.ait' % i, 'sz%d.ait' % i
        if not (os.path.exists(pa) and os.path.exists(pb)):
            continue
        ea, eb = load(pa), load(pb)
        oa, ob = outcome(ea), outcome(eb)
        ca, cb = counter(ea), counter(eb)
        keys = set(ca) | set(cb)
        dif = [k for k in keys if ca[k] != cb[k]]
        da = sum(abs(ca[k] - cb[k]) for k in dif)
        db = sum(abs(ca[k] - cb[k]) for k in dif)
        agg.append((i, ea, eb, oa, ob, ca, cb, dif))
        print('%-8s %8d %8d %10s %10s %8d %10d %10d' %
              ('tc/sz%d' % i, oa[0], ob[0],
               ('%s/%s' % ('胜' if oa[1] else '-', 'TC死' if oa[3] else ('祭死' if oa[2] else '-'))),
               ('%s/%s' % ('胜' if ob[1] else '-', 'TC死' if ob[3] else ('祭死' if ob[2] else '-'))),
               len(dif), da, db))
    print('=' * 104)
    for i, ea, eb, oa, ob, ca, cb, dif in agg:
        if dif:
            print('\n【tc%d vs sz%d 差异模板 TOP 12】' % (i, i))
            dif.sort(key=lambda k: -(abs(ca[k] - cb[k])))
            for k in dif[:12]:
                print('  A=%-5d B=%-5d  %s' % (ca[k], cb[k], k[:110]))
        print('\n【tc%d 结局对照】A: 末帧=%d 胜=%s 祭死=%s TC死=%s 发现WS=%s 反攻=%s' %
              (i, oa[0], oa[1], oa[2], oa[3], oa[4], oa[5]))
        print('【tc%d 结局对照】B: 末帧=%d 胜=%s 祭死=%s TC死=%s 发现WS=%s 反攻=%s' %
              (i, ob[0], ob[1], ob[2], ob[3], ob[4], ob[5]))


if __name__ == '__main__':
    main()
