import re, sys, glob, os
from collections import defaultdict

LINE = re.compile(r'^\s*([\d:]+)\s*\|\s*(\d+)\s*\|\s*(\w+)\s*\|\s*(-?\d+)\s*\|\s*(.*)$')
KITR = re.compile(r'\[KIT-R f=(\d+)\] SN=(\d+) dK=([\d.]+) R=([\d.]+) stage=(\d+) stuck=(\d+) aged=(\d+) self=\((-?[\d.]+),(-?[\d.]+)\) tgt=\((-?[\d.]+),(-?[\d.]+)\)')
KITS = re.compile(r'\[KIT-S f=(\d+)\] SN=(\d+) phaseAged=(\d+) dK=([\d.]+) R=([\d.]+)')
MOVE = re.compile(r'HumanMove:(\S+) (\d+) 移动至 \((-?[\d.]+),(-?[\d.]+)\)')
# 我方单位位置采样: 引擎事件 "X(编号:NNNN)开始向Y攻击" 不含坐标; 用 HumanMove 落点代替

def load(f):
    kitr = defaultdict(list); kits = defaultdict(list); moves = defaultdict(list)
    for line in open(f, encoding='utf-8', errors='ignore'):
        m = LINE.match(line)
        if not m: continue
        fr = int(m.group(2)); flag = int(m.group(4)); msg = m.group(5); color = m.group(3)
        r = KITR.search(msg)
        if r:
            kitr[int(r.group(2))].append((int(r.group(1)), float(r.group(3)), int(r.group(5)), int(r.group(6)), int(r.group(7))))
            continue
        s = KITS.search(msg)
        if s:
            kits[int(s.group(2))].append((int(s.group(1)), float(s.group(4))))
            continue
        if color == 'green' and flag == 0:
            mm = MOVE.search(msg)
            if mm:
                moves[(mm.group(1), int(mm.group(2)))].append((int(mm.group(2)) and 0 or 0) or int(0) or 0)
    return kitr, kits, moves

def load2(f):
    kitr = defaultdict(list); kits = defaultdict(list); moves = defaultdict(list)
    for line in open(f, encoding='utf-8', errors='ignore'):
        m = LINE.match(line)
        if not m: continue
        fr = int(m.group(2)); flag = int(m.group(4)); msg = m.group(5); color = m.group(3)
        r = KITR.search(msg)
        if r:
            kitr[int(r.group(2))].append((int(r.group(1)), float(r.group(3)), int(r.group(5)), int(r.group(6)), int(r.group(7))))
        s = KITS.search(msg)
        if s:
            kits[int(s.group(2))].append((int(s.group(1)), float(s.group(4))))
        if color == 'green' and flag == 0:
            mm = MOVE.search(msg)
            if mm:
                moves[(mm.group(1), int(mm.group(2)))].append((int(m.group(2)), float(mm.group(3)), float(mm.group(4))))
    return kitr, kits, moves

def report(name, kitr, kits, moves, start=33000, trace=None):
    print(f'===== {name} (f>={start})')
    tot_r = sum(len(v) for v in kitr.values())
    print(f'  KIT-R 总 {tot_r} 条 / {len(kitr)} 弓兵; KIT-S 总 {sum(len(v) for v in kits.values())} 条')
    rows = []
    for sn, recs in kitr.items():
        recs = [r for r in recs if r[0] >= start]
        if not recs: continue
        dks = [r[1] for r in recs]
        eps = 1
        for i in range(1, len(recs)):
            if recs[i][0]-recs[i-1][0] > 90: eps += 1
        rows.append((sn, len(recs), eps, min(dks), max(dks), recs[0][0], recs[-1][0], max(r[3] for r in recs)))
    rows.sort(key=lambda r: -r[1])
    print(f'  {"SN":>7}{"KIT-R":>7}{"epi":>5}{"dKmin":>7}{"dKmax":>7}{"首帧":>8}{"末帧":>8}{"stuckMax":>9}')
    for r in rows[:8]:
        print(f'  {r[0]:>7}{r[1]:>7}{r[2]:>5}{r[3]:>7.1f}{r[4]:>7.1f}{r[5]:>8}{r[6]:>8}{r[7]:>9}')
    # 距离分布: 有多少条落在 p<2格 (被追上)
    near = sum(1 for v in kitr.values() for r in v if r[0] >= start and r[1] <= 2.0)
    print(f'  被追上(dK<=2.0)条数={near}  占 {100.0*near/max(1,tot_r):.0f}%')
    if trace:
        for sn in trace:
            print(f'  --- trace SN={sn}')
            for r in kitr.get(sn, []):
                if r[0] >= start: print(f'      f={r[0]} dK={r[1]:.1f} stage={r[2]} stuck={r[3]} aged={r[4]}')
    cat = {k: v for k, v in moves.items() if k[0] == '投石车'}
    for (t, sn), v in sorted(cat.items()):
        v = [x for x in v if x[0] >= start]
        if not v: continue
        gaps = sorted(v[i+1][0]-v[i][0] for i in range(len(v)-1))
        print(f'  投石车 SN={sn}: 移动令 {len(v)} 条 f={v[0][0]}~{v[-1][0]} 间隔中位={gaps[len(gaps)//2] if gaps else 0} 最大={max(gaps) if gaps else 0}')
    cab = {k: v for k, v in moves.items() if k[0] == '复合弓兵'}
    for (t, sn), v in sorted(cab.items())[:6]:
        v = [x for x in v if x[0] >= start]
        if v: print(f'  复合弓 SN={sn}: 移动令 {len(v)} 条')

if __name__ == '__main__':
    args = sys.argv[1:]
    trace = [int(x) for x in args if x.isdigit()]
    fs = [x for x in args if not x.isdigit()] or sorted(glob.glob('ln*.ait'))
    for f in fs:
        k, s, mv = load2(f)
        report(os.path.basename(f), k, s, mv, trace=trace or None)
