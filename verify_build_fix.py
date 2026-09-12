# -*- coding: utf-8 -*-
"""建筑待建修复验证批：跑 N 局，聚合
  [BUILD-ISSUE] 按 type、[BUILD-FAIL] 按 (type,ret)、"产生了新的X" 按建筑名、胜负。
用法: python verify_build_fix.py [N] [tag]
"""
import subprocess, os, sys, time, re
from collections import Counter, defaultdict

os.chdir(r'C:\new-aoe3.0.7g')
MINGW_BIN = r'D:\360Downloads\Tools\mingw530_32\bin'
QT_BIN = r'D:/360Downloads/5.9.2/mingw53_32/bin'
QT_PLUGINS = r'D:/360Downloads/5.9.2/mingw53_32/plugins'
EXE = r'C:\new-aoe3.0.7g\release\newAOE.exe'

env = dict(os.environ)
env['PATH'] = MINGW_BIN + os.pathsep + QT_BIN + os.pathsep + env.get('PATH', '')
env['QT_QPA_PLATFORM'] = 'offscreen'
env['QT_QPA_PLATFORM_PLUGIN_PATH'] = QT_PLUGINS

BT = {0: 'HOME', 1: 'GRANARY', 2: 'CENTER', 3: 'STOCK', 4: 'FARM', 5: 'MARKET',
      6: 'ARROWTOWER', 7: 'ARMYCAMP', 8: 'STABLE', 9: 'RANGE', 12: 'COLLAGE'}

N = int(sys.argv[1]) if len(sys.argv) > 1 else 16
tag = sys.argv[2] if len(sys.argv) > 2 else 'fix'
# ★ 2026-09-21 新增：可指定 exe 路径 ⇒ 做 A/B 对照臂时无需覆盖 release/newAOE.exe
EXE = sys.argv[3] if len(sys.argv) > 3 else EXE

agg_fail = Counter()          # (type,ret) -> n
agg_fail_by_type = Counter()  # type -> n
agg_issue = Counter()         # type -> n
agg_built = Counter()         # 建筑名 -> n
games = []                    # (exit, dt, dict)

for i in range(1, N + 1):
    ait = 'vf_%s_%d.ait' % (tag, i)
    jsonl = 'vf_%s_%d.jsonl' % (tag, i)
    for f in (ait, jsonl):
        if os.path.exists(f):
            os.remove(f)
    t0 = time.time()
    try:
        r = subprocess.run([EXE, '-exam', '-offscreen', '-freq', 'MAX',
                            '-map', 'map3.njust', '-rotate', '90',
                            '-ResultLogFile', jsonl, '-AITextLog', ait],
                           capture_output=True, text=True, errors='replace',
                           env=env, timeout=350)
        rc = r.returncode
    except subprocess.TimeoutExpired:
        rc = -1
    dt = time.time() - t0

    fail = Counter(); issue = Counter(); built = Counter()
    win = lose = 0
    last_frame = 0
    if os.path.exists(ait):
        with open(ait, 'r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                p = line.split(' | ', 3)
                if len(p) >= 2:
                    try:
                        fr = int(p[1])
                        if fr > last_frame:
                            last_frame = fr
                    except ValueError:
                        pass
                if '[BUILD-FAIL' in line:
                    m = re.search(r'type=(\d+) ret=(\d+) at=\((-?\d+),(-?\d+)\)', line)
                    if m:
                        t, rt = int(m.group(1)), int(m.group(2))
                        fail[(t, rt)] += 1
                elif '[BUILD-ISSUE' in line:
                    m = re.search(r'type=(\d+)', line)
                    if m:
                        issue[int(m.group(1))] += 1
                elif '产生了新的' in line:
                    m = re.search(r'产生了新的(.+)', line)
                    if m:
                        built[m.group(1).strip().rstrip('!').strip()] += 1
                if 'VICTORY! Siege Workshop converted' in line:
                    win += 1
                if 'DEFEAT:' in line:
                    lose += 1
    for k, v in fail.items():
        agg_fail[k] += v
        agg_fail_by_type[k[0]] += v
    for k, v in issue.items():
        agg_issue[k] += v
    for k, v in built.items():
        agg_built[k] += v

    games.append((rc, dt, last_frame, dict(issue), dict(fail), dict(built), win, lose))
    nf = sum(fail.values())
    print('run%-2d exit=%s dt=%4.0fs lastFr=%5d ISSUE=%d FAIL=%d built=%d W/L=%d/%d  %s'
          % (i, rc, dt, last_frame, sum(issue.values()), nf, sum(built.values()),
             win, lose, time.strftime('%H:%M:%S')))
    sys.stdout.flush()

print('\n===== AGGREGATE (%d games) =====' % N)
print('BUILD-ISSUE by type:', {BT.get(k, k): v for k, v in sorted(agg_issue.items())})
print('BUILD-FAIL  total=%d' % sum(agg_fail.values()))
print('  by type:', {BT.get(k, k): v for k, v in sorted(agg_fail_by_type.items())})
print('  by (type,ret):', [('%s ret%d' % (BT.get(k[0], k[0]), k[1]), v)
                           for k, v in sorted(agg_fail.items())])
print('built (产生了新的X):', dict(sorted(agg_built.items(), key=lambda x: -x[1])))
print('games with ret=4 :', sum(1 for g in games if any(k[1] == 4 for k in g[4])))
print('games with ret=20:', sum(1 for g in games if any(k[1] == 20 for k in g[4])))
print('games with 0 FAIL:', sum(1 for g in games if sum(g[4].values()) == 0))
print('WINS=%d LOSSES=%d' % (sum(g[6] for g in games), sum(g[7] for g in games)))
print('ALL DONE', time.strftime('%H:%M:%S'))
