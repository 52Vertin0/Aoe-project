# -*- coding: utf-8 -*-
"""
kb 批（kiting 修正）vs gi 批（基线）机制量对比。
一次只改一组变量 ⇒ 用同一套口径量两批，看差异方向。

口径（与 kit_override_probe.py / kit_step_probe.py 逐字一致）：
  KIT-R 窗口 → 其后 90 帧内的 HumanMove 落点
  same_mv   后续首条移动令落点 ≈ 撤退落点(<3格)
  over_mv   后续首条移动令落点 明显不同(>3格)   ← 被别的指令覆盖
  after_over 撤退令之后【又冒出】不同落点        ← 撤退刚发完就被顶掉
  over_atk  后续 60 帧内出现攻击令              ← 引擎自行逼近
  空转      相邻 KIT-R 间隔>=25 帧时 self 位移 < 0.5 格
  dK 走向   同 SN 相邻窗口 dK 变大/变小
  M3 生效   撤退后 120 帧内是否仍有"朝敌推进"落点
"""
import re, glob, collections, statistics, sys

RE_KIT = re.compile(
    r"\[KIT-R f=(\d+)\] SN=(\d+) dK=([\d.]+) R=([\d.]+) stage=(\d+) stuck=(\d+) aged=(\d+) self=\(([\d.-]+),([\d.-]+)\) tgt=\(([\d.-]+),([\d.-]+)\)")
RE_MOVE = re.compile(r"HumanMove:[\u4e00-\u9fa5A-Za-z.]+ (\d+) 移动至 \(([\d.]+),([\d.]+)\)")
RE_ATK = re.compile(r"HumanAction:[\u4e00-\u9fa5A-Za-z.]+ (\d+) 设置攻击目标为 ")
RE_WIN = re.compile(r"VICTORY! Siege Workshop converted")
RE_LOSE_P = re.compile(r"DEFEAT: Priest killed")
RE_LOSE_T = re.compile(r"DEFEAT: Town Center destroyed")
RE_START = re.compile(r"设置转换目标为 攻城武器厂")
BL = 35.777

# 敌方基地方向推测：kb/gi 图固定，塔/厂在右上。用落点是否"远离敌"来判断方向：
# 简化口径 —— 撤退落点方向 = self→tgt 的反向。若后续落点落在 self→敌 一侧，判为"朝敌"。


def load(prefix):
    return sorted(glob.glob(prefix + "*.ait"),
                  key=lambda f: int(re.search(r"(\d+)", f).group(1)))


def analyze(prefix, label):
    files = load(prefix)
    tot = dict(kit=0, no_follow=0, same_mv=0, over_mv=0, after_over=0, over_atk=0)
    cover_dist, step_dist, idle = [], [], [0, 0]
    dk_up = dk_dn = 0
    win = lose_p = lose_t = none = 0
    starts = 0
    frames, starts_games = [], 0
    n_games = len(files)

    for f in files:
        kit_ev, mv_ev, atk_ev = [], [], []
        fw = fp = ft = False
        st = 0
        last_fr = 0
        for line in open(f, encoding="utf-8", errors="replace"):
            p = line.split(" | ", 3)
            if len(p) < 4:
                continue
            try:
                fr = int(p[1])
            except ValueError:
                continue
            last_fr = max(last_fr, fr)
            body = p[3]
            if RE_WIN.search(body):
                fw = True
            if RE_LOSE_P.search(body):
                fp = True
            if RE_LOSE_T.search(body):
                ft = True
            if RE_START.search(body):
                st += 1
            m = RE_KIT.search(body)
            if m:
                g = m.groups()
                kit_ev.append((int(g[0]), int(g[1]), float(g[2]), float(g[7]), float(g[8]),
                               float(g[9]), float(g[10])))
                continue
            m = RE_MOVE.search(body)
            if m:
                mv_ev.append((fr, int(m.group(1)), float(m.group(2)) / BL, float(m.group(3)) / BL))
                continue
            m = RE_ATK.search(body)
            if m:
                atk_ev.append((fr, int(m.group(1))))

        frames.append(last_fr)
        starts += st
        if st > 0:
            starts_games += 1
        if fw:
            win += 1
        elif fp:
            lose_p += 1
        elif ft:
            lose_t += 1
        else:
            none += 1

        mv_idx = collections.defaultdict(list)
        for fr, sn, x, y in mv_ev:
            mv_idx[sn].append((fr, x, y))
        atk_idx = collections.defaultdict(list)
        for fr, sn in atk_ev:
            atk_idx[sn].append(fr)

        for fr, sn, dK, sx, sy, tx, ty in kit_ev:
            tot["kit"] += 1
            step_dist.append(((tx - sx) ** 2 + (ty - sy) ** 2) ** 0.5)
            follows = [m for m in mv_idx.get(sn, []) if 0 < m[0] - fr <= 90]
            if not follows:
                tot["no_follow"] += 1
            else:
                follows.sort()
                f0 = follows[0]
                d0 = ((f0[1] - tx) ** 2 + (f0[2] - ty) ** 2) ** 0.5
                cover_dist.append(d0)
                if d0 < 3.0:
                    tot["same_mv"] += 1
                else:
                    tot["over_mv"] += 1
                if [m for m in follows[1:] if ((m[1] - tx) ** 2 + (m[2] - ty) ** 2) ** 0.5 > 3.0]:
                    tot["after_over"] += 1
            if any(0 < a - fr <= 60 for a in atk_idx.get(sn, [])):
                tot["over_atk"] += 1

        # 空转 + dK 走向：同 SN 相邻 KIT-R 窗口
        per = collections.defaultdict(list)
        for fr, sn, dK, sx, sy, tx, ty in kit_ev:
            per[sn].append((fr, dK, sx, sy))
        for sn, evs in per.items():
            evs.sort()
            for i in range(1, len(evs)):
                f0, d0, x0, y0 = evs[i - 1]
                f1, d1, x1, y1 = evs[i]
                if f1 - f0 >= 25:
                    idle[1] += 1
                    if ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 < 0.5:
                        idle[0] += 1
                if d1 > d0 + 0.3:
                    dk_up += 1
                elif d1 < d0 - 0.3:
                    dk_dn += 1

    print("=" * 88)
    print("【%s】%d 局｜末帧中位 %d｜祭司起手 %d 次 / %d 局" %
          (label, n_games, statistics.median(frames), starts, starts_games))
    print("  结局: 胜 %d ｜ 祭司死 %d ｜ TC 被毁 %d ｜ 无结局 %d" % (win, lose_p, lose_t, none))
    k = tot["kit"]
    if k == 0:
        print("  (无 KIT-R 样本)")
        return
    print("  --- 撤退窗口 %d 个 ---" % k)
    print("  后续90帧【无】移动令        : %5d (%5.1f%%)" % (tot["no_follow"], 100.0 * tot["no_follow"] / k))
    print("  后续首令 = 同一撤退落点     : %5d (%5.1f%%)" % (tot["same_mv"], 100.0 * tot["same_mv"] / k))
    print("  后续首令 = 不同落点(被覆盖) : %5d (%5.1f%%)" % (tot["over_mv"], 100.0 * tot["over_mv"] / k))
    print("  ★撤退后又冒出不同落点(顶掉) : %5d (%5.1f%%)" % (tot["after_over"], 100.0 * tot["after_over"] / k))
    print("  ★后续60帧内出现攻击令       : %5d (%5.1f%%)" % (tot["over_atk"], 100.0 * tot["over_atk"] / k))
    print("  空转(>=25帧位移<0.5格)       : %5d (%5.1f%%)" % (idle[0], 100.0 * idle[0] / idle[1] if idle[1] else 0))
    print("  dK 走向: 拉大 %d ｜ 缩小 %d ｜ 拉开比 %.0f%%" %
          (dk_up, dk_dn, 100.0 * dk_up / (dk_up + dk_dn) if dk_up + dk_dn else 0))
    print("  撤退落点距【自身】: 中位 %.1f / 均值 %.1f 格" %
          (statistics.median(step_dist), statistics.mean(step_dist)))
    print("  覆盖落点距撤退落点: 中位 %.1f 格" % statistics.median(cover_dist))


if __name__ == "__main__":
    analyze("gi", "基线 gi 批（kiting 修正前）")
    analyze("kb", "修正 kb 批（M1+M2+M3）")
    analyze("kc", "修正 kc 批（M1~M4）")
    analyze("kd", "修正 kd 批（M1~M4 + M5 拉扯撤退锁）")
