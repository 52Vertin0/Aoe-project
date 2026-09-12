# -*- coding: utf-8 -*-
"""A3：manageBuildings 第三轮 —— 长注释压缩（保留结论与"为什么"，删过程考古）。
用「首行/末行唯一子串」定位块，避免手抄整块文本出错。
"""
P = 'UsrAI.cpp'
s = open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')
before = s
lines = s.split('\n')


def repl(name, first_sub, last_sub, new_text):
    starts = [k for k, l in enumerate(lines) if first_sub in l]
    assert len(starts) == 1, '%s: 首行匹配 %d 次' % (name, len(starts))
    i = starts[0]
    ends = [k for k in range(i, len(lines)) if last_sub in lines[k]]
    assert ends, '%s: 末行未找到' % name
    j = ends[0]
    old_n = j - i + 1
    lines[i:j + 1] = new_text.split('\n')
    print('ok %-18s 行 %d-%d (%d行) → %d行' % (name, i + 1, j + 1, old_n, new_text.count('\n') + 1))


# 1) 第二仓库预判定
repl('第二仓库预判定',
     '// ★ 第二仓库的"是否需要建"预判定：市场闸前置',
     '//   性能：单帧扫完瞪羚即止（瞪羚≤30 / 仓库≤3 / 单帧成本 O(90)）。',
     """        // ★ 第二仓库「是否需要建」的预判定：市场/靶场按此让位，避免远距瞪羚存在时被它们抢走 builtThisFrame
        //   （前置过严 → 每帧 tryBuild 失败 → 下一建筑接力 = 历史上"农场被饿死"的同源问题）。
        //   ⚠ 时机闸(WAVE2_TIME)与木材闸(BUILD_STOCK_WOOD+30)必须与下方【实际建造块】同步：旧版只有
        //     "该不该建"、没有"建不建得起"，木材卡在中间区间时市场会被永久冻结、靶场冻到 14 分钟。
        //   ⚠ gazelleAlive==0 ⇒ 恒 false，让位闸同步失效，否则会被一个永远建不出来的仓库饿死。""")

# 2) 学院
repl('学院',
     '// ★ 学院：后期/反攻核心近战兵种(方阵兵=强力近战)',
     '//     （该局农场只有 3 座）。加时代闸后时代未达即完全跳过。',
     """        // ★ 学院：后期/反攻核心近战兵种(方阵兵)。铜器后 + 兵营已建 + 【马厩已建】(前置) + 时代闸。
        //   ⚠ 时代闸必须留：引擎 buildCon 要求 BRONZEAGE，缺闸时引擎拒绝建造、而 countBuildingsExisting
        //     的 90 帧防重窗口一过就归零 ⇒ AI 沿坐标轴逐格扫描重试（o3_r180 实证连发 235 次），
        //     每次吞掉 builtThisFrame → 饿死 postW2 后续建造（该局农场只有 3 座）。
        //   ⚠ 建造时机已放宽为"后期即可"（state>=DEFENSE_WAVE3 或 frame>=WAVE3_TIME）：反攻态门槛是
        //     全军≥12 人，前期长期不足会让整条方阵兵产线空转，这正是"后期没有方阵兵"的主因之一。""")

# 3) 瞪羚群中心仓库前言
repl('瞪羚仓库前言',
     '// ====== ★★★ 瞪羚群中心仓库：全建筑最高优先级（2026-09-12 用户需求）★★★ ======',
     '//     否则猎人要空跑 50 格回老仓库交肉。',
     """    // ====== ★★★ 瞪羚群中心仓库：全建筑最高优先级（用户需求：村民打猎前先建仓库）★★★ ======
    //   ① 块放在 preW1 之前 ⇒ 抢在房屋/兵营/靶场/市场/农场之前消耗木材（本帧只能先建仓库）；
    //   ② 闸门用"TC 可猎范围内有瞪羚"而非"已经在打猎" ⇒ 仓库在猎人出发前落地，不再空跑往返；
    //   ③ 聚类只在距 TC ≤ GAZELLE_HUNT_RANGE 的瞪羚里选（与猎人选取范围一致），
    //      否则会建在"全图最密但村民根本不会去"的假群上（旧版 bug）。
    //   建的是仓库 STOCK 而非谷仓：瞪羚肉 ProductSort=HUMAN_STOCKFOOD，只能交付仓库（Building.cpp:549）。""")

# 4) 根因 A
repl('根因A(经济前置)',
     '// ★ 2026-09-13（根因 A）：rushMilitary 期间不再整块跳过"经济前置建筑"。',
     '//   铜器期肉常被优先喂军，100 肉门槛会让市场在肉低谷反复跳空。',
     """            // ★ 2026-09-13（根因 A）：rushMilitary 期间不再整块跳过"经济前置建筑"。
            //   旧版整个 else 分支被跳过 ⇒ 谷仓/市场在整个 postW1 窗口零机会，只能等 postW2(9 分钟)；
            //   而农场依赖市场、市场依赖谷仓（Development.cpp:765 / :635）⇒ 整条食物经济链被推迟。
            //   现按最低优先级放行「谷仓 → 市场」：排在兵营/靶场/房屋之后，本帧无建造令且资源够才触发。""")

# 5) 第二仓库
repl('第二仓库',
     '// ★ 第二仓库：为"距现有 Stock 均>20格的远距瞪羚群"建一座，仓库落在群中心。',
     '//     也跳过（不为 1 只离群瞪羚建 150 木仓库）。',
     """        // ★ 第二仓库：为"距现有 Stock 均 >20 格的远距瞪羚群"建一座，落在群中心。
        //   ⚠ 三要素缺一不可（旧版缺陷导致贴 TC 多建 3 座）：① MAX_STOCK 闸；② 不能每帧重发令
        //     （木材一回就再 tryBuild）；③ 必须传 prefX/prefY，否则 findBuildSite 会落回 TC 附近。
        //   ⚠ 时机闸须与 needSecondStock 预判定同步（同为 WAVE2_TIME），否则预判定为真时本块仍被挡住。""")

# 6) 第二谷仓
repl('第二谷仓',
     '// ★ 第二谷仓：为"TC 之外 ≥6 丛的远距浆果群"建一座，谷仓落在群中心（2026-09-07 用户需求）',
     '//   ⚠ 必须传 prefX/prefY（群中心块坐标），否则 tryBuild 会 fallback 到 findGranarySite 落回 TC 附近。',
     """        // ★ 第二谷仓：为"TC 之外 ≥6 丛的远距浆果群"建一座，落在群中心（用户需求 2026-09-07）。
        //   浆果 resourceSort=HUMAN_GRANARYFOOD → 只往谷仓交；远距浆果群没有就近谷仓时村民往返 40+ 格几乎没产出。
        //   前置：首座谷仓已在 + 未达 MAX_GRANARY + 木材够；!needSecondStock 让位（远距瞪羚仓库优先级更高）。
        //   ⚠ 必须传群中心块坐标，否则 tryBuild 会 fallback 回 findGranarySite 落回 TC 附近。""")

# 7) 市场让位
repl('市场让位',
     '//   ★ 2026-09-05 加前置 !needSecondStock：远距瞪羚存在 + 仓库未满时不让市场抢 builtThisFrame',
     '//     现在与靶场(1811 段)口径完全对齐——让位只在 14 分钟反攻期前有效，进入反攻期市场优先级反超。',
     """        //   ★ 让位闸 !(needSecondStock && frame < WAVE3_TIME)：远距瞪羚存在 + 仓库未满时不许市场抢
        //     builtThisFrame（修"市场先于第二仓库落地"）。⚠ 必须有时间上界：否则"远距瞪羚≥2 但仓库迟迟
        //     建不出(位置冲突)"会把市场无限期冻住；现在与靶场口径完全对齐，14 分钟反攻期后市场优先级反超。""")

# 8) 靶场让位
repl('靶场让位',
     '//   ★ 2026-09-07 加前置 !(needSecondStock && frame < WAVE3_TIME)：',
     '//       也避免"仓库位置不可建 → 靶场被永久阻塞"的死锁。',
     """        //   ★ 让位闸同市场：远距瞪羚存在 + 仓库未满时不许抢 builtThisFrame（否则第二仓库被下游接力饿死）；
        //     但只在 14 分钟(WAVE3_TIME)前让位——反攻期靶场产能优先，
        //     也避免"仓库位置不可建 → 靶场被永久阻塞"的死锁。""")

# 9) 建造者硬超时
repl('建造者硬超时',
     '// ★ 2026-09-13 建造者硬超时（总钥匙）：从本次建造令下发起，超过 BUILDER_HARD_TIMEOUT(1800帧)',
     '//   ⇒ 下游建筑被引擎前置链连锁卡死（靶场←兵营、农场←市场，见 Development.cpp:727/765）。',
     """        // ★ 建造者硬超时（总钥匙）：自本次建造令下发起超过 BUILDER_HARD_TIMEOUT(1800 帧) 仍未完工、
        //   且地基上无人施工 → 判该地基作废：percent==0 拉黑另址重建 / percent>0 仅释放登记（交孤儿抢救
        //   接手，不丢弃已投入进度）。
        //   旧逻辑只在 IDLE 累计 900 帧才超时：建造者长期 WALKING(地基不可达/被挡死) 或被改派时会永不释放
        //   ⇒ 建筑永久卡 0%，且 countBuildingsExisting 仍算它"已存在" ⇒ 下游被引擎前置链连锁卡死。""")

out = '\n'.join(lines)
open(P, 'w', encoding='utf-8', newline='').write(out.replace('\n', '\r\n'))
print('A3 done, 行数 %d → %d' % (before.count('\n'), out.count('\n')))
