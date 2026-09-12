# -*- coding: utf-8 -*-
"""诊断跑局：复刻 wd_verify.sh 参数，跑 3 局收集 ait 日志，定位建筑待建根因。"""
import subprocess, os, sys, time

os.chdir(r'C:\new-aoe3.0.7g')
MINGW_BIN = r'D:\360Downloads\Tools\mingw530_32\bin'
QT_BIN = r'D:/360Downloads/5.9.2/mingw53_32/bin'
QT_PLUGINS = r'D:/360Downloads/5.9.2/mingw53_32/plugins'
EXE = r'C:\new-aoe3.0.7g\release\newAOE.exe'

env = dict(os.environ)
env['PATH'] = MINGW_BIN + os.pathsep + QT_BIN + os.pathsep + env.get('PATH', '')
env['QT_QPA_PLATFORM'] = 'offscreen'
env['QT_QPA_PLATFORM_PLUGIN_PATH'] = QT_PLUGINS

N = 3
for i in range(1, N + 1):
    ait = 'dg%d.ait' % i
    jsonl = 'dg%d.jsonl' % i
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
        out = (r.stdout or '') + (r.stderr or '')
    except subprocess.TimeoutExpired:
        rc = -1; out = '(timeout)'
    dt = time.time() - t0
    # 快速统计本局 BUILD-FAIL 数
    nf = 0
    if os.path.exists(ait):
        with open(ait, 'r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                if 'BUILD-FAIL' in line:
                    nf += 1
    print('run%d exit=%s dt=%.0fs BUILD-FAIL=%d %s' % (i, rc, dt, nf, time.strftime('%H:%M:%S')))
    sys.stdout.flush()

print('ALL DONE', time.strftime('%H:%M:%S'))
