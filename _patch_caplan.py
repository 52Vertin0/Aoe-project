# -*- coding: utf-8 -*-
import io, sys
p = r"C:\new-aoe3.0.7g\UsrAI.cpp"
s = io.open(p, encoding="utf-8").read()
def rep(old, new, n=1):
    global s
    c = s.count(old)
    assert c == n, "anchor count=%d (want %d): %r" % (c, n, old[:60])
    s = s.replace(old, new, n)

# (1) 不造学院 / 不造马厩（马厩唯一用途=学院前置；bronze 前置实测 m1r1s0，从不需要马厩）
rep("#define DISABLE_STABLE_BUILD  false   // 马厩建造开关：false=允许建造（作学院前置；骑兵仍不训练）",
    "#define DISABLE_STABLE_BUILD  true    // ★2026-10-08【全战车弓兵】不造马厩：其唯一用途是学院前置；\n                                      //   实测 bronze 硬前置恒为 m1r1s0(market+range 已经=2)，从不依赖马厩 ⇒ 省 150 木。")
rep("#define DISABLE_COLLAGE_BUILD false   // 学院建造开关：false=允许建造（方阵兵产线，后期即可投产）",
    "#define DISABLE_COLLAGE_BUILD true    // ★2026-10-08【全战车弓兵】不造学院：方阵兵(肉盾)停产的唯一入口；\n                                      //   省 60食+40金，且避免其占用建造期木材。")

# (2) 减少黄金矿工
rep("#define MIN_GOLD_WORKERS 1      // 至少1人挖金！复合弓兵/阔剑兵/方阵兵/投石车/后勤科技真扣黄金",
    "#define MIN_GOLD_WORKERS 1      // 至少1人挖金！复合弓兵/阔剑兵/方阵兵/投石车/后勤科技真扣黄金\n"
    "// \u2605\u2605\u2605 2026-10-08\u3010\u5168\u6218\u8f66\u5f13\u5175\u00b7\u51cf\u91d1\u5de5\u3011\u2605\u2605\u2605 \u6218\u8f66\u5f13\u5175\u53ea\u5403 \u98df\u7269+\u6728\u6750\uff08\u4e0d\u6263\u9ec4\u91d1\uff09\uff0c\n"
    "//   \u9614\u5251\u79d1\u6280\u5df2\u5c01\u7981\u3001\u5b66\u9662/\u65b9\u9635\u5175\u5df2\u505c\u5efa \u21d2 \u5168\u573a\u9ec4\u91d1\u9700\u6c42\u4ec5\u5269\u62a4\u7532\u4e8c\u7ea7\u79d1\u6280(50+50)\u3002\n"
    "//   \u6545\u628a\u91d1\u5de5\u76ee\u6807\u4ece food\u00d73/5 \u964d\u5230 food\u00d71/4 \u5e76\u52a0\u786c\u4e0a\u9650\uff0c\u5bcc\u4f59\u4eba\u529b\u8f6c\u53bb\u6728\u6750\uff08\u9776\u573a\u74f6\u9888\uff09\u3002\n"
    "#define GOLD_TARGET_MAX 3\n"
    "#define GOLD_WORKER_PER_FOOD_NUM 1\n"
    "#define GOLD_WORKER_PER_FOOD_DEN 4")

old_t = """    // 黄金目标人数：与食物工数按 FOOD_GOLD_DEN:FOOD_GOLD_NUM(5:3) 配比（复合弓40食+20金 / 方阵60食+40金 ⇒ 100:60）。
    // 黄金过剩(goldRich)时压到 MIN_GOLD_WORKERS，把人力让给食物与木头；铜器前为 0。
    int goldTarget = (!postBronze) ? 0
        : goldRich ? MIN_GOLD_WORKERS
        : std::max(MIN_GOLD_WORKERS,
                   (int)((double)foodWorkers * FOOD_GOLD_DEN / FOOD_GOLD_NUM + 0.999));"""
new_t = """    // 黄金目标人数：★2026-10-08【全战车弓兵】减金工★ 战车弓兵只吃 食物+木材（不扣黄金），
    //   阔剑科技封禁 + 学院/方阵兵停建 ⇒ 黄金只供护甲二级科技(50+50) ⇒ 目标 = food×1/4 且 ≤ GOLD_TARGET_MAX(3)。
    // 黄金过剩(goldRich)时压到 MIN_GOLD_WORKERS，把人力让给食物与木头；铜器前为 0。
    int goldTarget = (!postBronze) ? 0
        : goldRich ? MIN_GOLD_WORKERS
        : std::max(MIN_GOLD_WORKERS,
                   std::min(GOLD_TARGET_MAX,
                            (int)((double)foodWorkers * GOLD_WORKER_PER_FOOD_NUM / GOLD_WORKER_PER_FOOD_DEN + 0.999)));"""
rep(old_t, new_t)

io.open(p, "wb").write(s.encode("utf-8"))
print("ca-plan patch OK, chars:", len(s))