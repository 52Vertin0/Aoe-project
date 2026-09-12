#!/bin/bash
# ============================================================================
# 2026-09-29 fw2 批 —— A/B：闸放行「无条件」vs「带保命条件(&& localClear)」
#   blanket 臂 = fw1*（已跑，exe=fwv_blanket.exe，源 md5 a2b5f9ed）
#   guarded 臂 = gd1*（本批，exe=release/newAOE.exe）
#   bl1* = 用 blanket exe 复测同配置 ⇒ 判「跑局是否确定」（若 bl101 与 fw101 同果 ⇒ 确定 ⇒ A/B 有效）
#   配置与 fw1 完全一致：101-104 = map2，105-108 = map3，-rotate 90
# ============================================================================
export PATH="/d/360Downloads/5.9.2/mingw53_32/bin:/d/360Downloads/Tools/mingw530_32/bin:/c/Users/ZhuanZ/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
export QT_QPA_PLATFORM=offscreen
cd /c/new-aoe3.0.7g || exit 1

run() {  # $1=exe $2=tag $3=map
  : > "$2.jsonl"; : > "$2.ait"
  timeout -k 5 300 "$1" -exam -offscreen -freq MAX -map "$3" -rotate 90 \
    -ResultLogFile "$2.jsonl" -AITextLog "$2.ait" > /dev/null 2>&1
  echo "$2 $3 exit=$? $(date +%H:%M:%S)"
}
export -f run

rm -f gd1*.ait gd1*.jsonl bl1*.ait bl1*.jsonl 2>/dev/null

echo "=== fw2 A/B 开始 $(date +%H:%M:%S) ==="
echo "guarded exe md5 $(md5sum release/newAOE.exe | cut -c1-8)   blanket exe md5 $(md5sum fwv_blanket.exe | cut -c1-8)"

# 1) determinism 复测（blanket exe，两配置）
{ printf 'bl101 map2.njust\nbl105 map3.njust\n'; } | xargs -P 2 -n 2 bash -c 'run ./fwv_blanket.exe "$1" "$2"' _

# 2) guarded 臂（8 配置）
{ printf 'gd101 map2.njust\ngd102 map2.njust\ngd103 map2.njust\ngd104 map2.njust\n'
  printf 'gd105 map3.njust\ngd106 map3.njust\ngd107 map3.njust\ngd108 map3.njust\n'; } | \
xargs -P 8 -n 2 bash -c 'run ./release/newAOE.exe "$1" "$2"' _

echo "=== fw2 完成 $(date +%H:%M:%S) ==="
res() {  # $1=tag
  t=$1
  w=$(grep -c 'win":true' $t.jsonl 2>/dev/null)
  d=$(grep -c 'DEFEAT:' $t.ait 2>/dev/null)
  lf=$(tail -1 $t.ait 2>/dev/null | cut -d"|" -f2 | tr -d " ")
  cv=$(grep -c "Priest converting Siege Workshop" $t.ait 2>/dev/null)
  fwmax=$(grep -o "fW=[0-9]*" $t.ait 2>/dev/null | cut -d= -f2 | sort -n | tail -1)
  [ "${w:-0}" -gt 0 ] && v=W || { [ "${d:-0}" -gt 0 ] && v=L || v=U; }
  echo "$t: $v  末帧=${lf}  感化令=${cv}  fW峰值=${fwmax:-0}  DEFEAT行=${d}"
}
echo "--- 0) 确定性复测：blanket exe 复跑（应与 fw101/fw105 同果）---"
res bl101; res bl105
echo "--- 1) blanket 臂（= fw1*，无条件放行）---"
for t in fw101 fw102 fw103 fw104 fw105 fw106 fw107 fw108; do res $t; done
echo "--- 2) guarded 臂（带保命条件）---"
for t in gd101 gd102 gd103 gd104 gd105 gd106 gd107 gd108; do res $t; done
