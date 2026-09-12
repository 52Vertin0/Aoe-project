# -*- coding: utf-8 -*-
"""
2026-09-29 OJ SIGSEGV 根因加固：消除 AI 线程对 g_Object 的"结构性写"

根因链（完整证据见 UsrAI.cpp 内插入的区块注释）：
  instruction 的四个构造函数全部执行 `self = g_Object[SN]`（GlobalVariate.cpp:599-620），
  g_Object 是全局 std::map（MainWidget.cpp:35）且全工程零锁保护；
  std::map::operator[] 在 key 不存在时会插入节点并旋转红黑树（结构性写），
  与主线程的单位进场 insert / 阵亡置 NULL 并发 ⇒ 树被写坏 ⇒ 崩溃点随机落在下一次堆访问。

本补丁只做两件事：
  A. UsrAI.h —— 隐藏基类 5 个指令入口（非虚 public ⇒ 同名声明即隐藏）
  B. UsrAI.cpp —— 转发前用 find() 只读确认 SN 存在，再调引擎实现
                  + tryBuild 记账原子性守卫

用法：python patch_gsync.py
可重跑：锚点均断言命中 1 次。
"""
import sys, io, os

G = r'C:\new-aoe3.0.7g'
H = os.path.join(G, 'UsrAI.h')
C = os.path.join(G, 'UsrAI.cpp')


def read_text(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def write_text(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(t)


def sub1(text, old, new, tag):
    n = text.count(old)
    if n != 1:
        print('FAIL %-22s matched %d (expect 1)' % (tag, n))
        sys.exit(1)
    print('  ok %-22s (1 hit)' % tag)
    return text.replace(old, new, 1)


# ============================================================================
# A. UsrAI.h —— 隐藏基类 5 个指令入口（CRLF 原样保留）
# ============================================================================
h = read_text(H)
assert '\r\n' in h, 'UsrAI.h 应为 CRLF'

H_OLD = (
    "private:\r\n"
    "    void processData() override;           // 引擎入口：跑完一帧业务后调用 commitInstruction()\r\n"
    "    void processFrame();                   // 业务主体（原 processData 的全部内容）\r\n"
)
H_NEW = (
    "private:\r\n"
    "    void processData() override;           // 引擎入口：跑完一帧业务后调用 commitInstruction()\r\n"
    "    void processFrame();                   // 业务主体（原 processData 的全部内容）\r\n"
    "\r\n"
    "    // ★★★ 2026-09-29 OJ SIGSEGV 根因加固：隐藏基类 5 个指令入口（机理见 .cpp 同名区块）★★★\r\n"
    "    //   根因：instruction 的四个构造函数都执行 `self = g_Object[SN]`（GlobalVariate.cpp:599-620），\r\n"
    "    //   而 g_Object 是全局 std::map（MainWidget.cpp:35）且全工程零锁保护 ⇒ std::map::operator[]\r\n"
    "    //   在 key 不存在时【插入节点 + 旋转红黑树】(结构性写)，与主线程在 Core.cpp:143/264/347/382/417\r\n"
    "    //   的 `g_Object[SN]=NULL`、Army/Farmer/Building/Animal.cpp 的 insert 并发 ⇒ 树被写坏 ⇒\r\n"
    "    //   崩溃点随机落在下一次堆访问（4 次 OJ 崩点各异：428 / 501 / shared_ptr get / 700）。\r\n"
    "    //   本组方法在转发前用 g_Object.find() 只读确认 SN 存在 ⇒ 引擎构造里的 g_Object[key]\r\n"
    "    //   必然命中已有键 ⇒ 退化为纯查找、不再改结构 ⇒ 消除 AI 侧对 g_Object 的全部写操作。\r\n"
    "    //   ⚠ 基类这 5 个都是 **非虚 public** 函数（ai.h:21-25）⇒ 派生类同名声明即隐藏；\r\n"
    "    //      UsrAI.cpp 内 0 处 `AI::` 限定调用（已核对）⇒ 全覆盖。外部经 AI* 的调用\r\n"
    "    //      （Core.cpp:778 / SelectWidget.cpp:1105+）频率低且属引擎自身代码，不受影响。\r\n"
    "    int HumanMove(int SN, double DR0, double UR0);\r\n"
    "    int HumanAction(int SN, int obSN);\r\n"
    "    int HumanBuild(int SN, int BuildingNum, int BlockDR, int BlockUR);\r\n"
    "    int BuildingAction(int SN, int Action);\r\n"
    "    int PinPointStrike(int SN, double DR0, double UR0);\r\n"
)
h = sub1(h, H_OLD, H_NEW, 'h: 5 个方法声明')
write_text(H, h)
print('UsrAI.h 写回完成')

# ============================================================================
# B. UsrAI.cpp —— 实现块（LF 原样保留）
# ============================================================================
c = read_text(C)
assert '\r\n' not in c, 'UsrAI.cpp 应为纯 LF'

C_IMPL_ANCHOR = (
    "// ============================================================================================\n"
    "// ★★★ 2026-09-28 帧边界：processData 只做\"跑一帧 + 帧末统一提交指令\"两件事 ★★★\n"
)
C_IMPL_NEW = (
    "// ============================================================================================\n"
    "// ★★★ 2026-09-29 OJ SIGSEGV 根因加固：消除 AI 线程对 g_Object 的\"结构性写\" ★★★\n"
    "// 现象：4 次 OJ backtrace 崩点各异却全在\"堆访问\"上 —— UsrAI.cpp:428 / UsrAI.cpp:501\n"
    "//   （= infoPtr = fresh）/ shared_ptr_base.h:1665 get()（内联进 processData）/\n"
    "//   UsrAI.cpp:700（= frame = infoPtr->GameFrame）。本机 g321 亦复现（崩于 f≈13）。\n"
    "// 根因：instruction 的**四个构造函数全部**执行 `this->self = g_Object[SN]`\n"
    "//   （HumanAction 那条多一句 `this->obj = g_Object[obSN]`，见 GlobalVariate.cpp:599-620），\n"
    "//   而 g_Object 是**全局 std::map<int, Coordinate*>**（定义在 MainWidget.cpp:35），\n"
    "//   **全工程零锁保护**（唯一那把 AI::aiLock 在 AI.cpp:73-78 只有定义、零调用点，是死锁）。\n"
    "//   std::map::operator[] 在 key 不存在时**插入节点并旋转红黑树** —— 这是结构性写。\n"
    "//   与此同时主线程也在写同一棵树：单位进场 insert（Army.cpp:75/118、Farmer.cpp:61、\n"
    "//   Building.cpp:55、Animal.cpp:51）；单位阵亡 `g_Object[SN]=NULL`\n"
    "//   （Core.cpp:143/264/347/382/417）。\n"
    "//   ⇒ 两线程并发改同一棵红黑树 ⇒ 节点被写坏 ⇒ **崩溃点随机落在下一次堆访问上**\n"
    "//   （这正是 4 次崩点各不相同的成因；也是\"快照零拷贝 + 完整性哨兵\"治不好的原因 ——\n"
    "//     那层加固的是快照内容，与本根因无关：实测 [SNAP] bad=0、[DIRTY-SNAP] 累计 0 佐证）。\n"
    "// AI 侧可行边界：加不了锁（aiLock 是死锁；tagGame::Locker 是引擎私有成员；提交范围只有\n"
    "//   UsrAI.cpp/.h ⇒ 不能新增引擎符号）⇒ 只能**消除 AI 侧的全部写操作**：先用 find() 只读\n"
    "//   确认 SN 存在，再转发给引擎的 Human*；此后构造里的 `g_Object[key]` 命中的是已存在的键\n"
    "//   ⇒ 退化为纯查找，不再插入、不再旋转 ⇒ 树结构只由主线程单方修改。\n"
    "//   ⚠ 残留的 g_Object 访问只有 find()（本组函数 + instructionSelfOk + commitInstruction\n"
    "//     校验），全为只读；只读与主线程写并发的最坏后果是\"读到旋转中的节点\"⇒ 返回无效指针\n"
    "//     ⇒ 本组判为 nullptr 并丢弃该指令（等价于引擎原本会判的 ACTION_INVALID_SN，\n"
    "//     Core.cpp:1355），**不会损坏内存** ⇒ 把\"必然崩溃\"降为\"最多丢一条指令\"。\n"
    "//   ⚠ 为什么不自己构造 instruction 绕过构造函数：默认构造 instruction() 只设 type=-1\n"
    "//     （GlobalVariate.cpp:595），SN/obSN/option/DR/UR/BlockDR/BlockUR/ret 全是未初始化垃圾值\n"
    "//     ⇒ 漏初始化任一项就是新的野值源（比 obj 野指针更难查）。转发引擎构造则零遗漏。\n"
    "//   ⚠ 基类这 5 个是**非虚 public** 函数 ⇒ 派生类同名声明即隐藏生效；用 `AI::` 显式限定转发\n"
    "//     自身 ⇒ 不构成自递归。\n"
    "// ============================================================================================\n"
    "static Coordinate* lookupObjectRO(int sn) {\n"
    "    const std::map<int, Coordinate*>::const_iterator it = g_Object.find(sn);\n"
    "    return (it == g_Object.end()) ? nullptr : it->second;\n"
    "}\n"
    "\n"
    "int UsrAI::HumanMove(int SN, double DR0, double UR0) {\n"
    "    if (!lookupObjectRO(SN)) return -1;             // SN 不在引擎表 ⇒ 丢弃（引擎亦会判 INVALID_SN）\n"
    "    return AI::HumanMove(SN, DR0, UR0);             // 显式限定 ⇒ 调引擎实现，避免自递归\n"
    "}\n"
    "int UsrAI::HumanAction(int SN, int obSN) {\n"
    "    if (!lookupObjectRO(SN) || !lookupObjectRO(obSN)) return -1;\n"
    "    return AI::HumanAction(SN, obSN);\n"
    "}\n"
    "int UsrAI::HumanBuild(int SN, int BuildingNum, int BlockDR, int BlockUR) {\n"
    "    if (!lookupObjectRO(SN)) return -1;\n"
    "    return AI::HumanBuild(SN, BuildingNum, BlockDR, BlockUR);\n"
    "}\n"
    "int UsrAI::BuildingAction(int SN, int Action) {\n"
    "    if (!lookupObjectRO(SN)) return -1;\n"
    "    return AI::BuildingAction(SN, Action);\n"
    "}\n"
    "int UsrAI::PinPointStrike(int SN, double DR0, double UR0) {\n"
    "    if (!lookupObjectRO(SN)) return -1;\n"
    "    return AI::PinPointStrike(SN, DR0, UR0);\n"
    "}\n"
    "\n"
    + C_IMPL_ANCHOR
)
c = sub1(c, C_IMPL_ANCHOR, C_IMPL_NEW, 'cpp: 加固实现块')

# ---- 记账原子性守卫：tryBuild 里 HumanBuild 之前先确认建造者 SN 有效 ----
C_TB_OLD = (
    "    auto tryTIssue = tryNow();\n"
    "    buildingFarmerType[f->SN] = buildingType;\n"
)
C_TB_NEW = (
    "    // ★ 2026-09-29 加固层守卫：建造者 SN 不在引擎表 ⇒ 本次 HumanBuild 必被丢弃（返回 -1）\n"
    "    //   ⇒ 提前退出，避免把 -1 写进 pendingBuildIns / pendingBuildInsFrame 造成记账错乱。\n"
    "    //   （f 取自当帧快照的 farmers，正常恒有效 ⇒ 该分支实际不会触发，属纯防御。）\n"
    "    if (!lookupObjectRO(f->SN)) { tryFlush(); return false; }\n"
    "    auto tryTIssue = tryNow();\n"
    "    buildingFarmerType[f->SN] = buildingType;\n"
)
c = sub1(c, C_TB_OLD, C_TB_NEW, 'cpp: tryBuild 记账守卫')

write_text(C, c)
print('UsrAI.cpp 写回完成')
print('DONE')
