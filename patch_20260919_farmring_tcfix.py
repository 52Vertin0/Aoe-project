# -*- coding: utf-8 -*-
"""修 std::sort 破坏「TC 恒居 anchors[0]」的约定。

根因（ff1 诊断日志实证）：
    [FARM-PICK f=18776] tc=(19,18) NA=5 a0=(13,34) base=0(13,34) r=4 -> (9,34)
  锚点集合 = [(13,34), (19,18), (23,32), (29,70), (29,74)]
  第二谷仓 (13,34) 的块坐标字典序 < TC (19,18) ⇒ std::sort 后它排到 [0]。
  而下游三处全部假定 anchors[0] == TC：
    ① 段 1 ringOf(anchors[0]...)   → "TC 环"
    ② 段 1 评分基准 base = 0
    ③ 剪枝 (double)r*r > bestD2
  ⇒ 农场实际建在 (13,34) 周围；相对真 TC 的 r 高达 16（正是 kd/fc 批观测到的外溢）。
"""
P = r'C:\new-aoe3.0.7g\UsrAI.cpp'
raw = open(P, 'rb').read().decode('utf-8')
crlf = raw.count('\r\n') > 0
t = raw.replace('\r\n', '\n')

OLD = """    std::sort(anchors.begin(), anchors.end());
    anchors.erase(std::unique(anchors.begin(), anchors.end()), anchors.end());
    const int NA = (int)anchors.size();
"""
NEW = """    // ★★★ 2026-09-19 修复：TC 必须恒居 anchors[0] ★★★
    //   旧代码对【含 TC 的整个 anchors】做 std::sort ⇒ 一旦某谷仓/仓库的块坐标字典序小于 TC，
    //   它就会顶掉 TC。实测本图第二谷仓 (13,34) 的 x=13 < TC (19,18) 的 x=19 ⇒ sort 后
    //   anchors[0]=(13,34)，而下游三处全部硬编码假定 [0]==TC：
    //     ① 段 1 的 ringOf(anchors[0]...) —— 号称「TC 环」，实际在谷仓周围枚举；
    //     ② 段 1 的评分基准 base=0；
    //     ③ 剪枝 (double)r*r > bestD2。
    //   ⇒ 农场被建到谷仓旁，相对真 TC 的距离高达 16 格（ff1 实证 (9,34)：相对 (13,34) 是 r=4，
    //     相对真 TC (19,18) 是 r=16）—— 这正是 kd/fc 批「r≥8 占 30%」的直接成因。
    //   修复：TC 单独置顶不参与排序，其余锚点排序去重后追加。
    if (anchors.size() > 1) {
        std::vector<std::pair<int, int> > rest(anchors.begin() + 1, anchors.end());
        std::sort(rest.begin(), rest.end());
        rest.erase(std::unique(rest.begin(), rest.end()), rest.end());
        anchors.resize(1);
        for (size_t i = 0; i < rest.size(); ++i)
            if (rest[i] != anchors[0]) anchors.push_back(rest[i]);
    }
    const int NA = (int)anchors.size();
"""

assert t.count(OLD) == 1, 'hits=%d' % t.count(OLD)
t = t.replace(OLD, NEW)

out = t.replace('\n', '\r\n') if crlf else t
open(P, 'wb').write(out.encode('utf-8'))
print('TCFIX ok  bytes=', len(out.encode('utf-8')))
