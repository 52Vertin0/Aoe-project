# -*- coding: utf-8 -*-
"""石头账目精算：定位 stoneStop 首次=1 的时刻与当时 St，验证"多采 40"的来源。"""

import os, re, glob

BASE = r"C:\new-aoe3.0.7g"

def run(tag, limit=3):
    files = sorted(glob.glob(os.path.join(BASE, tag + "[0-9]*.ait")))[:limit]
    for fp in files:
        raw = open(fp, "rb").read().decode("utf-8", "replace")
        rows = []
        for ln in raw.splitlines():
            m = re.match(r"\s*(\d+):(\d+):(\d+)\s*\|\s*(\d+)\s*\|.*?ECO \| Fd:(\d+) Wd:(\d+) St:(\d+) Gd:(\d+) \|\| workers F(\d+) W(\d+) G(\d+) S(\d+) \|.*stoneStop:(\d+)", ln)
            if m:
                rows.append(dict(frame=int(m.group(4)), st=int(m.group(7)),
                                 sw=int(m.group(11)), stop=int(m.group(13))))
        # 塔完工时刻
        towers = []
        for ln in raw.splitlines():
            if "箭塔(编号" in ln and "建造完毕" in ln:
                mm = re.match(r"\s*(\d+):(\d+):(\d+)\s*\|\s*(\d+)\s*\|", ln)
                if mm:
                    towers.append(int(mm.group(4)))
        t1 = towers[0] if towers else None
        t2 = towers[1] if len(towers) > 1 else None
        # stoneStop 首次 =1
        firstStop = next((r for r in rows if r["stop"] == 1), None)
        # 峰值
        peak = max(rows, key=lambda r: r["st"])
        print(f"--- {os.path.basename(fp)}")
        print(f"    St 峰值 = {peak['st']} @ f={peak['frame']}")
        print(f"    第1座塔完工 @ f={t1}")
        print(f"    第2座塔完工 @ f={t2}")
        if firstStop:
            print(f"    stoneStop 首次=1 @ f={firstStop['frame']}  当时 St={firstStop['st']} 采石工 S={firstStop['sw']}")
        else:
            print("    stoneStop 从未=1（本局未触发）")

print("### 逐局石头账目 ###")
for t in ["th"]:
    run(t, 4)
print()
print("### 对照：sg ###")
for t in ["sg"]:
    run(t, 3)
