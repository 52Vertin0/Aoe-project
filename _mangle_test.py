# -*- coding: utf-8 -*-
"""复现实验：把干净的 UsrAI.cpp 做成 \r\r\n（多一个 CR）/ \n\n（倍行距）后编译，看行号与错误是否与用户日志一致。"""
import os

SRC = r'C:\new-aoe3.0.7g\UsrAI.cpp'
D = r'C:\new-aoe3.0.7g\_mangle'
os.makedirs(D, exist_ok=True)

raw = open(SRC, 'rb').read()
print('源文件字节 = %d，CRLF = %d，孤立 LF = %d' % (
    len(raw), raw.count(b'\r\n'), raw.count(b'\n') - raw.count(b'\r\n')))

m1 = raw.replace(b'\r\n', b'\r\r\n')
open(os.path.join(D, 'UsrAI_rrn.cpp'), 'wb').write(m1)
print('变体1 \\r\\r\\n : 字节 = %d，\\r\\r\\n 数 = %d' % (len(m1), m1.count(b'\r\r\n')))

m2 = raw.replace(b'\r\n', b'\n\n')
open(os.path.join(D, 'UsrAI_blank.cpp'), 'wb').write(m2)
print('变体2 \\n\\n   : 字节 = %d' % len(m2))
