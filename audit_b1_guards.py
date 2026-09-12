# -*- coding: utf-8 -*-
"""
audit_b1_guards.py —— B1（谷仓箭塔科技链收口）静态等价审计表

把「改前 bak_20260920_pre_tierb_UsrAI.cpp」与「当前 UsrAI.cpp」里
每一处 [谷仓箭塔科技 / 铜器箭塔升级] 的【下发点 + 上溯守卫行】并排抽出来，
供逐块打勾核对（项目铁律：多块合并成共享实现时，肉眼看不见条件集合的差异）。

用法：python audit_b1_guards.py      输出：控制台 + b1_guard_audit.txt
"""
import io, re, sys

PAIRS = [
    ('改前', r"C:\new-aoe3.0.7g\bak_20260920_pre_tierb_UsrAI.cpp"),
    ('当前', r"C:\new-aoe3.0.7g\UsrAI.cpp"),
]
SITES = [
    ('ARROWTOWER 下发/调用', re.compile(r'(BUILDING_GRANARY_ARROWTOWER\s*\)|tryArrowTowerTech\(\))')),
    ('UPGRADE   下发/调用', re.compile(r'(BUILDING_GRANARY_ARROWTOWE_UPGRADE\s*\)|tryBronzeTowerUpgrade\(\))')),
]
BACK = 6


def load(p):
    with io.open(p, 'r', encoding='utf-8', errors='replace', newline='') as f:
        return f.read().replace('\r\n', '\n').split('\n')


def guards(lines, idx, back=BACK):
    out, i = [], idx - 1
    while i >= 0 and len(out) < back:
        s = lines[i].strip()
        if s and not s.startswith('//'):
            out.append('%5d | %s' % (i + 1, lines[i].rstrip()))
        i -= 1
    return list(reversed(out))


out = []
for tag, path in PAIRS:
    lines = load(path)
    out.append('=' * 100)
    out.append('### %s：%s   （共 %d 行）' % (tag, path.split('\\')[-1], len(lines)))
    for label, rx in SITES:
        out.append('-' * 100)
        out.append('--- %s ---' % label)
        hits = [i for i, l in enumerate(lines) if rx.search(l)]
        # 只保留“下发点/调用点”本体行（排除宏/注释里的同名引用）
        hits = [i for i in hits if not lines[i].strip().startswith('//')]
        for k, i in enumerate(hits, 1):
            out.append('  【第 %d 处】调用行 %d:' % (k, i + 1))
            for g in guards(lines, i):
                out.append('      ' + g)
            out.append('      %5d | %s' % (i + 1, lines[i].rstrip()))
            out.append('')

txt = '\n'.join(out)
io.open('b1_guard_audit.txt', 'w', encoding='utf-8', newline='\r\n').write(txt)
print(txt)
