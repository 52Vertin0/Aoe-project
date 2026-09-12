# -*- coding: utf-8 -*-
"""
金矿仓库探针（2026-09-22）
用途：验收「金矿旁边没有仓库的话也要建仓库」，并给出改前/改后对照。

口径（全部来自 AI 日志 + 地图文件，不受采样影响）：
  - 建仓令      = `[BUILD-ISSUE f=..] type=3 .. at=(x,y)`（type=3 = 仓库 STOCK；x/y 是【块坐标】）
  - 金矿仓下单  = `[GOLD-STOCK f=..] 在用金矿簇心块(x,y) 簇内=n 在用格=k 远金矿格=m 金矿仓令=i/1 木=w`
  - 判据输入集  = `[GOLD-GATE f=..] 存活金矿格=a 远金矿格=b 在用远金矿格=c 金矿仓令=i/1 被落点闸挡下=g 木=w`
  - 下单失败    = `[GOLD-STOCK-FAIL f=..]`
  - 金矿真实位置 = map3.njust 的 StaticRes Num=2，按引擎的 90° 旋转公式换算成【游戏内块坐标】

几何换算（MapRotation.cpp:108 rotateBlockAnchor + config.json MAP_L=MAP_U=100）：
  90°: gameDR = 100 - rawBlockUR - footprint, gameUR = rawBlockDR
  校验锚点：Building_11 武器厂 raw(82,20)/fp=3 → game(77,82)，与日志 `siegeSN=11099 mem=(77,82)` 完全吻合；
            我方 TC raw(18,78) → (19,18)，与 MEMORY 记载一致。

用法：
  python gold_stock_probe.py scan <glob>     # 汇总
  python gold_stock_probe.py show <ait>     # 逐局明细
"""
import re, os, sys, glob, json, math
from collections import Counter

RE_BUILD = re.compile(r"\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) \S+=(\d+) at=\((-?\d+),(-?\d+)\) wood=(\d+)")
RE_GORD = re.compile(r"\[GOLD-STOCK f=(\d+)\] 在用金矿簇心块\((-?\d+),(-?\d+)\) 簇内=(\d+) 在用格=(\d+) 远金矿格=(\d+) 金矿仓令=(\d+)/(\d+) 木=(\d+)")
RE_GFAIL = re.compile(r"\[GOLD-STOCK-FAIL f=(\d+)\] 在用金矿簇心块\((-?\d+),(-?\d+)\) 在用格=(\d+) 远金矿格=(\d+) 木=(\d+)")
RE_GGATE = re.compile(r"\[GOLD-GATE f=(\d+)\] 存活金矿格=(\d+) 远金矿格=(\d+) 在用远金矿格=(\d+) 金矿仓令=(\d+)/(\d+) 被落点闸挡下=(\d+) 木=(\d+)")
RE_GATE = re.compile(r"\[GATE f=(\d+)\] needStock=\d+ gazAlive=\d+ stock=(\d+) wood=(\d+)")
RE_ORD2 = re.compile(r"\[STOCK-ORD f=(\d+)\] 第二仓库 群中心块\((-?\d+),(-?\d+)\)")

TC_BLK = (19, 18)
NEAR_BLK = 8.0          # 落点距"在用金矿格" ≤ 此值 ⇒ 认定为"真落在矿旁"
MAPFILE = r"C:\new-aoe3.0.7g\map3.njust"


def load_gold_tiles(path=MAPFILE):
    """返回游戏内块坐标的金矿格列表 [(x,y), ...]（90° 旋转后）。"""
    d = json.load(open(path, encoding="utf-8"))
    out = []
    for k, v in d.items():
        if k.startswith("StaticRes") and isinstance(v, dict) and v.get("Num") == 2:
            out.append((100 - v["BlockUR"] - 2, v["BlockDR"]))   # fp=2（SIZELEN_SMALL）
    return out


def parse(path):
    r = dict(orders=[], gord=[], gfail=[], ggate=[], gate=[], win=0, lose=0)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                p = line.split(" | ", 3)
                if len(p) < 4:
                    continue
                m = p[3]
                if "[BUILD-ISSUE" in m:
                    x = RE_BUILD.search(m)
                    if x and int(x.group(2)) == 3:
                        r["orders"].append((int(x.group(1)), int(x.group(5)), int(x.group(6))))
                if "[GOLD-STOCK " in m:
                    x = RE_GORD.search(m)
                    if x:
                        r["gord"].append(tuple(int(x.group(i)) for i in range(1, 10)))
                if "[GOLD-STOCK-FAIL" in m:
                    x = RE_GFAIL.search(m)
                    if x:
                        r["gfail"].append(tuple(int(x.group(i)) for i in range(1, 7)))
                if "[GOLD-GATE" in m:
                    x = RE_GGATE.search(m)
                    if x:
                        r["ggate"].append(tuple(int(x.group(i)) for i in range(1, 9)))
                if "[GATE f=" in m:
                    x = RE_GATE.search(m)
                    if x:
                        r["gate"].append((int(x.group(1)), int(x.group(2)), int(x.group(3))))
                if "VICTORY! Siege Workshop converted" in m:
                    r["win"] = 1
                if "DEFEAT:" in m:
                    r["lose"] = 1
    except Exception:
        pass
    return r


def scan(pattern):
    files = sorted(glob.glob(pattern))
    gold = load_gold_tiles()
    print("=" * 104)
    print(f"金矿格总数（地图真值）= {len(gold)}    TC 块坐标 = {TC_BLK}    '矿旁' 判据 = 落点距最近金矿格 ≤ {NEAR_BLK:.0f} 块")
    print(f"样本 = {len(files)} 局")
    print()
    n_ord, n_gord, n_gfail = 0, 0, 0
    hits, gord_rows, dev_rows, fail_rows = 0, [], [], []
    ready_games, ready_frame = 0, []
    ggate_alive, ggate_far, ggate_use = [], [], []
    maxstock, wins, loses = [], 0, 0
    for fp in files:
        nm = os.path.basename(fp)
        r = parse(fp)
        n_ord += len(r["orders"])
        n_gord += len(r["gord"])
        n_gfail += len(r["gfail"])
        if r["gord"]:
            hits += 1
        for t in r["gord"]:
            f, cx, cy, cnt, k, m, i, maxi, w = t
            # 簇心距矿（判据基准）与 实际落点距矿（要拿 [BUILD-ISSUE] 的 at= 来核）
            dcen = min(math.hypot(cx - gx, cy - gy) for gx, gy in gold)
            land = None
            for bf, bx, by in r["orders"]:
                if abs(bf - f) <= 12 and (land is None or abs(bf - f) < abs(land[0] - f)):
                    land = (bf, bx, by)
            if land:
                dland = min(math.hypot(land[1] - gx, land[2] - gy) for gx, gy in gold)
                dtc = math.hypot(land[1] - TC_BLK[0], land[2] - TC_BLK[1])
            else:
                dland, dtc = None, None
            gord_rows.append((nm, f, cx, cy, cnt, k, m, i, maxi, w, dcen, dtc, land, dland))
            if dland is not None:
                dev_rows.append(dland)
        for t in r["gfail"]:
            f, cx, cy, k, m, w = t
            fail_rows.append((nm, f, cx, cy, k, m, w, min(math.hypot(cx - gx, cy - gy) for gx, gy in gold)))
        use_frames = [g[0] for g in r["ggate"] if g[3] > 0]
        if use_frames:
            ready_games += 1
            ready_frame.append(use_frames[0])
        if r["ggate"]:
            ggate_alive.append(max(g[1] for g in r["ggate"]))
            ggate_far.append(max(g[2] for g in r["ggate"]))
            ggate_use.append(max(g[3] for g in r["ggate"]))
        if r["gate"]:
            maxstock.append(max(s for _, s, _ in r["gate"]))
        wins += r["win"]
        loses += r["lose"]

    print("【1】金矿仓是否真被下单（验收①）")
    print(f"  [GOLD-STOCK] 令数 = {n_gord}   命中局数 = {hits}/{len(files)} ({hits/max(1,len(files))*100:.1f}%)")
    print(f"  [GOLD-STOCK-FAIL] 条数 = {n_gfail}")
    print()
    print("【2】触发条件是否可达（门禁输入集，验收②）")
    print(f"  出现过 '在用远金矿格>0' 的局 = {ready_games}/{len(files)}")
    if ready_frame:
        rf = sorted(ready_frame)
        print(f"    首次出现帧：中位 {rf[len(rf)//2]}  最早 {rf[0]}  最晚 {rf[-1]}"
              f"   （1500 帧 = 1 游戏分 ⇒ 最早 ≈ {rf[0]/1500:.1f} 分）")
    if ggate_use:
        print(f"  各局峰值：存活金矿格 max={max(ggate_alive)}  远金矿格 max={max(ggate_far)}  在用远金矿格 max={max(ggate_use)}")
    print()
    print("【3】落点是否真在矿旁（验收③ —— 不是兜底跑飞回 TC）")
    if gord_rows:
        cen = sorted(r[10] for r in gord_rows)
        print(f"  簇心（判据基准）距最近金矿格：n={len(cen)}  中位 {cen[len(cen)//2]:.1f}  最大 {cen[-1]:.1f} 块"
              f"   （0.0 = 簇心正好落在金矿格上）")
    if dev_rows:
        s = sorted(dev_rows)
        print(f"  实际落点（[BUILD-ISSUE] at=）距最近金矿格：n={len(s)}  中位 {s[len(s)//2]:.1f} 块  最大 {s[-1]:.1f} 块")
        print(f"     ≤{NEAR_BLK:.0f} 块（矿旁）= {sum(1 for v in s if v <= NEAR_BLK)}/{len(s)}"
              f"    >20 块（等于没落到矿旁）= {sum(1 for v in s if v > 20)}")
    if gord_rows:
        dtcs = sorted(r[11] for r in gord_rows if r[11] is not None)
        if dtcs:
            print(f"  落点距 TC：中位 {dtcs[len(dtcs)//2]:.1f} 块   （应 >20 ⇒ 确认不是 TC 旁的兜底跑飞）")
        print("  逐条：")
        for nm, f, cx, cy, cnt, k, m, i, maxi, w, dcen, dtc, land, dland in gord_rows:
            lt = ("(%d,%d)" % (land[1], land[2])) if land else "—"
            print(f"    {nm:<16} f={f:<6} 簇心块=({cx},{cy}) 距矿={dcen:4.1f} → 落点{lt}"
                  f" 落点距矿={('%.1f' % dland) if dland is not None else '—'} 距TC={('%.1f' % dtc) if dtc is not None else '—'}"
                  f"  簇内={cnt} 在用格={k} 远金矿格={m} 金矿仓令={i}/{maxi} 木={w}")
    else:
        print("  本批无 [GOLD-STOCK] ⇒ 无可校验落点")
    if fail_rows:
        print("  下单失败（有候选但 tryBuild 没落地）：")
        for nm, f, cx, cy, k, m, w, dmin in fail_rows:
            print(f"    {nm:<16} f={f:<6} 簇心块=({cx},{cy}) 距最近金矿格={dmin:5.1f} 在用格={k} 远金矿格={m} 木={w}")
    print()
    print("【4】副作用（验收④：总量与胜负没劣化）")
    if maxstock:
        print(f"  末局 stock 最大值分布 = {dict(sorted(Counter(maxstock).items()))}   （上限应为 MAX_STOCK+MAX_GOLD_STOCK = 5）")
        print(f"  仓库令总数 = {n_ord}   平均 {n_ord/max(1,len(files)):.2f} 条/局")
    print(f"  胜负：胜 {wins} / 负 {loses} / 打满无结果 {len(files)-wins-loses}")


def show(files):
    gold = load_gold_tiles()
    for fp in files:
        r = parse(fp)
        print("=" * 104)
        print(f"{os.path.basename(fp)}   仓库令 {len(r['orders'])} 条   金矿仓令 {len(r['gord'])} 条   "
              f"胜负={('胜' if r['win'] else ('负' if r['lose'] else '无结果'))}")
        for f, x, y in r["orders"]:
            dmin = min(math.hypot(x - gx, y - gy) for gx, gy in gold)
            print(f"   [BUILD-ISSUE] f={f:<6} at=({x},{y})  距TC={math.hypot(x-TC_BLK[0],y-TC_BLK[1]):5.1f}"
                  f"  距最近金矿格={dmin:5.1f}")
        for t in r["gord"]:
            f, cx, cy, cnt, k, m, i, maxi, w = t
            dmin = min(math.hypot(cx - gx, cy - gy) for gx, gy in gold)
            print(f"   [GOLD-STOCK]  f={f:<6} 簇心块=({cx},{cy}) 距最近金矿格={dmin:5.1f} 距TC={math.hypot(cx-TC_BLK[0],cy-TC_BLK[1]):5.1f}"
                  f"  簇内={cnt} 在用格={k} 远金矿格={m} 令={i}/{maxi} 木={w}")
        for t in r["gfail"]:
            f, cx, cy, k, m, w = t
            print(f"   [GOLD-FAIL]   f={f:<6} 簇心块=({cx},{cy}) 在用格={k} 远金矿格={m} 木={w}")
        for g in r["ggate"][:0]:
            pass
        gg = r["ggate"]
        if gg:
            print(f"   [GOLD-GATE] 采样 {len(gg)} 条：首 {gg[0]}  末 {gg[-1]}")
        gt = r["gate"]
        if gt:
            print(f"   [GATE] 末条：stock={gt[-1][1]} wood={gt[-1][2]}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if mode == "show":
        show(sys.argv[2:])
    else:
        scan(sys.argv[2] if len(sys.argv) > 2 else "*.ait")
