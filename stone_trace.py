# -*- coding: utf-8 -*-
"""石头账目追踪：把 ECO 行的 St 曲线 + 建塔时刻对齐，看"多采"发生在哪。
关键假设（用户的猜测）：停采判据没把【在建的箭塔】算进去。
本脚本用于验证：st = towersDone 触发停采时，St 落在多少。
"""
import os, re, glob

BASE = r"C:\new-aoe3.0.7g"
WIN = "VICTORY! Siege Workshop converted"

def analyze(tag):
    files = sorted(glob.glob(os.path.join(BASE, tag + "[0-9]*.ait")))
    print("=" * 92)
    print(f"批次 {tag}")
    print("=" * 92)
    for fp in files:
        raw = open(fp, "rb").read().decode("utf-8", "replace")
        lines = raw.splitlines()
        # ECO 行的 (frame, stone)
        curve = []
        for ln in lines:
            m = re.match(r"\s*(\d+):(\d+):(\d+)\s*\|\s*(\d+)\s*\|.*ECO \|.*?St:(\d+)", ln)
            if m:
                curve.append((int(m.group(4)), int(m.group(5))))
        # 建塔时刻（放置/完工）
        towerEvents = []
        for ln in lines:
            if "箭塔" in ln and ("建造完毕" in ln or "开始建造" in ln or "建造" in ln):
                m = re.match(r"\s*(\d+):(\d+):(\d+)\s*\|\s*(\d+)\s*\|", ln)
                if m:
                    towerEvents.append((int(m.group(4)), ln.split("|")[-1].strip()[:40]))
        end = curve[-1] if curve else (0, 0)
        peak = max(curve, key=lambda x: x[1]) if curve else (0, 0)
        win = WIN in raw
        print(f"  {os.path.basename(fp):<12} 末帧={end[0]:<6} 末St={end[1]:<5} "
              f"峰值St={peak[1]}(f={peak[0]}) 胜={int(win)}")
        # 打印 stoneStop 触发点：St 首次 >=300
        first300 = next((f for f, s in curve if s >= 300), None)
        if first300:
            print(f"      ★ 首次 St>=300 @ f={first300}")
        # 塔事件
        for f, txt in towerEvents[:6]:
            print(f"      塔@f={f:<7} {txt}")

for t in ["th", "sg", "hc4"]:
    analyze(t)
