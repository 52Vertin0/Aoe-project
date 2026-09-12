# -*- coding: utf-8 -*-
"""语法检查（g++ -fsyntax-only），参数抄自 Makefile.Release。"""
import subprocess, os, sys, re

os.chdir(r'C:\new-aoe3.0.7g')
GXX = r'D:\360Downloads\Tools\mingw530_32\bin\g++.exe'
QT = r'D:/360Downloads/5.9.2/mingw53_32'
args = [GXX, '-fsyntax-only',
        '-fno-keep-inline-dllexport', '-O2', '-std=gnu++1y',
        '-Wextra', '-Wall', '-W', '-fexceptions', '-mthreads',
        '-DUNICODE', '-D_UNICODE', '-DQT_DEPRECATED_WARNINGS', '-DQT_NO_DEBUG',
        '-DQT_MULTIMEDIA_LIB', '-DQT_WIDGETS_LIB', '-DQT_GUI_LIB',
        '-DQT_NETWORK_LIB', '-DQT_CORE_LIB', '-DQT_NEEDS_QMAIN',
        '-I.', '-Irelease',
        '-I' + QT + '/include',
        '-I' + QT + '/include/QtMultimedia',
        '-I' + QT + '/include/QtWidgets',
        '-I' + QT + '/include/QtGui',
        '-I' + QT + '/include/QtANGLE',
        '-I' + QT + '/include/QtNetwork',
        '-I' + QT + '/include/QtCore',
        '-I' + QT + '/mkspecs/win32-g++',
        'UsrAI.cpp']

target = sys.argv[1] if len(sys.argv) > 1 else 'UsrAI.cpp'
args[-1] = target

# ⚠ cc1plus.exe 需要 mingw bin 里的 DLL：不把该目录放进 PATH 时，cc1plus 会静默活着失败
#   （rc=1、无任何输出，极易误判为"语法通过"）。故显式前置工具链 bin。
MINGW_BIN = r'D:\360Downloads\Tools\mingw530_32\bin'
env = dict(os.environ)
env['PATH'] = MINGW_BIN + os.pathsep + env.get('PATH', '')

r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8',
                   errors='replace', env=env)
out = (r.stdout or '') + (r.stderr or '')
lines = out.splitlines()
errs = [l for l in lines if re.search(r'\berror\b', l)]
warns = [l for l in lines if re.search(r'\bwarning\b', l)]
print('rc = %d' % r.returncode)
print('errors = %d ; warnings = %d' % (len(errs), len(warns)))
for l in errs[:20]:
    print('E| ' + l)
for l in warns[:12]:
    print('W| ' + l)
if not lines:
    print('(no output)')
