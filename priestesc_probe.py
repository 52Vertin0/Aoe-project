# -*- coding: utf-8 -*-
"""
祭司反攻期被战车弓兵锁定 —— 预警链分析
口径：PESC 行 hp / mode / nearE / threat / nRSort / nRD / threatR
      nRSort: 12=战车弓兵(AT_CHARIOT_ARCHER) 13=? 14=?
"""
import re, sys, os

PAT = re.compile(
    r"\[PESC f=(\d+)\]\s+hp=([\d.]+)\s+mode=(\d+)\s+nearE=([\d.]+)\s+"
    r"threat=([\d.eE+-]+)\s+nRSort=(-?\d+)\s+nRD=([\d.]+)\s+threatR=([\d.]+)"
)

def series(path):
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = PAT.search(line)
            if m:
                out.append(dict(
                    f=int(m.group(1)), hp=float(m.group(2)), mode=int(m.group(3)),
                    nearE=float(m.group(4)), threat=float(m.group(5)),
                    nRSort=int(m.group(6)), nRD=float(m.group(7)), threatR=float(m.group(8)),
                    raw=line.strip(),
                ))
    return out

# 哨兵值：无威胁时引擎给的超大体
SENT = 1e10
FLEE_HP = 0.6

def analyze(path):
    s = series(path)
    if not s:
        return None
    name = os.path.basename(path)
    r = dict(name=name, n=len(s),
             f0=s[0]["f"], f1=s[-1]["f"],
             hp0=s[0]["hp"], hpEnd=s[-1]["hp"], hpMin=min(x["hp"] for x in s))
    # 起手：第一次 hp < 1.0 的采样（= 开始挨打）
    first_blood = next((x for x in s if x["hp"] < 0.995), None)
    r["fb"] = first_blood
    # 第一次 mode=1（开始逃）
    first_flee = next((x for x in s if x["mode"] == 1), None)
    r["ff"] = first_flee
    # 死亡前最后一条
    r["last"] = s[-1]
    # 掉血量
    if first_blood:
        r["fb_hp"] = first_blood["hp"]
        r["delay_frames"] = (first_flee["f"] - first_blood["f"]) if first_flee else None
        r["delay_hp"] = (first_blood["hp"] - first_flee["hp"]) if first_flee else None
    else:
        r["fb_hp"] = None; r["delay_frames"] = None; r["delay_hp"] = None
    # 威胁判定窗口统计：hp 低于阈值但 mode 仍=0 的采样数
    r["sub06_no_flee"] = sum(1 for x in s if x["hp"] <= FLEE_HP and x["mode"] == 0)
    r["sub06_total"] = sum(1 for x in s if x["hp"] <= FLEE_HP)
    # nRSort 分布
    from collections import Counter
    r["sortcnt"] = Counter(x["nRSort"] for x in s)
    # 有威胁 / 无威胁(threat 哨兵) 的采样数
    r["thr_present"] = sum(1 for x in s if x["threat"] < SENT)
    r["thr_absent"] = sum(1 for x in s if x["threat"] >= SENT)
    # nearE 分布
    ne = sorted(x["nearE"] for x in s if x["nearE"] < SENT)
    r["nearE_med"] = ne[len(ne)//2] if ne else None
    r["nearE_min"] = ne[0] if ne else None
    # nRD 分布（威胁距离）
    nd = sorted(x["nRD"] for x in s if x["nRD"] < SENT)
    r["nRD_med"] = nd[len(nd)//2] if nd else None
    r["nRD_min"] = nd[0] if nd else None
    # nRD <= 7（战车弓兵真实射程内）的采样比例
    r["nd_le7"] = sum(1 for x in s if x["nRD"] <= 7.0)
    return r

files = sys.argv[1:] or [f"pe{i}.ait" for i in range(1, 9)]
print("=" * 100)
print("祭司反攻期 PESC 汇总（掉血→逃跑 预警链）")
print("=" * 100)
for p in files:
    if not os.path.exists(p):
        print(f"{p}: 不存在，跳过")
        continue
    r = analyze(p)
    if not r:
        print(f"{p}: 无 PESC 样本")
        continue
    print(f"\n### {r['name']}  样本={r['n']}  帧 {r['f0']}~{r['f1']}")
    print(f"  hp: 起 {r['hp0']:.2f} → 末 {r['hpEnd']:.2f}  最低 {r['hpMin']:.2f}")
    if r["fb"]:
        print(f"  首次挨打: f={r['fb']['f']} hp={r['fb']['hp']:.2f} "
              f"nearE={r['fb']['nearE']:.1f} nRSort={r['fb']['nRSort']} nRD={r['fb']['nRD']:.1f}")
    else:
        print("  首次挨打: 无（全程满血）")
    if r["ff"]:
        print(f"  首次逃跑: f={r['ff']['f']} hp={r['ff']['hp']:.2f} "
              f"nearE={r['ff']['nearE']:.1f} nRSort={r['ff']['nRSort']}")
        if r["fb"]:
            print(f"  ★ 预警延迟: {r['delay_frames']} 帧 ({(r['delay_frames'] or 0)/25.0:.1f}s)  "
                  f"期间又掉血 {100*(r['delay_hp'] or 0):.1f}%")
    else:
        print("  首次逃跑: 从未逃跑 (mode 恒 0)")
        if r["fb"]:
            print(f"  ★ 预警延迟: ∞  —— 从 hp={r['fb']['hp']:.2f} 一路被打到 {r['hpMin']:.2f}")
    print(f"  hp<=0.6 的采样 {r['sub06_total']} 条，其中 mode=0 仍不逃 {r['sub06_no_flee']} 条")
    print(f"  nRSort 分布: {dict(r['sortcnt'])}")
    print(f"  有威胁采样 {r['thr_present']} / 哨兵(无威胁) {r['thr_absent']}")
    print(f"  nearE 中位 {r['nearE_med']} 最小 {r['nearE_min']}")
    print(f"  nRD  中位 {r['nRD_med']} 最小 {r['nRD_min']}   nRD<=7 采样 {r['nd_le7']}")
    print(f"  末条: {r['last']['raw'][-120:]}")

print("\n" + "=" * 100)
