#!/bin/bash
# ============================================================================
# 2026-09-24 pp 批次 —— P0 + P2b 两处行为改动的 24 局验证（铁律 81：≥24 局/臂）
#
# 改动（相对 .bak_20260924_p0p2b = 2710f75b/6622）：
#   P0  = findConvertTarget 反攻期(inCounter)禁用第 2 档「远程军队」感化目标 + convPick 档位日志
#   P2b = manageMilitary B 段箭塔索敌：射程内最近敌人 → 优先打"没在以本塔为目标"的敌人
#
# 预期（若 P0 生效）：
#   ① 8 个负局那样"祭司最后一条感化令 = 远程兵"应消失（用 _priest_death.py 复查 pick 字段）
#   ② 祭司死亡帧 37xxx 扎堆应分散或整体后移；胜率应上移
# 预期（若 P2b 生效）：
#   ③ 箭塔换目标日志（同塔 SN 对多个敌 SN 的 HumanAction）应出现；防御期祭司被近战贴身次数下降
#
# 判据：胜 = jsonl 的 win:true（新口径）；AIText 的 VICTORY/DEFEAT 只作交叉验证
# 对照臂：cur 12 局 = 3 胜 8 负 1 未决（25.0%）｜kb2 12 局 = 5 胜 4 负 3 未决（41.7%）
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1

echo "=== pp 批次开始 $(date +%H:%M:%S) ==="
for i in $(seq 1 24); do
  : > pp${i}.jsonl 2>/dev/null
  : > pp${i}.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile pp${i}.jsonl -AITextLog pp${i}.ait > /dev/null 2>&1
  echo "pp${i}: exit=$? $(date +%H:%M:%S)  lastframe=$(tail -1 pp${i}.ait 2>/dev/null | cut -d'|' -f2 | tr -d ' ')"
done
echo "=== pp 批次完成 $(date +%H:%M:%S) ==="
