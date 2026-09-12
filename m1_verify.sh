#!/bin/bash
# ============================================================================
# 2026-09-27 m1 批次 —— 「祭司不理会敌方农民」24 局验证
#
# 改动（9 处，全在 managePriest 内）：
#   ① findConvertTarget 兜底档（最近敌方村民）→ return -1
#   ② chkThreat 不再把敌农民计入 threatDist
#   ③ nearestE 口径改为 敌方军队 + 敌箭塔（不含敌农民）
#   ④ locateNearest 逃跑远离点去掉敌农民
#   ⑤ 感化目标坐标回填去掉敌农民分支
#   ⑥ occupiedLanding（落点被占）去掉敌农民 4 格
#   ⑦ healLandingOk（治疗落点）去掉敌农民 2 格
#   ⑧ moveAdjacentToAlly fallback 空广度去掉敌农民
#   ⑨ priestFlee 推力去掉敌农民（原"仅避免贴脸"）
#
# 对照基线 g1(改动前, n=24)：胜 16/负 7/未决 1 = 66.7%；祭司死亡 7、早死 1
# 本批看：① 胜负三率 ② 祭司死亡/早死 ③ 祭司在敌农民附近的异常(卡死/落点重发) ④ 胜路 ADV_SIEGE/CONV
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1

echo "=== m1 批次开始 $(date +%H:%M:%S) ==="
for i in $(seq 1 24); do
  tag=$(printf "m1%02d" $i)
  : > ${tag}.jsonl 2>/dev/null
  : > ${tag}.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile ${tag}.jsonl -AITextLog ${tag}.ait > /dev/null 2>&1
  echo "${tag}: exit=$? $(date +%H:%M:%S)  lastframe=$(tail -1 ${tag}.ait 2>/dev/null | cut -d'|' -f2 | tr -d ' ')"
done
echo "=== m1 批次完成 $(date +%H:%M:%S) ==="
