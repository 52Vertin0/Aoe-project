import io, difflib
g = r"C:\new-aoe3.0.7g"
a=io.open(g+r"\UsrAI.cpp",encoding="utf-8",errors="replace").read().splitlines()
b=io.open(g+r"\UsrAI.cpp.bak_20261008_followcloser",encoding="utf-8",errors="replace").read().splitlines()
d=[l for l in difflib.unified_diff(a,b,lineterm="") if l.startswith(("+","-")) and not l.startswith(("+++","---"))]
print("diff 行数 =", len(d))
for l in d: print("  ", l[:120])