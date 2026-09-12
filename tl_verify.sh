#!/bin/bash
# 2026-09-14 tl 批次：箭塔迟滞锁缺口修复（在基线上单独施加）
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in 1 2 3 4 5 6 7 8; do
  : > tl$i.jsonl 2>/dev/null
  : > tl$i.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile tl$i.jsonl -AITextLog tl$i.ait > /dev/null 2>&1
  echo "run$i exit=$? $(date +%H:%M:%S)"
done
echo "ALL DONE $(date +%H:%M:%S)"
