# -*- coding: utf-8 -*-
"""删除 P1 残留行 chkThreat(e.DR, e.UR, r);（r 已被替换掉，该行是脚本区间边界 bug 的残留）。"""
P = 'UsrAI.cpp'
s = open(P, encoding='utf-8', newline='').read()
assert '\r\n' in s, 'CRLF 缺失'
old = ("            chkThreat(e.DR, e.UR, enemyThreatRange(e.Sort));\r\n"
       "            chkThreat(e.DR, e.UR, r);\r\n")
n = s.count(old)
assert n == 1, '匹配 %d 次' % n
s = s.replace(old, "            chkThreat(e.DR, e.UR, enemyThreatRange(e.Sort));\r\n")
open(P, 'w', encoding='utf-8', newline='').write(s)
print('ok 删残留行；行数 =', s.count('\n') + 1)
