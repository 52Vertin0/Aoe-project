# -*- coding: utf-8 -*-
"""解析 OJ debug_19104（胜利局）。日志格式：`MM:SS:CC 内容`，无 frame 列、无 UsrAI 打印。"""
import re, sys, collections, statistics

F = r"C:\Users\ZhuanZ\Downloads\debug_19104_0a4c2d71-7b3a-4248-aed1-9fed91df5f90.log"
BL = 35.777

T = re.compile(r"^(\d+):(\d+):(\d+) (.*)$")
MV = re.compile(r"^HumanMove:(\S+) (\d+) 移动至 \(([\d.\-]+),([\d.\-]+)\)$")
AC = re.compile(r"^HumanAction:(\S+) (\d+) 设置(?:转换|工作|攻击)目标为 (\S+) (\d+)$")
ATK = re.compile(r"^(\S+)\(编号:(\d+)\)开始向(\S+)\(编号：?(\d+)\)攻击$")


def sec(m, s, c):
    return int(m) * 60 + int(s) + int(c) / 100.0


rows = []
for ln in open(F, encoding="utf-8", errors="replace"):
    ln = ln.rstrip("\n")
    m = T.match(ln)
    if not m:
        continue
    t = sec(m.group(1), m.group(2), m.group(3))
    rows.append((t, m.group(4)))

print("总带时间戳行数 =", len(rows), " 末行时间 = %.2f 分" % (rows[-1][0] / 60.0))

# ---------- 1. 祭司轨迹 ----------
pri = []
for t, s in rows:
    m = MV.match(s)
    if m and m.group(2) == "91101":
        pri.append((t, float(m.group(3)) / BL, float(m.group(4)) / BL))
print("\n=== 祭司 91101 HumanMove 数 =", len(pri), "===")
if pri:
    print("首次 %.1f分 块(%.1f,%.1f)  末次 %.2f分 块(%.1f,%.1f)"
          % (pri[0][0] / 60, pri[0][1], pri[0][2], pri[-1][0] / 60, pri[-1][1], pri[-1][2]))

# 按分钟：祭司所在块（取该分钟最后一条令）
per = collections.OrderedDict()
for t, x, y in pri:
    per[int(t // 60)] = (x, y)
print("\n祭司逐分钟位置（该分钟最后一条移动令）:")
for k in sorted(per):
    x, y = per[k]
    print("  %2d分  块(%6.1f,%6.1f)  像素(%7.0f,%7.0f)" % (k, x, y, x * BL, y * BL))

# ---------- 2. 地图定位：所有我方单位移动坐标分布 ----------
my = []
for t, s in rows:
    m = MV.match(s)
    if not m:
        continue
    x, y = float(m.group(3)) / BL, float(m.group(4)) / BL
    my.append((t, m.group(1), x, y))
print("\n=== 全部 HumanMove n=%d ===" % len(my))
xs = [p[2] for p in my]; ys = [p[3] for p in my]
print("坐标范围 x %.1f~%.1f  y %.1f~%.1f" % (min(xs), max(xs), min(ys), max(ys)))

# 前 3 分钟（开局，单位都在基地附近）→ 基地中心估计
early = [p for p in my if p[0] <= 180]
if early:
    print("前 3 分钟 n=%d  中心(%.1f,%.1f)" % (
        len(early), statistics.mean([p[2] for p in early]), statistics.mean([p[3] for p in early])))

REF = {"map": (80.40, 12.05), "map1": (22.35, 74.95), "map2": (73.75, 87.25), "map3": (28.90, 81.00)}
if early:
    cx = statistics.mean([p[2] for p in early]); cy = statistics.mean([p[3] for p in early])
    print("\n与各图基地中心距离（参考表）:")
    for k, (rx, ry) in REF.items():
        print("  %-5s (%.2f,%.2f)  距 %.1f 格" % (k, rx, ry, ((cx - rx) ** 2 + (cy - ry) ** 2) ** 0.5))

# ---------- 3. 武器厂定位（用祭司进入射程前的最后位置反推） ----------
tgt = [t for t, s in rows if s == "HumanAction:祭司 91101 设置转换目标为 攻城武器厂 11098"]
print("\n=== 设武器厂为目标时刻 =", tgt)
if tgt:
    t0 = tgt[0]
    before = [p for p in pri if p[0] <= t0]
    after = [p for p in pri if p[0] >= t0]
    if before:
        print("  设目标时祭司在块(%.1f,%.1f)" % (before[-1][1], before[-1][2]))
    if after:
        print("  之后首次移动令 %.2f分 块(%.1f,%.1f)" % (after[0][0] / 60, after[0][1], after[0][2]))
        print("  最后一条移动令 %.2f分 块(%.1f,%.1f)" % (after[-1][0] / 60, after[-1][1], after[-1][2]))
    # 进入射程时刻
    hit = [t for t, s in rows if "开始向攻城武器厂(编号：11098)攻击" in s]
    print("  开始向武器厂攻击时刻 =", ["%.2f分" % (x / 60) for x in hit])
    if hit:
        print("  ⇒ 设目标→进射程耗时 %.1f 秒" % (hit[0] - t0))

# ---------- 4. 反攻期（22分起）祭司移动令密度 ----------
print("\n=== 22 分后祭司移动令条数 =", sum(1 for p in pri if p[0] >= 1320), "===")
print("=== 22 分后全部 HumanMove 条数 =", sum(1 for p in my if p[0] >= 1320), "===")

# ---------- 5. 祭司感化目标全序列 ----------
print("\n=== 祭司感化/工作目标设定全序列 ===")
for t, s in rows:
    m = AC.match(s)
    if m and m.group(2) == "91101":
        print("  %7.2f分  目标 %s %s" % (t / 60, m.group(3), m.group(4)))
