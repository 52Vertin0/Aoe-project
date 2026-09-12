# -*- coding: utf-8 -*-
"""精确辨识"中文变 ?"的路径：逐字节 / 逐字符 / GBK 往返，看哪种能对上用户日志的 60 条三元字警告。"""
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
MINGW_BIN = r'D:\360Downloads\Tools\mingw530_32\bin'
env = dict(os.environ)
env['PATH'] = MINGW_BIN + os.pathsep + env.get('PATH', '')

D = r'C:\new-aoe3.0.7g\_mangle'
os.makedirs(D, exist_ok=True)
raw = open(r'C:\new-aoe3.0.7g\UsrAI.cpp', 'rb').read()
text = raw.decode('utf-8')          # universal newlines -> \n

# E: 逐字符 -> '?'（非 ASCII 字符各 1 个 '?'）
e = text.replace('\r\n', '\n')
e = ''.join((ch if ord(ch) < 0x80 else '?') for ch in e)
e = e.replace('\n', '\r\n').encode('ascii')
P_E = os.path.join(D, 'UsrAI_qchar.cpp')
open(P_E, 'wb').write(e)

# F: GBK 往返（UTF-8 字节按 GBK 解 -> 按 GBK 写，不可映射 -> '?'）
try:
    f = text.encode('gbk', 'replace')
except Exception:
    f = text.encode('gbk', 'replace')
f = f.replace(b'\r\n', b'\r\r\n')
P_F = os.path.join(D, 'UsrAI_gbk.cpp')
open(P_F, 'wb').write(f)

print('逐字节变体 \\?\\?X = 1239（已知 → trigraph 73 条）')
print('逐字符变体 \\?\\?X = %d' % len(re.findall(rb'\?\?[=()<>/!\'-]', e)))
print('GBK往返  \\?\\?X = %d' % len(re.findall(rb'\?\?[=()<>/!\'-]', f)))
print()

USER = {761: [(72, '??=')], 1973: [(62, '??-')], 3387: [(80, '??('), (101, '??='), (115, '??=')],
        2847: [(146, '??)')], 9765: [(67, '??<'), (74, '??='), (86, '??<'), (93, '??='), (113, '??=')]}


def run(tag, path):
    r = subprocess.run(BASE + [path], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=env)
    out = (r.stdout or '') + (r.stderr or '')
    tri = re.findall(r'(\S+):(\d+):(\d+): warning: trigraph (\S+) ignored', out)
    errs = re.findall(r':(\d+):(\d+): error: (.*)', out)
    print('%-14s trigraph=%d  errors=%d' % (tag, len(tri), len(errs)))
    d = {}
    for _, ln, col, tg in tri:
        d.setdefault(int(ln), []).append((int(col), tg))
    ok = 0
    for ln, exp in USER.items():
        got = d.get(ln, [])
        hit = [g for g in got if any(g[1] == t for _, t in exp)]
        ok += 1 if hit else 0
        print('    user %-6d %-28s | got %s' % (ln, exp, got if got else '—'))
    print('    => 行命中 %d/%d' % (ok, len(USER)))
    return d


print('=== E 逐字符 ===')
dE = run('E 逐字符', P_E)
print()
print('=== F GBK 往返 ===')
dF = run('F GBK', P_F)
print()
print('=== 用户日志里的三元字行总计 60 条（手工数）===')
print('E 总条数 %d / F 总条数 %d / D(逐字节) 总条数 73'
      % (sum(len(v) for v in dE.values()), sum(len(v) for v in dF.values())))
