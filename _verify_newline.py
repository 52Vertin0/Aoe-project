# -*- coding: utf-8 -*-
"""证明 apply_safe_slim.py 那处修复有效：同一份内容，两种写法，看落盘字节。"""
import os, tempfile

SRC = r'C:\new-aoe3.0.7g\UsrAI.cpp'
D = os.path.join(tempfile.gettempdir(), 'nlprobe')
os.makedirs(D, exist_ok=True)

# 取前 200 行做样本，正常化成 LF 后再按脚本的写法拼 CRLF
raw = open(SRC, 'rb').read()
seg = raw.split(b'\r\n')[:200]
cpp = b'\n'.join(seg).decode('utf-8')

bad = os.path.join(D, 'old_write_text.cpp')
good = os.path.join(D, 'new_open_newline.cpp')

# ---- 旧写法（bug）----
from pathlib import Path
Path(bad).write_text(cpp.replace("\n", "\r\n"), encoding="utf-8")
# ---- 新写法（修复后）----
with open(good, 'w', encoding='utf-8', newline='') as f:
    f.write(cpp.replace("\n", "\r\n"))

for tag, p in (('旧 write_text(默认 newline=None)', bad),
               ('新 open(newline="")', good)):
    b = open(p, 'rb').read()
    rr = b.count(b'\r\r\n')
    crlf = b.count(b'\r\n')
    lf = b.count(b'\n')
    lone_lf = lf - crlf
    print('%-32s  \\r\\r\\n=%-6d  \\r\\n=%-6d  孤立LF=%-4d  %s'
          % (tag, rr, crlf, lone_lf,
             '✗ 会断续行 / 行号翻倍' if rr else '✓ 干净'))
    if rr:
        i = b.find(b'\r\r\n')
        print('     首现字节列 %d，上下文 %s' % (i, b[max(0, i - 12):i + 6]))

# 读回校验的对比
print()
old_read = Path(bad).read_text(encoding='utf-8')
new_read = open(good, encoding='utf-8', newline='').read()
print('旧写法 read_text(默认) 里 "\\r\\r\\n" 出现次数 =', old_read.count('\r\r\n'),
      '  <- 归一化后看不见问题，自检形同虚设')
print('新写法 open(newline="") 里 "\\r\\n" 计数 =', new_read.count('\r\n'))

# 顺带：真源文件体检
print()
print('真源 %s : \\r\\r\\n=%d  \\r\\n=%d' % (SRC, raw.count(b'\r\r\n'), raw.count(b'\r\n')))
