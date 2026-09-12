# -*- coding: utf-8 -*-
"""
kd 批副作用审查：M5 拉扯撤退锁是否带来「负局增加 / 末帧提前」的代价。

kd 验收已达成位移指标（撤退窗口位移 0.00 → 1.5 格），但结果指标反向：
  负局 9 → 12 ｜ 末帧中位 30.0 → 27.8 分 ｜ 满时长局 14 → 11
本脚本回答「反向是 M5 副作用还是波动」：

口径（铁律：跨批比较必须钳住时间窗）：
  • 我方阵亡：ait 行 `X(编号N)死亡`，flag(p[3] 首个 token) == 0
  • 统一时间窗 frame <= 39000（避开末帧差异造成的时长偏差）
  • 祭司（日志名「祭司」）首次死亡帧；祭司死亡是我方主败因
  • 分类型阵亡（复合弓兵 / 祭司 / 战车弓兵 / 近战 / 村民）—— 看 M5 是否让弓兵少死
"""
import re, glob, os, statistics, collections

RE_DEAD = re.compile(r"([\u4e00-\u9fa5A-Za-z.]+)\(编号:?(\d+)\)\s*(?:死亡|阵亡)")
WINDOW = 39000
BATCHES = [("gi", "基线"), ("kb", "M1~M3"), ("kc", "M1~M4"), ("kd", "M1~M5")]
GROUPS = [("复合弓兵", ("复合弓兵",)), ("祭司", ("祭司",)),
          ("战车弓兵", ("战车弓兵",)), ("近战", ("步兵", "骑兵", "武士", "棍棒", "矛兵", "剑士")),
          ("村民", ("村民",))]


def grp_of(name):
    for g, keys in GROUPS:
        for k in keys:
            if k in name:
                return g
    return "其他"


def analyze(prefix, label):
    fs = sorted(glob.glob(prefix + "*.jsonl"),
                key=lambda f: int(re.search(r"(\d+)", os.path.basename(f)).group(1)))
    n = len(fs)
    if not n:
        return
    cas_all = collections.Counter()
    cas_win = collections.Counter()     # 前 39000 帧
    priest_death = []
    priest_death_win = []
    mydead_per_game = []
    mydead_win_per_game = []
    for f in fs:
        ait = f[:-6] + ".ait"
        if not os.path.exists(ait):
            continue
        cnt = collections.Counter()
        cntw = collections.Counter()
        pd = None
        pdw = None
        for line in open(ait, encoding="utf-8", errors="replace"):
            p = line.split(" | ", 3)
            if len(p) < 4:
                continue
            try:
                fr = int(p[1])
            except ValueError:
                continue
            fl = p[3].split("|", 1)[0].strip()
            if fl not in ("0",):
                continue
            m = RE_DEAD.search(p[3])
            if not m:
                continue
            nm = m.group(1)
            g = grp_of(nm)
            cnt[g] += 1
            if fr <= WINDOW:
                cntw[g] += 1
            if g == "祭司":
                if pd is None:
                    pd = fr
                if pdw is None and fr <= WINDOW:
                    pdw = fr
        cas_all.update(cnt)
        cas_win.update(cntw)
        mydead_per_game.append(sum(cnt.values()))
        mydead_win_per_game.append(sum(cntw.values()))
        if pd is not None:
            priest_death.append(pd)
        if pdw is not None:
            priest_death_win.append(pdw)

    print("=" * 100)
    print("【%s %s】%d 局" % (prefix, label, n))
    print("  我方阵亡/局：全程 中位 %.1f ｜ 前 39000 帧 中位 %.1f" %
          (statistics.median(mydead_per_game), statistics.median(mydead_win_per_game)))
    print("  祭司阵亡局数：全程 %d/%d ｜ 前 39000 帧 %d/%d" %
          (len(priest_death), n, len(priest_death_win), n))
    if priest_death:
        print("  祭司首次阵亡帧：中位 %d（%.1f 分）｜ 最早 %d" %
              (statistics.median(priest_death), statistics.median(priest_death) / 1500.0,
               min(priest_death)))
    print("  分类型阵亡（前39000帧，总次数）：" +
          " ｜ ".join("%s %d" % (g, cas_win[g]) for g, _ in GROUPS))
    print("  分类型阵亡（全程）：" +
          " ｜ ".join("%s %d" % (g, cas_all[g]) for g, _ in GROUPS))


if __name__ == "__main__":
    for p, l in BATCHES:
        analyze(p, l)
