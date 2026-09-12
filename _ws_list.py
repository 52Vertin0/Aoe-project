# -*- coding: utf-8 -*-
"""列出基线编译的全部 write-strings 警告行号，用于和用户日志的 15 条对齐比较。"""
import subprocess, os, re

os.chdir(r'C:\new-aoe3.0.7g')
GXX = r'D:\360Downloads\Tools\mingw530_32\bin\g++.exe'
QT = r'D:/360Downloads/5.9.2/mingw53_32'
PROJ = r'C:\new-aoe3.0.7g'
BASE = [GXX, '-fsyntax-only', '-fno-keep-inline-dllexport', '-O2', '-std=gnu++1y',
        '-Wextra', '-Wall', '-W', '-fexceptions', '-mthreads',
        '-DUNICODE', '-D_UNICODE', '-DQT_DEPRECATED_WARNINGS', '-DQT_NO_DEBUG',
        '-DQT_MULTIMEDIA_LIB', '-DQT_WIDGETS_LIB', '-DQT_GUI_LIB',
        '-DQT_NETWORK_LIB', '-DQT_CORE_LIB', '-DQT_NEEDS_QMAIN',
        '-I.', '-I' + PROJ, '-I' + PROJ + r'\release',
        '-I' + QT + '/include', '-I' + QT + '/include/QtMultimedia',
        '-I' + QT + '/include/QtWidgets', '-I' + QT + '/include/QtGui',
        '-I' + QT + '/include/QtANGLE', '-I' + QT + '/include/QtNetwork',
        '-I' + QT + '/include/QtCore', '-I' + QT + '/mkspecs/win32-g++',
        'UsrAI.cpp']
env = dict(os.environ)
env['PATH'] = r'D:\360Downloads\Tools\mingw530_32\bin' + os.pathsep + env.get('PATH', '')
r = subprocess.run(BASE, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
out = (r.stdout or '') + (r.stderr or '')
ws = re.findall(r'UsrAI\.cpp:(\d+):\d+: warning: ISO C\+\+ forbids converting', out)
print('我们的 write-strings 警告 %d 条：' % len(ws))
print('  行号 = ' + ', '.join(sorted(set(ws), key=int)))
# 映射到用户日志口径（2N-1）
print('  折算到用户日志口径(2N-1) = ' + ', '.join(str(2 * int(x) - 1) for x in sorted(set(ws), key=int)))
print()
print('用户日志里的 write-strings 行号 = 1027, 1049, 1145, 1177, 1189, 1201, 1247, 1281, 1961, 1973, 8295, 10165, 10261, 10283, 11321  (15 条)')
