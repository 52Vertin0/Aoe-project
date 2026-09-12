# -*- coding: utf-8 -*-
"""shrink_20260922_argjoin.py —— L1 级（纯排版）：把 DebugText 的 `.arg(...)` 续行并回上一条语句。

判据（安全）：
  · 目标行 strip() 后以 `.arg(` 开头  ⇒ 它是上一行的续行；
  · 上一行必须【不含 `//`】（否则并入会落到注释之后，改变语义）；
  · 并入后显示宽度 <= MAXW_ARG；
  · 自证：全文去掉所有空白后，字符序列必须完全一致（纯排版 ⇒ 归一化文本全等）。
  · CRLF 写回。
"""
import io, sys, re

SRC = sys.argv[1] if len(sys.argv) > 1 else 'UsrAI.cpp'
MAXW_ARG = int(sys.argv[2]) if len(sys.argv) > 2 else 200

raw = io.open(SRC, 'rb').read()
text = raw.decode('utf-8')
assert text.count('\r\n') == text.count('\n'), '存在非 CRLF 行尾，ABORT'
lines = text.split('\r\n')

def disp_w(s):
    return sum(2 if ord(ch) > 0x2E7F else 1 for ch in s)

def norm(t):
    return ''.join(t.split())

out = []
merged = 0
i = 0
while i < len(lines):
    cur = lines[i]
    # 消费所有紧随其后的 .arg( 续行
    while (i + 1 < len(lines)
           and lines[i + 1].strip().startswith('.arg(')
           and '//' not in cur):
        nxt = lines[i + 1].strip()
        if disp_w(cur + nxt) > MAXW_ARG:
            break
        cur = cur + nxt
        merged += 1
        i += 1
    out.append(cur)
    i += 1

if norm('\r\n'.join(lines)) != norm('\r\n'.join(out)):
    print('ABORT: 归一化文本不等')
    sys.exit(1)

io.open(SRC, 'wb').write('\r\n'.join(out).encode('utf-8'))
print('并回 .arg 续行 %d 处；总行数 %d -> %d (省 %d)' % (
    merged, len(lines), len(out), len(lines) - len(out)))
