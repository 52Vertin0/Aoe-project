# -*- coding: utf-8 -*-
# 2026-09-19 需求：反攻时 27 分钟派所有农民进攻敌方基地
# 两处插入：① 常量块（COUNTER_FARMER_ATTACK*） ② manageCounterAttack 内 1.4 段（1.5 祭司护驾之前）
# 安全策略：纯 CRLF 断言 + 锚点唯一断言 + 插入后复核锚点位置
import sys

SRC = 'UsrAI.cpp'
raw = open(SRC, 'rb').read()
assert raw.count(b'\r\n') == raw.count(b'\n'), 'not pure CRLF'
text = raw.decode('utf-8')
lines = text.split('\r\n')

CONST_ANCHOR = '                                        //     已恢复。若今后再回滚，务必核对本常量。'
CODE_ANCHOR = '    snapWalkable(targetDR, targetUR);'

CONST_BLOCK = [
    '// ★★★ 2026-09-19 用户需求：「反攻时27分钟·派所有农民进攻敌方基地」★★★',
    '//   27 分钟 = 27×1500 = 40500 帧。触发后【所有】FARMERTYPE_FARMER 农民转为进攻：',
    '//   目标 = 敌方 TC(真正的"基地") > 最近的【非箭塔、非武器厂】敌建筑 > 无目标则不动。',
    '//   ⚠ 绝不把武器厂当目标 —— exam 胜条件唯一 = 祭司感化敌方武器厂，农民拆了它 = 自毁胜因',
    '//     （与 ARMY_IGNORE_SIEGE_WORKSHOP 同源语义）。',
    '//   ⚠ 与 COUNTER_ATTACK_FORCE_TIME(33000/22分) 配合：22 分军队强制反攻，27 分农民跟上。',
    '//   ⚠ 不排除 buildingFarmerType/waveBlockers 里的农民（用户要求"所有"）⇒ 未完工建筑会烂尾。',
    '#define COUNTER_FARMER_ATTACK true',
    '#define COUNTER_FARMER_ATTACK_FRAME 40500   // 27 分钟 × 1500 帧/分钟',
    '#define COUNTER_FARMER_ATTACK_GAP 90        // 同一农民的重复下发节流(帧)：防幂等判据失效时刷屏，',
    '                                            // 重发会 reset 引擎攻击关系并打断动作(铁律 14)',
]

CODE_BLOCK = [
    '',
    '    // ====== 1.4 ★ 农民总攻（27 分钟后全部农民投入进攻，2026-09-19 用户需求）======',
    '    //   刻意放在【1.5 祭司护驾】之前：护驾紧急时本函数会 return 停止推进，但"农民已出发"不该被撤回。',
    '    //   ① 目标选取：敌方 TC(真正的"基地") > 最近的【非箭塔、非武器厂】敌建筑 > 无目标则不动。',
    '    //      ⚠ 不含武器厂：exam 胜条件唯一 = 祭司感化敌方武器厂，农民把它拆了就没了胜因（与',
    '    //        ARMY_IGNORE_SIEGE_WORKSHOP 同一语义）。⚠ 不含箭塔：农民血量/射程撑不住塔火力，',
    '    //        且箭塔已由下方军队段单独处理。',
    '    //   ② 幂等 + 节流：仅当 WorkObjectSN != 目标 且距上次下发 >= GAP 帧才发令 —— 重发会 reset',
    '    //      引擎的攻击关系、打断动作（铁律 14）；GAP 是幂等判据万一失效时的兜底。',
    '    //   ③ 与经济的竞争：本函数在 manageEconomy(522) 之后跑 ⇒ 天然覆盖同帧的经济派工令；',
    '    //      跨帧不会被打回 —— 农民一旦进入攻击关系，NowState ≠ IDLE，而 assignIdleSimple 只筛空闲',
    '    //      农民 ⇒ 下帧不会再给它派采集工（铁律 43：先查"同帧谁后写"，再查"跨帧会不会被顶"）。',
    '    if (COUNTER_FARMER_ATTACK && frame >= COUNTER_FARMER_ATTACK_FRAME) {',
    '        static std::map<int, int> farmerAtkFrame;   // 农民 SN → 上次下发帧（节流）',
    '        int farmerTgtSN = -1;',
    '        tagBuilding* foeTC = findEnemyBuilding(BUILDING_CENTER);',
    '        if (foeTC) {',
    '            farmerTgtSN = foeTC->SN;',
    '        } else {',
    '            double bestTgtD = 1e18;',
    '            for (auto &b : info.enemy_buildings) {',
    '                if (b.Type == BUILDING_ARROWTOWER || b.Type == BUILDING_SIEGE) continue;',
    '                double d = calDistance((b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL, targetDR, targetUR);',
    '                if (d < bestTgtD) { bestTgtD = d; farmerTgtSN = b.SN; }',
    '            }',
    '        }',
    '        int nFarmer = 0;',
    '        for (auto &f : info.farmers) if (f.FarmerSort == FARMERTYPE_FARMER) nFarmer++;',
    '        int nEngaged = 0, nSent = 0;',
    '        if (farmerTgtSN >= 0) {',
    '            for (auto &f : info.farmers) {',
    '                if (f.FarmerSort != FARMERTYPE_FARMER) continue;',
    '                if (f.WorkObjectSN == farmerTgtSN) { nEngaged++; continue; }',
    '                if (farmerAtkFrame.count(f.SN) && frame - farmerAtkFrame[f.SN] < COUNTER_FARMER_ATTACK_GAP) continue;',
    '                HumanAction(f.SN, farmerTgtSN);',
    '                farmerAtkFrame[f.SN] = frame;',
    '                nSent++;',
    '            }',
    '        }',
    '        if (frame % 300 == 0)',
    '            DebugText(QString("[FARMER-ATK f=%1] 农民=%2 已投入=%3 本帧下发=%4 tgtSN=%5")',
    '                      .arg(frame).arg(nFarmer).arg(nEngaged).arg(nSent).arg(farmerTgtSN));',
    '    }',
]


def uniq(anchor, name):
    idx = [i for i, l in enumerate(lines) if l == anchor]
    print('%-14s 命中 %d 处 %s' % (name, len(idx), [i + 1 for i in idx]))
    assert len(idx) == 1, name
    return idx[0]


i_const = uniq(CONST_ANCHOR, 'CONST_ANCHOR')
i_code = uniq(CODE_ANCHOR, 'CODE_ANCHOR')
print('锚点行: const=%d code=%d' % (i_const + 1, i_code + 1))
assert i_const < i_code

if '--dry' in sys.argv:
    print('DRY RUN：将插入 常量 %d 行 + 代码 %d 行' % (len(CONST_BLOCK), len(CODE_BLOCK)))
    sys.exit(0)

new = lines[:i_const + 1] + CONST_BLOCK + lines[i_const + 1:]
i_code2 = i_code + len(CONST_BLOCK)
assert new[i_code2] == CODE_ANCHOR, 'code anchor shifted unexpectedly'
new = new[:i_code2 + 1] + CODE_BLOCK + new[i_code2 + 1:]

open(SRC, 'wb').write('\r\n'.join(new).encode('utf-8'))
print('OK: %d -> %d 行 (常量 +%d, 代码 +%d)' % (len(lines) - 1, len(new) - 1, len(CONST_BLOCK), len(CODE_BLOCK)))
