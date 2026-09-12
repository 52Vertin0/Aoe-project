#!/bin/bash
# ============================================================================
# 2026-09-27 m1b —— m1 批续跑（因会话终止，m1 停在 m112，此处补 m113~m124）
# 代码版本与 m1 相同（UsrAI.cpp md5 应 = 581c1437）
# 地图 map3.njust（与 m1 一致），PAR 路并发
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
PAR="${PAR:-8}"

echo "=== m1b(续跑 m113~m124) 开始 $(date +%H:%M:%S) PAR=$PAR ==="
echo "代码版本: UsrAI.cpp md5 $(md5sum UsrAI.cpp | cut -c1-8)"

{ for i in $(seq 13 24); do printf 'm1%02d map3.njust\n' "$i"; done
} | xargs -P "$PAR" -n 2 bash -c '
  tag="$1"; map="$2"
  : > "${tag}.jsonl" 2>/dev/null
  : > "${tag}.ait"   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map "${map}" -rotate 90 \
    -ResultLogFile "${tag}.jsonl" -AITextLog "${tag}.ait" > /dev/null 2>&1
  rc=$?
  lf=$(tail -1 "${tag}.ait" 2>/dev/null | cut -d"|" -f2 | tr -d " ")
  echo "${tag} ${map} exit=${rc} $(date +%H:%M:%S) lastframe=${lf}"
' _

echo "=== m1b 完成 $(date +%H:%M:%S) ==="
echo "m1 全批 ait 数: $(ls -1 m1*.ait 2>/dev/null | wc -l) / 24"
