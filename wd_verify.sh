#!/bin/bash
# 2026-09-21 wd 批次：验证当前二进制（仓库去重轮② STOCK_ORDER_SETTLE + 樵夫可达性预检 woodreach）
# 主判据①（woodreach）：WOOD-TREE|enclosedSkipped= 的累计跳过数（应适中，非几千）；[STUCK] 计数应下降
# 主判据②（stockdup）：同群<=9 的相邻 type=3 BUILD-ISSUE 局数应下降
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16; do
  : > wd$i.jsonl 2>/dev/null
  : > wd$i.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile wd$i.jsonl -AITextLog wd$i.ait > /dev/null 2>&1
  echo "run$i exit=$? $(date +%H:%M:%S)"
done
echo "ALL DONE $(date +%H:%M:%S)"
