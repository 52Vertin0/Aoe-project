# -*- coding: utf-8 -*-
# 追加 09-29 日志：probe_20260927 分析 + h3 结果。append-only，保持 LF。
import io, os

P = r'C:\Users\ZhuanZ\WorkBuddy\2026-07-29-18-11-46\.workbuddy\memory\2026-09-29.md'

TEXT = u'''
## 8 probe_20260927 分析（09-29 上午）—— 回答"为什么能运行但游戏失败"

**来源**：`D:\\deepseek\\optimize_new_aoe_20260921\\probe_20260927\\`
（`UsrAI.cpp` = `695734fc`·6741 行｜`UsrAI.h` = `a9987b36`·430 行，`MD5.txt` 自附）。
**不在我的备份链里**（7g/7h 全备份 md5 逐项比对无命中）；`.h` mtime = 09-28 18:30。

### 8.1 结论：它不是策略版本，是「最小探针」

`UsrAI::processData()`（cpp:554-583，**38 行**）被整体替换为：

```
只打一次 [ENV] → tagInfo probe = tagUsrGame.getInfo()  ← AI 线程直读，不走 postEvent 快照层
→ 每 300 帧打 [PROBE f=…]（各列表 size + W/M/G/S）→ CommitInstruction()（无指令可提交）
```

注释原文：「**只取一次快照、只打印标量与各列表 size；不下任何指令、不跑任何策略。**」

策略代码（`managePriest` / `manageCounterAttack` / `assignIdleSimple` / `tryBuild` /
`handleBuildResults` / `counterPriestConvert` … 数千行）**全部还在文件里，但成了死代码**
—— `processData` 不调用它们。

与当前 7g（`58143847`·7048 行）差异仅 **11 个变更块**：
① 类名 `UsrAISnapshotBase`(probe) vs `UsrAICore`(我)；② `processData`（38 行探针 vs 335 行加固实现区）；
③ 缺 ghost-build 4 处；④ 缺 gsync 2 处。常量全同（`WAVE1_TIME 5000` / `MAX_FARMS 10` / `SCOUT_MAX_DIST 45.0`
/ `PRIEST_TOWERS_CLEAR_MAX 2` / `BUILD_POS_BLACKLIST_FRAMES 1800`）。

### 8.2 为什么"能运行"（不崩）—— 是"什么都不做"的副产品

它**一次都不构造 `instruction`** ⇒ 不执行构造函数里的 `self = g_Object[SN]`
（`std::map::operator[]` 是**写操作**，key 不存在时插入节点 + 旋转红黑树）
⇒ **AI 线程对 `g_Object` 的写操作归零** ⇒ 红黑树无并发写
⇒ 09-29 定位的那条"无锁并发写踩坏 map"崩溃路径**在结构上不存在**。

**不是修好了，是把唯一会写那棵树的嘴巴闭上了。**

### 8.3 为什么"游戏失败"—— 必然，且是 0 不是"低"

AI 零指令 ⇒ 村民不采集/不建造、不训练兵、祭司不动、不反攻 ⇒ 我方阵营全程停摆
⇒ 敌方脚本 AI 主动推平。**胜率恒 0。**

### 8.4 真正的价值：这个探针实验是**成功**的

不崩 ⇒ 同时证伪两条假设：
1. 「引擎 `getInfo()` / 双缓冲在 Linux 上不安全（引擎 bug）」—— **否**；
2. 更关键：probe 用的是 **AI 线程直读 `tagUsrGame.getInfo()`**（完全不经过 postEvent 快照层）
   —— **连直读都不崩** ⇒ **引擎侧深拷贝也排除**。

⇒ 崩溃只在**策略层 / 指令下发路径**。
⇒ 与 09-29 独立做出的 `g_Object`（`MainWidget.cpp:35` 全局 map，全工程零锁）无锁并发写定位
**两条独立证据链吻合**。
⇒ 也解释了 09-23~27 几轮快照加固（深拷贝改线程、零拷贝 shared_ptr、完整性哨兵）为何全部无效：
那些 backtrace（`tagInfo::operator=` → `vector<tagBuilding>::operator=` → `memcpy`）
是**内存被踩之后崩在最方便的堆访问点上的假象**，不是根因。

### 8.5 probe 里两个会误导人的坑

- `UsrAI.h:30-31` 注释写「改为：先分配全局唯一 id 并缓存到 `InsPerFrame`，由 processData 末尾统一提交」
  —— **纯属未落地的设计意图**：`UsrAISnapshotBase` 里**既无 `InsPerFrame` 成员、也无 commit 函数**；
  而 `h:102` 的 `AddToIns` 实际仍**直推 `UsrIns.instructions`**（与旧版一字不差）。
- `UsrAI::AddToIns` 本身是**死代码**（引擎 `AI::HumanMove/...` 内写的是 `AI::AddToIns`，显式限定
  ⇒ 静态绑定，永不进派生类 override）⇒ **照那段注释去做"指令缓存"，会以为改了、其实一行都没生效**。
  （这正是 09-28 我改用显式 `commitInstruction()` 接管帧末提交的原因。）

## 9 h3 批（gsync 版 · map3）—— 首个「零崩溃」批

`MAP=map3.njust N=24 TAG=h3 PAR=4`，exe = 09-29 09:30:34（gsync 版 `58143847`）。

**结果：W=16 / L=4 / U=4 = 66.7%，24/24 局无一崩溃。**

| 批 | 内容 | 结果 |
|---|---|---|
| b3（基线 pre_marchfix） | — | 12/24 = 50.0% |
| m3（方案2：march 活锁修复） | — | 9/24 = 37.5% |
| g3（幽灵地基修复，**无** gsync） | — | 12胜/8负/1未决（21 局，**被崩溃打断**）⇒ 未证实 |
| **h3（幽灵地基 + gsync）** | — | **16/24 = 66.7%，零崩溃** |

Fisher 精确检验：h3 vs b3 **p=0.3801**｜h3 vs m3 **p=0.0820** ⇒ **样本仍不足以判定显著**
（铁律 81：≥24 局/臂，本次达标但两臂方差大）。两条支撑：① 方向一致 ② **零崩溃**。

⚠ 关键旁证：**本机 g3 批曾在 `g321` 崩于 f≈13**（exe 是 gsync 之前）⇒ **本机能复现该崩溃 = 本机可做 A/B**；
h3 批 24/24 无崩 ⇒ gsync 有效的初步证据。map2 防回归批（h2）随后启动。
'''

t = io.open(P, 'r', encoding='utf-8', newline='').read()
if u'## 8 probe_20260927 分析' in t:
    print('SKIP: 已有该节')
else:
    if not t.endswith('\n'):
        t += '\n'
    t += TEXT
    io.open(P, 'w', encoding='utf-8', newline='').write(t)
    print('APPENDED')

b = open(P, 'rb').read()
crlf = b.count(b'\r\n'); lf = b.count(b'\n')
print('size=%d lines=%d CRLF=%d bareLF=%d' % (len(b), lf, crlf, lf - crlf))
