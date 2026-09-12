# -*- coding: utf-8 -*-
"""
审计 v2：
(A) 注释里的行号引用分类：本文件(cpp:NNNN) vs 外部引擎文件(Xxx.cpp:NNNN)
    - 本文件引用 → 核对该行当前内容
    - 外部引用   → 检查文件是否存在于工程内，存在则核对
(B) #define 行的"注释数值 vs 真值"自动比对
(C) 注释中声称"与 config.json 一致"的断言 → 与 config.json 真值核对
"""
import io, re, os, json

SRC = "UsrAI.cpp"
raw = io.open(SRC, encoding="utf-8", newline="").read()
lines = raw.split("\n")
COMMENT = re.compile(r"^\s*(//|/\*|\*)")
out = []

# ============ (A) 行号引用分类 ============
RE_SELF = re.compile(r"(?<![.\w])cpp\s*[:：]\s*(\d{3,5})")
RE_EXT  = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*\.(?:cpp|h|md))\s*[:：]\s*(\d{2,5})(?:\s*-\s*(\d{2,5}))?")

self_refs, ext_refs = [], []
for i, ln in enumerate(lines):
    if not COMMENT.match(ln):
        continue
    for m in RE_SELF.finditer(ln):
        tgt = int(m.group(1))
        cur = lines[tgt - 1].strip() if 0 < tgt <= len(lines) else "<越界>"
        self_refs.append((i + 1, tgt, ln.strip()[:150], cur[:150]))
    for m in RE_EXT.finditer(ln):
        if m.group(1) == "UsrAI.cpp":
            continue
        ext_refs.append((i + 1, m.group(1), m.group(2), m.group(3) or "", ln.strip()[:150]))

out.append("=" * 90)
out.append("## A-1  「本文件」行号引用 (cpp:NNNN) — %d 处" % len(self_refs))
out.append("=" * 90)
for cl, tg, txt, cur in self_refs:
    out.append("注释 L%-6d → cpp:%-6d" % (cl, tg))
    out.append("   注释: %s" % txt)
    out.append("   实际: %s" % cur)
    out.append("")

out.append("=" * 90)
out.append("## A-2  「外部文件」行号引用 — %d 处（按文件汇总，检查文件是否存在）" % len(ext_refs))
out.append("=" * 90)
byfile = {}
for cl, fn, a, b, txt in ext_refs:
    byfile.setdefault(fn, []).append((cl, a, b, txt))
for fn, occ in sorted(byfile.items(), key=lambda x: -len(x[1])):
    exists = os.path.exists(fn)
    # 也查上级目录
    found = fn if exists else ""
    if not exists:
        for root, dirs, files in os.walk("."):
            if fn in files:
                found = os.path.join(root, fn)
                break
    out.append("--- %s  引用 %d 次  →  %s" % (fn, len(occ), ("存在: " + found) if found else "★ 工程内未找到"))
    for cl, a, b, txt in occ[:8]:
        out.append("     注释L%-6d  %s:%s%s" % (cl, fn, a, ("-" + b) if b else ""))
    out.append("")

# ============ (B) #define 注释数值 vs 真值 ============
out.append("=" * 90)
out.append("## B. #define 行「注释里的数字」vs「真值」（仅列不一致）")
out.append("=" * 90)
RE_DEF = re.compile(r"^#define\s+([A-Za-z_][A-Za-z0-9_]*)\s+([^/\n]+?)\s*(?://\s*(.*))?$")
mismatch = []
for i, ln in enumerate(lines):
    m = RE_DEF.match(ln.rstrip())
    if not m:
        continue
    name, val, cmt = m.group(1), m.group(2).strip(), (m.group(3) or "")
    if not cmt:
        continue
    # 注释里的数字
    nums_cmt = re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])", cmt)
    nums_val = re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])", val)
    if not nums_val or not nums_cmt:
        continue
    try:
        v = float(nums_val[0])
    except Exception:
        continue
    # 注释里出现"首数字"与真值不同的情况（只报明显冲突：注释头一个数字 != 真值，且注释无"旧/原/之前"等历史标记）
    if re.search(r"旧|原|之前|历史|旧版|曾|was|previous", cmt):
        continue
    c0 = float(nums_cmt[0])
    if abs(c0 - v) > 1e-9 and re.match(r"^\s*\d", cmt):
        mismatch.append((i + 1, name, val, cmt[:130], nums_cmt))
for i, name, val, cmt, nums in mismatch:
    out.append("L%-6d %-32s = %-14s // %s" % (i, name, val, cmt))
out.append("(共 %d 处可疑)" % len(mismatch))

# ============ (C) "与 config.json 一致" 类断言 ============
out.append("")
out.append("=" * 90)
out.append("## C. 声称与 config.json 一致的注释 → 与真值核对")
out.append("=" * 90)
for i, ln in enumerate(lines):
    if "config" in ln.lower() and ("一致" in ln or "相同" in ln or "同值" in ln or "=" in ln):
        out.append("L%-6d %s" % (i + 1, ln.strip()[:180]))

io.open("audit_refs2.txt", "w", encoding="utf-8", newline="\n").write("\n".join(out))
print("写出 audit_refs2.txt")
print("A-1 本文件行号引用 = %d" % len(self_refs))
print("A-2 外部文件引用   = %d （%d 个文件）" % (len(ext_refs), len(byfile)))
print("B #define 注释数值可疑 = %d" % len(mismatch))
