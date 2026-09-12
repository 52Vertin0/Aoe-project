#!/bin/bash
# ============================================================================
# 2026-09-29 cy1 批 —— 「infoPtr 野指针金丝雀」冒烟验证（4 局：map2×2 + map3×2）
#
# 改动（相对 .bak_20260929_pre_canary = 7fc73965/7081）：仅 UsrAI.cpp，+61 行，UsrAI.h 不动
#   ① SnapState 加 ptrBadCount / ptrRepairCount 两个计数
#   ② 新增 g_curSnapPtr（infoPtr 最近一次合法值）+ installSnap()（被踩坏才原地重建）+ snapPtrIntact()
#   ③ refreshSnapshot 两处赋值改走 installSnap()
#   ④ processFrame 在第一次解引用 infoPtr 之前加一次指针自证
#   ⑤ [SNAP] 心跳加 ptrBad= / repair=
#
# 本批判据（**不是**胜率对照，胜率 4 局无统计意义）：
#   A. **零崩溃**：4/4 exit=0，ait 跑满到终局（末帧 >30000）
#   B. **金丝雀恒不误报**：全部 [SNAP] 行 ptrBad=0 repair=0
#      （>0 说明判据有问题——正常路径被当成"被踩坏"⇒ AI 会停摆，日志立刻可见）
#   C. **机制量无回归**：main>0（主线程代取快照仍在跑）、bad=0、skip 低、reuse 与历史同量级
#   D. 胜负与历史同量级（仅参考）
#
# 跑法：bash cy1_verify.sh
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
export QT_QPA_PLATFORM=offscreen
cd /c/new-aoe3.0.7g || exit 1

echo "=== cy1 批次开始 $(date +%H:%M:%S) ==="
echo "UsrAI.cpp md5 $(md5sum UsrAI.cpp | cut -c1-8)  exe $(ls -la --time-style=+%m-%d_%H:%M release/newAOE.exe | awk '{print $6}')"
rm -f cy1*.ait cy1*.jsonl 2>/dev/null

{ printf 'cy101 map2.njust\ncy102 map2.njust\ncy103 map3.njust\ncy104 map3.njust\n'; } | \
xargs -P 4 -n 2 bash -c '
  tag="$1"; map="$2"
  : > "${tag}.jsonl"; : > "${tag}.ait"
  timeout -k 5 300 ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map "${map}" -rotate 90 \
    -ResultLogFile "${tag}.jsonl" -AITextLog "${tag}.ait" > /dev/null 2>&1
  echo "${tag} ${map} exit=$? $(date +%H:%M:%S)"
' _

echo "=== cy1 完成 $(date +%H:%M:%S) ==="
echo "--- B 判据：金丝雀（应全 0）---"
for t in cy101 cy102 cy103 cy104; do
  n=$(grep -c "\[SNAP" ${t}.ait 2>/dev/null)
  g=$(grep -o "ptrBad=[0-9]*" ${t}.ait 2>/dev/null | grep -v "ptrBad=0" | wc -l)
  r=$(grep -o "repair=[0-9]*" ${t}.ait 2>/dev/null | grep -v "repair=0" | wc -l)
  echo "${t}: [SNAP]行=${n}  ptrBad非0=${g}  repair非0=${r}"
done
echo "--- C 判据：机制量（末行）---"
for t in cy101 cy102 cy103 cy104; do
  echo "${t}: $(grep "\[SNAP" ${t}.ait 2>/dev/null | tail -1)"
done
echo "--- D 判据：胜负 ---"
for t in cy101 cy102 cy103 cy104; do
  w=$(grep -c "win\":true" ${t}.jsonl 2>/dev/null)
  lf=$(tail -1 ${t}.ait 2>/dev/null | cut -d"|" -f2 | tr -d " ")
  v=$(grep -c "VICTORY\|DEFEAT" ${t}.ait 2>/dev/null)
  echo "${t}: win行=${w} 末帧=${lf} 胜负标记=${v}"
done
