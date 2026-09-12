# -*- coding: utf-8 -*-
"""解析诊断局 ait 日志：统计 [BUILD-FAIL] 真实拒绝码分布 + [BUILD-ISSUE] 次数 +
是否最终"产生了新的X"（地基落下）。ret 码含义见引擎 ACTION_INVALID_*。"""
import os, re, sys, collections

BT = {1:'HOME',2:'GRANARY',3:'FARM',4:'MARKET',5:'ARMYCAMP',6:'RANGE',7:'STABLE',
      8:'ARROWTOWER',9:'STOCK',10:'COLLAGE'}
RET_NAME = {
    0:'SUCCESS?',
}
# 从 ins_ret 取值，未知码原样打印

def analyze(ait):
    fails = collections.Counter()          # (type, ret) -> n
    fail_samples = []
    issues = collections.Counter()         # type -> n
    built = collections.Counter()          # 产生了新的X 名 -> n
    fail_by_ret = collections.Counter()    # ret -> n
    with open(ait, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if '[BUILD-FAIL' in line:
                m = re.search(r'type=(\d+)\s+ret=(\-?\d+)\s+at=\((\-?\d+),(\-?\d+)\)', line)
                if m:
                    t, ret, x, y = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
                    fails[(BT.get(t,t), ret)] += 1
                    fail_by_ret[ret] += 1
                    if len(fail_samples) < 25:
                        fail_samples.append((BT.get(t,t), ret, x, y))
            elif '[BUILD-ISSUE' in line:
                m = re.search(r'type=(\d+)\b', line)
                if m:
                    issues[BT.get(int(m.group(1)), int(m.group(1)))] += 1
            elif '产生了新的' in line:
                m = re.search(r'产生了新的(.+?)(?:\(|$)', line)
                if m:
                    built[m.group(1).strip()] += 1
    return fails, fail_by_ret, issues, built, fail_samples

for i in range(1, 4):
    ait = 'dg%d.ait' % i
    if not os.path.exists(ait):
        print('== %s 不存在 ==' % ait); continue
    fails, fail_by_ret, issues, built, samples = analyze(ait)
    print('========== %s ==========' % ait)
    print('BUILD-ISSUE(按类型):', dict(issues))
    print('BUILD-FAIL(按 ret 汇总):', dict(fail_by_ret))
    print('BUILD-FAIL(按 类型,ret):')
    for k, v in sorted(fails.items(), key=lambda kv: -kv[1]):
        print('   %-10s ret=%-4s x%d' % (k[0], k[1], v))
    print('产生了新的(建筑落地基证据):', dict(built))
    if samples:
        print('失败样例(at 坐标):')
        for s in samples[:12]:
            print('   %-10s ret=%-4s at=(%d,%d)' % s)
    print()
print('DONE')
