#!/bin/bash
# 2026-09-13 复合弓科技解锁提速验证：8 局 map3 / rotate 90
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g

: > cb_results.tsv
printf "run\tframe\treason\twoodTech\tcbTech\tgap\tfarmCount\twoodAtCB\tmeatAtCB\n" >> cb_results.tsv

for i in 1 2 3 4 5 6 7 8; do
  : > GameLog.log
  rm -f cb${i}.jsonl cb${i}.ait 2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile cb${i}.jsonl -AITextLog cb${i}.ait > /dev/null 2>&1

  frame=$(tail -1 cb${i}.jsonl 2>/dev/null | grep -o '"frame":[0-9]*' | head -1 | cut -d: -f2)
  [ -z "$frame" ] && frame=0
  if grep -q "DEFEAT" GameLog.log 2>/dev/null; then reason=PRIEST_DEAD; else reason=TIMEOUT; fi

  wt=$(grep -o "TECH WoodProcessing(伐木+2) f=[0-9]*" cb${i}.ait 2>/dev/null | head -1 | grep -o '[0-9]*$')
  ct=$(grep -o "TECH CompositeBow f=[0-9]*" cb${i}.ait 2>/dev/null | head -1 | grep -o '[0-9]*$')
  [ -z "$wt" ] && wt=0
  [ -z "$ct" ] && ct=0
  if [ "$wt" -gt 0 ] && [ "$ct" -gt 0 ]; then gap=$((ct - wt)); else gap=-1; fi

  fc=$(grep -c "建造完毕" cb${i}.ait 2>/dev/null)
  cbline=$(grep "TECH CompositeBow" cb${i}.ait 2>/dev/null | head -1)
  ww=$(echo "$cbline" | grep -o 'wood=[0-9]*' | cut -d= -f2)
  mm=$(echo "$cbline" | grep -o 'meat=[0-9]*' | cut -d= -f2)
  [ -z "$ww" ] && ww=0
  [ -z "$mm" ] && mm=0

  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$i" "$frame" "$reason" "$wt" "$ct" "$gap" "$fc" "$ww" "$mm" >> cb_results.tsv
  echo "run$i frame=$frame $reason woodTech=$wt cbTech=$ct gap=$gap"
done

echo "=== 汇总 ==="
cat cb_results.tsv
