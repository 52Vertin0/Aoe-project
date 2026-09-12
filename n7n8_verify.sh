#!/bin/bash
# ============================================================================
# 2026-09-27 n7/n8 批次 —— 【建造者保护】扩样 + 跨地图回归
#
# 改动（同 n6，本批无新变量）：assignIdleSimple 内两处"挪岗"路径补 buildingFarmerType 保护
#   代码版本：UsrAI.cpp md5 3a624749（exe 13:51）；备份 bak_20260927_builder_guard_UsrAI.cpp
#
# 目的：
#   n7 = map2 再跑 12 局 → 与 n6 合并成 n=24，提高胜率检验力
#   n8 = map3 12 局      → 回归（对照 n3 基线 map3 45 格：7胜/4负/1未决 = 58.3%）
#
# 判据（项目铁律）：
#   胜 = jsonl 任一行 "win":true；负 = ait 含 "DEFEAT: Priest killed"；其余 = 未决
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
PAR="${PAR:-8}"

echo "=== n7/n8 批次开始 $(date +%H:%M:%S)  PAR=$PAR ==="
echo "代码版本: UsrAI.cpp md5 $(md5sum UsrAI.cpp | cut -c1-8)"

rm -f n7*.ait n7*.jsonl n8*.ait n8*.jsonl 2>/dev/null

{ for i in $(seq 1 12); do printf 'n7%02d map2.njust\n' "$i"; done
  for i in $(seq 1 12); do printf 'n8%02d map3.njust\n' "$i"; done
} | xargs -P "$PAR" -n 2 bash -c '
  tag="$1"; map="$2"
  : > "${tag}.jsonl" 2>/dev/null
  : > "${tag}.ait"   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map "${map}" -rotate 90 \
    -ResultLogFile "${tag}.jsonl" -AITextLog "${tag}.ait" > /dev/null 2>&1
  rc=$?
  bh=$(grep -c "BUILDER-HARD" "${tag}.ait" 2>/dev/null)
  mm=$(grep -oE "Mil:[0-9]+" "${tag}.ait" 2>/dev/null | cut -d: -f2 | sort -n | tail -1)
  echo "${tag} ${map} exit=${rc} $(date +%H:%M:%S) BUILDER-HARD=${bh} MilMax=${mm}"
' _

echo "=== n7/n8 完成 $(date +%H:%M:%S) ==="
echo "n7: ait=$(ls -1 n7*.ait 2>/dev/null | wc -l)  n8: ait=$(ls -1 n8*.ait 2>/dev/null | wc -l)"
