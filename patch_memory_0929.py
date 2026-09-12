# -*- coding: utf-8 -*-
"""2026-09-29 更新 MEMORY.md：入档 g_Object 跨线程无锁并发（OJ 崩溃根因）"""
import io, sys, os

P = r'C:\Users\ZhuanZ\WorkBuddy\2026-07-29-18-11-46\.workbuddy\memory\MEMORY.md'
CRLF = '\r\n'


def sub1(t, old, new, tag):
    n = t.count(old)
    if n != 1:
        print('FAIL %-16s matched %d' % (tag, n))
        sys.exit(1)
    print('  ok %-16s' % tag)
    return t.replace(old, new, 1)


with io.open(P, 'r', encoding='utf-8', newline='') as f:
    t = f.read()
assert '\r\n' in t, 'MEMORY.md 应为 CRLF'

# ---- ① 标题版本号 ----
t = sub1(t,
         '# AOE UsrAI 记忆（v72 · 2026-09-28）',
         '# AOE UsrAI 记忆（v73 · 2026-09-29）',
         'title')

# ---- ② §0 版本行 + 新增根因大条目 ----
OLD2 = ('- **工作副本 `C:\\new-aoe3.0.7g\\UsrAI.cpp`＋`.h` = `774348fe`·6968／`ef95ac14`·490**（2026-09-28）。' + CRLF +
        '  7h 镜像 `C:\\new-aoe3.0.7h\\` 同 md5、**逐字节一致**（`cmp` 校验过）。' + CRLF)
NEW2 = ('- **工作副本 `C:\\new-aoe3.0.7g\\UsrAI.cpp`＋`.h` = `58143847`·7048／`370b53c7`·507**（2026-09-29）。' + CRLF +
        '  7h 镜像 `C:\\new-aoe3.0.7h\\` 同 md5、**逐字节一致**（`cmp` 校验过）。' + CRLF +
        '- ★★★★★ **09-29 OJ 崩溃根因钉死：`g_Object` 跨线程无锁并发**（第 4 次 backtrace）。' + CRLF +
        '  判据：4 次崩点各异（`UsrAI.cpp:428`／`501`／`shared_ptr_base.h:1665 get()`／`700`）' + CRLF +
        '  **却全落在"堆访问"上** ⇒ 不是逻辑漏判，是内存被踩。' + CRLF +
        '  · `g_Object` = 全局 `std::map<int,Coordinate*>`（`MainWidget.cpp:35`），**全工程零锁**；' + CRLF +
        '    唯一那把 `AI::aiLock`（`ai.h:49`）在 `AI.cpp:73-78` **只有定义、零调用点（是死锁）**。' + CRLF +
        '  · AI 线程每次构造指令都做**结构性写**：`GlobalVariate.cpp:595-620` 四个构造**全部**执行' + CRLF +
        '    `self=g_Object[SN]`（HumanAction 那条多一句 `obj=g_Object[obSN]`），而 `std::map::operator[]`' + CRLF +
        '    在 key 不存在时**插入节点并旋转红黑树**。' + CRLF +
        '  · 主线程同时写同一棵树：insert（`Army.cpp:75/118`·`Farmer.cpp:61`·`Building.cpp:55`·`Animal.cpp:51`）、' + CRLF +
        '    置空（`Core.cpp:143/264/347/382/417` 的 `g_Object[SN]=NULL`）。' + CRLF +
        '  · ⇒ 树被写坏 ⇒ **崩点随机落在下一次堆访问**。⚠ §0 的零拷贝+哨兵治不了它（哨兵管的是**快照内容**：' + CRLF +
        '    实测 `[SNAP] bad=0`、`[DIRTY-SNAP]=0` 正是"快照健康"的证据）。' + CRLF +
        '  · **修法**（AI 侧唯一可行边界：加不了锁——aiLock 死锁、`tagGame::Locker` 私有、禁止新增引擎符号）：' + CRLF +
        '    隐藏基类 5 个指令入口（`ai.h:21-25` 是**非虚 public** ⇒ 派生类同名声明即隐藏；已核对 `UsrAI.cpp`' + CRLF +
        '    内 **0 处** `AI::` 限定调用），转发前用 `g_Object.find()` 只读确认 SN 存在 ⇒ 引擎构造里的' + CRLF +
        '    `g_Object[key]` 必然命中已有键 ⇒ **退化为纯查找、不再改结构** ⇒ 树只由主线程单方修改。' + CRLF +
        '    残留仅 `find()` 只读；最坏读到旋转中节点 ⇒ 返回 nullptr ⇒ 丢弃该指令（= 引擎本会判的' + CRLF +
        '    `ACTION_INVALID_SN`）⇒ **把"必然崩溃"降为"最多丢一条指令"**。' + CRLF +
        '    ⚠ **不要**自建 `instruction` 绕过构造函数：`instruction()` 默认构造只设 `type=-1`，' + CRLF +
        '    `SN/obSN/option/DR/UR/BlockDR/BlockUR/ret` 全是垃圾值 ⇒ 漏初始化 = 新野值源。' + CRLF +
        '    ⚠ 引擎 `Core.cpp:1350/1355` **无 null 检查地解引用 `cur.self`** ⇒ **永不把 `instruction.self` 置 nullptr**。' + CRLF +
        '  · **本机亦复现**：g3 批第 21 局（`g321`）崩于 **f≈13**（`ait` 末两条 = `PRODUCE FARMER f=12` +' + CRLF +
        '    `[INS-BAD f=12]`；`[ENV] NOWPLAYER=2 MAXPLAYER=8`）⇒ 跑局中断、map2 批从未启动。' + CRLF +
        '  · **校验**：`syn.py` 改动前 **16 warn** == 改动后 **16 warn** ✅ 零增量。' + CRLF +
        '    ⚠ 口径坑：必须用 `syn.py <备份文件>` 对比；`grep -c "warning:"` 只得 12（≠ syn 的 `\\bwarning\\b` 16）。' + CRLF)
t = sub1(t, OLD2, NEW2, 'sec0')

# ---- ③ §1 增补铁律 ----
OLD3 = '- ★★★ 只提交 `UsrAI.cpp`＋`.h`；**严禁引用引擎新增符号**（悬空 extern ⇒ 判零）。' + CRLF
NEW3 = (OLD3 +
        '- ★★★ **引擎全局 `g_Object`（`std::map`）跨线程无锁**：AI 线程 `g_Object[SN]`（`operator[]`）' + CRLF +
        '  就会**插入节点+旋转红黑树**（结构性写），与主线程增删单位并发 ⇒ 树被踩坏 ⇒ 崩点随机。' + CRLF +
        '  **AI 侧只许用 `find()`（只读）**，绝不用 `operator[]`；新写指令通道一律先 `find` 预检再转发。' + CRLF)
t = sub1(t, OLD3, NEW3, 'sec1')

# ---- ④ §3 增补瓶颈⑤ ----
OLD4 = '  `[MARCH-SELF]` 21/24 局有「>=2档」（最高 949，活锁下理论恒 0）⇒ **活锁已解**，胜负零回归。' + CRLF
NEW4 = (OLD4 +
        '- **瓶颈⑤ OJ/本机 SIGSEGV（09-29 已定位并加固）**：根因 = §0 的 `g_Object` 跨线程无锁并发。' + CRLF +
        '  待跑局验收（`h3` 批：24 局 map3 是否 24/24 不再中断；对照 g3 批 21/24 即崩）。' + CRLF +
        '  ⚠ g3 批（仅 ghost-build 的幽灵地基修复）= **12胜/8负/1未决（21 局）** vs 基线 b3 = 12/24（50%）' + CRLF +
        '  ⇒ **未见改善**，且被崩溃打断 ⇒ ghost-build 效果**未证实**，与本次加固混在同一 exe 内一并验收。' + CRLF)
t = sub1(t, OLD4, NEW4, 'sec3')

with io.open(P, 'w', encoding='utf-8', newline='') as f:
    f.write(t)

b = open(P, 'rb').read()
print('DONE  size=%d CRLF=%d bareLF=%d' % (len(b), b.count(b'\r\n'), b.count(b'\n') - b.count(b'\r\n')))
