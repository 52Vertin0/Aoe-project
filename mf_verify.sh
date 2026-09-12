#!/bin/bash
# ============================================================================
# 2026-09-28 【反攻推进「卡死自救活锁」修复】验证批
#
# 改动：manageCounterAttack() 内 issueMarch 自救退让 + 卡死判据
#   ① 档位(marchStuckTry)清零条件：从"距【本轮下发点】变近"改为
#      "距【最终推进目标】的净距离创新低"(marchToFinal) —— 退让必然远离最终目标，
#      故档位不再被自己的退让清零，可单调升到 2/3…档。
#   ② 退让距离硬上限 MARCH_MAX_BACK=8 格（防"一路退回 TC"）。
#   ③ 退让档位上限 MARCH_STUCK_TRY_MAX=8。
#
# 验收判据：
#   A. [MARCH-SELF] 的「其中>=2档」必须 > 0（活锁下理论恒 0）
#   B. 胜负口径零回归（对拍基线 map2 24 局 = 17胜/4负/3未决 = 70.8%）
#
# ⚠ PATH 必须同含 Qt 与 mingw；本机 /c/Users/ZhuanZ/.local/bin/env 是 328B sh 脚本、
#   不支持 `env VAR=val cmd` ⇒ 一律用 export，绝不用 env 前缀。
#
# ⚠⚠ 2026-09-29 注记（判据 A 已失效，勿再误读）：
#   现行线 `58143847` **不含** 方案2 —— 它只在 `UsrAI.cpp.bak_20260928_marchfix2`（`4b33881a`）。
#   ⇒ 判据 A（[MARCH-SELF] 的「其中>=2档」> 0）**只适用于 marchfix2 版**；
#     在现行版上跑必然 0 命中，那是"判据不适用"，**不是回归**（h3/h2 两批实测 0 命中）。
#   现行版该看的判据：`[GHOST-BLD]`（幽灵地基拉黑）＋ `[INS-BAD]`（self/obj 校验）＋ 24/24 局跑满。
# 用法： MAP=map2.njust N=24 TAG=w1 bash mf_verify.sh
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:$PATH"
export QT_QPA_PLATFORM=offscreen

cd /c/new-aoe3.0.7g || exit 1
N="${N:-24}"
PAR="${PAR:-4}"
MAP="${MAP:-map2.njust}"
TAG="${TAG:-w1}"
TMO="${TMO:-300}"

echo "=== [MARCH-FIX] 验证批开始 $(date +%H:%M:%S)  地图=$MAP N=$N PAR=$PAR TAG=$TAG ==="
echo "代码: UsrAI.cpp md5 $(md5sum UsrAI.cpp | cut -c1-8) / UsrAI.h md5 $(md5sum UsrAI.h | cut -c1-8)"
echo "exe:  $(ls -la --time-style=+%m-%d_%H:%M release/newAOE.exe | awk '{print $6, $7}')"

rm -f "${TAG}"[0-9][0-9].jsonl "${TAG}"[0-9][0-9].ait 2>/dev/null

for i in $(seq 1 "$N"); do printf '%s%02d %s\n' "$TAG" "$i" "$MAP"; done | \
xargs -P "$PAR" -n 2 bash -c '
  tag="$1"; map="$2"
  timeout -k 5 '"$TMO"' ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map "${map}" -rotate 90 \
    -ResultLogFile "${tag}.jsonl" -AITextLog "${tag}.ait" > /dev/null 2>&1
  rc=$?
  jb=$(stat -c %s "${tag}.jsonl" 2>/dev/null); ab=$(stat -c %s "${tag}.ait" 2>/dev/null)
  if grep -q "\"win\":true" "${tag}.jsonl" 2>/dev/null; then res=WIN
  else
    last=$(tail -1 "${tag}.jsonl" 2>/dev/null | grep -o "\"frame\":[0-9]*" | head -1 | cut -d: -f2)
    if [ -n "$last" ] && [ "$last" -ge 44000 ]; then res=UND; else res=LOSS; fi
  fi
  echo "${tag} exit=${rc} jsonl=${jb} ait=${ab} ${res}"
' _

echo "=== 结果 $(date +%H:%M:%S) ==="
W=$(grep -l "\"win\":true" "${TAG}"[0-9][0-9].jsonl 2>/dev/null | wc -l)
echo "胜局(WIN)=$W / $N"
echo
echo "--- [MARCH-SELF] 自救退让档位分布（每局末行）---"
for f in "${TAG}"[0-9][0-9].ait; do
  [ -f "$f" ] || continue
  last=$(grep "MARCH-SELF" "$f" 2>/dev/null | tail -1)
  if [ -n "$last" ]; then echo "$(basename "$f"): ${last##*打印：}"; fi
done
echo
echo "--- 汇总：>=2档 是否出现（验收判据 A）---"
g2=$(grep -h "MARCH-SELF" "${TAG}"[0-9][0-9].ait 2>/dev/null | sed 's/.*其中>=2档=\([0-9]*\).*/\1/' | sort -n | tail -1)
echo "全批 最高「其中>=2档」= ${g2:-无}"
echo "命中 [MARCH-SELF] 的文件数 = $(grep -l "MARCH-SELF" "${TAG}"[0-9][0-9].ait 2>/dev/null | wc -l)"
echo
echo "--- 反攻/推进相关日志计数 ---"
for k in "MARCH-SELF" "TOWER-TGT" "MARCH-Stuck" "STUCK f="; do
  printf "%-14s 命中文件数=%s 总行数=%s\n" "$k" \
    "$(grep -l "$k" "${TAG}"[0-9][0-9].ait 2>/dev/null | wc -l)" \
    "$(grep -h "$k" "${TAG}"[0-9][0-9].ait 2>/dev/null | wc -l)"
done
echo "=== 完成 $(date +%H:%M:%S) ==="
