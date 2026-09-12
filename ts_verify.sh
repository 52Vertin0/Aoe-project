#!/bin/bash
# ts = towerstrict 验证批（敌塔全拆唯一闸）
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in 1 2 3 4 5 6 7 8; do
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile ts${i}.jsonl -AITextLog ts${i}.ait > /dev/null 2>&1
  echo "ts${i}: exit=$?"
done
