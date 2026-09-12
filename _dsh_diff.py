import io, difflib
g = r"C:\new-aoe3.0.7g"
def rd(p):
    return io.open(p, encoding="utf-8", errors="replace").read().splitlines()
cur  = rd(g + r"\UsrAI.cpp")
pe2  = rd(g + r"\UsrAI.cpp.bak_20261008_pre_safecast")
sc1  = rd(g + r"\UsrAI.cpp.bak_20261008_safecast_rejected")
far  = rd(g + r"\UsrAI.cpp.bak_20261008_farmer20")
out = []
def summ(name, a, b):
    d = list(difflib.unified_diff(a, b, lineterm="", n=3))
    adds = sum(1 for l in d if l.startswith("+") and not l.startswith("+++"))
    dels = sum(1 for l in d if l.startswith("-") and not l.startswith("---"))
    out.append("=== %s : +%d -%d ===" % (name, adds, dels))
    out.extend(d)
summ("current vs pe2", pe2, cur)
out.append("")
out.append("farmer20 == sc1 ? %s" % (far == sc1))
out.append("farmer20 vs pe2 diff:")
summ("farmer20 vs pe2", pe2, far)
io.open(g + r"\_dsh_diff.txt", "w", encoding="utf-8").write("\n".join(out))
print("written")