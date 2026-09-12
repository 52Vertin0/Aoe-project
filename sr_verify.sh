#!/bin/bash
# 2026-09-20 「代码精简（注释压缩 + Tier B 去重）」验证批次（sr_1..sr_8）
# 验收：机制量与 t2 批同口径（该版本 = t2 版 + 纯注释压缩 + 纯去重，行为应等价）
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in 1 2 3 4 5 6 7 8; do
  : > sr_$i.jsonl 2>/dev/null
  : > sr_$i.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile sr_$i.jsonl -AITextLog sr_$i.ait > /dev/null 2>&1
  echo "run$i exit=$? $(date +%H:%M:%S)"
done
echo "ALL DONE $(date +%H:%M:%S)"
