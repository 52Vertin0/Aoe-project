# -*- coding: utf-8 -*-
import io
p = r"C:\new-aoe3.0.7g\UsrAI.cpp"
s = io.open(p, encoding="utf-8").read()
OLD = """            if (priestMoveCooldown > 0) {
                bool rejected = (priestConvSN == convSN && priest->NowState == HUMAN_STATE_IDLE &&
                                 priestConvFrame > -999999 && frame - priestConvFrame >= 15);
                if (!rejected) return;
            }"""
NEW = """            // \u2605\u2605 2026-10-08\u3010\u611f\u5316\u4e0d\u5403\u79fb\u52a8\u8282\u6d41\u3011\u2605\u2605
            //   \u539f\u95f8 `if (priestMoveCooldown > 0) { ... if(!rejected) return; }` \u7528\u7684\u662f\u300c\u79fb\u52a8\u4ee4\u8282\u6d41\u300d
            //   \uff08priestApproachMove/priestFlee \u6bcf\u53d1\u4e00\u6761\u79fb\u52a8\u4ee4\u5c31\u628a cd \u8bbe\u6210 20 \u5e27\uff09\uff1b
            //   \u5b9e\u6d4b\u53cd\u653b\u671f\u8be5 cd \u6709 91.7% \u65f6\u95f4\u975e\u96f6 \u21d2 \u300c\u654c\u5df2\u5728 28 \u683c\u5185\u300d\u7684\u7a97\u53e3\u91cc 86% \u88ab\u81ea\u5bb6\u95f8\u95e8\u6321\u6389
            //   \uff08\u53ef\u8d77\u624b\u7a97\u53e3\u53ea\u5269 5.0%\uff1b\u7406\u8bba 20s/\u4e2a \u21d2 \u5b9e\u6d4b 165s/\u4e2a\uff09\u3002
            //   \u6545\u611f\u5316\u6539\u7528\u3010\u81ea\u8eab\u9632\u91cd\u53d1\u95f8\u3011\uff1a
            //     \u2460 \u5f15\u5bfc\u4e2d(WORKING/ATTACKING) \u7edd\u4e0d\u518d\u53d1 \u2192 \u91cd\u53d1\u4f1a\u6253\u65ad\u5f15\u5bfc\uff08\u4e0a\u65b9 canAct \u95f8\u5df2\u515c\u5e95\uff0c\u53cc\u4fdd\u9669\uff09
            //     \u2461 \u8ddd\u4e0a\u6b21\u611f\u5316\u4ee4 <15 \u5e27 \u4e0d\u518d\u53d1 \u2192 \u7ed9\u5f15\u64ce 0.6 \u79d2\u53cd\u5e94\u65f6\u95f4\uff0c\u4fdd\u7559\u539f\u300c\u62d2\u6536\u68c0\u6d4b\u540e\u91cd\u53d1\u300d\u80fd\u529b
            //   \u5176\u4f59\u60c5\u51b5\uff08\u542b priestMoveCooldown>0\uff09\u4e00\u5f8b\u5141\u8bb8\u611f\u5316\u3002
            if (priest->NowState == HUMAN_STATE_WORKING ||
                priest->NowState == HUMAN_STATE_ATTACKING) return;
            if (priestConvFrame > -999999 && (frame - priestConvFrame) < 15) return;"""
c = s.count(OLD)
assert c == 1, "anchor count=%d" % c
s = s.replace(OLD, NEW, 1)
io.open(p, "wb").write(s.encode("utf-8"))
print("conv-no-move-throttle patch OK, chars:", len(s))