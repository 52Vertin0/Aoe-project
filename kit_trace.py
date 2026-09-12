# -*- coding: utf-8 -*-
"""
决定性取证：末dK极小的单位（91420/91422/91429）到底经历了什么。
  同时打印 KIT-R(tgt=撤退落点) 与 HumanMove(全部移动令落点) 的时序，
  看是否存在「撤退点 ←→ 推进点」交替 ⇒ 走了又回来（净位移=0）。
"""
import re, glob, collections

RE_KIT = re.compile(r"\[KIT-R f=(\d+)\] SN=(\d+) dK=([\d.]+).*?stage=(\d+) stuck=(\d+) aged=(\d+) self=\(([\d.-]+),([\d.-]+)\) tgt=\(([\d.-]+),([\d.-]+)\)")
RE_MOVE = re.compile(r"HumanMove:([\u4e00-\u9fa5A-Za-z.]+) (\d+) 移动至 \(([\d.]+),([\d.]+)\)")
RE_ATK = re.compile(r"HumanAction:([\u4e00-\u9fa5A-Za-z.]+) (\d+) 设置攻击目标为 ([\u4e00-\u9fa5A-Za-z.]+) (\d+)")
BL = 35.777

FILES = sorted(glob.glob("gi*.ait"), key=lambda f: int(re.search(r"(\d+)", f).group(1)))
TARGETS = [91420, 91422, 91429]

for f in FILES:
    ev = []
    for line in open(f, encoding="utf-8", errors="replace"):
        p = line.split(" | ", 3)
        if len(p) < 4:
            continue
        try:
            fr = int(p[1])
        except ValueError:
            continue
        body = p[3]
        m = RE_KIT.search(body)
        if m and int(m.group(2)) in TARGETS:
            ev.append((fr, int(m.group(2)), "KIT", int(m.group(4)), float(m.group(3)),
                       "self=(%.1f,%.1f) 落点=(%.1f,%.1f)" % (float(m.group(7)), float(m.group(8)),
                                                             float(m.group(9)), float(m.group(10)))))
            continue
        m = RE_MOVE.search(body)
        if m and int(m.group(2)) in TARGETS:
            ev.append((fr, int(m.group(2)), "MOVE", 0, 0.0,
                       "-> (%.1f,%.1f)" % (float(m.group(3)) / BL, float(m.group(4)) / BL)))
            continue
        m = RE_ATK.search(body)
        if m and int(m.group(2)) in TARGETS:
            ev.append((fr, int(m.group(2)), "ATK", 0, 0.0, "打 %s %s" % (m.group(3), m.group(4))))
    if not ev:
        continue
    ev.sort()
    print("=" * 96)
    print("文件 %s" % f)
    for sn in TARGETS:
        sub = [e for e in ev if e[1] == sn]
        if len(sub) < 8:
            continue
        print("  --- SN=%d (%d 条事件) ---" % (sn, len(sub)))
        # 取末段 40 条
        for fr, _, typ, st, dK, desc in sub[-34:]:
            extra = (" stage=%d dK=%.1f" % (st, dK)) if typ == "KIT" else ""
            print("     %-7d %-5s%s %s" % (fr, typ, extra, desc))
        break
    break
