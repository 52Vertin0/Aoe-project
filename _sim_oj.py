# -*- coding: utf-8 -*-
"""实验：把 MainWidget 的双 tryLock 去掉，模拟"评测机（无锁调用方）"，看能否复现 SIGSEGV。
   跑完必须还原（备份 MainWidget.cpp.bak_20260923_preojsim）。"""
import io, os, shutil

D = r'C:\new-aoe3.0.7g'
P = os.path.join(D, 'MainWidget.cpp')
BAK = P + '.bak_20260923_preojsim'

if not os.path.exists(BAK):
    shutil.copyfile(P, BAK)
    print('备份 ->', os.path.basename(BAK))
else:
    print('备份已存在，沿用')

s = io.open(P, encoding='utf-8').read()          # 归一成 \n 便于匹配

old = """            const bool usrGameLocked = tagUsrGame.tryLock();
            if (usrGameLocked) {
                const bool enemyGameLocked = tagEnemyGame.tryLock();
                if (enemyGameLocked) {
                    core->infoShare();

                    tagEnemyGame.release();
                    tagUsrGame.release();

                    // AI继续跑
                    emit startAI();
                }
                else {
                    tagUsrGame.release();
                }
            }"""

new = """            // \u2605 2026-09-23 实验：模拟评测机（调用方不持锁）—— 跑完必须还原！
            core->infoShare();
            emit startAI();"""

n = s.count(old)
print('锁块命中 =', n)
assert n == 1, '匹配数不为 1，中止'

io.open(P, 'w', encoding='utf-8', newline='').write(s.replace(old, new).replace('\n', '\r\n'))
print('已改为无锁调用（模拟评测机）')

# 回读确认
t = io.open(P, encoding='utf-8').read()
i = t.find('core->infoShare();')
print('--- 改后上下文 ---')
print('\n'.join('   ' + l for l in t[i - 260:i + 90].split('\n')))
