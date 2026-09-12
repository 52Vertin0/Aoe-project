#!/bin/bash
# 2026-09-20 方案 B【Tier-2 推进偏置】验证批次（t2_1..t2_8）
# 验收三件套：
#   ① [TOWER-APPROACH] 必须出现（否则 Tier-2 分支没跑到）
#   ② [TOWER-CHANCE] 末行的 Tier2偏置 必须 ≠ 0 且随帧递增（累计计数器在涨）
#   ③ [TOWER-TGT] 覆盖率应较基线（复合弓兵 56%）上升
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in 1 2 3 4 5 6 7 8; do
  : > t2_$i.jsonl 2>/dev/null
  : > t2_$i.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile t2_$i.jsonl -AITextLog t2_$i.ait > /dev/null 2>&1
  echo "run$i exit=$? $(date +%H:%M:%S)"
done
echo "ALL DONE $(date +%H:%M:%S)"
