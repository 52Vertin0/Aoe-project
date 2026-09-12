# -*- coding: utf-8 -*-
"""对比改动前后 -fsyntax-only 的 warning 集合（忽略行号，只看类别+消息）。"""
import subprocess, os, re, shutil

os.chdir(r'C:\new-aoe3.0.7g')
GXX = r'D:\360Downloads\Tools\mingw530_32\bin\g++.exe'
QT = r'D:/360Downloads/5.9.2/mingw53_32'
BASE = ['-fsyntax-only', '-fno-keep-inline-dllexport', '-O2', '-std=gnu++1y',
        '-Wextra', '-Wall', '-W', '-fexceptions', '-mthreads',
        '-DUNICODE', '-D_UNICODE', '-DQT_DEPRECATED_WARNINGS', '-DQT_NO_DEBUG',
        '-DQT_MULTIMEDIA_LIB', '-DQT_WIDGETS_LIB', '-DQT_GUI_LIB',
        '-DQT_NETWORK_LIB', '-DQT_CORE_LIB', '-DQT_NEEDS_QMAIN',
        '-I.', '-Irelease',
        '-I' + QT + '/include', '-I' + QT + '/include/QtMultimedia',
        '-I' + QT + '/include/QtWidgets', '-I' + QT + '/include/QtGui',
        '-I' + QT + '/include/QtANGLE', '-I' + QT + '/include/QtNetwork',
        '-I' + QT + '/include/QtCore', '-I' + QT + '/mkspecs/win32-g++']
MINGW = r'D:\360Downloads\Tools\mingw530_32\bin'
env = dict(os.environ); env['PATH'] = MINGW + os.pathsep + env.get('PATH', '')

def run(path):
    r = subprocess.run([GXX] + BASE + [path], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=env)
    out = (r.stdout or '') + (r.stderr or '')
    ws = []
    for l in out.splitlines():
        if re.search(r'\bwarning\b', l):
            m = re.search(r'warning: (.*)', l)
            src = l.split(':')[0]
            ws.append((src, m.group(1).strip() if m else l.strip()))
    return r.returncode, ws

shutil.copyfile('UsrAI.cpp.bak_20260915_pre_siegeguard', 'tmp_pre.cpp')
shutil.copyfile('UsrAI.cpp', 'tmp_now.cpp')

rc1, a = run('tmp_pre.cpp')
rc2, b = run('tmp_now.cpp')
print('pre rc=%d warns=%d | now rc=%d warns=%d' % (rc1, len(a), rc2, len(b)))

from collections import Counter
ca, cb = Counter(a), Counter(b)
print('\n--- 只在 pre 出现:')
for k, v in (ca - cb).items(): print('  %dx %s | %s' % (v, k[0], k[1]))
print('--- 只在 now 出现:')
for k, v in (cb - ca).items(): print('  %dx %s | %s' % (v, k[0], k[1]))
print('\n--- 全量 now:')
for src, msg in b: print('   %-14s %s' % (src, msg[:110]))

for f in ('tmp_pre.cpp', 'tmp_now.cpp'):
    if os.path.exists(f): os.remove(f)
