# -*- coding: utf-8 -*-
"""M4：窗口开始时同步清除 kitingRetPrevDK（跨窗口比较是结构性误判源）。
每处断言命中数 == 1（此处共 3 处），全部通过才落盘。"""
import sys

P = "UsrAI.cpp"
OLD = ('                    kitingRetStuck[a.SN] = 0;   // \u2605 2026-09-14\uff1a'
       '\u6bcf\u5f00\u4e00\u4e2a\u65b0\u64a4\u9000\u7a97\u53e3\u90fd\u91cd\u8bd5"\u8fdc\u79bb\u76ee\u6807"\u6863\r\n')
NEW = OLD + (
    '                    // \u2605 2026-09-18 M4\uff08\u7ed3\u6784\u4fee\u6b63\uff09\uff1a'
    '\u7a97\u53e3\u5f00\u59cb\u5fc5\u987b\u540c\u65f6\u6e05\u9664 kitingRetPrevDK\uff0c\u5426\u5219\u300c\u6492\u4e0d\u52a8\u300d\u5224\u5b9a\u6052\u4e3a\u771f\u3002\r\n'
    '                    //   \u94c1\u8bc1\uff08gi/kb \u5404 24 \u5c40\uff09\uff1a\u65b0\u4e00\u8f6e RETREAT \u7531\u300c\u654c\u8d34\u8eab dK<=0.5R/0.9R\u300d\u89e6\u53d1\uff0c'
    '\u800c prevDK \u662f\u4e0a\u4e00\u8f6e\u7a97\u53e3\u672b\uff08\u6492\u5f97\u6700\u8fdc\uff09\u7684 dK\r\n'
    '                    //   \u21d2 \u672c\u8f6e\u9996\u5e27 dK \u5fc5\u5b9a < prevDK+0.3 \u21d2 stuck \u5fc5\u5806\u5230 1 \u21d2 '
    '\u7b2c 1 \u6863\u300c\u8fdc\u79bb\u654c\u300d\u6c38\u8fdc\u88ab\u8df3\u8fc7\uff0c\u53ea\u80fd\u8d70\u7b2c 2 \u6863\u300c\u671d TC\u300d\uff08\u65b9\u5411\u76f2\uff09\u3002\r\n'
    '                    //   \u5b9e\u6d4b\u5bf9\u5e94\uff1astuck=0 \u7684 1739 \u6b21 \u2248 stage=1 \u7684 1737 \u6b21\uff1b'
    'stage=2 \u5360 76.3%\u3001\u5176 dK \u62c9\u5f00\u6bd4\u4ec5 15%\uff0c\u800c stage=1 \u4e3a 90%\u3002\r\n'
    '                    kitingRetPrevDK.erase(a.SN);\r\n'
)

s = open(P, encoding="utf-8", newline="").read()
n = s.count(OLD)
print("anchor hits =", n)
assert n == 3, "expect exactly 3 hits, got %d" % n
s = s.replace(OLD, NEW)
open(P, "w", encoding="utf-8", newline="").write(s)
print("OK: patched 3 sites")
