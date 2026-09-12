# -*- coding: utf-8 -*-
"""对比任意两个源码文件的 -fsyntax-only warning 集合（忽略行号，只看类别+消息）。
用法: python warn_cmp2.py <base.cpp> <now.cpp>
"""
import subprocess, os, re, sys

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
    ws, errs = [], []
    for l in out.splitlines():
        if re.search(r'\berror\b', l):
            errs.append(l.strip())
        if re.search(r'\bwarning\b', l):
            m = re.search(r'warning: (.*)', l)
            src = l.split(':')[0]
            ws.append((src, m.group(1).strip() if m else l.strip()))
    return r.returncode, ws, errs

base_p, now_p = sys.argv[1], sys.argv[2]
import shutil
shutil.copyfile(base_p, 'tmp_wb.cpp')
shutil.copyfile(now_p, 'tmp_wn.cpp')
rc1, a, e1 = run('tmp_wb.cpp')
rc2, b, e2 = run('tmp_wn.cpp')
print('BASE(%s) rc=%d warns=%d errors=%d' % (os.path.basename(base_p), rc1, len(a), len(e1)))
print('NOW (%s) rc=%d warns=%d errors=%d' % (os.path.basename(now_p), rc2, len(b), len(e2)))
for x in e1: print('  BASE-ERR: %s' % x[:160])
for x in e2: print('  NOW-ERR : %s' % x[:160])

from collections import Counter
ca, cb = Counter(a), Counter(b)
print('\n--- 只在 BASE 出现:')
for k, v in (ca - cb).items(): print('  %dx %s | %s' % (v, k[0], k[1]))
print('--- 只在 NOW 出现:')
for k, v in (cb - ca).items(): print('  %dx %s | %s' % (v, k[0], k[1]))
if ca == cb:
    print('  ✓ warning 集合完全一致')
for f in ('tmp_wb.cpp', 'tmp_wn.cpp'):
    if os.path.exists(f): os.remove(f)
