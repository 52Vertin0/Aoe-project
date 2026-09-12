# -*- coding: utf-8 -*-
"""E2：逐字符替换 + \r\r\n，与用户日志的 60 条三元字做逐条比对。"""
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
        '-I' + QT + '/include/QtCore', '-I' + QT + '/mkspecs/win32-g++']
env = dict(os.environ)
env['PATH'] = r'D:\360Downloads\Tools\mingw530_32\bin' + os.pathsep + env.get('PATH', '')

D = r'C:\new-aoe3.0.7g\_mangle'
raw = open(r'C:\new-aoe3.0.7g\UsrAI.cpp', 'rb').read()
text = raw.decode('utf-8').replace('\r\n', '\n')
per_char = ''.join((ch if ord(ch) < 0x80 else '?') for ch in text)
b = per_char.replace('\n', '\r\r\n').encode('ascii')
P = os.path.join(D, 'UsrAI_qchar_rrn.cpp')
open(P, 'wb').write(b)
print('E2 字节 = %d，\\r\\r\\n = %d，\\?\\?X = %d'
      % (len(b), b.count(b'\r\r\n'), len(re.findall(rb'\?\?[=()<>/!\'-]', b))))

r = subprocess.run(BASE + [P], capture_output=True, text=True,
                   encoding='utf-8', errors='replace', env=env)
out = (r.stdout or '') + (r.stderr or '')
tri = re.findall(r':(\d+):(\d+): warning: trigraph (\S+) ignored', out)
err = re.findall(r':(\d+):(\d+): error: (.*)', out)
print('trigraph = %d 条 ; error = %s' % (len(tri), err[:1]))
got = {}
for ln, col, tg in tri:
    got.setdefault(int(ln), []).append((int(col), tg))

USER = [(761, 72, '??='), (1973, 62, '??-'),
        (2847, 146, '??)'), (3015, 193, '??)'),
        (3387, 80, '??('), (3387, 101, '??='), (3387, 115, '??='),
        (3541, 50, '??('), (3541, 64, '??)'),
        (3705, 144, '??='),
        (3793, 85, '??('), (3793, 108, '??='), (3793, 122, '??='),
        (3801, 77, '??('), (3801, 100, '??='),
        (3815, 71, '??='),
        (3971, 89, '??('), (3971, 104, '??='), (3971, 119, '??='), (3971, 137, '??='),
        (3977, 94, '??('), (3977, 113, '??='), (3977, 131, '??='),
        (3989, 71, '??='), (3989, 89, '??='), (3989, 115, '??='), (3989, 161, '??='),
        (4071, 47, '??('), (4071, 61, '??)'),
        (4097, 59, '??('), (4097, 77, '??)'),
        (5309, 91, '??('), (5309, 107, '??)'),
        (5321, 119, '??('), (5321, 133, '??)'),
        (6649, 59, '??='), (6649, 95, '??('),
        (6659, 61, '??='),
        (6715, 168, '??('), (6715, 198, '??('),
        (6729, 80, '??('), (7227, 64, '??('),
        (8499, 69, '??='), (8499, 86, '??='), (8499, 116, '??='),
        (8731, 92, '??)'),
        (8747, 118, '??/'), (8747, 127, '??)'),
        (8807, 79, '??('),
        (9023, 130, '??('), (9023, 143, '??/'), (9023, 153, '??)'),
        (9719, 54, '??/'),
        (9765, 67, '??<'), (9765, 74, '??='), (9765, 86, '??<'), (9765, 93, '??='), (9765, 113, '??='),
        (12111, 105, '??='), (12111, 115, '??(')]

ok = 0
bad = []
for ln, col, tg in USER:
    hit = any(t == tg for _, t in got.get(ln, []))
    if hit:
        ok += 1
    else:
        bad.append((ln, col, tg, got.get(ln, '—')))
print('用户 60 条中，E2 在同行命中 %d 条' % ok)
for x in bad:
    print('   未命中 user %d:%d %s | E2 该行 = %s' % x)
print()
print('E2 三元字总数 = %d ; 用户 = 60' % len(tri))
