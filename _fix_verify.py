# -*- coding: utf-8 -*-
"""
采集卡死修复验证分析  (v2 —— 修正 J3 口径错误)

★ 口径修正记录（2026-10-03）：
  v1 用「村民末条指令帧 → 沉默时长」当卡死判据 —— **错误**。
  原因：引擎只在【换目标】时打印 "设置工作目标为 X"（或 HumanAction/Build/Move），
        村民持续采集同一处【不会】产生新行 ⇒ v1 把"稳定在采"误判成"沉默卡死"
        （实测 fix2 误报 13 人，而引擎状态行显示 Work:17 Idle:0 —— 全在干活）。
  正确判据：引擎状态行的 Idle/Walk/Work 计数（记忆铁律：引擎动作日志不受采样影响，最可靠）
  + 死亡记录（死后无指令 ≠ 卡死）。

判据：
  J1  [STUCK] 行是否带新字段（"在采N人" / "拉黑N帧+待重派"）
  J2  同一村民多次 [STUCK] 时目标 SN 是否变化（改前：严格等间隔复发且目标不变）
  J3  引擎状态行 Work/Idle/Walk 趋势（★主判据）+ 死亡名单
  J4  浆果丛派工序列（某丛是否"吃人"：派工后村民从此无新指令且非死亡/非在采）
  J5  [STUCK] 触发后该村民是否恢复工作
用法： python _fix_verify.py fix1.ait [fix2.ait ...]
"""
import re, io, sys, collections

def rows(path):
    out = []
    for ln in io.open(path, encoding='utf-8', errors='replace'):
        p = ln.split(' | ', 3)
        if len(p) < 4:
            continue
        try:
            fr = int(p[1])
        except ValueError:
            continue
        out.append((fr, p[3].strip()))
    return out

RE_ASSIGN = re.compile(r'村民 (\d+) 设置工作目标为 (.+?) (\d+)')
RE_BORN   = re.compile(r'产生了新的村民\(编号:(\d+)\)')
RE_DEAD   = re.compile(r'村民\(编号(\d+)\)死亡')
RE_DONE   = re.compile(r'(.+?)\(编号:(\d+)\)采集完成')
RE_ORD    = re.compile(r'(?:HumanAction|HumanBuild|HumanMove):村民 (\d+)')
RE_STAT   = re.compile(r'阶段?\]\s*(\w+) \| Fd:(\d+).*?Frm:(\d+) Idle:(\d+)\(Carry:(\d+)\) Walk:(\d+) Work:(\d+) Atk:(\d+) \| Mil:(\d+) E:(\d+)')

def analyze(path):
    R = rows(path)
    if not R:
        print(f"!! {path}: 空/不可解析"); return
    raw = io.open(path, encoding='utf-8', errors='replace').read()
    last = max(f for f, _ in R)
    print("=" * 80)
    print(f"### {path}   行数={len(R)}   末帧={last}  (约 {last/25/60:.1f} 分钟游戏时间)")
    print("=" * 80)

    # ---------- J1 ----------
    st = [(f, m) for f, m in R if 'STUCK' in m]
    print(f"\n[J1] [STUCK] 触发 {len(st)} 次   → 新字段: {'✅ 有' if any('待重派' in m for _,m in st) else '❌ 无'}")
    for f, m in st:
        print(f"   {m[m.find('[STUCK'):] if '[STUCK' in m else m}")

    # ---------- J2 ----------
    byv = collections.OrderedDict()
    for f, m in st:
        v = re.search(r'村民SN=(\d+)', m); t = re.search(r'目标SN=(-?\d+)', m)
        if v: byv.setdefault(v.group(1), []).append((f, t.group(1) if t else '?'))
    print(f"\n[J2] 同村民多次触发的目标变化")
    if not byv:
        print("   (无触发)")
    for v, lst in byv.items():
        tgs = [t for _, t in lst]; fs = [f for f, _ in lst]
        ok = len(set(tgs)) == len(tgs)
        gap = [fs[i+1]-fs[i] for i in range(len(fs)-1)]
        print(f"   村民{v}: {len(lst)}次 目标={tgs} 间隔={gap}  {'✅ 每次不同' if ok and len(tgs)>1 else ('单次' if len(tgs)==1 else '⚠ 重复')}")

    # ---------- J3 ★主判据 ----------
    dead = RE_DEAD.findall(raw)
    born = [s for s, _ in [(m, 0) for m in re.findall(r'产生了新的村民\(编号:(\d+)\)', raw)]]
    stl = [(f, m) for f, m in R if 'Idle:' in m]
    print(f"\n[J3] ★活动度（引擎状态行 —— 不受日志采样影响）")
    print(f"   出生村民 {len(born)} 人   死亡 {len(dead)} 人 {dead if dead else ''}")
    if stl:
        print(f"   状态行 {len(stl)} 条  首 f={stl[0][0]}  末 f={stl[-1][0]}")
        for f, m in stl[:1] + stl[-4:]:
            g = re.search(r'\] (\w+) \| Fd:(\S+) .*?Frm:(\d+) Idle:(\d+)\(Carry:(\d+)\) Walk:(\d+) Work:(\d+) Atk:(\d+) \| Mil:(\d+) E:(\d+)', m)
            if g:
                print(f"     f={f:<6} 阶段={g.group(1):<4} Idle:{g.group(4):<3} Carry:{g.group(5):<3} Walk:{g.group(6):<3} Work:{g.group(7):<3} Atk:{g.group(8):<3} | Mil:{g.group(9):<3} E:{g.group(10)}")
        # 趋势判定：末 1/4 段是否仍有人在工作
        tailfr = stl[-1][0]
        tail = [(f, m) for f, m in stl if f > tailfr * 0.6]
        idle_hi = sum(1 for f, m in tail if (re.search(r'Idle:(\d+)', m) and int(re.search(r'Idle:(\d+)', m).group(1)) > 3))
        work_ok = sum(1 for f, m in tail if (re.search(r'Work:(\d+)', m) and int(re.search(r'Work:(\d+)', m).group(1)) >= 5))
        print(f"   → 末段({len(tail)} 条) 中 Work≥5 的有 {work_ok} 条, Idle>3 的有 {idle_hi} 条")
        print(f"   → 判定: {'✅ 全员在岗（无卡死）' if work_ok == len(tail) and idle_hi == 0 else '⚠ 需人工查看'}")
    else:
        print("   (无状态行 —— 该局日志不含状态输出)")

    # ---------- J4 ----------
    seq = collections.OrderedDict(); done = {}
    for f, m in R:
        mm = RE_ASSIGN.search(m)
        if mm:
            if '浆果' in mm.group(2) or 'BUSH' in mm.group(2).upper():
                seq.setdefault(mm.group(3), []).append((f, mm.group(1)))
            continue
        mm = RE_DONE.search(m)
        if mm: done[mm.group(2)] = f
    print(f"\n[J4] 浆果丛派工序列")
    for t, lst in sorted(seq.items()):
        runs = []; cur = None
        for f, v in lst:
            if v != cur: runs.append(v); cur = v
        tag = f"✅采完 f={done[t]}" if t in done else "❌日志内未采完"
        print(f"   丛 {t}: {tag}  不同村民={len(runs)} → {runs}")

    # ---------- J5 ----------
    print(f"\n[J5] [STUCK] 触发后是否恢复工作")
    for v, lst in byv.items():
        trig = lst[-1][0]
        after = [f for f, m in R if f > trig and v in m and ('设置工作目标' in m or 'HumanBuild' in m or 'HumanMove' in m)]
        print(f"   村民{v} 末次触发 f={trig} → 之后的指令 {len(after)} 条 {after[:5]}{' ...' if len(after)>5 else ''}  {'✅ 恢复' if after else '❌ 无后续'}")

    # ---------- 胜负 ----------
    jl = path.rsplit('.', 1)[0] + '.jsonl'
    try:
        txt = io.open(jl, encoding='utf-8', errors='replace').read()
        print(f"\n[胜负] win:true {'✅ 胜' if '\"win\":true' in txt.replace(' ','') else ('❌ 负/未决' if 'DEFEAT:' in raw else '❌ 未决')}   (jsonl {len(txt.splitlines())} 行)")
    except IOError:
        print(f"\n[胜负] 无 {jl}")
    print()

for p in sys.argv[1:]:
    analyze(p)
