import io, difflib
a=io.open(r"C:\new-aoe3.0.7g\_submit.bak_20261008_pre_nodebug\UsrAI.cpp",encoding="utf-8",errors="replace").read().splitlines()
b=io.open(r"C:\new-aoe3.0.7g\_submit\nodebug\UsrAI.cpp",encoding="utf-8",errors="replace").read().splitlines()
d=[l for l in difflib.unified_diff(a,b,lineterm="",n=1) ]
print("diff 行数:", len(d))
for l in d[:60]: print("  ", l[:150])