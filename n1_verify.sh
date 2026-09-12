#!/bin/bash
# ============================================================================
# 2026-09-27 n1 批次 —— 【map2 单图验证：探路期敌情闸】12 局
#
# 改动（本批唯一变量）：结束探路的触发 从「纯时间闸(开战/反攻)」改为「时间闸 ∨ 祭司附近(≤12格)出现敌军」
#   · UsrAI.cpp 常量 SCOUT_BREAK_ENEMY_DIST 12.0（新增）
#   · processData 内强推块新增 scoutBreakByEnemy 分支 + [SCOUT-BREAK] 日志
#   · managePriestScout 的 enemyDist 改用同一常量（等价重命名，铁律 21/26）
#   代码版本：UsrAI.cpp md5 e3fde282（exe 12:47 编译）
#
# 为什么只在 map2 跑：map2 是唯一观测到「敌人在 WAVE1_TIME(5000帧) 前截住探路祭司」的图
#   （z202 死 4165 / z203 死 3788；firstLOCK 2900/2800，Mil 全程 0，0 条 Priest st=）。
#   上一轮同图 3 局样本：0 胜 / 3 负（z201 死 39786、z202 4165、z203 3788）。
#
# 判据（项目铁律）：
#   胜 = jsonl 任一行 "win":true；负 = ait 含 "DEFEAT: Priest killed"；其余 = 未决
#   （"ALL WAVES DEFEATED!" 是反攻启动事件，非胜负）
#
# 观察指标：早死(<5000帧)局数 / 祭司死亡数 / 胜率 / [SCOUT-BREAK] 触发次数 / WAVE1 是否出现
# 并发：PAR 路（默认 8；单局 exe 约 578MB，本机 32 核 / 16GB）
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
PAR="${PAR:-8}"

echo "=== n1 批次(map2 探路期敌情闸)开始 $(date +%H:%M:%S)  PAR=$PAR ==="
echo "代码版本: UsrAI.cpp md5 $(md5sum UsrAI.cpp | cut -c1-8)  exe $(ls -la --time-style=+%m-%d_%H:%M release/newAOE.exe | awk '{print $6}')"

rm -f n1*.ait n1*.jsonl 2>/dev/null

{ for i in $(seq 1 12); do printf 'n1%02d map2.njust\n' "$i"; done
} | xargs -P "$PAR" -n 2 bash -c '
  tag="$1"; map="$2"
  : > "${tag}.jsonl" 2>/dev/null
  : > "${tag}.ait"   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map "${map}" -rotate 90 \
    -ResultLogFile "${tag}.jsonl" -AITextLog "${tag}.ait" > /dev/null 2>&1
  rc=$?
  lf=$(tail -1 "${tag}.ait" 2>/dev/null | cut -d"|" -f2 | tr -d " ")
  sbrk=$(grep -c "SCOUT-BREAK" "${tag}.ait" 2>/dev/null)
  echo "${tag} ${map} exit=${rc} $(date +%H:%M:%S) lastframe=${lf} SCOUT-BREAK=${sbrk}"
' _

echo "=== n1 批次完成 $(date +%H:%M:%S) ==="
echo "--- 落盘统计 ---"
echo "n1: ait=$(ls -1 n1*.ait 2>/dev/null | wc -l) jsonl=$(ls -1 n1*.jsonl 2>/dev/null | wc -l)"
