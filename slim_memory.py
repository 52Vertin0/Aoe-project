# -*- coding: utf-8 -*-
"""MEMORY.md 四次压缩：压缩 §0.1 第 3 条（用户自改清单，细节已过时）。目标 < 19700。"""
import io

P = r'C:\Users\ZhuanZ\WorkBuddy\2026-07-29-18-11-46\.workbuddy\memory\MEMORY.md'
t = io.open(P, 'r', encoding='utf-8', newline='').read()
lines = t.split('\r\n')

out = []
i = 0
hit = 0
while i < len(lines):
    l = lines[i]
    if l.startswith('3. **用户 09-24 自改**'):
        out.append('3. **用户 09-24/09-27 自改**：伐木/复合弓块前移、`postBronze` 四处、瞪羚仓解闸、`MAX_FARMS 12→10`、'
                   '删"复合弓未就绪→普通弓"兜底、建造位黑名单按帧过期（`BUILD_POS_BLACKLIST_FRAMES 1800`）、'
                   '删 `COMPOSITE_BOW_MIN_FRAME`、ECO/TRY 性能剖析、`findBuildSite` 家族性能优化')
        # 吞掉原第 3 条的续行（到下一个 "   " 缩进的非编号行结束）
        j = i + 1
        while j < len(lines) and lines[j].startswith('   ') and not lines[j].strip()[:2] in ('4.',):
            if lines[j].startswith('4.'):
                break
            j += 1
        hit += 1
        i = j
        continue
    out.append(l)
    i += 1

assert hit == 1, '未命中条目 3（hit=%d）' % hit
io.open(P, 'w', encoding='utf-8', newline='').write('\r\n'.join(out))
b = open(P, 'rb').read()
print('size=%d (limit 20000)  CRLF=%d' % (len(b), b.count(b'\r\n')))
