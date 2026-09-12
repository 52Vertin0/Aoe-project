# -*- coding: utf-8 -*-
"""kd 验收补：失败类型拆分 + 祭司死亡时段分布（回答"负局 9→12 从哪来"）。"""
import re, glob, os, collections

RE_WIN = re.compile(r"VICTORY! Siege Workshop converted")
RE_LP = re.compile(r"DEFEAT: Priest killed")
RE_LT = re.compile(r"DEFEAT: Town Center destroyed")
RE_PD = re.compile(r"祭司[（(]编号:?\d+[)）]\s*(?:死亡|阵亡)")

for p in ("gi", "kb", "kc", "kd"):
    fs = sorted(glob.glob(p + "*.jsonl"), key=lambda f: int(re.search(r"(\d+)", os.path.basename(f)).group(1)))
    w = lp = lt = to = 0
    pd_early = pd_late = 0
    for f in fs:
        ait = f[:-6] + ".ait"
        if not os.path.exists(ait):
            continue
        has_w = has_lp = has_lt = False
        pd_fr = None
        for line in open(ait, encoding="utf-8", errors="replace"):
            if RE_WIN.search(line):
                has_w = True
            if RE_LP.search(line):
                has_lp = True
            if RE_LT.search(line):
                has_lt = True
            m = RE_PD.search(line)
            if m and pd_fr is None:
                try:
                    pd_fr = int(line.split(" | ", 3)[1])
                except Exception:
                    pd_fr = -1
        if has_w:
            w += 1
        if has_lp:
            lp += 1
        if has_lt:
            lt += 1
        if not (has_w or has_lp or has_lt):
            to += 1
        if pd_fr is not None:
            if pd_fr <= 39000:
                pd_early += 1
            else:
                pd_late += 1
    print("%-4s 胜 %2d ｜ 祭司死 %2d ｜ TC毁 %2d ｜ 无结局 %2d   ‖ 祭司死时段: <=26分 %2d / >26分 %2d" %
          (p, w, lp, lt, to, pd_early, pd_late))
