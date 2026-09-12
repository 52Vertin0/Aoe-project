#!/bin/bash
# 2026-09-15 towerskip 批次：射程<箭塔射程的兵种（复合弓/战车弓/弓兵/投石兵）不再把敌箭塔选为攻击目标
# 对照 mc/md（同基线、未加此闸）：验证「远程打塔」是否归零、且不产生新的卡死/副作用
#   观察点：①[TOWER-TGT] 里"复合弓兵/远程"应归零、近战保留 ②[TOWER-SKIP] 出现并记录现场
#           ③胜负/祭司起手 ④HumanMove/HumanAction 千帧率 ⑤有无崩溃
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g || exit 1
for i in 1 2 3 4 5 6 7 8; do
  : > tc$i.jsonl 2>/dev/null
  : > tc$i.ait   2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile tc$i.jsonl -AITextLog tc$i.ait > /dev/null 2>&1
  echo "run$i exit=$? $(date +%H:%M:%S)"
done
echo "ALL DONE $(date +%H:%M:%S)"
