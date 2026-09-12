#!/bin/bash
# kiting 修复验证 第二轮（4 局 map3 / rotate 90）—— 验证 stuck 升档是否生效
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Windows/System32:/c/Windows:$PATH"
cd /c/new-aoe3.0.7g

taskkill //F //IM newAOE.exe >/dev/null 2>&1

printf "run\tframe\treason\tKIT_R\tKIT_S\tMM_move\tMM_action\tagedMax\tstage1\tstage2\tstage3\tdKfirst\tdKlast\n" > kiting_results_v2.tsv

for i in 1 2 3 4; do
  : > GameLog.log
  timeout -k 5 220 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile m${i}.jsonl -AITextLog m${i}.ait > /dev/null 2>&1
  fr=$(tail -1 m${i}.jsonl | sed -E 's/.*"frame":([0-9]+).*/\1/')
  if grep -q "DEFEAT: Priest killed" m${i}.ait; then rs=PRIEST_DEAD
  elif [ "${fr:-0}" -ge 44999 ]; then rs=TIMEOUT
  else rs=OTHER; fi
  kr=$(grep -c "KIT-R" m${i}.ait)
  ks=$(grep -c "KIT-S" m${i}.ait)
  mm=$(grep -c "HumanMove:复合弓兵" m${i}.ait)
  ma=$(grep -c "HumanAction:复合弓兵" m${i}.ait)
  am=$(grep -o "aged=[0-9]*" m${i}.ait | sed 's/aged=//' | sort -n | tail -1)
  s1=$(grep -o "stage=1" m${i}.ait | wc -l)
  s2=$(grep -o "stage=2" m${i}.ait | wc -l)
  s3=$(grep -o "stage=3" m${i}.ait | wc -l)
  d1=$(grep "KIT-R" m${i}.ait | head -1 | sed -E 's/.*dK=([0-9.]+).*/\1/')
  d2=$(grep "KIT-R" m${i}.ait | tail -1 | sed -E 's/.*dK=([0-9.]+).*/\1/')
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$i" "$fr" "$rs" "$kr" "$ks" "$mm" "$ma" "${am:-0}" "$s1" "$s2" "$s3" "${d1:-NA}" "${d2:-NA}" >> kiting_results_v2.tsv
  echo "run $i done: frame=$fr reason=$rs KIT_R=$kr stage=(1:$s1 2:$s2 3:$s3)"
done

echo "=================== kiting_results_v2.tsv ==================="
cat kiting_results_v2.tsv
echo "=================== 全部 KIT-R（v2）==================="
cat m*.ait 2>/dev/null | grep -o "\[KIT-R f=[0-9]*\] SN=[0-9]* dK=[0-9.]* R=[0-9.]* stage=[0-9]* stuck=[0-9]* aged=[0-9]*" > kiting_all_v2.txt
wc -l kiting_all_v2.txt
grep -o "stage=[0-9]*" kiting_all_v2.txt | sort | uniq -c
