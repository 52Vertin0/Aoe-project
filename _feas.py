# -*- coding: utf-8 -*-
"""可行性检验：给了「nearT>7 才起手」的闸之后，那些 nearT<=7 起手的局是否真能等到 nearT>7 的时刻？
   用 [LC-DBG]（frame%300）的 nearT 序列——注意它自身带 mvcd/位置，稀疏但可用。"""
import re,glob,statistics as st
def oc(t):
    if '被祭司转换,归属阵营1->0' in t: return 'W'
    if 'DEFEAT: Priest killed' in t: return 'P'
    return 'T'
LO,HI=7.0,999.0
rows=[]
for fn in sorted(glob.glob('fixI_*_r0_*.ait')):
    t=open(fn,encoding='utf-8',errors='replace').read()
    sites=re.findall(r'converting Siege Workshop! f=(\d+) d=([\d.]+) hp=([\d.]+) nearT=([-\d.]+) towers=(\d+) path=',t)
    if not sites: continue
    F0=int(sites[0][0]); nt0=float(sites[0][3]); hp0=float(sites[0][2])
    if not (0<=nt0<=LO): continue          # 只看"危险起手"那一群
    # LC-DBG 序列（帧,nearT）：全时段
    seq=[]
    for L in t.splitlines():
        m=re.search(r'\[LC-DBG f=(\d+)\][^\n]*?nearT=([-\d.]+)',L)
        if m: seq.append((int(m.group(1)),float(m.group(2))))
    # 死亡帧
    md=re.search(r'\|\s*(\d+)\s*\|[^|]*\|[^|]*\|[^|]*DEFEAT: Priest killed',t)
    dth=int(md.group(1)) if md else None
    fs=[int(x) for x in re.findall(r'\|\s*(\d+)\s*\|\s*(?:red|green|blue|black)',t)]
    end=max(fs) if fs else 0
    # 起手之后，是否存在 nearT>7 且祭司还活着的时刻
    after=[(f,n) for f,n in seq if f>F0]
    safe=[(f,n) for f,n in after if n>LO or n<0]     # -1 = 无塔（更安全）
    rows.append((fn,oc(t),F0,nt0,hp0,dth,end,len(after),len(safe),
                 (safe[0][0] if safe else None)))
print(f'{"局":<24}{"结局":<4}{"起手f":>7}{"nearT":>7}{"hp":>6}{"死亡f":>7}{"末帧":>7}{"起手后LC采样":>12}{"其中安全":>8}{"首个安全f":>10}')
for r in rows:
    print(f'{r[0]:<24}{r[1]:<4}{r[2]:>7}{r[3]:>7.1f}{r[4]:>6.2f}{str(r[5]):>7}{r[6]:>7}{r[7]:>12}{r[8]:>8}{str(r[9]):>10}')
n=len(rows)
print()
print(f'=== 汇总：危险起手(nearT<=7) 共 {n} 局 ===')
w=sum(1 for r in rows if r[1]=='W')
has=sum(1 for r in rows if r[8]>0)
print(f'  胜={w}  起手后【曾出现 nearT>7】的局={has}/{n}')
alive_before_death=sum(1 for r in rows if r[8]>0 and r[5] and r[9] and r[9]<r[5])
print(f'  其中【在死亡之前】就出现过 nearT>7 的局={alive_before_death}')
for r in rows:
    if r[1]=='W' and r[3]<=7: print(f'    (胜局样本) {r[0]}  nearT0={r[3]}  首个安全f={r[9]}')
