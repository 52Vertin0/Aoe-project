#!/bin/bash
set -u
cd /c/new-aoe3.0.7g || exit 1
MAPS=${MAPS:-"map.njust"}
ROT=${ROT:-0}
N=${N:-48}
PAR=${PAR:-8}
TAG=${TAG:-base}
TMO=${TMO:-420}
EXE=${EXE:-./release/newAOE.exe}
export QT_QPA_PLATFORM=offscreen
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:$PATH"
run_one() {
  local map="$1" rot="$2" i="$3" tag="$4"
  local stem="${tag}_${map%.njust}_r${rot}_${i}"
  rm -f "${stem}.ait"
  /usr/bin/timeout "${TMO}" ${EXE} -exam -offscreen -freq MAX \
      -map "$map" -rotate "$rot" \
      -AITextLog "$(pwd)/${stem}.ait" \
      > "${stem}.out" 2> "${stem}.err"
  local rc=$?
  local n=$([ -f "${stem}.ait" ] && wc -l < "${stem}.ait" || echo 0)
  echo "done $stem exit=$rc lines=$n"
}
for map in $MAPS; do
  for i in $(seq "$I0" "$I1"); do
    run_one "$map" "$ROT" "$i" "$TAG" &
    while [ "$(jobs -rp | wc -l)" -ge "$PAR" ]; do wait -n; done
  done
done
wait
echo "all done: $TAG"