#!/bin/bash
# ============================================================================
# 2026-09-24 w1 批次 —— WAVE1_TIME 6000→5000 单行对照臂（24 局）
#
# 改动（相对 .bak_20260924_pre_w15000 = 2710f75b/6622）：仅 1 行 + 注释块
#   WAVE1_TIME 6000 -> 5000
#
# 本批目的：量化「提前 1000 帧进入战备」的胜率价值。
#   已证（_wave_pulse.py）：三波实际发动帧恒为 6001/13501/21001，与 AI 侧常量无关，
#   [5000~5999] 敌方行动帧 = 0 ⇒ 5000 不是"错值"，而是"敌实攻前 1000 帧就切进战时状态"。
#   机制面：TOOL_AGE_ARMY_TARGET (frame>=WAVE1_TIME ? 6 : 2) 提前 1000 帧升至 6；
#          EARLY_ECONOMY → 第一波防御准备 的状态切换提前 1000 帧。
#
# 对照臂：p 批(6000+P0) 3/24=12.5%｜pp 批(6000+P0+P2b) 6/24=25.0%｜cur 批(6000) 3/12=25.0%
#         旧码批(gsk+kb+kb2, 常量均 5000) 16/36=44.4%
#
# 判据：胜 = jsonl 任一行 win:true（★必须扫全文件：引擎在胜帧后会再写一帧 win:false）；
#       AIText 的 VICTORY/DEFEAT 作交叉验证；恒等式 胜+负+未决==n 必过。
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1

echo "=== w1 批次开始 $(date +%H:%M:%S) ==="
for i in $(seq 1 3); do
  tag=$(printf "sp%02d" $i)
  : > ${tag}.jsonl 2>/dev/null
  : > ${tag}.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile ${tag}.jsonl -AITextLog ${tag}.ait > /dev/null 2>&1
  echo "${tag}: exit=$? $(date +%H:%M:%S)  lastframe=$(tail -1 ${tag}.ait 2>/dev/null | cut -d'|' -f2 | tr -d ' ')"
done
echo "=== w1 批次完成 $(date +%H:%M:%S) ==="
