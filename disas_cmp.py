# -*- coding: utf-8 -*-
"""
disas_cmp.py —— Tier B 反汇编结构比对
用途：把「改前/改后」两个 .o 中某个函数的反汇编按 nm 的 value/size 切出来，
     抽取【指令助记符序列】并做差分，用于证明"控制流等价"（而非逐字节相同）。
用法：python disas_cmp.py <pre.o> <cur.o> <符号1> [符号2 ...]
"""
import subprocess, sys, re, io, difflib

def nm_table(o):
    out = subprocess.run(['nm', '-S', '--size-sort', o],
                         capture_output=True, text=True, encoding='utf-8',
                         errors='replace').stdout
    t = {}
    for l in out.splitlines():
        q = l.split()
        if len(q) >= 4:
            try:
                t[q[3]] = (int(q[0], 16), int(q[1], 16))
            except ValueError:
                pass
    return t

def disas(o):
    out = subprocess.run(['objdump', '-d', o], capture_output=True, text=True,
                         encoding='utf-8', errors='replace').stdout
    ins = []
    for l in out.splitlines():
        m = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S+)(.*)$', l)
        if m:
            ins.append((int(m.group(1), 16), m.group(3), m.group(4).strip()))
    return ins

def slice_fn(ins, table, name):
    if name not in table:
        return None
    addr, size = table[name]
    return [x for x in ins if addr <= x[0] < addr + size]

def norm(seq):
    """归一化：去掉跳转目标地址与立即数中的地址，只留助记符+操作数形态。"""
    out = []
    for a, mn, ops in seq:
        ops = re.sub(r'\b[0-9a-f]{4,}\b', 'IMM', ops)      # 地址/大立即数
        ops = re.sub(r'%(e[a-z]{2})', '%reg', ops)
        ops = re.sub(r'\$0x[0-9a-f]+', '$K', ops)
        ops = re.sub(r'-?0x[0-9a-f]+\(%reg\)', 'OFF(%reg)', ops)
        out.append(mn + ' ' + ops)
    return out

pre, cur, names = sys.argv[1], sys.argv[2], sys.argv[3:]
TA, TC = nm_table(pre), nm_table(cur)
IA, IC = disas(pre), disas(cur)

for n in names:
    sa, sc = slice_fn(IA, TA, n), slice_fn(IC, TC, n)
    if sa is None or sc is None:
        print('== %s == 缺符号 (pre=%s cur=%s)' % (n[-40:], sa is not None, sc is not None))
        continue
    na, nc = norm(sa), norm(sc)
    print('== %s ==' % n[-56:])
    print('   指令数 %d -> %d   | 字节 %d -> %d' % (
        len(na), len(nc), TA[n][1], TC[n][1]))
    # 只统计"出现的助记符种类与次数"，避免顺序噪声
    import collections
    ca, cc = collections.Counter(x.split()[0] for x in na), collections.Counter(x.split()[0] for x in nc)
    add = {k: cc[k] - ca.get(k, 0) for k in cc if cc[k] != ca.get(k, 0)}
    rem = {k: ca[k] - cc.get(k, 0) for k in ca if ca[k] != cc.get(k, 0)}
    print('   助记符新增/增多: %s' % (add or '无'))
    print('   助记符消失/减少: %s' % (rem or '无'))
    sm = difflib.SequenceMatcher(None, na, nc, autojunk=False)
    print('   序列相似度 %.3f' % sm.ratio())
    print()
