#!/bin/bash
# kb = kiting balance 验证批（迟滞带修正 + 撤退冷静期）
# 基线对照：gi 批 24 局（464c0796 / 未改 kiting）
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in $(seq 1 24); do
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile kb${i}.jsonl -AITextLog kb${i}.ait > /dev/null 2>&1
  echo "kb${i}: exit=$?"
done
echo "=== kb 批次完成 ==="
