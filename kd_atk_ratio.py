# -*- coding: utf-8 -*-
"""直接口径：每个 KIT-R 撤退窗口，其后 90 帧内同 SN 是否出现攻击令 ⇒ 窗口夹攻击令占比。"""
import re, glob, os, collections

RE_KIT = re.compile(r"\[KIT-R f=(\d+)\] SN=(\d+)")
RE_ATK = re.compile(r"设置攻击目标为")
WINDOW = 90

for p in ("gi", "kb", "kc", "kd"):
    fs = sorted(glob.glob(p + "*.jsonl"), key=lambda f: int(re.search(r"(\d+)", os.path.basename(f)).group(1)))
    tot = 0
    withatk = 0
    for f in fs:
        ait = f[:-6] + ".ait"
        if not os.path.exists(ait):
            continue
        kits = []
        atks = collections.defaultdict(list)
        for line in open(ait, encoding="utf-8", errors="replace"):
            pp = line.split(" | ", 3)
            if len(pp) < 4:
                continue
            try:
                fr = int(pp[1])
            except ValueError:
                continue
            m = RE_KIT.search(pp[3])
            if m:
                kits.append((fr, int(m.group(2))))
            elif RE_ATK.search(pp[3]):
                mm = re.search(r"[\u4e00-\u9fa5A-Za-z.]+ (\d+) 设置攻击目标为", pp[3])
                if mm:
                    atks[int(mm.group(1))].append(fr)
        for fr, sn in kits:
            tot += 1
            lst = atks.get(sn)
            if lst and any(fr < x <= fr + WINDOW for x in lst):
                withatk += 1
    if tot:
        print("%-4s 撤退窗口 %6d ｜ 其后90帧夹攻击令 %6d ｜ 占比 %5.1f%%" %
              (p, tot, withatk, 100.0 * withatk / tot))
