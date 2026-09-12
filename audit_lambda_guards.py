# -*- coding: utf-8 -*-
"""
审计 shrink 轮：把 pre_shrink 与当前版里每个 tryBuild(BUILDING_*, ...) 调用点
的【守卫条件行】抽出来并排对照，找出"多块合并成 lambda 时条件分叉"的隐患。

用法: python audit_lambda_guards.py
输出: 控制台对照表 + guard_audit.txt
"""
import re, sys, io

PRE = r"C:\new-aoe3.0.7g\bak_20260915_pre_shrink_UsrAI.cpp"
CUR = r"C:\new-aoe3.0.7g\UsrAI.cpp"

TRY = re.compile(r'tryBuild\(\s*(BUILDING_[A-Z_]+)')

def load(p):
    with io.open(p, 'r', encoding='utf-8', errors='replace', newline='') as f:
        return f.read().replace('\r\n', '\n').split('\n')

def is_comment_or_blank(line):
    s = line.strip()
    return s == '' or s.startswith('//')

def guards(lines, idx, back=9):
    """向上收集 guard 行（跳过注释/空行），最多 back 行"""
    out = []
    j = idx - 1
    while j >= 0 and len(out) < back:
        if not is_comment_or_blank(lines[j]):
            out.append((j + 1, lines[j].strip()))
        j -= 1
    out.reverse()
    return out

def collect(lines):
    hits = []
    for i, L in enumerate(lines):
        m = TRY.search(L)
        if not m:
            continue
        hits.append({
            'line': i + 1,
            'type': m.group(1),
            'guards': guards(lines, i),
            'call': L.strip(),
        })
    return hits

def norm(txt):
    """归一化：去空白、去尾部分号/大括号差异，便于比对"""
    t = re.sub(r'\s+', '', txt)
    t = t.replace('builtThisFrame', 'BTF')
    return t

def main():
    pre = collect(load(PRE))
    cur = collect(load(CUR))
    out = []
    def w(s=''):
        out.append(s)

    w('=' * 100)
    w('pre_shrink 全部 tryBuild(BUILDING_*) 调用点: %d 个' % len(pre))
    w('=' * 100)
    for h in pre:
        w('--- [PRE] L%d  %s' % (h['line'], h['type']))
        for ln, g in h['guards']:
            w('      L%-6d %s' % (ln, g))
        w('      >> %s' % norm(h['call']))
    w()
    w('=' * 100)
    w('当前版 全部 tryBuild(BUILDING_*) 调用点: %d 个' % len(cur))
    w('=' * 100)
    for h in cur:
        w('--- [CUR] L%d  %s' % (h['line'], h['type']))
        for ln, g in h['guards']:
            w('      L%-6d %s' % (ln, g))
        w('      >> %s' % norm(h['call']))
    w()
    w('=' * 100)
    w('按建筑类型分组计数（看哪些类型的块被合并了）')
    w('=' * 100)
    from collections import Counter
    cp = Counter(h['type'] for h in pre)
    cc = Counter(h['type'] for h in cur)
    for t in sorted(set(cp) | set(cc)):
        w('  %-28s PRE=%d  CUR=%d  %s' % (t, cp.get(t, 0), cc.get(t, 0),
          '  <== 数量变化' if cp.get(t, 0) != cc.get(t, 0) else ''))

    txt = '\n'.join(out)
    print(txt)
    with io.open(r"C:\new-aoe3.0.7g\guard_audit.txt", 'w', encoding='utf-8') as f:
        f.write(txt)

if __name__ == '__main__':
    main()
