#!/bin/bash
# ============================================================================
# 2026-09-26 h3 批次 —— 方案A'（祭司前出闸：反攻期 或 30格内≥2护卫兵）
#
# 背景：方案A（全局 army>=3）实测无效——所有死亡局全局 army 都≥3，但兵都在前线、
#       距祭司>30格 ⇒ [PRIEST GUARD] cmds=0 无兵可护 ⇒ 集火死。
# 本批（h3，24局）目的：量化方案A'是否真的减少祭司早死：
#   ① 胜负三率（胜/负/未决）
#   ② 祭司早死局数（DEFEAT: Priest killed 且死前未进反攻期）
#   ③ [PRIEST-NOADV] 触发次数（应比方案A更多、更精准卡在"身边无兵"时）
#   ④ 对照 h2（方案A，24局）：死亡 7 → 期望 <7，显著更好则采纳
#
# 判据：胜 = jsonl 任一行 win:true（须扫全文件）；负 = AIText 含 DEFEAT:
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1

echo "=== h3 批次开始 $(date +%H:%M:%S) ==="
for i in $(seq 1 24); do
  tag=$(printf "h3%02d" $i)
  : > ${tag}.jsonl 2>/dev/null
  : > ${tag}.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile ${tag}.jsonl -AITextLog ${tag}.ait > /dev/null 2>&1
  echo "${tag}: exit=$? $(date +%H:%M:%S)  lastframe=$(tail -1 ${tag}.ait 2>/dev/null | cut -d'|' -f2 | tr -d ' ')"
done
echo "=== h3 批次完成 $(date +%H:%M:%S) ==="
