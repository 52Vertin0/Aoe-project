# -*- coding: utf-8 -*-
"""Release 增量编译（mingw32-make）。rc/error 摘要 + 末尾日志。"""
import subprocess, os, sys, re

os.chdir(r'C:\new-aoe3.0.7g')
BIN = r'D:\360Downloads\Tools\mingw530_32\bin'
env = dict(os.environ)
env['PATH'] = BIN + os.pathsep + env.get('PATH', '')

r = subprocess.run([os.path.join(BIN, 'mingw32-make.exe'), '-f', 'Makefile.Release', '-j4'],
                   capture_output=True, text=True, errors='replace', env=env)
out = (r.stdout or '') + (r.stderr or '')
lines = out.splitlines()
errs = [l for l in lines if re.search(r'\berror\b', l)]
print('rc = %d ; errors = %d ; lines = %d' % (r.returncode, len(errs), len(lines)))
for l in errs[:10]:
    print('E| ' + l)
print('--- tail ---')
print('\n'.join(lines[-12:]))
