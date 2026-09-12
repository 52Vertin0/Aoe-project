# -*- coding: utf-8 -*-
"""
fa 批验收：反攻 27 分钟后「派所有农民进攻敌方基地」（COUNTER_FARMER_ATTACK）。

回答四个问题：
  ① 触发覆盖 —— 有多少局的帧数真的走到了 40500（27 分）之后？（没走到的局本功能等于不存在）
  ② 是否真的下发 —— [FARMER-ATK] 日志首帧 / 已投入农民数；村民 SN 是否出现在 `设置攻击目标为`
  ③ 打的是什么 —— 目标名分布（市镇中心 / 箭塔 / 其他）；tgtSN 是否 = 敌方 TC
  ④ 代价 —— 村民阵亡数、祭司阵亡、胜负，与 kd 批（同批 24 局、无此功能）对比

口径（铁律 41/25）：
  • ait 行 = time | frame | color | flag | message；split(" | ", 3) 后 frame=p[1]，flag=p[3] 头部
  • 我方村民日志名 = 「村民」（SN 4xxxx 段）；敌方 TC 日志名同为「市镇中心」，靠 SN 区分
  • 胜负只在 DebugText 里认带冒号的精确串（ResultLogFile.win 恒 false）
  • 跨批比较一律夹同一时间窗，避免早崩局数不等伪造差异
"""
import re, glob, os, statistics, collections

FRAME_27 = 40500          # 27 分钟 × 1500
RE_DEAD = re.compile(r"([\u4e00-\u9fa5A-Za-z.]+)\(编号:?(\d+)\)\s*(?:死亡|阵亡)")
RE_FATK = re.compile(r"\[FARMER-ATK f=(\d+)\]\s*农民=(\d+)\s*已投入=(\d+)\s*本帧下发=(\d+)"
                     r"\s*tgtSN=(-?\d+)(?:\s+kind=(\d+))?(?:\s+敌建筑=(\d+))?")
RE_VIL_ATK = re.compile(r"HumanAction:村民 (\d+) 设置攻击目标为 ([\u4e00-\u9fa5A-Za-z]+) (\d+)")
RE_WIN = re.compile(r"VICTORY! Siege Workshop converted")
RE_DEF = re.compile(r"DEFEAT: (Priest killed|Town Center destroyed)")


def load(prefix):
    fs = sorted(glob.glob(prefix + "[0-9]*.jsonl"),
                key=lambda f: int(re.search(r"(\d+)", os.path.basename(f)).group(1)))
    games = []
    for f in fs:
        ait = f[:-6] + ".ait"
        if not os.path.exists(ait):
            continue
        g = dict(idx=int(re.search(r"(\d+)", os.path.basename(f)).group(1)),
                 maxf=0, win=0, lose=0, end="none",
                 fatk_n=0, fatk_first=None, fatk_max_engaged=0, fatk_tgt=set(), fatk_frames=[],
                 fatk_kind=collections.Counter(), fatk_nbuild_min=None, fatk_nbuild_max=0, fatk_sent=0,
                 vil_atk=0, vil_atk_tgt=collections.Counter(), vil_atk_first=None,
                 vil_dead=0, vil_dead_after27=0, priest_dead=None, my_dead=0)
        for line in open(ait, encoding="utf-8", errors="replace"):
            p = line.split(" | ", 3)
            if len(p) < 4:
                continue
            try:
                fr = int(p[1])
            except ValueError:
                continue
            if fr > g["maxf"]:
                g["maxf"] = fr
            flag = p[3].split("|", 1)[0].strip()
            body = p[3].split("|", 1)[1] if "|" in p[3] else ""

            if RE_WIN.search(body):
                g["win"] += 1; g["end"] = "win"
            m = RE_DEF.search(body)
            if m:
                g["lose"] += 1; g["end"] = "defeat:" + m.group(1)

            m = RE_FATK.search(body)
            if m:
                g["fatk_n"] += 1
                f0 = int(m.group(1))
                if g["fatk_first"] is None or f0 < g["fatk_first"]:
                    g["fatk_first"] = f0
                g["fatk_max_engaged"] = max(g["fatk_max_engaged"], int(m.group(3)))
                g["fatk_tgt"].add(int(m.group(5)))
                g["fatk_frames"].append(f0)
                g["fatk_sent"] += int(m.group(4))
                if m.group(6) is not None:
                    g["fatk_kind"][int(m.group(6))] += 1
                if m.group(7) is not None:
                    nb = int(m.group(7))
                    g["fatk_nbuild_max"] = max(g["fatk_nbuild_max"], nb)
                    g["fatk_nbuild_min"] = nb if g["fatk_nbuild_min"] is None else min(g["fatk_nbuild_min"], nb)

            m = RE_VIL_ATK.search(body)
            if m:
                g["vil_atk"] += 1
                g["vil_atk_tgt"][m.group(2)] += 1
                if g["vil_atk_first"] is None:
                    g["vil_atk_first"] = fr

            if flag == "0":
                m = RE_DEAD.search(body)
                if m:
                    nm = m.group(1)
                    g["my_dead"] += 1
                    if "村民" in nm:
                        g["vil_dead"] += 1
                        if fr > FRAME_27:
                            g["vil_dead_after27"] += 1
                    if "祭司" in nm and g["priest_dead"] is None:
                        g["priest_dead"] = fr
        games.append(g)
    return games


def report(prefix, label):
    gs = load(prefix)
    n = len(gs)
    if not n:
        print("【%s %s】无日志" % (prefix, label)); return None
    reached = [g for g in gs if g["maxf"] >= FRAME_27]
    trig = [g for g in gs if g["fatk_n"] > 0]
    print("=" * 104)
    print("【%s %s】%d 局" % (prefix, label, n))
    print("  走到 27 分(>=%d 帧)的局：%d/%d ｜ 末帧中位 %.1f 分 ｜ 最短 %d 帧" %
          (FRAME_27, len(reached), n, statistics.median([g["maxf"] for g in gs]) / 1500.0,
           min(g["maxf"] for g in gs)))
    print("  结局：胜 %d ｜ 负 %d ｜ 无结局 %d" %
          (sum(1 for g in gs if g["end"] == "win"),
           sum(1 for g in gs if g["end"].startswith("defeat")),
           sum(1 for g in gs if g["end"] == "none")))
    print("  村民阵亡：总计 %d ｜ 其中 >27 分后 %d ｜ 局均 %.1f" %
          (sum(g["vil_dead"] for g in gs), sum(g["vil_dead_after27"] for g in gs),
           statistics.mean([g["vil_dead"] for g in gs])))
    print("  我方总阵亡：局均 %.1f（中位 %.1f）｜ 祭司阵亡局 %d/%d" %
          (statistics.mean([g["my_dead"] for g in gs]), statistics.median([g["my_dead"] for g in gs]),
           sum(1 for g in gs if g["priest_dead"] is not None), n))
    print("  村民攻击令(vil_atk)：总计 %d ｜ 有令的局 %d/%d" %
          (sum(g["vil_atk"] for g in gs), sum(1 for g in gs if g["vil_atk"] > 0), n))

    if trig:
        print("  --- [FARMER-ATK] 日志 ---")
        print("  触发局 %d/%d ｜ 首帧：中位 %s ｜ 最早 %s" %
              (len(trig), n,
               ("%.1f 分" % (statistics.median([g["fatk_first"] for g in trig]) / 1500.0)),
               ("%.1f 分" % (min(g["fatk_first"] for g in trig) / 1500.0))))
        print("  峰值「已投入」农民数：中位 %d ｜ 最大 %d" %
              (statistics.median([g["fatk_max_engaged"] for g in trig]),
               max(g["fatk_max_engaged"] for g in trig)))
        tgts = collections.Counter()
        for g in trig:
            for t in g["fatk_tgt"]:
                tgts[t] += 1
        print("  tgtSN 分布（局数）：%s" % dict(tgts))
        kinds = collections.Counter()
        for g in trig:
            for k, v in g["fatk_kind"].items():
                kinds[k] += v
        if kinds:
            KN = {0: "无目标", 1: "敌方TC", 2: "软目标建筑", 3: "箭塔", 4: "行军到记忆方位"}
            print("  目标档位 kind 计数：%s" % {KN.get(k, k): v for k, v in sorted(kinds.items())})
            nz = sum(v for k, v in kinds.items() if k != 0)
            print("  有效目标率 = %d/%d = %.1f%%" % (nz, sum(kinds.values()), 100.0 * nz / sum(kinds.values())))
        nb = [g["fatk_nbuild_max"] for g in trig if g["fatk_nbuild_max"]]
        if nb:
            print("  可见敌建筑数：中位 %d ｜ 最大 %d（<=3 说明视野里基本只剩箭塔/武器厂）" %
                  (statistics.median(nb), max(nb)))
        print("  本帧下发累计（去掉节流重复后仍是每农民 1 条）：%d" %
              sum(g["fatk_sent"] for g in trig))
    else:
        print("  --- [FARMER-ATK] 无任何日志（功能未落地 / 无局走到 27 分）---")

    tname = collections.Counter()
    for g in gs:
        for k, v in g["vil_atk_tgt"].items():
            tname[k] += v
    if tname:
        print("  村民攻击【目标名】分布：%s" % dict(tname.most_common(8)))

    if trig:
        print("  --- 触发局明细 (idx/末帧分/结局/农民峰值/村民攻令/村民亡) ---")
        for g in sorted(trig, key=lambda x: x["idx"]):
            kd_ = collections.Counter(g["fatk_kind"])
            print("    %s%-3d %5.1f分 %-22s peak=%2d vilAtk=%4d vilDead=%2d nBld=%d kind=%s tgt=%s" %
                  (prefix, g["idx"], g["maxf"] / 1500.0, g["end"], g["fatk_max_engaged"],
                   g["vil_atk"], g["vil_dead"], g["fatk_nbuild_max"],
                   dict(sorted(kd_.items())), sorted(g["fatk_tgt"])))
    return gs


if __name__ == "__main__":
    report("kd", "对照A·无农民总攻（旧代码）")
    report("fa", "对照B·农民总攻首版（目标选取有 bug）")
    report("fb", "★ 农民总攻修正版（三级目标 + 兜底行军）")
