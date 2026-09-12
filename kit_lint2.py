import re, sys, glob, os
from collections import defaultdict

LINE = re.compile(r'^\s*([\d:]+)\s*\|\s*(\d+)\s*\|\s*(\w+)\s*\|\s*(-?\d+)\s*\|\s*(.*)$')
KITR = re.compile(r'\[KIT-R f=(\d+)\] SN=(\d+) dK=([\d.]+) R=([\d.]+) stage=(\d+) stuck=(\d+) aged=(\d+)')
CMD  = re.compile(r'(HumanMove|HumanAction):(\S+) (\d+)(?: 移动至 \((-?[\d.]+),(-?[\d.]+)\)| 设置攻击目标为 (\S+) (\d+))')
DIE  = re.compile(r'(\S+)\(编号:(\d+)\)被摧毁')

def load(f):
    kitr = defaultdict(list)
    cmds = defaultdict(list)   # sn -> [(frame, kind, val/targetsn)]
    died = {}
    for line in open(f, encoding='utf-8', errors='ignore'):
        m = LINE.match(line)
        if not m: continue
        fr = int(m.group(2)); flag = int(m.group(4)); msg = m.group(5); color = m.group(3)
        r = KITR.search(msg)
        if r: kitr[int(r.group(2))].append((int(r.group(1)), float(r.group(3)), int(r.group(5)), int(r.group(6))))
        d = DIE.search(msg)
        if d: died[int(d.group(2))] = (fr, d.group(1))
        if color == 'green' and flag == 0:
            c = CMD.search(msg)
            if c:
                if c.group(1) == 'HumanMove':
                    cmds[int(c.group(3))].append((int(m.group(2)), 'M', (float(c.group(4)), float(c.group(5)))))
                else:
                    cmds[int(c.group(3))].append((int(m.group(2)), 'A', c.group(7)))
    return kitr, cmds, died

def analyze(f, kind_label, start=33000):
    kitr, cmds, died = load(f)
    print(f'===== {os.path.basename(f)} 反攻窗口 f>={start}')
    # ---- 复合弓 ----
    bow_sns = set(kitr.keys())
    n_move = n_atk = 0; caught = 0
    dead = [sn for sn in bow_sns if sn in died]
    for sn in bow_sns:
        for fr, k, v in cmds.get(sn, []):
            if fr < start: continue
            if k == 'M': n_move += 1
            else: n_atk += 1
    tot = sum(len([r for r in v if r[0] >= start]) for v in kitr.values())
    near = sum(1 for v in kitr.values() for r in v if r[0] >= start and r[1] <= 2.0)
    print(f'  复合弓: 参战 {len(bow_sns)} 个, 反攻窗口内 KIT-R={tot} 撤退令={n_move} 攻击令={n_atk} 被贴近(dK<=2)={near}({100.0*near/max(1,tot):.0f}%) 阵亡 {len(dead)}')
    if dead: print(f'    阵亡弓兵: {sorted(dead)[:12]}')
    # ---- 投石车 (仅我方指令) ----
    cats = {sn: [c for c in v if c[0] >= start] for sn, v in cmds.items() if any(k == 'A' for _, k, _ in v)}
    # 通过类型名过滤: 重扫比较麻烦 -> 用“指令里出现投石车”的特征在 load 里没存, 这里退回只看 SN 匹配
    return kitr, cmds, died

if __name__ == '__main__':
    for f in (sys.argv[1:] or ['ln1.ait', 'ln7.ait', 'lm5.ait']):
        analyze(f, '')
