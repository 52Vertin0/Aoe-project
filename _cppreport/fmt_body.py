# -*- coding: utf-8 -*-
"""给正文段落批量套「1.5 倍行距 + 首行缩进 2 字符」（分两次调用，因属性互斥）"""
import json, io, subprocess, sys, os

SKILL = r"D:\Program Files\wb\WorkBuddy\resources\app.asar.unpacked\resources\plugins\workbuddy-builtin\skills\tencent-local-office-edit"
F = "C:/Users/ZhuanZ/Downloads/C++课程设计报告_帝国时代游戏.docx"

d = json.load(io.open(r"C:\new-aoe3.0.7g\_ds7.json", encoding="utf-8"))
ranges = []
for n in d["nodes"]:
    if n.get("type") != "Paragraph":
        continue
    p = n["paragraph_index"]
    if p < 45 or p >= 180:
        continue
    pv = (n.get("text_preview") or "")
    if "Image" in pv or pv.startswith("图 1") or pv.startswith("图 2") or pv.startswith("图 3"):
        continue
    if n["end_index"] <= n["start_index"]:
        continue
    ranges.append({"begin": n["start_index"], "end": n["end_index"]})

print("待处理段落数 =", len(ranges))


def call(tool, payload):
    p = subprocess.run([sys.executable, "edsdk.py", "call", tool, "--json",
                        json.dumps(payload, ensure_ascii=False)],
                       cwd=SKILL, capture_output=True, text=True, encoding="utf-8")
    out = (p.stdout or "") + (p.stderr or "")
    return out.strip()[:200]


print("① 1.5 倍行距 + 两端对齐 ...")
print(call("doc_modify_paragraph", {"file_id": F, "ranges": ranges,
                                    "jc": "both", "line_spacing": 1.5, "line_spacing_rule": 1}))
print("② 首行缩进 2 字符 ...")
print(call("doc_modify_paragraph", {"file_id": F, "ranges": ranges,
                                    "first_line_indent_chars": 2}))
