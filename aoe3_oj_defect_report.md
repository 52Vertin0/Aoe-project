# AoE3 评测平台缺陷报告

> 可直接转发给评测方。含最小复现、根因、两行修法、影响面。

## 一、一句话

`Core::infoShare()` 用**运行时配置** `NOWPLAYER` 作为**固定长度编译期数组** `Buffer0[2]` / `Buffer1[2]` 的上界。当 `config.json` 的 `NOWPLAYER ≥ 3` 时，每帧必定越界写，**砸坏紧随其后的全局指针 `tagInfo* currentBuff`**，随后选手 AI 线程在读取快照时收到 SIGSEGV。

**这是平台工程自身既存缺陷，与选手提交的 `UsrAI.cpp` / `UsrAI.h` 无关。**

---

# ★ 2026-09-29 勘误与新增（**请先读这一节**）

拿到第 5 次崩溃的完整 backtrace 后，在**与评测机同源的引擎**（本仓库 `v3.0.7h`，其 `Core.cpp`
仍是 `Buffer0[2]`）上做了单变量 A/B —— **只改 `config.json` 的 `NOWPLAYER`**，同 exe、同图、同参数（`map2` × 3 局，`-exam -offscreen -freq MAX`）：

| 臂 | `NOWPLAYER` | 结果 |
|---|---|---|
| A（对照） | 2 | 3/3 `exit=0`，跑满 f=35623 / 43583 / 45000 |
| B | 3 | **3/3 SIGSEGV（`exit=139`），jsonl 仅 86 B、末帧 = 1** |

**物理含义**：`NOWPLAYER ≥ 3` 的越界发生在**第 1~2 帧的主线程**（`infoShare()` 内），进程在 `frame=1` 就死；
而选手 AI 线程要 `g_frame > 10` 才进入 `processData()`。

⇒ **第 5 次崩溃的栈（AI 线程已跑到 `UsrAI::processFrame`）与"`NOWPLAYER ≥ 3` + `Buffer0[2]` 越界"不相容。**
⇒ 评测机 `NOWPLAYER` 的实际取值**应为 2**（或 `Core.cpp` 已被修过），上述"一、一句话"的推断**在本次崩溃上不成立**。
⇒ **第五节的 `Buffer0[MAXPLAYER]` 修法仍建议采纳**（预防性：`NOWPLAYER` 是运行期值而 `MAXPLAYER=8`），但它**不是**本次崩溃的原因。
⇒ **本节以下内容请按"已排除的假设 + 预防性建议"阅读；本次崩溃的第一嫌疑见下节。**

---

# ★ 2026-09-29 新增：本次崩溃的第一嫌疑 —— `g_Object` 无锁并发**结构性写**

## A. 事实（行号均按评测机同源版本 `v3.0.7h` 核过）

`g_Object` 是全局 `std::map<int, Coordinate*>`（定义：`MainWidget.cpp:35`），**全工程零锁**。

**AI 线程侧的写操作**只有一处，但每帧都在发生 —— `instruction` 的**四个构造函数都做 `g_Object[SN]`**：

```cpp
// GlobalVariate.cpp（v3.0.7h）
instruction::instruction(int type,int SN,int obSN,bool){  // 535 / 536
    this->self=g_Object[SN];   this->obj=g_Object[obSN]; }
instruction::instruction(int type,int SN,int BL,int BU,int option){  // 541 → HumanBuild
    this->self=g_Object[SN]; }
instruction::instruction(int type,int SN,Double L,Double U){          // 549 → HumanMove / PinPointStrike
    this->self=g_Object[SN]; }
instruction::instruction(int type,int SN,int option){                 // 556 → BuildingAction
    this->self=g_Object[SN]; }
// 另有 600/601 在 instruction::Serialize() 的读分支里，只在回放/读档时走
```

`std::map::operator[]` 在 key 不存在时**插入节点并旋转红黑树** —— 这是**结构性写**，不是读。
调用者全在 **AI 线程**：`enemyai.cpp` 有 **36 处**直调 `HumanMove(...)/HumanAction(...)`
（另 1 处 `instruction(INS_CANCEL, …)`）。选手侧 `UsrAI.cpp` 这半边已由选手自行消除
（隐藏 5 个非虚入口 + `find()` 只读预检），**但引擎侧 `enemyai.cpp` 的调用存在，A/B 实测无法从选手侧关掉**。

**同时主线程在改同一棵树**：
- 单位进场 `insert`：`Army.cpp:75/118`、`Farmer.cpp:61`、`Building.cpp:55`、`Animal.cpp:51`
- 单位阵亡 / 清除：`g_Object[SN] = NULL`：`Core.cpp:143 / 264 / 347 / 382 / 417`
- 另有 `Core.cpp:443 / 514` 用 `operator[]` 取值（同为写语义）

## B. 结论：这是**按 C++ 标准即可判定**的 UB，不依赖复现

两个线程（主线程 + `EnemyAI` 线程）无任何同步地修改同一个 `std::map`，其中一个做插入/旋转 ——
按标准即 UB。后果是节点与指针被写坏，**崩溃点随机落在之后任一次堆访问上**：

| 崩次 | 崩点 | 形态 |
|---|---|---|
| 第 1 次 | `UsrAI::processData`（`tagInfo::operator=` → `__memcpy`） | 深拷贝源被写坏 |
| 第 2 次 | `UsrAI::refreshSnapshot`（`dst = *fresh`） | 同上，换了源 |
| 第 3 次 | `UsrAI::processData` → `shared_ptr::get()` | 指针成员被写坏 |
| 第 4 次 | `UsrAI::processFrame`（`frame = infoPtr->GameFrame;`） | 同上 |
| 第 5 次 | `UsrAI::processFrame`（同一句） | 同上 |

⇒ 5 次崩点各不相同，**却全落在"堆访问"上** ⇒ 是内存被踩，不是逻辑漏判。

评测机编译的是 **Debug（`-O0 -g`）**：`std::map` 操作不再内联、读-改-写窗口远大于 `-O2`
—— 这与"评测机 5/5 必崩、选手本机（Windows/MinGW，Release 与 Debug）100+ 局均未复现"的现象一致。

## C. 建议修法（5 行，语义等价）

把上面 5 处构造里的 `g_Object[SN]` / `g_Object[obSN]` 换成**只读查找**：

```cpp
// GlobalVariate.cpp（或任一公共头）
static inline Coordinate* g_ObjectRO(int sn) {
    auto it = g_Object.find(sn);                       // find：不存在时不插入、不旋转
    return it == g_Object.end() ? nullptr : it->second;
}
// 四个构造函数：g_Object[SN] → g_ObjectRO(SN) ；g_Object[obSN] → g_ObjectRO(obSN)
```

**语义等价性**：构造里取的是"构造那一刻"的对象指针，只是给 `instruction.self/obj` 一个快照；
消费侧 `Core::updateByObject`（`Core.cpp:1398`）本来就会**再查一次** `g_Object[cur.SN] == NULL`。
改成 `find` 后 AI 线程**不再插入、不再旋转红黑树** ⇒ 树结构只由主线程单方修改 ⇒ 该竞态消失。

## D. 对选手侧的意义

选手能改的只有 `UsrAI.cpp` / `UsrAI.h`，**关不掉 `enemyai.cpp` 的调用** ——
因此这条根因**必须由引擎侧修**。选手侧此前做的等价改动（`find()` 只读预检）只覆盖了一半写者。

## 二、崩溃现场（选手侧表象）

```
Thread 5 "AI" received signal SIGSEGV
#0 __memcpy_avx_unaligned_erms
#5 std::copy<..., tagBuilding>          (/usr/include/c++/13/bits/stl_algobase.h:633)
#6 std::vector<tagBuilding>::operator=   (__x = vector of length 6, capacity 6)
#7 tagInfo::operator=                    (GlobalVariate.cpp:1013)
#8 UsrAI::processData                    (UsrAI.cpp:473)     ← info = getInfo();
#9 AI::run                               (AI.cpp:62)
```

注意：**崩在"受害者"身上**（一次普通深拷贝），不是崩在破坏点。同一份日志里主线程最后一帧的位置每次都不同（`SelectWidget::drawActs` / `Core::updateByObject`），也印证这一点。

## 三、最小复现（单变量，同一份二进制）

> ⚠ **定位说明（2026-09-29 补）**：本节复现的是 `Buffer0[2]` **这个缺陷本身**（它确实是真缺陷、可复现），
> 但**它不是第 5 次崩溃的原因**（见上方勘误）。此处保留复现步骤，是为了让平台方**独立验证该缺陷存在**，
> 而不是为了指认本次崩溃。

```bash
cd <工程根>
cp -p config.json config.json.bak

# 只改一个值：NOWPLAYER
python3 - <<'EOF'
import re
p='config.json'
t=open(p,'rb').read().decode('utf-8')
t2=re.sub(r'"NOWPLAYER":\s*2', '"NOWPLAYER": 3', t, count=1)
assert t2!=t
open(p,'wb').write(t2.encode('utf-8'))
EOF

QT_QPA_PLATFORM=offscreen ./release/newAOE.exe -exam -offscreen -freq MAX \
  -map map3.njust -rotate 90 -ResultLogFile r.jsonl -AITextLog r.ait
echo "exit=$?"        # 139 = SIGSEGV

mv config.json.bak config.json
```

### 实测结果（Windows/MinGW 构建，同一份 exe）

| `NOWPLAYER` | 结果 |
|---|---|
| **2**（工程默认） | 正常跑满（多局均可分胜负，最长 f=44044） |
| **3** | **SIGSEGV，约 17 秒，`-AITextLog` 仅写入 61 行** |
| **4** | **SIGSEGV，约 19 秒，61 行** |
| **8** | **SIGSEGV，约 21 秒，61 行** |

**临界值 3 与数组长度 2 严格对应。**

## 四、上面这个缺陷的作用机理（**非本次崩溃原因**）

> 命名为"机理"而非"根因"：它是 `Buffer0[2]` 缺陷自身的机理（**已证可复现**），但对第 5 次崩溃而言是**已排除的假设**。

```cpp
// Core.cpp:7-10 —— 连续定义的全局
tagInfo Buffer0[2];
tagInfo Buffer1[2];          // &Buffer0[2] == &Buffer1[0]
int     buff;
tagInfo* currentBuff;        // ← 紧随 Buffer1 之后，越界第一个撞到的就是它

// Core.cpp:680-689
currentBuff = (buff == 0) ? Buffer0 : Buffer1;
for (int i = 0; i < NOWPLAYER; i++) currentBuff[i].clear();
for (int i = 0; i < NOWPLAYER; i++) updateByPlayer(i);
for (int i = 0; i < NOWPLAYER; i++) updateCommon(&currentBuff[i], i);

// Core.cpp:720-723
tagUsrGame.update(&currentBuff[0]);
tagEnemyGame.update(&currentBuff[1]);
buff ^= 1;                   // ← 每帧交替，两组缓冲区轮换
```

`NOWPLAYER` 由 `RuntimeConfig_NOWPLAYER()` 在运行时从 `config.json` 读取，**全链路无范围钳制**（`MAXPLAYER` = 8）。

- `buff == 0` 帧：`currentBuff[2]` = `Buffer1[0]` —— 假性合法，把**敌方快照**当己方 buffer 反复 `clear()` + 重填，**静默污染**
- `buff == 1` 帧：`currentBuff[2]` = `Buffer1[2]` —— **真越界，且砸的正是 `tagInfo* currentBuff` 本身**

`buff ^= 1` 每帧翻转 ⇒ **`NOWPLAYER ≥ 3` 时每隔一帧必踩一次**。`currentBuff` 一旦变垃圾：

```cpp
tagUsrGame.update(&currentBuff[0]);   // Info = 垃圾指针
// 之后选手侧：
tagInfo tagGame::getInfo() { QMutexLocker locker(&Locker); return *Info; }   // 从垃圾地址深拷贝 ⇒ SIGSEGV
```

## 五、建议修法

**方案 A（推荐，改 2 行）**

```cpp
// Core.cpp:7-8
tagInfo Buffer0[MAXPLAYER];
tagInfo Buffer1[MAXPLAYER];
```

`MAXPLAYER` 是既有常量（8），`MainWidget.cpp:1476` 已用 `new Player*[MAXPLAYER]`。改后 `NOWPLAYER ∈ [0, MAXPLAYER]` 全程合法。

**方案 B（最小改动，3 处循环加界）**

```cpp
for (int i = 0; i < NOWPLAYER && i < 2; i++)
```

只保证不越界；代价是 `NOWPLAYER > 2` 时第 3 名及以后的玩家拿不到快照（功能缺失，但不崩）。

**方案 C（防御性，建议与 A 同修）**

```cpp
// Core.cpp:1355 —— self 是"构造指令那一刻"的快照，判空却在消费时重新查 g_Object，
// 两者时刻不同，短路保护可能失效
if (g_Object[cur.SN] == NULL || self == NULL || self->getPlayerRepresent() != id)
```

## 六、影响面

- **触发条件**：仅取决于 `config.json` 的 `NOWPLAYER`。`== 2` 不触发；`≥ 3` 必崩。
- **若不修且评测机 `NOWPLAYER ≥ 3`**：任何选手的提交都会崩，**与 AI 策略无关**（把 `UsrAI.cpp` 换成空实现也一样崩）。
- **另一处伴随问题**：即使通过其它方式避开越界，`NOWPLAYER ≥ 3` 时 `buff==0` 帧会把敌方快照当己方 buffer 清空重填，**污染的是对手 AI 读到的数据**，会造成难以理解的行为差异。

## 七、请协助确认的两项

1. 评测机 `config.json` 中 `NOWPLAYER` 的实际取值。
2. 评测机 `GlobalVariate.cpp` 的版本——见下。

> **版本对齐提示（2026-09-29 更正）**：崩溃栈中 `tagInfo::operator=` 位于 `GlobalVariate.cpp:1013`。
> 经逐行核对：**`v3.0.7h` 的 `tagInfo::operator=` 起始于第 1011 行** ⇒ 评测机栈 = **7h + 2 行**。
> 该偏移在多个独立文件上自洽可验：
>
> | 评测机栈 | 7h 对应行 | 7h 该行内容 | 偏移 |
> |---|---|---|---|
> | `GlobalVariate.cpp:1013` | 1011 | `tagInfo &tagInfo::operator=(const tagInfo &)` | +2 |
> | `AI.cpp:64` | 62 | `processData();` | +2 |
> | `MainWidget.cpp:2267` | 2265 | `emit startAI();` | +2 |
> | `MainWidget.cpp:2261` | 2259 | `core->infoShare();` | +2 |
> | `Core_List.cpp:848` / `Core_CondiFic.h:127` | 848 / 127 | 逐字一致 | 0 |
>
> ⇒ **评测机引擎与 `v3.0.7h` 同源**（`MainWidget.cpp`／`AI.cpp`／`GlobalVariate.cpp` 各多 2 行；
> `Core_List.cpp`／`Core_CondiFic.h` 与本仓库完全一致），**不是** `v3.0.7g`
> （7g 的同名符号分别在第 2269／62／1072 行，对不上）。
> ⇒ 定位具体行号请以 **`v3.0.7h` 减去 2** 为准；第五节的改动本身不受版本影响。

## 八、附：另两处可疑点（供参考）

> ⚠ **2026-09-29 更新**：本节第 1 条已被上方「★ 新增：第一嫌疑 —— `g_Object` 无锁并发结构性写」一节**取代**——
> 那里给出了 7h 行号（535/536/541/549/556）、完整写者集合与 5 行修法，**并已升级为本次崩溃的第一嫌疑**。
> 本节第 1 条的旧判断（"`insert` 不释放旧节点 ⇒ 不产生 unmapped 地址"）只覆盖了"节点被 `free`"这一种踩法，
> **未覆盖"红黑树旋转期间被另一方读到/改到"** —— 后者不需要 `free` 就能产生野值。以此为准。

1. `g_Object` 是**无锁全局** `std::map<int, Coordinate*>`，被 AI 线程（`instruction` 构造函数的 `operator[]`）
   与主线程（对象构造 `insert`、死亡 `g_Object[SN]=NULL`、`Core.cpp:1617` 全表遍历）并发访问 —— 属未定义行为（详见上方专节）。
2. `Core.cpp:143/264/347/382/417` 用 `g_Object[SN] = NULL` 标记死亡（不 `erase`），键永久累积；若长期运行需评估内存增长。
