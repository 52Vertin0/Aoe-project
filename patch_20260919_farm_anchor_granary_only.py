# -*- coding: utf-8 -*-
"""
2026-09-19 用户需求：「农场可以建在谷仓附近，但不能建在仓库附近」
  ⇒ findFarmSiteBest 的锚点集合：TC + 【谷仓 BUILDING_GRANARY】，不再含【仓库 BUILDING_STOCK】。

改动（4 处代码 + 若干注释同步）：
  A1 锚点构造：`GRANARY || STOCK` -> 只收 `GRANARY`；新增 anchorTypes 平行数组（与 anchors 同下标）
  A2 TC 置顶排序：把类型随坐标一起搬运（原来只搬 pair，类型会错位）
  A3 FARM-PICK 日志：追加 `ty=[C,G,...]` 字段 —— 这是本次的【核心验收机制量】
     （不给类型，验收时无法区分"农场落在谷仓环"还是"落在仓库环"）
  A4 FARM-RING 诊断日志：措辞纠正（仓库不再是锚点）
用法：python patch_...py [--dry]
"""
import io
import sys

P = r'C:\new-aoe3.0.7g\UsrAI.cpp'
DRY = '--dry' in sys.argv


def rep(text, old, new, tag):
    """CRLF 归一后做唯一命中替换；命中数 != 1 直接报错。"""
    o = old.replace('\r\n', '\n').replace('\n', '\r\n')
    n = new.replace('\r\n', '\n').replace('\n', '\r\n')
    c = text.count(o)
    if c != 1:
        raise SystemExit('[FAIL] %s 命中 %d 次（期望 1）' % (tag, c))
    return text.replace(o, n)


raw = open(P, 'rb').read().decode('utf-8')

# ---------------------------------------------------------------- 头部注释
raw = rep(raw,
    '//     候选空间 = TC 环 ∪ 全部已建成【谷仓 GRANARY / 仓库 STOCK】环；',
    '//     候选空间 = TC 环 ∪ 全部已建成【谷仓 GRANARY】环（★ 2026-09-19 起不再含仓库 STOCK）；',
    'H1 候选空间')

raw = rep(raw,
    '//       TC 环半径内全满才轮到谷仓/仓库旁 = 用户原话「基地附近位置不够的话」。',
    '//       TC 环半径内全满才轮到谷仓旁 = 用户原话「基地附近位置不够的话」。',
    'H2 TC 满才轮到')

raw = rep(raw,
    '//     谷仓/瞪羚仓库旁：实测 >10 格占比 6.8%→39.2%、到 TC 中位 5.7→12.4、最大 60.8。',
    '//     谷仓旁：实测 >10 格占比 6.8%→39.2%、到 TC 中位 5.7→12.4、最大 60.8。',
    'H3 fl 证伪段')

raw = rep(raw,
    '//   ★ 座数补偿：TC 环满后吃【谷仓/仓库环】（同一 r=4 口径），见 findFarmSiteBest 第 2 段。',
    '//   ★ 座数补偿：TC 环满后吃【谷仓环】（同一 r=4 口径），见 findFarmSiteBest 第 2 段。',
    'H4 座数补偿')

raw = rep(raw,
    '#define FARM_ANCHOR_R_MAX 4      // 搜索半径上限 = R_MIN ⇒ 只允许紧邻环（2026-09-19 用户硬限制）',
    '#define FARM_ANCHOR_R_MAX 4      // 搜索半径上限 = R_MIN ⇒ 只允许紧邻环（2026-09-19 用户硬限制）\n'
    '// ★★★ 2026-09-19 用户需求追加：「农场可以建在谷仓附近，但不能建在仓库附近」★★★\n'
    '//   ⇒ 锚点集合 = TC ＋ 已建成【谷仓 GRANARY】；**仓库 STOCK 一律不作锚点**（见 findFarmSiteBest）。\n'
    '//   为什么单独排除仓库（口径，不是实现细节）：\n'
    '//     · 仓库是按【瞪羚群】布点的猎场节点（MAX_STOCK=4），为覆盖远处兽群而建，天然远离 TC 通勤圈。\n'
    '//     · 农场原地生产食物、村民从 TC 出发 ⇒ 把农场挂到仓库旁 = 把食物产出绑在远距通勤上，\n'
    '//       与"农场服务基地经济圈"的取向相反；谷仓则服务浆果群、位置在基地经济圈内。\n'
    '//   实测依据（fc 批 6 局 / 87 次落位）：两座非 TC 锚点 (13,34)/(23,32) 合计吃掉 33 次 = 37.9%，\n'
    '//     其类型由 FARM-PICK 新增的 ty= 字段给出（ty=[C,G] = 只有 TC + 谷仓）。',
    'H5 新需求块')

# ---------------------------------------------------------------- A1 锚点构造
old_a1 = '''    // ---- 锚点集合（块左下角）：TC 第一（平局优先），其后谷仓/仓库 ----
    std::vector<std::pair<int, int> > anchors;
    anchors.push_back(std::make_pair(center->BlockDR, center->BlockUR));
    for (auto &b : info.buildings) {
        if (b.Percent < 100) continue;                       // 只在【已建成】的谷仓/仓库旁扩展
        if (b.Type == BUILDING_GRANARY || b.Type == BUILDING_STOCK)
            anchors.push_back(std::make_pair(b.BlockDR, b.BlockUR));
    }'''
new_a1 = '''    // ---- 锚点集合（块左下角）：TC 第一（平局优先），其后【谷仓】 ----
    //   ★★★ 2026-09-19 用户要求：「农场可以建在谷仓附近，但不能建在仓库附近」★★★
    //     ⇒ 锚点只收 BUILDING_GRANARY(谷仓)，**不再收 BUILDING_STOCK(仓库)**。
    //   排除仓库的理由见文件头 FARM_ANCHOR_R_MAX 下方的需求块（仓库是远距猎场节点，非经济圈）。
    //   ⚠ 与 09-19 早先版本的差异：早先叫「谷仓/仓库环」，fc 批实测 (13,34)/(23,32) 两座锚点
    //     合计吃掉 33/87 = 37.9% 的农场落位 —— 本次按用户要求一并取消。
    std::vector<std::pair<int, int> > anchors;
    std::vector<int> anchorTypes;          // ★ 与 anchors 严格同下标（0=TC，其余=谷仓）—— 供 FARM-PICK 日志核对
    anchors.push_back(std::make_pair(center->BlockDR, center->BlockUR));
    anchorTypes.push_back(BUILDING_CENTER);
    for (auto &b : info.buildings) {
        if (b.Percent < 100) continue;                       // 只在【已建成】的谷仓旁扩展
        if (b.Type != BUILDING_GRANARY) continue;            // ★ 仓库 BUILDING_STOCK 已按用户要求排除
        anchors.push_back(std::make_pair(b.BlockDR, b.BlockUR));
        anchorTypes.push_back(b.Type);
    }'''
raw = rep(raw, old_a1, new_a1, 'A1 锚点构造')

# ---------------------------------------------------------------- A2 TC 置顶排序（类型同步搬运）
old_a2 = '''    if (anchors.size() > 1) {
        std::vector<std::pair<int, int> > rest(anchors.begin() + 1, anchors.end());
        std::sort(rest.begin(), rest.end());
        rest.erase(std::unique(rest.begin(), rest.end()), rest.end());
        anchors.resize(1);
        for (size_t i = 0; i < rest.size(); ++i)
            if (rest[i] != anchors[0]) anchors.push_back(rest[i]);
    }'''
new_a2 = '''    //   ★ 2026-09-19：锚点类型必须随坐标一起搬运（anchorTypes 与 anchors 严格同下标），
    //     否则排序后类型的下标会与实际锚点错位，FARM-PICK 的 ty= 字段就失去意义。
    if (anchors.size() > 1) {
        std::vector<std::pair<std::pair<int, int>, int> > rest;
        rest.reserve(anchors.size() - 1);
        for (size_t i = 1; i < anchors.size(); ++i)
            rest.push_back(std::make_pair(anchors[i], anchorTypes[i]));
        std::sort(rest.begin(), rest.end());
        rest.erase(std::unique(rest.begin(), rest.end()), rest.end());
        anchors.resize(1);
        anchorTypes.resize(1);
        for (size_t i = 0; i < rest.size(); ++i)
            if (rest[i].first != anchors[0]) {
                anchors.push_back(rest[i].first);
                anchorTypes.push_back(rest[i].second);
            }
    }'''
raw = rep(raw, old_a2, new_a2, 'A2 TC 置顶排序')

# ---------------------------------------------------------------- 顺带修正过时注释
raw = rep(raw,
    '    //   ★ 2026-09-19：base = 评分基准锚点索引（0 = TC；>=1 = 对应的谷仓/仓库）。',
    '    //   ★ 2026-09-19：base = 评分基准锚点索引（0 = TC；>=1 = 对应的谷仓）。',
    'C1 base 注释')

raw = rep(raw,
    '    //   ⇒ 谷仓/仓库旁只有在"TC 环 [R_MIN, R_MAX] 内全满"时才会胜出，',
    '    //   ⇒ 谷仓旁只有在"TC 环 [R_MIN, R_MAX] 内全满"时才会胜出，',
    'C2 谷仓仓库旁注释')

raw = rep(raw,
    '        // ---- 第 2 段：谷仓/仓库环（★ 仅当第 1 段彻底无解时才跑）----',
    '        // ---- 第 2 段：谷仓环（★ 仅当第 1 段彻底无解时才跑；仓库已按用户要求排除）----',
    'C3 第2段标题')

raw = rep(raw,
    '//   全部候选都不可用 ⇒ 返回 false，由 tryBuild 的 findBuildSite(avoidFarmAdjacent=true) 兜底。',
    '//   全部候选都不可用 ⇒ 返回 false，农场【本帧不建】（通用兜底对农场已禁用，见 tryBuild）。',
    'C4 返回 false 注释')

# ---------------------------------------------------------------- A3 FARM-PICK 加 ty= 字段
old_a3 = '''        DebugText(QString("[FARM-PICK f=%1] base=%2(%3,%4) r=%5 tcR=%6 -> (%7,%8)")
                  .arg(frame).arg(bestBase).arg(bbx).arg(bby).arg(rr).arg(tcR).arg(bx).arg(by));'''
new_a3 = '''        //   ★ ty=[...] = 本次锚点集合的类型序列（C=TC / G=谷仓 / S=仓库），与 base= 的下标一一对应；
        //     这是"农场绝不再靠仓库"的唯一直接证据 —— 只要 ty 里不出现 S，就不可能落在仓库旁。
        char tyBuf[80];
        int  tp = 0;
        for (size_t i = 0; i < anchorTypes.size() && tp < 76; ++i) {
            if (i) tyBuf[tp++] = ',';
            tyBuf[tp++] = (anchorTypes[i] == BUILDING_CENTER)  ? 'C'
                        : (anchorTypes[i] == BUILDING_GRANARY) ? 'G' : 'S';
        }
        tyBuf[tp] = '\\0';
        DebugText(QString("[FARM-PICK f=%1] base=%2(%3,%4) r=%5 tcR=%6 -> (%7,%8) ty=[%9]")
                  .arg(frame).arg(bestBase).arg(bbx).arg(bby).arg(rr).arg(tcR).arg(bx).arg(by)
                  .arg(QString::fromLatin1(tyBuf)));'''
raw = rep(raw, old_a3, new_a3, 'A3 FARM-PICK ty 字段')

# ---------------------------------------------------------------- A4 FARM-RING 措辞
raw = rep(raw,
    '锚点紧邻环无空位 farms=%2/%3 谷仓=%4 仓库=%5',
    '锚点紧邻环无空位 farms=%2/%3 谷仓锚点=%4 仓库(已排除)=%5',
    'A4 FARM-RING 措辞')

# ---------------------------------------------------------------- tryBuild 注释
raw = rep(raw,
    '        //   新逻辑把 TC 与全部已建成谷仓/仓库作为并列锚点，直接取"离最近锚点最近"的空位。',
    '        //   新逻辑把 TC 与全部已建成谷仓作为并列锚点（★ 仓库已按 2026-09-19 用户要求排除）。',
    'T1 并列锚点注释')

raw = rep(raw,
    '        //   只在 findFarmSiteBest 的【两段紧邻环】内落位：第 1 段 TC 环 → 第 2 段 谷仓/仓库环，',
    '        //   只在 findFarmSiteBest 的【两段紧邻环】内落位：第 1 段 TC 环 → 第 2 段 谷仓环，',
    'T2 两段注释')

if DRY:
    print('[DRY] 全部 12 处替换命中 1 次，未落盘')
else:
    open(P, 'wb').write(raw.encode('utf-8'))
    print('[OK] 已落盘，bytes=%d lines=%d' % (len(raw.encode('utf-8')), raw.count('\n')))
