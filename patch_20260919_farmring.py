# -*- coding: utf-8 -*-
"""2026-09-19 农场紧邻环硬限制补丁
用户需求：「农场只能建在谷仓和 TC 周围隔一格的地方」（硬限制 + 谷仓旁可作锚点）

改动 4 处：
  F1  FARM_ANCHOR_R_MAX 18 → 4（只允许紧邻环）
  F2  consider/ringOf 增加 base 锚点参数；删除三角不等式剪枝用的 tcx/dAT
  F3  pass 循环：第 1 段 TC 环有解即 break；第 2 段（谷仓/仓库环）仅在第 1 段无解时才跑
  F4  tryBuild：农场禁用通用 findBuildSite 兜底 + 新增 [FARM-RING] 诊断日志
"""
import io, sys

PATH = 'UsrAI.cpp'
DRY = '--dry' in sys.argv

raw = open(PATH, 'rb').read()
S = raw.decode('utf-8')
L = S.split('\r\n')
txt = '\r\n'.join(L)
assert txt == S, 'CRLF 拆分回代不一致'


def rep(old, new, tag):
    old = old.replace('\r\n', '\n').replace('\n', '\r\n')   # 统一成文件实际的 CRLF
    new = new.replace('\r\n', '\n').replace('\n', '\r\n')
    n = txt.count(old)
    assert n == 1, '%s 命中 %d 次（应为 1）' % (tag, n)
    return txt.replace(old, new, 1)


# ---------- F1：R_MAX 18 → 4 ----------
OLD1 = '''#define FARM_ANCHOR_R_MIN 4      // 锚点外的最近可行环（3x3 锚点 + 隔 1 格 + 3x3 农场）
#define FARM_ANCHOR_R_MAX 18     // 单锚点搜索半径上限；超出即认为不划算，交给 tryBuild 的 findBuildSite 兜底
//   ★ 2026-09-15 由 12 上调到 18：R_MAX=12 时，一旦 TC 环 12 格内被建筑/资源/相邻约束挤满，
//     就只剩 findBuildSite 兜底；而兜底已带上 avoidFarmAdjacent（守"农场隔 1 格"），可能直接失败。
//     实测 fm3 因此只建出 6 座农场（f=24877 之后连续 13500 帧无任何农场令）。
//     放大半径只增加"内圈确实全满时"的候选，不影响紧凑度 —— 评分按"到 TC 距离"，内圈永远优先命中。'''
NEW1 = '''#define FARM_ANCHOR_R_MIN 4      // 锚点外的最近可行环（3x3 锚点 + 隔 1 格 + 3x3 农场）
// ★★★ 2026-09-19 用户需求「农场只能建在谷仓和 TC 周围隔一格的地方」（硬限制）★★★
//   R_MAX 由 18 收到 = R_MIN ⇒ 只允许【紧邻环】，不再接受任何外扩环。
//   实测依据（kd 23 局 / 251 座农场，探针 farm_ring_probe.py）：
//     · 紧邻环(r=4)几何上只有 8 个槽位：每条边只能放 3 个（dx=-4/0/+4），因为农场彼此须隔 1 格
//       （dx 差 <4 会触发 isFarmAdjacent）。其中 TC 正下方那格 (-4,-4) 在 23/23 局被初始箭塔占
//       ⇒ 每局真正可用的只有 6~7 座。
//     · 内圈满后 r=5/6/7 会与紧邻环的农场"错位相邻"而几乎不可用（实测仅 10.8%/3.2%/2.4%），
//       下一个能与 r=4 整排对齐的层恰好是 r=8 ⇒ 旧 R_MAX=18 下有 30.3% 的农场落在 r=8
//       （8.0~11.3 格），破坏"只隔一格"的约束。
//   ★ 座数补偿：TC 环满后吃【谷仓/仓库环】（同一 r=4 口径），见 findFarmSiteBest 第 2 段。
//     第 2 段只在 TC 环彻底无解时才跑 ⇒ 保住"村民从 TC 出发"的通勤最优部分。
#define FARM_ANCHOR_R_MAX 4      // 搜索半径上限 = R_MIN ⇒ 只允许紧邻环（2026-09-19 用户硬限制）'''
txt = rep(OLD1, NEW1, 'F1')

# ---------- F2：考虑函数 / 环枚举 / 删除 tcx+dAT ----------
OLD2 = '''    const double tcx = center->BlockDR + 1.0, tcy = center->BlockUR + 1.0;
    std::vector<double> dAT(NA, 0.0);        // 各锚点中心 → TC 的距离（用于三角不等式剪枝）
    for (int i = 0; i < NA; ++i) {
        double ax = anchors[i].first + 1.0, ay = anchors[i].second + 1.0;
        dAT[i] = std::sqrt((ax - tcx) * (ax - tcx) + (ay - tcy) * (ay - tcy));
    }

    double bestD2 = 1e18;                    // 到 TC 距离的平方（避免 sqrt）
    int bx = -1, by = -1;
    // 候选评定（两段共用）：黑名单 → isPositionFree → isFarmAdjacent → 按「到 TC 距离」刷新最优
    auto consider = [&](int nx, int ny, bool useBlack) {
        if (nx < 0 || ny < 0) return;
        if (useBlack && triedBuildPositions.count(nx * 1000 + ny)) return;
        if (!isPositionFree(nx, ny, 3)) return;
        if (isFarmAdjacent(nx, ny)) return;
        double fcx = nx + 1.0, fcy = ny + 1.0;
        double d2 = (fcx - tcx) * (fcx - tcx) + (fcy - tcy) * (fcy - tcy);
        if (d2 < bestD2) { bestD2 = d2; bx = nx; by = ny; }
    };
    // 锚点外 r 环的 4 条带（上/下/左/右）；几何与旧 findFarmRingSite 一致（3x3 + 隔 1 格 ⇒ r>=4）
    auto ringOf = [&](int ax, int ay, int r, bool useBlack) {'''
NEW2 = '''    double bestD2 = 1e18;                    // 距离平方（避免 sqrt）
    int bx = -1, by = -1;
    // 候选评定（两段共用）：黑名单 → isPositionFree → isFarmAdjacent → 按「到 base 锚点距离」刷新最优
    //   ★ 2026-09-19：base = 评分基准锚点索引（0 = TC；>=1 = 对应的谷仓/仓库）。
    //     两段各自【段内】公平比较，段间不比较 ⇒ 第 1 段（TC 环）永远优先。
    auto consider = [&](int nx, int ny, bool useBlack, int base) {
        if (nx < 0 || ny < 0) return;
        if (useBlack && triedBuildPositions.count(nx * 1000 + ny)) return;
        if (!isPositionFree(nx, ny, 3)) return;
        if (isFarmAdjacent(nx, ny)) return;
        double fcx = nx + 1.0, fcy = ny + 1.0;
        double abx = anchors[base].first + 1.0, aby = anchors[base].second + 1.0;
        double d2 = (fcx - abx) * (fcx - abx) + (fcy - aby) * (fcy - aby);
        if (d2 < bestD2) { bestD2 = d2; bx = nx; by = ny; }
    };
    // 锚点外 r 环的 4 条带（上/下/左/右）；几何与旧 findFarmRingSite 一致（3x3 + 隔 1 格 ⇒ r>=4）
    auto ringOf = [&](int ax, int ay, int r, bool useBlack, int base) {'''
txt = rep(OLD2, NEW2, 'F2a')
txt = rep('                consider(nx, ny, useBlack);',
          '                consider(nx, ny, useBlack, base);', 'F2b')

# ---------- F3：两段式（TC 环优先 → 仅当无解才吃谷仓/仓库环）----------
OLD3 = '''        // ---- 第 1 段：TC 环（主锚点）----
        //   r 层候选到 TC 的最小距离恰为 r（nx==ax 时 Δx=0、Δy=r）⇒ 一旦 r² 超过当前最优，
        //   本层及所有更外层都不可能更优，直接 break。
        for (int r = FARM_ANCHOR_R_MIN; r <= FARM_ANCHOR_R_MAX; ++r) {
            if ((double)r * (double)r > bestD2) break;
            ringOf(anchors[0].first, anchors[0].second, r, useBlack);
        }
        // ---- 第 2 段：谷仓/仓库环（备选空间；只有 TC 环更远时才会胜出）----
        //   剪枝用三角不等式下界：d(TC,候选) >= d(TC,锚点) - max|锚点→候选|；
        //   该下界 >= 真实值 ⇒ 只会少剪、不会误剪。锚点离 TC 越远越容易被整体剪掉
        //   （例如 52 格外的谷仓：dAT≈52、rMaxD≈7 ⇒ lb≈45 ⇒ lb² 远超 TC 旁的 25，直接跳过）。
        for (int ai = 1; ai < NA; ++ai) {
            for (int r = FARM_ANCHOR_R_MIN; r <= FARM_ANCHOR_R_MAX; ++r) {
                const double rMaxD = std::sqrt((double)((r + 2) * (r + 2) + r * r));
                double lb = dAT[ai] - rMaxD;
                if (lb < 0) lb = 0;
                if (lb * lb > bestD2) continue;
                ringOf(anchors[ai].first, anchors[ai].second, r, useBlack);
            }
        }
    }'''
NEW3 = '''        // ---- 第 1 段：TC 环（主锚点；评分基准 = 到 TC）----
        //   r 层候选到 TC 的最小距离恰为 r（nx==ax 时 Δx=0、Δy=r）⇒ 一旦 r² 超过当前最优，
        //   本层及所有更外层都不可能更优，直接 break。
        for (int r = FARM_ANCHOR_R_MIN; r <= FARM_ANCHOR_R_MAX; ++r) {
            if ((double)r * (double)r > bestD2) break;
            ringOf(anchors[0].first, anchors[0].second, r, useBlack, 0);
        }
        if (bx >= 0) break;                  // ★ TC 环有解 ⇒ 不碰谷仓/仓库（保通勤最优）
        // ---- 第 2 段：谷仓/仓库环（★ 仅当第 1 段彻底无解时才跑）----
        //   评分基准切换为【到该锚点】的距离（段内公平）：谷仓旁 4.0 格与 TC 旁 4.0 格等价，
        //   但两段之间不比较 ⇒ 谷仓旁只在"TC 环真的塞不下"时才被启用。
        //   ⚠ 旧代码在此用三角不等式剪枝（谷仓 dAT≈52 ⇒ lb²≈2007 远超 TC 旁 bestD2≈25）
        //     ⇒ 该段恒被剪空，这正是 09-15 实测"谷仓旁 0 座农场"的成因。
        //     改用"仅当第 1 段无解才进入"来控制优先级，既保住 TC 优先、又让谷仓环真正可达。
        for (int ai = 1; ai < NA; ++ai) {
            for (int r = FARM_ANCHOR_R_MIN; r <= FARM_ANCHOR_R_MAX; ++r)
                ringOf(anchors[ai].first, anchors[ai].second, r, useBlack, ai);
        }
    }'''
txt = rep(OLD3, NEW3, 'F3')

# ---------- F4a：农场调用点 + 诊断日志 ----------
OLD4 = '''        //   新逻辑把 TC 与全部已建成谷仓/仓库作为并列锚点，直接取"离最近锚点最近"的空位。
        //   全部锚点半径内都放不下时才回落到底部通用的 findBuildSite 兜底（保留原兜底能力）。
        placed = findFarmSiteBest(x, y);
    }'''
NEW4 = '''        //   新逻辑把 TC 与全部已建成谷仓/仓库作为并列锚点，直接取"离最近锚点最近"的空位。
        // ★★★ 2026-09-19 用户需求「农场只能建在谷仓和 TC 周围隔一格的地方」★★★
        //   只在 findFarmSiteBest 的【两段紧邻环】内落位：第 1 段 TC 环 → 第 2 段 谷仓/仓库环，
        //   两段都是 r = R_MIN = 4（隔 1 格）。失败即本帧不建（下方通用兜底对农场已禁用）
        //   ⇒ 不再出现 8~11 格的散落农场。
        placed = findFarmSiteBest(x, y);
        if (!placed) {
            // ★ 诊断（铁律 53：必须打印判据的输入集合规模，否则"0 输出"分不清没触发/没候选/被过滤）
            static int lastFarmRingLog = -9999;
            if (frame - lastFarmRingLog >= 300) {
                lastFarmRingLog = frame;
                int nFarm = 0, nGr = 0, nSt = 0;
                for (auto &b : info.buildings) {
                    if (b.Type == BUILDING_FARM) nFarm++;
                    else if (b.Type == BUILDING_GRANARY && b.Percent >= 100) nGr++;
                    else if (b.Type == BUILDING_STOCK   && b.Percent >= 100) nSt++;
                }
                DebugText(QString("[FARM-RING f=%1] 锚点紧邻环无空位 farms=%2/%3 谷仓=%4 仓库=%5 ⇒ 本帧不建")
                          .arg(frame).arg(nFarm).arg(MAX_FARMS).arg(nGr).arg(nSt));
            }
        }
    }'''
txt = rep(OLD4, NEW4, 'F4a')

# ---------- F4b：禁用农场通用兜底 ----------
OLD5 = '''    // ★ 2026-09-15 农场兜底：额外要求"与已有农场不相邻"，守 isFarmAdjacent 的隔 1 格设计
    if (!placed) placed = findBuildSite(x, y, size, buildingType == BUILDING_FARM);'''
NEW5 = '''    // ★★★ 2026-09-19 用户需求「农场只能建在谷仓和 TC 周围隔一格的地方」⇒ 农场【禁用】通用兜底。
    //   旧行为：findFarmSiteBest 失败后回落到 findBuildSite(avoidFarmAdjacent=true)，而后者只要
    //   地图上还有空位就恒返回 true ⇒ 农场会落到任意远处（实测 30.3% 掉在 r=8 = 8~11.3 格）。
    //   现在农场只在锚点紧邻环内落位；两段都无解 ⇒ 本帧不建（下一帧有空位时自然重试）。
    if (!placed && buildingType != BUILDING_FARM)
        placed = findBuildSite(x, y, size, false);'''
txt = rep(OLD5, NEW5, 'F4b')

out = txt.encode('utf-8')
print('原始 %d 字节 / %d 行' % (len(raw), raw.count(b'\r\n')))
print('新版 %d 字节 / %d 行' % (len(out), out.count(b'\r\n')))
print('差异 %+d 行' % (out.count(b'\r\n') - raw.count(b'\r\n')))
if DRY:
    print('--- DRY RUN，未写入 ---')
else:
    open(PATH, 'wb').write(out)
    print('已写入')
