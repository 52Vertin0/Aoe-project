# -*- coding: utf-8 -*-
import io
p = r"C:\new-aoe3.0.7g\UsrAI.cpp"
s = io.open(p, encoding="utf-8").read()
def rep(old, new, n=1):
    global s
    c = s.count(old)
    assert c == n, "anchor count=%d (want %d): %r" % (c, n, old[:70])
    s = s.replace(old, new, n)

rep("#define PRIEST_CONVERT_RANGE 28.0",
    "#define PRIEST_CONVERT_RANGE 36.0  // \u26052026-10-09\u3010\u795e\u53f8\u611f\u5316\u66f4\u6fc0\u8fdb\u3011\u2605 28\u219236 \u683c\uff1a\u66f4\u591a\u53ef\u9009\u611f\u5316\u76ee\u6807")

rep("        const double abortHp = danger ? 0.60 : 0.25;",
    "        // \u26052026-10-09\u3010\u795e\u53f8\u611f\u5316\u66f4\u6fc0\u8fdb\u3011\u2605 \u5f15\u5bfc\u4e2d\u65ad\u9608 0.60/0.25 \u2192 0.45/0.15\uff08\u4e0d\u8f7b\u6613\u6253\u65ad\u5f15\u5bfc\uff0c\u5b8c\u6210\u66f4\u591a\u611f\u5316\uff09\n"
    "        const double abortHp = danger ? 0.45 : 0.15;")

rep("#define PRIEST_SIEGE_CONVERT_LOCKOUT 400",
    "#define PRIEST_SIEGE_CONVERT_LOCKOUT 250  // \u2605\u611f\u5316\u66f4\u6fc0\u8fdb\uff1a400\u2192250 \u5e27\uff0816s\u219210s\uff09\uff0c\u88ab\u6253\u65ad\u540e\u66f4\u5feb\u91cd\u8bd5")

rep("#define PRIEST_SIEGE_GUARD_HP      0.45",
    "#define PRIEST_SIEGE_GUARD_HP      0.30  // \u2605\u611f\u5316\u66f4\u6fc0\u8fdb\uff1a0.45\u21920.30 \u6b8b\u8840\u4e5f\u6562\u8d77\u624b")
io.open(p, "wb").write(s.encode("utf-8"))
print("aggressive-priest patch OK, chars:", len(s))