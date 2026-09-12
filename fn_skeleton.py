# -*- coding: utf-8 -*-
"""
函数骨架提取：对指定函数，输出「顶层语句 + 其上方注释」，
用于快速核对"函数头注释声明的顺序/优先级" vs 代码真实结构。
用法: python fn_skeleton.py <函数名> [缩进阈值]
"""
import io, re, sys

SRC = "UsrAI.cpp"
lines = io.open(SRC, encoding="utf-8", newline="").read().split("\n")
COMMENT = re.compile(r"^\s*(//|/\*|\*)")

def find_fn(name):
    pat = re.compile(r"^[A-Za-z_].*UsrAI::" + re.escape(name) + r"\s*\(")
    for i, ln in enumerate(lines):
        if pat.match(ln):
            return i
    return -1

def fn_end(start):
    depth = 0; started = False
    for j in range(start, min(start + 6000, len(lines))):
        s = re.sub(r'//.*$', '', lines[j])
        s = re.sub(r'"(\\.|[^"\\])*"', '""', s)
        s = re.sub(r"'(\\.|[^'\\])*'", "''", s)
        depth += s.count("{") - s.count("}")
        if "{" in s: started = True
        if started and depth <= 0: return j
    return start

name = sys.argv[1]
START = find_fn(name)
if START < 0:
    print("未找到函数", name); sys.exit(1)
END = fn_end(START)
print("### %s  LINE %d~%d  (%d 行)" % (name, START + 1, END + 1, END - START + 1))
print()

pending = []
for j in range(START, END + 1):
    s = lines[j].rstrip()
    if COMMENT.match(s):
        pending.append(s.strip())
        continue
    # 顶层语句：缩进 ≤ 8 且非空
    indent = len(s) - len(s.lstrip())
    body = s.strip()
    if body and indent <= 8:
        for p in pending[-3:]:
            print("      " + p[:150])
        pending = []
        print("L%-6d %s" % (j + 1, s[:150]))
    elif body:
        pending = []
