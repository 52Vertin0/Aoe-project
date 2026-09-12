#!/bin/bash
# 2026-09-16 towerhit 批次：仅复合弓兵(AT_COMPOSITE_BOWMAN)恢复直接攻击箭塔，其余射程<塔的远程兵保持不打塔。
#   对照 sz1-8（同 shrink 二进制、towerskip 全禁打塔）= 看"恢复复合弓打塔"这一有意行为变更的影响。
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in 1 2 3 4 5 6 7 8; do
  : > th$i.jsonl 2>/dev/null
  : > th$i.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile th$i.jsonl -AITextLog th$i.ait > /dev/null 2>&1
  echo "run$i exit=$? $(date +%H:%M:%S)"
done
echo "ALL DONE $(date +%H:%M:%S)"
