#!/bin/bash
# 2026-09-15 dm 批次：反攻探路最简化（直达敌方基地附近目标点，删除步进/绕路）
# 观察点：①是否出现"无航点/卡死"（已无相关 DebugText）②发现→收编转化率 ③胜负 ④蒸发/异常退出
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in 1 2 3 4 5 6 7 8; do
  : > dm$i.jsonl 2>/dev/null
  : > dm$i.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile dm$i.jsonl -AITextLog dm$i.ait > /dev/null 2>&1
  echo "run$i exit=$? $(date +%H:%M:%S)"
done
echo "ALL DONE $(date +%H:%M:%S)"
