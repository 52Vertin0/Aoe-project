#!/bin/bash
# ============================================================================
# 2026-09-24 p0 批次 —— 撤回 P2b 后（只留 P0）的 24 局确认（与 pp 批同规模可直接对比）
#
# 改动（相对 .bak_20260924_p0p2b = 2710f75b/6622）：
#   P0  = findConvertTarget 反攻期(inCounter)禁用第 2 档「远程军队」感化目标 + convPick 档位日志
#   P2b = 已撤回（24 局实测零触发＝空转，见 aoe3_pp_verify_20260924.html）
#
# 本批目的：确认「删除 P2b 这段从未执行的代码」不引入副作用。
#   预期：胜率量级与 pp 批持平（≈25%，6/24）；反攻期感化档 pick 分布中 2（远程军队）仍为 0；
#         祭司亡帧分布、胜负分离度（胜局最后感化令＝攻城武器厂）与 pp 批同形。
#
# 判据：胜 = jsonl 任一行 win:true（★必须扫全文件：引擎在胜帧后会再写一帧 win:false）；
#       AIText 的 VICTORY/DEFEAT 作交叉验证；恒等式 胜+负+未决==n 必过。
# 对照臂：pp 24 局 = 6 胜 14 负 4 未决（25.0%）｜cur 12 局 = 3 胜 8 负 1 未决（25.0%）
#         kb2 12 局 = 5 胜 4 负 3 未决（41.7%）
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1

echo "=== p0 批次开始 $(date +%H:%M:%S) ==="
for i in $(seq 1 24); do
  : > p0${i}.jsonl 2>/dev/null
  : > p0${i}.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile p0${i}.jsonl -AITextLog p0${i}.ait > /dev/null 2>&1
  echo "p0${i}: exit=$? $(date +%H:%M:%S)  lastframe=$(tail -1 p0${i}.ait 2>/dev/null | cut -d'|' -f2 | tr -d ' ')"
done
echo "=== p0 批次完成 $(date +%H:%M:%S) ==="
