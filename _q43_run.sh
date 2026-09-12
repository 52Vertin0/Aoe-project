#!/bin/bash
set -u
cd /c/new-aoe3.0.7g || exit 1
export QT_QPA_PLATFORM=offscreen
MAPS="map.njust map1.njust map2.njust map3.njust"
echo "=== ARM B (before / aggpriest, bc28a78d) ==="
MAPS="$MAPS" ROT=0 N=3 PAR=8 TMO=420 TAG=g2w0q EXE=./release/newAOE_aggpriest.exe bash _ab_run.sh
echo "=== ARM A (after / g2w2, gold->wood) ==="
MAPS="$MAPS" ROT=0 N=3 PAR=8 TMO=420 TAG=g2w2q EXE=./release/newAOE_g2w2.exe bash _ab_run.sh
echo "=== ALL DONE ==="
