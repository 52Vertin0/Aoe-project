#!/bin/bash
# 2026-09-16 prieststrict 批次：感化武器厂收紧为【敌方士兵全灭 + 箭塔全拆】(PRIEST_SIEGE_REQUIRE_GLOBAL_CLEAR=true)
#   对照 th1-8（原局部清场版）。重点：感化次数、[SIEGE-WAIT] 计数、胜局数。
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in 1 2 3 4 5 6 7 8; do
  : > ps$i.jsonl 2>/dev/null
  : > ps$i.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile ps$i.jsonl -AITextLog ps$i.ait > /dev/null 2>&1
  echo "run$i exit=$? $(date +%H:%M:%S)"
done
echo "ALL DONE $(date +%H:%M:%S)"
