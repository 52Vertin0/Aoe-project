#!/bin/bash
# kiting 修复验证（8 局 map3 / rotate 90）
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Windows/System32:/c/Windows:$PATH"
cd /c/new-aoe3.0.7g

taskkill //F //IM newAOE.exe >/dev/null 2>&1

printf "run\tframe\treason\tKIT_R\tKIT_S\tMM_move\tMM_action\tagedMax\tdKfirst\tdKlast\n" > kiting_results.tsv

for i in 1 2 3 4 5 6 7 8; do
  : > GameLog.log
  timeout -k 5 220 env QT_QPA_PLATFORM=offscreen ./release/newAOE.exe \
    -exam -offscreen -freq MAX -map map3.njust -rotate 90 \
    -ResultLogFile k${i}.jsonl -AITextLog k${i}.ait > /dev/null 2>&1
  fr=$(tail -1 k${i}.jsonl | sed -E 's/.*"frame":([0-9]+).*/\1/')
  if grep -q "DEFEAT: Priest killed" k${i}.ait; then rs=PRIEST_DEAD
  elif [ "${fr:-0}" -ge 44999 ]; then rs=TIMEOUT
  else rs=OTHER; fi
  kr=$(grep -c "KIT-R" k${i}.ait)
  ks=$(grep -c "KIT-S" k${i}.ait)
  mm=$(grep -c "HumanMove:复合弓兵" k${i}.ait)
  ma=$(grep -c "HumanAction:复合弓兵" k${i}.ait)
  am=$(grep -o "aged=[0-9]*" k${i}.ait | sed 's/aged=//' | sort -n | tail -1)
  d1=$(grep "KIT-R" k${i}.ait | head -1 | sed -E 's/.*dK=([0-9.]+).*/\1/')
  d2=$(grep "KIT-R" k${i}.ait | tail -1 | sed -E 's/.*dK=([0-9.]+).*/\1/')
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$i" "$fr" "$rs" "$kr" "$ks" "$mm" "$ma" "${am:-0}" "${d1:-NA}" "${d2:-NA}" >> kiting_results.tsv
  echo "run $i done: frame=$fr reason=$rs KIT_R=$kr"
done

echo "=================== kiting_results.tsv ==================="
cat kiting_results.tsv
echo "=================== 汇总全部 KIT-R ==================="
cat k*.ait 2>/dev/null | grep -o "\[KIT-R f=[0-9]*\] SN=[0-9]* dK=[0-9.]* R=[0-9.]* stage=[0-9]* stuck=[0-9]* aged=[0-9]*" > kiting_all.txt
wc -l kiting_all.txt
echo "--- stage 分布 ---"
grep -o "stage=[0-9]*" kiting_all.txt | sort | uniq -c
echo "--- aged 分布(前20个不同值) ---"
grep -o "aged=[0-9]*" kiting_all.txt | sed 's/aged=//' | sort -n | uniq -c | head -20
