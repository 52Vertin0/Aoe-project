# -*- coding: utf-8 -*-
"""
把「函数注释里提到的常量」逐个查出真值，输出对照表。
用于核对注释的数量声明（N 格 / N 帧 / N 人 / N 座）。
"""
import io, re

SRC = "UsrAI.cpp"
lines = io.open(SRC, encoding="utf-8", newline="").read().split("\n")
COMMENT = re.compile(r"^\s*(//|/\*|\*)")
RE_DEF = re.compile(r"^\s*#define\s+([A-Za-z_][A-Za-z0-9_]*)\s+(.+?)\s*(?://\s*(.*))?$")

# 常量真值表
vals = {}
for i, ln in enumerate(lines):
    m = RE_DEF.match(ln)
    if m:
        vals[m.group(1)] = (i + 1, m.group(2).strip(), (m.group(3) or "").strip())
# 类内常量（UsrAI.h）
try:
    h = io.open("UsrAI.h", encoding="utf-8", newline="").read().split("\n")
except Exception:
    h = []
hvals = {}
for i, ln in enumerate(h):
    m = re.match(r"^\s*(?:static\s+)?(?:const\s+)?(?:int|double|bool)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^;]+);", ln)
    if m:
        hvals[m.group(1)] = (i + 1, m.group(2).strip())

# 函数定义与范围
RE_FN = re.compile(r"^[A-Za-z_].*UsrAI::([A-Za-z_][A-Za-z0-9_]*)\s*\(")
fns = []
for i, ln in enumerate(lines):
    m = RE_FN.match(ln)
    if m:
        fns.append((i, m.group(1)))
fns.append((len(lines), "<END>"))

def end_of(k):
    start = fns[k][0]
    depth = 0; started = False
    for j in range(start, min(start + 6000, len(lines))):
        s = re.sub(r'//.*$', '', lines[j])
        s = re.sub(r'"(\\.|[^"\\])*"', '""', s)
        depth += s.count("{") - s.count("}")
        if "{" in s: started = True
        if started and depth <= 0: return j
    return start

out = []
out.append("# 函数注释 → 常量真值 对照表\n")
for k in range(len(fns) - 1):
    start, name = fns[k]
    end = end_of(k)
    # 头部注释（上方连续） + 函数内首部 20 行注释
    text = []
    j = start - 1
    while j >= 0 and (lines[j].strip() == "" or COMMENT.match(lines[j])):
        if COMMENT.match(lines[j]):
            text.append(lines[j])
        j -= 1
        if start - j > 60: break
    for j in range(start, min(start + 30, end + 1)):
        if COMMENT.match(lines[j]):
            text.append(lines[j])
    blob = "\n".join(text)
    ids = []
    for m in re.finditer(r"\b([A-Z][A-Z0-9_]{3,})\b", blob):
        nm = m.group(1)
        if nm not in ids:
            ids.append(nm)
    if not ids:
        continue
    out.append("=" * 80)
    out.append("### %s  (L%d~%d)" % (name, start + 1, end + 1))
    for nm in ids:
        if nm in vals:
            lno, v, cm = vals[nm]
            out.append("  %-34s = %-16s  [#define L%d]" % (nm, v, lno))
        elif nm in hvals:
            lno, v = hvals[nm]
            out.append("  %-34s = %-16s  [UsrAI.h L%d]" % (nm, v, lno))
        else:
            out.append("  %-34s ?? 未在 #define / UsrAI.h 成员中找到" % nm)
    out.append("")

io.open("audit_consts.txt", "w", encoding="utf-8", newline="\n").write("\n".join(out))
print("写出 audit_consts.txt")
print("函数数 =", len(fns) - 1)
