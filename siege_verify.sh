#!/bin/bash
# 2026-09-13 军队不攻击武器厂 + 祭司局部清场后感化武器厂 验证：8 局 map3 / rotate 90
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g

: > siege_results.tsv
printf "run\tframe\tscore\treason\tsiegeFound\tarmyHitSiege\tpriestConvSiege\tpriestAdvSiege\tpriestDbgClear\tatkOnOther\n" >> siege_results.tsv

for i in 1 2 3 4 5 6 7 8; do
  : > GameLog.log
  rm -f sg${i}.jsonl sg${i}.ait 2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile sg${i}.jsonl -AITextLog sg${i}.ait > /dev/null 2>&1

  j=$(tail -1 sg${i}.jsonl 2>/dev/null)
  frame=$(echo "$j" | grep -o '"frame":[0-9]*' | cut -d: -f2); [ -z "$frame" ] && frame=0
  score=$(echo "$j" | grep -o '"score":[0-9]*' | cut -d: -f2); [ -z "$score" ] && score=0
  if grep -q "DEFEAT" GameLog.log 2>/dev/null; then reason=PRIEST_DEAD; else reason=TIMEOUT; fi

  # 我方侦察到敌武器厂
  sf=$(grep -c "Enemy Siege Workshop found" sg${i}.ait 2>/dev/null)
  # 我方军队下发的攻击令中目标为攻城武器厂（引擎命令派发行，green）
  ahs=$(grep "设置攻击目标为 攻城武器厂" sg${i}.ait 2>/dev/null | grep -c "| 0 |")
  # 祭司感化武器厂（我方 debug 输出）
  pcs=$(grep -c "Priest converting Siege Workshop" sg${i}.ait 2>/dev/null)
  # 祭司向武器厂推进
  pas=$(grep -c "Priest ADVANCE to Siege" sg${i}.ait 2>/dev/null)
  # 祭司全局/局部清场状态打点
  pdc=$(grep -c "Priest CLEAR" sg${i}.ait 2>/dev/null)
  # 我方其他攻击令总数（对照）
  aot=$(grep "设置攻击目标为" sg${i}.ait 2>/dev/null | grep -c "| 0 |")

  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$i" "$frame" "$score" "$reason" "$sf" "$ahs" "$pcs" "$pas" "$pdc" "$aot" >> siege_results.tsv
  echo "run$i frame=$frame score=$score $reason | siegeFound=$sf armyHitSiege=$ahs priestConv=$pcs priestAdv=$pas clearDbg=$pdc atkTotal=$aot"
done

echo "=== 汇总 ==="
cat siege_results.tsv
