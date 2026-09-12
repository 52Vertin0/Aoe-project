#!/bin/bash
# ============================================================================
# 2026-09-27 i1 批次 —— 反攻期「祭司被锁定即后撤」(LOCK-FLEE) 24 局验证
#
# 改动：managePriest 内、感化分支【之前】新增闸：
#   inCounter && lockers >= PRIEST_COUNTER_LOCK_FLEE(1) ⇒ priestFlee 后撤(优先于感化推进)
#   lockers = info.enemy_armies 中 WorkObjectSN==priestSN 的敌数(与护驾 priestAttackerSN 同判据)
#   ⚠ 必须放感化前：感化无条件最高优先且两子分支均 return ⇒ 放后面是死码
#
# 对照基线 g1(无闸, n=24)：胜 16/负 7/未决 1 = 66.7%；祭司死亡 7、早死 1
# 本批看：① 胜负三率 ② 祭司死亡/早死 ③ [PRIEST LOCK-FLEE] 触发频率(是否触发过频=削弱进攻)
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1

echo "=== i1 批次开始 $(date +%H:%M:%S) ==="
for i in $(seq 1 24); do
  tag=$(printf "i1%02d" $i)
  : > ${tag}.jsonl 2>/dev/null
  : > ${tag}.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile ${tag}.jsonl -AITextLog ${tag}.ait > /dev/null 2>&1
  echo "${tag}: exit=$? $(date +%H:%M:%S)  lastframe=$(tail -1 ${tag}.ait 2>/dev/null | cut -d'|' -f2 | tr -d ' ')"
done
echo "=== i1 批次完成 $(date +%H:%M:%S) ==="
