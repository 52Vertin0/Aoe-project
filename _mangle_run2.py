# -*- coding: utf-8 -*-
"""两条验证：
   ① 把干净源做成变体 D（\r\r\n + 逐字节把 >=0x80 换成 '?'），看能否复现用户的 trigraph 警告批。
   ② 编译 D:\deepseek\optimize_new_aoe_20260921 下四个臂，看它们本身是否可编译。
"""
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

# ---------- 变体 D：逐字节 '?' 化 ----------
D = r'C:\new-aoe3.0.7g\_mangle'
os.makedirs(D, exist_ok=True)
raw = open(r'C:\new-aoe3.0.7g\UsrAI.cpp', 'rb').read()
ascii_bytes = bytes((c if c < 0x80 else 0x3F) for c in raw)      # >=0x80 -> '?'
d1 = ascii_bytes.replace(b'\r\n', b'\r\r\n')
P_D = os.path.join(D, 'UsrAI_qmark.cpp')
open(P_D, 'wb').write(d1)
print('变体D 字节 = %d，\\r\\r\\n = %d，\\?\\?X 序列 = %d'
      % (len(d1), d1.count(b'\r\r\n'), len(re.findall(rb'\?\?[=()<>/!\'-]', d1))))

def run(tag, tgt, cwd=None):
    r = subprocess.run(BASE + [tgt], cwd=cwd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=env)
    out = (r.stdout or '') + (r.stderr or '')
    lines = out.splitlines()
    errs = [l for l in lines if re.search(r':\d+:\d+: error', l)]
    tri = [l for l in lines if 'trigraph' in l]
    ww = [l for l in lines if 'write-strings' in l]
    print('%-26s rc=%d  errors=%d  trigraph=%d  write-strings=%d'
          % (tag, r.returncode, len(errs), len(tri), len(ww)))
    for l in errs[:2]:
        print('      E| ' + l[:130])
    for l in tri[:4]:
        print('      T| ' + l[:120])
    return out

print()
print('=== 变体 D（\\r\\r\\n + 中文→?）===')
run('D \\r\\r\\n + ?', r'_mangle\UsrAI_qmark.cpp')

print()
print('=== optimize_new_aoe_20260921 四个臂 ===')
for tag, arm in [('baseline', 'baseline'), ('slim', 'slim'), ('opt', 'opt'), ('opt2', 'opt2')]:
    d = os.path.join(r'D:\deepseek\optimize_new_aoe_20260921', arm)
    tgt = os.path.join(d, 'UsrAI.cpp')
    if os.path.exists(tgt):
        run('  ' + tag, tgt, cwd=d)
    else:
        print('%-26s 缺失 %s' % (tag, tgt))
