# -*- coding: utf-8 -*-
"""
kd 批（M1~M5 拉扯撤退锁）验收脚本。
一次遍历给出四批（gi 基线 / kb M1~M3 / kc M1~M4 / kd M1~M5）的：
  A. 结果与安全指标：局数、末帧中位、胜负(带冒号判定)、感化起手、攻击令/移动令总数
     ⇒ 防"M5 让弓兵不打人"（锁死输出）这一副作用。
  B. 机制指标（控制变量）：按【窗口 dK 分桶】比较撤退窗口位移
     ⇒ dK 中位会受 M1 阈值(11格)影响，是阈值效应；位移才是行为量。

铁律 25/36：胜负 8 局/批不可判；起手是引擎动作日志（不受采样影响）→ 可信排序依据。
"""
import re, glob, os, statistics, collections, sys

RE_KIT = re.compile(
    r"\[KIT-R f=(\d+)\] SN=(\d+) dK=([\d.]+) R=([\d.]+) stage=(\d+) stuck=(\d+) aged=(\d+) self=\(([\d.-]+),([\d.-]+)\) tgt=\(([\d.-]+),([\d.-]+)\)")
RE_MOVE = re.compile(r"HumanMove:[\u4e00-\u9fa5A-Za-z.]+ (\d+) 移动至 \(([\d.]+),([\d.]+)\)")
RE_ATK = re.compile(r"HumanAction:[\u4e00-\u9fa5A-Za-z.]+ (\d+) 设置攻击目标为 ")
RE_WIN = re.compile(r"VICTORY! Siege Workshop converted")
RE_LOSE_P = re.compile(r"DEFEAT: Priest killed")
RE_LOSE_T = re.compile(r"DEFEAT: Town Center destroyed")
RE_START = re.compile(r"设置转换目标为 攻城武器厂")

BATCHES = [
    ("gi", "基线"), ("kb", "M1~M3"), ("kc", "M1~M4"), ("kd", "M1~M5"),
]
DK_BUCKETS = [(0, 6.5), (6.5, 8.5), (8.5, 11.0), (11.0, 999)]


def bucket_of(dk):
    for i, (lo, hi) in enumerate(DK_BUCKETS):
        if lo <= dk < hi:
            return i
    return len(DK_BUCKETS) - 1


def files_of(prefix):
    fs = sorted(glob.glob(prefix + "*.jsonl"),
                key=lambda f: int(re.search(r"(\d+)", os.path.basename(f)).group(1)))
    return fs


def analyze(prefix, label):
    fs = files_of(prefix)
    n = len(fs)
    if n == 0:
        return None
    wins = losses = timeouts = 0
    start_games = 0
    conv_games = 0
    last_frames = []
    atk_tot = mv_tot = kit_tot = 0
    # 控制变量：按 dK 桶的窗口位移
    step_by_bucket = collections.defaultdict(list)
    stage_cnt = collections.Counter()

    for f in fs:
        # ait 与 jsonl 同名不同后缀
        ait = f[:-6] + ".ait"
        win = lose = False
        st = False
        last_fr = 0
        seq = collections.defaultdict(list)   # sn -> [(frame, dK, stage, selfx, selfy)]
        if os.path.exists(ait):
            for line in open(ait, encoding="utf-8", errors="replace"):
                p = line.split(" | ", 3)
                if len(p) < 4:
                    continue
                body = p[3]
                try:
                    fr = int(p[1])
                except ValueError:
                    continue
                if fr > last_fr:
                    last_fr = fr
                if "HumanMove:" in body:
                    mv_tot += 1
                if "HumanAction:" in body:
                    atk_tot += 1
                if RE_START.search(body):
                    st = True
                if RE_WIN.search(body):
                    win = True
                if RE_LOSE_P.search(body) or RE_LOSE_T.search(body):
                    lose = True
                m = RE_KIT.search(body)
                if m:
                    kit_tot += 1
                    sn = int(m.group(2))
                    seq[sn].append((int(m.group(1)), float(m.group(3)),
                                    int(m.group(5)), float(m.group(8)), float(m.group(9))))
        # jsonl 兜底取末帧
        if last_fr == 0 and os.path.exists(f):
            for line in open(f, encoding="utf-8", errors="replace"):
                for mm in re.finditer(r'"frame"\s*:\s*(\d+)', line):
                    v = int(mm.group(1))
                    if v > last_fr:
                        last_fr = v
        last_frames.append(last_fr * (1.0 / 1500.0))   # 分钟
        if win:
            wins += 1
        elif lose:
            losses += 1
        else:
            timeouts += 1
        if st:
            start_games += 1
            if win:
                conv_games += 1
        # 窗口位移（间隔 25~45 帧）
        for sn, ev in seq.items():
            ev.sort()
            for i in range(1, len(ev)):
                gap = ev[i][0] - ev[i - 1][0]
                if not (25 <= gap <= 45):
                    continue
                d = ((ev[i][3] - ev[i - 1][3]) ** 2 + (ev[i][4] - ev[i - 1][4]) ** 2) ** 0.5
                if d > 12.0:      # 明显换点/传送伪影，剔除
                    continue
                step_by_bucket[bucket_of(ev[i - 1][1])].append(d)
                stage_cnt[ev[i - 1][2]] += 1

    print("=" * 100)
    print("【%s %s】局数 %d ｜ 末帧中位 %.1f 分（满时长>=29.3分 %d 局）" %
          (prefix, label, n, statistics.median(last_frames),
           sum(1 for x in last_frames if x >= 29.3)))
    print("  结果：胜 %d ｜ 负 %d ｜ 无结局 %d   → 胜率 %.0f%%" %
          (wins, losses, timeouts, 100.0 * wins / n))
    print("  感化起手：%d/%d 局   → 起手局胜率 %.0f%%" %
          (start_games, n, 100.0 * conv_games / start_games if start_games else 0))
    print("  指令量：攻击令 %d ｜ 移动令 %d ｜ KIT-R 窗口 %d   （每局：攻击 %.1f 移动 %.1f 窗口 %.1f）" %
          (atk_tot, mv_tot, kit_tot, atk_tot / n, mv_tot / n, kit_tot / n))
    tot = sum(len(v) for v in step_by_bucket.values())
    if tot:
        names = ["dK<6.5", "6.5~8.5", "8.5~11", ">=11"]
        print("  撤退窗口位移（按窗口 dK 分桶，控制阈值效应）：")
        for i, nm in enumerate(names):
            v = step_by_bucket.get(i, [])
            if not v:
                continue
            print("    %-9s n=%6d ｜ 位移中位 %.2f 格 ｜ >1格 %5.1f%% ｜ <0.2格 %5.1f%%" %
                  (nm, len(v), statistics.median(v),
                   100.0 * sum(1 for x in v if x > 1.0) / len(v),
                   100.0 * sum(1 for x in v if x < 0.2) / len(v)))
    return dict(n=n, win=wins, lose=losses, to=timeouts, start=start_games,
                atk=atk_tot, mv=mv_tot, kit=kit_tot,
                step_bucket={k: list(v) for k, v in step_by_bucket.items()})


if __name__ == "__main__":
    res = {}
    for p, l in BATCHES:
        r = analyze(p, l)
        if r:
            res[p] = r
    # 汇总表
    print()
    print("=" * 100)
    print("汇总（★ = 机制量，不受采样影响 ⇒ 可信排序依据）")
    print("=" * 100)
    hdr = "%-5s %4s %4s %5s %7s %9s %10s %10s %10s"
    print(hdr % ("批", "胜", "负", "无结局", "起手局", "攻击令/局", "移动令/局", "窗口/局", "末帧中位"))
    for p, l in BATCHES:
        r = res.get(p)
        if not r:
            continue
        print(hdr % (p, r["win"], r["lose"], r["to"], r["start"],
                     "%.1f" % (r["atk"] / r["n"]), "%.0f" % (r["mv"] / r["n"]),
                     "%.0f" % (r["kit"] / r["n"]), ""))
    print("=" * 100)
