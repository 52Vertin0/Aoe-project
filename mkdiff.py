# -*- coding: utf-8 -*-
"""生成 pre_shrink vs shrink 的逐段 diff（忽略 CRLF），写入 diff_shrink.txt 供人工复核。"""
import difflib

A = open('bak_20260915_pre_shrink_UsrAI.cpp', encoding='utf-8').read().replace('\r\n', '\n').split('\n')
B = open('UsrAI.cpp', encoding='utf-8').read().replace('\r\n', '\n').split('\n')

out = []
op = 0
for line in difflib.unified_diff(A, B, 'pre_shrink', 'shrink', lineterm='', n=2):
    out.append(line)
    if line.startswith('@@'):
        op += 1
open('diff_shrink.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('hunks = %d, diff lines = %d' % (op, len(out)))

# 统计新增/删除
adds = sum(1 for l in out if l.startswith('+') and not l.startswith('+++'))
dels = sum(1 for l in out if l.startswith('-') and not l.startswith('---'))
print('+%d / -%d' % (adds, dels))
