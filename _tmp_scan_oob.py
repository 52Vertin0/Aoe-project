# -*- coding: utf-8 -*-
# 扫描引擎源码里的"定长数组 + 可疑下标"组合（越界写候选）
# 判据：数组声明为 [字面量]；其下标表达式含 SN / .size() / 变量
import re, sys, os

FILES = ["enemyai.cpp", "Core.cpp", "GlobalVariate.cpp", "Army.cpp", "Human.cpp",
         "Farmer.cpp", "Building.cpp", "Player.cpp", "Map.cpp", "Core_List.cpp",
         "Building_Resource.cpp", "Animal.cpp", "MoveObject.cpp", "Development.cpp"]

# static/普通 定长数组声明（含 2 维）
decl_re = re.compile(
    r'^\s*(?:static\s+)?(?:const\s+)?(?:unsigned\s+)?'
    r'(?:bool|char|short|int|long|float|double|size_t|'
    r'[A-Za-z_][A-Za-z0-9_:<>]*)\s+'
    r'([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*(\d+)\s*\]'
    r'(?:\s*\[\s*(\d+)\s*\])?\s*[;=]',
    re.M)

rows = []
for fn in FILES:
    if not os.path.exists(fn):
        continue
    src = open(fn, 'rb').read().decode('utf-8', 'replace')
    lines = src.split('\n')
    decls = {}
    for m in decl_re.finditer(src):
        name, n1, n2 = m.group(1), int(m.group(2)), m.group(3)
        ln = src[:m.start()].count('\n') + 1
        decls.setdefault(name, []).append((ln, n1, int(n2) if n2 else None))
    for name, ds in decls.items():
        # 收集所有 name[...] 的下标文本
        use_re = re.compile(r'(?<![A-Za-z0-9_])' + re.escape(name) + r'\s*\[([^\]]*)\]')
        uses = []
        for m in use_re.finditer(src):
            ln = src[:m.start()].count('\n') + 1
            idx = m.group(1).strip()
            # 跳过声明自身
            if any(ln == d[0] for d in ds):
                continue
            uses.append((ln, idx))
        # 只报"可疑下标"：含 SN / size() / 非纯字面量
        susp = []
        for ln, idx in uses:
            if re.search(r'\bSN\b|\.size\s*\(|\.capacity\s*\(|->SN', idx):
                susp.append((ln, idx, 'SN/SIZE'))
            elif not re.fullmatch(r'-?\d+', idx):
                susp.append((ln, idx, 'VAR'))
        if susp:
            rows.append((fn, name, ds, len(uses), susp))

for fn, name, ds, nuse, susp in rows:
    dl = ", ".join(f"L{l}:[{n1}]" + (f"[{n2}]" if n2 else "") for l, n1, n2 in ds)
    print(f"\n### {fn}  {name}   声明 {dl}   共 {nuse} 处引用")
    sn = [s for s in susp if s[2] == 'SN/SIZE']
    var = [s for s in susp if s[2] == 'VAR']
    if sn:
        print(f"  ★高危(SN/size 作下标) {len(sn)} 处:")
        for ln, idx, _ in sn[:12]:
            print(f"     L{ln}: {name}[{idx}]")
    if var:
        print(f"  次要(变量下标) {len(var)} 处:")
        for ln, idx, _ in var[:8]:
            print(f"     L{ln}: {name}[{idx}]")

print(f"\n=== 命中 {len(rows)} 个数组 ===")
