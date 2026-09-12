# -*- coding: utf-8 -*-
"""扫描候选目录，找出含 \r\r\n 行尾、或非 UTF-8 的 UsrAI*.cpp 副本。"""
import os

roots = [r'C:\new-aoe3.0.7g', r'C:\new-aoe3.0.7h', r'C:\Users\ZhuanZ\aoe_project',
         r'C:\Users\ZhuanZ\aoe_workspace', r'D:\deepseek\newAOE', r'D:\new-aoe3.0.7a',
         r'C:\Users\ZhuanZ\Desktop', r'C:\Users\ZhuanZ\Downloads', r'C:\Users\ZhuanZ\Documents',
         r'D:\\']
hits = 0
listed = 0
for r in roots:
    if not os.path.isdir(r):
        continue
    for dp, dn, fn in os.walk(r):
        parts = dp.split(os.sep)
        if 'release' in parts or '.git' in parts or 'tmpbuild' in parts or '$RECYCLE.BIN' in dp:
            continue
        for f in fn:
            low = f.lower()
            if not (low.endswith('.cpp') or low.endswith('.txt') or low.endswith('.h')):
                continue
            p = os.path.join(dp, f)
            try:
                b = open(p, 'rb').read()
            except Exception:
                continue
            rr = b.count(b'\r\r\n')
            if rr:
                hits += 1
                print('RR-CRLF  x%-6d  %s' % (rr, p))
                continue
            if low.startswith('usrai') and listed < 40:
                listed += 1
                nl = b.count(b'\n')
                blank = sum(1 for L in b.split(b'\n') if L.strip() == b'')
                try:
                    b.decode('utf-8'); enc = 'utf-8'
                except Exception:
                    enc = 'NOT-utf8'
                print('  normal  %-56s 行=%-6d 空行=%-5d %s' % (p, nl, blank, enc))
print('含 \\r\\r\\n 的文件数 =', hits)
