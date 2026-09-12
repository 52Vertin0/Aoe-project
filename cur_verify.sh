#!/bin/bash
# ============================================================================
# 2026-09-23 cur 批次 —— 当前二进制（UsrAI.cpp 2710f75b / 6622 行）12 局胜率
#
# 目的：给出"当前版本"的首个多局胜率读数。
# 现行 exe 含：方案 B(Tier-2 推进偏置) + OJ 快照自救(SNAP f=) + WAVE1_TIME=6000
#              + 可读性重构 + 注释同步（后两项已证 .text 逐字节不变）。
#
# ⚠ 铁律 81：12 局只读方向，不足判胜负（同码复跑 4/8 vs 2/8）。要与 kb2 批对拍
#    必须补"同源码重跑臂"。
# 判据：胜 = DebugText 带冒号的 "VICTORY! Siege Workshop converted"
#       负 = "DEFEAT: ..."      其余 = 打满 30 分钟未决
# 参考基线：vf_kb2 12 局 = 5 胜 4 负 3 未决（41.7%）
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1

echo "=== cur 批次开始 $(date +%H:%M:%S) ==="
for i in $(seq 1 12); do
  : > cur${i}.jsonl 2>/dev/null
  : > cur${i}.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile cur${i}.jsonl -AITextLog cur${i}.ait > /dev/null 2>&1
  echo "cur${i}: exit=$? $(date +%H:%M:%S)  lastframe=$(tail -1 cur${i}.ait 2>/dev/null | cut -d'|' -f2 | tr -d ' ')"
done
echo "=== cur 批次完成 $(date +%H:%M:%S) ==="
