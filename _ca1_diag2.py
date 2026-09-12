import io, re, glob
g = r"C:\new-aoe3.0.7g"
for tag in ("pe2","ca1"):
    W=P=T=U=0; pd=[]
    for fn in sorted(glob.glob(g+"\\"+tag+"_map_r0_*.ait")):
        t=io.open(fn,encoding="utf-8",errors="replace").read()
        if '被祭司转换,归属阵营1->0' in t: W+=1
        elif 'DEFEAT: Priest killed' in t:
            P+=1
            m=re.search(r'(\d+):(\d+):(\d+) \| (\d+)', t[t.find('DEFEAT: Priest killed')-200:t.find('DEFEAT: Priest killed')])
            pd.append(m.group(4) if m else "?")
        elif 'DEFEAT: Town Center destroyed' in t: T+=1
        else: U+=1
    print("%s : W=%d P=%d T=%d U=%d  (n=%d, win=%.1f%%, priestDeath=%.1f%%)" % (tag,W,P,T,U,W+P+T+U,100*W/(W+P+T+U),100*P/(W+P+T+U)))