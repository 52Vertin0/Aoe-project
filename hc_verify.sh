#!/bin/bash
# housecap 验证批：MAX_HOUSES 10→12（2026-09-16）
# 跑 hc1-8，确认二进制不崩溃且 AI 会在人口压力下建到第 11/12 座房屋。
cd /c/new-aoe3.0.7g
for N in 1 2 3 4 5 6 7 8; do
  echo "=== run $N ==="
  ./release/newAOE.exe -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile hc$N.jsonl -AITextLog hc$N.ait
  echo "exit=$? run $N done"
done
echo "ALL DONE"
