#!/bin/bash
# ============================================================================
# 2026-09-27 n3 批次 —— 【map3 回归：探路半径 100→40 格】12 局
#
# 改动（本批唯一变量）：祭司探路半径 SCOUT_MAX_DIST = 40 格（原 100 格）
#   · 新增常量 SCOUT_MAX_DIST 40.0（L228）
#   · managePriestScout 内 const double SCOUT_DIST = SCOUT_MAX_DIST（L2446，原硬编码 100.0）
#   · 同时【回退】上一轮的"探路期敌情闸"(SCOUT_BREAK_ENEMY_DIST / scoutBreakByEnemy)——n1 批已证伪
#   代码版本：UsrAI.cpp md5 408e2e62（exe 12:57 编译）；备份 bak_20260927_scout40_UsrAI.cpp
#
# 依据（上一轮 n1 证据）：map2 上祭司探路 100 格直奔敌区，f≈2708 在距 TC 56 格处撞上敌 10 个单位；
#   祭司速度 ~0.5 格/秒 vs 敌方 ~1.76 格/秒(3.5 倍) ⇒ 接触后必死。限 40 格 = 与敌主力留 16 格余量。
#
# 对照：z2 批(改动前同图 3 局，0胜/3负，死 3788/4165/39786)｜n1 批(敌情闸 12 局，0胜/12负，9 局早死 3007~3477)
#
# 判据（项目铁律）：
#   胜 = jsonl 任一行 "win":true；负 = ait 含 "DEFEAT: Priest killed"；其余 = 未决
#
# 观察指标：早死(<5000帧) / 祭司死亡 / 胜率 / 祭司最远探路距离(末次 HumanMove 坐标到 TC 距离)
# 并发：PAR 路（默认 8；单局 exe 约 578MB，本机 32 核 / 16GB）
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
PAR="${PAR:-8}"

echo "=== n3 批次(map3 回归·探路半径40)开始 $(date +%H:%M:%S)  PAR=$PAR ==="
echo "代码版本: UsrAI.cpp md5 $(md5sum UsrAI.cpp | cut -c1-8)  exe $(ls -la --time-style=+%m-%d_%H:%M release/newAOE.exe | awk '{print $6}')"

rm -f n3*.ait n3*.jsonl 2>/dev/null

{ for i in $(seq 1 12); do printf 'n3%02d map3.njust\n' "$i"; done
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

echo "=== n3 批次完成 $(date +%H:%M:%S) ==="
echo "--- 落盘统计 ---"
echo "n3: ait=$(ls -1 n3*.ait 2>/dev/null | wc -l) jsonl=$(ls -1 n3*.jsonl 2>/dev/null | wc -l)"
