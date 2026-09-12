# -*- coding: utf-8 -*-
import io, re
p = r"C:\new-aoe3.0.7g\UsrAI.cpp"
s = io.open(p, encoding="utf-8").read()
def rep(pat, new, n=1):
    global s
    m = re.findall(pat, s, re.M)
    assert len(m) == n, "pattern %r found %d" % (pat, len(m))
    s = re.sub(pat, new, s, count=n, flags=re.M)

# ★ 2026-10-08【祭司跟随距离】三常量收紧
rep(r'^#define PRIEST_WITH_ARMY_LEAD 12\.0',
    '#define PRIEST_WITH_ARMY_LEAD 6.0   // \u2605\u8ddf\u968f\u8ddd\u79bb\uff1a\u795e\u53f8\u6700\u591a\u9886\u5148\u519b\u961f\u524d\u6cbf 6 \u683c\uff08\u539f 12\uff09')
rep(r'^#define PRIEST_SAFE_BEHIND     8\.0',
    '#define PRIEST_SAFE_BEHIND     3.0   // \u2605\u8ddf\u968f\u8ddd\u79bb\uff1a\u8ddf\u5728\u5927\u961f\u91cd\u5fc3\u540e 3 \u683c\uff08\u539f 8\uff09')
rep(r'^#define PRIEST_MIN_DIST_TARGET 18\.0',
    '#define PRIEST_MIN_DIST_TARGET 12.0  // \u2605\u8ddf\u968f\u8ddd\u79bb\uff1a\u4e0e\u53cd\u653b\u76ee\u6807\u6700\u5c0f\u5b89\u5168\u8ddd 12 \u683c\uff08\u539f 18\uff09=\u611f\u5316\u5c04\u7a0b')
io.open(p, "wb").write(s.encode("utf-8"))
print("follow-distance patch OK, len:", len(s))