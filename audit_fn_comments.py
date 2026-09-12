# -*- coding: utf-8 -*-
"""
函数注释审计：提取每个 UsrAI:: 函数定义的「头部注释块」与「函数内首部注释块」，
供人工对照"注释声明的行为/数值" vs "代码真值"。
输出 audit_fn_comments.txt
"""
import io, re, sys

SRC = "UsrAI.cpp"
lines = io.open(SRC, encoding="utf-8", newline="").read().split("\n")

# 函数定义行：顶层、含 UsrAI::
RE_DEF = re.compile(r"^[A-Za-z_][A-Za-z0-9_:<>,*&\s]*\s+UsrAI::([A-Za-z_][A-Za-z0-9_]*)\s*\(")
# 也匹配构造/析构等其它形式
RE_DEF2 = re.compile(r"^[A-Za-z_].*UsrAI::([A-Za-z_~][A-Za-z0-9_]*)\s*\(")

defs = []
for i, ln in enumerate(lines):
    m = RE_DEF.match(ln) or RE_DEF2.match(ln)
    if m:
        defs.append((i, m.group(1), ln.rstrip()))

# 找每个函数体结束（用大括号配平，从定义行开始）
def body_end(start):
    depth = 0
    started = False
    for j in range(start, min(start + 4000, len(lines))):
        s = lines[j]
        # 粗略剥离字符串与行注释，避免括号误计
        s2 = re.sub(r'//.*$', '', s)
        s2 = re.sub(r'"(\\.|[^"\\])*"', '""', s2)
        s2 = re.sub(r"'(\\.|[^'\\])*'", "''", s2)
        depth += s2.count("{") - s2.count("}")
        if "{" in s2:
            started = True
        if started and depth <= 0:
            return j
    return start

def comment_block_above(idx, maxback=40):
    """抓函数定义上方连续的注释行（含中间空行分隔的多个片段，取最近一段）"""
    out = []
    j = idx - 1
    # 跳过空行
    while j >= 0 and lines[j].strip() == "":
        j -= 1
    # 收集连续注释行
    while j >= 0 and (lines[j].lstrip().startswith("//") or lines[j].lstrip().startswith("/*") or lines[j].lstrip().startswith("*")):
        out.append(lines[j].rstrip())
        j -= 1
        if idx - j > maxback:
            break
    out.reverse()
    return out

def comment_block_inside(start, end, maxlines=30):
    """抓函数体首部的注释/说明行（最多 maxlines 行，遇到实质代码就停）"""
    out = []
    j = start
    seen_code = 0
    while j <= end and len(out) < maxlines:
        s = lines[j].rstrip()
        t = s.strip()
        if t.startswith("//") or t.startswith("/*") or t.startswith("*"):
            out.append(s)
        elif t == "" or t == "{":
            pass
        else:
            seen_code += 1
            if seen_code > 6:
                break
        j += 1
    return out

buf = []
buf.append("# 函数注释审计底稿  source=%s  总行数=%d  函数数=%d\n" % (SRC, len(lines), len(defs)))

for k, (i, name, sig) in enumerate(defs):
    end = body_end(i)
    buf.append("=" * 100)
    buf.append("[%02d] %s   LINE %d~%d  (%d 行)" % (k + 1, name, i + 1, end + 1, end - i + 1))
    buf.append("SIG: %s" % sig.strip())
    above = comment_block_above(i)
    if above:
        buf.append("--- 头部注释 ---")
        buf.extend(above)
    inside = comment_block_inside(i, end)
    if inside:
        buf.append("--- 函数内首部注释 ---")
        buf.extend(inside)
    # 函数内所有 TODO/FIXME/★ 标注
    stars = [(j + 1, lines[j].rstrip()) for j in range(i, end + 1)
             if re.search(r"TODO|FIXME|XXX|待办|待实现|未实现|暂未|留待|以后|后续", lines[j])]
    if stars:
        buf.append("--- TODO/未实现 标注 ---")
        for ln, txt in stars[:40]:
            buf.append("  L%d: %s" % (ln, txt.strip()[:180]))
    buf.append("")

io.open("audit_fn_comments.txt", "w", encoding="utf-8", newline="\n").write("\n".join(buf))
print("写出 audit_fn_comments.txt  函数数=%d" % len(defs))
print("文件行数=%d" % len(buf))
