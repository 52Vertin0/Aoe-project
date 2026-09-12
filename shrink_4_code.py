# -*- coding: utf-8 -*-
"""
shrink_4_code.py —— 第四轮：代码级去重（Tier B）
  B1  manageTechUpgrade：谷仓箭塔科技链原在 3 处/2 处各写一遍 ⇒ 收口为 2 个 lambda
  B2  findAnyFarmer：4 段前缀守卫完全相同的扫描 ⇒ 收口为 pass 循环
纪律：按"定位串 + 行数 + 首末行断言"切片，断言不含预期外代码行；强制 CRLF 写回。
"""
import io, sys

SRC = 'UsrAI.cpp'
raw = io.open(SRC, encoding='utf-8', newline='').read()
lines = raw.split('\r\n')
N = len(lines)

def find1(tok, expect=1):
    """返回含 tok 的行下标列表（0-based）。"""
    idx = [k for k, l in enumerate(lines) if tok in l]
    if len(idx) != expect:
        print('ABORT 定位失败: %r 命中 %d 次（期望 %d）' % (tok, len(idx), expect))
        for k in idx:
            print('    @%d: %s' % (k + 1, lines[k][:90]))
        sys.exit(1)
    return idx[0]

ops = []   # (start_idx, end_idx_exclusive, [new lines])

# ---------- B1a 插入 2 个 lambda ----------
i = find1('void UsrAI::manageTechUpgrade() {')
assert lines[i + 4] == '    bool done = false;', repr(lines[i + 4])
assert 'bool postBronze' in lines[i + 5], repr(lines[i + 5])
LAM = [
 '',
 '    // ★ 2026-09-20 精简：谷仓箭塔科技链收口 —— 同一判据原先在 3 处（preW3 / milUnlocked 前 / TIER2）各写一遍，',
 '    //   逐字等价 ⇒ 抽为 lambda，调用点保持原位置 + 原守卫。findBuilding 为纯查找（只读循环），',
 '    //   故 TIER2 那处把 `info.Meat >= 50` 提到外层与放在内层无行为差异，一并收口。',
 '    auto tryArrowTowerTech = [&]() {',
 '        if (!done && !towerTechResearched) {',
 '            auto g = findBuilding(BUILDING_GRANARY);',
 '            if (g && g->Project == ACT_NULL && info.Meat >= 50) {',
 '                BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWER);',
 '                towerTechResearched = true; done = true;',
 '            }',
 '        }',
 '    };',
 '    auto tryBronzeTowerUpgrade = [&]() {',
 '        if (!DISABLE_TOWER_UPGRADE && !done && !bronzeTowerUpgraded && towerTechResearched) {',
 '            auto g = findBuilding(BUILDING_GRANARY);',
 '            if (g && g->Project == ACT_NULL && info.Meat >= 120 && info.Stone >= 50) {',
 '                BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWE_UPGRADE);',
 '                bronzeTowerUpgraded = true; done = true;',
 '            }',
 '        }',
 '    };',
]
ops.append((i + 6, i + 6, LAM))          # 插在 postBronze 行之后

# ---------- B1b preW3 处的「箭塔科技 + 铜器升级」连续两块（16 行）----------
i = find1('箭塔科技提前（已解除门槛）')
assert lines[i + 1] == '    if (!done && !towerTechResearched) {', repr(lines[i + 1])
assert lines[i + 7] == '    }', repr(lines[i + 7])
assert lines[i + 8].lstrip().startswith('// 铜器箭塔升级'), repr(lines[i + 8])
assert lines[i + 15] == '    }', repr(lines[i + 15])
ops.append((i, i + 16, [
 '    // ★ 箭塔科技提前（已解除门槛）：铜器后立即可研究，不等第3波、不要求军事解锁 ★',
 '    // 铜器箭塔升级：用户要求"箭塔只用解锁就行，不用升级"→ 用 DISABLE_TOWER_UPGRADE 封禁（省120食物+50石头）',
 '    tryArrowTowerTech();',
 '    tryBronzeTowerUpgrade();',
]))

# ---------- B1c milUnlocked 分支内的箭塔科技块（7 行，8 空格缩进）----------
i = find1('        if (!done && !towerTechResearched) {')
assert lines[i + 1] == '            auto g = findBuilding(BUILDING_GRANARY);', repr(lines[i + 1])
assert lines[i + 6] == '        }', repr(lines[i + 6])
ops.append((i, i + 7, ['        tryArrowTowerTech();']))

# ---------- B1d TIER2 处的两块（17 行）----------
i = find1('// --- 谷仓：箭塔科技（解锁箭塔） ---')
assert lines[i + 1] == '    if (!done && !towerTechResearched && info.Meat >= 50) {', repr(lines[i + 1])
assert lines[i + 8] == '', repr(lines[i + 8])
assert '铜器箭塔升级' in lines[i + 9], repr(lines[i + 9])
assert lines[i + 16] == '    }', repr(lines[i + 16])
ops.append((i, i + 17, [
 '    // --- 谷仓：箭塔科技链（解锁 + 铜器升级），判据已收口到函数首的两个 lambda ---',
 '    tryArrowTowerTech();',
 '    tryBronzeTowerUpgrade();',
]))

# ---------- B2 findAnyFarmer 收口（27 行）----------
i = find1('tagFarmer* UsrAI::findAnyFarmer() {')
assert lines[i + 1].strip().startswith('for (auto &f : info.farmers) {'), repr(lines[i + 1])
assert lines[i + 25] == '    return nullptr;', repr(lines[i + 25])
assert lines[i + 26] == '}', repr(lines[i + 26])
ops.append((i, i + 27, [
 'tagFarmer* UsrAI::findAnyFarmer() {',
 '    // ★ 2026-09-20 精简：4 轮扫描（石→金→木→非空闲非战斗），轮内条件不同、前缀守卫完全一致',
 '    //   ⇒ 收口为 pass 循环。逐轮全表扫描 + 首个命中即返回 ⇒ 与原先 4 段复制逐字等价。',
 '    for (int pass = 0; pass < 4; ++pass) {',
 '        for (auto &f : info.farmers) {',
 '            if (f.FarmerSort != FARMERTYPE_FARMER) continue;',
 '            if (buildingFarmerType.count(f.SN) || waveBlockers.count(f.SN)) continue;',
 '            if (f.Resource > 0) continue;',
 '            bool hit = (pass == 0) ? (f.NowState == HUMAN_STATE_WORKING && f.ResourceSort == HUMAN_STONE)',
 '                     : (pass == 1) ? (f.NowState == HUMAN_STATE_WORKING && f.ResourceSort == HUMAN_GOLD)',
 '                     : (pass == 2) ? (f.NowState == HUMAN_STATE_WORKING && f.ResourceSort == HUMAN_WOOD)',
 '                                   : (f.NowState != HUMAN_STATE_IDLE && f.NowState != HUMAN_STATE_ATTACKING);',
 '            if (hit) return &f;',
 '        }',
 '    }',
 '    return nullptr;',
 '}',
]))

# ---------- 应用 ----------
ops.sort(key=lambda t: -t[0])
before = len(lines)
out = list(lines)
for (s, e, repl) in ops:
    out[s:e] = repl
after = len(out)
print('操作数 %d ｜ 行 %d → %d （−%d）' % (len(ops), before, after, before - after))

txt = '\r\n'.join(out)
# 完整性自检：改动前 6 处谷仓查找 = 开局即研究块1 + B1b 2 + B1c 1 + B1d 2
#   开局即研究块（带 techCooldown/early return/引擎 Project 同步）语义不同，刻意不动 ⇒ 期望剩 1 + lambda 内 2 = 3
n = txt.count('auto g = findBuilding(BUILDING_GRANARY);')
assert n == 3, '谷仓查找应为 3（开局块 1 + lambda 内 2），实际 %d' % n
n2 = txt.count('tryArrowTowerTech();')
assert n2 == 3, 'tryArrowTowerTech 调用点应为 3，实际 %d' % n2
n3 = txt.count('tryBronzeTowerUpgrade();')
assert n3 == 2, 'tryBronzeTowerUpgrade 调用点应为 2，实际 %d' % n3
assert txt.count('tryArrowTowerTech = [&]()') == 1
assert txt.count('tryBronzeTowerUpgrade = [&]()') == 1

io.open(SRC, 'w', encoding='utf-8', newline='').write(txt)
d = io.open(SRC, 'rb').read()
print('CRLF %d / LF %d（应相等）' % (d.count(b'\r\n'), d.count(b'\n')))
print('自检通过：谷仓查找 2 / arrowtower 调用 3 / bronze 调用 2')
print('WROTE OK')
