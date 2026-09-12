#!/bin/bash
# ============================================================================
# 2026-09-27 z 批次 —— 【跨地图胜率矩阵】4 地图 × 3 局 = 12 局（用户 11:26 指定每图 3 局）
#
# ⚠ n=3/图 仅作快速探样，无统计效力（不能据此判定地图难度差异）。
#
# 地图（文件名 → 本次标签前缀）：
#   map.njust   (视作 map0) → z0   局号 z001~z024
#   map1.njust              → z1   局号 z101~z124
#   map2.njust              → z2   局号 z201~z224
#   map3.njust              → z3   局号 z301~z324
#
# 代码版本：与 m1 批同源（UsrAI.cpp md5 581c1437；exe 11:05 编译）
#   ⇒ 全矩阵同一份代码，唯一变量 = 地图。
#
# 判据（沿用项目铁律）：
#   胜 = jsonl **任一行** "win":true（必须扫全文件：胜帧后引擎还会再写一帧 win:false）
#   负 = ait 含 "DEFEAT: Priest killed"
#        （注意 "ALL WAVES DEFEATED!" 是反攻启动事件，非胜负）
#   其余 = 未决（打满 45000 帧）
#
# 并发：PAR 路（默认 8；单局 exe 约 578MB / 单核，本机 32 核 / 16GB）
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
PAR="${PAR:-8}"

echo "=== z 批次(跨地图矩阵)开始 $(date +%H:%M:%S)  PAR=$PAR ==="
echo "代码版本: UsrAI.cpp md5 $(md5sum UsrAI.cpp | cut -c1-8)  exe $(ls -la --time-style=+%m-%d_%H:%M release/newAOE.exe | awk '{print $6}')"

# 清掉可能存在的同名旧输出
rm -f z0*.ait z0*.jsonl z1*.ait z1*.jsonl z2*.ait z2*.jsonl z3*.ait z3*.jsonl 2>/dev/null

{ for i in $(seq 1 3); do printf 'z0%02d map.njust\n'  "$i"; done
  for i in $(seq 1 3); do printf 'z1%02d map1.njust\n' "$i"; done
  for i in $(seq 1 3); do printf 'z2%02d map2.njust\n' "$i"; done
  for i in $(seq 1 3); do printf 'z3%02d map3.njust\n' "$i"; done
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

echo "=== z 批次完成 $(date +%H:%M:%S) ==="
echo "--- 落盘统计 ---"
for p in z0 z1 z2 z3; do
  echo "${p}: ait=$(ls -1 ${p}*.ait 2>/dev/null | wc -l) jsonl=$(ls -1 ${p}*.jsonl 2>/dev/null | wc -l)"
done
