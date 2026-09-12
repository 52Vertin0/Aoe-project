# -*- coding: utf-8 -*-
"""
仓库令落点探针（2026-09-22）
用途：回答"同一个瞪羚群附近是否重复建了 2 座仓库"，并给出改前/改后对照。

口径（全部来自引擎/AI 日志，不受采样影响）：
  - 建造令 = `[BUILD-ISSUE f=..] type=3 .. at=(x,y)`（type=3 = 仓库 STOCK），x/y 是【块坐标】
  - 新增观测（2026-09-22）：`[STOCK-ORD f=..] 第二仓库 群中心块(x,y) 远距瞪羚=n 现存仓=k/4 木=w`
  - 判据输入自描述：`[GATE ..] .. | 仓库令落点=(x,y)Δn ...`
  - 被落点闸挡下：`[STOCK-SUPPRESS f=..] 远距瞪羚=n < 阈值2`

分类（块距离，1 块 = BLOCKSIDELENGTH = 35.777）：
  - 同点  ≤ 9    （tryBuild 偏移表 0/±3/±6 ⇒ 同簇被挤到旁边一格）
  - 同群 10~20   （同一连通群内；isFarGazelle 的锚点半径就是 20 格）
  - 分散 > 20    （不同群，属"多群各建 1 座"的正常情形）
  - 贴TC ≤ 20    （距 TC(19,18) ≤20 块 ⇒ 建在基地旁，根本不是猎场节点 = 选址兜底跑飞）

★ 2026-09-22 补充【真·同一群判据】：上面的"同群"用的是【落点】间距（代理量）。
  用户要的是"同一个瞪羚群"，应直接比 `[STOCK-ORD]` 里的【群中心块】——
  两个令若服务于同一群，其群中心块必然几乎重合；不同群的中心相距可达 20+ 块。
  故新增 HERD_SAME(≤8 块) 判据：一对令的【群中心块】距 ≤8 ⇒ 判为"同一个群被重复下单"。

用法：
  python stock_order_probe.py scan <glob>        # 汇总
  python stock_order_probe.py show <ait> [...]   # 逐局明细
"""
import re, os, sys, glob, math
from collections import defaultdict, Counter

RE_BUILD = re.compile(r"\[BUILD-ISSUE f=(\d+)\] type=(\d+) size=(\d+) \S+=(\d+) at=\((-?\d+),(-?\d+)\) wood=(\d+)")
RE_ORD = re.compile(r"\[STOCK-ORD f=(\d+)\] 第二仓库 群中心块\((-?\d+),(-?\d+)\) 远距瞪羚=(\d+) 现存仓=(\d+)/(\d+) 木=(\d+)")
RE_SUP = re.compile(r"\[STOCK-SUPPRESS f=(\d+)\] 远距瞪羚=(\d+) < 阈值(\d+)（其中被落点闸挡下 (\d+) 只；落点记忆 (\d+) 条）")
RE_GATE = re.compile(r"\[GATE f=(\d+)\] needStock=(\d+) gazAlive=(\d+) stock=(\d+) wood=(\d+).*?snGB=(\d+)(?: \| 仓库令落点=(.*))?$")
TC_BLK = (19, 18)          # 本图固定地理：TC 块坐标（见 MEMORY §3 主循环/固定地理）
DUP_POINT = 9.0
DUP_HERD = 20.0
HERD_SAME = 8.0            # 群中心块距 ≤ 此值 ⇒ 判为"同一个群"（真判据，见文件头 ★）


def parse(path):
    """返回 dict(orders=[(frame,x,y)], ord_log=[(frame,x,y,far,cnt,maxs,wood)], sup=[(frame,far,thr)], gate=[...])"""
    orders, ordlog, sup, gate, ordfail = [], [], [], [], []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                p = line.split(" | ", 3)
                if len(p) < 4:
                    continue
                msg = p[3]
                if "[BUILD-ISSUE" in msg:
                    m = RE_BUILD.search(msg)
                    if m and int(m.group(2)) == 3:
                        orders.append((int(m.group(1)), int(m.group(5)), int(m.group(6))))
                if "[STOCK-ORD" in msg:
                    m = RE_ORD.search(msg)
                    if m:
                        ordlog.append((int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                       int(m.group(4)), int(m.group(5)), int(m.group(6)), int(m.group(7))))
                if "[STOCK-SUPPRESS" in msg:
                    m = RE_SUP.search(msg)
                    if m:
                        sup.append((int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                    int(m.group(4)), int(m.group(5))))
                if "[STOCK-ORD-FAIL" in msg:
                    ordfail.append((int(re.search(r"f=(\d+)", msg).group(1)),))
                if "[GATE f=" in msg:
                    m = RE_GATE.search(msg.strip())
                    if m:
                        gate.append(dict(fr=int(m.group(1)), need=int(m.group(2)), gaz=int(m.group(3)),
                                         stock=int(m.group(4)), snGB=int(m.group(6)),
                                         pts=(m.group(7) or "").strip()))
    except Exception:
        pass
    return dict(orders=orders, ordlog=ordlog, sup=sup, gate=gate, ordfail=ordfail)


def classify(orders):
    """局级判读：返回 (n, 最小成对块距|None, 贴TC条数)"""
    n = len(orders)
    mind = None
    for i in range(n):
        for j in range(i + 1, n):
            d = math.hypot(orders[i][1] - orders[j][1], orders[i][2] - orders[j][2])
            if mind is None or d < mind:
                mind = d
    ntc = sum(1 for _, x, y in orders
              if math.hypot(x - TC_BLK[0], y - TC_BLK[1]) <= DUP_HERD)
    return n, mind, ntc


def herd_pairs(ordlog):
    """真·同一群判据：对 [STOCK-ORD] 的【群中心块】做成对距离。
    返回 (min_center_dist|None, [(d, f1, c1, f2, c2), ...] 全部对)"""
    pts = [(f, x, y) for f, x, y, _far, _k, _m, _w in ordlog]
    pairs = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = math.hypot(pts[i][1] - pts[j][1], pts[i][2] - pts[j][2])
            pairs.append((d, pts[i][0], (pts[i][1], pts[i][2]), pts[j][0], (pts[j][1], pts[j][2])))
    mn = min((p[0] for p in pairs), default=None)
    return mn, pairs


def scan(pattern):
    files = sorted(glob.glob(pattern))
    per = []
    for fp in files:
        d = parse(fp)
        n, mind, ntc = classify(d["orders"])
        per.append((os.path.basename(fp), n, mind, ntc, d))
    print("=" * 100)
    print("【0】样本规模")
    print(f"  局数 = {len(files)}")
    tot_ord = sum(len(d['orders']) for _, _, _, _, d in per)
    print(f"  仓库建造令总数 = {tot_ord}   平均 {tot_ord/max(1,len(files)):.2f} 条/局"
          f"   （对比：MAX_STOCK=4 ⇒ 首座为剧本预置，AI 每局最多可下 3 条）")
    print()
    print("=" * 100)
    print("【1】每局仓库令条数分布")
    c = Counter(n for _, n, _, _, _ in per)
    for k in sorted(c):
        print(f"  {k} 条 : {c[k]:5d} 局 ({c[k]/max(1,len(files))*100:5.1f}%)")
    print()
    print("=" * 100)
    print("【2】多仓局（≥2 条）的成对最小块距分类")
    multi = [(nm, n, md, ntc, d) for nm, n, md, ntc, d in per if n >= 2]
    pt = sum(1 for _, _, md, _, _ in multi if md is not None and md <= DUP_POINT)
    hd = sum(1 for _, _, md, _, _ in multi if md is not None and DUP_POINT < md <= DUP_HERD)
    sp = sum(1 for _, _, md, _, _ in multi if md is not None and md > DUP_HERD)
    print(f"  多仓局 = {len(multi)} 局")
    print(f"    同点(≤{DUP_POINT:.0f}块) = {pt:5d}  ({pt/max(1,len(multi))*100:5.1f}%)")
    print(f"    同群({DUP_POINT:.0f}~{DUP_HERD:.0f}块)  = {hd:5d}  ({hd/max(1,len(multi))*100:5.1f}%)")
    print(f"    分散(>{DUP_HERD:.0f}块)   = {sp:5d}  ({sp/max(1,len(multi))*100:5.1f}%)")
    print(f"  ★ 同点/同群重复占比 = {(pt+hd)/max(1,len(multi))*100:.1f}%   （口径=落点间距，代理量）")
    print()
    print("=" * 100)
    print(f"【2b】真·同一群判据：对[STOCK-ORD]的【群中心块】做成对距离（≤{HERD_SAME:.0f}块 = 同一个群）")
    same, near, far, n2 = 0, 0, 0, 0
    histc = Counter()
    for nm, n, md, ntc, d in per:
        mn, _pairs = herd_pairs(d["ordlog"])
        if mn is None:
            continue
        n2 += 1
        histc[int(mn) // 5 * 5] += 1
        if mn <= HERD_SAME:
            same += 1
        elif mn <= DUP_HERD:
            near += 1
        else:
            far += 1
    print(f"  可比局（≥2 条含群中心） = {n2} 局")
    print(f"    同一个群(中心≤{HERD_SAME:.0f}块)  = {same:5d}  ({same/max(1,n2)*100:5.1f}%)  ← 用户所指缺陷")
    print(f"    相邻群({HERD_SAME:.0f}~{DUP_HERD:.0f}块)   = {near:5d}  ({near/max(1,n2)*100:5.1f}%)")
    print(f"    不同群(>{DUP_HERD:.0f}块)    = {far:5d}  ({far/max(1,n2)*100:5.1f}%)")
    print(f"  群中心对最小距直方图（块）：" + "  ".join(f"{k}~{k+4}:{histc[k]}" for k in sorted(histc)))
    print()
    print("=" * 100)
    print("【3】多仓局最小仓间距直方图（块）")
    hist = Counter(int(md) // 5 * 5 for _, _, md, _, _ in multi if md is not None)
    for k in sorted(hist):
        print(f"  {k:3d}~{k+4:3d} : {hist[k]:4d}  {'#'*min(60,hist[k])}")
    print()
    print("=" * 100)
    print(f"【4】贴 TC 的仓库令（距 TC{TC_BLK} ≤{DUP_HERD:.0f} 块 ⇒ 不是猎场节点，属选址兜底跑飞）")
    tcg = sum(1 for _, _, _, ntc, _ in per if ntc > 0)
    tot_tc = sum(ntc for _, _, _, ntc, _ in per)
    print(f"  命中局数 = {tcg} / {len(files)} ({tcg/max(1,len(files))*100:.1f}%)   令数 = {tot_tc}")
    for nm, n, md, ntc, d in per:
        if ntc <= 0:
            continue
        ctr = {f: (x, y) for f, x, y, _f, _k, _m, _w in d['ordlog']}
        for f, x, y in d['orders']:
            if math.hypot(x - TC_BLK[0], y - TC_BLK[1]) <= DUP_HERD:
                c = ctr.get(f)
                if c:
                    dev = math.hypot(x - c[0], y - c[1])
                else:
                    dev = float('nan')
                dc = math.hypot(c[0] - TC_BLK[0], c[1] - TC_BLK[1]) if c else float('nan')
                print(f"    {nm:<18} f={f:<6} 落点=({x},{y}) 距TC={math.hypot(x-TC_BLK[0],y-TC_BLK[1]):5.1f}"
                      f"  群中心={c} 距TC={dc:5.1f}  选址偏差={dev:.1f}"
                      f"  {'✅该群本来就在TC旁(合法)' if dc <= DUP_HERD else '❌兜底跑飞'}")
    print()
    print("=" * 100)
    print("【5】新观测（2026-09-22 新增日志）")
    print(f"  [STOCK-ORD]      总条数 = {sum(len(d['ordlog']) for _,_,_,_,d in per)}")
    nsup = sum(len(d['sup']) for _, _, _, _, d in per)
    ghit = sum(x[3] for _, _, _, _, d in per for x in d['sup'])
    print(f"  [STOCK-SUPPRESS] 总条数 = {nsup}   累计【被落点闸挡下】的瞪羚 = {ghit}"
          f"   （0 条且 [STOCK-ORD]=0 ⇒ 该批压根没走到这条路径）")
    print(f"  [STOCK-ORD-FAIL] 总条数 = {sum(len(d['ordfail']) for _,_,_,_,d in per)}"
          f"   （有候选但 tryBuild 失败 = 选址冲突/没空闲村民/木不够）")
    # ★ 群中心块 → 实际选址 的块距（大 ⇒ 选址兜底跑飞，仓库离它该服务的兽群太远）
    devs = []
    for _, _, _, _, d in per:
        ctr = {f: (x, y) for f, x, y, _f, _k, _m, _w in d['ordlog']}
        for f, x, y in d['orders']:
            if f in ctr:
                devs.append(math.hypot(x - ctr[f][0], y - ctr[f][1]))
    if devs:
        srt = sorted(devs); md50 = srt[len(srt) // 2]; p90 = srt[int(len(srt) * 0.9)]
        print(f"  选址偏差 |实际选址 − 群中心块|：n={len(devs)} 中位={md50:.1f} 块  P90={p90:.1f} 块"
              f"  >10块的 = {sum(1 for v in devs if v > 10)} 条")
    snGB = Counter(g['snGB'] for _, _, _, _, d in per for g in d['gate'])
    print(f"  [GATE] snGB 分布 = {dict(snGB)}   （恒 1 ⇒ 近场那块从未执行，见源码注释）")
    pts = sum(1 for _, _, _, _, d in per for g in d['gate'] if g['pts'] and g['pts'] != '无')
    print(f"  [GATE] 含仓库令落点(非'无')的采样 = {pts} 条")
    print()
    print("=" * 100)
    print("【6】实例（同点/同群优先，各局前 25 局）")
    shown = 0
    for nm, n, md, ntc, d in per:
        if shown >= 25:
            break
        if n >= 2 and md is not None and md <= DUP_HERD:
            tag = "同点" if md <= DUP_POINT else "同群"
            ptsx = " ".join(f"f{f}({x},{y})" for f, x, y in d["orders"])
            print(f"  [{tag}] {nm:<20} minD={md:5.1f} 贴TC={ntc}  {ptsx}")
            shown += 1


def show(files):
    for fp in files:
        d = parse(fp)
        nm = os.path.basename(fp)
        n, md, ntc = classify(d["orders"])
        print("=" * 100)
        print(f"{nm}   仓库令 {n} 条   最小块距 {('%.1f' % md) if md is not None else '-'}   贴TC {ntc} 条")
        for f, x, y in d["orders"]:
            print(f"   [BUILD-ISSUE] f={f:<6} at=({x},{y})   距TC={math.hypot(x-TC_BLK[0], y-TC_BLK[1]):5.1f} 块")
        for f, x, y, far, k, mx, w in d["ordlog"]:
            print(f"   [STOCK-ORD]   f={f:<6} 群中心块=({x},{y}) 远距瞪羚={far} 现存仓={k}/{mx} 木={w}")
        for f, far, thr, gh, npt in d["sup"]:
            print(f"   [SUPPRESS]    f={f:<6} 远距瞪羚={far} < {thr}  (被落点闸挡下 {gh} 只 / 落点 {npt} 条)")
        for (f,) in d["ordfail"]:
            print(f"   [ORD-FAIL]    f={f:<6} 有候选但 tryBuild 失败")
        for g in d["gate"]:
            print(f"   [GATE]        f={g['fr']:<6} needStock={g['need']} gaz={g['gaz']} stock={g['stock']} snGB={g['snGB']} 落点={g['pts']}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if mode == "show":
        show(sys.argv[2:])
    else:
        pat = sys.argv[2] if len(sys.argv) > 2 else "*.ait"
        scan(pat)
