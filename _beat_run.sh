#!/bin/bash
# ============================================================================================
# 本地基线跑局（[BEAT] 逐帧心跳对拍用）
#   产出：_beat_<n>.ait  = AIText.log 全文（含 [BEAT f=...] 行，OJ 侧同格式）
#         _beat_<n>.out  = stdout（[OJ-ENV] / [OJ-HB]）
#         _beat_<n>.err  = stderr
#   用法：MAP=map.njust ROT=0 N=3 bash _beat_run.sh
# ============================================================================================
set -u
cd /c/new-aoe3.0.7g || exit 1

MAP=${MAP:-map.njust}
ROT=${ROT:-0}
N=${N:-3}
TAG=${TAG:-beat}

export QT_QPA_PLATFORM=offscreen
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:$PATH"

for i in $(seq 1 "$N"); do
  rm -f "${TAG}_${i}.ait" "${TAG}_${i}.out" "${TAG}_${i}.err"
  /usr/bin/timeout "${TMO:-300}" ./release/newAOE.exe -exam -offscreen -freq MAX \
      -map "$MAP" -rotate "$ROT" \
      -AITextLog "$(pwd)/${TAG}_${i}.ait" \
      > "${TAG}_${i}.out" 2> "${TAG}_${i}.err"
  rc=$?
  a=$([ -f "${TAG}_${i}.ait" ] && wc -l < "${TAG}_${i}.ait" || echo 0)
  b=$([ -f "${TAG}_${i}.ait" ] && grep -ac "\[BEAT f=" "${TAG}_${i}.ait" || echo 0)
  echo "run $i: exit=$rc  ait_lines=$a  beat_lines=$b"
  # 跑完若 newAOE.exe 被占用没退出 ⇒ 挪开，避免下一局的链接/启动失败
  mv release/newAOE.exe "release/newAOE_occupied_b${i}.exe" 2>/dev/null
  cp -f release/newAOE_occupied_b${i}.exe release/newAOE.exe 2>/dev/null
done
echo "done."
