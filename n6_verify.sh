#!/bin/bash
# ============================================================================
# 2026-09-27 n6 批次 —— 【map2 验证：建造者保护】12 局
#
# 改动（本批唯一变量）：assignIdleSimple 内两处"挪岗"路径补 buildingFarmerType 保护
#   · GOLD-REBAL 段（按帧把食物工转采金）  → 加 `if (buildingFarmerType.count(f.SN)) continue;`
#   · 资源达上限回撤段（woodStop/stoneStop/goldRich/foodStop 挪岗）→ 同上
#   代码版本：UsrAI.cpp md5 3a624749（exe 13:51 编译）；备份 bak_20260927_builder_guard_UsrAI.cpp
#
# 根因（n1~n5 诊断）：建造者 WALKING 去工地途中，因 WorkObjectSN 被引擎长期保留为"上次目标"
#   而被 GOLD-REBAL 判成食物工、抢去采金 ⇒ 房子 percent 恒 0 ⇒ BUILDER_HARD_TIMEOUT(1800) 超时作废
#   ⇒ 反复重建失败 ⇒ 人口上限上不去 ⇒ Mil 卡 7~14 ⇒ 从未前出感化武器厂 ⇒ 打满 45000 = 未决。
#   实证：n201 BUILDER-HARD=141 次（Mil 卡 10）、胜局 n206/g101 = 0 次（Mil 27）。
#
# 观察指标（本批重点）：
#   ① [BUILDER-HARD] 次数   —— 期望大幅下降/归零（② 类局原为 48~141）
#   ② Mil 峰值              —— 期望 ② 类局从 7~14 抬升（胜局约 25.8）
#   ③ 胜率 / 未决            —— 对照 n5（45 格基线：7胜/4负/1未决 = 58.3%）
#
# 判据（项目铁律）：
#   胜 = jsonl 任一行 "win":true；负 = ait 含 "DEFEAT: Priest killed"；其余 = 未决
# 并发：PAR 路（默认 8；单局 exe 约 578MB，本机 32 核 / 16GB）
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
PAR="${PAR:-8}"

echo "=== n6 批次(map2 建造者保护)开始 $(date +%H:%M:%S)  PAR=$PAR ==="
echo "代码版本: UsrAI.cpp md5 $(md5sum UsrAI.cpp | cut -c1-8)  exe $(ls -la --time-style=+%m-%d_%H:%M release/newAOE.exe | awk '{print $6}')"

rm -f n6*.ait n6*.jsonl 2>/dev/null

{ for i in $(seq 1 12); do printf 'n6%02d map2.njust\n' "$i"; done
} | xargs -P "$PAR" -n 2 bash -c '
  tag="$1"; map="$2"
  : > "${tag}.jsonl" 2>/dev/null
  : > "${tag}.ait"   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map "${map}" -rotate 90 \
    -ResultLogFile "${tag}.jsonl" -AITextLog "${tag}.ait" > /dev/null 2>&1
  rc=$?
  lf=$(tail -1 "${tag}.ait" 2>/dev/null | cut -d"|" -f2 | tr -d " ")
  bh=$(grep -c "BUILDER-HARD" "${tag}.ait" 2>/dev/null)
  mm=$(grep -oE "Mil:[0-9]+" "${tag}.ait" 2>/dev/null | cut -d: -f2 | sort -n | tail -1)
  echo "${tag} ${map} exit=${rc} $(date +%H:%M:%S) lastframe=${lf} BUILDER-HARD=${bh} MilMax=${mm}"
' _

echo "=== n6 批次完成 $(date +%H:%M:%S) ==="
echo "n6: ait=$(ls -1 n6*.ait 2>/dev/null | wc -l) jsonl=$(ls -1 n6*.jsonl 2>/dev/null | wc -l)"
