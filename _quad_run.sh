#!/bin/bash
# ============================================================================================
# 四图并行矩阵跑局（每张地图稳定胜利的基线测量）
#   用法: MAPS="map.njust map1.njust" ROT=0 N=12 PAR=8 TAG=base bash _quad_run.sh
#   产出: ${TAG}_<map>_<rot>_<i>.ait  （AIText 全文，含 [BEAT] 行）
#   安全: 每局独立 -AITextLog 路径；不 mv exe（并行会竞争）
# ============================================================================================
set -u
cd /c/new-aoe3.0.7g || exit 1

MAPS=${MAPS:-"map.njust map1.njust map2.njust map3.njust"}
ROT=${ROT:-0}
N=${N:-12}
PAR=${PAR:-8}
TAG=${TAG:-base}
TMO=${TMO:-420}

export QT_QPA_PLATFORM=offscreen
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:$PATH"

run_one() {
  local map="$1" rot="$2" i="$3" tag="$4"
  local stem="${tag}_${map%.njust}_r${rot}_${i}"
  rm -f "${stem}.ait"
  /usr/bin/timeout "${TMO}" ./release/newAOE.exe -exam -offscreen -freq MAX \
      -map "$map" -rotate "$rot" \
      -AITextLog "$(pwd)/${stem}.ait" \
      > "${stem}.out" 2> "${stem}.err"
  local rc=$?
  local n=$([ -f "${stem}.ait" ] && wc -l < "${stem}.ait" || echo 0)
  echo "done $stem exit=$rc lines=$n"
}

for map in $MAPS; do
  for i in $(seq 1 "$N"); do
    run_one "$map" "$ROT" "$i" "$TAG" &
    while [ "$(jobs -rp | wc -l)" -ge "$PAR" ]; do wait -n; done
  done
done
wait
echo "all done: $TAG"
