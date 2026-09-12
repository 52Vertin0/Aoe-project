# -*- coding: utf-8 -*-
# 二轮压缩 MEMORY.md 回到 20000 限内
import io

P = r'C:\Users\ZhuanZ\WorkBuddy\2026-07-29-18-11-46\.workbuddy\memory\MEMORY.md'
CR = '\r\n'
t = io.open(P, 'r', encoding='utf-8', newline='').read()
print('BEFORE size=%d' % len(t.encode('utf-8')))

# A. §0 gsync 段压缩
OLD_A = CR.join([
 '    隐藏基类 5 个指令入口（`ai.h:21-25` 是**非虚 public** ⇒ 派生类同名声明即隐藏；已核对 `UsrAI.cpp`',
 '    内 **0 处** `AI::` 限定调用），转发前用 `g_Object.find()` 只读确认 SN 存在 ⇒ 引擎构造里的',
 '    `g_Object[key]` 必然命中已有键 ⇒ **退化为纯查找、不再改结构** ⇒ 树只由主线程单方修改。',
 '    残留仅 `find()` 只读；最坏读到旋转中节点 ⇒ 返回 nullptr ⇒ 丢弃该指令（= 引擎本会判的',
 '    `ACTION_INVALID_SN`）⇒ **把"必然崩溃"降为"最多丢一条指令"**。',
 '    ⚠ **不要**自建 `instruction` 绕过构造函数：`instruction()` 默认构造只设 `type=-1`，',
 '    `SN/obSN/option/DR/UR/BlockDR/BlockUR/ret` 全是垃圾值 ⇒ 漏初始化 = 新野值源。',
 '    ⚠ 引擎 `Core.cpp:1350/1355` **无 null 检查地解引用 `cur.self`** ⇒ **永不把 `instruction.self` 置 nullptr**。',
 '   · 本机亦复现（g3 第 21 局 g321 崩于 f≈13）；`syn.py` 前后均 **16 warn**（零增量；⚠ 须同口径比 —— 用 `syn.py <备份>` 而非 grep）。'])
NEW_A = CR.join([
 '    隐藏基类 5 个指令入口（`ai.h:21-25` 非虚 public ⇒ 同名声明即隐藏；已核对 `UsrAI.cpp` 内 **0 处** `AI::` 限定），',
 '    转发前用 `g_Object.find()` 只读确认 SN 存在 ⇒ 引擎构造里的 `g_Object[key]` 必然命中已有键 ⇒ **退化为纯查找**。',
 '    残留仅 `find()` 只读；最坏读到旋转中节点 ⇒ nullptr ⇒ 丢该指令（= 引擎本会判的 `ACTION_INVALID_SN`）。',
 '    ⚠ **不要**自建 `instruction` 绕过构造函数（默认构造只设 `type=-1`，其余字段全是垃圾值 ⇒ 新野值源）。',
 '    ⚠ 引擎 `Core.cpp:1350/1355` **无 null 检查地解引用 `cur.self`** ⇒ **永不把 `instruction.self` 置 nullptr**。',
 '   · 本机亦复现（g3 第 21 局 g321 崩于 f≈13）；`syn.py` 前后均 **16 warn**（⚠ 须用 `syn.py <备份>` 同口径比，非 grep）。'])

# B. §4 待办压缩
OLD_B = CR.join([
 '- 待拍板：① ★ **map3 专题**（优先级最高）——需 ㊀ 干净 A/B（在 `4bf8f9a0` 上单独去掉建造者保护跑 map3；',
 '  n8/n3 是两变量同变、**不可归因**）㊁ 排查**农场建造者被谁改派**（map3 卡死建筑 农场 432 次 > 房子 397，map2 以房子为主）；',
 '  ② 卡死自救活锁（瓶颈④）；③ 黄金供给（先只读探针）；④ `tryAssignFood` 新增 `if (foodStop) return false;` 是否有意；',
 '  ⑤ 8 个死字段是否删；⑥ `[TOWER-APPROACH]` 30 格内不发攻击令是否过保守；⑦ map2 剩余败局同瓶颈①（方向已关）。'])
NEW_B = CR.join([
 '- 待拍板：① ★ **map3 专题**——需干净 A/B（在 `4bf8f9a0` 上单独去掉建造者保护跑 map3；n8/n3 两变量同变、**不可归因**）；',
 '  ② 排查**农场建造者被谁改派**（map3 卡死建筑 农场 432 次 > 房子 397）；③ `tryAssignFood` 新增 `if (foodStop) return false;` 是否有意；',
 '  ④ 8 个死字段是否删；⑤ `[TOWER-APPROACH]` 30 格内不发攻击令是否过保守；⑥ ★ **h2 批（map2 防回归）前 8 局仅 3 胜** ⇒ 待 24 局定论。'])

# C. §3 probe 段压缩
OLD_C = CR.join([
 '  ★★ **`probe_20260927`（D:\\deepseek\\optimize_new_aoe_20260921\\）= 「最小探针」不是策略版**：',
 '  其 `processData` 只 `tagUsrGame.getInfo()` 直读 + 打各列表 size，**不下任何指令** ⇒ 不构造 `instruction`',
 '  ⇒ 不碰 `g_Object` ⇒ **结构性不崩**，但**胜率恒 0**。这是二分法的**成功**实验：不崩 ⇒ ①证伪「引擎',
 '  `getInfo()` 在 Linux 不安全」②**连 AI 线程直读 getInfo() 都安全** ⇒ 崩只在**策略层/指令下发路径**',
 '  ⇒ 与 `g_Object` 定位**互证**；也解释 09-23~27 几轮快照加固为何全无效（backtrace 是内存被踩后的假象）。'])
NEW_C = CR.join([
 '  ★★ **`probe_20260927`（D:\\deepseek\\…）= 「最小探针」非策略版**：其 `processData` 只直读 `getInfo()`+打 size，',
 '  **不下任何指令** ⇒ 不构造 `instruction` ⇒ 不碰 `g_Object` ⇒ **结构性不崩、但胜率恒 0**。二分法**成功**实验：',
 '  不崩 ⇒ ①证伪「引擎 `getInfo()` 在 Linux 不安全」②连 AI 线程直读都安全 ⇒ 崩只在**策略层/指令路径** ⇒ 与',
 '  `g_Object` 定位**互证**；也解释 09-23~27 快照加固全无效（backtrace 是内存被踩后的假象）。'])

for old, new, tag in [(OLD_A, NEW_A, 'A-gsync'), (OLD_B, NEW_B, 'B-待办'), (OLD_C, NEW_C, 'C-probe')]:
    n = t.count(old)
    if n != 1:
        print('!! %s hits=%d <-- 跳过' % (tag, n)); continue
    t = t.replace(old, new, 1); print('ok %s' % tag)

io.open(P, 'w', encoding='utf-8', newline='').write(t)
b = open(P, 'rb').read()
print('AFTER size=%d (limit 20000) CRLF=%d lines=%d' % (len(b), b.count(b'\r\n'), b.count(b'\n')))
