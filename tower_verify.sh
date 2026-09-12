#!/bin/bash
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/new-aoe3.0.7g

: > tw_results.tsv
printf "run\tframe\tscore\treason\ttwrBuilt\tstonePeak\tstoneMin\tstoneFirst150\tstoneZeroStart\ttower1F\ttower2F\ttower3F\n" >> tw_results.tsv

for i in 1 2 3 4 5 6 7 8; do
  : > GameLog.log
  rm -f tw${i}.jsonl tw${i}.ait 2>/dev/null
  timeout -k 5 300 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile tw${i}.jsonl -AITextLog tw${i}.ait > /dev/null 2>&1

  j=$(tail -1 tw${i}.jsonl 2>/dev/null)
  frame=$(echo "$j" | grep -o '"frame":[0-9]*' | cut -d: -f2); [ -z "$frame" ] && frame=0
  score=$(echo "$j" | grep -o '"score":[0-9]*' | cut -d: -f2); [ -z "$score" ] && score=0
  if grep -q "DEFEAT" GameLog.log 2>/dev/null; then reason=PRIEST_DEAD; else reason=TIMEOUT; fi

  twrBuilt=$(grep "BUILD-ISSUE" tw${i}.ait 2>/dev/null | grep "type=6" | grep -c "| 0 |")
  stonePeak=$(grep "ECO" tw${i}.ait 2>/dev/null | grep -o "St:[0-9]*" | grep -o "[0-9]*" | sort -n | tail -1)
  stoneMin=$(grep "ECO" tw${i}.ait 2>/dev/null | grep -o "St:[0-9]*" | grep -o "[0-9]*" | sort -n | head -1)
  stoneFirst150=$(grep "ECO" tw${i}.ait 2>/dev/null | grep -o "St:[0-9]*" | grep -o "[0-9]*" | awk '$1>=150 {print NR; exit}')
  stoneZeroStart=$(grep "ECO" tw${i}.ait 2>/dev/null | grep -o "St:[0-9]*" | grep -o "[0-9]*" | awk '$1==0 {print NR; exit}')
  tower1F=$(grep "BUILD-ISSUE" tw${i}.ait 2>/dev/null | grep "type=6" | head -1 | awk -F'|' '{print $2}' | tr -d ' ')
  tower2F=$(grep "BUILD-ISSUE" tw${i}.ait 2>/dev/null | grep "type=6" | head -2 | tail -1 | awk -F'|' '{print $2}' | tr -d ' ')
  tower3F=$(grep "BUILD-ISSUE" tw${i}.ait 2>/dev/null | grep "type=6" | head -3 | tail -1 | awk -F'|' '{print $2}' | tr -d ' ')

  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$i" "$frame" "$score" "$reason" "$twrBuilt" "${stonePeak:-N/A}" "${stoneMin:-N/A}" "${stoneFirst150:-N/A}" "${stoneZeroStart:-N/A}" "${tower1F:-N/A}" "${tower2F:-N/A}" "${tower3F:-N/A}" >> tw_results.tsv
  echo "run$i frame=$frame score=$score $reason | twrBuilt=$twrBuilt stonePeak=${stonePeak:-N/A} stoneFirst150=${stoneFirst150:-N/A} tower1=${tower1F:-N/A} tower2=${tower2F:-N/A} tower3=${tower3F:-N/A}"
done

echo "=== 汇总 ==="
cat tw_results.tsv
