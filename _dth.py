# -*- coding: utf-8 -*-
"""祭司死亡帧（对全部 96 局）"""
import re,glob,collections
for fn in sorted(glob.glob('fixI_*_r0_*.ait')):
    t=open(fn,encoding='utf-8',errors='replace').read()
    if t.count('[BEAT')<5: continue
    m=re.search(r'\| (\d+) \| black \| 0 \| .*DEFEAT: Priest killed',t)
    if not m: continue
    f=int(m.group(1))
    ca=re.search(r'Counterattack! Frame=(\d+)',t)
    caf=int(ca.group(1)) if ca else -1
    if caf>0: continue
    print(f"{fn.replace('fixI_','').replace('.ait',''):<14} 死f={f:>6} ({f/1500:>5.1f}分)")
