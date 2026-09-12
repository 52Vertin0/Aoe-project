# -*- coding: utf-8 -*-
"""
2026-09-19  assignIdleFarmers() 无用注释/代码清理
纯清理：注释改写 + 删空 if 块 + 删 void 末尾 return + 缩进归位。行为零变化。

三处改动：
 R1 头注释（"分配空闲村民采集…" 全假）→ 改写为真实职责
 R2 注释内失效行号引用（"见下方 2076 行附近"）→ 改为判据名
 R3 尾部：空 if 块 { } + 注释 + 末尾 return + 错位缩进 → 收敛为两个右花括号
"""
import io, sys, hashlib

P = 'UsrAI.cpp'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')

# 前置：全文必须纯 CRLF
assert txt.count('\r\n') == txt.count('\n'), '存在非 CRLF 行尾，ABORT'
lines = txt.split('\r\n')
n0 = len(lines) - 1

def ln(i):            # 1-based
    return lines[i - 1]

# ---------------- 锚点断言 ----------------
a1 = '// 分配空闲村民采集（改进版：每帧2个 + 金矿 + 自动调整农场目标）'
assert lines.count(a1) == 1, 'R1 锚点命中 %d' % lines.count(a1)
assert ln(2210) == a1
assert ln(2209) == '// ============================================================'
assert ln(2211) == '// ============================================================'
assert ln(2212) == 'void UsrAI::assignIdleFarmers() {'

a2 = '        //   (到达某方向终点(nearTarget)时 scoutDirsDone++，见下方 2076 行附近。)'
assert lines.count(a2) == 1, 'R2 锚点命中 %d' % lines.count(a2)
assert ln(2295) == a2

blk = lines[2633:2642]          # 行 2634..2642
expect = [
    '    // 探路完成（phase>=16或祭司死亡/不存在）后释放标记',
    '    if (scoutPhase >= 16) {',
    '        // 祭司探路完成，managePriest恢复常规逻辑',
    '    }',
    '',
    '    // 旧分配逻辑全部禁用：探路完成后直接返回，村民分配由 assignIdleSimple() 单独负责。',
    '    return;',
    '}',
    '}',
]
assert blk == expect, 'R3 区间不匹配:\n' + '\n'.join(repr(x) for x in blk)
assert ln(2632) == '        }', repr(ln(2632))
assert ln(2643) == ''
assert ln(2644) == 'void UsrAI::assignIdleSimple() {'

# ---------------- R3：尾部（先从大索引做，避免偏移） ----------------
new = lines[:2632] + ['    }', '}'] + lines[2642:]
assert len(new) == len(lines) - 10 + 2

# ---------------- R2 ----------------
i2 = new.index(a2)
new[i2] = '        //   (到达某方向终点时，由下方 nearTarget 分支执行 scoutDirsDone++。)'

# ---------------- R1 ----------------
i1 = new.index(a1)
new[i1:i1 + 1] = [
    '// 每帧维护三件事：①重置资源分配去重表(供下游分配函数计数) ②动态农场目标 ③祭司探路状态机',
    '//   ⚠ 本函数【不做】村民分配——旧分配逻辑已全部移除，分配统一由 assignIdleSimple() 负责。',
]

out = '\r\n'.join(new).encode('utf-8')
assert out.count(b'\r\n') == out.count(b'\n'), '输出出现非 CRLF'
open(P, 'wb').write(out)

n1 = len(new) - 1
print('行数 %d -> %d  (净 %+d)' % (n0, n1, n1 - n0))
print('md5  %s -> %s' % (hashlib.md5(raw).hexdigest(), hashlib.md5(out).hexdigest()))
print('OK')
