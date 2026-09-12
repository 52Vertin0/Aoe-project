# -*- coding: utf-8 -*-
"""解析 OJ debug 日志（debug_16577）：败因定位。
只读，不改任何源码/产物。"""
import re, sys, statistics, collections

F = r"C:\Users\ZhuanZ\Downloads\debug_16577_c25cac93-ef50-4273-82d3-9a852508e764.log"
lines = open(F, encoding="utf-8", errors="replace").read().splitlines()

# [BEAT f=.. b=..] st=.. Frm=.. Idle=.. Walk=.. Work=.. Atk=.. Mil=.. | Fd= Wd= St= Gd= | a= hop= arch= oth= pr=(..) | nEB= nEA= nMy= bbox=(..) pr@=(..) | ins= drop= adopt= objMv= gObj=.. | pm f.. ca.. h.. cnt.. o.. last=(..)
BEAT = re.compile(r"\[BEAT f=(\d+) b=(\d+)\]\s*st=(\S+)\s*Frm=(\d+)\s*Idle=(\d+)\s*Walk=(\d+)\s*Work=(\d+)\s*Atk=(\d+)\s*Mil=(\d+)"
                  r"\s*\|\s*Fd=(\d+)\s*Wd=(\d+)\s*St=(\d+)\s*Gd=(\d+)"
                  r"\s*\|\s*a=(\d+)\s*hop=(\d+)\s*arch=(\d+)\s*oth=(\d+)"
                  r"\s*pr=\(([^)]*)\)"
                  r"\s*\|\s*nEB=(\d+)\s*nEA=(\d+)\s*nMy=(\d+)"
                  r"\s*(?:bbox=\(([^)]*)\))?\s*pr@=\(([^)]*)\)"
                  r"\s*\|\s*ins=(\d+)\s*drop=(\d+)\s*adopt=(\d+)\s*objMv=(\d+)\s*gObj=(\S+)"
                  r"\s*\|\s*pm f(\d+)\s*ca(\d+)\s*h(\d+)\s*cnt(\d+)\s*o(\d+)\s*last=\(([^)]*)\)")

rows = []
for i, ln in enumerate(lines):
    m = BEAT.search(ln)
    if m:
        g = m.groups()
        rows.append(dict(
            ln=i + 1, f=int(g[0]), b=int(g[1]), st=g[2], Frm=int(g[3]),
            Idle=int(g[4]), Walk=int(g[5]), Work=int(g[6]), Atk=int(g[7]), Mil=int(g[8]),
            Fd=int(g[9]), Wd=int(g[10]), St=int(g[11]), Gd=int(g[12]),
            a=int(g[13]), hop=int(g[14]), arch=int(g[15]), oth=int(g[16]),
            pr=g[17], nEB=int(g[18]), nEA=int(g[19]), nMy=int(g[20]),
            bbox=g[21], pra=g[22],
            ins=int(g[23]), drop=int(g[24]), adopt=int(g[25]), objMv=int(g[26]), gObj=g[27],
            pm_f=int(g[28]), pm_ca=int(g[29]), pm_h=int(g[30]), pm_cnt=int(g[31]), pm_o=int(g[32]),
            last=g[33],
        ))

print("=" * 100)
print(f"BEAT 解析: {len(rows)} 条  (日志 {len(lines)} 行)")
print("=" * 100)
if not rows:
    sys.exit("no beat")

dead = [r for r in rows if r["pr"].startswith("sn-1")]
alive = [r for r in rows if not r["pr"].startswith("sn-1")]
print(f"祭司已死帧数={len(dead)}  存活帧数={len(alive)}")
if alive:
    print(f"祭司存活区间: f={alive[0]['f']} .. {alive[-1]['f']}   ({alive[0]['f']/1500:.2f} 分 .. {alive[-1]['f']/1500:.2f} 分)")
    print(f"祭司存活期最后一个 pr 字段: {alive[-1]['pr']}")
if dead:
    print(f"祭司死亡首帧: f={dead[0]['f']}  ({dead[0]['f']/1500:.2f} 分)")

print()
print("-" * 100)
print("时间轴（每 1500 帧 = 1 分，取每分钟内首条）")
print("-" * 100)
hdr = f"{'f':>6} {'分':>5} {'st':<6} {'Mil':>4} {'a':>3} {'hop':>4} {'arc':>4} {'oth':>4} {'Fd':>5} {'Wd':>4} {'St':>4} {'Gd':>4} " \
      f"{'nEB':>4} {'nEA':>4} {'nMy':>4} {'pra':>18} {'ins/dr/do/ob':>13} {'pm f/ca/h/cnt/o':>18} {'last':>16}"
print(hdr)
seen = set()
for r in rows:
    bucket = r["f"] // 1500
    if bucket in seen:
        continue
    seen.add(bucket)
    print(f"{r['f']:>6} {r['f']/1500:>5.2f} {r['st']:<6} {r['Mil']:>4} {r['a']:>3} {r['hop']:>4} {r['arch']:>4} {r['oth']:>4} "
          f"{r['Fd']:>5} {r['Wd']:>4} {r['St']:>4} {r['Gd']:>4} {r['nEB']:>4} {r['nEA']:>4} {r['nMy']:>4} {r['pra']:>18} "
          f"{str(r['ins'])+'/'+str(r['drop'])+'/'+str(r['adopt'])+'/'+str(r['objMv']):>13} "
          f"{str(r['pm_f'])+'/'+str(r['pm_ca'])+'/'+str(r['pm_h'])+'/'+str(r['pm_cnt'])+'/'+str(r['pm_o']):>18} {r['last']:>16}")

print()
print("-" * 100)
print("阶段统计")
print("-" * 100)
segs = [("W1 前", 0, 5000), ("W1~W2", 5000, 13500), ("W2~W3", 13500, 21000),
        ("W3~反攻", 21000, 33002), ("反攻后", 33002, 10 ** 9)]
for name, lo, hi in segs:
    s = [r for r in rows if lo <= r["f"] < hi]
    if not s:
        print(f"{name:<10} 无样本")
        continue
    print(f"{name:<10} n={len(s):<3} Mil 均={statistics.mean(x['Mil'] for x in s):5.1f} "
          f"max={max(x['Mil'] for x in s):<3} | a 均={statistics.mean(x['a'] for x in s):5.1f} | "
          f"hop 均={statistics.mean(x['hop'] for x in s):5.1f} arch 均={statistics.mean(x['arch'] for x in s):5.1f} | "
          f"pm f={sum(x['pm_f'] for x in s):<4} ca={sum(x['pm_ca'] for x in s):<4} h={sum(x['pm_h'] for x in s):<4} "
          f"cnt={sum(x['pm_cnt'] for x in s):<4} o={sum(x['pm_o'] for x in s):<4} | nEA 均={statistics.mean(x['nEA'] for x in s):5.1f}")

print()
print("-" * 100)
print("祭司存活期最后 30 条 BEAT（死前轨迹）")
print("-" * 100)
for r in alive[-30:]:
    print(f"f={r['f']:>6} ({r['f']/1500:>5.2f}分) {r['st']:<6} Mil={r['Mil']:>3} pr={r['pr']:<28} pr@=({r['pra']}) "
          f"pm={r['pm_f']}/{r['pm_ca']}/{r['pm_h']}/{r['pm_cnt']}/{r['pm_o']} last={r['last']} "
          f"nEA={r['nEA']} nEB={r['nEB']} ins={r['ins']} objMv={r['objMv']}")

print()
print("-" * 100)
print("资源曲线（Fd 食物 / Wd 木材 / St 石 / Gd 金）每分钟")
print("-" * 100)
for r in rows:
    if r["f"] % 1500 < 90:
        pass
seen = set()
for r in rows:
    b = r["f"] // 1500
    if b in seen:
        continue
    seen.add(b)
    print(f"  {r['f']/1500:>5.2f}分  Fd={r['Fd']:>5} Wd={r['Wd']:>5} St={r['St']:>5} Gd={r['Gd']:>5}  "
          f"Work={r['Work']:>3} Idle={r['Idle']:>3} Walk={r['Walk']:>3} Atk={r['Atk']:>3}")
