#!/bin/bash
# 2026-09-15 sg 批次：祭司起手保护（已残血 + 敌塔 <=14 格 ⇒ 本帧不起手）+ 起手全过程可观测
# 对照 sb 批次（无起手保护、起手日志被 frame%50 采样掩盖）
# 观察点：①SIEGE-HOLD 次数 ②起手时 nearT/towers/hp ③起手→收编帧数 ④祭司死/胜负
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in 1 2 3 4 5 6 7 8; do
  : > sg$i.jsonl 2>/dev/null
  : > sg$i.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile sg$i.jsonl -AITextLog sg$i.ait > /dev/null 2>&1
  echo "run$i exit=$? $(date +%H:%M:%S)"
done
echo "ALL DONE $(date +%H:%M:%S)"
