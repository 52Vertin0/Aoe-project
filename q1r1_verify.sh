#!/bin/bash
# ============================================================================
# 2026-09-27 q1/r1 批次 —— 【祭司推进脱困】验证（map2 × 24 扩样 + map3 × 12 回归）
#
# 改动（本批唯一变量）：counterPriestConvert 的 ADVANCE 路径加"两段脱困阶梯"
#   A 档：连续 PRIEST_ADV_STUCK_FRAMES(120) 帧未真正逼近 >0.5 格 ⇒ 侧移 4 格绕开堵点（左右交替）
#   B 档：A 无效则把祭司 2 格内的友军沿侧向推开 6 格（清障；需祭司周边 15 格内无活敌才做）
#   铁律 9：脱困动作【绝不算进展】—— priestAdvBest 只在真逼近时降低，priestEscapeStage 只有真进展才归零
#   代码版本：UsrAI.cpp md5 4bf8f9a0·6700 / UsrAI.h 78b64ea7·402（exe 14:32:22）
#   备份 bak_20260927_priest_escape_UsrAI.cpp/.h
#
# 目标失败模式（②b，n610 铁证）：反攻末期敌军全灭后祭司卡在距武器厂 12.4 格（只差 0.4 格），
#   连续 4500 帧零位移（被 27 个友军裹住 nearAlly=0.4BL）⇒ 打满 45000 = 未决。
#
# 观察指标：
#   ① [PRIEST-ESCAPE A/B] 是否出现（机制是否活着）
#   ② 未决数（基线 n6+n7 = 2/24）；②b 特征局 = dS 恒定且 45000 帧结束
#   ③ map3 回归：胜负对照 n3/n8（均 7胜/4负/1未决）
# 判据（项目铁律）：胜 = jsonl 任一行 "win":true；负 = ait 含 "DEFEAT:"；其余 = 打满 45000 = 未决
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
PAR="${PAR:-8}"

echo "=== q1/r1 批次开始 $(date +%H:%M:%S)  PAR=$PAR ==="
echo "代码版本: UsrAI.cpp md5 $(md5sum UsrAI.cpp | cut -c1-8)  exe $(ls -la --time-style=+%m-%d_%H:%M release/newAOE.exe | awk '{print $6}')"

rm -f q1*.ait q1*.jsonl r1*.ait r1*.jsonl 2>/dev/null

{ for i in $(seq 1 24); do printf 'q1%02d map2.njust\n' "$i"; done
  for i in $(seq 1 12); do printf 'r1%02d map3.njust\n' "$i"; done
} | xargs -P "$PAR" -n 2 bash -c '
  tag="$1"; map="$2"
  : > "${tag}.jsonl" 2>/dev/null
  : > "${tag}.ait"   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map "${map}" -rotate 90 \
    -ResultLogFile "${tag}.jsonl" -AITextLog "${tag}.ait" > /dev/null 2>&1
  rc=$?
  es=$(grep -c "PRIEST-ESCAPE" "${tag}.ait" 2>/dev/null)
  ls2=$(awk -F"|" "{print \$2}" "${tag}.ait" 2>/dev/null | sort -n | tail -1)
  echo "${tag} ${map} exit=${rc} $(date +%H:%M:%S) lastframe=${ls2} ESCAPE=${es}"
' _

echo "=== q1/r1 完成 $(date +%H:%M:%S) ==="
echo "q1: ait=$(ls -1 q1*.ait 2>/dev/null | wc -l)  r1: ait=$(ls -1 r1*.ait 2>/dev/null | wc -l)"
echo "exe 时间(跑后核对): $(ls -la --time-style=+%m-%d_%H:%M:%S release/newAOE.exe | awk '{print $6}')"
