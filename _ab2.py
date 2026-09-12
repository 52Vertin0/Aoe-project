import re
def frame_at(lines, idx):
    for j in range(idx, -1, -1):
        m = re.search(r'(?:Frame=|f=)(\d{3,6})', lines[j])
        if m: return int(m.group(1))
    return None
for r in ['_n0_1','_n0_2','_n0_3','_fix_1','_fix_2','_fix_3']:
    lines = open(r+'.dbg', encoding='utf-8', errors='replace').read().splitlines()
    conv = [i for i,l in enumerate(lines) if '被祭司转换' in l]
    died = [i for i,l in enumerate(lines) if 'DEFEAT: Priest killed' in l]
    lastf = None
    for l in reversed(lines):
        m = re.search(r'(?:Frame=|f=)(\d{3,6})', l)
        if m: lastf = int(m.group(1)); break
    tt = [l for l in lines if '[TOWER-TGT]' in l and '近战' in l]
    app = [l for l in lines if '[TOWER-APPROACH]' in l]
    res = '胜' if conv else ('负(祭司死)' if died else '超时')
    cf = frame_at(lines, conv[0]) if conv else None
    print('%-8s %-10s 末帧=%-6s 转换帧=%-6s (%s分) | [TOWER-TGT]近战=%-3d [TOWER-APPROACH]=%d' %
          (r, res, lastf, cf, ('%.1f'%(cf/1500.0)) if cf else '—', len(tt), len(app)))
