#!/bin/bash
# ============================================================================
# 2026-09-28 【加固层拆分 + commitInstruction】验证批
#
# 验证目标：
#   ① 加固层 UsrAICore 拆分后 AI 行为是否与拆分前一致（胜负口径）
#   ② commitInstruction 的动态指针体检是否真的拦到东西 → ait 里搜 [INS-BAD]
#   ③ 快照机制是否照常工作 → [SNAP] / [ENV] / [DIRTY-SNAP]
#
# ⚠ 2026-09-28 重要修复：本机 PATH 里 /c/Users/ZhuanZ/.local/bin/env 是个
#   328 字节的 shell 脚本（往 PATH 加 ~/.local/bin），**不支持 `env VAR=val cmd`**，
#   而它排在 /usr/bin 之前 ⇒ 原脚本 `timeout ... env QT_QPA_PLATFORM=offscreen exe`
#   会被它接走并静默退出（exit=0、产物 0 字节）。
#   故本脚本一律用 `export`，绝不用 `env` 前缀。
#
# ⚠ 7g 引擎支持 -AITextLog（DebugText 无条件落盘，在 IsExamining 闸之前）
#   ⇒ 是唯一能看到 [INS-BAD] / [SNAP] 的通道。
#
# 用法： MAP=map2.njust N=4 TAG=v1 bash ins_verify.sh
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:$PATH"
export QT_QPA_PLATFORM=offscreen

cd /c/new-aoe3.0.7g || exit 1
N="${N:-4}"
PAR="${PAR:-4}"
MAP="${MAP:-map2.njust}"
TAG="${TAG:-v}"
TMO="${TMO:-300}"

echo "=== [INS-BAD] 验证批开始 $(date +%H:%M:%S)  地图=$MAP N=$N PAR=$PAR TAG=$TAG ==="
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
  # 判胜：jsonl 里 "win":true 出现即 WIN
  if grep -q "\"win\":true" "${tag}.jsonl" 2>/dev/null; then res=WIN
  else
    last=$(tail -1 "${tag}.jsonl" 2>/dev/null | grep -o "\"frame\":[0-9]*" | head -1 | cut -d: -f2)
    if [ -n "$last" ] && [ "$last" -ge 44000 ]; then res=UND; else res=LOSS; fi
  fi
  echo "${tag} exit=${rc} jsonl=${jb} ait=${ab} ${res}"
' _

echo "=== 结果 $(date +%H:%M:%S) ==="
rm -f "${TAG}"*.tmp 2>/dev/null
echo "--- 加固层机制日志汇总（来自 ait）---"
for k in "INS-BAD" "SNAP f=" "ENV" "DIRTY-SNAP"; do
  printf "%-14s 命中文件数=%s 总行数=%s\n" "$k" \
    "$(grep -l "$k" "${TAG}"[0-9][0-9].ait 2>/dev/null | wc -l)" \
    "$(grep -h "$k" "${TAG}"[0-9][0-9].ait 2>/dev/null | wc -l)"
done
echo "--- [INS-BAD] 样例（最多 6 条）---"
grep -h "INS-BAD" "${TAG}"[0-9][0-9].ait 2>/dev/null | head -6
echo "--- [SNAP] 样例（最多 3 条）---"
grep -h "SNAP f=" "${TAG}"[0-9][0-9].ait 2>/dev/null | head -3
echo "=== 完成 $(date +%H:%M:%S) ==="
