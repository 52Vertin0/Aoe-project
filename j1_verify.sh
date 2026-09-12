#!/bin/bash
# ============================================================================
# 2026-09-27 j1 批次 —— 反攻期「祭司自保后撤」(方案1+2) 24 局验证
#
# 改动：manageCounterAttack 在 counterPriestGuard(HALT) 之前新增 counterPriestRetreat(BL, forestGrid)：
#   距最近【敌兵】< PRIEST_COUNTER_SAFE_D(14格) ⇒ 撤到大军后方、距最近敌兵 ≥18格；跑在 HALT 前 ⇒ 不被饿死。
#   根因：HALT 一 return 就跳过 counterPriestConvert(祭司后排站位/武器厂) ⇒ g124 全期 [PRST-REAR]/ADV_SIEGE=0。
#
# 对照基线 g1(无此闸, n=24)：胜 16/负 7/未决 1 = 66.7%；祭司死亡 7、早死 1
# 本批看：① 胜负三率 ② 祭司死亡/早死 ③ [PRIEST RETREAT] 触发量 ④ [PRST-REAR]/ADV_SIEGE 是否被救活(应上升)
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1

echo "=== j1 批次开始 $(date +%H:%M:%S) ==="
for i in $(seq 1 24); do
  tag=$(printf "j1%02d" $i)
  : > ${tag}.jsonl 2>/dev/null
  : > ${tag}.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile ${tag}.jsonl -AITextLog ${tag}.ait > /dev/null 2>&1
  echo "${tag}: exit=$? $(date +%H:%M:%S)  lastframe=$(tail -1 ${tag}.ait 2>/dev/null | cut -d'|' -f2 | tr -d ' ')"
done
echo "=== j1 批次完成 $(date +%H:%M:%S) ==="
