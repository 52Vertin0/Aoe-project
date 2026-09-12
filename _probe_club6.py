# -*- coding: utf-8 -*-
"""四图 ×2 局抽检：看有无『祭司在反攻前早死』。
口径：
  - 结局 W/P/T/U（W=祭司转换敌武器厂；P=DEFEAT: Priest killed；T=TC毁；U=超时/未结算）
  - 反攻触发帧 = 'ALL WAVES DEFEATED! Counterattack! Frame=N'
  - 祭司死亡帧（仅 P 局）= 该局日志最大帧（祭司死后游戏再走 ~15 帧即结算）
  - 『反攻前早死』 = P 且 死亡帧 < 反攻触发帧（或该局根本没触发反攻）
"""
import glob, re, os, sys

TAG = sys.argv[1] if len(sys.argv) > 1 else 'club6probe'
FRAME_RE = re.compile(r'^\d\d:\d\d:\d\d+\s*\|\s*(\d+)\s*\|')

def frames_of(text):
    fr = []
    for line in text.splitlines():
        m = FRAME_RE.match(line)
        if m:
            fr.append(int(m.group(1)))
    return fr

def outcome(text):
    if '被祭司转换,归属阵营1->0' in text: return 'W'
    if 'DEFEAT: Priest killed' in text:   return 'P'
    if 'DEFEAT: Town Center destroyed' in text: return 'T'
    if '敌方 摧毁主营' in text: return 'T'   # ★ 我方 TC 被毁（AI 自身 defeat 打印可能来不及）
    return 'U'

def ca_frame(text):
    m = re.search(r'ALL WAVES DEFEATED! Counterattack! Frame=(\d+)', text)
    return int(m.group(1)) if m else None

def fmt(f):
    # 1500 帧/分钟 = 25fps
    if f is None: return '-'
    return f'{f} ({f/1500:.1f}分)'

print('=' * 104)
print(f'抽检 TAG={TAG}   判定：P(祭司死) 且 死亡帧 < 反攻触发帧 ⇒ 反攻前早死')
print('=' * 104)
print(f'{"文件":<26}{"结局":<5}{"最大帧":<16}{"反攻触发帧":<16}{"祭司死亡帧":<16}{"判定"}')
print('-' * 104)

summary = {}
for fn in sorted(glob.glob(f'{TAG}_*_r0_*.ait')):
    t = open(fn, encoding='utf-8', errors='replace').read()
    res = outcome(t)
    fr = frames_of(t)
    maxf = max(fr) if fr else 0
    ca = ca_frame(t)
    # 结局行是否出现（完整局判据）
    done = ('被祭司转换,归属阵营1->0' in t) or ('DEFEAT: Priest killed' in t) or ('DEFEAT: Town Center destroyed' in t) or maxf >= 44500
    if res == 'P':
        deathf = maxf
    else:
        deathf = None
    if res == 'P':
        verdict = ('★反攻前早死' if (ca is None or (deathf is not None and deathf < ca)) else '反攻后死')
        if ca is None: verdict += '（未触发反攻）'
    else:
        verdict = '-'
    name = os.path.basename(fn).replace(f'{TAG}_', '').replace('_r0_', ' / r0_')
    print(f'{name:<26}{res:<5}{fmt(maxf):<16}{fmt(ca):<16}{fmt(deathf):<16}{verdict}')
    key = fn.split(f'{TAG}_')[1].split('_r0_')[0]
    summary.setdefault(key, []).append((res, verdict))

print('=' * 104)
print('按图汇总：')
for mp, lst in summary.items():
    rs = ''.join(r for r, _ in lst)
    early = sum(1 for _, v in lst if '★反攻前早死' in v)
    print(f'  {mp:<8} n={len(lst)}  结局={rs}  反攻前早死={early}/{len(lst)}')
print('=' * 104)
print('说明：本抽检只 2 局/图，仅用于『有无』快速判断，不足以下胜率结论（n=2 噪声极大）。')
