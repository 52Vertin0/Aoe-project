#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-09-21 祭司死亡分析：对比 修复前(wd) / 修复后(pd)
# 判据：真实死亡事件 = 行内 '祭司(编号:NNNN)死亡'（每局至多 1 次，单祭司单位）
# 帧分桶：scout<5000 / early 5000~21000 / counter>=21000（反攻期前出探武器厂高危带）
import io, re, os, glob, sys

RE_DEATH = re.compile(r'祭司\(编号[:：]?[0-9]*\)死亡')
RE_FRAME = re.compile(r'\|\s*(\d+)\s*\|')   # 取首个 |数字| 作为帧
RE_VIC = re.compile(r'VICTORY')
RE_DEF = re.compile(r'DEFEAT')
# 死亡前诊断：UsrAI 打印里可能带 hp / nearE / mode
RE_HP = re.compile(r'hp[=:]?\s*([0-9.]+)')
RE_NEAR = re.compile(r'nearE[=:]?\s*([0-9.]+)')
RE_MODE = re.compile(r'mode[=:]?\s*(\d+)')

def parse(fp):
    lines = io.open(fp, encoding='utf-8', errors='replace').readlines()
    death_frame = None
    death_ctx = {}
    for i, r in enumerate(lines):
        if RE_DEATH.search(r):
            m = RE_FRAME.search(r)
            if m:
                death_frame = int(m.group(1))
            # 向前扫 60 行抓诊断
            for j in range(max(0,i-60), i):
                s = lines[j]
                if '祭司' in s or 'PRIEST' in s or 'priest' in s:
                    for rx, key in ((RE_HP,'hp'),(RE_NEAR,'nearE'),(RE_MODE,'mode')):
                        mm = rx.search(s)
                        if mm and key not in death_ctx:
                            death_ctx[key] = mm.group(1)
            break
    txt = ''.join(lines)
    vic = bool(RE_VIC.search(txt))
    defe = bool(RE_DEF.search(txt))
    return death_frame, death_ctx, ('VICTORY' if vic else ('DEFEAT' if defe else '?'))

def bucket(f):
    if f is None: return 'alive'
    if f < 5000: return 'scout(<5k)'
    if f < 21000: return 'early(5k~21k)'
    return 'counter(>=21k)'

batch = sys.argv[1] if len(sys.argv)>1 else 'pd'
files = sorted(glob.glob('%s*.ait' % batch))
if not files:
    print('no %s*.ait' % batch); sys.exit(0)
deaths=0; buckets={'scout(<5k)':0,'early(5k~21k)':0,'counter(>=21k)':0,'alive':0}
vic_when_dead=0; def_when_dead=0; outcomes={'VICTORY':0,'DEFEAT':0,'?':0}
details=[]
for fp in files:
    f,ctx,outc = parse(fp)
    outcomes[outc]+=1
    b = bucket(f); buckets[b]+=1
    if f is not None:
        deaths+=1
        if outc=='VICTORY': vic_when_dead+=1
        else: def_when_dead+=1
        details.append((os.path.basename(fp), f, b, outc, ctx))
print('=== 批次 %s：%d 局 ===' % (batch, len(files)))
print('祭司死亡局数 = %d / %d  (%.1f%%)' % (deaths, len(files), 100.0*deaths/len(files)))
print('分桶：', buckets)
print('结局：', outcomes)
print('死亡局中 → 胜 %d / 负 %d' % (vic_when_dead, def_when_dead))
print()
print('【死亡明细 frame | 分桶 | 结局 | 诊断(hp/nearE/mode)】')
for name,f,b,outc,ctx in details:
    print('  %-10s f=%6d %-14s %-8s %s' % (name, f, b, outc, ctx))
