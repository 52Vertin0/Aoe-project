#!/bin/bash
# ============================================================================
# 2026-09-29 fw1 批 —— 「农民吸火 ⇒ 祭司跟随农民直接感化武器厂」冒烟验证
#   改动（相对 .bak_20260929_pre_fwave = f67fd89e/7142）：仅 UsrAI.cpp，+60/-13 行，UsrAI.h 不动
#     ① 新增 COUNTER_FARMER_WAVE_MIN 3（判「农民波已投入」的最少在打建筑农民数）
#     ② counterPriestConvert 内自算 farmerWaveN / farmerWaveOn（不改 .h、不引跨函数状态）
#     ③ clearOk 追加 `|| farmerWaveOn`（农民波投入即视为清场 ⇒ 塔闸放行）
#     ④ priestTooClose 在 farmerWaveOn 时置 false（解除"太靠前⇒后撤"）
#     ⑤ rear 分支跟随锚：farmerWaveOn 时 大军重心 → 农民重心
#     ⑥ `PRIEST_MIN_DIST_TARGET` 夹持在 farmerWaveOn 时跳过
#     ⑦ 可观测：LC-DBG 加 fW=；PRST-REAR 加 anchor=farmer|army + fW=；ADVANCE / converting(early) 加 fW=
#
#   本批判据：
#     A. **零回归**：跑满（末帧>30000）；[SNAP] ptrBad=0 repair=0；[INS-BAD] 累计丢弃恒 0
#     B. **新逻辑真的触发**：末帧>40500 的局里，出现 fW≥3 的 LC-DBG 行；PRST-REAR 出现 anchor=farmer
#     C. **效果**：末帧>40500 的局里，是否出现 `Priest ADVANCE to Siege` / `Priest converting`
#        （历史基线：h214/h224/h303/h311/h324 这 5 局 f>40500 后两者全为 0）
#     D. 胜负（8 局无统计意义，仅参考）
#
#   跑法：bash fw1_verify.sh
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
export QT_QPA_PLATFORM=offscreen
cd /c/new-aoe3.0.7g || exit 1

echo "=== fw1 批次开始 $(date +%H:%M:%S) ==="
echo "UsrAI.cpp md5 $(md5sum UsrAI.cpp | cut -c1-8)  exe $(ls -la --time-style=+%m-%d_%H:%M release/newAOE.exe | awk '{print $6}')"
rm -f fw1*.ait fw1*.jsonl 2>/dev/null

{ printf 'fw101 map2.njust\nfw102 map2.njust\nfw103 map2.njust\nfw104 map2.njust\n'
  printf 'fw105 map3.njust\nfw106 map3.njust\nfw107 map3.njust\nfw108 map3.njust\n'; } | \
xargs -P 8 -n 2 bash -c '
  tag="$1"; map="$2"
  : > "${tag}.jsonl"; : > "${tag}.ait"
  timeout -k 5 300 ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map "${map}" -rotate 90 \
    -ResultLogFile "${tag}.jsonl" -AITextLog "${tag}.ait" > /dev/null 2>&1
  echo "${tag} ${map} exit=$? $(date +%H:%M:%S)"
' _

echo "=== fw1 完成 $(date +%H:%M:%S) ==="
echo "--- A 判据：零回归 ---"
for t in fw101 fw102 fw103 fw104 fw105 fw106 fw107 fw108; do
  lf=$(tail -1 ${t}.ait 2>/dev/null | cut -d"|" -f2 | tr -d " ")
  g=$(grep -o "ptrBad=[0-9]*" ${t}.ait 2>/dev/null | grep -v "ptrBad=0" | wc -l)
  r=$(grep -o "repair=[0-9]*" ${t}.ait 2>/dev/null | grep -v "repair=0" | wc -l)
  ib=$(grep -o "累计丢弃=[0-9]*" ${t}.ait 2>/dev/null | grep -v "累计丢弃=0" | wc -l)
  sz=$(stat -c %s ${t}.ait 2>/dev/null)
  echo "${t}: 末帧=${lf} ait=${sz}B ptrBad非0=${g} repair非0=${r} INS-BAD丢弃非0=${ib}"
done
echo "--- B 判据：新逻辑是否触发（末帧>40500 才有意义）---"
for t in fw101 fw102 fw103 fw104 fw105 fw106 fw107 fw108; do
  fwc=$(grep -c "fW=" ${t}.ait 2>/dev/null)
  fwmax=$(grep -o "fW=[0-9]*" ${t}.ait 2>/dev/null | cut -d= -f2 | sort -n | tail -1)
  anch=$(grep -o "anchor=farmer" ${t}.ait 2>/dev/null | wc -l)
  echo "${t}: LC-DBG含fW行=${fwc} fW峰值=${fwmax:-0} anchor=farmer行=${anch}"
done
echo "--- C 判据：f>40500 后的祭司推进/感化 ---"
for t in fw101 fw102 fw103 fw104 fw105 fw106 fw107 fw108; do
  adv=$(awk -F' \\| ' '$2>40500 && /Priest ADVANCE to Siege/' ${t}.ait 2>/dev/null | wc -l)
  cvt=$(awk -F' \\| ' '$2>40500 && /Priest converting Siege Workshop/' ${t}.ait 2>/dev/null | wc -l)
  adall=$(grep -c "Priest ADVANCE to Siege" ${t}.ait 2>/dev/null)
  cvall=$(grep -c "Priest converting Siege Workshop" ${t}.ait 2>/dev/null)
  echo "${t}: >40.5k ADVANCE=${adv} converting=${cvt}   | 全局 ADVANCE=${adall} converting=${cvall}"
done
echo "--- D 判据：胜负（仅参考）---"
for t in fw101 fw102 fw103 fw104 fw105 fw106 fw107 fw108; do
  w=$(grep -c "win\":true" ${t}.jsonl 2>/dev/null)
  d=$(grep -c "DEFEAT:" ${t}.ait 2>/dev/null)
  lf=$(tail -1 ${t}.ait 2>/dev/null | cut -d"|" -f2 | tr -d " ")
  [ "$w" -gt 0 ] && v="W" || { [ "$d" -gt 0 ] && v="L" || v="U"; }
  echo "${t}: ${v} (win行=${w} DEFEAT行=${d} 末帧=${lf})"
done
