# -*- coding: utf-8 -*-
"""用当前 config.json 的 NOWPLAYER 跑一局，汇报 rc / ait 大小 / 末行 / 胜负。
用法: python _n3test.py TAG [TIMEOUT]
   rc=0 且 ait 尾行出现胜负 ⇒ 正常跑完
   rc=TIMEOUT 且 ait 巨大、末帧很大 ⇒ 仍在跑（超时设短了）
   rc=TIMEOUT 且 ait 只有 4KB、末帧=1 ⇒ 帧 1 就挂死（真挂）
"""
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

tag = sys.argv[1] if len(sys.argv) > 1 else 'n3'
tmo = int(sys.argv[2]) if len(sys.argv) > 2 else 150
ait = 'vf_%s_1.ait' % tag
jsonl = 'vf_%s_1.jsonl' % tag
for f in (ait, jsonl):
    if os.path.exists(f):
        os.remove(f)
t0 = time.time()
try:
    r = subprocess.run([EXE, '-exam', '-offscreen', '-freq', 'MAX', '-map', 'map3.njust',
                        '-rotate', '90', '-ResultLogFile', jsonl, '-AITextLog', ait],
                       capture_output=True, text=True, errors='replace', env=env, timeout=tmo)
    rc = r.returncode
    err = (r.stderr or '')[-400:]
except subprocess.TimeoutExpired:
    rc = 'TIMEOUT'; err = ''
dt = time.time() - t0

lines = []
if os.path.exists(ait):
    with open(ait, encoding='utf-8', errors='replace') as fh:
        lines = fh.read().splitlines()
size = os.path.getsize(ait) if os.path.exists(ait) else 0
lastfr = 0
for line in lines:
    p = line.split(' | ', 3)
    if len(p) >= 4:
        try:
            lastfr = max(lastfr, int(p[1]))
        except ValueError:
            pass
outcome = [l for l in lines if ('VICTORY!' in l or 'DEFEAT:' in l)]
print('tag=%s rc=%s 耗时=%.1fs ait=%dB 行=%d 末帧=%d 胜负=%s'
      % (tag, rc, dt, size, len(lines), lastfr,
         (outcome[-1].split(' | ', 3)[-1].strip()[:60] if outcome else '无')))
print('末行: %s' % (lines[-1][:130] if lines else '(空)'))
if err.strip():
    print('stderr尾部:', err.replace('\n', ' / ')[-300:])
