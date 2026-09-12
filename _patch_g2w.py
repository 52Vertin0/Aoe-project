# -*- coding: utf-8 -*-
import io
p = r"C:\new-aoe3.0.7g\UsrAI.cpp"
s = io.open(p, encoding="utf-8").read()
def rep(old, new, n=1):
    global s
    c = s.count(old)
    assert c == n, "anchor count=%d (want %d): %r" % (c, n, old[:70])
    s = s.replace(old, new, n)

# 1) 金工目标比例 3/5 -> 2/5，并加硬上限（新增两个常量 + 一个上限）
rep("#define MIN_GOLD_WORKERS 1      // 至少1人挖金！复合弓兵/阔剑兵/方阵兵/投石车/后勤科技真扣黄金",
    "#define MIN_GOLD_WORKERS 1      // 至少1人挖金！复合弓兵/阔剑兵/方阵兵/投石车/后勤科技真扣黄金\n"
    "// \u2605\u2605\u2605 2026-10-09\u3010\u51cf\u91d1\u5de5\u2192\u8f6c\u6728\u6750\u3011\u2605\u2605\u2605 \u5b9e\u6d4b\uff1a\u7ec8\u5c40\u9ec4\u91d1\u4e2d\u4f4d 244\u3001\u53cd\u653b\u671f 60%\u91c7\u6837 goldRich=1\uff0c\n"
    "//   \u800c\u4ea7\u65b9\u9635\u5175(\u6210\u672c40\u91d1)\u65f6\u4f59\u989d\u4e2d\u4f4d 270 \u21d2 \u9ec4\u91d1\u51e0\u4e4e\u4ece\u4e0d\u6784\u6210\u7ea6\u675f\uff1b\u5bf9\u7167\u53cd\u653b\u671f\u6728\u6750\u4e2d\u4f4d 106\u300140%\u91c7\u6837<70\u3002\n"
    "//   \u6545\u628a\u91d1\u5de5\u76ee\u6807\u4ece \u98df\u7269\u00d73/5 \u964d\u5230 \u98df\u7269\u00d72/5\uff0c\u5e76\u52a0\u786c\u4e0a\u9650 4\uff08\u4fdd\u8089\u76fe\u4ea7\u7ebf 40\u91d1/\u4e2a \u4e0d\u65ad\u7cae\uff09\u3002\n"
    "#define GOLD_WORKER_PER_FOOD_NUM 2   // \u91d1\u5de5\u76ee\u6807 = \u98df\u7269\u5de5 \u00d7 NUM/DEN\n"
    "#define GOLD_WORKER_PER_FOOD_DEN 5\n"
    "#define GOLD_TARGET_MAX 4            // \u91d1\u5de5\u786c\u4e0a\u9650")

# 2) 停采上限 1000 -> 500（实测峰值中位仅 310；仍是峰值 1.6 倍，不会触发注释 418 行警告的"采一半就转走"）
rep("#define GOLD_CAP_STOP  1000  // 黄金≥1000 不再派金工（一场反攻约耗 800~900 黄金，故留 100 余量）",
    "#define GOLD_CAP_STOP  500   // \u26052026-10-09 \u51cf\u91d1\u5de5\uff1a1000\u2192500\uff08\u5b9e\u6d4b\u5168\u7a0b\u5cf0\u503c\u4e2d\u4f4d\u4ec5 310\uff0c500 \u4ecd\u662f 1.6 \u500d\uff09")

# 3) goldTarget 计算式
old_t = """    // 黄金目标人数：与食物工数按 FOOD_GOLD_DEN:FOOD_GOLD_NUM(5:3) 配比（复合弓40食+20金 / 方阵60食+40金 ⇒ 100:60）。
    // 黄金过剩(goldRich)时压到 MIN_GOLD_WORKERS，把人力让给食物与木头；铜器前为 0。
    int goldTarget = (!postBronze) ? 0
        : goldRich ? MIN_GOLD_WORKERS
        : std::max(MIN_GOLD_WORKERS,
                   (int)((double)foodWorkers * FOOD_GOLD_DEN / FOOD_GOLD_NUM + 0.999));"""
new_t = """    // 黄金目标人数：★2026-10-09【减金工→转木材】★ 从 食物×3/5 降到 食物×2/5，且 ≤ GOLD_TARGET_MAX(4)。
    //   依据：产方阵兵(40金)时黄金余额中位 270（=6.8倍成本）、反攻期 60% 采样 goldRich=1
    //   ⇒ 黄金冗余；同期反攻期木材中位仅 106、40% 采样 <70（连 1 个战车弓兵都造不起）。
    // 黄金过剩(goldRich)时压到 MIN_GOLD_WORKERS，把人力让给食物与木头；铜器前为 0。
    int goldTarget = (!postBronze) ? 0
        : goldRich ? MIN_GOLD_WORKERS
        : std::max(MIN_GOLD_WORKERS,
                   std::min(GOLD_TARGET_MAX,
                            (int)((double)foodWorkers * GOLD_WORKER_PER_FOOD_NUM / GOLD_WORKER_PER_FOOD_DEN + 0.999)));"""
rep(old_t, new_t)
io.open(p, "wb").write(s.encode("utf-8"))
print("gold2wood patch OK, chars:", len(s))