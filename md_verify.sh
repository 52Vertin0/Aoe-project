#!/bin/bash
# 2026-09-15 mcslim 批次：manageCounterAttack 去重 + 删死变量（行为中性重构）
# 对照 sb 批次（同基线、未重构）：验证"结构改动不改变行为"——
#   观察点：①胜负/结局 ②祭司起手/收编 ③[SIEGE-HOLD] ④[KIT-R]/[KIT-S] ⑤HumanMove 千帧率 ⑥有无崩溃
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in 1 2 3 4 5 6 7 8; do
  : > md$i.jsonl 2>/dev/null
  : > md$i.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile md$i.jsonl -AITextLog md$i.ait > /dev/null 2>&1
  echo "run$i exit=$? $(date +%H:%M:%S)"
done
echo "ALL DONE $(date +%H:%M:%S)"
