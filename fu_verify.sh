#!/bin/bash
# 2026-09-20 fu 批次：仓库重复建造修复（STOCK_ORDER_SETTLE + 覆盖锚点去掉 Percent==100）验证
# 主判据：同一群是否还被建 2 座（相邻两条 type=3 BUILD-ISSUE 的块距 <=9 的局数）
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16; do
  : > fu$i.jsonl 2>/dev/null
  : > fu$i.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile fu$i.jsonl -AITextLog fu$i.ait > /dev/null 2>&1
  echo "run$i exit=$? $(date +%H:%M:%S)"
done
echo "ALL DONE $(date +%H:%M:%S)"
