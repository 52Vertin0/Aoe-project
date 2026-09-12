import io, sys, os

M = r"C:\Users\ZhuanZ\WorkBuddy\2026-07-29-18-11-46\.workbuddy\memory"

def crlf(s):
    return s.replace("\r\n", "\n").replace("\n", "\r\n")

def load(fn):
    p = os.path.join(M, fn)
    b = open(p, "rb").read()
    return b.decode("utf-8"), p

def save(txt, p):
    open(p, "wb").write(txt.encode("utf-8"))

def rep(txt, old, new, tag):
    n = txt.count(old)
    assert n == 1, "FAIL[%s]: hits=%d" % (tag, n)
    return txt.replace(old, new, 1)

# ---------------- MEMORY.md ----------------
t, p = load("MEMORY.md")

# 1) 分流行：条数 70->73，章节 §A~§Y -> §A~§Z
t = rep(t,
    "（§A~§Y）｜铁律全表（70 条）→ `detail_laws.md`｜",
    "（§A~§Z）｜铁律全表（73 条）→ `detail_laws.md`｜",
    "MEMORY.divert")

# 2) §6 标题条数
t = rep(t,
    "## 6 铁律（70 条全表＋逐条详解见 `detail_laws.md`）",
    "## 6 铁律（73 条全表＋逐条详解见 `detail_laws.md`）",
    "MEMORY.sec6title")

# 3) 新增铁律 71~73
anchor70 = '★ 升格判据：**"固定尺寸数组 + 运行时变量作上界"是必查项**。｜'
add71_73 = anchor70 + crlf("""
71 ★★★ **"临界值必须与结构尺寸严格对应"**（配置扫描收尾判据）：`NOWPLAYER` 临界值落 **3** 而数组长 **2**
⇒ 2 正常、3/4/8 全崩 ⇒ **因果闭合**；临界值与尺寸对不上 ⇒ 还有别的因素，别收工｜
72 ★★★ **崩溃栈的行号 = 版本指纹**：栈中某文件行号与本地对不上 ⇒ **评测机源码 ≠ 本地**
（实证 `tagInfo::operator=` 栈里 `GlobalVariate.cpp:1013` / 本地 `1072`，**差 59 行**）；
行号吻合者（`UsrAI.cpp:473` = `info = getInfo();`）可确证"提交的就是评测机在用的"。**跨机崩溃先做行号对齐**｜
73 ★★★ **先看崩溃读到的地址"是什么性质"**：`insert`/`=NULL`/`clear()` **都不 free** ⇒ 不产生 **unmapped**
⇒ **凡崩溃源"不可访问"，破坏者必是 `free`/`delete`/`munmap`**；据此一刀排除"无锁容器竞争"类假说｜""")
t = rep(t, anchor70, add71_73, "MEMORY.law71_73")

# 4) §0/§1 之间插入第 6 轮版本note
anchor_sec1 = "## 1 动手前必看"
note6 = crlf("""- ★★★ **2026-09-19 深夜（第 6 轮 · 站内可修性判定）**：用户确认「评测机只收 `UsrAI.cpp`/`UsrAI.h`」后，
  本轮只判一件事：**站内能不能修 ⇒ 不能**（四堵墙：`Info` private｜`getInfo()` 唯一读口无钩子｜
  `tryLock`/`getInfo` **共用一把非递归锁** ⇒ 先锁后读必死锁｜信号兜底会漏锁致卡死且本机验证无预测价值）。
  ① **第三次、最终否证"数据竞争"**：`tryLock/release/getInfo/insertInsRet` **同一把 `Locker`**（`GlobalVariate.cpp:1140-1163`），
  写侧在双锁内（`MainWidget.cpp:2259-2273`）⇒ **读写互斥**。
  ② 候选清理：`g_Object` 无锁 map（`insert`/`=NULL` **不 free** ⇒ 不产生 unmapped ⇒ 无法解释崩溃，**降级**）｜
  指令三出口**全有边界校验** ⇒ "AI 乱发参数"否｜`playerMap` 是 `Core` 成员（非局部）⇒ 不悬垂｜`tagInfo` 无自定义析构。
  ③ ★★ **配置扫描临界值**：`NOWPLAYER` **2 正常 / 3（17s）、4（19s）、8（21s）全崩、ait 均 61 行**
  ⇒ **临界值 3 与数组长 2 严格对应 ⇒ 因果闭合**。
  ④ ★★ **版本指纹**：栈里 `tagInfo::operator=` = `GlobalVariate.cpp:1013`、本地 **1072**（**差 59 行**）
  ⇒ **评测机引擎源码 ≠ 本地**；`UsrAI.cpp:473` 精确吻合 ⇒ 提交的那份与评测机一致。
  **产出**：`aoe3_crash_20260919_r6.html` ＋ **`aoe3_oj_defect_report.md`（可直接转发评测方）**｜**新铁律 71~73**｜`np3.ait`。
  **待用户**：① 评测机 `config.json` 的 `NOWPLAYER`（≥3 ⇒ 就是本缺陷，改两行收工）；② 评测机引擎源码（对齐 59 行差异）。

""")
t = rep(t, anchor_sec1, note6 + anchor_sec1, "MEMORY.note6")

save(t, p)
print("MEMORY.md OK  lines=%d" % t.count("\n"))

# ---------------- detail_laws.md ----------------
t, p = load("detail_laws.md")
t = rep(t, "# 通用铁律 70 条（详解版 · 2026-09-19）",
        "# 通用铁律 73 条（详解版 · 2026-09-19）", "laws.title")
t = t.rstrip("\r\n") + crlf("""

71. ★★★ **"临界值必须与结构尺寸严格对应"**（配置扫描的收尾判据）
   - 单变量扫描配置值时，只看"崩/不崩"不够 —— 要看**翻转点落在哪里**。
   - 实证：`NOWPLAYER` 2 正常、3/4/8 全崩 ⇒ 临界值 **3**，而数组长度是 **2** ⇒ **严格对应 ⇒ 因果闭合**。
   - 反面用法：临界值若与结构尺寸对不上（或大很多），说明还有别的因素，**别急着收工**。
   - 旁证：崩溃局一律停在 ait 第 **61** 行（17~21 秒）⇒ 越界时刻高度一致，是"结构性"而非"随机"。
72. ★★★ **崩溃栈里的行号 = 版本指纹**
   - 跨机器/跨平台崩溃，**第一步做行号对齐**，不要急着读代码。
   - 实证：栈里 `tagInfo::operator=` 在 `GlobalVariate.cpp:1013`，本地该函数在 **1072** 行
     （本地 1013 行是 `tagObj::operator<`），**差 59 行** ⇒ **评测机编译的引擎源码与本地不是同一份**。
   - 反向同样有力：`UsrAI.cpp:473` 在本机精确等于 `info = getInfo();` ⇒ 确证"评测机用的就是我提交的这份 UsrAI"。
   - ⇒ **行号吻合的文件 = 版本可信；行号不吻合的文件 = 结论不可外推**。
73. ★★★ **先看崩溃读到的地址"是什么性质"，再决定查什么**
   - 把操作按"会不会 free"分类：`insert`（分配新节点）、`= NULL`、`clear()`（不释放 capacity）**都不 free**
     ⇒ **不产生 unmapped 地址**。
   - 因此：**凡崩溃源是"不可访问"（unmapped）地址，破坏者必然是 `free`/`delete`/`munmap`**。
   - 据此一刀排除"无锁容器竞争"类假说：`g_Object` 虽是无锁全局 map（`GlobalVariate.h:30`），
     但写方只 `insert` 不 free ⇒ 顶多读到结构不一致，**不可能产生 unmapped** ⇒ 不是本案崩因。
   - ⇒ **分诊第一个问题**："这块地址是已释放页，还是有效页上的脏数据？"
""")
save(t, p)
print("detail_laws.md OK  lines=%d" % t.count("\n"))

# ---------------- detail_state.md ----------------
t, p = load("detail_state.md")
t = t.rstrip("\r\n") + crlf("""


## §Z 第 6 轮：站内可能性穷尽 ＋ 配置扫描临界值确认 ＋ 版本指纹（2026-09-19 深夜）

> 前提：用户拍板「评测机接受 `UsrAI.cpp` 和 `UsrAI.h`」。本轮只解决一个问题：**站内能不能修**。

### Z.1 结论
**站内不能修。** 不是"试了不行"，而是**通道不存在**。站外两行可修（见 Z.6）。

### Z.2 站内的四堵墙（逐条实证）
| # | 墙 | 位置 | 依据 |
|---|---|---|---|
| 1 | 拿不到快照本体 | `GlobalVariate.h:250-252` | `tagInfo* Info` 与 `QMutex Locker` 都是 `private` |
| 2 | 唯一读口无钩子 | `GlobalVariate.cpp:1155-1158` | `QMutexLocker locker(&Locker); return *Info;` 深拷贝内联，插不进检查 |
| 3 | 不能"先锁后读" | `GlobalVariate.cpp:1140-1163` | `tryLock/release/getInfo/insertInsRet` **共用同一把 `Locker`** 且 `QMutex` 非递归 ⇒ 同线程二次加锁**死锁** |
| 4 | 信号兜底不可取 | — | 崩在锁内会跳过 `QMutexLocker` 析构 ⇒ **永久持锁、引擎卡死（比崩溃更糟）**；MinGW 的 POSIX signal 是模拟的、gcc13 是真的 ⇒ **本机验证零预测价值** |

### Z.3 三次否证（最终定论）
| 假说 | 结论 |
|---|---|
| 写侧 `clear()` 释放 AI 正读的内存 | 否 —— `tagInfo::clear()` 不释放 capacity |
| `tagGame::update()` 锁被注释 ⇒ 竞争 | 否 —— 唯一调用方 `infoShare()` 已在锁内，那把锁冗余；恢复它反而同线程二次加锁 |
| **本轮复核：`tryLock()` 与 `getInfo()` 是否同一把锁** | **是**（`GlobalVariate.cpp:1140-1163`）⇒ 写侧双锁内（`MainWidget.cpp:2259-2273`）+ 读侧同锁 ⇒ **读写互斥，竞争不存在** |
| `g_Object` 无锁全局 map 的跨线程访问 | **降级**：`insert`/`=NULL` **都不 free** ⇒ 不产生 unmapped ⇒ 无法解释崩溃；且 UsrAI 全文无 `isHuman/isBuilding` 调用 |
| AI 发非法参数 ⇒ 引擎越界写 | 否 —— 三出口全有边界校验（`Core.cpp:1380`/`1392`/`1437`/`1443`） |
| `taginfo->theMap` 悬垂 | 否 —— `playerMap` 是 `Core` 成员（`Core.h:15`/`Core.cpp:18`）；`data` 是 `static Data*`（`Core.cpp:651`） |
| `tagInfo` 析构 delete 了什么 | 否 —— 全文无 `~tagInfo`；`theMap` 浅拷贝且无人 delete |

### Z.4 配置扫描：临界值确认
| `NOWPLAYER` | 结果 |
|---|---|
| 2（工程默认） | 正常跑满（`oj1` 胜 f=43293／`oj2` 负 f=25677／`rec1` 负 f=44044） |
| **3** | **SIGSEGV，17 秒，`np3.ait` 61 行** |
| 4 | SIGSEGV，19 秒，61 行 |
| 8 | SIGSEGV，21 秒，61 行 |

⇒ **临界值 3 与数组长度 2 严格对应 ⇒ 因果闭合**（铁律 71）。

### Z.5 版本指纹（本轮新发现，影响可外推性）
`tagInfo::operator=` 在栈里位于 `GlobalVariate.cpp:1013`，本地在 **1072**（相差 **59** 行）
⇒ **评测机引擎源码 ≠ 本地**。而 `UsrAI.cpp:473` 精确吻合 ⇒ 提交的 UsrAI 与评测机一致。
⇒ 引擎侧结论必须先用评测机源码对齐版本。

### Z.6 站外修法（两行，任选一）
- **A（推荐）**：`Core.cpp:7-8` → `tagInfo Buffer0[MAXPLAYER]; tagInfo Buffer1[MAXPLAYER];`
- **B（最小）**：`Core.cpp:681/684/687` → `for (int i = 0; i < NOWPLAYER && i < 2; i++)`
- **C（防御性）**：`Core.cpp:1355` 补 `self == NULL`（`self` 是构造期快照，判空却在消费期重查）

### Z.7 交付与待用户
- 交付：`aoe3_crash_20260919_r6.html`（技术报告）＋ **`aoe3_oj_defect_report.md`（可直接转发评测方）**。
- 待用户：① 评测机 `config.json` 的 `NOWPLAYER`（**≥3 ⇒ 就是本缺陷**）；② 评测机引擎源码（对齐 59 行差异）。
- 若 `NOWPLAYER == 2` ⇒ 排除本缺陷，转 ASan（gcc13）。
""")
save(t, p)
print("detail_state.md OK  lines=%d" % t.count("\n"))

# ---------------- daily log ----------------
t, p = load("2026-09-19.md")
t = t.rstrip("\r\n") + crlf("""

## 第 6 轮（深夜续）：站内可修性判定 —— 不能；配置临界值确认；版本指纹
- **问题**：用户问「能修复吗」（前提：评测机只收 `UsrAI.cpp`/`UsrAI.h`）。
- **答**：站内**不能**（四堵墙，见 `detail_state.md` §Z.2）；站外**两行可修**。
- ★★ **最终否证"数据竞争"**：`tryLock/release/getInfo/insertInsRet` **同一把 `Locker`**（`GlobalVariate.cpp:1140-1163`）
  ＋ 写侧双锁内（`MainWidget.cpp:2259-2273`）⇒ **读写互斥** ⇒ 该假说**第三次、最终出局**。
- 其余排除：`g_Object` 无锁 map（`insert`/`=NULL` **不 free** ⇒ 不产生 unmapped ⇒ 不能解释崩溃）｜
  指令三出口**全有边界校验** ⇒ "AI 乱发参数"否｜`playerMap` 是 `Core` 成员（非局部）｜`tagInfo` 无自定义析构。
- ★★★ **配置扫描临界值**：`NOWPLAYER` **2 正常 / 3（17s）、4（19s）、8（21s）全崩、ait 均 61 行**
  ⇒ **临界值 3 与数组长 2 严格对应 ⇒ 因果闭合**（新铁律 71）。
- ★★★ **版本指纹**：栈里 `tagInfo::operator=` = `GlobalVariate.cpp:1013`、本地 **1072**（**差 59 行**）
  ⇒ **评测机引擎源码 ≠ 本地**；`UsrAI.cpp:473` 精确吻合（新铁律 72）。
- **未改代码**：`UsrAI.cpp`/`UsrAI.h` 原样；引擎保持原始；`config.json` **逐字节还原**（`cmp` 通过，备份 `config.json.bak_np3`）。
- **产出**：`aoe3_crash_20260919_r6.html`｜**`aoe3_oj_defect_report.md`（可转发评测方）**｜新铁律 71~73｜`np3.ait`。
- **待用户**：① 评测机 `config.json` 的 `NOWPLAYER`；② 评测机引擎源码（对齐 59 行差异）。
""")
save(t, p)
print("2026-09-19.md OK  lines=%d" % t.count("\n"))
print("ALL DONE")
