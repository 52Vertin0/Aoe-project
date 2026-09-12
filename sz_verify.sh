#!/bin/bash
# 2026-09-15 shrink 批次：四个最长函数代码精简
#   （manageBuildings A1-A3 / managePriest P1-P2 / manageMilitary M1-M2 / manageCounterAttack C1）
# 对照 tc（同基线、精简前源码所跑）：本轮为【纯重构】，红线 = 行为零变化。
#   判据：①逐局 ait 与 tc 日志是否逐行一致（确定论环境下期望完全一致）
#         ②机制量（HumanMove/HumanAction 千帧率、KIT-R、LC-DBG）③胜负/祭司阵亡
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in 1 2 3 4 5 6 7 8; do
  : > sz$i.jsonl 2>/dev/null
  : > sz$i.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile sz$i.jsonl -AITextLog sz$i.ait > /dev/null 2>&1
  echo "run$i exit=$? $(date +%H:%M:%S)"
done
echo "ALL DONE $(date +%H:%M:%S)"
