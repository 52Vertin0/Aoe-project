#!/bin/bash
# 2026-09-15 sb 批次：卡死最小脱困（stuckTry>0 时朝集结 TC 内缩 stuckTry 格重发）
# 对照 dm 批次（无脱困）；观察点：①胜负 ②祭司死 ③真卡死（同点重发条数占比）④HumanMove/千帧
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in 1 2 3 4 5 6 7 8; do
  : > sb$i.jsonl 2>/dev/null
  : > sb$i.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile sb$i.jsonl -AITextLog sb$i.ait > /dev/null 2>&1
  echo "run$i exit=$? $(date +%H:%M:%S)"
done
echo "ALL DONE $(date +%H:%M:%S)"
