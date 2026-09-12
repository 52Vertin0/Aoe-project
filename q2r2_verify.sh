#!/bin/bash
# ============================================================================
# 2026-09-27 q2/r2 批次 —— 【祭司推进脱困】补样（map2 +12 → n=36；map3 +24 → n=36）
#
# 代码版本：UsrAI.cpp md5 4bf8f9a0·6700 / UsrAI.h 78b64ea7·402（exe 14:32:22）
# 目的：
#   · map2：q1(24) = 21胜/3负/0未决 = 87.5% ⇒ 再 12 局把样本推到 36，收窄置信区间
#   · map3：r1(12) = 5胜/4负/3未决 = 41.7%（vs n8/n3 的 58.3%）⇒ 补 24 局，
#     判定 41.7% 是【方差】还是【真回归】。关键旁证：r1 的所有失败局 `[PRIEST-ESCAPE]` 均为 0 次
#     ⇒ 脱困从未触发 ⇒ 不可能由本次改动引起（只可能是方差 / 建造者保护在 map3 的遗留问题）。
# 判据（项目铁律）：胜 = jsonl 任一行 "win":true；负 = ait 含 "DEFEAT:"；其余 = 打满 45000 = 未决
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
PAR="${PAR:-8}"

echo "=== q2/r2 批次开始 $(date +%H:%M:%S)  PAR=$PAR ==="
echo "代码版本: UsrAI.cpp md5 $(md5sum UsrAI.cpp | cut -c1-8)  exe $(ls -la --time-style=+%m-%d_%H:%M release/newAOE.exe | awk '{print $6}')"

rm -f q2*.ait q2*.jsonl r2*.ait r2*.jsonl 2>/dev/null

{ for i in $(seq 1 12); do printf 'q2%02d map2.njust\n' "$i"; done
  for i in $(seq 1 24); do printf 'r2%02d map3.njust\n' "$i"; done
} | xargs -P "$PAR" -n 2 bash -c '
  tag="$1"; map="$2"
  : > "${tag}.jsonl" 2>/dev/null
  : > "${tag}.ait"   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map "${map}" -rotate 90 \
    -ResultLogFile "${tag}.jsonl" -AITextLog "${tag}.ait" > /dev/null 2>&1
  rc=$?
  es=$(grep -c "PRIEST-ESCAPE" "${tag}.ait" 2>/dev/null)
  echo "${tag} ${map} exit=${rc} $(date +%H:%M:%S) ESCAPE=${es}"
' _

echo "=== q2/r2 完成 $(date +%H:%M:%S) ==="
echo "q2: ait=$(ls -1 q2*.ait 2>/dev/null | wc -l)  r2: ait=$(ls -1 r2*.ait 2>/dev/null | wc -l)"
echo "exe 时间(跑后核对): $(ls -la --time-style=+%m-%d_%H:%M:%S release/newAOE.exe | awk '{print $6}')"
