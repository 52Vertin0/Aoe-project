#!/bin/bash
# 2026-09-27 s1 批：验证"主线程代取快照"自救恢复后机制是否真在跑
# 判据：ait 中 [SNAP f=...] main>0 且 fallback=0 且 skip 低；胜负与历史一致
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
PAR="${PAR:-4}"
echo "=== s1 批次开始 $(date +%H:%M:%S) ==="
echo "UsrAI.cpp md5 $(md5sum UsrAI.cpp | cut -c1-8)  exe $(ls -la --time-style=+%m-%d_%H:%M release/newAOE.exe | awk '{print $6}')"
rm -f s1*.ait s1*.jsonl 2>/dev/null
{ for i in 1 2 3 4; do printf 's1%02d map2.njust\n' "$i"; done
} | xargs -P "$PAR" -n 2 bash -c '
  tag="$1"; map="$2"
  : > "${tag}.jsonl"; : > "${tag}.ait"
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map "${map}" -rotate 90 \
    -ResultLogFile "${tag}.jsonl" -AITextLog "${tag}.ait" > /dev/null 2>&1
  echo "${tag} exit=$? $(date +%H:%M:%S)"
' _
echo "=== s1 完成 $(date +%H:%M:%S) ==="
