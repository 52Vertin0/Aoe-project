# -*- coding: utf-8 -*-
"""
注释引用核对：
1) 注释中出现的大写常量标识符（>=4 字符）是否在代码中真实存在（#define / 变量 / 枚举）
2) 注释中出现 "cpp:NNNN" / "UsrAI.cpp:NNNN" 行号引用，指向的行当前内容是否还是注释所说的东西
3) 注释中出现 "见 LNNNN" 等
输出到 audit_refs.txt
"""
import io, re, os, sys

SRC = "UsrAI.cpp"
raw = io.open(SRC, encoding="utf-8", newline="").read()
lines = raw.split("\n")

# ---- 1. 收集代码中真实存在的标识符 ----
defined = set()
for m in re.finditer(r"#define\s+([A-Za-z_][A-Za-z0-9_]*)", raw):
    defined.add(m.group(1))
for m in re.finditer(r"\b(?:const|static|int|double|bool|QString|std::\w+)\s+([A-Za-z_][A-Za-z0-9_]*)", raw):
    defined.add(m.group(1))
for m in re.finditer(r"\b([A-Z][A-Z0-9_]{3,})\b", raw):
    defined.add(m.group(1))
# 枚举成员 / 其他
for m in re.finditer(r"\b([A-Z][A-Za-z0-9_]{3,})\b", raw):
    defined.add(m.group(1))

# ---- 2. 逐行找注释行，抽取其中的大写标识符 ----
COMMENT = re.compile(r"^\s*(//|/\*|\*)")
CONSTID = re.compile(r"\b([A-Z][A-Z0-9_]{3,})\b")
# 排除常见英文/通用词
STOP = set("""
TODO FIXME XXX NOTE AI TC SN BL HP DPS ID OK ERROR WARNING TRUE FALSE NULL
HH MM SS KB MB GB UTF GBK JSON XML HTML HTTP CPU GPU RAM
""".split())

missing = {}
for i, ln in enumerate(lines):
    if not COMMENT.match(ln):
        continue
    for m in CONSTID.finditer(ln):
        name = m.group(1)
        if name in STOP:
            continue
        if name not in defined:
            missing.setdefault(name, []).append((i + 1, ln.strip()[:150]))

# ---- 3. 行号引用核对 ----
RE_LINEREF = re.compile(r"(?:cpp|UsrAI\.cpp|L)\s*[:：]\s*(\d{3,5})")
linerefs = []
for i, ln in enumerate(lines):
    if not COMMENT.match(ln):
        continue
    for m in RE_LINEREF.finditer(ln):
        tgt = int(m.group(1))
        content = lines[tgt - 1].strip() if 0 < tgt <= len(lines) else "<越界>"
        linerefs.append((i + 1, tgt, ln.strip()[:130], content[:130]))

out = []
out.append("# 注释引用核对  source=%s\n" % SRC)

out.append("\n## A. 注释中出现、但代码里找不到的「大写标识符」 (%d 个)\n" % len(missing))
for name, occ in sorted(missing.items(), key=lambda x: -len(x[1])):
    out.append("### %s   (出现 %d 次)" % (name, len(occ)))
    for lno, txt in occ[:6]:
        out.append("    L%d: %s" % (lno, txt))
    if len(occ) > 6:
        out.append("    ... 另 %d 处" % (len(occ) - 6))
    out.append("")

out.append("\n## B. 注释中的行号引用 → 当前该行真实内容 (%d 处)\n" % len(linerefs))
for cline, tgt, ctxt, actual in linerefs:
    flag = ""
    out.append("注释L%-6d 引用 L%-6d" % (cline, tgt))
    out.append("    注释文字: %s" % ctxt)
    out.append("    该行实际: %s" % actual)
    out.append("")

io.open("audit_refs.txt", "w", encoding="utf-8", newline="\n").write("\n".join(out))
print("写出 audit_refs.txt")
print("A 段：注释提及但代码不存在的大写标识符 = %d" % len(missing))
print("B 段：行号引用 = %d" % len(linerefs))
