#!/bin/bash
# 2026-09-21 pd 批次：验证祭司探路不死修复（当前二进制 = woodreach + stockdup + priestdeath 全部生效）
# 主判据：祭司死亡局数下降；counterattack 期(>=21k帧) 祭司阵亡应明显减少
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16; do
  : > pd$i.jsonl 2>/dev/null
  : > pd$i.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile pd$i.jsonl -AITextLog pd$i.ait > /dev/null 2>&1
  echo "run$i exit=$? $(date +%H:%M:%S)"
done
echo "ALL DONE $(date +%H:%M:%S)"
