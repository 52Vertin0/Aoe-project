# -*- coding: utf-8 -*-
"""对照编译：干净源 / \r\r\n 变体 / \n\n 变体，统计 error、trigraph warning、行号。"""
import subprocess, os, re, sys

os.chdir(r'C:\new-aoe3.0.7g')
GXX = r'D:\360Downloads\Tools\mingw530_32\bin\g++.exe'
QT = r'D:/360Downloads/5.9.2/mingw53_32'
BASE = [GXX, '-fsyntax-only',
        '-fno-keep-inline-dllexport', '-O2', '-std=gnu++1y',
        '-Wextra', '-Wall', '-W', '-fexceptions', '-mthreads',
        '-DUNICODE', '-D_UNICODE', '-DQT_DEPRECATED_WARNINGS', '-DQT_NO_DEBUG',
        '-DQT_MULTIMEDIA_LIB', '-DQT_WIDGETS_LIB', '-DQT_GUI_LIB',
        '-DQT_NETWORK_LIB', '-DQT_CORE_LIB', '-DQT_NEEDS_QMAIN',
        '-I.', '-Irelease',
        '-I' + QT + '/include', '-I' + QT + '/include/QtMultimedia',
        '-I' + QT + '/include/QtWidgets', '-I' + QT + '/include/QtGui',
        '-I' + QT + '/include/QtANGLE', '-I' + QT + '/include/QtNetwork',
        '-I' + QT + '/include/QtCore', '-I' + QT + '/mkspecs/win32-g++']
MINGW_BIN = r'D:\360Downloads\Tools\mingw530_32\bin'
env = dict(os.environ)
env['PATH'] = MINGW_BIN + os.pathsep + env.get('PATH', '')

targets = [
    ('A 干净源            ', 'UsrAI.cpp'),
    ('B \\r\\r\\n 变体     ', r'_mangle\UsrAI_rrn.cpp'),
    ('C \\n\\n 变体        ', r'_mangle\UsrAI_blank.cpp'),
]

for tag, tgt in targets:
    if not os.path.exists(tgt):
        print('%s : 文件不存在 %s' % (tag, tgt)); continue
    r = subprocess.run(BASE + [tgt], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=env)
    out = (r.stdout or '') + (r.stderr or '')
    lines = out.splitlines()
    errs = [l for l in lines if re.search(r'^\S+:\d+:\d+: error', l)]
    tri = [l for l in lines if 'trigraph' in l]
    ww = [l for l in lines if 'write-strings' in l]
    print('=' * 78)
    print('%s rc=%d  总行=%d  errors=%d  trigraph警告=%d  write-strings=%d'
          % (tag, r.returncode, len(lines), len(errs), len(tri), len(ww)))
    for l in errs[:3]:
        print('   E| ' + l[:150])
    for l in tri[:4]:
        print('   T| ' + l[:120])
