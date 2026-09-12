#!/bin/bash
# ============================================================================
# 2026-09-27 k1 批次 —— 取消「农民总攻」24 局验证
#
# 改动：常量 COUNTER_FARMER_ATTACK true -> false（L229）。
#   原功能（2026-09-19）：反攻 40500 帧后（27 分钟）全部农民投入进攻，
#   目标四级 = 敌 TC > 最近软目标(非箭塔/非武器厂) > 最近箭塔 > 记忆方位行军。
#   用户 2026-09-27：不用处理打敌农民 ⇒ 关闭。农民留在后方采集。
#
# 对照基线 g1(无此改动, n=24)：胜 16/负 7/未决 1 = 66.7%；祭司死亡 7、早死 1
# g1 中该功能实测：仅 3/24 局触发（g102/g107/g108），均在 41400 帧后，目标均为箭塔(kind=3)。
# 本批看：① 胜负三率 ② 祭司死亡/早死 ③ [FARMER-ATK] 应归零 ④ 农民数/经济是否改善
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1

echo "=== k1 批次开始 $(date +%H:%M:%S) ==="
for i in $(seq 1 24); do
  tag=$(printf "k1%02d" $i)
  : > ${tag}.jsonl 2>/dev/null
  : > ${tag}.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile ${tag}.jsonl -AITextLog ${tag}.ait > /dev/null 2>&1
  echo "${tag}: exit=$? $(date +%H:%M:%S)  lastframe=$(tail -1 ${tag}.ait 2>/dev/null | cut -d'|' -f2 | tr -d ' ')"
done
echo "=== k1 批次完成 $(date +%H:%M:%S) ==="
