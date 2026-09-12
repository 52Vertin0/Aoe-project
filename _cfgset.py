# -*- coding: utf-8 -*-
"""改 config.json 的任意键（就地、只改第一处）。用法: python _cfgset.py KEY VALUE"""
import io, re, sys

P = r'C:\new-aoe3.0.7g\config.json'
k, v = sys.argv[1], sys.argv[2]
s = io.open(P, encoding='utf-8').read()
s2, hit = re.subn(r'("%s"\s*:\s*)([^,\n]+)' % re.escape(k), lambda m: m.group(1) + v, s, count=1)
assert hit == 1, '%s 命中 %d 处' % (k, hit)
io.open(P, 'w', encoding='utf-8', newline='').write(s2)
print('%s -> %s' % (k, v))
