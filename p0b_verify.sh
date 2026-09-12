#!/bin/bash
# ============================================================================
# 2026-09-24 p0 批·补跑 —— p16..p24（前 15 局已完成，跑批在 p16 中途被中断）
#
# 改动（相对 .bak_20260924_p0p2b = 2710f75b/6622）：仅 P0（反攻期禁第 2 档「远程军队」感化）
#   P2b 已撤回（24 局零触发＝空转）
# 本批目的：确认"删除从未执行的代码"无副作用；对照 pp 批 6/24 = 25.0%
# 判据：胜 = jsonl 任一行 win:true（★扫全文件，胜帧后引擎还会写一帧 win:false）
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1

echo "=== p0 补跑开始 $(date +%H:%M:%S)  局 16..24 ==="
for i in $(seq 16 24); do
  : > p${i}.jsonl 2>/dev/null
  : > p${i}.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile p${i}.jsonl -AITextLog p${i}.ait > /dev/null 2>&1
  echo "p${i}: exit=$? $(date +%H:%M:%S)  lastframe=$(tail -1 p${i}.ait 2>/dev/null | cut -d'|' -f2 | tr -d ' ')"
done
echo "=== p0 补跑完成 $(date +%H:%M:%S) ==="
