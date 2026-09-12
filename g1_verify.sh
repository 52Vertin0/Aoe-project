#!/bin/bash
# ============================================================================
# 2026-09-26 g1 批次(当前码6423行验证) —— 现行版（6607 行 0e26e560）机制体检臂（24 局）
#
# 现行版构成（相对 09-24 早些时候）：
#   WAVE1_TIME=5000（定案）｜MAX_FARMS=10（用户 09-24 22:55）｜删"复合弓未就绪→普通弓兜底"
#   伐木科技+复合弓块前移（用户 09-24 22:28）｜快照机制加固：shared_ptr 发布 + 删兜底直读
#   ※ 此组合**实测 0 局**（w1 批用的是不含用户自改的 exe）⇒ 本批是它的第一次实测。
#
# 本批目的：找优化方向（不是验单一改动），重点看：
#   ① 胜负总率 + 三率（胜/负/未决）
#   ② 漏斗：进反攻期 → 反攻期发感化令 → 胜
#   ③ 靶场产能：删掉普通弓兜底后，反攻期是否"一个弓兵都产不出"
#   ④ 祭司死因（最后感化目标分布）
#   ⑤ 快照机制量 main=/fallback=/skip=（加固后不得退化）
#
# 判据：胜 = jsonl **任一行** win:true（★必须扫全文件：引擎胜帧后会再写一帧 win:false）；
#       负 = AIText 含 DEFEAT: ；恒等式 胜+负+未决==n 必过。
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1

echo "=== g1 批次(当前码6423行验证)开始 $(date +%H:%M:%S) ==="
for i in $(seq 1 24); do
  tag=$(printf "g1%02d" $i)
  : > ${tag}.jsonl 2>/dev/null
  : > ${tag}.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile ${tag}.jsonl -AITextLog ${tag}.ait > /dev/null 2>&1
  echo "${tag}: exit=$? $(date +%H:%M:%S)  lastframe=$(tail -1 ${tag}.ait 2>/dev/null | cut -d'|' -f2 | tr -d ' ')"
done
echo "=== g1 批次(当前码6423行验证)完成 $(date +%H:%M:%S) ==="
