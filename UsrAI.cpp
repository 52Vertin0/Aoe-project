#include "UsrAI.h"
#include <unordered_set>

tagGame tagUsrGame;
ins UsrIns;
/*##########DO NOT MODIFY THE CODE ABOVE##########*/

// 波次时间（帧）- 来自任务文档
#define WAVE1_TIME 5000
#define WAVE2_TIME 13500
#define WAVE3_TIME 21000

// ★★★ 完整版：PPT策略——房→市→兵营→靶场→马厩→箭塔 ★★★
#define MAX_FARMERS 22          // 目标村民数量（PPT建议20-28）
#define MAX_HOUSES 10           // PPT：50人口=10房
#define POP_HEADROOM_BUILD 2    // 人口余量≤此值即补房屋（即 人口达到 人口上限-2 时建房）
// ★ 农场上限：2026-09-01 二改 8 → 12。
//   后期野生食物枯竭后，食物产能 = 农场座数 × 1人/座（代码强制"每座农场有且仅有一人"），
//   8 座 = 8 个食物工，成为造兵瓶颈（食物不够 → 兵造不出 → 黄金只进不出 → 黄金过量）。
//   农场间隔 1 格（isFarmAdjacent）仍需选址空间，若实测建不满 12 座可调回 10。
#define MAX_FARMS 7             // 农场上限：最多7座（2026-09-04 用户要求 6→7）
// ★ 建农场时为【瞪羚中心仓库】预留的木头（2026-09-06 用户要求「建造瞪羚的仓库前先不要建农场，预留120木头」）。
//   判据用 info.Wood >= BUILD_FARM_WOOD + WOOD_RESERVE_FOR_GAZELLE_STOCK，
//   即"造完农场后仍留得住 120 木"，保证瞪羚仓库(BUILD_STOCK_WOOD)永远有料可建。
//   ★ 背景：旧代码 postW2 的农场块(见下方)只有 Wood>=75 且【无瞪羚仓库闸】，而瞪羚仓库窗口是 frame<16500
//     (11分钟)、postW2 从 13500(9分钟) 就开始了 ⇒ 9~11 分钟两者并存，农场抢光木材 → 仓库永远建不出。
#define WOOD_RESERVE_FOR_GAZELLE_STOCK 120
// ★ 农场木材判据（2026-09-06 用户定案「建完农场后不用预留木材了」）：
//   预留 120 木头【只】在瞪羚仓库还没建成时有意义（那 120 是留给仓库的）；
//   一旦仓库已建成(storageNearGazelleBuilt==1)，农场就恢复原阈值 BUILD_FARM_WOOD，不再多留。
//   ★ 为什么必须这样：农场建造点本身就带 storageNearGazelleBuilt==1 闸，若无条件 +120，
//     农场门槛会永久抬高到 75+120=195 木，导致仓库建好后农场严重滞后（实测会晚很多）。
#define FARM_WOOD_NEED(gazelleStockBuilt) \
    ((gazelleStockBuilt) ? BUILD_FARM_WOOD : (BUILD_FARM_WOOD + WOOD_RESERVE_FOR_GAZELLE_STOCK))
// ★ 打猎瞪羚选取范围（2026-09-04 用户要求"扩大一些"）：30→50 格，覆盖远距未建仓库的瞪羚群。
//   仓库覆盖判断（1547/1705 nearStock）也用此常量同步，避免猎人跑出去 50 格打、仓库仍卡 30 格内。
#define GAZELLE_HUNT_RANGE  50
// ★ 组队猎象（2026-09-03 用户需求）：大象血45/攻10/射程10/不逃跑/掉肉300，性价比远超瞪羚(血8会逃跑)。
//   单挑村民(血25)必死，须凑够 ELEPHANT_HUNT_GROUP 人围猎快速击杀。每头象最多派此人数，集中火力不分散。
#define ELEPHANT_HUNT_GROUP 5
#define MAX_TOWERS 2            // 箭塔数量（2026-09-03 用户改需求：只需2座箭塔，多采150石建第2座，其余人力转食物）
#define MAX_RANGES 3            // 反攻阶段靶场上限(并行产弓线，越多弓兵越快)
#define MAX_STOCK 2             // 仓库上限：1座给瞪羚群中心 + 1座给远距瞪羚群，共2座
                                  // ★ 2026-09-04 实测补：此前缺此上限，旧"第二仓库"段（1676）每帧重发令+不传坐标，
                                  //   导致贴 TC 多建 3 座仓库（地图多群远距瞪羚就触发多次）
// ★ 不训练棍棒兵（2026-09-03 用户要求）：棍棒兵改为由箭塔替代防守，省下食物/人口转向箭塔+复合弓。
#define DISABLE_CLUBMAN_TRAIN true
// ★ 建造/地基保护常量
#define DEAD_BUILDING_GRACE 1800  // 废弃地基宽限期(帧,30秒)：拉黑后这段时间内仍算"已存在"，
                                  // 给"孤儿地基抢救"时间补救；超时才允许另择新址重建(避免重复建造)
#define ORPHAN_REDISPATCH_CD 120  // 孤儿地基(在建但无人施工)补派村民的节流间隔(帧)
#define PENDING_BUILD_TIMEOUT 300 // 建造指令结果迟迟不回的超时(帧)：超时则清掉占位，防止永久虚占名额
#define BUILD_GAP 1              // 建筑间距：候选建筑footprint外扩1格内不得有其他建筑(含敌我)，避免建筑成墙堵死路
#define MELEE_OVERFLOW_FOOD 150      // 后期/反攻"爆近战"食物溢出阈值：食物≥此值才大规模造近战兵(棍棒/方阵)
// ★ 反攻期兵种编制（2026-09-02 用户要求）：反攻**只训练 复合弓兵(主) + 方阵兵(副)**，不训练其他兵种。
//   原因：旧逻辑里骑兵(70食+80金)与棍棒兵(50食)会抢占复合弓兵(40食+20金)的资源与人口，
//   骑兵单次吃掉 4 个复合弓兵的黄金 → 复合弓兵判据长期不过 → 退化成普通弓兵/停产。
#define DISABLE_CAVALRY_TRAIN true  // 全局不训练骑兵【主力】(骑兵/战车等)：性价比低且严重挤占复合弓兵黄金
// ★ 远程兵（复合弓兵/普通弓兵）最早训练时间（2026-09-06 用户要求「15min 前先不训练复合弓兵，避免被打死」）。
//   早期造出的弓兵会被敌人打死，白白浪费食物 + 20 黄金 → 资源全留给村民 / 铜器升级 / 复合弓科技。
//   ★ 用户已选「完全停产」：前 15 分钟靶场(BUILDING_RANGE)闲置，连普通弓兵兜底也一并停掉
//     （普通弓射程 5、无复合科技，比复合弓更脆，照样送人头）。
//   注意：只停产【造兵】，不影响靶场建造与复合弓科技研究——靶场闲置反而更利于科技判据(Project==ACT_NULL)。
#define COMPOSITE_BOW_MIN_FRAME 22500   // 15 分钟 × 1500 帧/分钟 = 22500 帧
// ★ 探路先锋（2026-09-03 用户改需求）：不再造侦察骑兵，改派【感化的战车弓兵(优先,SPEED 4.07)或投石车(视野13)】
//   去探路。未探明敌基地时，这些单位快速奔袭敌基地方向 → 探到 enemy_buildings → 点亮 enemyBaseScouted
//   → 大部队直接全图寻路直达，省去逐格摸索。故侦察骑兵训练开关设 false。
#define ENABLE_SCOUT_RECON false
#define COUNTER_ATTACK_MIN_ARMY 20   // ★ 全体反攻门槛：非祭司军队(含远程/近战/投石车)≥此数才一起反攻，避免单个士兵零散冲出被集火
#define COUNTER_ATTACK_FORCE_TIME 36000 // 24分钟强制反攻(=36000帧,1500帧/分钟)：即使人数不足也一起进攻
                                        // （2026-09-04 用户要求：22分钟→24分钟，多留2分钟集结攒兵）
// ★ 祭司护驾三级半径(格)：祭司死=立刻失败，故护驾优先于士兵自卫/守家/前出等一切军事行为
#define PRIEST_GUARD_URGENT 8.0   // 紧急：敌进入祭司此半径 → 所有兵(可打断战斗)立即回防
#define PRIEST_GUARD_ALERT  15.0  // 预警：敌进入祭司此半径 → 空闲/行军兵前往护驾(不打断正在战斗的兵，防反复横跳)
#define PRIEST_GUARD_RECALL 30.0  // 召回上限：只调距祭司此半径内的兵回防(避免把反攻大军从全图拉回)
#define PRIEST_GUARD_MAX_CMDS 12  // 护驾指令每帧上限(独立于普通 attackCmds，保证护驾不被限流饿死)
// ★ 祭司感化目标选取范围(格)：从 20 扩到 28，让祭司更主动地去感化远处的投石车等高价值目标。
//   (投石车射程10格、感化射程14格；28格仍在护驾召回半径 PRIEST_GUARD_RECALL=30 内，不会脱离保护。)
#define PRIEST_CONVERT_RANGE 28.0
// ★★★ 临时封禁开关：改 true→false 即可恢复建造 ★★★
#define DISABLE_STABLE_BUILD  true    // 2026-09-04 用户要求：暂时不建马厩（与 DISABLE_CAVALRY_TRAIN=true 配合：纯步战阵线）
#define DISABLE_COLLAGE_BUILD true    // 2026-09-04 用户要求：暂时不建学院（方阵兵依赖学院 → 反攻期只剩复合弓兵）
#define DISABLE_GRANARY_BUILD false   // 已解封(2026-09-03)：恢复谷仓建造，实现"瞪羚群中间建仓库优先于农场"
// ★ 暂时封禁阔剑科技：引擎解锁条件有 bug——Development.cpp:602-603 把
//   历史上的引擎 bug（黄金被错传进石头槽）已修正：Development.cpp:602-603/607-608 现写为
//   (..._FOOD, 0, ..._GOLD) → 阔剑科技/阔剑兵实际扣 食物+黄金（need_Stone=0）。
//   仍保留封禁（DISABLE_BROADSWORD_TECH）仅因用户此前"暂不研究该科技"决策；引擎条件已正确，可随时改 false 解禁。
#define DISABLE_BROADSWORD_TECH true  // 暂不研究阔剑科技（引擎条件已修正：现真扣 食物+黄金，解禁只需改 false）
// ★ 箭塔只要"解锁"(BUILDING_GRANARY_ARROWTOWER)，不研究"铜器箭塔升级"
//   (BUILDING_GRANARY_ARROWTOWE_UPGRADE，120食物+50石头)——用户要求：解锁即可，不升级。
//   恢复升级：改 false 即可（两处调用点均已用此开关封禁）。
#define DISABLE_TOWER_UPGRADE true
// ★ 2026-09-06 用户定案：只研究 4 项科技 —— 铜器时代 / 箭塔解锁 / 复合弓 / 弓兵护甲，其余全部封禁。
//   三个开关与上方 DISABLE_BROADSWORD_TECH / DISABLE_TOWER_UPGRADE 同风格，单独恢复只需改回 false。
#define DISABLE_USETOOL_TECH true         // 仓库·工具使用（100食物，近战+2）—— 封禁
#define DISABLE_INFANTRY_ARMOR_TECH true  // 仓库·步兵护甲（75食物，近战防御+2）—— 封禁
#define DISABLE_MARKET_TECH true          // 市场全部 5 项经济科技（木材加工/驯养/车轮/犁/工艺）—— 封禁
//   ⚠ 注意：市场【建筑本身】不能停建！1483 行 `marketReady` 是农场建造的前置闸门，
//     停建市场会导致农场永远建不出来。封禁的只是市场里的科技研究。
#define LION_AVOID_RADIUS 10         // 建造选点避开狮子的半径(block)；狮子会攻击靠近的建筑/村民，留缓冲
// ★ 狮子防御（2026-09-01）：引擎事实 Animal.cpp::isMonitorObject —— 狮子只攻击【村民】与【非祭司军队】，
//   不攻击祭司、不攻击建筑；狮子视野 3 格(VISION_LION)、血量 20(BLOOD_LION)，村民单挑必死，须成组出动。
#define LION_THREAT_RADIUS 6    // 狮子距我方任一单位 ≤6 格 → 预警级威胁，派空闲村民猎杀
#define LION_ATTACK_RADIUS 2    // 我方单位已受伤且狮子 ≤2 格 → 判定"正在被咬"，紧急级(可打断采集/赶路)
#define LION_HUNTER_GROUP 4     // 每只威胁狮的猎手目标人数（狮子20血，2个村民打不完还会送命）
#define LION_HUNTER_RANGE 22    // 只派距狮 ≤22 格的村民，避免全图奔波、经济被抽空
#define LION_ARMY_RANGE  4      // 空闲军队距狮 ≤4 格才派（军队战力高，就近秒狮，不抽调远处部队）
#define LION_TASK_FRAMES 300    // 猎狮任务保底时长(帧)：期间不重复下令、不被采集模块抢走(10秒)
#define MIN_GOLD_WORKERS 1      // 至少1人挖金！复合弓兵/阔剑兵/方阵兵/投石车/后勤科技真扣黄金
// ★ 资源停采上限（2026-09-01）：存量达到即停止派/补采该资源，人力转向其他资源
#define STONE_CAP_STOP 150   // 石头≥150 不再采石（2026-09-03：只需2座箭塔=开局150石建第1座+额外采150石建第2座，故上限150）
// ★ 2026-09-03 用户需求："木头维持150左右、优先食物"。木头是"够用就行"的资源：
//   日常水位 150（够房屋30/谷仓120/兵营125/靶场150/马厩150/市场150/农场75），省下人力全投食物。
//   但后期有高木头门槛：反攻多靶场(WAVE3_TIME后 Wood≥230)、学院(反攻期 Wood≥210)，
//   故 WAVE3_TIME 后临时放宽到 250，避免这些关键建筑被 150 水位卡死、永远建不了。
#define WOOD_CAP_STOP  150   // 木头≥150 日常停采（够绝大多数建筑）
#define WOOD_CAP_STOP_LATE 250 // 反攻准备期(WAVE3_TIME后)木头水位：覆盖多靶场230/学院210
#define WOOD_KEEP_MIN  2     // 木头达上限回撤时保留的伐木工人数
#define GOLD_CAP_STOP  400   // ★ 黄金≥400 不再派金工（只留 MIN_GOLD_WORKERS 保底），人力还给食物/木头
#define FOOD_CAP_STOP  500   // ★ 铜器后：食物≥500 不再派新食物工（食物偏多时人力转去伐木）
#define FOOD_CAP_STOP_PREBRONZE 850 // ★ 铜器前：食物停采阈值提到 850(>800升级费)，否则食物到500就停采、永远攒不够800升铜器
#define WOOD_LOW_LINE  100   // 木头<100 判定"缺木"，临时提高伐木工目标
#define WOOD_TARGET_BASE 4   // 常态伐木工目标人数（优先食物，木头只保底）
#define WOOD_TARGET_LOW  8   // 缺木(<WOOD_LOW_LINE)时的伐木工目标人数
// ★ 2026-09-06 砍树选树：树到最近已建成仓库/TC 的距离上限（单位=地图区块 BLOCK）。
//   超过此距离的树一律不派工（宁可让村民干等/转采别的），避免长距离搬运拖垮伐木效率。
//   若实测"附近树砍光后全员闲置"，适当上调；若仍嫌远，下调到 10。
#define WOOD_MAX_ANCHOR_DIST 15
// ★ 选树评分权重：score = (α·村民→树 + β·树→最近仓库/TC) × 拥挤惩罚
//   β > α → 锚点距离主导（砍树成本主要在"树↔仓库"的往返搬运，而非村民走过去）。
#define WOOD_SCORE_ALPHA 0.5   // 村民→树 权重（保留约束：避免村民横穿半张地图去砍一棵"离仓库近"的树）
#define WOOD_SCORE_BETA  1.0   // 树→最近仓库/TC 权重（主导项）
#define WOOD_MAX_WORKERS_PER_TREE 2   // 单棵树同帧累计工人数上限
#define GOLD_RICH_TOL   1.25 // 黄金相对 5:3 目标配比的宽容系数：超出 1.25 倍即判定"黄金相对过剩"
// ★ 食物:黄金 目标配比 = 复合弓兵(40食+20金) 与 方阵兵(60食+40金) 成本综合 = 100:60 = 5:3
//   即 食物工数 : 黄金工数 ≈ 5 : 3（黄金工目标 = 食物工数 * 3/5，向上取整）
#define FOOD_GOLD_NUM 5
#define FOOD_GOLD_DEN 3
// ★ 石头保底采集（仅在不达停采上限时生效）：石头现仅用于
//   箭塔(150)/投石兵(10)/铜器箭塔升级(50)/采石科技(50)/建筑维修。
//   2026-09-03 用户改需求"只需再采150石建2座箭塔"：4→1 人，1人采够150石即可，其余人力全转食物。
#define STONE_WORKERS_LATE 1    // 后期保底采石人数（只需1人采够150石建第2座箭塔）
#define FOOD_PAUSE_TECH_TRAIN 60 // 食物<60暂停科技/训练
#define STUCK_GATHER_TIMEOUT 1500     // 空手且非空闲超时(帧)→判定寻路卡死(60秒)
#define STUCK_BLACKLIST_FRAMES 15000  // 不可达资源拉黑时长(10分钟,到期可重试)
// ============================================================
// processData - 主循环（每帧调用）
// 规则：祭司保命 > 失败检查 > 阶段切换 > 打猎 > 经济 > 军事 > 反攻
// ============================================================
void UsrAI::processData() {
    info = getInfo();
    frame = info.GameFrame;

    // 0. 处理上一帧建造指令结果：失败则释放建造者并换位置重试
    handleBuildResults();

    // 1. 失败检查（第一时间检查）
    checkDefeat();
    if (state == VICTORY || state == DEFEAT) return;

    // 2. 初始化关键 SN
    if (townCenterSN == -1) {
        for (auto &b : info.buildings) {
            if (b.Type == BUILDING_CENTER) { townCenterSN = b.SN; break; }
        }
    }
    if (priestSN == -1) {
        for (auto &a : info.armies) {
            if (a.Sort == AT_PRIEST) { priestSN = a.SN; break; }
        }
    }
    if (state == INIT) {
        if (townCenterSN != -1 && priestSN != -1) {
            state = EARLY_ECONOMY;
            DebugText("AI started — Tool Age. Target: Bronze Age + survive 3 waves.");
        }
        return;
    }

    // ---- 每帧更新祭司SN（防止祭司被重新编号） ----
    {
        bool found = false;
        for (auto &a : info.armies) {
            if (a.Sort == AT_PRIEST) { priestSN = a.SN; found = true; break; }
        }
        if (!found) priestSN = -1;
    }

    // ★ 战/反攻期间强制结束探路：探路模块只在 !isWar && state != COUNTERATTACK 时驱动祭司，
    //   而 managePriest 又要求 scoutPhase>=20 才运行 → 开战时若探路未完，祭司两头都不管，
    //   被敌人贴脸也一动不动（表现为"敌人来了祭司也不跑"）。开战即结束探路，交还祭司管理保命。
    {
        bool isWarNow = (state >= DEFENSE_WAVE1 && state <= DEFENSE_WAVE3);
        if ((isWarNow || state == COUNTERATTACK) && scoutPhase < 20) {
            scoutPhase = 20;
            scoutReturnTry = 0;
            scoutWalkTimer = 0;
            scoutIssueFrame = -999999;
        }
    }

    // 3. 祭司保命（最高优先级，每帧都要检查！）
    managePriest();

    // 4. 递减冷却
    if (buildCooldown > 0) buildCooldown--;
    if (techCooldown  > 0) techCooldown--;
    if (trainCooldown > 0) trainCooldown--;

    // 5. 阶段切换
    updateState();

    manageCarriedResources();

    manageFirstWaveDefense();

    // 6. 打猎管理（必须在经济管理之前！否则空闲农民已被分配完）
    manageHunting();

    // 6.2 ★ 狮子防御：有狮子逼近/正在咬我方单位时立刻派人猎杀（优先于常规采集分配）
    manageLionDefense();

    // 6.5 检测寻路卡死的采集村民（先拉黑不可达资源再分配，避免反复派去）
    detectStuckGatherers();

    // 7. 经济管理（始终运行）
    manageEconomy();

    // 8. 军事管理（始终运行）
    manageMilitary();

    // 9. 反攻
    if (state == COUNTERATTACK) {
        manageCounterAttack();
    }

    // 10. 调试输出
    doDebugOutput();
}

// ============================================================
// 阶段切换（改进版：更稳健的状态转换）
// ============================================================
void UsrAI::updateState() {
    switch (state) {
    case EARLY_ECONOMY: {
        // ★ 食物够800立刻升铜器（一满足条件就升级，无建筑前置）
        if (info.Meat >= BUILDING_CENTER_UPGRADE_BRONZEAGE_FOOD) {
            auto tc = findBuilding(BUILDING_CENTER);
            if (tc && tc->Project == ACT_NULL) {
                BuildingAction(tc->SN, BUILDING_CENTER_UPGRADE);
                hasUpgraded = true;
                state = UPGRADING;
                DebugText(QString(">> Upgrading to Bronze Age! Frame=%1, Meat=%2, Farmers=%3")
                    .arg(frame).arg((int)info.Meat).arg((int)info.farmers.size()));
            }
        }
        // 超时保护：frame > WAVE1_TIME → 进入第一波防御准备
        if (frame > WAVE1_TIME && state == EARLY_ECONOMY) {
            state = DEFENSE_PREP;
            DebugText("!! Force DEFENSE_PREP (timeout from ECONOMY)");
        }
        break;
    }
    case UPGRADING:
        if (info.civilizationStage >= CIVILIZATION_BRONZEAGE) {
            state = DEFENSE_PREP;
            DebugText(">> Bronze Age reached!");
        }
        // 升级完成前保持 UPGRADING 状态，自然等待 civilizationStage 变化
        break;

    case DEFENSE_WAVE1:
        // ★ 食物够800立刻升铜器
        if (info.civilizationStage < CIVILIZATION_BRONZEAGE && !hasUpgraded) {
            if (info.Meat >= BUILDING_CENTER_UPGRADE_BRONZEAGE_FOOD) {
                auto tc = findBuilding(BUILDING_CENTER);
                if (tc && tc->Project == ACT_NULL) {
                    BuildingAction(tc->SN, BUILDING_CENTER_UPGRADE);
                    hasUpgraded = true;
                    state = UPGRADING;
                    DebugText(QString(">> WAVE1 Bronze Age! Frame=%1, Meat=%2")
                        .arg(frame).arg((int)info.Meat));
                    break;
                }
            }
        }
        // 第一波结束条件：敌人稀少 或 超时强制结束
        if (frame > WAVE1_TIME + 3500) {
            int eCount = info.enemy_armies.size() + info.enemy_farmers.size();
            if (eCount < 3 || frame > WAVE1_TIME + 6000) {
                wave1Defeated = true;
                state = DEFENSE_PREP;
                DebugText(QString(">> Wave 1 defeated at frame %1").arg(frame));
            }
        }
        // 第二波时间到了直接切换
        if (frame >= WAVE2_TIME && !wave2Started) {
            wave2Started = true;
            state = DEFENSE_WAVE2;
            DebugText("!! WAVE 2 INCOMING!");
        }
        break;

    case DEFENSE_PREP:
        // ★ 食物够800立刻升铜器
        if (info.civilizationStage < CIVILIZATION_BRONZEAGE && !hasUpgraded) {
            if (info.Meat >= BUILDING_CENTER_UPGRADE_BRONZEAGE_FOOD) {
                auto tc = findBuilding(BUILDING_CENTER);
                if (tc && tc->Project == ACT_NULL) {
                    BuildingAction(tc->SN, BUILDING_CENTER_UPGRADE);
                    hasUpgraded = true;
                    state = UPGRADING;
                    DebugText(QString(">> LATE Bronze Age! Frame=%1, Meat=%2")
                        .arg(frame).arg((int)info.Meat));
                }
            }
        }
        // 检测波次开始
        if (frame >= WAVE1_TIME && !wave1Started) {
            wave1Started = true;
            state = DEFENSE_WAVE1;
            DebugText("!! WAVE 1 INCOMING!");
            break;
        }
        if (frame >= WAVE2_TIME && !wave2Started) {
            wave2Started = true;
            state = DEFENSE_WAVE2;
            DebugText("!! WAVE 2 INCOMING!");
            break;
        }
        if (frame >= WAVE3_TIME && !wave3Started) {
            wave3Started = true;
            state = DEFENSE_WAVE3;
            DebugText("!! WAVE 3 INCOMING (no retreat)!");
            break;
        }
        break;

    case DEFENSE_WAVE2:
        // 铜器升级
        if (info.civilizationStage < CIVILIZATION_BRONZEAGE && !hasUpgraded) {
            if (info.Meat >= BUILDING_CENTER_UPGRADE_BRONZEAGE_FOOD) {
                auto tc = findBuilding(BUILDING_CENTER);
                if (tc && tc->Project == ACT_NULL) {
                    BuildingAction(tc->SN, BUILDING_CENTER_UPGRADE);
                    hasUpgraded = true;
                    state = UPGRADING;
                    DebugText(QString(">> W2 Bronze Age! Frame=%1, Meat=%2")
                        .arg(frame).arg((int)info.Meat));
                    break;
                }
            }
        }
        if (frame > WAVE2_TIME + 4500) {
            int eCount = info.enemy_armies.size() + info.enemy_farmers.size();
            if (eCount < 5 || frame > WAVE2_TIME + 7000) {
                wave2Defeated = true;
                state = DEFENSE_PREP;
                DebugText(QString(">> Wave 2 defeated at frame %1").arg(frame));
            }
        }
        if (frame >= WAVE3_TIME && !wave3Started) {
            wave3Started = true;
            state = DEFENSE_WAVE3;
            DebugText("!! WAVE 3 INCOMING (no retreat)!");
        }
        break;

    case DEFENSE_WAVE3:
        // 第三波必须全部消灭
        if (frame > WAVE3_TIME + 6000) {
            int eCount = info.enemy_armies.size() + info.enemy_farmers.size();
            if (eCount < 3 || frame > WAVE3_TIME + 10000) {
                wave3Defeated = true;
                state = COUNTERATTACK;
                DebugText(QString(">> ALL WAVES DEFEATED! Counterattack! Frame=%1").arg(frame));
            }
        }
        // 超时强制反击：frame > 27000
        if (frame > 27000 && state == DEFENSE_WAVE3) {
            state = COUNTERATTACK;
            DebugText("!! Force COUNTERATTACK (timeout)");
        }
        break;

    default: break;
    }
}

// ============================================================
// 祭司管理（W1感化刀斧兵 > 反攻感化 > 逃跑保命 > 治疗）
// ============================================================
void UsrAI::managePriest() {
    if (priestSN == -1) return;

    // ★ 祭司正在探路→跳过常规逻辑（由探路模块接管）
    if (scoutPhase < 20) return;

    tagArmy* priest = nullptr;
    for (auto &a : info.armies) {
        if (a.SN == priestSN) { priest = &a; break; }
    }
    if (!priest) return;

    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return;
    double BL = (double)BLOCKSIDELENGTH;
    double pDR = priest->DR, pUR = priest->UR;
    double tcDR = (center->BlockDR + 1) * BL;
    double tcUR = (center->BlockUR + 1) * BL;
    bool canAct = (priest->NowState == HUMAN_STATE_IDLE || priest->NowState == HUMAN_STATE_WALKING);

    if (priestMoveCooldown > 0) priestMoveCooldown--;

    // ★ 落点合法性过滤：目标格被建筑/单位占据时引擎判定移动失败（"被占据/不可达"）→单位原地不动、
    //   每次冷却到期又重发同一坐标刷屏。所有祭司移动指令的落点都必须先过这一关。
    auto occupiedLanding = [&](double x, double y) {
        for (auto &b : info.buildings)
            if (calDistance(x, y, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL) < 2.5 * BL) return true;
        for (auto &a : info.armies)
            if (a.SN != priestSN && calDistance(x, y, a.DR, a.UR) < 2.0 * BL) return true;
        for (auto &f : info.farmers)
            if (calDistance(x, y, f.DR, f.UR) < 2.0 * BL) return true;
        for (auto &e : info.enemy_armies)
            if (calDistance(x, y, e.DR, e.UR) < 4.0 * BL) return true;
        for (auto &e : info.enemy_farmers)
            if (calDistance(x, y, e.DR, e.UR) < 4.0 * BL) return true;
        return false;
    };

    auto findConvertTarget = [&](double dr, double ur, double range) -> int {
        // ★ 转化优先级（2026-09-03 用户要求：优先感化【近战单位】，投石车仍最优先）：
        //   ① 投石车(AT_STONE_THROWER)无条件最优先——最强攻城单位，转过来即我方最强远程火力。
        //   ② 近战单位优先于远程（除投石车）——近战能顶前排、给远程弓兵/祭司挡刀，转来价值高于远程脆皮。
        //      (近战判定：攻击距离 DIS=0，即非 isRanged 的军队；近战含棍棒/剑士/骑兵/战车/方阵/阔剑等。)
        //      多辆近战选血量最高者(更耐打、转来更强)，同血取近者。
        //   ③ 无近战则退回"血量最多"的剩余远程军队兜底；仍无军队则"最近敌方村民"。
        // 优先感化投石车
        int bestCatSN = -1; int bestCatBlood = -1; double bestCatDist = 1e12;
        for (auto &e : info.enemy_armies) {
            if (e.Blood <= 0) continue;
            if (e.Sort != AT_STONE_THROWER) continue;
            double d = calDistance(dr, ur, e.DR, e.UR);
            if (d > range) continue;
            if (e.Blood > bestCatBlood || (e.Blood == bestCatBlood && d < bestCatDist)) {
                bestCatBlood = e.Blood; bestCatSN = e.SN; bestCatDist = d;
            }
        }
        if (bestCatSN >= 0) return bestCatSN;    // 1) 范围内有投石车→最高优先感化
        // 2) 范围内血量最多的【近战】敌方军队（投石车已排除，远程也排除）
        int bestSN = -1; int bestBlood = -1; double bestDist = 1e12;
        for (auto &e : info.enemy_armies) {
            if (e.Blood <= 0) continue;             // 跳过尸体/零血
            if (e.Sort == AT_STONE_THROWER) continue;             // 投石车已在①处理
            // 近战判定：非远程（远程=弓/复合弓/战车弓/投石兵，DIS>0；投石车亦远程但已排除）
            bool isMelee = !(e.Sort == AT_BOWMAN || e.Sort == AT_CHARIOT_ARCHER ||
                             e.Sort == AT_COMPOSITE_BOWMAN || e.Sort == AT_SLINGER);
            if (!isMelee) continue;                 // 只优先近战
            double d = calDistance(dr, ur, e.DR, e.UR);
            if (d > range) continue;
            if (e.Blood > bestBlood || (e.Blood == bestBlood && d < bestDist)) {
                bestBlood = e.Blood; bestSN = e.SN; bestDist = d;
            }
        }
        if (bestSN >= 0) return bestSN;             // 2) 范围内有近战→优先感化
        // 3) 范围内血量最多的剩余远程军队（投石车/近战已排除，作兜底）
        for (auto &e : info.enemy_armies) {
            if (e.Blood <= 0) continue;
            if (e.Sort == AT_STONE_THROWER) continue;
            bool isMelee = !(e.Sort == AT_BOWMAN || e.Sort == AT_CHARIOT_ARCHER ||
                             e.Sort == AT_COMPOSITE_BOWMAN || e.Sort == AT_SLINGER);
            if (isMelee) continue;                  // 近战已在②处理
            double d = calDistance(dr, ur, e.DR, e.UR);
            if (d > range) continue;
            if (e.Blood > bestBlood || (e.Blood == bestBlood && d < bestDist)) {
                bestBlood = e.Blood; bestSN = e.SN; bestDist = d;
            }
        }
        if (bestSN >= 0) return bestSN;
        // 兜底：无敌方军队时，最近敌方村民（保留原行为）
        int bestVilSN = -1; double bestVilDist = 1e12;
        for (auto &e : info.enemy_farmers) {
            double d = calDistance(dr, ur, e.DR, e.UR);
            if (d > range) continue;
            if (d < bestVilDist) { bestVilDist = d; bestVilSN = e.SN; }
        }
        return bestVilSN;
    };

    // ★ 侦测"视野内正被敌军攻击的己方村民"：返回正在攻击该村民的敌军 SN 及其坐标。
    //   用于"自身安全时上前感化凶手"(感化优先级 > 逃跑)。
    //   判定：① 村民在祭司视野内(≤20格) ② 存在 enemy_armies 单位且 NowState==ATTACKING(确在攻击)
    //        ③ 该敌距村民 ≤ 其攻击射程+余量(确实在揍这名村民,非路过)→即凶手。
    //   取离祭司最近的一起救援(路程最短、暴露风险最低)；返回 -1 表示视野内无村民正挨打。
    auto findAttackedVillager = [&](double &aDR, double &aUR) -> int {
        aDR = 0; aUR = 0;
        const double VIEW = PRIEST_CONVERT_RANGE * BL;   // 祭司感化目标发现范围（扩大到与 findConvertTarget 一致）
        int bestSN = -1; double bestDist = 1e12;
        for (auto &f : info.farmers) {     // 己方村民
            double dP = calDistance(pDR, pUR, f.DR, f.UR);
            if (dP > VIEW) continue;        // 超出视野
            for (auto &e : info.enemy_armies) {
                if (e.NowState != HUMAN_STATE_ATTACKING) continue;   // 必须正在攻击
                double rA = (e.Sort == AT_BOWMAN || e.Sort == AT_CHARIOT_ARCHER ||
                             e.Sort == AT_COMPOSITE_BOWMAN || e.Sort == AT_SLINGER ||
                             e.Sort == AT_STONE_THROWER) ? 12.0 * BL : 2.5 * BL;
                if (calDistance(e.DR, e.UR, f.DR, f.UR) <= rA + 1.5 * BL) {
                    if (dP < bestDist) { bestDist = dP; bestSN = e.SN; aDR = e.DR; aUR = e.UR; }
                    break;   // 该村民已锁定凶手,看下一个村民
                }
            }
        }
        return bestSN;
    };

    // ★ 朝敌靠近进入感化范围；落点做可达预检+侧向偏移重试，避免落在建筑/单位上被引擎拒收
    //   → 祭司原地刷屏、永远走不进感化距离(表现为"一直移动却不动+不感化")。
    //   ★ 用户要求"能感化直接感化"：已移除"身处威胁不主动迎敌"守卫——冷却好了就朝感化目标靠近。
    double threatDist = 1e12;
    double nearestThreatR = 2.5 * BL;   // 最近威胁的射程半径：逃/感的阈值据此算"逃出射程"的安全余量
    {
        auto chkThreat = [&](double x, double y, double r) {
            double d = calDistance(pDR, pUR, x, y);
            if (d <= r + 4.0 * BL) {
                if (d < threatDist) { threatDist = d; nearestThreatR = r; }  // 记录最近威胁及其射程
            }
        };
        for (auto &e : info.enemy_armies) {
            double r = (e.Sort == AT_BOWMAN || e.Sort == AT_CHARIOT_ARCHER ||
                        e.Sort == AT_COMPOSITE_BOWMAN || e.Sort == AT_SLINGER ||
                        e.Sort == AT_STONE_THROWER) ? 12.0 * BL : 2.5 * BL;
            chkThreat(e.DR, e.UR, r);
        }
        for (auto &e : info.enemy_farmers) chkThreat(e.DR, e.UR, 1.0 * BL);
        for (auto &b : info.enemy_buildings)
            if (b.Type == BUILDING_ARROWTOWER) chkThreat((b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL, 12.0 * BL);
    }

    auto priestApproachMove = [&](double eDR, double eUR, double stopDist) -> bool {
        if (priestMoveCooldown > 0) return false;   // 节流：冷却期内绝不重发(与 priestFlee 同闸)
        double dx = eDR - pDR, dy = eUR - pUR;
        double len = std::sqrt(dx*dx + dy*dy);
        if (len < 0.01) return false;
        double ux = dx/len, uy = dy/len;
        double bx = pDR + ux * (len - stopDist * BL);
        double by = pUR + uy * (len - stopDist * BL);
        const double OFF[6] = {0.0, 3.0, -3.0, 6.0, -6.0, 9.0};
        double candX = bx, candY = by; bool ok = false;
        for (int o = 0; o < 6; ++o) {
            double cx = bx - uy * OFF[o] * BL;   // 垂直于"祭司-敌人"连线方向偏移,绕开挡路建筑
            double cy = by + ux * OFF[o] * BL;
            cx = max(0.0, min((double)MAP_L * BL, cx));
            cy = max(0.0, min((double)MAP_U * BL, cy));
            if (!occupiedLanding(cx, cy)) { candX = cx; candY = cy; ok = true; break; }
        }
        if (!ok) return false;   // 全部侧向偏移都不可达→本帧不发令,下帧再试,杜绝刷屏
        HumanMove(priestSN, candX, candY);
        priestMoveCooldown = 20;
        return true;
    };

    // ★ 祭司逃跑（螺旋避障 + 朝安全区 + 卡死检测）；enDR/enUR 为威胁敌人坐标（退路用）
    // ★ 祭司逃跑（v7）：螺旋避障+朝安全区+卡死检测；节流(冷却期内不重发)+状态判定死锁(下发的点被引擎拒收→
    //   祭司仍是 IDLE 且离该点远→换下一扇区)。根治"每帧重发同一不可达点刷屏、一直移动却不动"。
    auto priestFlee = [&](double enDR, double enUR) {
        if (priestMoveCooldown > 0) return;   // 节流：冷却期内绝不重发(旧版无此闸→每帧重发同点刷屏)
        // 威胁半径：远程(弓/投石/战车弓/复合弓/投石车)≈12 格;近战≈2.5 格;敌方箭塔≈12 格;村民不攻击≈1 格。
        const int MAXT = 256;
        double thX[MAXT], thY[MAXT], thR[MAXT];
        int nT = 0;
        auto pushThreat = [&](double x, double y, double r) {
            if (nT < MAXT) { thX[nT] = x; thY[nT] = y; thR[nT] = r; nT++; }
        };
        for (auto &e : info.enemy_armies) {
            double d = calDistance(pDR, pUR, e.DR, e.UR);
            double r = (e.Sort == AT_BOWMAN || e.Sort == AT_CHARIOT_ARCHER ||
                        e.Sort == AT_COMPOSITE_BOWMAN || e.Sort == AT_SLINGER ||
                        e.Sort == AT_STONE_THROWER) ? 12.0 * BL : 2.5 * BL;
            if (d <= r + 4.0 * BL) pushThreat(e.DR, e.UR, r);   // 含提前量4格,进射程前就起步
        }
        for (auto &e : info.enemy_farmers) {
            double d = calDistance(pDR, pUR, e.DR, e.UR);
            if (d <= 2.0 * BL) pushThreat(e.DR, e.UR, 1.0 * BL);  // 村民不攻击,仅避免贴脸
        }
        for (auto &b : info.enemy_buildings)
            if (b.Type == BUILDING_ARROWTOWER) {
                double bx = (b.BlockDR + 1) * BL, by = (b.BlockUR + 1) * BL;
                double d = calDistance(pDR, pUR, bx, by);
                if (d <= 16.0 * BL) pushThreat(bx, by, 12.0 * BL);
            }
        // 远离所有"能打到我"的威胁合力方向(主力轴)
        double pushX = 0, pushY = 0;
        for (int t = 0; t < nT; ++t) {
            double dx = pDR - thX[t], dy = pUR - thY[t];
            double d = std::sqrt(dx*dx + dy*dy);
            if (d < 0.01) { pushX += 1; continue; }
            double w = 1.0 / (d * d);
            pushX += dx / d * w; pushY += dy / d * w;
        }
        double baseAng;
        if (nT > 0) baseAng = std::atan2(pushY, pushX);
        else if (enDR != 0 || enUR != 0) baseAng = std::atan2(pUR - enUR, pDR - enDR);
        else return;   // 无威胁也无坐标→不逃,避免朝(0,0)乱跑
        // ★ 逃跑安全锚点（2026-09-03 用户需求"绕着箭塔走"）：优先朝【最近己方箭塔】跑(≤30格)。
        //   箭塔既是掩体(挡在祭司与追兵之间)又是火力点(追兵进 8 格射程被箭塔打)，比一味跑回 TC 更有效。
        //   无箭塔 / 箭塔太远(>30格) 则退回 TC 当锚点。
        //   ★ 2026-09-04 加安全过滤：若所有可用箭塔都被围攻(在威胁射程内+4)，仍退回 TC——否则祭司朝
        //     "正在被攻的箭塔"跑→深入敌火、原地转圈送命。这是"躲外线箭塔被攻击也要逃"的关键。
        double anchorX = tcDR, anchorY = tcUR;
        {
            double bestTowerDist = 30.0 * BL;
            for (auto &b : info.buildings)
                if (b.Type == BUILDING_ARROWTOWER && b.Percent == 100) {
                    double bx = (b.BlockDR + 1) * BL, by = (b.BlockUR + 1) * BL;
                    double d = calDistance(pDR, pUR, bx, by);
                    // 箭塔必须在所有威胁射程外(+4 格提前量)；否则被围攻，朝它跑反被夹击
                    bool unsafe = false;
                    for (int t = 0; t < nT; ++t) {
                        if (calDistance(bx, by, thX[t], thY[t]) <= thR[t] + 4.0 * BL) {
                            unsafe = true; break;
                        }
                    }
                    if (unsafe) continue;
                    if (d < bestTowerDist) { bestTowerDist = d; anchorX = bx; anchorY = by; }
                }
        }
        // 偏向安全锚点(箭塔优先/否则TC)：既远离威胁又靠己方火力/保护
        double toAX = anchorX - pDR, toAY = anchorY - pUR;
        double alen = std::sqrt(toAX*toAX + toAY*toAY);
        if (alen > 0.01) {
            double dot = (toAX/alen)*std::cos(baseAng) + (toAY/alen)*std::sin(baseAng);
            if (dot > 0) baseAng = std::atan2(std::sin(baseAng) + toAY/alen*0.9,
                                              std::cos(baseAng) + toAX/alen*0.9);
        }
        // 死锁检测(基于"下发点是否被引擎拒收"):上一帧下发 flee 点后,本帧祭司仍是 IDLE 且离该点>2格
        //   → 说明该落点不可达/被占(引擎拒收、祭司原地不动)→换下一扇区重试;若已抵达/正在接近→重置。
        if (priestFleeLastFrame > -999999) {
            double distToLast = calDistance(pDR, pUR, priestFleeLastX, priestFleeLastY);
            if (priest->NowState == HUMAN_STATE_IDLE && distToLast > 2.0 * BL) {
                if (priestFleeTry < 30) priestFleeTry++;   // 卡死→换角度/半径重试
            } else if (distToLast <= 2.0 * BL) {
                priestFleeTry = 0;   // 已抵达或正在接近→正常,重置计数
            }
        }
        // 落点合法性:不压己方建筑/单位;且不落在任何威胁射程内(否则逃出又进射程,继续被远程消耗)。
        auto badLanding = [&](double x, double y) -> bool {
            if (x < 0 || y < 0 || x > MAP_L * BL || y > MAP_U * BL) return true;
            for (auto &b : info.buildings)
                if (calDistance(x, y, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL) < 2.5 * BL) return true;
            for (auto &a : info.armies)
                if (a.SN != priestSN && calDistance(x, y, a.DR, a.UR) < 2.0 * BL) return true;
            for (auto &f : info.farmers)
                if (calDistance(x, y, f.DR, f.UR) < 2.0 * BL) return true;
            for (int t = 0; t < nT; ++t)
                if (calDistance(x, y, thX[t], thY[t]) < thR[t]) return true;  // 仍在威胁射程内→不安全
            return false;
        };
        // 扫描 24 方向(±165°,15°/档) × 7 半径:挑"完全安全(逃出所有威胁射程)且最靠近TC"的落点;
        //   若无一完全安全,挑"相对最安全(离威胁射程余量最大)"的。从 priestFleeTry 起旋转,卡死时换扇区。
        int start = priestFleeTry % 24;
        double bestX = 0, bestY = 0, bestSafe = -1e9, bestAnchor = 1e9;
        bool found = false, foundSafe = false;
        for (int k = 0; k < 24; ++k) {
            int idx = start + k; if (idx >= 24) idx -= 24;
            double ang = baseAng + (idx - 11) * (3.141592653589793 / 12.0);
            const double RADS[7] = {8.0, 12.0, 16.0, 22.0, 28.0, 34.0, 40.0};
            for (int ri = 0; ri < 7; ++ri) {
                double rad = RADS[ri] * BL;
                double tx = pDR + std::cos(ang) * rad;
                double ty = pUR + std::sin(ang) * rad;
                if (badLanding(tx, ty)) continue;
                double margin = 1e9;   // 落点到最近威胁射程边界的余量
                for (int t = 0; t < nT; ++t)
                    margin = std::min(margin, calDistance(tx, ty, thX[t], thY[t]) - thR[t]);
                double dAnchor = calDistance(tx, ty, anchorX, anchorY);   // 靠锚点(箭塔优先/否则TC)
                if (margin >= 0 && !foundSafe) { bestX = tx; bestY = ty; bestSafe = margin; bestAnchor = dAnchor; foundSafe = true; found = true; }
                else if (margin >= 0 && dAnchor < bestAnchor) { bestX = tx; bestY = ty; bestSafe = margin; bestAnchor = dAnchor; found = true; }
                else if (!foundSafe && margin > bestSafe) { bestX = tx; bestY = ty; bestSafe = margin; bestAnchor = dAnchor; found = true; }
            }
        }
        if (!found) {
            // 被建筑/单位/威胁彻底封死→退回主方向最远档,交卡死检测换档
            double rad = 40.0 * BL;
            bestX = max(0.0, min((double)MAP_L * BL, pDR + std::cos(baseAng) * rad));
            bestY = max(0.0, min((double)MAP_U * BL, pUR + std::sin(baseAng) * rad));
            if (frame % 50 == 0) DebugText("Priest FLEE: 无安全落点→退回主方向");
        }
        // 彻底卡死(已轮换全部24扇区仍原地不动)→本帧不再发令,长冷却静默待命,避免刷屏;
        //   下帧逻辑(感化/待命)仍可接管,不再死磕同一不可达点。
        if (priestFleeTry >= 24 && priest->NowState == HUMAN_STATE_IDLE &&
            calDistance(pDR, pUR, priestFleeLastX, priestFleeLastY) > 2.0 * BL) {
            priestMoveCooldown = 40;
            if (frame % 50 == 0) DebugText("Priest FLEE: 卡死->本帧静默");
            return;
        }
        HumanMove(priestSN, bestX, bestY);
        priestFleeLastX = bestX; priestFleeLastY = bestY; priestFleeLastFrame = frame;
        priestMoveCooldown = 18;   // 威胁紧迫,缩短决策间隔
        if (frame % 50 == 0)
            DebugText(QString("Priest FLEE hp=%1 safe=%2 dAnchor=%3")
                      .arg((priest->MaxBlood > 0 ? (double)priest->Blood / priest->MaxBlood : 1.0), 0, 'f', 2)
                      .arg(foundSafe ? 1 : 0).arg(bestAnchor / BL, 0, 'f', 0));
    };


    // ★ 祭司引导中(WORKING=感化/治疗引导、ATTACKING)→绝不下发新命令打断引导。
    //   感化是"随机时段"的引导过程，期间 ConvertCooldown 仍为0；若此时重发
    //   HumanAction/移动命令，引导会被打断重来→永远转不完(本次bug"一直设置转换目标却没感化")。
    //   唯一例外：残血(≤0.25)强制打断逃命(祭司死=立刻失败，保命高于感化)。
    if (!canAct) {
        double pBRx = (priest->MaxBlood > 0) ? priest->Blood / priest->MaxBlood : 1.0;
        if (pBRx > 0.25) return;
        double feDR = 0, feUR = 0, fbest = 1e12;
        for (auto &e : info.enemy_armies) {
            double d = calDistance(pDR, pUR, e.DR, e.UR);
            if (d < fbest) { fbest = d; feDR = e.DR; feUR = e.UR; }
        }
        priestMode = 1;
        priestFlee(feDR, feUR);
        return;
    }

    // ★ 统一生存/感化决策（迟滞锁 priestMode + 威胁感知，根治往返走 / 走进敌人射程被消耗）
    {
        double nearestE = 1e12;
        for (auto &e : info.enemy_armies)
            nearestE = std::min(nearestE, calDistance(pDR, pUR, e.DR, e.UR));
        for (auto &e : info.enemy_farmers)
            nearestE = std::min(nearestE, calDistance(pDR, pUR, e.DR, e.UR));
        for (auto &b : info.enemy_buildings)
            if (b.Type == BUILDING_ARROWTOWER)
                nearestE = std::min(nearestE, calDistance(pDR, pUR, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL));
        double pBR = (priest->MaxBlood > 0) ? priest->Blood / priest->MaxBlood : 1.0;
        if (frame % 100 == 0)
            DebugText(QString("Priest st=%1 hp=%2 nearE=%3 threat=%4 mode=%5")
                      .arg(priest->NowState).arg(pBR, 0, 'f', 2)
                      .arg(nearestE / BL, 0, 'f', 1).arg(threatDist / BL, 0, 'f', 1).arg(priestMode));
        auto locateNearest = [&](double &ox, double &oy) {
            ox = 0; oy = 0;
            if (nearestE >= 1e11) return;
            for (auto &e : info.enemy_armies)
                if (calDistance(pDR, pUR, e.DR, e.UR) <= nearestE + 0.01) { ox = e.DR; oy = e.UR; return; }
            for (auto &e : info.enemy_farmers)
                if (calDistance(pDR, pUR, e.DR, e.UR) <= nearestE + 0.01) { ox = e.DR; oy = e.UR; return; }
        };
        // ★ 2026-09-05 死代码清理：原 `woundedRest` lambda（受伤静养回 TC 旁可达环）已删除。
        //   唯一调用点原在统一块第 5) 步 `if (pBR <= 0.25) { woundedRest(); return; }`，
        //   而第 2) 步早已用完全相同条件 `pBR <= 0.25` 无条件 return 逃命；pBR 自 699 行定义后
        //   从未重新赋值 → 第 5) 步恒不可达，该 lambda 永不执行（删前编译告警 unused-but-set-variable）。
        //   功能等价替代：濒死由第 2) 步 priestFlee() 逃命（更安全——躲开威胁方向，而非径直回 TC）。
        // 感化检测(无安全门槛)：冷却好+视野内有可感化敌(≤20格)即可，直接感化/靠近感化。
        //   ★ 用户要求"不用安全感化，能感化直接感化"：感化绝对优先，不再要求逃出敌射程、
        //     不再看血量——冷却好了就转(贴身敌≤3时转走攻击者本身往往就是最好的保命)。
        int safeConv = -1;
        if (priest->ConvertCooldown <= 0 && nearestE <= PRIEST_CONVERT_RANGE * BL) {
            int t = findConvertTarget(pDR, pUR, PRIEST_CONVERT_RANGE * BL);
            if (t >= 0) safeConv = t;
        }
        // 1) ★ 感化无条件最高优先（用户要求：不用安全感化，能感化直接感化）：
        //    a) 视野内村民正被攻击→上前感化凶手；
        //    b) 附近(≤20格)有可感化敌→直接感化或靠近感化。
        //    冷却好即转：不看血量、不要求逃出敌射程——贴身敌≤3时转走攻击者本身往往就是最好的保命；
        //    即便上帧在逃(priestMode==1)也优先转，彻底消除"该感化却只逃"的问题。
        int villConv = -1; double villDR = 0, villUR = 0;
        if (priest->ConvertCooldown <= 0) {
            villConv = findAttackedVillager(villDR, villUR);
        }
        int convSN = -1; double convDR = 0, convUR = 0;
        if (villConv >= 0) {
            convSN = villConv; convDR = villDR; convUR = villUR;
        } else if (safeConv >= 0) {
            convSN = safeConv;
            for (auto &e : info.enemy_armies) if (e.SN == convSN) { convDR = e.DR; convUR = e.UR; break; }
            if (convDR == 0 && convUR == 0)
                for (auto &e : info.enemy_farmers) if (e.SN == convSN) { convDR = e.DR; convUR = e.UR; break; }
        }
        if (convSN >= 0) {
            // ★ 节流闸(本次bug根因)：感化引导期间 ConvertCooldown 仍为0，若无此闸会每帧
            //   重发 HumanAction 把引导反复打断重来，转换永远完不成。冷却期内绝不再发令。
            //   拒收检测：下发感化后≥15帧祭司仍是 IDLE 且目标未变→指令被引擎拒收
            //   (真在引导会进入 WORKING 被上方 canAct 闸拦住)→提前放行重发，不白等150帧。
            if (priestMoveCooldown > 0) {
                bool rejected = (priestConvSN == convSN && priest->NowState == HUMAN_STATE_IDLE &&
                                 priestConvFrame > -999999 && frame - priestConvFrame >= 15);
                if (!rejected) return;
            }
            priestMode = 0;   // 转去感化→解除撤退迟滞锁
            double cdist = calDistance(pDR, pUR, convDR, convUR);
            if (cdist <= 12 * BL) {
                HumanAction(priestSN, convSN);
                priestConvSN = convSN; priestConvFrame = frame;
                priestMoveCooldown = 150;
                if (frame % 50 == 0)
                    DebugText(QString("Priest CONVERT(defense) SN=%1 vill=%2")
                              .arg(convSN).arg(villConv >= 0 ? 1 : 0));
                return;
            } else {
                double stopDist = 12.0;   // 停12格正好进入引擎感化射程(DIS_PRIEST=12)
                priestApproachMove(convDR, convUR, stopDist); return;
            }
        }
        // ==== 以下均为"无法感化"(冷却中/视野内无目标)时才轮到的保命/待命逻辑 ====
        // 2) ★ 强制撤退闸：仅在【残血(pBR≤0.25)】时无条件逃命，不再用 OR 触发 nearestE≤3。
        //   【2026-09-04 修·用户反馈"祭司不满血时不治友军"根因】：
        //     原条件 `nearestE <= 3 * BL || pBR <= 0.25` (OR)——只要任意近战贴身 3 格就 fled
        //     → 807 战地急救 / 840 主动趋近 / 916 闲时治友军三档被本闸抢先 return 全压制。
        //     贴脸场景下祭司血量仍较高(pBR>0.55,被 AOE/流矢擦掉血)时，本应先治身边重伤友军
        //     再考虑逃命——但旧版会先 fled，导致"血量不满就不治"的观测。
        //   改后：仅当濒死(pBR≤0.25)才全闸 fled。正常贴脸场景由下方 900/906 的"威胁射程+2"
        //   flee 闸接管(更精细,近战贴身会 fled,远程远处骚扰照常治友军)。
        //   ★ 治档铁律：所有对友军治疗调用必须使用 `HumanAction(priestSN, allySN)`
        //     —— 引擎 Core.cpp:1091-1096 判定:祭司对同阵营人类(SORT_ARMY/SORT_FARMER)的
        //     HumanAction 走 CoreEven_Attacking 关系,记录为"治疗"而非"攻击";祭司自指
        //     HumanAction(priestSN,priestSN) 走自疗(非自毁);非祭司军队自指才自毁。
        //     严禁用 HumanBuild / Upgrade / 任何其他动作触发治疗——HumanAction 才是入口。
        if (pBR <= 0.25) {
            double feDR = 0, feUR = 0; locateNearest(feDR, feUR);
            priestMode = 1; priestFlee(feDR, feUR); return;
        }
        // ★ 2.5) 战地急救（本次修复"祭司只在满血才治疗友军"的核心）：
        //   【原现象根因】治友军步原本排在"威胁撤退闸"(下方第4步)之后，而撤退闸对远程敌的阈值是
        //     threatDist ≤ nearestThreatR(12格) + 2 = 14格 —— 即任何弓兵/战车弓/复合弓/投石兵/箭塔
        //     出现在祭司 14 格内，祭司就 return 去逃跑，永远走不到治友军。于是只有"身边14格完全无敌"
        //     的脱战时段才治疗友军，而那时祭司恰好没挨打=满血 → 观感就是"只在满血状态才治友军"。
        //   【修复】在撤退闸之前插入战地急救档：重伤友军近在身边且局部安全时先救人，不设自身血量门槛。
        //   【保命红线】(缺一不可，防止为救人送命)：
        //     ① 自身血量 > 0.25（濒死 pBR≤0.25 仍归顶部 canAct 闸/第2步强制逃命；2026-09-03 放宽：
        //        原 0.35 门槛会让祭司稍一受伤就不治友军，观感"不满血就不治"）；② 目标距离 ≤3格；
        //     ③ 目标 6 格内无敌军 / 4 格内无敌村民（不会一头扎进敌群）；④ 祭司空闲且节流就绪。
        if (priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0 && pBR > 0.25) {
            int urgentAlly = -1; double urgentRatio = 1.0;
            for (auto &a : info.armies) {
                if (a.SN == priestSN) continue;      // 铁律：绝不把祭司自己当治疗目标
                if (a.MaxBlood <= 0 || a.Blood <= 0) continue;
                double r = (double)a.Blood / a.MaxBlood;
                if (r >= 0.55) continue;             // 只救重伤友军(<55%)
                if (calDistance(pDR, pUR, a.DR, a.UR) > 3.0 * BL) continue;  // 必须近在身边
                bool allySafe = true;
                for (auto &e : info.enemy_armies)
                    if (calDistance(a.DR, a.UR, e.DR, e.UR) < 6.0 * BL) { allySafe = false; break; }
                if (allySafe)
                    for (auto &e : info.enemy_farmers)
                        if (calDistance(a.DR, a.UR, e.DR, e.UR) < 4.0 * BL) { allySafe = false; break; }
                if (!allySafe) continue;
                if (r < urgentRatio) { urgentRatio = r; urgentAlly = a.SN; }
            }
            if (urgentAlly >= 0) {
                HumanAction(priestSN, urgentAlly);
                priestMoveCooldown = 30;
                if (frame % 50 == 0)
                    DebugText(QString("Priest HEAL (combat) SN=%1 ratio=%2 hp=%3")
                              .arg(urgentAlly).arg(urgentRatio, 0, 'f', 2).arg(pBR, 0, 'f', 2));
                return;
            }
        }
        // ★ 2.6) 主动趋近治疗重伤友军（即便自身未满血，只要不在即时危险中就该去救人）
        //   【根因·三度复现】前两轮加的 2.5/2.6 仍用 "nearestE>8格(附近无敌)" 作安全判据，
        //     而"满血"恰好=附近无敌(附近有敌早被打掉血) → 治疗档仍只在满血时触发，观感不变。
        //     正确判据必须与下方撤退闸一致：安全 = 不在任何威胁射程+2格内(threatDist>nearestThreatR+2)，
        //     而非"附近无敌人"。这样"受伤但已脱险(敌退出射程)"的祭司也会去救人。
        //   【保命红线】(缺一不可)：pBR>0.25(濒死仍归顶部 canAct 闸强制逃命，2026-09-03 放宽：
        //     原 0.4 门槛会让受伤祭司不救人) + 不在威胁射程+2格内(真被逼近射程则落到下方撤退闸逃跑)。
        if (priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0 && pBR > 0.25 &&
            threatDist > nearestThreatR + 2.0 * BL) {
            int needAlly = -1; double worstRatio = 1.0; double bestAllyDist = 1e12;
            double allyDR = 0, allyUR = 0;
            for (auto &a : info.armies) {
                if (a.SN == priestSN) continue;          // 铁律：绝不把自己当治疗目标
                if (a.MaxBlood <= 0 || a.Blood <= 0) continue;
                double r = (double)a.Blood / a.MaxBlood;
                if (r >= 0.8) continue;                  // 只救明显受伤(<80%)友军(免为小伤跨图)
                double d = calDistance(pDR, pUR, a.DR, a.UR);
                if (d > 25.0 * BL) continue;             // 太远不追，防送命/离TC过远
                if (r < worstRatio || (r == worstRatio && d < bestAllyDist)) {
                    worstRatio = r; needAlly = a.SN; bestAllyDist = d; allyDR = a.DR; allyUR = a.UR;
                }
            }
            if (needAlly >= 0) {
                auto healLandOk = [&](double x, double y) -> bool {
                    if (x < 0 || y < 0 || x > MAP_L * BL || y > MAP_U * BL) return false;
                    for (auto &b : info.buildings)
                        if (calDistance(x, y, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL) < 2.5 * BL) return false;
                    for (auto &e : info.enemy_armies)
                        if (calDistance(x, y, e.DR, e.UR) < 4.0 * BL) return false;
                    for (auto &e : info.enemy_farmers)
                        if (calDistance(x, y, e.DR, e.UR) < 4.0 * BL) return false;
                    return true;
                };
                if (bestAllyDist <= 1.0 * BL) {
                    HumanAction(priestSN, needAlly);
                    priestMoveCooldown = 30;
                    if (frame % 50 == 0)
                        DebugText(QString("Priest HEAL(approach) SN=%1 ratio=%2 hp=%3")
                                  .arg(needAlly).arg(worstRatio, 0, 'f', 2).arg(pBR, 0, 'f', 2));
                    return;
                }
                double ux = (allyDR - pDR) / bestAllyDist;
                double uy = (allyUR - pUR) / bestAllyDist;
                const double OFF[5] = {0.0, 1.0, -1.0, 2.0, -2.0};
                bool moved = false;
                for (int o = 0; o < 5; ++o) {
                    double cx = allyDR - ux * 0.6 * BL - uy * OFF[o] * BL;
                    double cy = allyUR - uy * 0.6 * BL + ux * OFF[o] * BL;
                    cx = max(0.0, min((double)MAP_L * BL, cx));
                    cy = max(0.0, min((double)MAP_U * BL, cy));
                    if (healLandOk(cx, cy)) {
                        HumanMove(priestSN, cx, cy);
                        moved = true;
                        break;
                    }
                }
                if (moved) {
                    priestMoveCooldown = 30;
                    if (frame % 50 == 0)
                        DebugText(QString("Priest MOVE->HEAL SN=%1 ratio=%2 hp=%3 d=%4")
                                  .arg(needAlly).arg(worstRatio, 0, 'f', 2).arg(pBR, 0, 'f', 2)
                                  .arg(bestAllyDist / BL, 0, 'f', 1));
                    return;
                }
            }
        }
        // 3) 撤退迟滞：上帧在逃且仍处最近威胁射程内(threatDist≤最近威胁射程+2)→继续逃，不切回(消除往返走)
        if (priestMode == 1 && threatDist <= nearestThreatR + 2.0 * BL) {
            double feDR = 0, feUR = 0; locateNearest(feDR, feUR);
            priestFlee(feDR, feUR); return;
        }
        priestMode = 0;
        // 4) 有威胁且无法感化(冷却中/无目标)→保命撤退
        if (threatDist <= nearestThreatR + 2.0 * BL) {
            double feDR = 0, feUR = 0; locateNearest(feDR, feUR);
            priestMode = 1; priestFlee(feDR, feUR); return;
        }
        // ★ 闲时治疗友军：位于感化/逃跑之后、回TC等其它逻辑之前。
        //   本分支只治疗友军(自身治疗见下方 SELF-HEAL 步)；且在安全范围内(避免祭司深入敌区送命)。
        //   ★ 用户要求：祭司治疗友军应【优先于】自我治疗 → 本步不设自身血量门槛(pBR>0.5 已删除)，
        //     只要安全(已通过上方威胁撤退闸)且有 25 格内受伤友军(<90%)即治友军；
        //     自身自疗(SELF-HEAL)作为本步"无伤友军可治"时的兜底,绝不抢占祭司本职。
        //   ★ 保命底线仍由顶部 canAct 闸(540行, pBR≤0.25强制逃命)兜底,故本步不会让祭司带险送命。
        //   ★ 治疗铁律：必须用 `HumanAction(priestSN, allySN)`——见上文治档铁律,不要换成
        //     HumanBuild/任何其他动作。本步已统一 HumanAction 化。
        //   ★ 2026-09-04 放宽：18 格 → 25 格,提升祭司治疗覆盖面,避免小伤兵被忽略。
        if (priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0) {
            int bestAlly = -1; double worstRatio = 1.0; double bestAllyDist = 1e12;
            double bestAllyDR = 0, bestAllyUR = 0;
            for (auto &a : info.armies) {
                if (a.SN == priestSN) continue;      // ★ 铁律：绝不把祭司自己当治疗目标(=自毁)
                if (a.MaxBlood <= 0) continue;       // 防除零
                if (a.Blood <= 0) continue;          // 已死亡/血量为0，不治疗
                double r = (double)a.Blood / a.MaxBlood;
                if (r >= 0.9) continue;              // 仅治疗明显受伤(血<90%)友军,免为小伤跨图奔波
                double d = calDistance(pDR, pUR, a.DR, a.UR);
                if (d > 25.0 * BL) continue;          // ★ 放宽到 25 格(原 18 太近,小伤兵被忽视)
                if (r < worstRatio || (r == worstRatio && d < bestAllyDist))
                    { worstRatio = r; bestAlly = a.SN; bestAllyDist = d; bestAllyDR = a.DR; bestAllyUR = a.UR; }
            }
            if (bestAlly >= 0) {
                // 先确保祭司走到伤兵相邻格：相邻时直接下令治疗；
                // 较远时用“允许靠近目标伤兵”的落点检查逐步走近，到达后引擎会自动/显式治疗。
                auto healLandingOk = [&](double x, double y) -> bool {
                    if (x < 0 || y < 0 || x > MAP_L * BL || y > MAP_U * BL) return false;
                    for (auto &b : info.buildings)
                        if (calDistance(x, y, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL) < 2.5 * BL) return false;
                    // ★ 治疗须贴近友军，故不再因"附近有其他友军/村民"拒掉落点——否则祭司被推到远处反复横跳、永远进不了治疗射程；
                    //   只避让建筑(不能站进去)与敌军(避免送命)。
                    for (auto &e : info.enemy_armies)
                        if (calDistance(x, y, e.DR, e.UR) < 4.0 * BL) return false;
                    for (auto &e : info.enemy_farmers)
                        if (calDistance(x, y, e.DR, e.UR) < 4.0 * BL) return false;
                    return true;
                };
                bool issued = false;
                if (bestAllyDist > 1.0 * BL) {
                    // ★ 治疗射程极短(引擎 Core_List.cpp 仅校验 isAttackable 标志、无距离判定)，须贴到友军身边(≈0.6格)才发治疗指令；
                    //   用小幅垂直偏移(0/±1/±2格)确保落点贴近友军，避免被推到远处反复横跳。
                    double ux = (bestAllyDR - pDR) / bestAllyDist;
                    double uy = (bestAllyUR - pUR) / bestAllyDist;
                    const double OFF[5] = {0.0, 1.0, -1.0, 2.0, -2.0};
                    for (int o = 0; o < 5; ++o) {
                        double cx = bestAllyDR - ux * 0.6 * BL - uy * OFF[o] * BL;
                        double cy = bestAllyUR - uy * 0.6 * BL + ux * OFF[o] * BL;
                        cx = max(0.0, min((double)MAP_L * BL, cx));
                        cy = max(0.0, min((double)MAP_U * BL, cy));
                        if (healLandingOk(cx, cy)) {
                            HumanMove(priestSN, cx, cy);
                            issued = true;
                            break;
                        }
                    }
                } else {
                    HumanAction(priestSN, bestAlly);
                    issued = true;
                }
                if (!issued) return;
                priestMoveCooldown = 30;
                if (frame % 50 == 0)
                    DebugText(QString("Priest HEAL (idle) SN=%1 ratio=%2")
                              .arg(bestAlly).arg(worstRatio, 0, 'f', 2));
                return;
            }
        }
        // ★ 祭司自我治疗（用户要求：祭司要能自我治疗）
        //   触发：自身受伤(pBR<0.9) + 空闲 + 节流就绪 + 安全(不在任何敌射程内: threatDist>最近威胁射程+1格)
        //   → 对自身下发 HumanAction(priestSN,priestSN) 触发引擎自疗(一帧内回满血，见 Core.cpp 1068-1080)。
        //   ★ 引擎真相：祭司自指=治疗(回满)，【绝非自毁】；仅"非祭司军队"自指才自毁。故本步安全。
        //   ★ 这是"统一生存/感化决策块"内唯一真正生效的自疗逻辑——本块末尾(804行)无条件 return，
        //     故下方 1024 行的 SELF-HEAL(idle) 分支是统一块重构后**遗留的死代码，永远不会执行**(本次修复落在活代码上)。
        //   ★ 安全阈值：仅要求"不在任何敌方交战射程内"(threatDist>nearestThreatR+1)，
        //     放宽原 nearestE>12格 与 +2 双重过严门槛，使祭司脱战安全时即自疗；
        //     若自疗期间被敌人逼近打到 pBR<=0.25，顶部 canAct 闸(540行)会强制打断并逃命(保命优先于自疗)。
        //   ★ 优先级：位于"闲时治友军"之后，作为【兜底】——仅当上方治友军步未触发(18格内无受伤友军)时
        //     才对自己自疗；祭司本职(治友军)永远优先于自疗(用户明确要求)。保命底线由 canAct 闸(540行)兜底。
        if (pBR < 0.9 && priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0 &&
            threatDist > nearestThreatR + 1.0 * BL) {
            HumanAction(priestSN, priestSN);
            priestMoveCooldown = 30;
            if (frame % 50 == 0)
                DebugText(QString("Priest SELF-HEAL hp=%1").arg(pBR, 0, 'f', 2));
            return;
        }
        // ★ 2026-09-05：原 `if (pBR <= 0.25) { woundedRest(); return; }` 是本块的死代码——
        //   第 2) 步(797-813 行)已用完全相同的条件 `pBR <= 0.25` 无条件 return，本行永不执行。已删除。
        //   "受伤静养回 TC"的语义由第 2) 步 priestFlee() 逃命覆盖（更安全：会躲开威胁方向而非回 TC）。
        // 6) ★ 无事可做→回【己方箭塔】旁待命（用户需求 2026-09-04：祭司躲在基地的箭塔附近）。
        //    ★ 与 priestFlee 一致：优先最近己方箭塔(≤30 格)，无箭塔/太远退回 TC。
        //    箭塔既有 8 格火力覆盖(追兵进射程会被打)又能当掩体(挡在祭司与敌之间)，比 TC 中心暴露安全得多。
        //    探完路/战斗结束后祭司必须撤回箭塔或 TC 附近，不能滞留野外。
        //    用锚点旁"空地"而非锚点中心(中心不可达→引擎拒收原地不动)，多半径×多角度螺旋找可走点。
        {
            // ★ 锚点：优先最近己方箭塔(≤30 格且 Percent==100 已建成)，否则退回 TC
            double anchorX = tcDR, anchorY = tcUR;
            {
                double bestTowerDist = 30.0 * BL;
                for (auto &b : info.buildings)
                    if (b.Type == BUILDING_ARROWTOWER && b.Percent == 100) {
                        double bx = (b.BlockDR + 1) * BL, by = (b.BlockUR + 1) * BL;
                        double d = calDistance(pDR, pUR, bx, by);
                        if (d < bestTowerDist) { bestTowerDist = d; anchorX = bx; anchorY = by; }
                    }
            }
            double dAnchor = calDistance(pDR, pUR, anchorX, anchorY);
            if (priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0 && dAnchor > 6 * BL) {
                // 卡死检测：记录点只在祭司真正挪窝后刷新——否则每次重发都刷新时间戳，
                // 45帧窗口永远走不满→priestNearTCTry 永不递增→永远重发同一被占落点。
                double pIssueMoved = calDistance(pDR, pUR, priestIssueDR, priestIssueUR);
                if (pIssueMoved > 1.0 * BL) {
                    priestNearTCTry = 0;
                    priestIssueDR = pDR; priestIssueUR = pUR; priestIssueFrame = frame;
                } else if (priestIssueFrame > -999999 && frame - priestIssueFrame > 45) {
                    if (priestNearTCTry + 1 < 24) priestNearTCTry++;
                    priestIssueFrame = frame;   // 该档重新计时
                }
                // 多半径×多角度找锚点旁可走点({4,7,10}格×8角=24档)，环形扫描取首个未被占据的落点
                const double R[3] = {4.0, 7.0, 10.0};
                const int NA = 8;
                int start = priestNearTCTry; if (start >= 24) start = 23;
                double tx = anchorX, ty = anchorY;
                for (int k = 0; k < 24; ++k) {
                    int idx = start + k; if (idx >= 24) idx -= 24;
                    int ri = idx / NA; if (ri > 2) ri = 2;
                    int ai = idx % NA;
                    double ang = (double)ai * 3.141592653589793 / 4.0;
                    double candX = anchorX + std::cos(ang) * R[ri] * BL;
                    double candY = anchorY + std::sin(ang) * R[ri] * BL;
                    candX = max(0.0, min((double)MAP_L * BL, candX));
                    candY = max(0.0, min((double)MAP_U * BL, candY));
                    tx = candX; ty = candY;
                    if (!occupiedLanding(candX, candY)) break;
                }
                HumanMove(priestSN, tx, ty);
                priestMoveCooldown = 15;
                if (frame % 50 == 0)
                    DebugText(QString("Priest RETURN-TOWER dA=%1 anchor=(%2,%3)")
                              .arg(dAnchor / BL, 0, 'f', 0)
                              .arg(anchorX / BL, 0, 'f', 0)
                              .arg(anchorY / BL, 0, 'f', 0));
                return;
            }
        }
        return;
    }
    // ★ 2026-09-05 死代码清理：本函数「统一生存/感化决策块」（690 行裸 `{` 起，1046 行 `}` 止）
    //   末尾是无条件 return，其下原有约 215 行代码永不执行，已删除。被删段落：
    //     优先级1 W1感化 / 优先级2 反攻感化武器厂 / 优先级3 W2·W3感化 /
    //     优先级4 迎敌感化·冷却中治友军 / 优先级4.5 冷却中治友军 / 优先级5 守TC旁
    //   功能均未丢失：① 感化由上述统一决策块全量覆盖；
    //                 ② 反攻感化武器厂另有活实现在 manageCounterAttack 内(findEnemyBuilding(BUILDING_SIEGE) 段)。
    //   ⚠ 改祭司逻辑请只动 690-1046 活代码块，勿在此处补代码（不会执行）。
}

// ============================================================
// 经济管理（农民生产 + 建筑 + 分配 + 科技）
// ============================================================
void UsrAI::manageEconomy() {
    // 1. 村民生产：有50食物就造人，冲到目标数量
    //    ★ 铜器升级条件已满足时优先升级：暂停造村民，把TC和食物留给升级指令
    auto center = findBuilding(BUILDING_CENTER);
    bool bronzeUpgradeReady = (info.civilizationStage < CIVILIZATION_BRONZEAGE && !hasUpgraded &&
                               info.Meat >= BUILDING_CENTER_UPGRADE_BRONZEAGE_FOOD &&
                               (state == EARLY_ECONOMY || state == DEFENSE_PREP ||
                                state == DEFENSE_WAVE1 || state == DEFENSE_WAVE2));
    if (center && center->Project == ACT_NULL && !bronzeUpgradeReady) {
        int farmerCount = 0;
        for (auto &f : info.farmers)
            if (f.FarmerSort == FARMERTYPE_FARMER) farmerCount++;

        int totalPop = info.farmers.size() + info.armies.size();
        int currentMaxFarmers = (frame < 13500) ? 16 : MAX_FARMERS;  // W2前限16农，优先升级
        if (farmerCount < currentMaxFarmers && totalPop < info.Human_MaxNum) {
            // ★ 铜器后：检查军事科技是否真的在研究中（已扣资源），而非乐观布尔值 ★
            // 乐观布尔值在 BuildingAction 发出时就设为 true，但资源尚未扣除
            // 必须查建筑的实际 Project 状态，确认科技已经"付款"正在执行
            bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
            int minFood = 50;
            if (postBronze) {
                // 检查阔剑/复合弓是否真的已启动（建筑 Project 非空）
                bool broadswordRunning = false;
                auto ac = findBuildingIncludingUnderConstruction(BUILDING_ARMYCAMP);
                if (ac && ac->Project == BUILDING_ARMYCAMP_UPGRADE_BROADSWORD)
                    broadswordRunning = true;

                bool compositeBowRunning = false;
                auto rng = findBuildingIncludingUnderConstruction(BUILDING_RANGE);
                if (rng && rng->Project == BUILDING_RANGE_UPGRADE_COMPOSITE_BOW)
                    compositeBowRunning = true;

                // 只有当真在研究中（已扣资源）才解锁农民生产
                bool militaryTechPaid = broadswordRunning || compositeBowRunning
                    || broadswordResearched || compositeBowResearched;

                // ★ 阔剑科技已封禁(DISABLE_BROADSWORD_TECH)，军事解锁改由复合弓科技承担，
                //   故食物预留额改为按复合弓科技真实食物成本 + 50 缓冲（不再硬编码 190=阔剑140+50）。
                if (!militaryTechPaid)
                    minFood = BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_FOOD + 50;

                if (frame % 50 == 0) {
                    DebugText(QString("[FARMER f=%1] postBr=%2 paid=%3(brRun=%4 cbRun=%5 brd=%6 cmp=%7) minFd=%8 meat=%9 fCnt=%10")
                        .arg(frame).arg((int)postBronze).arg((int)militaryTechPaid)
                        .arg((int)broadswordRunning).arg((int)compositeBowRunning)
                        .arg((int)broadswordResearched).arg((int)compositeBowResearched)
                        .arg(minFood).arg((int)info.Meat).arg(farmerCount));
                }
            }

            bool canResearchCB = false;
            if (postBronze && !compositeBowResearched && !compositeBowQueued) {
                auto rng = findBuilding(BUILDING_RANGE);
                if (rng && rng->Project == ACT_NULL &&
                    info.Meat >= BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_FOOD &&
                    info.Wood >= BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_WOOD) {
                    canResearchCB = true;
                }
            }
            if (info.Meat >= minFood && !canResearchCB) {
                DebugText(QString("!! PRODUCE FARMER f=%1 meat=%2 minFood=%3").arg(frame).arg((int)info.Meat).arg(minFood));
                BuildingAction(center->SN, BUILDING_CENTER_CREATEFARMER);
            }
        }
    }

    // 2. 建造管理
    manageBuildings();

    // 3. 分配空闲村民
    assignIdleFarmers();
    assignIdleSimple();

    // 4. 科技升级
    manageTechUpgrade();
}

// ============================================================
// 建造管理（PPT顺序：房屋→谷仓→市场→兵营→靶场→马厩→箭塔→学院）
// ============================================================
void UsrAI::manageBuildings() {
    releasedBuilders.clear();

    // 农场上限按“实际存在 + 已下发未回写”统计，不能因 deadBuildings 漏算而超建
    auto countFarmsForCap = [&]() {
        int cnt = 0;
        for (auto &b : info.buildings)
            if (b.Type == BUILDING_FARM) cnt++;
        for (auto &kv : pendingBuildIns)
            if (kv.second.second == BUILDING_FARM) cnt++;
        return cnt;
    };

    // ---- 废弃地基标记清理：已开始建造(Percent>0)或已不存在的建筑恢复有效 ----
    for (auto it = deadBuildings.begin(); it != deadBuildings.end(); ) {
        bool stillDead = false;
        for (auto &b : info.buildings) {
            if (b.SN == *it && b.Percent == 0) { stillDead = true; break; }
        }
        if (!stillDead) it = deadBuildings.erase(it); else ++it;
    }

    // ---- 建造者清理 ----
    // ★ 释放建造者：清空登记并标记本帧可重新分配
    auto releaseBuilder = [&](int sn) {
        releasedBuilders.insert(sn);
        builderIdleFrame.erase(sn);
    };
    for (auto it = buildingFarmerType.begin(); it != buildingFarmerType.end(); ) {
        int sn = it->first;
        int buildType = it->second;
        tagFarmer* f = nullptr;
        for (auto &x : info.farmers) {
            if (x.SN == sn) { f = &x; break; }
        }
        if (!f) {
            builderIdleFrame.erase(sn);
            buildRedispatchFrame.erase(sn);
            it = buildingFarmerType.erase(it);
            continue;
        }

        // ★ 定位该建造者正在建的建筑：优先按 WorkObjectSN 精确匹配，
        //   其次退化为"该类型里离他最近的在建建筑"（旧代码取"第一处在建"，
        //   多座同类地基并存时会把建造者绑到别人的地基上，造成互相抢/都建不完）。
        tagBuilding* myB = nullptr;
        for (auto &b : info.buildings)
            if (b.SN == f->WorkObjectSN && b.Type == buildType) { myB = &b; break; }
        if (!myB) {
            double bestD = 1e18;
            for (auto &b : info.buildings) {
                if (b.Type != buildType || b.Percent >= 100) continue;
                if (deadBuildings.count(b.SN)) continue;
                double d = calDistance(f->DR, f->UR, (b.BlockDR + 1) * BLOCKSIDELENGTH, (b.BlockUR + 1) * BLOCKSIDELENGTH);
                if (d < bestD) { bestD = d; myB = &b; }
            }
        }

        if (!myB || myB->Percent >= 100) {
            // ★ 指令刚下发、地基还没回写进 info.buildings（HumanBuild 是异步的）→
            //   此时绝不能释放登记：否则村民走到一半就被当成"空闲可采集"，
            //   地基从此无人施工、永久卡在"建设中"（房屋建不完/人口卡顶的根因）。
            bool pendingNow = false;
            for (auto &kv : pendingBuildIns)
                if (kv.second.first == sn && kv.second.second == buildType) { pendingNow = true; break; }
            if (pendingNow) { ++it; continue; }

            // 建筑已建成或已不存在 → 真正"建完才释放"
            releaseBuilder(sn);
            it = buildingFarmerType.erase(it);
            continue;
        }

        // 建造者正在施工（WORKING 且目标就是该建筑）→ 正常推进，保持登记
        bool working = (f->NowState == HUMAN_STATE_WORKING && f->WorkObjectSN == myB->SN);
        if (working) {
            builderIdleFrame.erase(sn);
            buildRedispatchFrame.erase(sn);
            ++it; continue;
        }

        // 建筑仍在进行：建造者若空闲（走到一半/被打断/卡顿），重新派它回去继续建，绝不中途释放去采集
        if (f->NowState == HUMAN_STATE_IDLE && f->Resource <= 0) {
            if (builderIdleFrame.find(sn) == builderIdleFrame.end())
                builderIdleFrame[sn] = frame;   // 首次空闲起累计（重派不重置）
            // 节流：每60帧重新下发建造指令，把它送回地基继续施工
            if (buildRedispatchFrame.find(sn) == buildRedispatchFrame.end() || frame - buildRedispatchFrame[sn] >= 60) {
                HumanBuild(sn, buildType, (int)myB->BlockDR, (int)myB->BlockUR);
                buildRedispatchFrame[sn] = frame;
            }
            // 累计空闲>15秒仍建不成 → 判定地基不可达/废弃，放弃并拉黑（避免死等浪费村民）
            if (frame - builderIdleFrame[sn] > 900) {
                deadBuildings.insert(myB->SN);
                if (!deadBuildingsFrame.count(myB->SN)) deadBuildingsFrame[myB->SN] = frame;
                releaseBuilder(sn);
                it = buildingFarmerType.erase(it);
                continue;
            }
            ++it; continue;
        }

        // 其他状态（WALKING/ATTACKING 等）：保持登记等待；不清除 builderIdleFrame，让其继续累计空闲时间
        ++it;
    }

    // ---- 孤儿地基抢救：在建(Percent<100)但没有任何村民在施工 → 补派村民，避免永久卡在"建设中" ----
    // 成因：建造者登记因异步回写/被打断/死亡而丢失后，原地基不会有任何代码再派人过去，
    //       而 houseBuildingInProgress 又把它算作"在建中"，于是新房也不建 → 人口卡顶。
    {
        for (auto &b : info.buildings) {
            if (b.Percent >= 100) continue;
            // 被判定为废弃地基(卡0%)的：宽限期内仍尝试换人补救；过了宽限期就放弃它、改由另建新址解决
            if (deadBuildings.count(b.SN)) {
                auto dit = deadBuildingsFrame.find(b.SN);
                if (dit != deadBuildingsFrame.end() && frame - dit->second > DEAD_BUILDING_GRACE) continue;
            }
            // 是否已有村民在干这个地基
            bool hasWorker = false;
            for (auto &f : info.farmers) {
                if (f.WorkObjectSN == b.SN) { hasWorker = true; break; }
                // 刚下发指令、WorkObjectSN 尚未回写的同类型建造者：也算有人在管
                auto bt = buildingFarmerType.find(f.SN);
                if (bt != buildingFarmerType.end() && bt->second == b.Type && f.WorkObjectSN <= 0) {
                    hasWorker = true; break;
                }
            }
            if (hasWorker) continue;
            // 同一地基的重派节流（不reset，避免卡住时每帧刷指令）
            auto oit = orphanBuildFrame.find(b.SN);
            if (oit != orphanBuildFrame.end() && frame - oit->second < ORPHAN_REDISPATCH_CD) continue;
            // 只调空闲村民，没有就本帧不抢人（优先保证采集/建造主流程）
            auto f = findIdleFarmer();
            if (!f) break;
            buildingFarmerType[f->SN] = b.Type;
            HumanBuild(f->SN, b.Type, (int)b.BlockDR, (int)b.BlockUR);
            orphanBuildFrame[b.SN] = frame;
            if (frame % 60 == 0)
                DebugText(QString("[ORPHAN f=%1] 地基SN=%2 type=%3 percent=%4 补派村民SN=%5")
                          .arg(frame).arg(b.SN).arg(b.Type).arg(b.Percent).arg(f->SN));
            break;   // 每帧最多救 1 个，防止指令刷屏
        }
    }

    bool builtThisFrame = false;
    int humanPop = info.farmers.size() + info.armies.size();
    int houseCount = countBuildingsAll(BUILDING_HOME);
    bool houseBuildingInProgress = false;
    for (auto &b : info.buildings) {
        if (b.Type == BUILDING_HOME && b.Percent < 100 && !deadBuildings.count(b.SN)) { houseBuildingInProgress = true; break; }
    }
    bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
    bool upgradeStarted = (state == UPGRADING || postBronze);

    bool preW1 = (frame < WAVE1_TIME);
    bool postW1 = (frame >= WAVE1_TIME && frame < WAVE2_TIME);
    bool postW2 = (frame >= WAVE2_TIME);

    // ====== 第一波前：房屋→兵营（工具时代就能建），不建其他 ======
    if (preW1) {
        // 人口余量≤POP_HEADROOM_BUILD(=人口上限-2)时补房屋
        bool popHeadroomLow = (info.Human_MaxNum - humanPop <= POP_HEADROOM_BUILD);
        if (!builtThisFrame && houseCount < MAX_HOUSES && !houseBuildingInProgress && popHeadroomLow &&
            info.Wood >= BUILD_HOUSE_WOOD) {
            builtThisFrame = tryBuild(BUILDING_HOME, 2);
        }
        // 有房屋后尽早造兵营（木材够就建，不等人满）
        if (!builtThisFrame && countBuildingsExisting(BUILDING_ARMYCAMP) == 0 &&
            houseCount >= 1 && info.Wood >= BUILD_ARMYCAMP_WOOD) {
            builtThisFrame = tryBuild(BUILDING_ARMYCAMP, 3);
        }
        // ★ 兵营建好后立刻建靶场（工具时代即可，不等铜器）
        if (!builtThisFrame && countBuildingsExisting(BUILDING_RANGE) == 0 &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_RANGE_WOOD) {
            builtThisFrame = tryBuild(BUILDING_RANGE, 3);
        }
    }

    // ====== 第一波后~第二波前：铜器启动即优先军事（工具时代就能建兵营） ======
    if (postW1) {
        bool rushMilitary = (upgradeStarted && frame < 16500 && !wave2Defeated);  // 升级已启动即可建兵营

        // ★ 瞪羚群中心仓库（缩短猎人运输）：每局仅建 1 座，建在最密集瞪羚群的中心。
        //   ★ 2026-09-04 优化（响应"13 分钟才建太晚"反馈）：原代码位置在 postW1 的 else 分支里、且
        //     排在市场/箭塔/靶场/马厩之后，窗口(5~9 分钟)被这些抢 builtThisFrame → 仓库从未建出，
        //     猎人空跑 TC↔瞪羚群 8+ 分钟。
        //     修复：①窗口延伸到 5~11 分钟(frame<16500，与 rushMilitary 截止同步)；
        //           ②加 huntingGroup 非空前置（猎人已开始工作→仓库才有意义，避免 0 猎人时建空仓库）；
        //           ③提到 else 分支最前面（在市场/箭塔/靶场/马厩之前），rushMilitary 时不建。
        //   ★ 建的是 BUILDING_STOCK 而非谷仓（2026-09-03 用户纠正）：瞪羚打猎产物 ProductSort=HUMAN_STOCKFOOD
        //     (Core.cpp:506)，只能交付给仓库 BUILDING_STOCK (Building.cpp:549)。
        //   ★ 2026-09-04 三改：即使 30 格内有现成仓库(init 开局给的/上一局遗留),只要 MAX_STOCK 还有
        //     余地就【仍要尝试在瞪羚中心建一座】,让猎人始终能就近交付——而不是依赖"已有库存"提前解锁农场闸。
        //     否则猎人空跑 30+ 格仍回老仓库,既不缩短运输,也违反"在瞪羚中心仓库前不要建农场"的语义。
        if (!rushMilitary && !builtThisFrame && storageNearGazelleBuilt == 0 &&
            frame < 16500 && !huntingGroup.empty() && info.Wood >= BUILD_STOCK_WOOD) {
            double BL = (double)BLOCKSIDELENGTH;
            // 收集所有存活瞪羚
            std::vector<tagResource*> gaz;
            for (auto &r : info.resources)
                if (r.Type == RESOURCE_GAZELLE && r.Cnt > 0) gaz.push_back(&r);
            if (!gaz.empty()) {
                // 6 格邻域聚类，取数量最多的群（不取距 TC 最近的群），求该群 DR/UR 几何中心 = 仓库位置
                double bestSumDR = 0, bestSumUR = 0; int bestCnt = 0;
                for (auto seed : gaz) {
                    double sumDR = 0, sumUR = 0; int cnt = 0;
                    for (auto g : gaz)
                        if (calDistance(seed->DR, seed->UR, g->DR, g->UR) < 6 * BL) {
                            sumDR += g->DR; sumUR += g->UR; cnt++;
                        }
                    if (cnt > bestCnt) { bestCnt = cnt; bestSumDR = sumDR; bestSumUR = sumUR; }
                }
                if (bestCnt > 0) {
                    double centerDR = bestSumDR / bestCnt, centerUR = bestSumUR / bestCnt;
                    // 已有仓库在 30 格内则不重复建。
                    //   ★ 2026-09-04 修：这种情况下直接置 storageNearGazelleBuilt=1 视为"已被前置库存覆盖"
                    //     ——否则地图初始已有仓库时,tryBuild 被 nearStock 跳过、标志位永远停在 0,
                    //     农场闸靠 storageNearGazelleBuilt==1 永远不解锁。
                    bool nearStock = false;
                    for (auto &b : info.buildings)
                        if (b.Type == BUILDING_STOCK && b.Percent == 100 &&
                            // ★ 2026-09-04 覆盖半径放宽：30→GAZELLE_HUNT_RANGE(50) 格，与猎人选取同步
                            calDistance(centerDR, centerUR, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL) < GAZELLE_HUNT_RANGE * BL) {
                            nearStock = true; break;
                        }
                    int tBlockDR = (int)(centerDR / BL) - 1;
                    int tBlockUR = (int)(centerUR / BL) - 1;
                    if (!nearStock) {
                        // 30 格内没有现成仓库 → 直接在瞪羚中心建
                        if (tryBuild(BUILDING_STOCK, 3, false, tBlockDR, tBlockUR)) {
                            storageNearGazelleBuilt = 1;
                            builtThisFrame = true;
                        }
                    } else if (countBuildingsExisting(BUILDING_STOCK) < MAX_STOCK) {
                        // 30 格内已有现成仓库(初始化开局/上一局遗留) —— 但 MAX_STOCK 还有余地(MAX=2)
                        // ★ 仍要尝试在瞪羚【中心】补一座,让猎人始终能就近交付瞪羚肉
                        if (tryBuild(BUILDING_STOCK, 3, false, tBlockDR, tBlockUR)) {
                            storageNearGazelleBuilt = 1;
                            builtThisFrame = true;
                        } else {
                            // 地基不可建(被占/塌方) → 既然地图上已有仓库、只是不在瞪羚中心,
                            // 也算"已有前置覆盖",解锁农场闸,避免永远不建农场导致食物枯竭
                            storageNearGazelleBuilt = 1;
                        }
                    } else {
                        // 已达 MAX_STOCK=2 上限 —— 直接解锁农场闸,不再尝试建
                        storageNearGazelleBuilt = 1;
                    }
                }
            }
        }

        if (rushMilitary) {
            // ★ 铜器后军事优先：兵营→靶场→阔剑科技，不建市场农场
            if (!builtThisFrame && countBuildingsExisting(BUILDING_ARMYCAMP) == 0 &&
                info.Wood >= BUILD_ARMYCAMP_WOOD) {
                builtThisFrame = tryBuild(BUILDING_ARMYCAMP, 3);
            }
            if (!builtThisFrame && countBuildingsExisting(BUILDING_RANGE) == 0 &&
                countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_RANGE_WOOD) {
                builtThisFrame = tryBuild(BUILDING_RANGE, 3);
            }
            // 人口余量≤POP_HEADROOM_BUILD(=人口上限-2)时补房屋
            bool popHeadroomLow = (info.Human_MaxNum - humanPop <= POP_HEADROOM_BUILD);
            if (!builtThisFrame && houseCount < MAX_HOUSES && !houseBuildingInProgress && popHeadroomLow &&
                info.Wood >= BUILD_HOUSE_WOOD) {
                builtThisFrame = tryBuild(BUILDING_HOME, 2);
            }
        } else {
            // ★ 铜器前/11分钟后/W2结束后：正常市场→农场
            bool canAffordBuilding = (info.Meat >= 80 && info.Wood >= 50);

            // ★ 检测基地附近浆果是否耗尽（耗尽则提前建市场+农场）
            int nearBushFood = 0;
            {
                double bBL = (double)BLOCKSIDELENGTH;
                auto bCenter = findBuilding(BUILDING_CENTER);
                double btcDR = bCenter ? (bCenter->BlockDR + 1) * bBL : 0;
                double btcUR = bCenter ? (bCenter->BlockUR + 1) * bBL : 0;
                for (auto &r : info.resources)
                    if (r.Type == RESOURCE_BUSH && r.Cnt > 0)
                        if (calDistance(btcDR, btcUR, r.DR, r.UR) < 30 * bBL) nearBushFood += r.Cnt;
            }

            if (!builtThisFrame && canAffordBuilding &&
                countBuildingsExisting(BUILDING_MARKET) == 0 && countBuildingsExisting(BUILDING_GRANARY) == 0 &&
                info.Wood >= BUILD_GRANARY_WOOD && !DISABLE_GRANARY_BUILD) {
                builtThisFrame = tryBuild(BUILDING_GRANARY, 3);
            }
            if (!builtThisFrame && canAffordBuilding &&
                countBuildingsExisting(BUILDING_MARKET) == 0 &&
                countBuildingsExisting(BUILDING_GRANARY) >= 1 && info.Wood >= 150 && info.Meat >= 100) {  // 造市场（已去掉所有限制条件）
                builtThisFrame = tryBuild(BUILDING_MARKET, 3);
            }

            // ★ 箭塔优先于农场：石头够就造（数量上限 MAX_TOWERS）。
            //   反攻阶段(游戏时间≥14分钟=WAVE3_TIME)起不再新建箭塔——反攻应集中资源爆兵推进。
            if (!builtThisFrame && towerCount < MAX_TOWERS && frame < WAVE3_TIME &&
                info.Stone >= 150) {
                builtThisFrame = tryBuild(BUILDING_ARROWTOWER, 2);
                if (builtThisFrame) towerCount++;
            }

            // ★ 靶场优先于农场：兵营已有、木材够就建（不等铜器）
            if (!builtThisFrame && countBuildingsExisting(BUILDING_RANGE) == 0 &&
                countBuildings(BUILDING_ARMYCAMP) >= 1 &&
                info.Wood >= BUILD_RANGE_WOOD) {
                builtThisFrame = tryBuild(BUILDING_RANGE, 3);
            }

            // ★ 马厩（postW1 经济阶段即可建：兵营已有 + 木材≥150 就建；学院前置需马厩，故早于学院）
            if (!builtThisFrame && countBuildingsExisting(BUILDING_STABLE) == 0 &&
                countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_STABLE_WOOD && !DISABLE_STABLE_BUILD) {
                builtThisFrame = tryBuild(BUILDING_STABLE, 3);
            }

            bool marketReady = (countBuildings(BUILDING_MARKET) >= 1);
// ★ 农场：市场已建 + 木材/食物够才建。
        //   2026-09-04 用户新需求："在建造瞪羚中心谷仓前不要建农场"——
        //   ★ 注：瞪羚中心实际建的是【仓库 BUILDING_STOCK】（2026-09-03 纠正：瞪羚肉 ProductSort=HUMAN_STOCKFOOD
        //     交付仓库，不是谷仓 GRANARY），故此处闸用 storageNearGazelleBuilt == 1。
        //   ★ 强制约束：仓库建好前不允许建农场——避免农民先造农场后仓库才落地，
        //     期间猎人空跑 TC↔瞪羚群（仓库未建的窗口期农场抢食物资源没意义）。
        // ★ 2026-09-04 又修"初始已有一仓库不能解锁农场"反馈：原条件 `storageNearGazelleBuilt == 1` 是 AI
        //   自己 `tryBuild` 成功才置 1 的开关——地图初始已存在仓库时,1547 段会算"30 格内有库存→nearStock=true→
        //   tryBuild 跳过" → **storageNearGazelleBuilt 永远停在 0** → 农场闸永远卡死。
        //   放宽：地图上【任意】一座我方仓库即可解锁农场(初始/已建/试建失败但已有库存,都视为满足前置)。
if (!builtThisFrame && marketReady && storageNearGazelleBuilt == 1 &&
                info.Wood >= FARM_WOOD_NEED(storageNearGazelleBuilt == 1) && info.Meat >= 100) {
            int currentFarms = countFarmsForCap();
                int farmerCount = 0;
                for (auto &f : info.farmers)
                    if (f.FarmerSort == FARMERTYPE_FARMER) farmerCount++;
                int targetFarms = std::max(0, farmerCount - 2);
                targetFarms = std::min(targetFarms, MAX_FARMS);
                if (currentFarms < targetFarms) {
                    builtThisFrame = tryBuild(BUILDING_FARM, 3);
                }
            }

            bool popHeadroomLow = (info.Human_MaxNum - humanPop <= POP_HEADROOM_BUILD);
            if (!builtThisFrame && houseCount < MAX_HOUSES && !houseBuildingInProgress && popHeadroomLow &&
                info.Wood >= BUILD_HOUSE_WOOD) {
                builtThisFrame = tryBuild(BUILDING_HOME, 2);
            }
        }
    }

    // ====== 第二波后：正常军事建筑 ======
    if (postW2) {
        // 房屋：人口余量≤POP_HEADROOM_BUILD(=人口上限-2)时优先补，不军事建筑木材预留挤掉，
        // 否则人口将满时村民/军队会卡住无法训练。
        bool popHeadroomLow = (info.Human_MaxNum - humanPop <= POP_HEADROOM_BUILD);
        if (!builtThisFrame && houseCount < MAX_HOUSES && !houseBuildingInProgress && popHeadroomLow &&
            info.Wood >= BUILD_HOUSE_WOOD) {
            builtThisFrame = tryBuild(BUILDING_HOME, 2);
        }

        // 谷仓
        if (!builtThisFrame && countBuildingsExisting(BUILDING_GRANARY) == 0 &&
            info.Wood >= BUILD_GRANARY_WOOD && !DISABLE_GRANARY_BUILD) {
            builtThisFrame = tryBuild(BUILDING_GRANARY, 3);
        }

        // ★ 第二仓库的"是否需要建"预判定（2026-09-05）：市场闸前置，避免远距瞪羚存在时市场抢 builtThisFrame
        //   而第二仓库被架空（前置条件过于严苛时每帧 tryBuild 失败 → 下一建筑接力 = 历史上"农场被饿死"同源问题）。
        //   needSecondStock = true 当：仓库数<MAX_STOCK 且 已过兜底时机(>WAVE2_TIME+1500) 且 存在"距 TC>20 且 距所有现有 Stock>20"的远距瞪羚。
        //   性能：单帧仅扫到第一个满足条件的瞪羚就 break（瞪羚≤30 / 仓库≤3 / 单帧成本 O(90)）。
        bool needSecondStock = false;
        if (countBuildingsExisting(BUILDING_STOCK) < MAX_STOCK && frame > WAVE2_TIME + 1500) {
            auto centerP = findBuilding(BUILDING_CENTER);
            if (centerP) {
                double BLp = (double)BLOCKSIDELENGTH;
                double tcDRp = (centerP->BlockDR + 1) * BLp;
                double tcURp = (centerP->BlockUR + 1) * BLp;
                for (auto &r : info.resources) {
                    if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) continue;
                    if (calDistance(tcDRp, tcURp, r.DR, r.UR) < 20 * BLp) continue;
                    bool nearAnyStock = false;
                    for (auto &b : info.buildings) {
                        if (b.Type == BUILDING_STOCK && b.Percent == 100) {
                            double gDR = (b.BlockDR + 1) * BLp;
                            double gUR = (b.BlockUR + 1) * BLp;
                            if (calDistance(r.DR, r.UR, gDR, gUR) < 20 * BLp) {
                                nearAnyStock = true; break;
                            }
                        }
                    }
                    if (!nearAnyStock) { needSecondStock = true; break; }
                }
            }
        }

        // ★ 第二仓库：为"距现有Stock均>20格的远距瞪羚群"建一座，仓库落在群中心
        //   ★ 2026-09-04 修：旧版三个缺陷导致贴 TC 多建 3 座——
        //     ① 缺 MAX_STOCK 上限；② 每帧 if(!builtThisFrame) tryBuild(...),木材一回就再发令；③ tryBuild(BUILDING_STOCK,3) 不传坐标,
        //     走默认 findBuildSite 落 TC 附近空地,故多座都贴 TC。
        //     修复：加 MAX_STOCK 闸 + 复用 1597 段几何中心算法传 prefX/prefY，让仓库真落远距瞪羚群中心而非 TC。
        //   ★ 2026-09-04 又修：兜底时机 wave2Defeated(13.67 分钟)太迟——若第一仓库（5~11分钟窗口）失败，
        //     猎人空跑到 13 分钟才有兜底仓库。改为 frame > WAVE2_TIME + 1500(10 分钟)兜底。
        if (!builtThisFrame && countBuildingsExisting(BUILDING_STOCK) < MAX_STOCK &&
            frame > WAVE2_TIME + 1500 && info.Wood >= BUILD_STOCK_WOOD + 30) {
            auto center = findBuilding(BUILDING_CENTER);
            double BL = (double)BLOCKSIDELENGTH;
            double tcDR = center ? (center->BlockDR + 1) * BL : 0;
            double tcUR = center ? (center->BlockUR + 1) * BL : 0;
            // 收集"距 TC>20 且 距所有现有 Stock>20"的瞪羚
            std::vector<std::pair<double,double>> farGaz;
            for (auto &r : info.resources) {
                if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) continue;
                if (calDistance(tcDR, tcUR, r.DR, r.UR) < 20 * BL) continue;
                bool farFromStock = true;
                for (auto &b : info.buildings) {
                    if (b.Type == BUILDING_STOCK && b.Percent == 100) {
                        double gDR = (b.BlockDR + 1) * BL;
                        double gUR = (b.BlockUR + 1) * BL;
                        if (calDistance(r.DR, r.UR, gDR, gUR) < 20 * BL) {
                            farFromStock = false; break;
                        }
                    }
                }
                if (farFromStock) farGaz.emplace_back(r.DR, r.UR);
            }
            if (!farGaz.empty()) {
                // ★ 复用 1597 段的"最密群 + 几何中心"算法：6 格邻域聚类，取最大群中心 = 仓库位置
                double bestSumDR = 0, bestSumUR = 0; int bestCnt = 0;
                for (auto &seed : farGaz) {
                    double sumDR = 0, sumUR = 0; int cnt = 0;
                    for (auto &g : farGaz)
                        if (calDistance(seed.first, seed.second, g.first, g.second) < 6 * BL) {
                            sumDR += g.first; sumUR += g.second; cnt++;
                        }
                    if (cnt > bestCnt) { bestCnt = cnt; bestSumDR = sumDR; bestSumUR = sumUR; }
                }
                if (bestCnt > 0 && info.Wood >= BUILD_STOCK_WOOD) {
                    double centerDR = bestSumDR / bestCnt, centerUR = bestSumUR / bestCnt;
                    int tBlockDR = (int)(centerDR / BL) - 1;
                    int tBlockUR = (int)(centerUR / BL) - 1;
                    // ★ 关键：传坐标。仓库将落在远距瞪羚群中心，而非 TC 附近
                    builtThisFrame = tryBuild(BUILDING_STOCK, 3, false, tBlockDR, tBlockUR);
                }
            }
        }

        // 市场
        //   ★ 2026-09-05 加前置 !needSecondStock：远距瞪羚存在 + 仓库未满时不让市场抢 builtThisFrame
        //     （修"市场先于第二仓库落地"——同源问题：前置条件严苛→目标建筑被下游接力建出）
        if (!builtThisFrame && !needSecondStock &&
            countBuildingsExisting(BUILDING_MARKET) == 0 &&
            countBuildingsExisting(BUILDING_GRANARY) >= 1 && info.Wood >= 150) {  // 造市场（已去掉11分钟时间限制）
            builtThisFrame = tryBuild(BUILDING_MARKET, 3);
        }

        // 兵营
        if (!builtThisFrame && upgradeStarted && countBuildingsExisting(BUILDING_ARMYCAMP) == 0 &&
            info.Wood >= BUILD_ARMYCAMP_WOOD) {
            builtThisFrame = tryBuild(BUILDING_ARMYCAMP, 3);
        }

        // 靶场（不限铜器，兵营已有即可建）
        if (!builtThisFrame && countBuildingsExisting(BUILDING_RANGE) == 0 &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_RANGE_WOOD) {
            builtThisFrame = tryBuild(BUILDING_RANGE, 3);
        }

        // 箭塔：石头够就造（已解除 铜器/箭塔科技/兵营/靶场 前置；数量上限 MAX_TOWERS 保留）。
        //   反攻阶段(≥14分钟=WAVE3_TIME)起不再新建——资源转向爆兵反攻。
        if (!builtThisFrame && towerCount < MAX_TOWERS && frame < WAVE3_TIME &&
            info.Stone >= 150) {
            builtThisFrame = tryBuild(BUILDING_ARROWTOWER, 2);
            if (builtThisFrame) towerCount++;
        }

        // ★ 反攻多线产弓：游戏时间≥14分钟(=WAVE3_TIME)起增建靶场(最多 MAX_RANGES 座)，
        //   形成并行产线，弓兵产量随靶场数线性提升。木材留 80 余量避免饿死房屋/马厩。
        if (!builtThisFrame && frame >= WAVE3_TIME &&
            countBuildingsExisting(BUILDING_RANGE) < MAX_RANGES &&
            info.Wood >= BUILD_RANGE_WOOD + 80) {
            builtThisFrame = tryBuild(BUILDING_RANGE, 3);
        }

        // ★ 马厩（postW2 反攻准备）：兵营已有 + 木材≥150 就建（同 postW1 段，已恢复建造，供学院前置）
        if (!builtThisFrame && countBuildingsExisting(BUILDING_STABLE) == 0 &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_STABLE_WOOD && !DISABLE_STABLE_BUILD) {
            builtThisFrame = tryBuild(BUILDING_STABLE, 3);
        }

        // ★ 学院：后期/反攻爆近战核心兵种(方阵兵=强力近战)。铜器后、兵营已建、且**马厩已建**(前置)才建，
        //   与靶场并列；建好后训练块检测学院存在即自动产方阵兵，配合"爆近战"反攻。
        //   2026-09-04 用户要求"暂时不建学院"：加 DISABLE_COLLAGE_BUILD 闸（同时方阵兵产线失效 → 反攻只剩复合弓兵）。
        if (!builtThisFrame && countBuildingsExisting(BUILDING_COLLAGE) == 0 && !DISABLE_COLLAGE_BUILD &&
            state >= COUNTERATTACK && countBuildings(BUILDING_ARMYCAMP) >= 1 &&
            countBuildingsExisting(BUILDING_STABLE) >= 1 &&   // ★ 学院前置：必须先建好马厩
            info.Wood >= BUILD_COLLAGE_WOOD + 30) {
            builtThisFrame = tryBuild(BUILDING_COLLAGE, 3);
            if (builtThisFrame) academyBuilt = true;
        }

        // 农场
        //   ★ 2026-09-06 用户要求「建造瞪羚的仓库前先不要建农场，预留120木头」：
        //     本块原先【完全没有】storageNearGazelleBuilt 闸，只有 Wood>=75；而本块处于 if(postW2)，
        //     postW2 自 WAVE2_TIME(13500, 9分钟) 起成立，瞪羚仓库窗口却要到 frame<16500(11分钟) 才结束
        //     ⇒ 9~11 分钟两者并存，农场抢光木材 → 瞪羚仓库永远建不出、猎人来回空跑。
        //     故补上与 1487 段一致的双重闸：瞪羚仓库已建 + 木材预留
        //     （★ 预留仅仓库【未】建成时生效，仓库已建则恢复原阈值，见 FARM_WOOD_NEED 宏注释）。
        if (!builtThisFrame && storageNearGazelleBuilt == 1) {
            int currentFarms = countFarmsForCap();
            if (currentFarms < farmTarget &&
                info.Wood >= FARM_WOOD_NEED(storageNearGazelleBuilt == 1)) {
                builtThisFrame = tryBuild(BUILDING_FARM, 3);
            }
        }
    }
}

// ============================================================
// 分配空闲村民采集（改进版：每帧2个 + 金矿 + 自动调整农场目标）
// ============================================================
void UsrAI::assignIdleFarmers() {
    frameFoodTargets.clear();  // ★ 每帧重置：防同帧多农民分配到同一目标
    frameBushCount.clear();    // ★ 每帧重置浆果每丛分配计数
    frameWoodCount.clear();  // ★ 每帧重置木材分配计数
    frameGazelleCount.clear(); // ★ 每帧重置瞪羚每只分配计数

    // ---- 动态计算农场目标 ----
    int bushFood = 0, huntFood = 0, nearBushFood = 0;
    {
        double bBL = (double)BLOCKSIDELENGTH;
        auto bCenter = findBuilding(BUILDING_CENTER);
        double btcDR = bCenter ? (bCenter->BlockDR + 1) * bBL : 0;
        double btcUR = bCenter ? (bCenter->BlockUR + 1) * bBL : 0;
        for (auto &r : info.resources) {
            if (r.Type == RESOURCE_BUSH) {
                bushFood += r.Cnt;
                if (calDistance(btcDR, btcUR, r.DR, r.UR) < 30 * bBL) nearBushFood += r.Cnt;
            }
            else if (r.Type == RESOURCE_GAZELLE || r.Type == RESOURCE_ELEPHANT)
                huntFood += r.Cnt;
        }
    }
    int totalWildFood = bushFood + huntFood;
    bool marketBuilt = (countBuildings(BUILDING_MARKET) >= 1);

    // ★ 农场策略：基地附近浆果耗尽时转农场；远处浆果不算
    if (nearBushFood > 0) {
        // 基地附近还有浆果，继续采野果
        farmTarget = 0;
    } else if (!marketBuilt) {
        farmTarget = 0;
    } else if (frame < 7500 && totalWildFood > 300) {
        // 5分钟前野生食物充足：不建农场
        farmTarget = 0;
    } else {
        // 缺食物(野生食物枯竭或肉库存告急)→全上农场(MAX_FARMS)；否则不建农场
        farmTarget = (totalWildFood < 300 || info.Meat < 200) ? MAX_FARMS : 0;
    }

    // ====== 祭司探路：8方向放射状，祭司视野远，覆盖更广 ======
    bool isWar = (state >= DEFENSE_WAVE1 && state <= DEFENSE_WAVE3);
    if (!isWar && state != COUNTERATTACK && scoutPhase < 16) {
        double BL = (double)BLOCKSIDELENGTH;

        // ★ 返回绕路：多半径×多角度螺旋（被石头/障碍堵住时逐级放大半径重试，降低死循环）★
        const int SCOUT_RETURN_RADII[3] = {4, 7, 10};   // 单位 BL
        const int SCOUT_RETURN_ANGLES = 8;
        const int SCOUT_RETURN_MAX = SCOUT_RETURN_ANGLES * 3;  // 共 24 次尝试
        auto scoutReturnPoint = [&](int tryN, double bDR, double bUR, double& wx, double& wy) {
            int a = tryN % SCOUT_RETURN_ANGLES;
            int r = tryN / SCOUT_RETURN_ANGLES; if (r > 2) r = 2;
            double ra = (double)a * 3.141592653589793 / 4.0;
            double R = SCOUT_RETURN_RADII[r] * BL;
            wx = bDR + std::cos(ra) * R;
            wy = bUR + std::sin(ra) * R;
            wx = max(0.0, min((double)MAP_L * BL, wx));
            wy = max(0.0, min((double)MAP_U * BL, wy));
        };

        if (scoutCooldown > 0) scoutCooldown--;

        // ★ 探路结束条件（2026-09-03 用户改）：不再因"发现黄金/瞪羚/浆果(树)"就提前停止，
        //   而是探完全部 8 个外向方向(scoutDirsDone>=8)才结束探路、回 TC 待命。
        //   (到达某方向终点(nearTarget)时 scoutDirsDone++，见下方 2076 行附近。)
        if (scoutDirsDone >= 8) {
            scoutPhase = 20;  // 8 方向探完 → 结束探路，回 TC 待命
        }

        // 验证祭司是否还活着
        if (priestSN != -1) {
            bool alive = false;
            for (auto &a : info.armies) {
                if (a.SN == priestSN && a.Sort == AT_PRIEST) {
                    alive = true; break;
                }
            }
            if (!alive) { priestSN = -1; scoutWalkTimer = 0; }
        }

        // 祭司不存在→无法探路
        if (priestSN == -1) {
            scoutPhase = 20;  // 释放探路状态
        }

        // 发探路移动指令
        if (priestSN != -1 && scoutPhase < 16) {
            tagArmy* scout = nullptr;
            for (auto &a : info.armies) {
                if (a.SN == priestSN) { scout = &a; break; }
            }

            // ★ 每帧检测：敌方军队→回TC换方向；野兽/敌村民→逃12格（禁止感化！）
            bool fledThisFrame = false;
            if (scout) {
                auto center = findBuilding(BUILDING_CENTER);
                double tcDR = center ? (center->BlockDR + 1) * BL : scout->DR;
                double tcUR = center ? (center->BlockUR + 1) * BL : scout->UR;

                double beastDist = 12 * BL, beastX = scout->DR, beastY = scout->UR;
                bool beastNearby = false;
                double enemyDist = 12 * BL;
                bool enemyNearby = false;

                // 野兽
                for (auto &r : info.resources) {
                    if (r.Cnt <= 0) continue;
                    if (r.Type != RESOURCE_LION && r.Type != RESOURCE_ELEPHANT) continue;
                    double d = calDistance(scout->DR, scout->UR, r.DR, r.UR);
                    if (d < beastDist) { beastDist = d; beastX = r.DR; beastY = r.UR; beastNearby = true; }
                }
                // 敌方军队
                for (auto &e : info.enemy_armies) {
                    if (e.Blood <= 0) continue;
                    double d = calDistance(scout->DR, scout->UR, e.DR, e.UR);
                    if (d < enemyDist) { enemyDist = d; enemyNearby = true; }
                }
                // 敌方村民
                for (auto &e : info.enemy_farmers) {
                    if (e.Blood <= 0) continue;
                    double d = calDistance(scout->DR, scout->UR, e.DR, e.UR);
                    if (d < beastDist) { beastDist = d; beastX = e.DR; beastY = e.UR; beastNearby = true; }
                }

                if (scout->NowState != HUMAN_STATE_WALKING) {
                    if (enemyNearby) {
                        // ★ 发现敌军→立刻回TC，跳过此方向（下一轮探另一方向）
                        // 遇敌返回：移到TC旁空地（避开建筑中心/石头），用多半径螺旋绕路
                        double rx = 0, ry = 0;
                        scoutReturnPoint(scoutReturnTry, tcDR, tcUR, rx, ry);
                        HumanMove(scout->SN, rx, ry);
                        scoutIssueDR = scout->DR; scoutIssueUR = scout->UR; scoutIssueFrame = frame;
                        scoutPhase++;
                        if (scoutPhase >= 16) scoutPhase = 20;  // 探完→结束探路回TC待命
                        scoutReturnTry = 0;
                        scoutCooldown = 20;
                        scoutWalkTimer = 0;
                        fledThisFrame = true;
                    } else if (beastNearby) {
                        // ★ 野兽→远离12格，继续当前方向
                        double awayDX = scout->DR - beastX;
                        double awayDY = scout->UR - beastY;
                        double awayLen = std::sqrt(awayDX*awayDX + awayDY*awayDY);
                        if (awayLen < 0.01) { awayDX = 1; awayDY = 0; awayLen = 1; }
                        double tx = scout->DR + (awayDX / awayLen) * 12 * BL;
                        double ty = scout->UR + (awayDY / awayLen) * 12 * BL;
                        tx = max(0.0, min((double)MAP_L * BL, tx));
                        ty = max(0.0, min((double)MAP_U * BL, ty));
                        HumanMove(scout->SN, tx, ty);
                        scoutIssueDR = scout->DR; scoutIssueUR = scout->UR; scoutIssueFrame = frame;
                        scoutCooldown = 30;
                        scoutWalkTimer = 0;
                        fledThisFrame = true;
                    }
                }
            }

            if (!fledThisFrame) {
            if (scoutCooldown > 0) { /* 冷却中且无威胁→等待 */ }
            else {
            // 走路计时：走路+1，空闲清零。超1200帧(48秒)=不可达→跳过
            if (scout) {
                if (scout->NowState == HUMAN_STATE_WALKING) scoutWalkTimer++;
                else scoutWalkTimer = 0;
            }
            // ★ 关键修复：目标不可达时祭司保持 IDLE（不进入 WALKING），
            //   原 scoutWalkTimer 永远为0、scoutLegStartFrame 又被每帧重发重置，
            //   卡死检测失效→scoutReturnTry 不前进→同一不可达点无限重发。
            //   改用"下发移动指令后祭司实际没挪窝"的位置进度检测，即使 IDLE 也能识别卡死。
            double scoutIssueMoved = calDistance(scout->DR, scout->UR, scoutIssueDR, scoutIssueUR);
            bool noProgress = (scoutIssueFrame > -999999) && (frame - scoutIssueFrame > 20) && (scoutIssueMoved < 1.0 * BL);
            bool scoutStuck = (scoutWalkTimer > 1200 || noProgress ||
                               (scoutLegStartFrame > 0 && frame - scoutLegStartFrame > 2000));

            if (scoutStuck) {
                bool stuckInReturn = (scoutPhase % 2 == 1);  // 奇数=返回阶段
                if (stuckInReturn && scoutReturnTry + 1 < SCOUT_RETURN_MAX) {
                    // ★ 返回被石头堵→多半径×多角度螺旋重试绕路（逐级放大半径），不放弃返回
                    scoutReturnTry++;
                    scoutWalkTimer = 0;
                    scoutLegStartFrame = frame;
                    scoutCooldown = 5;
                } else if (stuckInReturn) {
                    // 返回8个角度都失败→放弃返回，交给 managePriest 回TC旁（多半径螺旋绕路，避免卡在建筑中心）
                    scoutPhase = 20;
                    scoutReturnTry = 0;
                    priestNearTCTry = 0;  // 重置守TC旁绕路计数，从角度0重新尝试
                    scoutWalkTimer = 0;
                    scoutIssueFrame = -999999;  // 重置，避免 managePriest 误判卡死
                    scoutCooldown = 10;
                } else if (scoutReturnTry + 1 < 8) {
                    // 外出探路被挡→先左右偏转绕障（档位越大偏角越大），不急着放弃这个方向
                    scoutReturnTry++;
                    scoutWalkTimer = 0;
                    scoutLegStartFrame = frame;
                    scoutCooldown = 5;
                } else {
                    // 绕障8次仍不通（石头/地图边缘/建筑挡死）→放弃此方向，换下一个外向方向继续探
                    scoutPhase++;
                    if (scoutPhase >= 16) scoutPhase = 20;  // 探完→结束探路回TC待命
                    scoutReturnTry = 0;
                    scoutWalkTimer = 0;
                    scoutLegStartFrame = frame;
                    scoutCooldown = 10;
                }
            } else if (scout && (scout->NowState == HUMAN_STATE_ATTACKING || scout->NowState == HUMAN_STATE_WORKING)) {
                // ★ 探路中被野兽/敌人纠缠→远离最近的威胁（禁止感化！保命+继续探路优先）
                double fleeX = scout->DR, fleeY = scout->UR;
                double nearestDist = 1e12;
                // 检查野兽威胁
                for (auto &r : info.resources) {
                    if (r.Cnt <= 0) continue;
                    if (r.Type != RESOURCE_LION && r.Type != RESOURCE_ELEPHANT) continue;
                    double d = calDistance(scout->DR, scout->UR, r.DR, r.UR);
                    if (d < nearestDist) { nearestDist = d; fleeX = r.DR; fleeY = r.UR; }
                }
                // 检查敌方军队威胁（包括正在被感化的敌人）
                for (auto &e : info.enemy_armies) {
                    if (e.Blood <= 0) continue;
                    double d = calDistance(scout->DR, scout->UR, e.DR, e.UR);
                    if (d < nearestDist) { nearestDist = d; fleeX = e.DR; fleeY = e.UR; }
                }
                // 检查敌方村民威胁
                for (auto &e : info.enemy_farmers) {
                    if (e.Blood <= 0) continue;
                    double d = calDistance(scout->DR, scout->UR, e.DR, e.UR);
                    if (d < nearestDist) { nearestDist = d; fleeX = e.DR; fleeY = e.UR; }
                }
                // 远离最近威胁，跑12格
                double awayDX = scout->DR - fleeX;
                double awayDY = scout->UR - fleeY;
                double awayLen = std::sqrt(awayDX*awayDX + awayDY*awayDY);
                if (awayLen < 0.01) { awayDX = 1; awayDY = 0; awayLen = 1; }
                double tx = scout->DR + (awayDX / awayLen) * 12 * BL;
                double ty = scout->UR + (awayDY / awayLen) * 12 * BL;
                tx = max(0.0, min((double)MAP_L * BL, tx));
                ty = max(0.0, min((double)MAP_U * BL, ty));
                HumanMove(scout->SN, tx, ty);
                scoutIssueDR = scout->DR; scoutIssueUR = scout->UR; scoutIssueFrame = frame;
                scoutCooldown = 30;
                scoutWalkTimer = 0;
            } else if (scout && scout->NowState == HUMAN_STATE_IDLE) {
                auto center = findBuilding(BUILDING_CENTER);
                if (center) {
                    double baseDR = (center->BlockDR + 1) * BL;
                    double baseUR = (center->BlockUR + 1) * BL;
                    double sDR = scout->DR, sUR = scout->UR;

                    // 地图四边边缘坐标
                    double edgeWest  = 0;
                    double edgeEast  = MAP_L * BL;
                    double edgeSouth = 0;
                    double edgeNorth = MAP_U * BL;

                    bool nearTarget = false;
                    const double SCOUT_DIST = 100.0;  // 探索半径扩大到100格，覆盖整张地图(100x100)边缘

                    // ★ 根据TC象限决定探索方向和顺序
                    double distWest  = baseDR / BL;
                    double distEast  = (MAP_L * BL - baseDR) / BL;
                    double distSouth = baseUR / BL;
                    double distNorth = (MAP_U * BL - baseUR) / BL;
                    double tcBlockX = baseDR / BL;
                    double tcBlockY = baseUR / BL;
                    double mapCX = MAP_L / 2.0;
                    double mapCY = MAP_U / 2.0;
                    bool nearWest  = (tcBlockX < mapCX * 0.5);
                    bool nearEast  = (tcBlockX > mapCX * 1.5);
                    bool nearSouth = (tcBlockY < mapCY * 0.5);
                    bool nearNorth = (tcBlockY > mapCY * 1.5);

                    // 计算8方向范围(格数)
                    double range[8];
                    range[0] = distWest;
                    range[1] = (distWest  < distSouth ? distWest  : distSouth) * 1.414;
                    range[2] = distSouth;
                    range[3] = (distEast  < distSouth ? distEast  : distSouth) * 1.414;
                    range[4] = distEast;
                    range[5] = (distEast  < distNorth ? distEast  : distNorth) * 1.414;
                    range[6] = distNorth;
                    range[7] = (distWest  < distNorth ? distWest  : distNorth) * 1.414;

                    // 按象限构建dirOrder：优先方向→其余按范围填充
                    int dirOrder[8];
                    bool used[8] = {false};
                    int di = 0;
                    auto addDir = [&](int d) { if (!used[d]) { dirOrder[di++] = d; used[d] = true; } };
                    if (nearWest && nearNorth) {
                        addDir(4); addDir(3);  // E优先, SE次之（NW角→向E/SE最远）
                    } else if (nearWest && nearSouth) {
                        addDir(6); addDir(4);  // N优先, E次之（SW角→N最远）
                    } else if (nearEast && nearSouth) {
                        addDir(6); addDir(0);  // N优先, W次之（SE角→N最远）
                    } else if (nearEast && nearNorth) {
                        addDir(0); addDir(1);  // W→SW（NE角远离东和北边缘）
                    }
                    // 其余方向按范围降序填充
                    while (di < 8) {
                        int best = -1; double bestR = -1;
                        for (int j = 0; j < 8; j++) {
                            if (!used[j] && range[j] > bestR) { bestR = range[j]; best = j; }
                        }
                        dirOrder[di++] = best; used[best] = true;
                    }

                    int dir = dirOrder[scoutPhase / 2];
                    bool ret = (scoutPhase % 2 == 1);

                    if (!ret) {
                            // 8方向单位向量 (dx=东, dy=北)
                            double dirX[8] = {-1, -1,  0,  1, 1, 1, 0, -1};
                            double dirY[8] = { 0, -1, -1, -1, 0, 1, 1,  1};
                            bool isDiag = (dir % 2 == 1);
                            double dist = SCOUT_DIST * BL;
                            if (isDiag) dist *= 0.707;  // 对角线保持实际距离≈100格

                            double dx = dirX[dir], dy = dirY[dir];
                            // 探索终点：TC 沿该方向 SCOUT_DIST 格（钳制到地图边缘）
                            double gx = baseDR + dx * dist;
                            double gy = baseUR + dy * dist;
                            gx = max(edgeWest, min(edgeEast, gx));
                            gy = max(edgeSouth, min(edgeNorth, gy));
                            // ★ 关键：每步只朝终点走 ~9 格（< 祭司 12 格视野），
                            //   保证目标始终在已探索范围内可达；到达后再走下一步，逐步推进
                            double gdx = gx - sDR, gdy = gy - sUR;
                            double goalLen = std::sqrt(gdx*gdx + gdy*gdy);
                            const double SCOUT_STEP = 9.0;
                            double wx, wy;
                            if (goalLen <= SCOUT_STEP * BL) {
                                wx = gx; wy = gy;
                            } else {
                                wx = sDR + gdx / goalLen * SCOUT_STEP * BL;
                                wy = sUR + gdy / goalLen * SCOUT_STEP * BL;
                            }
                            nearTarget = (goalLen < 3.0 * BL);

                            // ★ 危险检测：目标12格+路径前8格避开狮/象
                            bool dangerNearby = false;
                            double pathDX = wx - sDR, pathDY = wy - sUR;
                            double pathLen = std::sqrt(pathDX*pathDX + pathDY*pathDY);
                            for (auto &r : info.resources) {
                                if (r.Cnt <= 0) continue;
                                if (r.Type != RESOURCE_LION && r.Type != RESOURCE_ELEPHANT) continue;
                                double lx = r.DR, ly = r.UR;
                                if (calDistance(wx, wy, lx, ly) < 12 * BL) {
                                    dangerNearby = true; break;
                                }
                                if (pathLen > 0.01) {
                                    double t = ((lx - sDR)*pathDX + (ly - sUR)*pathDY) / (pathLen*pathLen);
                                    if (t < 0 || t * pathLen > 8 * BL) continue;  // 只检查前8格，远端不管
                                    if (t > 1) t = 1;
                                    double nearX = sDR + t * pathDX;
                                    double nearY = sUR + t * pathDY;
                                    if (calDistance(lx, ly, nearX, nearY) < 1.5 * BL) {
                                        dangerNearby = true; break;
                                    }
                                }
                            }

                            if (nearTarget || dangerNearby) {
                                if (nearTarget) scoutDirsDone++;
                                scoutReturnTry = 0;  // 开始返回阶段，重置绕路计数
                                scoutPhase++;  // 到达或遇险→进入返回阶段
                                scoutCooldown = 10;
                            } else {
                                // ★ 绕障：scoutReturnTry 作为绕障档位——0=正对目标，其余左右交替偏转、档位越大偏角越大
                                double ang = std::atan2(gdy, gdx);
                                if (scoutReturnTry > 0) {
                                    int t = scoutReturnTry;
                                    double off = ((t % 2 == 1) ? 1.0 : -1.0) * (20.0 * ((t + 1) / 2));
                                    ang += off * 3.141592653589793 / 180.0;
                                }
                                double wx2 = sDR + std::cos(ang) * SCOUT_STEP * BL;
                                double wy2 = sUR + std::sin(ang) * SCOUT_STEP * BL;
                                wx2 = max(edgeWest, min(edgeEast, wx2));
                                wy2 = max(edgeSouth, min(edgeNorth, wy2));
                                HumanMove(scout->SN, wx2, wy2);
                                // ★ 记录点/计时器只在祭司真正挪窝(>1格)后才刷新——
                                //   原来每次重发指令(冷却15帧)都刷新 scoutIssueFrame 与 scoutLegStartFrame，
                                //   导致 20 帧的 noProgress 窗口永远走不满、leg 超时也被不断重置→
                                //   卡死永不识别，同一不可达落点无限重发（日志里同一坐标刷屏）。
                                if (calDistance(sDR, sUR, scoutIssueDR, scoutIssueUR) > 1.0 * BL) {
                                    scoutIssueDR = sDR; scoutIssueUR = sUR; scoutIssueFrame = frame;
                                    scoutLegStartFrame = frame;
                                    scoutWalkTimer = 0;
                                }
                                scoutCooldown = 15;
                            }
                    } else {
                        // 返回：回TC旁空地（多半径×多角度螺旋绕路，被石头堵时逐级放大半径重试）
                        double wx = 0, wy = 0;
                        scoutReturnPoint(scoutReturnTry, baseDR, baseUR, wx, wy);
                        nearTarget = (calDistance(sDR, sUR, wx, wy) < 7 * BL) ||
                                     (calDistance(sDR, sUR, baseDR, baseUR) < 8 * BL);

                        // ★ 返程也要检测路径前8格是否有狮/象
                        bool dangerNearby = false;
                        double pathDX = wx - sDR, pathDY = wy - sUR;
                        double pathLen = std::sqrt(pathDX*pathDX + pathDY*pathDY);
                        for (auto &r : info.resources) {
                            if (r.Cnt <= 0) continue;
                            if (r.Type != RESOURCE_LION && r.Type != RESOURCE_ELEPHANT) continue;
                            double lx = r.DR, ly = r.UR;
                            if (pathLen > 0.01) {
                                double t = ((lx - sDR)*pathDX + (ly - sUR)*pathDY) / (pathLen*pathLen);
                                if (t < 0 || t * pathLen > 8 * BL) continue;  // 只检查前8格
                                if (t > 1) t = 1;
                                double nearX = sDR + t * pathDX;
                                double nearY = sUR + t * pathDY;
                                if (calDistance(lx, ly, nearX, nearY) < 1.5 * BL) {
                                    dangerNearby = true; break;
                                }
                            }
                        }

                        if (nearTarget || dangerNearby) {
                            scoutReturnTry = 0;  // 成功回到TC旁→重置绕路计数
                            scoutPhase++;  // 回到TC或遇险→下一个外向方向
                            if (scoutPhase >= 16) scoutPhase = 20;  // 全部探完→结束探路回TC待命
                            scoutCooldown = 10;
                        } else {
                            HumanMove(scout->SN, wx, wy);
                            // ★ 同样只在真正挪窝后才刷新记录点/计时器，否则 noProgress 与 leg 超时双双失效，
                            //   返回路径被堵时会无限重发同一个 scoutReturnPoint 落点。
                            if (calDistance(sDR, sUR, scoutIssueDR, scoutIssueUR) > 1.0 * BL) {
                                scoutIssueDR = sDR; scoutIssueUR = sUR; scoutIssueFrame = frame;
                                scoutLegStartFrame = frame;
                                scoutWalkTimer = 0;
                            }
                            scoutCooldown = 15;
                        }
                    }
                }
            }
            } // if(!fledThisFrame)
            }
        }

    // 探路完成（phase>=16或祭司死亡/不存在）后释放标记
    if (scoutPhase >= 16) {
        // 祭司探路完成，managePriest恢复常规逻辑
    }

    // 旧分配逻辑全部禁用：探路完成后直接返回，村民分配由 assignIdleSimple() 单独负责。
    return;
}
}

void UsrAI::assignIdleSimple() {
    std::map<int,int> assignedBush;
    std::map<int,int> assignedGazelle;
    std::map<int,int> assignedElephant;  // ★ 本帧已派往大象的 <elephantSN, 人数>，配合组队围猎
    std::map<int,int> assignedFarm;   // ★ 本帧已派往农场的 <farmSN, workerSN>，防同场重复派工导致>1人
    double BL = (double)BLOCKSIDELENGTH;
    // ★ 伐木工目标动态化（2026-09-01）：缺木(<120)时拉到 10 人抢木，常态 6 人。
    const int woodTarget = (info.Wood < WOOD_LOW_LINE) ? WOOD_TARGET_LOW : WOOD_TARGET_BASE;
    auto center = findBuilding(BUILDING_CENTER);
    double tcDR = center ? (center->BlockDR + 1) * BL : 0;
    double tcUR = center ? (center->BlockUR + 1) * BL : 0;

    // ★ 狮子防御：预检"是否有狮子进入 TC 8 格内"。命中则记录离 TC 最近的一只，
    //   ★ 2026-09-01：原"只看 TC 8 格内的狮子、派 2 人"的旧逻辑已废弃，统一由 manageLionDefense()
    //     处理（覆盖全图我方单位、分紧急/预警两级、每狮 4 人）。此处只负责"跳过正在猎狮的村民"，
    //     避免刚派出去的猎手被采集分配立刻改派去砍树/挖金。
    int goldWorkers = 0;
    int woodWorkers = 0;
    int stoneWorkers = 0;   // ★ 采石工计数
    int foodWorkers  = 0;   // ★ 食物工计数（浆果/瞪羚/大象/农场）
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (f.ResourceSort == HUMAN_GOLD) goldWorkers++;
        if (f.ResourceSort == HUMAN_WOOD) woodWorkers++;
        if (f.ResourceSort == HUMAN_STONE) stoneWorkers++;
        if (f.ResourceSort == HUMAN_GRANARYFOOD || f.ResourceSort == HUMAN_STOCKFOOD) foodWorkers++;
        if (f.WorkObjectSN > 0) {
            for (auto &r : info.resources)
                if (r.SN == f.WorkObjectSN) {
                    if (r.Type == RESOURCE_GOLD) goldWorkers++;
                    else if (r.Type == RESOURCE_TREE) woodWorkers++;
                    else if (r.Type == RESOURCE_STONE) stoneWorkers++;
                    else if (r.Type == RESOURCE_BUSH || r.Type == RESOURCE_GAZELLE || r.Type == RESOURCE_ELEPHANT) foodWorkers++;
                    break;
                }
            for (auto &b : info.buildings)
                if (b.SN == f.WorkObjectSN && b.Type == BUILDING_FARM) { foodWorkers++; break; }
        }
    }

    // ★ 资源停采门禁（2026-09-01）：存量达上限即停止派/补采该资源，人力转向其他资源
    const bool woodStop  = (info.Wood >= (frame >= WAVE3_TIME ? WOOD_CAP_STOP_LATE : WOOD_CAP_STOP));
    // ★ 石头停采（2026-09-03 用户需求）：14分钟(=WAVE3_TIME)后不再采石，或存量≥STONE_CAP_STOP 也停。
    //   14分钟后箭塔已建满、投石兵已够、反攻期石头无用，采石工全部撤去食物/木头。
    //   ★ 2026-09-05 用户新增需求：**建满 MAX_TOWERS(2) 座箭塔后立刻永久停采**。
    //     已实证箭塔(150石)是当前【唯一活的石头消耗】——铜器箭塔升级(50石)被 DISABLE_TOWER_UPGRADE=true 封禁、
    //     投石兵无训练代码、建筑维修在代码中未实现 ⇒ 塔建满后石头再无任何用途，继续采石纯属浪费人力。
    //     判据用 countBuildingsExisting（含在建地基 + pendingBuildIns 异步窗口 + 下令后90帧宽限），
    //     与建造段同源自洽。**不并列 towerCount 成员**：towerCount 在 tryBuild 成功当帧即++、被摧毁也不回退，
    //     若并列会导致"第2座建造失败/被打掉"后永久误停采、再也补建不出；改用实际存在数则天然自愈
    //     ——塔没了计数回落即自动恢复采石补建。
    //   stoneStop 同时驱动「派工块跳过采石(!stoneStop)」+「回撤块撤走采石工(stoneStop && isStone)」两个方向，一处改两处生效。
    const bool towersDone = (countBuildingsExisting(BUILDING_ARROWTOWER) >= MAX_TOWERS);
    const bool stoneStop = (frame >= WAVE3_TIME) || (info.Stone >= STONE_CAP_STOP) || towersDone;
    // ★ 黄金过剩判定（2026-09-02 三改）：后期实测"黄金堆到 700+、木头食物都不够"。
    //   根因：上一版为"反攻期黄金持续消耗"加了豁免 `(state<COUNTERATTACK)&&`，导致反攻期金工**无上限开采**；
    //   而反攻期食物才是造兵真瓶颈（复合弓40食/方阵60食，食物需求≈黄金2倍），食物跟不上→兵造不出→黄金只进不出→堆700。
    //   复核反攻期黄金需求其实有限：一场反攻(约20复合弓+10方阵)黄金总量 ≈ 20*20+10*40 = 800，
    //   GOLD_CAP_STOP=400 储备 + MIN_GOLD_WORKERS=1 持续产出 完全够用，不存在"靶场缺金空转"——
    //   故**去掉反攻豁免，让压制全程生效**。命中→goldTarget 压到 MIN_GOLD_WORKERS，人力经派工链/回撤块转去木头+食物。
    //   判定两种过剩：①绝对过剩：存量 ≥ GOLD_CAP_STOP(400)；
    //                ②相对过剩：黄金/食物 超出 5:3 目标配比的 1.25 倍（+50 基数避免早期食物为0误判）。
    const bool goldRich =
        (info.Gold >= GOLD_CAP_STOP) ||
        ((double)info.Gold > (double)(info.Meat + 50) * (double)FOOD_GOLD_DEN
                             / (double)FOOD_GOLD_NUM * GOLD_RICH_TOL);
    // ★ 铜器时代前不采集黄金（2026-09-03 用户要求）：黄金是铜器主货币，铜器前用不上；
    //   故 goldTarget 强制为 0，人力全投食物/木头/石头，加速攒 800 食物升铜器。
    const bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
    // ★ 食物停采门禁（2026-09-02）：食物≥阈值即不再派新食物工（浆果/瞪羚/大象/农场），
    //   已派食物工由下方回撤块逐步转去伐木——修"食物堆 1500+ 而木头只 50 不够"的失衡。
    //   ★ 2026-09-03 修正：铜器升级要 800 食物，铜器前停采阈值必须 >800，
    //     否则食物到 500 就停采+撤食物工，永远攒不到 800 → 升级拖到 20 分钟。铜器前 850、铜器后 500。
    const bool foodStop = (info.Meat >= (postBronze ? FOOD_CAP_STOP : FOOD_CAP_STOP_PREBRONZE));
    // ★ 黄金目标人数：与食物工数按 5:3 配比（复合弓兵40食+20金 / 方阵兵60食+40金 → 100:60=5:3）。
    //   黄金过剩时压到保底人数，把人力让给食物与木头。★
    int goldTarget = (!postBronze) ? 0
        : goldRich ? MIN_GOLD_WORKERS
        : std::max(MIN_GOLD_WORKERS,
                   (int)((double)foodWorkers * FOOD_GOLD_DEN / FOOD_GOLD_NUM + 0.999));

    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (f.Resource > 0) continue;
        if (f.NowState != HUMAN_STATE_IDLE) continue;
        if (waveBlockers.count(f.SN) || f.SN == scoutFarmerSN) continue;
        if (lionHunterSN.count(f.SN)) continue;   // ★ 正在猎狮，不要改派去采集

        // ★ 木头达停采上限(日常≥150 / WAVE3后≥250)则不再派新伐木工，人力优先留作食物
        if (!woodStop && woodWorkers < woodTarget) {
            auto treeFirst = findBestWoodTree(f.DR, f.UR);
            if (treeFirst) {
                HumanAction(f.SN, treeFirst->SN);
                woodWorkers++;
                continue;
            }
        }

        // ★ 黄金：与食物按 5:3 配比（复合弓兵+方阵兵成本综合）；不受木头/石头门禁影响，
        //   但受「黄金过剩」约束——goldRich 时 goldTarget 已被压到 MIN_GOLD_WORKERS，人力自动落到食物/木头。
        if (goldWorkers < goldTarget) {
            auto gold = findNearestResource(RESOURCE_GOLD, f.DR, f.UR);
            if (gold) {
                HumanAction(f.SN, gold->SN);
                goldWorkers++;
                continue;
            }
        }

        // ★ 石头供给（箭塔/投石兵/建筑维修需要）：复合弓兵/阔剑兵引擎现已修正为扣「食物 + 黄金」(非石头)，
        //   故不再把采金工转去采石（旧逻辑会在金≥200 时把所有金矿工每帧重派去采石，造成重复下令刷屏）。
        //   采石仅由本保底块负责：不达停采上限(!stoneStop)就保底派 STONE_WORKERS_LATE 人采石。
        //   ★ 2026-09-03 修复"前期没人采石"：删掉过时的 (compositeBowResearched || state>=DEFENSE_WAVE3) 门槛——
        //     那门槛是"石头只用于投石兵/铜器箭塔升级"时代的产物，现在箭塔前期就要建、投石兵已取消，
        //     导致前期该门槛恒 false、没人采石、第2座箭塔(需额外150石)一直建不出。stoneStop 已含
        //     "14分钟后停"+"采够150停"两道闸，不会过度采石，无需再加其他门槛。
        if (!stoneStop &&
            stoneWorkers < STONE_WORKERS_LATE) {
            auto stoneR = findNearestResource(RESOURCE_STONE, f.DR, f.UR);
            if (stoneR) {
                HumanAction(f.SN, stoneR->SN);
                stoneWorkers++;
                continue;
            }
        }

        // ★ 食物过剩停采（2026-09-02）：食物≥FOOD_CAP_STOP 时不再派新食物工（浆果/瞪羚/大象/农场），
        //   本空闲村民改派伐木（修"食物堆 1500+ 而木头只 50 不够"）。木头也满时才跳过（此时食/木都过剩，无需再采）。
        if (foodStop) {
            if (!woodStop) {
                auto tree = findBestWoodTree(f.DR, f.UR);
                if (tree) { HumanAction(f.SN, tree->SN); woodWorkers++; continue; }
            }
            continue;  // 食物过剩：不再派食物，直接跳过（木头满则保持空闲，木头缺则已被上面派去伐木）
        }

        tagResource* bestBush = nullptr;
        double bestBushScore = 1e12;
        for (auto &r : info.resources) {
            if (r.Type != RESOURCE_BUSH || r.Cnt <= 0) continue;
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > 20 * BL) continue;
            int onBush = 0;
            for (auto &other : info.farmers)
                if (other.WorkObjectSN == r.SN) onBush++;
            int totalOnBush = onBush + assignedBush[r.SN];
            if (totalOnBush >= 3) continue;
            double d = (r.DR - f.DR)*(r.DR - f.DR) + (r.UR - f.UR)*(r.UR - f.UR);
            double score = d * (1.0 + totalOnBush * 0.8);
            if (score < bestBushScore) { bestBushScore = score; bestBush = &r; }
        }
        if (bestBush) {
            HumanAction(f.SN, bestBush->SN);
            assignedBush[bestBush->SN]++;
            continue;
        }

        tagResource* bestGazelle = nullptr;
        double bestGazelleDist = 1e12;
        for (auto &r : info.resources) {
            if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) continue;
            // ★ 2026-09-04 范围放宽：30→GAZELLE_HUNT_RANGE(50) 格，覆盖远距未建仓库的瞪羚群
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > GAZELLE_HUNT_RANGE * BL) continue;
            int onGazelle = 0;
            for (auto &other : info.farmers)
                if (other.WorkObjectSN == r.SN) onGazelle++;
            if (onGazelle + assignedGazelle[r.SN] >= 2) continue;
            double d = (r.DR - f.DR)*(r.DR - f.DR) + (r.UR - f.UR)*(r.UR - f.UR);
            if (d < bestGazelleDist) { bestGazelleDist = d; bestGazelle = &r; }
        }
        if (bestGazelle) {
            HumanAction(f.SN, bestGazelle->SN);
            assignedGazelle[bestGazelle->SN]++;
            continue;
        }

        // ★ 组队猎象（2026-09-03 用户需求）：大象血45/攻10/不逃跑/掉肉300，性价比远超瞪羚。
        //   村民(血25)单挑必死，须凑够 ELEPHANT_HUNT_GROUP 人围猎。此处遍历所有大象，
        //   选"已有人在打(集中火力) 且 猎人未满"的最近一头，每头 ≤ ELEPHANT_HUNT_GROUP 人，
        //   让空闲村民源源不断补充到同一头象，快速击杀——而不是各自为战单挑送死。
        tagResource* bestElephant = nullptr;
        double bestElephantScore = 1e12;
        for (auto &r : info.resources) {
            if (r.Type != RESOURCE_ELEPHANT || r.Cnt <= 0) continue;
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > 30 * BL) continue;
            int onElephant = 0;
            for (auto &other : info.farmers)
                if (other.WorkObjectSN == r.SN) onElephant++;
            int totalOnElephant = onElephant + assignedElephant[r.SN];
            if (totalOnElephant >= ELEPHANT_HUNT_GROUP) continue;  // 已满员→不补
            double d = (r.DR - f.DR)*(r.DR - f.DR) + (r.UR - f.UR)*(r.UR - f.UR);
            // 已有人在打的大象加权(-1.5格距离当量)优先补位，集中火力；再按距离近者优先
            double score = d - (onElephant > 0 ? 1.5 * BL * 1.5 * BL : 0.0);
            if (score < bestElephantScore) { bestElephantScore = score; bestElephant = &r; }
        }
        if (bestElephant) {
            HumanAction(f.SN, bestElephant->SN);
            assignedElephant[bestElephant->SN]++;
            continue;
        }

        // ★ 农场：每座农场"有且仅有一人"。跳过本帧已派的农场，且已有≥1工人(实时)的也跳过，杜绝重复派工
        tagBuilding* farm = nullptr;
        for (auto &b : info.buildings) {
            if (b.Type != BUILDING_FARM || b.Percent < 100) continue;
            if (assignedFarm.count(b.SN)) continue;        // 本帧已派过，跳过
            int onFarm = 0;
            for (auto &other : info.farmers)
                if (other.WorkObjectSN == b.SN) onFarm++;
            if (onFarm >= 1) continue;                     // 已有工人，不再加派
            farm = &b; break;
        }
        if (farm) {
            HumanAction(f.SN, farm->SN);
            assignedFarm[farm->SN] = f.SN;                 // 记录，本帧内后续空闲村民不会再来这座
            continue;
        }

        // ★ 兜底：前面所有食物来源(BUSH/GAZELLE/ELEPHANT/FARM)都不可用→伐木，绝不空闲。
        //   不受 woodTarget 上限约束：食物耗尽时即便已有 ≥woodTarget 个伐木工，也把多余空闲村民派去伐木，
        //   避免村民站在原地空耗（用户需求：村民没有可选食物采集的目标时伐木）。
        // ★ 兜底：前面食物来源都不可用 → 优先黄金(5:3配比)，其次伐木(受woodStop门禁，≥250不强行伐)
        auto goldRes = findNearestResource(RESOURCE_GOLD, f.DR, f.UR);
        if (goldRes && goldWorkers < goldTarget) {
            HumanAction(f.SN, goldRes->SN); goldWorkers++;
        } else {
            auto tree = findBestWoodTree(f.DR, f.UR);
            if (tree && !woodStop) {
                HumanAction(f.SN, tree->SN);
                woodWorkers++;
            }
        }
    }

    // ========== ★ 资源达上限回撤：把多余伐木/采石/采金工转移到缺口资源 ==========
    // 木头≥400 / 石头≥120 / 黄金过剩 时，已派工人应停采，人力转去"当前最缺的资源"。
    // 转移优先级：缺木(<120)时直接去伐木，否则先食物，食物接不住再伐木（不再转黄金，黄金正是过剩方）。
    // 节流：每 10 帧最多撤 1 人（防震荡）；伐木保留 WOOD_KEEP_MIN 人保底，采石全撤，采金保留 MIN_GOLD_WORKERS。
    if ((woodStop || stoneStop || goldRich || foodStop) && frame % 10 == 0) {
        const bool woodHungry = (info.Wood < WOOD_LOW_LINE);
        for (auto &f : info.farmers) {
            if (f.FarmerSort != FARMERTYPE_FARMER) continue;
            if (waveBlockers.count(f.SN) || f.SN == scoutFarmerSN) continue;
            if (lionHunterSN.count(f.SN)) continue;   // ★ 正在猎狮，不要撤回采资源
            if (f.NowState != HUMAN_STATE_WORKING && f.NowState != HUMAN_STATE_WALKING) continue;
            bool isStone = (f.ResourceSort == HUMAN_STONE);
            bool isWood  = (f.ResourceSort == HUMAN_WOOD);
            bool isGold  = (f.ResourceSort == HUMAN_GOLD);
            bool isFood  = (f.ResourceSort == HUMAN_GRANARYFOOD || f.ResourceSort == HUMAN_STOCKFOOD);
            if (f.WorkObjectSN > 0 && !isStone && !isWood && !isGold && !isFood) {
                for (auto &r : info.resources)
                    if (r.SN == f.WorkObjectSN) {
                        if (r.Type == RESOURCE_STONE) isStone = true;
                        else if (r.Type == RESOURCE_TREE) isWood = true;
                        else if (r.Type == RESOURCE_GOLD) isGold = true;
                        else if (r.Type == RESOURCE_BUSH || r.Type == RESOURCE_GAZELLE || r.Type == RESOURCE_ELEPHANT) isFood = true;
                        break;
                    }
                for (auto &b : info.buildings)
                    if (b.SN == f.WorkObjectSN && b.Type == BUILDING_FARM) { isFood = true; break; }
            }
            // 统一转派：缺木→伐木；否则食物优先，食物接不住再伐木（绝不再送回黄金）
            auto reassignToDeficit = [&](tagFarmer &w)->bool {
                if (woodHungry) {
                    auto t = findBestWoodTree(w.DR, w.UR);
                    if (t) { HumanAction(w.SN, t->SN); return true; }
                }
                if (tryAssignFood(&w)) return true;
                auto t2 = findBestWoodTree(w.DR, w.UR);
                if (t2) { HumanAction(w.SN, t2->SN); return true; }
                return false;
            };
            bool reassigned = false;
            if (foodStop && isFood) {
                // ★ 食物过剩：食物工直接转伐木（木头偏少时补木；木头满则转黄金，黄金也满才罢休）
                auto t = findBestWoodTree(f.DR, f.UR);
                if (t && !woodStop) {
                    HumanAction(f.SN, t->SN); reassigned = true;
                } else {
                    auto g = findNearestResource(RESOURCE_GOLD, f.DR, f.UR);
                    if (g && postBronze && !goldRich) { HumanAction(f.SN, g->SN); reassigned = true; }
                }
            } else if (stoneStop && isStone) {
                // 石头达标：采石工全撤
                reassigned = reassignToDeficit(f);
            } else if (goldRich && isGold && goldWorkers > MIN_GOLD_WORKERS) {
                // 黄金过剩：采金工撤到只剩保底人数
                reassigned = reassignToDeficit(f);
            } else if (woodStop && isWood && woodWorkers > WOOD_KEEP_MIN) {
                // 木头达标：伐木工保留 WOOD_KEEP_MIN 人，其余撤
                reassigned = reassignToDeficit(f);
            }
            if (reassigned) break;  // 每 10 帧最多撤 1 人，防震荡
        }
    }

    // ★ 资源调度自检打印（便于实测调参）：存量 / 各资源工数 / 门禁状态
    if (frame % 600 == 0) {
        DebugText(QString("ECO | Fd:%1 Wd:%2 St:%3 Gd:%4 || workers F%5 W%6 G%7 S%8 || goldRich:%9 woodStop:%10 stoneStop:%11 foodStop:%12 woodTarget:%13 twr:%14/%15")
                  .arg((int)info.Meat).arg((int)info.Wood).arg((int)info.Stone).arg((int)info.Gold)
                  .arg(foodWorkers).arg(woodWorkers).arg(goldWorkers).arg(stoneWorkers)
                  .arg(goldRich ? 1 : 0).arg(woodStop ? 1 : 0).arg(stoneStop ? 1 : 0).arg(foodStop ? 1 : 0)
                  .arg(woodTarget)
                  .arg(countBuildingsExisting(BUILDING_ARROWTOWER)).arg(MAX_TOWERS));
    }

    // ========== ★ 农场"有且仅有一人"强制校验（兜底） ==========
    // 任何一帧若发现某农场工人数≥2，立即把多余工人转移到空农场或伐木；
    // 一并把本帧刚派下去(引擎尚未回写 WorkObjectSN)的工人计入，避免一帧内同场重复派工漏检。
    {
        std::map<int, std::vector<int>> fwMap;   // farmSN -> 工人SN列表
        for (auto &b : info.buildings)
            if (b.Type == BUILDING_FARM && b.Percent >= 100) fwMap[b.SN];
        for (auto &f : info.farmers) {
            if (f.FarmerSort != FARMERTYPE_FARMER) continue;
            if (f.WorkObjectSN > 0 && fwMap.count(f.WorkObjectSN))
                fwMap[f.WorkObjectSN].push_back(f.SN);
        }
        for (auto &kv : assignedFarm)            // 本帧主循环刚派的工人（其 WorkObjectSN 仍是旧值），手动补入
            if (fwMap.count(kv.first)) fwMap[kv.first].push_back(kv.second);

        std::vector<int> emptyFarms;
        for (auto &kv : fwMap) if ((int)kv.second.size() == 0) emptyFarms.push_back(kv.first);

        for (auto &kv : fwMap) {
            auto &workers = kv.second;
            if ((int)workers.size() <= 1) continue;   // 已满足"恰好一人"，跳过
            // 保留第1个工人，其余(多余)转移走
            for (size_t i = 1; i < workers.size(); ++i) {
                int wSN = workers[i];
                tagFarmer* wf = nullptr;
                for (auto &f : info.farmers) if (f.SN == wSN) { wf = &f; break; }
                if (!wf) continue;
                // 只移动可安全重派的工人（空闲/工作/走路中），不打断行军或建造
                if (wf->NowState != HUMAN_STATE_IDLE && wf->NowState != HUMAN_STATE_WORKING
                    && wf->NowState != HUMAN_STATE_WALKING) continue;
                if (!emptyFarms.empty()) {
                    int dst = emptyFarms.back(); emptyFarms.pop_back();
                    HumanAction(wSN, dst);            // 多余工人→空农场（同时填补空场）
                } else if (woodWorkers < woodTarget) {
                    auto tree = findBestWoodTree(wf->DR, wf->UR);
                    if (tree) { HumanAction(wSN, tree->SN); woodWorkers++; }
                    else break;
                } else break;                          // 无处可去则保留（不造成更糟局面）
            }
        }
    }
}

void UsrAI::manageHunting() {
    if (state >= DEFENSE_WAVE1 && state <= DEFENSE_WAVE3) return;
    if (state == COUNTERATTACK) return;

    double BL = (double)BLOCKSIDELENGTH;
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return;
    double tcDR = (center->BlockDR + 1) * BL;
    double tcUR = (center->BlockUR + 1) * BL;

    // 统计TC附近浆果总食物量（不用丛数，避免多丛快枯的浆果误判为"充足"）
    int bushFood = 0;
    for (auto &r : info.resources)
        if (r.Type == RESOURCE_BUSH && r.Cnt > 0)
            if (calDistance(tcDR, tcUR, r.DR, r.UR) < 30 * BL) bushFood += r.Cnt;
    // 清理狩猎组（农民不在攻击状态→已完成狩猎）★ 每帧都清，避免浆果>400时 stale 条目让村民被跳过
    for (auto it = huntingGroup.begin(); it != huntingGroup.end(); ) {
        bool still = false;
        for (auto &f : info.farmers)
            if (f.SN == *it && f.NowState == HUMAN_STATE_ATTACKING) { still = true; break; }
        if (!still) it = huntingGroup.erase(it); else ++it;
    }

    if (bushFood > 400) return;  // 浆果还够吃（>400食物），暂不主动打猎

    // 找TC附近最近的瞪羚（每只≤2人）—— ★ 范围 2026-09-04 放宽到 50 格（GAZELLE_HUNT_RANGE）
    tagResource* bestGazelle = nullptr;
    double bestDist = 1e12;
    for (auto &r : info.resources) {
        if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) continue;
        double d = calDistance(tcDR, tcUR, r.DR, r.UR);
        if (d >= GAZELLE_HUNT_RANGE * BL) continue;
        int realCount = 0;
        for (auto &other : info.farmers)
            if (other.WorkObjectSN == r.SN) realCount++;
        if (realCount >= 2) continue;  // 每只≤2人
        if (d < bestDist) { bestDist = d; bestGazelle = &r; }
    }
    if (!bestGazelle) return;

    // ★ 只用空闲农民，不抢采浆果的 ★
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN) || waveBlockers.count(f.SN)) continue;
        if (huntingGroup.count(f.SN)) continue;  // 已分配过，不重复设
        if (f.Resource > 0) continue;
        if (f.NowState != HUMAN_STATE_IDLE) continue;  // 只等空闲

        HumanAction(f.SN, bestGazelle->SN);
        huntingGroup.insert(f.SN);
        return;  // 每帧最多分配1个猎人
    }
}

// ============================================================
// ★ 狮子防御（2026-09-01）：一旦有狮子逼近/正在攻击我方单位，立刻就近派人猎杀
//   引擎事实（Animal.cpp::isMonitorObject）：狮子只攻击【村民】与【非祭司军队】，
//   不攻击祭司、也不攻击建筑 → 威胁判定只针对村民与非祭司军队。
//   两级威胁：
//     · 紧急级(attacking)：我方单位已掉血且狮子 ≤2 格 → 判定"正在被咬"，允许打断采集/赶路强行抽人。
//     · 预警级：狮子距我方任一单位 ≤6 格（狮子视野 3 格，随时会扑上来）→ 只派空闲村民。
//   人力：每只狮 4 人（狮子 20 血，村民攻击低，2 人打不完还会送命）；
//         贴脸(≤4格)的空闲军队优先上，战力高可快速解决。
// ============================================================
void UsrAI::manageLionDefense() {
    const double BL = (double)BLOCKSIDELENGTH;

    // ---- 1. 清理失效/完成的猎狮任务 ----
    for (auto it = lionHunterSN.begin(); it != lionHunterSN.end(); ) {
        const int unitSN = it->first, lionSN = it->second;
        bool lionAlive = false;
        for (auto &r : info.resources)
            if (r.SN == lionSN && r.Type == RESOURCE_LION && r.Cnt > 0) { lionAlive = true; break; }
        // 单位已不存在、或已回到 IDLE（说明猎狮动作结束/被打断）→ 任务结束
        bool idle = true;
        for (auto &f : info.farmers) if (f.SN == unitSN) { idle = (f.NowState == HUMAN_STATE_IDLE); break; }
        for (auto &a : info.armies)  if (a.SN == unitSN) { idle = (a.NowState == HUMAN_STATE_IDLE); break; }
        auto eit = lionHunterExpire.find(unitSN);
        if (!lionAlive || idle || eit == lionHunterExpire.end() || frame > eit->second) {
            lionHunterExpire.erase(unitSN);
            it = lionHunterSN.erase(it);
        } else {
            ++it;
        }
    }

    // ---- 2. 扫描活狮，评估威胁等级 ----
    struct LionThreat { tagResource* lion; double dist; bool attacking; int victimSN; };
    std::vector<LionThreat> threats;
    for (auto &r : info.resources) {
        if (r.Type != RESOURCE_LION || r.Cnt <= 0) continue;
        double best = 1e18; int victim = 0; bool attacking = false;
        for (auto &f : info.farmers) {
            double d = calDistance(f.DR, f.UR, r.DR, r.UR);
            if (d < best) { best = d; victim = f.SN; }
            if (d <= LION_ATTACK_RADIUS * BL && f.Blood < f.MaxBlood) attacking = true;
        }
        for (auto &a : info.armies) {
            if (a.Sort == AT_PRIEST) continue;          // 狮子不咬祭司，祭司也别去送
            double d = calDistance(a.DR, a.UR, r.DR, r.UR);
            if (d < best) { best = d; victim = a.SN; }
            if (d <= LION_ATTACK_RADIUS * BL && a.Blood < a.MaxBlood) attacking = true;
        }
        if (attacking || best <= LION_THREAT_RADIUS * BL)
            threats.push_back({&r, best, attacking, victim});
    }
    if (threats.empty()) return;
    // 正在咬人的排最前，其次按距离由近到远
    std::sort(threats.begin(), threats.end(), [](const LionThreat &x, const LionThreat &y) {
        if (x.attacking != y.attacking) return x.attacking;
        return x.dist < y.dist;
    });

    // ---- 3. 逐只威胁狮派人 ----
    for (auto &th : threats) {
        int hunters = 0;
        for (auto &kv : lionHunterSN) if (kv.second == th.lion->SN) hunters++;
        int need = LION_HUNTER_GROUP - hunters;
        if (need <= 0) continue;

        // 3.1 军队优先：贴脸(≤LION_ARMY_RANGE)且空闲的军队直接下令（战斗力远高于村民）
        for (auto &a : info.armies) {
            if (need <= 0) break;
            if (a.Sort == AT_PRIEST) continue;
            if (lionHunterSN.count(a.SN)) continue;
            if (a.NowState != HUMAN_STATE_IDLE) continue;
            if (calDistance(a.DR, a.UR, th.lion->DR, th.lion->UR) > LION_ARMY_RANGE * BL) continue;
            HumanAction(a.SN, th.lion->SN);
            lionHunterSN[a.SN] = th.lion->SN;
            lionHunterExpire[a.SN] = frame + LION_TASK_FRAMES;
            need--;
        }

        // 3.2 村民补位：预警级只用空闲村民；紧急级(正在被咬)允许打断采集/赶路
        std::vector<std::pair<double, int>> cands;   // <距狮距离, farmers下标>
        for (size_t i = 0; i < info.farmers.size(); ++i) {
            auto &f = info.farmers[i];
            if (f.FarmerSort != FARMERTYPE_FARMER) continue;
            if (lionHunterSN.count(f.SN)) continue;
            if (waveBlockers.count(f.SN) || f.SN == scoutFarmerSN) continue;
            if (buildingFarmerType.count(f.SN)) continue;             // 不打断建造
            if (huntingGroup.count(f.SN)) continue;                   // 不抢现有猎手
            if (f.Resource > 0) continue;                             // 手上有资源，先送回
            if (f.NowState == HUMAN_STATE_ATTACKING) continue;         // 已在战斗
            if (!th.attacking && f.NowState != HUMAN_STATE_IDLE) continue;  // 预警级只抽空闲
            double d = calDistance(f.DR, f.UR, th.lion->DR, th.lion->UR);
            if (d > LION_HUNTER_RANGE * BL) continue;
            cands.push_back(std::make_pair(d, (int)i));
        }
        std::sort(cands.begin(), cands.end());
        for (auto &c : cands) {
            if (need <= 0) break;
            auto &f = info.farmers[c.second];
            HumanAction(f.SN, th.lion->SN);
            lionHunterSN[f.SN] = th.lion->SN;
            lionHunterExpire[f.SN] = frame + LION_TASK_FRAMES;
            need--;
        }

        if (need < LION_HUNTER_GROUP && frame % 30 == 0)
            DebugText(QString("Lion DEFENSE lion=%1 dist=%2 attacking=%3 victim=%4 hunters=%5/%6")
                      .arg(th.lion->SN).arg(th.dist / BL, 0, 'f', 1)
                      .arg(th.attacking ? 1 : 0).arg(th.victimSN)
                      .arg(LION_HUNTER_GROUP - need).arg(LION_HUNTER_GROUP));
    }
}

// ============================================================
// 科技升级（铜器后三级制：军事解锁 > 军事强化 > 经济）
// ============================================================
void UsrAI::manageTechUpgrade() {
    if (techCooldown > 0) return;
    if (info.Meat < FOOD_PAUSE_TECH_TRAIN) return;

    bool done = false;
    bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);

    // ★ 原 preW1（第一波前只许阔剑科技）门槛已移除：复合弓科技现在「能解锁就解锁」，不再受波次阶段限制。
    // ★ 开局即研究箭塔科技（不等铜器/第3波/军事解锁）：有谷仓+50食物就研究，解锁箭塔建造 ★
    if (!towerTechResearched) {
        auto g = findBuilding(BUILDING_GRANARY);
        if (g && g->Project == BUILDING_GRANARY_ARROWTOWER) {
            towerTechResearched = true;  // 引擎已在研究中（已扣资源）
        } else if (g && g->Project == ACT_NULL && info.Meat >= 50) {
            BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWER);
            towerTechResearched = true;
            techCooldown = 25;
            return;
        }
    }

    // ★★★ 铜器前：除箭塔科技外禁止其他科技！每一粒食物都留给800升级费 ★★★
    if (!postBronze) return;

    // ★ 从游戏状态同步布尔值（检查建筑是否真在研究中，已扣资源）★
    // 不使用乐观标记！必须确认科技已经"付款"正在执行
    if (!broadswordResearched) {
        auto ac = findBuildingIncludingUnderConstruction(BUILDING_ARMYCAMP);
        if (ac && ac->Project == BUILDING_ARMYCAMP_UPGRADE_BROADSWORD) {
            broadswordResearched = true;  // 真的在研究了！
        } else if (broadswordQueued && ac && ac->Project == ACT_NULL) {
            // 已排队 → 建筑空闲 → 科技已完成
            broadswordResearched = true;
        }
    }
    if (!compositeBowResearched) {
        auto rng = findBuildingIncludingUnderConstruction(BUILDING_RANGE);
        if (rng && rng->Project == BUILDING_RANGE_UPGRADE_COMPOSITE_BOW) {
            compositeBowResearched = true;
        } else if (compositeBowQueued && rng && rng->Project == ACT_NULL) {
            compositeBowResearched = true;
        }
    }

    // ==================================================================
    // ★ TIER 1：军事解锁（复合弓优先，不等阔剑）★
    // ==================================================================
    // ★ 引擎真实条件（Development.cpp:739-740）：
    //     conditionDevelop(CIVILIZATION_BRONZEAGE, BUILDING_RANGE, TIME,
    //                      BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_WOOD,
    //                      BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_FOOD)
    //   构造函数签名 (civ, building, time, wood, food, stone, gold)（GlobalVariate.h:346）
    //   → 复合弓科技只需「铜器时代 + 木材 + 食物」：**不需要黄金**，且**引擎层没有阔剑前置条件**。
    //   旧代码的 info.Gold >= 40 是凭空多出来的伪门槛，黄金不足时会导致复合弓科技永远研究不了；
    //   旧代码还把它排在阔剑之后并加了 preW1 / DEFENSE_PREP / DEFENSE_WAVE2 阶段门槛，进一步推迟解锁。
    //   现在：能解锁就立刻解锁——排在阔剑之前、去掉伪黄金门槛与阶段门槛、判据用引擎真实成本宏。

    // --- Range: 复合弓科技（最高优先，不受阔剑阻塞）---
    if (!done && !compositeBowResearched && !compositeBowQueued) {
        auto r = findBuilding(BUILDING_RANGE);
        // ★ 复合弓科技诊断：每 30 帧打印一次 5 个闸门状态，定位"为什么不立刻升级"
        if (frame % 30 == 0) {
            int rngPct = -1, rngProj = -2;
            auto rngAll = findBuildingIncludingUnderConstruction(BUILDING_RANGE);
            if (rngAll) { rngPct = rngAll->Percent; rngProj = rngAll->Project; }
            bool meatOK = (info.Meat >= BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_FOOD);
            bool woodOK = (info.Wood >= BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_WOOD);
            bool readyOK = (r && r->Project == ACT_NULL && meatOK && woodOK);
            DebugText(QString("[CB f=%1] rngFound=%2 rngPct=%3 rngProj=%4 meat=%5(%6) wood=%7(%8) techCD=%9 ready=%10")
                .arg(frame)
                .arg(r ? 1 : 0).arg(rngPct).arg(rngProj)
                .arg((int)info.Meat).arg(meatOK ? 1 : 0)
                .arg((int)info.Wood).arg(woodOK ? 1 : 0)
                .arg(techCooldown)
                .arg(readyOK ? 1 : 0));
        }
        if (r && r->Project == ACT_NULL &&
            info.Meat >= BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_FOOD &&
            info.Wood >= BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_WOOD) {
            BuildingAction(r->SN, BUILDING_RANGE_UPGRADE_COMPOSITE_BOW);
            compositeBowQueued = true;
            done = true;
            DebugText(QString("!! TECH CompositeBow f=%1 meat=%2 wood=%3")
                .arg(frame).arg((int)info.Meat).arg((int)info.Wood));
        }
    }

    // --- Army camp: 阔剑科技（封禁中，见 DISABLE_BROADSWORD_TECH）---
    //   引擎条件已修正：阔剑科技现真扣 食物+黄金（need_Stone=0）。若解禁：把开关改 false，
    //   且下方判据应改回 info.Gold（而非当前 info.Stone）。
    if (!DISABLE_BROADSWORD_TECH && !done && !broadswordResearched && !broadswordQueued) {
        auto ac = findBuilding(BUILDING_ARMYCAMP);
        if (ac && ac->Project == ACT_NULL &&
            info.Meat >= BUILDING_ARMYCAMP_UPGRADE_BROADSWORD_FOOD &&
            info.Stone >= BUILDING_ARMYCAMP_UPGRADE_BROADSWORD_GOLD) {
            BuildingAction(ac->SN, BUILDING_ARMYCAMP_UPGRADE_BROADSWORD);
            broadswordQueued = true;
            done = true;
        }
    }

    // ==================================================================
    // ★ 箭塔科技提前（已解除门槛）：铜器后立即可研究，不等第3波、不要求军事解锁 ★
    // ==================================================================
    if (!done && !towerTechResearched) {
        auto g = findBuilding(BUILDING_GRANARY);
        if (g && g->Project == ACT_NULL && info.Meat >= 50) {
            BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWER);
            towerTechResearched = true; done = true;
        }
    }
    // 铜器箭塔升级：用户要求"箭塔只用解锁就行，不用升级"→ 用 DISABLE_TOWER_UPGRADE 封禁（省120食物+50石头）
    if (!DISABLE_TOWER_UPGRADE && !done && !bronzeTowerUpgraded && towerTechResearched) {
        auto g = findBuilding(BUILDING_GRANARY);
        if (g && g->Project == ACT_NULL && info.Meat >= 120 && info.Stone >= 50) {
            BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWE_UPGRADE);
            bronzeTowerUpgraded = true; done = true;
        }
    }

    // ==================================================================
    // ★ TIER 2+3 前置锁：军事解锁前不研究任何其他科技 ★
    // ==================================================================
    // Before wave 3, only military unlock techs may be researched.
    if (frame < WAVE3_TIME) {
        if (done) techCooldown = 25;
        return;
    }

    bool milUnlocked = (broadswordResearched || compositeBowResearched);
    if (!milUnlocked) {
        if (!done && !towerTechResearched) {
            auto g = findBuilding(BUILDING_GRANARY);
            if (g && g->Project == ACT_NULL && info.Meat >= 50) {
                BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWER);
                towerTechResearched = true; done = true;
            }
        }
        if (done) techCooldown = 25;
        return;
    }

    // ==================================================================
    // ★ TIER 2：军事强化 ★
    // ==================================================================

    // --- 仓库：工具使用（近战+2） ---
    if (!DISABLE_USETOOL_TECH && !done && !useToolDone && info.Meat >= 100) {
        auto s = findBuilding(BUILDING_STOCK);
        if (s && s->Project == ACT_NULL) {
            BuildingAction(s->SN, BUILDING_STOCK_UPGRADE_USETOOL);
            useToolDone = true; done = true;
        }
    }

    // --- 仓库：步兵护甲（近战防御+2） ---
    if (!DISABLE_INFANTRY_ARMOR_TECH && !done && !infantryArmorDone && info.Meat >= 75) {
        auto s = findBuilding(BUILDING_STOCK);
        if (s && s->Project == ACT_NULL) {
            BuildingAction(s->SN, BUILDING_STOCK_UPGRADE_DEFENSE_INFANTRY);
            infantryArmorDone = true; done = true;
        }
    }

    // --- 仓库：弓兵护甲（远程防御+2） ---
    if (!done && !archerArmorDone && info.Meat >= 100) {
        auto s = findBuilding(BUILDING_STOCK);
        if (s && s->Project == ACT_NULL) {
            BuildingAction(s->SN, BUILDING_STOCK_UPGRADE_DEFENSE_ARCHER);
            archerArmorDone = true; done = true;
        }
    }

    // --- 谷仓：箭塔科技（解锁箭塔） ---
    if (!done && !towerTechResearched && info.Meat >= 50) {
        auto g = findBuilding(BUILDING_GRANARY);
        if (g && g->Project == ACT_NULL) {
            BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWER);
            towerTechResearched = true; done = true;
        }
    }

    // --- 谷仓：铜器箭塔升级（同上，DISABLE_TOWER_UPGRADE 封禁：解锁即可，不升级）---
    if (!DISABLE_TOWER_UPGRADE && !done && !bronzeTowerUpgraded && towerTechResearched) {
        auto g = findBuilding(BUILDING_GRANARY);
        if (g && g->Project == ACT_NULL && info.Meat >= 120 && info.Stone >= 50) {
            BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWE_UPGRADE);
            bronzeTowerUpgraded = true; done = true;
        }
    }

    // ==================================================================
    // ★ TIER 3：经济科技 — 成本价即研究 ★
    // ==================================================================

    // --- 市场：木材加工（120食物+75木材） ---
    // ★ 2026-09-06 补幂等标志位：原代码只有 `!done`（仅同帧有效），缺 `!marketWoodUpgraded`，
    //   25 帧冷却一过就会重判一次 → 市场空闲且资源够时【重复研究、重复扣资源】。
    //   其余 4 个市场科技各有标志位，唯独此项漏写，属遗漏而非有意设计。
    if (!DISABLE_MARKET_TECH && !done && !marketWoodUpgraded) {
        auto m = findBuilding(BUILDING_MARKET);
        if (m && m->Project == ACT_NULL && info.Meat >= 120 && info.Wood >= 75) {
            BuildingAction(m->SN, BUILDING_MARKET_WOOD_UPGRADE);
            marketWoodUpgraded = true; done = true;
        }
    }

    // --- 市场：驯养动物（200食物+50木材） ---
    if (!DISABLE_MARKET_TECH && !done && !marketFarmUpgraded) {
        auto m = findBuilding(BUILDING_MARKET);
        if (m && m->Project == ACT_NULL && info.Meat >= 200 && info.Wood >= 50) {
            BuildingAction(m->SN, BUILDING_MARKET_FARM_UPGRADE);
            marketFarmUpgraded = true; done = true;
        }
    }

    // --- 市场：车轮（150食物+100木材） ---
    if (!DISABLE_MARKET_TECH && !done && !wheelResearched) {
        auto m = findBuilding(BUILDING_MARKET);
        if (m && m->Project == ACT_NULL && info.Meat >= 150 && info.Wood >= 100) {
            BuildingAction(m->SN, BUILDING_MARKET_WHEEL_UPGRADE);
            wheelResearched = true; done = true;
        }
    }

    // --- 市场：犁（250食物+75木材） ---
    if (!DISABLE_MARKET_TECH && !done && !marketPlowUpgraded) {
        auto m = findBuilding(BUILDING_MARKET);
        if (m && m->Project == ACT_NULL && info.Meat >= 250 && info.Wood >= 75) {
            BuildingAction(m->SN, BUILDING_MARKET_PLOW_UPGRADE);
            marketPlowUpgraded = true; done = true;
        }
    }

    // --- 市场：工艺（170食物+150木材） ---
    if (!DISABLE_MARKET_TECH && !done && !craftResearched) {
        auto m = findBuilding(BUILDING_MARKET);
        if (m && m->Project == ACT_NULL && info.Meat >= 170 && info.Wood >= 150) {
            BuildingAction(m->SN, BUILDING_MARKET_CRAFT_UPGRADE);
            craftResearched = true; done = true;
        }
    }

    if (done) techCooldown = 25;  // 铜器后加长冷却，1秒1科技
}

// ============================================================
// 军事管理（训练 + 箭塔防御 + 护祭司 + 自动作战）
// ============================================================
void UsrAI::manageMilitary() {
    bool isWarTime = (state >= DEFENSE_WAVE1 && state <= DEFENSE_WAVE3);
    bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
    int humanPop = info.farmers.size() + info.armies.size();
    double BL = (double)BLOCKSIDELENGTH;

    // ====== A. 军事训练 ======
    if (trainCooldown > 0) trainCooldown--;
    // ★ 反攻阶段「能产弓就产弓」：不再受 FOOD_PAUSE_TECH_TRAIN(60食物) 经济保护闸压制，
    //   只要食物够一个弓箭手成本就开产（反攻期把资源变成兵比屯食物更有价值）。
    int trainMinFood = (state >= COUNTERATTACK)
                     ? BUILDING_RANGE_CREATE_BOWMAN_FOOD
                     : FOOD_PAUSE_TECH_TRAIN;
    if (info.Meat >= trainMinFood && trainCooldown <= 0 && humanPop < info.Human_MaxNum) {
        bool trained = false;

        // --- 工具时代：也训练廉价填线兵（凑够目标数就停，之后全力升铜器） ---
        if (!postBronze) {
            int toolArmy = 0;
            for (auto &a : info.armies) if (a.Sort != AT_PRIEST) toolArmy++;
            // 工具时代练兵上限：W1 前 2 个(不拖慢 800 食物升铜器)；W1 开始后提到 6 个——
            // 铜器未升完前本块是唯一产出(廉价填线块 postBronze 才生效)，W2 前只有 2 个棍棒兵曾致祭司被杀。
            // W1→W2 约 8500 帧，足够把守军补到 6 个护祭司；升铜器后由优先级2.5 廉价填线接管(不封顶)。
            // ★ 2026-09-03 用户要求"不训棍棒兵"：DISABLE_CLUBMAN_TRAIN 关掉本块，改由箭塔防守。
            const int TOOL_AGE_ARMY_TARGET = (frame >= WAVE1_TIME) ? 6 : 2;
            if (!DISABLE_CLUBMAN_TRAIN && toolArmy < TOOL_AGE_ARMY_TARGET &&
                info.Meat >= BUILDING_ARMYCAMP_CREATE_CLUBMAN_FOOD) {
                auto ac = findBuilding(BUILDING_ARMYCAMP);
                if (ac && ac->Project == ACT_NULL) {
                    BuildingAction(ac->SN, BUILDING_ARMYCAMP_CREATE_CLUBMAN);
                    trained = true;
                }
            }
        }

        // --- 铜器时代：训练军事单位 ---
        if (postBronze) {
            bool lateGame = (state >= DEFENSE_WAVE3 || frame >= WAVE3_TIME);
            bool counterAtk = (state >= COUNTERATTACK);

            // ==================================================================
            // ★★ 反攻期专用编制（2026-09-02 用户要求）：只产 复合弓兵(主) + 方阵兵(副) ★★
            //   旧逻辑的抢占点：优先级3"爆近战"不检查 trained，反攻期照样产棍棒/骑兵；
            //   优先级4 骑兵在 trained=false 时触发，一次吃掉 80 黄金 = 4 个复合弓兵的黄金 →
            //   黄金长期 <20 → 复合弓兵判据 `info.Gold >= 20` 失败 → 退化成普通弓兵甚至停产。
            //   故反攻期走独立分支，棍棒兵/骑兵/侦察/阔剑全部禁掉。
            // ==================================================================
            if (counterAtk) {
                // ① 复合弓兵（主 DPS）：遍历所有空闲靶场并行产，产量随靶场数(MAX_RANGES)线性提升。
                //    ★ 复合弓兵真实扣费（Development.cpp:744-745，引擎已修正）：食物 + **黄金**(20)，不扣石头。
                //    ★ 黄金不足时**不退化产普通弓**：把黄金攒给复合弓兵，否则又被便宜兵吃掉永远造不出。
                //      仅当复合弓科技没研究出来(compositeBowResearched=false)才用普通弓兜底，避免靶场空转。
                for (auto &b : info.buildings) {
                    if (b.Type != BUILDING_RANGE || b.Project != ACT_NULL) continue;
                    // ★ 15 分钟前完全停产（2026-09-06 用户要求）：见 COMPOSITE_BOW_MIN_FRAME
                    if (frame < COMPOSITE_BOW_MIN_FRAME) continue;
                    if (compositeBowResearched &&
                        info.Meat >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_FOOD &&
                        info.Gold >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_GOLD) {
                        BuildingAction(b.SN, BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN);
                        trained = true;
                    } else if (!compositeBowResearched &&
                               info.Meat >= BUILDING_RANGE_CREATE_BOWMAN_FOOD &&
                               info.Wood >= BUILDING_RANGE_CREATE_BOWMAN_WOOD) {
                        BuildingAction(b.SN, BUILDING_RANGE_CREATE_BOWMAN);
                        trained = true;
                    }
                }

                // ② 方阵兵（副，肉盾挡刀）：双保险保证"复合弓兵为主"——
                //    a) 黄金预留：付完方阵后，黄金仍须够**所有空闲靶场各产一个复合弓**
                //       （方阵 40 金 vs 复合弓 20 金，从根上保证复合弓的黄金不被方阵抢走；
                //        空闲靶场为 0(全在造兵)时按 1 座计，保证任何时刻都留得住 1 个复合弓的黄金）。
                //    b) ★ 数量比例闸：现役方阵数 < (复合弓数+4)/2，即长期趋近 2:1。
                //       +4 缓冲让开局 comp=0 时也先出 2 个方阵顶前排，不会因零弓兵而完全断肉盾。
                int idleRanges = 0;
                for (auto &b : info.buildings)
                    if (b.Type == BUILDING_RANGE && b.Project == ACT_NULL) idleRanges++;
                int goldKeep = BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_GOLD * std::max(1, idleRanges);
                int nCompNow = 0, nHopNow = 0;
                for (auto &a : info.armies) {
                    if (a.Sort == AT_COMPOSITE_BOWMAN)      nCompNow++;
                    else if (a.Sort == AT_HOPLITE)          nHopNow++;
                }
                auto colC = findBuilding(BUILDING_COLLAGE);
                if (colC && colC->Project == ACT_NULL &&
                    nHopNow < (nCompNow + 4) / 2 &&
                    info.Meat >= BUILDING_COLLAGE_CREATE_HOPLITE_FOOD + BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_FOOD &&
                    info.Gold >= BUILDING_COLLAGE_CREATE_HOPLITE_GOLD + goldKeep) {
                    BuildingAction(colC->SN, BUILDING_COLLAGE_CREATE_HOPLITE);
                    trained = true;
                }

                // ③ 诊断打印（每 600 帧）：反攻期兵种构成，用于验证"复合弓兵为主、无骑兵/棍棒混入"
                if (frame % 600 == 0) {
                    int nComp = 0, nBow = 0, nHop = 0, nClub = 0, nCav = 0, nOther = 0;
                    for (auto &a : info.armies) {
                        if (a.Sort == AT_PRIEST) continue;
                        else if (a.Sort == AT_COMPOSITE_BOWMAN) nComp++;
                        else if (a.Sort == AT_BOWMAN)           nBow++;
                        else if (a.Sort == AT_HOPLITE)          nHop++;
                        else if (a.Sort == AT_CLUBMAN)          nClub++;
                        else if (a.Sort == AT_CAVALRY)          nCav++;
                        else nOther++;
                    }
                    DebugText(QString("ARMY | comp:%1 bow:%2 hoplite:%3 club:%4 cav:%5 other:%6 "
                                      "|| ranges:%7/idle:%8 gold:%9 compositeTech:%10")
                              .arg(nComp).arg(nBow).arg(nHop).arg(nClub).arg(nCav).arg(nOther)
                              .arg(countBuildingsExisting(BUILDING_RANGE)).arg(idleRanges)
                              .arg((int)info.Gold).arg((int)compositeBowResearched));
                }
            } else {
            // ==================== 非反攻期：沿用原优先级链（但骑兵受 DISABLE_CAVALRY_TRAIN 门禁）====================
            // 后期/反攻：主要训练弓箭手（复合弓兵优先，未研究时先出普通弓箭手）
            //   ★ 遍历所有空闲靶场并行产弓——弓兵产量随靶场数(MAX_RANGES)线性提升，
            //     实现"反攻阶段多训练弓箭兵"。靶场全忙时 trained 仍 false，下方转产其他兵种不浪费产能。
            // ★ 复合弓兵训练的真实扣费（Development.cpp:744-745，引擎已修正）：
            //     conditionDevelop(BRONZEAGE, RANGE, TIME, 0, ..._FOOD, 0, ..._GOLD)
            //   第6参 need_Stone=0，第7参 need_Gold=BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_GOLD(20)
            //   → 引擎实际扣「食物 + 黄金」，不再扣石头。判据改用 info.Gold。
            //   黄金充足→产复合弓兵；黄金不足则落到下面的普通弓箭手兜底（纯木+食）。
            // ★ 15 分钟前完全停产（2026-09-06 用户要求）：见 COMPOSITE_BOW_MIN_FRAME
            if (lateGame && !trained && frame >= COMPOSITE_BOW_MIN_FRAME) {
                for (auto &b : info.buildings) {
                    if (b.Type != BUILDING_RANGE || b.Project != ACT_NULL) continue;
                    if (compositeBowResearched &&
                        info.Meat >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_FOOD &&
                        info.Gold >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_GOLD) {
                        BuildingAction(b.SN, BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN);
                        trained = true;
                    } else if (info.Meat >= BUILDING_RANGE_CREATE_BOWMAN_FOOD &&
                               info.Wood >= BUILDING_RANGE_CREATE_BOWMAN_WOOD) {
                        // ★ 兜底：复合弓未解锁/石头不足 → 出普通弓箭手，保证「反攻能产弓就产弓」
                        BuildingAction(b.SN, BUILDING_RANGE_CREATE_BOWMAN);
                        trained = true;
                    }
                }
            }

            // 优先级1：复合弓兵（远程DPS，PPT重点）——判据为 info.Gold（引擎真实扣费：食物+黄金）
            //   ★ 15 分钟前完全停产（2026-09-06 用户要求）：见 COMPOSITE_BOW_MIN_FRAME
            if (!trained && compositeBowResearched && frame >= COMPOSITE_BOW_MIN_FRAME) {
                auto r = findBuilding(BUILDING_RANGE);
                if (r && r->Project == ACT_NULL &&
                    info.Meat >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_FOOD &&
                    info.Gold >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_GOLD) {
                    BuildingAction(r->SN, BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN);
                    trained = true;
                }
            }

            // 优先级2：阔剑兵（近战肉盾）
            //   ★ 引擎已修正：训练阔剑兵(Development.cpp:607-608)现真扣 食物+黄金（need_Stone=0）。
            //     若解禁本块：判据应改 info.Gold。注：阔剑科技当前封禁，broadswordResearched 恒 false，本块不会触发。
            if (!trained && broadswordResearched) {
                auto ac = findBuilding(BUILDING_ARMYCAMP);
                if (ac && ac->Project == ACT_NULL &&
                    info.Meat >= BUILDING_ARMYCAMP_CREATE_BROADSWORD_FOOD &&
                    info.Stone >= BUILDING_ARMYCAMP_CREATE_BROADSWORD_GOLD) {
                    BuildingAction(ac->SN, BUILDING_ARMYCAMP_CREATE_BROADSWORD);
                    trained = true;
                }
            }

            // 优先级2.5：PREP/W1/W2/W3期间训练廉价填线兵（前期投石兵已全改为棍棒兵）
            //   ★ 用户要求：前期不再造投石兵，改用棍棒兵填线（无石头依赖、更扛揍、便宜）。
            //   ★ 本块不封顶：W1/W2 复合弓未解锁时仍需廉价近战填线，否则会断兵（反攻期由优先级3 爆近战接管）。
            //   ★ 2026-09-03 用户改需求"不训棍棒兵、改箭塔防守"：DISABLE_CLUBMAN_TRAIN 关掉本块。
            bool canTrainCheap = (isWarTime || state == DEFENSE_PREP);
            if (!DISABLE_CLUBMAN_TRAIN && !trained && canTrainCheap &&
                info.Meat >= BUILDING_ARMYCAMP_CREATE_CLUBMAN_FOOD) {
                auto ac = findBuilding(BUILDING_ARMYCAMP);
                if (ac && ac->Project == ACT_NULL) {
                    BuildingAction(ac->SN, BUILDING_ARMYCAMP_CREATE_CLUBMAN);
                    trained = true;
                }
            }

            // 优先级3：后期/反攻「爆近战」——食物溢出时主攻近战兵，与弓兵混编反攻。
            //   ★ 不依赖全局 trained 闸门(否则单次只能产1弓、近战被饿死)：改为按"建筑空闲"逐栋下发，
            //     与弓兵并行产出；每下发一次置 trained=true 触发 trainCooldown，避免同帧对同建筑重复下令。
            //   - 兵营→棍棒兵(50食物,纯近战填线,无石头/黄金依赖,溢出首选)
            //   - 学院→方阵兵(60食物+40黄金,强力近战,需先建学院)
            //   - 马厩→骑兵(70食物+80黄金;当前 DISABLE_STABLE_BUILD 时无马厩不触发,留作恢复马厩后自动生效)
            if (lateGame && info.Meat >= MELEE_OVERFLOW_FOOD) {
                // 兵营→棍棒兵：★ 2026-09-03 用户要求"不训棍棒兵"，DISABLE_CLUBMAN_TRAIN 关掉，
                //   近战肉盾改由学院方阵兵(下方)承担。
                if (!DISABLE_CLUBMAN_TRAIN) {
                    auto acMelee = findBuilding(BUILDING_ARMYCAMP);
                    if (acMelee && acMelee->Project == ACT_NULL &&
                        info.Meat >= BUILDING_ARMYCAMP_CREATE_CLUBMAN_FOOD) {
                        BuildingAction(acMelee->SN, BUILDING_ARMYCAMP_CREATE_CLUBMAN);
                        trained = true;
                    }
                }
                auto col = findBuilding(BUILDING_COLLAGE);
                if (col && col->Project == ACT_NULL &&
                    info.Meat >= BUILDING_COLLAGE_CREATE_HOPLITE_FOOD &&
                    info.Gold >= BUILDING_COLLAGE_CREATE_HOPLITE_GOLD) {
                    BuildingAction(col->SN, BUILDING_COLLAGE_CREATE_HOPLITE);
                    trained = true;
                }
                // 马厩→骑兵：★ 受 DISABLE_CAVALRY_TRAIN 门禁（2026-09-02 用户要求不训练骑兵）
                if (!DISABLE_CAVALRY_TRAIN) {
                    auto stMelee = findBuilding(BUILDING_STABLE);
                    if (stMelee && stMelee->Project == ACT_NULL &&
                        info.Meat >= BUILDING_STABLE_CREATE_CAVALRY_FOOD &&
                        info.Gold >= BUILDING_STABLE_CREATE_CAVALRY_GOLD) {
                        BuildingAction(stMelee->SN, BUILDING_STABLE_CREATE_CAVALRY);
                        trained = true;
                    }
                }
            }

            // 优先级4：骑兵（冲击远程部队）——★ 受 DISABLE_CAVALRY_TRAIN 门禁
            if (!trained && !DISABLE_CAVALRY_TRAIN) {
                auto st = findBuilding(BUILDING_STABLE);
                if (st && st->Project == ACT_NULL &&
                    info.Meat >= BUILDING_STABLE_CREATE_CAVALRY_FOOD &&
                    info.Gold >= BUILDING_STABLE_CREATE_CAVALRY_GOLD) {
                    BuildingAction(st->SN, BUILDING_STABLE_CREATE_CAVALRY);
                    trained = true;
                }
            }

            // 侦察骑兵训练【已禁用 ENABLE_SCOUT_RECON=false】：2026-09-03 用户改需求，
            //   不再造侦察骑兵，改派感化的战车弓兵/投石车探路（见 manageCounterAttack 先锋分支）。
            if (ENABLE_SCOUT_RECON && !trained && !scoutBuilt && state >= COUNTERATTACK) {
                auto st = findBuilding(BUILDING_STABLE);
                if (st && st->Project == ACT_NULL &&
                    info.Meat >= BUILDING_STABLE_CREATE_SCOUT_FOOD) {
                    BuildingAction(st->SN, BUILDING_STABLE_CREATE_SCOUT);
                    scoutBuilt = true; trained = true;
                }
            }
            }  // ← 闭合 else（非反攻期分支）
        }

        if (trained) trainCooldown = 15;
    }

    // ====== B. 箭塔防御：所有波次手动指挥箭塔攻击进入射程的敌人 ======
    //   ★ 引擎箭塔攻击必须用 HumanAction(箭塔SN, 目标SN)，不能用 BuildingAction——
    //     BuildingAction 第二参语义是"动作编号(action)"，不是目标 SN，传敌 SN 会被当 action 编号处理，箭塔不攻击。
    //   ★ 箭塔的 tagBuilding.Project 被引擎改写为"当前攻击目标 SN"(Core.cpp:582 getObjectSN)，
    //     空闲=-1、攻击中=目标SN，故判断"已在攻击"要用 Project != -1（不是 ACT_NULL=0）。
    if (isWarTime) {
        for (auto &tower : info.buildings) {
            if (tower.Type != BUILDING_ARROWTOWER || tower.Percent < 100) continue;
            if (tower.Project != -1) continue; // 已在攻击（Project=当前目标SN，空闲才=-1）
            // 找箭塔射程内的最近敌人
            double tDR = (tower.BlockDR + 1) * BL;
            double tUR = (tower.BlockUR + 1) * BL;
            int target = findNearestEnemySN(tDR, tUR, 8 * BL); // 箭塔射程约8格
            if (target >= 0) {
                HumanAction(tower.SN, target);
            }
        }
    }

    // ====== C. 获取祭司和TC位置 ======
    double priestDR = 0, priestUR = 0;
    bool priestAlive = false;
    for (auto &a : info.armies) {
        if (a.SN == priestSN) {
            priestDR = a.DR; priestUR = a.UR;
            priestAlive = true; break;
        }
    }

    auto center = findBuilding(BUILDING_CENTER);
    double centerDR = 0, centerUR = 0;
    if (center) {
        centerDR = (center->BlockDR + 1) * BL;
        centerUR = (center->BlockUR + 1) * BL;
    }

    auto enemyNearTC = [&](int enemySN) -> bool {
        if (!center) return false;
        for (auto &e : info.enemy_armies)
            if (e.SN == enemySN)
                return calDistance(centerDR, centerUR, e.DR, e.UR) <= 25 * BL;
        for (auto &e : info.enemy_farmers)
            if (e.SN == enemySN)
                return calDistance(centerDR, centerUR, e.DR, e.UR) <= 25 * BL;
        return false;
    };
    (void)enemyNearTC;   // 保留备用：护驾已取消"敌须在TC 25格内"门槛，显式引用以抑制未使用警告

    // ====== D. 空闲士兵分配攻击指令 ======
    int maxAttackCmds = isWarTime ? 8 : 4;
    int attackCmds = 0;

    // 检测祭司是否受威胁
    bool priestThreatened = false;
    int priestEnemySN2 = -1;
    if (priestAlive) {
        priestEnemySN2 = findNearestEnemySN(priestDR, priestUR, 15 * BL);
        priestThreatened = (priestEnemySN2 >= 0);
    }

    // --- D-1: 祭司护驾（★最高优先级，先于士兵自卫/守家/前出；祭司死=立刻失败） ---
    //   三级：紧急(敌≤8格)→所有兵回防(可打断战斗)；预警(敌≤15格)→空闲/行军兵前往护驾。
    //   目标优先选非投石车(留给祭司感化)；若威胁祭司的只有投石车，保命优先照打。
    //   只召回距祭司 PRIEST_GUARD_RECALL 内的兵，避免把反攻大军从全图拉回。
    std::map<int,int> guardIssued;   // 本帧已下达护驾令的兵：下方 D1/D2 不得抢占覆盖
    if (priestAlive) {
        // ★★ 最高优先级：有敌人正以祭司为目标(WorkObjectSN==priestSN) → 立刻全军扑上拉仇恨。
        //    无视 8/15 距离门槛(远程敌可站 12 格外射祭司)、打断一切战斗、不计召回距离(生死攸关)。
        int attackingPriestSN = -1;
        for (auto &e : info.enemy_armies) {
            if (e.WorkObjectSN == priestSN) { attackingPriestSN = e.SN; break; }
        }

        // 优先非投石车目标；没有再退化为任意敌(含投石车)
        int urgentSN = findNearestEnemyNoStone(priestDR, priestUR, PRIEST_GUARD_URGENT * BL);
        if (urgentSN < 0) urgentSN = findNearestEnemySN(priestDR, priestUR, PRIEST_GUARD_URGENT * BL);
        int alertSN  = findNearestEnemyNoStone(priestDR, priestUR, PRIEST_GUARD_ALERT * BL);
        if (alertSN < 0) alertSN = findNearestEnemySN(priestDR, priestUR, PRIEST_GUARD_ALERT * BL);

        int guardSN = (attackingPriestSN >= 0) ? attackingPriestSN
                    : ((urgentSN >= 0) ? urgentSN : alertSN);
        if (guardSN >= 0) {
            const bool lockedOn = (attackingPriestSN >= 0);   // 敌人已锁定祭司：最高紧急，不计召回距离
            const bool urgent = lockedOn || (urgentSN >= 0);
            int guardCmds = 0;
            for (auto &a : info.armies) {
                if (a.Sort == AT_PRIEST) continue;
                if (guardCmds >= PRIEST_GUARD_MAX_CMDS) break;
                if (lionHunterSN.count(a.SN)) continue;   // ★ 正在猎狮，别把指令覆盖掉
                if (a.NowState == HUMAN_STATE_WORKING) continue;
                // 已接令/正在攻击该目标(引擎 Core.cpp:433 会把 WorkObjectSN 设为目标SN)→不重发，
                // 否则每帧重复 HumanAction 会不断打断攻击动作→兵原地横跳、输出为零。
                if (a.WorkObjectSN == guardSN) continue;
                // 预警级不打断正在战斗的兵；紧急级(敌已锁祭司/贴到8格内)一律召回
                if (a.NowState == HUMAN_STATE_ATTACKING && !urgent) continue;
                if (!lockedOn && calDistance(a.DR, a.UR, priestDR, priestUR) > PRIEST_GUARD_RECALL * BL) continue;
                HumanAction(a.SN, guardSN);
                guardIssued[a.SN] = 1;
                guardCmds++;
            }
            if (urgent && frame % 50 == 0)
                DebugText(QString("[PRIEST GUARD] %1 SN=%2 cmds=%3").arg(lockedOn ? "LOCKED-ON" : "urgent").arg(guardSN).arg(guardCmds));
        }
    }

    // --- D0: 士兵——(护驾已在 D-1 处理)自卫挡刀 / W2+主动前出拦截 ---
    if (priestAlive && center) {
        for (auto &a : info.armies) {
            if (a.Sort == AT_PRIEST) continue;
            // ★ 投石车非反攻期不参战（2026-09-06 用户要求「投石车改为只在反攻阶段攻击敌人」）。
            //   反攻期由 manageCounterAttack 的投石车独立 standoff 分支(~3975)负责；非反攻期本块的
            //   自卫 / W2+前出拦截 / 就近搜敌全部跳过——投石车 SPEED 1.63 极慢且脆弱，派出去等于送掉。
            //   ⚠ 例外：D-1 祭司护驾仍对投石车生效（祭司死=立刻失败，保命高于一切）。
            if (a.Sort == AT_STONE_THROWER) continue;
            if (attackCmds >= maxAttackCmds) break;
            if (lionHunterSN.count(a.SN)) continue;   // ★ 正在猎狮，别把指令覆盖掉

            // ★ 状态闸：WORKING 跳过；ATTACKING(正在输出)不打断；IDLE/WALKING 正常接令。
            //   (WALKING 允许接令：否则敌人在眼前砍祭司/队友，兵却要先把待命路走完→"站着看戏不挡刀")
            if (a.NowState == HUMAN_STATE_WORKING) continue;
            if (a.NowState == HUMAN_STATE_ATTACKING) continue;

            // ★ 优先级1（护驾）：正在攻击祭司的敌人 → 全军扑上去
            //   （★取消原 enemyNearTC "敌须在TC 25格内"门槛：祭司在哪就保到哪，保命高于守家）
            int attackingPriest = -1;
            for (auto &e : info.enemy_armies) {
                if (e.WorkObjectSN == priestSN) { attackingPriest = e.SN; break; }
            }
            if (attackingPriest >= 0) {
                if (a.WorkObjectSN != attackingPriest) {   // 已在打它→不重发，防打断输出
                    HumanAction(a.SN, attackingPriest);
                    attackCmds++;
                }
                continue;
            }

            // ★ 优先级2（护驾）：祭司预警范围有敌（D-1 因限流/超距未召回到的兵）→ 也去护驾
            if (priestThreatened) {
                if (a.WorkObjectSN != priestEnemySN2) {    // 已在打它→不重发，防打断输出
                    HumanAction(a.SN, priestEnemySN2);
                    attackCmds++;
                }
                continue;
            }

            // ★ 优先级3（自卫）：身边8格内有敌才反击——★ 排在护驾之后（用户要求：士兵优先保护祭司）
            int selfEnemy = findNearestEnemyNoStone(a.DR, a.UR, 8 * BL);
            if (a.NowState != HUMAN_STATE_IDLE && selfEnemy < 0) continue;
            if (selfEnemy >= 0) {
                HumanAction(a.SN, selfEnemy);
                attackCmds++;
                continue;
            }

            // W2/W3：主动前出拦截远处敌人
            //   ★ 反攻期(COUNTERATTACK)跳过：前出拦截的 HumanAction 会与 manageCounterAttack
            //     的后撤 HumanMove 同帧打架，导致远程兵被反复拉去攻击、无法后撤(被贴脸输出)。
            if (state >= DEFENSE_WAVE2 && state <= DEFENSE_WAVE3) {
                int farEnemy = findNearestEnemyNoStone(centerDR, centerUR, 25 * BL);
                if (farEnemy >= 0) {
                    HumanAction(a.SN, farEnemy);
                    attackCmds++;
                    continue;
                }
                // 没找到敌人→回基地外围待命（距TC 16格内为外围待命区，不再缩进TC中心→避免不可达失败刷屏）
                double distTC = calDistance(a.DR, a.UR, centerDR, centerUR);
                if (distTC <= 16 * BL) {
                    armyReturnTry[a.SN] = 0;  // 已在外围待命区，清卡死计数
                } else if (armyReturnTry[a.SN] < 24) {
                    // 螺旋前往可达外围点（半径8/11/14格，全在TC建筑外→杜绝进入TC导致不可达失败）
                    int atry = armyReturnTry[a.SN];
                    int aang = atry % 8;
                    int arad = atry / 8; if (arad > 2) arad = 2;
                    const int ARADII[3] = {8, 11, 14};
                    double ara = (double)aang * 3.141592653589793 / 4.0;
                    double aR = ARADII[arad] * BL;
                    double atx = centerDR + std::cos(ara) * aR;
                    double aty = centerUR + std::sin(ara) * aR;
                    atx = max(0.0, min((double)MAP_L * BL, atx));
                    aty = max(0.0, min((double)MAP_U * BL, aty));
                    HumanMove(a.SN, atx, aty);
                    // 卡死检测：不可达/被堵时快速换档（8帧，避免同一不可达点失败刷屏）
                    if (armyIssueFrame.count(a.SN) && a.NowState == HUMAN_STATE_IDLE &&
                        frame - armyIssueFrame[a.SN] > 8 &&
                        calDistance(a.DR, a.UR, armyIssueDR[a.SN], armyIssueUR[a.SN]) < 1.0 * BL) {
                        armyReturnTry[a.SN]++;
                    }
                    armyIssueDR[a.SN] = a.DR; armyIssueUR[a.SN] = a.UR; armyIssueFrame[a.SN] = frame;
                }
                // atry>=24：全部档失败→放弃移动，就地待命（防无限刷屏）
                attackCmds++;
                continue;
            }

            // W1/非战时：就近搜敌攻击 + 回基地待命
            //   ★ 反攻期(COUNTERATTACK)跳过：此分支在反攻期会掉进来（上面 3294 前出拦截已排除反攻期，
            //     但这里无 state 门禁），给"25格内无敌人"的军队(含投石车)下发"回基地螺旋待命"HumanMove，
            //     与 manageCounterAttack 的推进/standoff 同帧打架 → 投石车被反复拉回 TC 又推出去，来回抽搐。
            //     反攻期单位调度完全交给 manageCounterAttack，此处不额外下发攻击/回撤令。
            if (state == COUNTERATTACK) {
                // 反攻期：不在此处发令（交给 manageCounterAttack 统一调度拉扯/推进）
            } else {
                int nearbyEnemy = findNearestEnemyNoStone(centerDR, centerUR, 25 * BL);
                if (nearbyEnemy >= 0) {
                    HumanAction(a.SN, nearbyEnemy);
                } else {
                    double distToTC = calDistance(a.DR, a.UR, centerDR, centerUR);
                    if (distToTC <= 16 * BL) {
                        armyReturnTry[a.SN] = 0;  // 已在外围待命区，清卡死计数
                    } else if (armyReturnTry[a.SN] < 24) {
                        // 回基地外围待命：螺旋前往可达外围点（半径8/11/14格，全在TC建筑外→避免不可达失败）
                        int atry = armyReturnTry[a.SN];
                        int aang = atry % 8;
                        int arad = atry / 8; if (arad > 2) arad = 2;
                        const int ARADII[3] = {8, 11, 14};
                        double ara = (double)aang * 3.141592653589793 / 4.0;
                        double aR = ARADII[arad] * BL;
                        double atx = centerDR + std::cos(ara) * aR;
                        double aty = centerUR + std::sin(ara) * aR;
                        atx = max(0.0, min((double)MAP_L * BL, atx));
                        aty = max(0.0, min((double)MAP_U * BL, aty));
                        HumanMove(a.SN, atx, aty);
                        // 卡死检测：不可达/被堵时快速换档（8帧，避免同一不可达点失败刷屏）
                        if (armyIssueFrame.count(a.SN) && a.NowState == HUMAN_STATE_IDLE &&
                            frame - armyIssueFrame[a.SN] > 8 &&
                            calDistance(a.DR, a.UR, armyIssueDR[a.SN], armyIssueUR[a.SN]) < 1.0 * BL) {
                            armyReturnTry[a.SN]++;
                        }
                        armyIssueDR[a.SN] = a.DR; armyIssueUR[a.SN] = a.UR; armyIssueFrame[a.SN] = frame;
                    }
                    // atry>=24：放弃移动，就地待命（防无限刷屏）
                }
            }
            attackCmds++;
        }
    }

    // --- D1: 波次期间TC附近有敌人时优先清除 ---
    if (isWarTime && center && attackCmds < maxAttackCmds) {
        int tcEnemy = findNearestEnemyNoStone(centerDR, centerUR, 25 * BL);
        if (tcEnemy >= 0) {
            for (auto &a : info.armies) {
                if (a.Sort == AT_PRIEST) continue;
                if (a.Sort == AT_STONE_THROWER) continue;   // ★ 投石车只在反攻期攻击（2026-09-06）
                if (guardIssued.count(a.SN)) continue;   // 本帧已去护驾→不得抢占覆盖
                if (lionHunterSN.count(a.SN)) continue;  // ★ 正在猎狮，别把指令覆盖掉
                if (a.NowState != HUMAN_STATE_IDLE) continue;
                if (attackCmds >= maxAttackCmds) break;
                HumanAction(a.SN, tcEnemy);
                attackCmds++;
            }
        }
    }

    // --- D2: 每个空闲士兵搜敌攻击 ---
    //   ★ 反攻期(COUNTERATTACK)跳过：此块给 IDLE 兵就近下 HumanAction 攻击令，
    //     会覆盖 manageCounterAttack 的后撤 HumanMove，导致远程兵站着打对面不逃跑。
    if (state == COUNTERATTACK) {
        // 反攻期单位调度完全交给 manageCounterAttack 的拉扯逻辑，此处不额外下发攻击令。
    } else
    for (auto &a : info.armies) {
        if (a.Sort == AT_PRIEST) continue;
        if (a.Sort == AT_STONE_THROWER) continue;   // ★ 投石车只在反攻期攻击（2026-09-06）
        if (guardIssued.count(a.SN)) continue;   // 本帧已去护驾→不得抢占覆盖
        if (lionHunterSN.count(a.SN)) continue;  // ★ 正在猎狮，别把指令覆盖掉
        if (a.NowState != HUMAN_STATE_IDLE) continue;
        if (attackCmds >= maxAttackCmds) break;

        bool isRanged = (a.Sort == AT_BOWMAN || a.Sort == AT_COMPOSITE_BOWMAN ||
                         a.Sort == AT_CHARIOT_ARCHER || a.Sort == AT_SLINGER);
        double searchRange = isRanged ? 10 : 6;
        searchRange *= BL;

        int enemySN = findNearestEnemyNoStone(a.DR, a.UR, searchRange);
        if (enemySN < 0) continue;

        // 校验：敌人目标必须在防御圈内
        double eDR = 0, eUR = 0;
        bool foundEnemy = false;
        for (auto &e : info.enemy_armies) {
            if (e.SN == enemySN) { eDR = e.DR; eUR = e.UR; foundEnemy = true; break; }
        }
        if (!foundEnemy) {
            for (auto &e : info.enemy_farmers) {
                if (e.SN == enemySN) { eDR = e.DR; eUR = e.UR; foundEnemy = true; break; }
            }
        }
        if (!foundEnemy) continue;

        bool inDefenseZone = false;
        if (priestAlive && calDistance(priestDR, priestUR, eDR, eUR) <= 25 * BL)
            inDefenseZone = true;
        if (!inDefenseZone && center && calDistance(centerDR, centerUR, eDR, eUR) <= 25 * BL)
            inDefenseZone = true;
        if (!inDefenseZone) continue;

        HumanAction(a.SN, enemySN);
        attackCmds++;
    }
}

// ============================================================
// 反攻管理（PPT策略：侦察→集结→推进→祭司转化武器厂）
// ============================================================
void UsrAI::manageCarriedResources() {
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (f.Resource <= 0) {
            depositFarmers.erase(f.SN);
            depositStartFrame.erase(f.SN);
            continue;
        }
        if (f.NowState != HUMAN_STATE_IDLE) {
            depositFarmers.erase(f.SN);
            depositStartFrame.erase(f.SN);
            continue;
        }
        if (depositFarmers.count(f.SN)) {
            if (frame - depositStartFrame[f.SN] < 30) continue;
            depositStartFrame[f.SN] = frame;
        }

        // ★ 就近交付（2026-09-03 修）：按资源类型就近选交付建筑，而非 TC 无条件优先。
        //   原逻辑 TC 放最前 break，导致瞪羚肉/浆果(均 HUMAN_STOCKFOOD)/木/金/石都优先交回 TC，
        //   瞪羚群中心建的仓库(STOCK)形同虚设——猎人仍跑回 TC 交付。
        //   资源→建筑映射（引擎确认）：瞪羚/大象/浆果/树/石/金 → 仓库(STOCK，Building.cpp:549 收
        //   WOOD/STOCKFOOD/STONE/GOLD)；农场 → 谷仓(GRANARY，收 GRANARYFOOD)；鱼 → 码头(DOCK)。
        //   故：STOCKFOOD/WOOD/STONE/GOLD → 就近仓库；GRANARYFOOD → 就近谷仓；DOCKFOOD → 就近码头；
        //   无匹配建筑 → 退回最近 TC 兜底。
        tagBuilding* depot = nullptr;
        double bestDepotDist = 1e12;
        for (auto &b : info.buildings) {
            if (b.Percent != 100) continue;
            double bDR = (b.BlockDR + 1) * BLOCKSIDELENGTH, bUR = (b.BlockUR + 1) * BLOCKSIDELENGTH;
            double dd = calDistance(f.DR, f.UR, bDR, bUR);
            bool match = false;
            if (f.ResourceSort == HUMAN_GRANARYFOOD) {
                if (b.Type == BUILDING_GRANARY) match = true;         // 农场食物 → 谷仓
            } else if (f.ResourceSort == HUMAN_DOCKFOOD) {
                if (b.Type == BUILDING_DOCK) match = true;            // 鱼肉 → 码头
            } else {
                // HUMAN_WOOD / HUMAN_STOCKFOOD(瞪羚肉/浆果) / HUMAN_STONE / HUMAN_GOLD → 仓库
                if (b.Type == BUILDING_STOCK) match = true;
            }
            if (match && dd < bestDepotDist) { depot = &b; bestDepotDist = dd; }
        }
        if (!depot) {
            // 无匹配建筑 → 退回 TC（顺便选最近的 TC）
            double bestTcDist = 1e12;
            for (auto &b : info.buildings) {
                if (b.Percent != 100 || b.Type != BUILDING_CENTER) continue;
                double dd = calDistance(f.DR, f.UR, (b.BlockDR + 1) * BLOCKSIDELENGTH, (b.BlockUR + 1) * BLOCKSIDELENGTH);
                if (dd < bestTcDist) { depot = &b; bestTcDist = dd; }
            }
        }
        if (depot) {
            HumanAction(f.SN, depot->SN);
            depositFarmers.insert(f.SN);
            depositStartFrame[f.SN] = frame;
        }
    }
}

// ============================================================
// 村民安全：敌人不会主动攻击村民，故不再让村民看到敌人就撤退/驻留。
// 村民照常采集生产，无需躲避。保留空函数以兼容 processData 的调用。
// （原"村民撤退"逻辑已按用户要求移除。）
// ============================================================
void UsrAI::manageFirstWaveDefense() {
    // 敌人不主动攻击村民 → 无需撤退。waveBlockers 保持空，村民正常分配采集。
    waveBlockers.clear();
}
void UsrAI::manageCounterAttack() {
    double BL = (double)BLOCKSIDELENGTH;

    // 可走判定：已探索(非UNKNOWN/OCEAN)且不在树林/石矿/金矿内。
    // 关键：树林/石矿/金矿在引擎里都是放在 GRASS 格上的独立资源对象，地图格类型仍是 GRASS，
    // 故"已探索"≠"可走"——不额外排除这些资源，落点选到其格上→引擎无法寻路、单位卡死。
    // 预建逐格 forestGrid：树节点±2格、矿节点±1格记为障碍(只建一次，O(1)查询)。
    // (若后续能拿到全局 Map*，可改用 TreeBlock[bx][by] 做更精确的逐格判断；此处用资源节点近似。)
    std::vector<std::vector<char>> forestGrid(MAP_L, std::vector<char>(MAP_U, 0));
    for (auto &r : info.resources) {
        if (r.Cnt <= 0) continue;
        if (r.Type != RESOURCE_TREE && r.Type != RESOURCE_STONE && r.Type != RESOURCE_GOLD) continue;
        int tx = (int)(r.DR / BL), ty = (int)(r.UR / BL);
        int rad = (r.Type == RESOURCE_TREE) ? 2 : 1;   // 树冠大(±2格)，矿堆小(±1格)
        for (int ddx = -rad; ddx <= rad; ++ddx)
            for (int ddy = -rad; ddy <= rad; ++ddy) {
                int cx = tx + ddx, cy = ty + ddy;
                if (cx >= 0 && cy >= 0 && cx < MAP_L && cy < MAP_U) forestGrid[cx][cy] = 1;
            }
    }
    auto isPassableAt = [&](double x, double y) -> bool {
        if (!info.theMap) return false;
        int bx = (int)(x / BL), by = (int)(y / BL);
        if (bx < 0 || by < 0 || bx >= MAP_L || by >= MAP_U) return false;
        int t = (*info.theMap)[bx][by].type;
        if (t == MAPPATTERN_UNKNOWN || t == MAPPATTERN_OCEAN) return false;  // 未探索/海不可走
        if (forestGrid[bx][by]) return false;                               // 林内不可走
        return true;
    };

    // 绕路兜底：当直行/偏转锥都找不到可走落点(被大片树林或海拦住)时，从当前格做 BFS——
    // 仅沿"可走已探索格"扩散，在可达范围内选"离目标最近的可走格"作为航点→自然绕开障碍、沿已探明陆地推进。
    // 不用 std::queue(本文件未包含<queue>)，用 vector 当环形队列；bestD 初值取大常数避免依赖 climits。
    auto findDetourWaypoint = [&](double fx, double fy, double tx, double ty,
                                  double &wx, double &wy) -> bool {
        int sx = (int)(fx / BL), sy = (int)(fy / BL);
        int gx = (int)(tx / BL), gy = (int)(ty / BL);
        if (sx < 0 || sy < 0 || sx >= MAP_L || sy >= MAP_U) return false;
        const int R = 24;            // BFS 最大半径(格)
        const int MAXVISIT = 2200;   // 访问上限，防极端卡顿时开销爆炸
        std::vector<std::vector<int>> dist(MAP_L, std::vector<int>(MAP_U, -1));
        std::vector<std::pair<int,int>> q; q.reserve(MAXVISIT + 8);
        q.push_back({sx, sy}); dist[sx][sy] = 0;
        int head = 0, bestCX = -1, bestCY = -1, bestD = 1000000000, visited = 0;
        const int d4x[4] = {1, -1, 0, 0}, d4y[4] = {0, 0, 1, -1};
        while (head < (int)q.size() && visited < MAXVISIT) {
            int cx = q[head].first, cy = q[head].second; head++; visited++;
            // 候选航点：非起点且可走→取离目标(格)最近者
            if (!(cx == sx && cy == sy) && isPassableAt(cx*BL + BL*0.5, cy*BL + BL*0.5)) {
                int dd = (cx - gx)*(cx - gx) + (cy - gy)*(cy - gy);
                if (dd < bestD) { bestD = dd; bestCX = cx; bestCY = cy; }
            }
            if (dist[cx][cy] >= R) continue;   // 超出半径不再扩展
            for (int d = 0; d < 4; ++d) {
                int nx = cx + d4x[d], ny = cy + d4y[d];
                if (nx < 0 || ny < 0 || nx >= MAP_L || ny >= MAP_U) continue;
                if (dist[nx][ny] != -1) continue;
                if (!isPassableAt(nx*BL + BL*0.5, ny*BL + BL*0.5)) continue;  // 仅扩展可走格
                dist[nx][ny] = dist[cx][cy] + 1;
                q.push_back({nx, ny});
            }
        }
        if (bestCX < 0) return false;
        wx = bestCX*BL + BL*0.5; wy = bestCY*BL + BL*0.5;
        return true;
    };

    // 坐标轴步进：对角正前方被海/石/林拦住时，先沿单一坐标轴(±X 或 ±Y)走一步、再走另一轴，
    // 形成 L 形绕行——沿障碍边缘(海岸/林缘/矿缘)稳步推进，比纯角度偏转更稳、不会卡死。
    // 候选：全步→半步→1/4步，依次试 X 轴与 Y 轴方向(朝目标靠近的符号)，取"可走且离目标最近"者。
    auto axisAlignedTry = [&](double fx, double fy, double tx, double ty,
                              double STEP, double &wx, double &wy) -> bool {
        double dx = tx - fx, dy = ty - fy;
        int sx = (dx >= 0 ? 1 : -1), sy = (dy >= 0 ? 1 : -1);
        double bestWx = 0, bestWy = 0, bestD = 1e18; bool found = false;
        const double fr[3] = {1.0, 0.5, 0.25};
        for (int i = 0; i < 3; ++i) {          // 全步 → 半步 → 1/4步
            for (int j = 0; j < 2; ++j) {      // 先 X 轴 → 再 Y 轴
                double cx = fx + (j == 0 ? sx * fr[i] * STEP : 0.0);
                double cy = fy + (j == 1 ? sy * fr[i] * STEP : 0.0);
                if (!isPassableAt(cx, cy)) continue;
                double d = (cx - tx) * (cx - tx) + (cy - ty) * (cy - ty);
                if (d < bestD) { bestD = d; bestWx = cx; bestWy = cy; found = true; }
            }
        }
        if (found) { wx = bestWx; wy = bestWy; return true; }
        return false;
    };

    // 朝目标走“一步”：步长不超过单位视野，落点必须是已探索可走格(非海/非林/非矿)；
    // 直行点不可走时缩短步长/坐标轴 L 形绕行/左右偏转；锥内全不可走则启用 BFS 绕路兜底(选可达且离目标最近的可走航点)。
    auto nextVisibleStep = [&](double fx, double fy, double tx, double ty,
                               double stepBlocks, double &wx, double &wy) -> bool {
        double dx = tx - fx, dy = ty - fy;
        double len = std::sqrt(dx*dx + dy*dy);
        if (len < 0.01) return false;
        const double STEP = stepBlocks * BL;
        double gx, gy;
        if (len <= STEP) { gx = tx; gy = ty; }
        else { gx = fx + dx / len * STEP; gy = fy + dy / len * STEP; }
        if (isPassableAt(gx, gy)) { wx = gx; wy = gy; return true; }

        // 逐步缩短，直到落在可走格
        for (int k = 1; k <= 5; ++k) {
            double r = 1.0 - 0.15 * k;
            double cx = fx + dx / len * STEP * r;
            double cy = fy + dy / len * STEP * r;
            if (isPassableAt(cx, cy)) { wx = cx; wy = cy; return true; }
        }

        // 坐标轴 L 形绕行：对角被海/石/林拦住→先沿任一坐标轴(±X或±Y)走一步再走另一轴，
        // 沿障碍边缘推进，自然地"先走一个方向再走另一个方向"，避免卡死。
        if (axisAlignedTry(fx, fy, tx, ty, STEP, wx, wy)) return true;

        // 左右偏转找“更接近目标且可走”的点
        double baseAng = std::atan2(dy, dx);
        for (int off = 1; off <= 8; ++off) {
            for (int sign = -1; sign <= 1; sign += 2) {
                double ang = baseAng + sign * off * 12.0 * 3.141592653589793 / 180.0;
                double cx = fx + std::cos(ang) * STEP;
                double cy = fy + std::sin(ang) * STEP;
                if (!isPassableAt(cx, cy)) continue;
                if (std::cos(ang - baseAng) > 0.3) { wx = cx; wy = cy; return true; }
            }
        }

        // 锥内全不可走(被大片树林/海拦住)→BFS 绕路：选可达且离目标最近的可走航点
        return findDetourWaypoint(fx, fy, tx, ty, wx, wy);
    };

    auto isRanged = [&](int sort) -> bool {
        return sort == AT_STONE_THROWER || sort == AT_BOWMAN ||
               sort == AT_COMPOSITE_BOWMAN || sort == AT_SLINGER ||
               sort == AT_CHARIOT_ARCHER;
    };

    // 近战兵种(短手、贴身肉搏)：用于判断敌是否会"冲过来贴身打我们"。
    // 拉扯(kiting)时对近战敌要更早后撤、后撤更远——它们射程极短但会持续追击贴身。
    auto isMeleeSort = [&](int sort) -> bool {
        return sort == AT_CLUBMAN || sort == AT_SCOUT || sort == AT_SWORDSMAN ||
               sort == AT_IMPROVED || sort == AT_CAVALRY || sort == AT_HOPLITE ||
               sort == AT_CHARIOT || sort == AT_BROADSWORDSMAN;
    };

    // 各远程兵种最大攻击射程(格)：投石车10 / 复合弓7 / 战车弓7 / 弓5 / 投石兵4（与 config.json 一致）。
    //   用于反攻拉扯(kiting)：把敌方保持在最远射程边缘无伤输出。
    auto rangedMaxRange = [&](int sort) -> double {
        switch (sort) {
            case AT_STONE_THROWER:   return 10.0 * BL;
            case AT_COMPOSITE_BOWMAN: return 7.0 * BL;
            case AT_CHARIOT_ARCHER:  return 7.0 * BL;
            case AT_BOWMAN:          return 5.0 * BL;
            case AT_SLINGER:         return 4.0 * BL;
            default:                 return 5.0 * BL;
        }
    };

    // ====== 1. 侦察阶段：寻找敌方武器厂 ======
    if (enemySiegeSN == -1) {
        auto siege = findEnemyBuilding(BUILDING_SIEGE);
        if (siege) {
            enemySiegeSN = siege->SN;
            rallyDR = siege->BlockDR;
            rallyUR = siege->BlockUR;
            DebugText(QString(">> Enemy Siege Workshop found at (%1,%2)!").arg(rallyDR).arg(rallyUR));
        }
    }

    // 侦察骑兵补造【已禁用 ENABLE_SCOUT_RECON=false】：探路改由感化的战车弓兵/投石车承担
    // （见下方主循环先锋分支），不再单独造侦察骑兵。
    if (ENABLE_SCOUT_RECON && enemySiegeSN == -1 && !scoutBuilt) {
        auto st = findBuilding(BUILDING_STABLE);
        if (st && st->Project == ACT_NULL && info.Meat >= BUILDING_STABLE_CREATE_SCOUT_FOOD) {
            BuildingAction(st->SN, BUILDING_STABLE_CREATE_SCOUT);
            scoutBuilt = true;
        }
    }

    // 反攻目标：已发现武器厂→武器厂；未发现→TC 的对角角落（敌人基地方向）
    tagBuilding* siege = nullptr;
    if (enemySiegeSN != -1) siege = findEnemyBuilding(BUILDING_SIEGE);
    if (enemySiegeSN != -1 && !siege) {
        // 已记录武器厂但敌方列表里没有了：检查是否已被我方转化
        bool converted = false;
        for (auto &b : info.buildings)
            if (b.Type == BUILDING_SIEGE) { converted = true; break; }
        if (converted) {
            state = VICTORY;
            DebugText("!!! VICTORY! Siege Workshop converted !!!");
            return;
        }
        enemySiegeSN = -1;   // 不是转化则重新搜索
    }
    // ★ 探到过敌方基地：一旦 info.enemy_buildings 出现过敌方建筑，记录其方位并【持久化】——
    //   即便之后暂时失去视野/该建筑消失，也记得大致方位，反攻时直接奔袭基地而非盲走对角角落。
    //   定位优先级：武器厂 > 敌方TC > 列表首个敌建筑(任一敌建筑出现即视为探到基地)。
    if (!enemyBaseScouted && info.enemy_buildings.size() > 0) {
        tagBuilding* eb = findEnemyBuilding(BUILDING_SIEGE);
        if (!eb) eb = findEnemyBuilding(BUILDING_CENTER);
        if (!eb) eb = &info.enemy_buildings[0];
        enemyBaseScouted = true;
        enemyBaseDR = (eb->BlockDR + 1) * BL;
        enemyBaseUR = (eb->BlockUR + 1) * BL;
        DebugText(QString(">> Enemy base scouted at (%1,%2)!").arg(enemyBaseDR).arg(enemyBaseUR));
    }
    // directMarch：已知敌方基地真实位置(找到武器厂 或 探到过敌方建筑)→ 让引擎全图寻路直奔基地；
    //   否则(完全未探明)仍走对角角落猜测路线、逐步摸索已探索区域(原行为不变)。
    bool directMarch = (siege != nullptr) || enemyBaseScouted;

    double targetDR, targetUR;
    if (siege) {
        targetDR = (siege->BlockDR + 1) * BL;
        targetUR = (siege->BlockUR + 1) * BL;
    } else if (enemyBaseScouted) {
        targetDR = enemyBaseDR; targetUR = enemyBaseUR;   // ★ 探到过基地→直奔已知方位
    } else {
        auto center = findBuilding(BUILDING_CENTER);
        double tcDR = center ? (center->BlockDR + 1) * BL : MAP_L * BL * 0.5;
        double tcUR = center ? (center->BlockUR + 1) * BL : MAP_U * BL * 0.5;
        // ★ 取 TC 的【真正对角角落】：必须【逐轴独立取反】，不能用一个"坐标和"去二选一。
        //   ✗ 旧逻辑：tcDR+tcUR < (MAP_L+MAP_U)*0.5*BL ? (MAP_L,MAP_U) : (0,0)
        //     → 永远只在主对角线两端 (0,0)↔(L,U) 之间二选一，【永远到不了另两个角 (L,0)/(0,U)】。
        //     → 后果：TC 位于反对角线上(左下/右上)时，目标被定成【相邻角】而非对角，
        //       正是"不会走到对角线、而是走到相邻角落"的根因。
        //       例(方形图) TC 在左下(0,U)：旧目标=左上(0,0)，同属左边界→【相邻角】；真正对角应是右上(L,0)。
        //   ✓ 逐轴取反后四种情况全对：左上→右下、右上→左下、左下→右上、右下→左上。
        //   CORNER_INSET：精确角落点 (MAP_L*BL, MAP_U*BL) 落到 bx=MAP_L → 越界 → isPassableAt 恒 false，
        //     单位永远走不到该点(只能在其外侧反复缩短/偏转)。故内缩 3 格，保证目标点界内且可达。
        const int CORNER_INSET = 3;
        targetDR = (tcDR < MAP_L * BL * 0.5) ? (MAP_L - CORNER_INSET) * BL : CORNER_INSET * BL;
        targetUR = (tcUR < MAP_U * BL * 0.5) ? (MAP_U - CORNER_INSET) * BL : CORNER_INSET * BL;
    }

    // ====== 1.5 祭司护驾（★优先于反攻推进：祭司死=立刻失败） ======
    //   manageMilitary 的护驾令会被本函数的推进令【同帧覆盖】(UsrAI.cpp 124/127-129 每帧先跑
    //   manageMilitary、反攻期再追加本函数)，故反攻期必须在此再判一次，紧急时直接 return 停止推进。
    {
        double pDR = 0, pUR = 0; bool pAlive = false;
        for (auto &a : info.armies) if (a.Sort == AT_PRIEST) { pDR = a.DR; pUR = a.UR; pAlive = true; break; }
        if (pAlive) {
            // ★ 敌人已锁祭司(WorkObjectSN==priestSN) 或 紧急(敌≤PRIEST_GUARD_URGENT 格) → 叫停反攻回防。
            int attackingPriestSN = -1;
            for (auto &e : info.enemy_armies) {
                if (e.WorkObjectSN == priestSN) { attackingPriestSN = e.SN; break; }
            }
            int guardSN = attackingPriestSN;
            if (guardSN < 0) {
                guardSN = findNearestEnemyNoStone(pDR, pUR, PRIEST_GUARD_URGENT * BL);
                if (guardSN < 0) guardSN = findNearestEnemySN(pDR, pUR, PRIEST_GUARD_URGENT * BL);
            }
            if (guardSN >= 0) {
                for (auto &a : info.armies) {
                    if (a.Sort == AT_PRIEST) continue;
                    if (a.WorkObjectSN == guardSN) continue;   // 已在打它→不重发，防打断输出
                    if (attackingPriestSN < 0 && calDistance(a.DR, a.UR, pDR, pUR) > PRIEST_GUARD_RECALL * BL) continue;
                    HumanAction(a.SN, guardSN);
                }
                if (frame % 50 == 0)
                    DebugText(QString("[PRIEST GUARD] counterattack HALT -> defend priest, target SN=%1").arg(guardSN));
                return;
            }
        }
    }

    // ====== 2. 集结与推进（投石车/远程优先，逐步走已探索区域） ======
    int marchCmds = 0;
    int armyCount = 0;
    for (auto &a : info.armies) if (a.Sort != AT_PRIEST) armyCount++;  // 非祭司军队总数(近战集结门槛用)
    // ★ 全体反攻门槛：所有军事单位(非祭司，含远程/近战/投石车)≥COUNTER_ATTACK_MIN_ARMY 才一起反攻；
    //   或到 COUNTER_ATTACK_FORCE_TIME(24分钟) 强制一起进攻——避免人数不足时零散冲出被敌方集火。
    bool readyToAttack = (armyCount >= COUNTER_ATTACK_MIN_ARMY) || (frame >= COUNTER_ATTACK_FORCE_TIME);
    // 集结中心：未达门槛时全军回己方 TC 附近集结待命(形成密集兵力，来敌也能抱团防守)
    tagBuilding* rallyTC = findBuilding(BUILDING_CENTER);
    double rallyCtrDR = rallyTC ? (rallyTC->BlockDR + 1) * BL : MAP_L * BL * 0.5;
    double rallyCtrUR = rallyTC ? (rallyTC->BlockUR + 1) * BL : MAP_U * BL * 0.5;
    tagArmy* priest = nullptr;

    // 脱困航点：正常时用 nextVisibleStep 朝目标步进；判定卡死后按档位把"朝目标"方向逐档偏转 45°
    // 做扇形扫描(8格远)，优先取可走落点 → 绕出死角(L形口袋/林间空地/海岸死胡同)；
    // 扫描点仍不可走则退回 nextVisibleStep(内部含 BFS 绕路兜底)。
    auto marchWaypoint = [&](double fx, double fy, double &wx, double &wy, int stuckTry,
                             double stepBlocks) -> bool {
        if (stuckTry <= 0) return nextVisibleStep(fx, fy, targetDR, targetUR, stepBlocks, wx, wy);
        double dx = targetDR - fx, dy = targetUR - fy;
        if (std::sqrt(dx*dx + dy*dy) < 0.01)
            return nextVisibleStep(fx, fy, targetDR, targetUR, stepBlocks, wx, wy);
        double base = std::atan2(dy, dx);
        double fanR = 8.0;                                  // 扇形扫描半径(格)：大部队 8 格
        if (stepBlocks < 5.0) fanR = stepBlocks + 3.0;      // 探路小步长(4格)→扇形 7 格，别跳太远踩进 UNKNOWN

        // ★ 2026-09-05 修探路卡死（原用户反馈："战车弓兵 91079 每 4 秒 HumanMove 到同一坐标 1168.38,2596.11 永不变"）：
        //   旧逻辑：扇形单档点不可走 → fallback nextVisibleStep → nextVisibleStep 永远先尝试"朝目标 4 格"，
        //     而 isPassableAt 把"朝目标 4 格"那个点判为可通过（点本身可走，但中间有 UNKNOWN 格寻路被引擎拒），
        //     单位原地不动 → fx,fy 不变 → nextVisibleStep 每次输出同一 wx,wy → 30 帧节流一过就 HumanMove 同一坐标。
        //   stuckTry 一直在涨（marchMoveFrame 不刷新），但扇形 fallback 把航点锁死回 nextVisibleStep 同一点。
        //   修复：扇形 8 个角度(stuckTry 决定起点档)全扫一遍；全失败才 fallback findDetourWaypoint BFS，
        //     不再 fallback nextVisibleStep——它的"朝目标 4 格"是原点航点问题来源。
        int startSlot = (stuckTry - 1) % 8;
        for (int off = 0; off < 8; ++off) {
            int slot = (startSlot + off) % 8;
            double ang = base + (double)slot * (3.141592653589793 / 4.0);
            double tx = fx + std::cos(ang) * fanR * BL;
            double ty = fy + std::sin(ang) * fanR * BL;
            tx = max(0.0, min((double)MAP_L * BL, tx));
            ty = max(0.0, min((double)MAP_U * BL, ty));
            if (isPassableAt(tx, ty)) { wx = tx; wy = ty; return true; }
        }
        // 8 个扇形角度全不可走 → BFS 兜底找"任何可达且离目标最近"的航点（不限定方向）
        return findDetourWaypoint(fx, fy, targetDR, targetUR, wx, wy);
    };

    // 统一推进出口：已知敌方基地(directMarch)且未卡死→直接 HumanMove(目标坐标)，
    //   交给引擎全图寻路直奔基地附近(不再逐格试探摸索)；卡死(stuckTry>0)或未知基地→退回 marchWaypoint 逐格步进+BFS兜底。
    //   (卡死时即便 directMarch 也需扇形扫描脱困，故 stuckTry>0 走逐格分支。)
    //   ★ canReissue：directMarch 直奔必须节流——否则每帧重发同一(可能不可达)目标点→刷新 marchCmdFrame
    //     → canReissue 永假 → stuckTry 永不涨 → 单位卡死打转(2026-09-03 踩坑)。
    auto issueMarch = [&](double fx, double fy, int sn, int sort, int stuckTry, bool canReissue) {
        if (directMarch && stuckTry <= 0 && canReissue) {
            HumanMove(sn, targetDR, targetUR);   // ★ 引擎完整寻路：直接走到敌方基地附近
            marchCmdFrame[sn] = frame;
        } else if (directMarch && stuckTry <= 0) {
            // 未到节流窗口：本帧静默，不重复发指令，等 stuckNow 累积 stuckTry 触发脱困
            ;
        } else {
            double wx = 0, wy = 0;
            if (marchWaypoint(fx, fy, wx, wy, stuckTry, 5.0)) {
                HumanMove(sn, wx, wy);
                marchCmdFrame[sn] = frame;
            } else if (stuckTry > 0 && frame % 150 == 0) {
                DebugText(QString("[MARCH STUCK] army SN=%1 sort=%2 try=%3 无可用航点")
                          .arg(sn).arg(sort).arg(stuckTry));
            }
        }
    };

    for (int pass = 0; pass < 2 && marchCmds < 8; ++pass) {
        for (auto &a : info.armies) {
            if (a.Sort == AT_PRIEST) { priest = &a; continue; }
            if (lionHunterSN.count(a.SN)) continue;   // ★ 正在猎狮，别把推进指令盖掉

            // ★ 卡死检测(独立表 marchIssue*/marchMoveFrame，绝不复用 armyIssue*)：只认"是否真有位移"。
            //   原逻辑 `a.NowState != IDLE → continue` 有致命漏洞：单位一旦领到走不到的航点，
            //   引擎会把它一直留在 WALKING → 永不变回 IDLE → 再也收不到任何新指令 → 永久卡死
            //   （既不前进、也不攻击）。故对"长时间无位移"的单位强制重下令脱困。
            //   ★ 探路先锋分支(下方)也复用本检测——先算 stuckTry，探路兵卡死时也能逐档换向脱困，
            //     修复"投石车/战车弓兵探路卡死在基地打转"(此前探路分支在检测之前 continue，无脱困机制)。
            if (!marchIssueDR.count(a.SN)) {          // 首次见到→建立基准
                marchIssueDR[a.SN] = a.DR; marchIssueUR[a.SN] = a.UR;
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
            } else if (calDistance(a.DR, a.UR, marchIssueDR[a.SN], marchIssueUR[a.SN]) > 0.5 * BL) {
                marchIssueDR[a.SN] = a.DR; marchIssueUR[a.SN] = a.UR;  // 有位移→刷新基准
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0; // 并清卡死档，回正常寻路
            }
            // ⚠ ATTACKING(正在开火)绝不算卡死：投石车/弓兵按最大射程站桩输出时本就不位移，
            //   若计入卡死，90帧后会被拽走去移动，直接破坏投石车的 standoff 输出。
            //   这里同时刷新基准，使其停火后重新计时而非立刻被判卡死。
            if (a.NowState == HUMAN_STATE_ATTACKING) {
                marchIssueDR[a.SN] = a.DR; marchIssueUR[a.SN] = a.UR;
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
            }
            bool stuckNow = (frame - marchMoveFrame[a.SN] > 90);        // 90帧无位移→判定卡死
            bool canReissue = !marchCmdFrame.count(a.SN) ||
                              (frame - marchCmdFrame[a.SN] >= 30);      // 30帧节流，防每帧换方向抖动
            if (stuckNow && canReissue) marchStuckTry[a.SN]++;          // 升档：换个方向试
            int stuckTry = marchStuckTry[a.SN];

            // ===== ★ 高机动单位"先锋探路"（独立于集结/接战，最优先调度） =====
            //   用户需求（2026-09-03 改）：不造侦察骑兵，改派【感化的战车弓兵/骑兵(Prof.Lu)】去探路。
            //   ★ 投石车不参与探路（2026-09-03 再修）：投石车 SPEED 1.63 极慢 + VISION 13 虽大，
            //     但探路"4格小步+未探索格当障碍"对慢速单位几乎无法推进，反而把【攻城核心火力】锁死在
            //     TC 附近磨蹭(用户实测"投石车还在 TC 附近、离敌人很远")。故探路只留高机动单位：
            //     战车弓兵(SPEED 4.07、VISION 9) + 骑兵 Prof.Lu(AT_CAVALRY，SPEED 4.07、血150厚)，
            //     投石车回归下方 standoff 攻城分支(跟着大部队朝 target 5格步进推进、最大射程处轰炸)。
            //   未探明敌基地时单独快速奔袭目标方向(对角角落/已知方位)，探到 enemy_buildings → 点亮
            //   enemyBaseScouted → directMarch=true → 大部队直接 HumanMove 全图寻路。
            //   探明后(enemyBaseScouted=true)这些单位恢复正常作战，不再当探路兵。
            //
            //   ★ 卡死修复(2026-09-03)：引擎把"未探索格"当障碍(loadfindPathMapTemperature)，探路只能靠
            //   "走到已探索边界→视野(reset_CellExplore)照亮新格→再走"的渐进推进。此前 8 格大步长一步
            //   直接踩进 UNKNOWN → isPassableAt 拒绝 → BFS 只在已探索格内打转 → 永久卡在基地。
            //   修复：① 步长降到 4 格(稳定落在视野内已探索格，每步推进边界)；② 复用上面算出的 stuckTry
            //   做扇形脱困(复用 marchWaypoint 的 45°/档扫描，绕出森林/海岸死角)；③ 保留 BFS 兜底。
            if ((a.Sort == AT_CHARIOT_ARCHER || a.Sort == AT_CAVALRY) &&
                !enemyBaseScouted && enemySiegeSN == -1) {
                double scx = a.DR, scy = a.UR;
                double wx = 0, wy = 0;
                // stuckTry==0 → 正常 4 格小步贴近边界推进；stuckTry>0 → 扇形换向脱困(内部仍含 BFS 兜底)
                if (marchWaypoint(scx, scy, wx, wy, stuckTry, 4.0)) {
                    HumanMove(a.SN, wx, wy);
                    marchCmdFrame[a.SN] = frame;
                } else if (stuckTry > 0 && frame % 150 == 0) {
                    DebugText(QString("[SCOUT STUCK] SN=%1 sort=%2 try=%3 无可用航点")
                              .arg(a.SN).arg(a.Sort).arg(stuckTry));
                }
                marchCmds++;
                continue;
            }

            // ===== ★ 远程兵反攻拉扯(kiting)后撤——优先于状态闸，可打断 ATTACKING/WALKING =====
            //   根因(2026-09-03 两度修；2026-09-04 三修)：原阈值 d<0.9R 太迟——敌贴到 0.9R(=复合弓6.3格)
            //   才后撤时已早挨打；而下方的"跟进到 0.95R"分支(d≤R+6)更致命——敌在 7~13 格(射程外)
            //   时单位朝敌**主动走近**到 0.95R 位置,触发"反复 HumanMove到敌附近 + HumanAction"循环,
            //   完全失去拉扯(日志现象:"复合弓兵反复在移动和设置攻击目标之间,没有后撤")。
            //   修复:① 后撤阈值放宽到 dD ≤ R+1 格(进入射程就撤,留1格缓冲防边界抖动);
            //        ② 删除"跟进到 0.95R"分支(远程兵不再主动追近落单敌,由 issueMarch 推进逻辑拖动)。
            //   ⚠ 投石车独立 standoff 分支(下方)已单独处理,这里只处理弓/复合弓/投石兵/战车弓。
            if (readyToAttack && isRanged(a.Sort) && a.Sort != AT_STONE_THROWER) {
                const double KR = rangedMaxRange(a.Sort);
                double dEx = 0, dEy = 0; int dSort = -1; double dD = 1e12;
                for (auto &e : info.enemy_armies) {
                    if (e.Sort == AT_STONE_THROWER) continue;   // 投石车留给祭司
                    double dd = calDistance(a.DR, a.UR, e.DR, e.UR);
                    if (dd < dD) { dD = dd; dEx = e.DR; dEy = e.UR; dSort = e.Sort; }
                }
                if (dSort >= 0) {
                    // ★ 进入射程即后撤(含近战贴身:它们的射程极短但会持续追,kiting 须早撤):
                    //   retreatThresh = KR + 1 格(留1格提前量);近战无远程威胁,但会贴身追击,
                    //   用 max(KR+1, 4格) 保证贴上来时甩得够远。
                    // ★ 2026-09-06 五修：后撤阈值 KR+1BL(8格) → 0.5R(复合弓3.5格)。
                    //   根因：旧阈值 8 格【大于】射程 R=7 格 ⇒ 敌人还在射程外弓兵就开始撤，
                    //   撤完落在 1.6R=11.2 格更是远超射程 ⇒ "撤完打不到 → 等敌追近 → 再撤"
                    //   的死循环，全程零输出（用户实测"一直在动、偶尔攻击一下"）。
                    //   标准 kiting 必须【贴脸才撤】：阈值远小于射程，保证撤之前一直在射程内输出。
                    double retreatThresh = isMeleeSort(dSort) ? std::max(0.5 * KR, 3.0 * BL) : 0.5 * KR;
                    if (dD <= retreatThresh) {
                        // ★ 2026-09-04 三修：节流 12 帧(0.48秒) → 30 帧(1秒)。
                        //   12 帧弓兵只走 1 格,而从 7.65 撤到 1.4R=9.8 格要 2.15 格约 16 帧,
                        //   节流一过就重发 HumanMove→引擎不停 reset 路径→弓兵"完全来不及移动"
                        //   (用户实测反馈)。30 帧 = 1 秒,足够弓兵完成 1 次"撤-射"闭环:
                        //   30 帧内走出 2 格到达 9.5 格附近,d=9.5 > R+1BL=7.65 格 → 退出 kiting 段
                        //   → 落到下方 4129 IDLE 站位判定(d=9.5 ≤ 1.5R=10.5)=kActed=true 不发新令,
                        //   完美闭环"边撤边射"。
                        //   兜底:30 帧内即便未到目标点,引擎正常寻路中也不会被覆盖,等 30 帧结束重判。
                        const int KITING_COOLDOWN = 30;
                        bool cool = !marchCmdFrame.count(a.SN) ||
                                    (frame - marchCmdFrame[a.SN] >= KITING_COOLDOWN);
                        // ★ 2026-09-05 四修：后撤倍率 1.4R → 1.6R。
                        //   根因：复合弓 R=7 时 1.4R=9.8 格，与后撤阈值 R+1=7.65 格只差 2.15 格——
                        //     敌近战(速度≈4格/秒)追完这 2.15 格只要约 13 帧，而节流是 30 帧，
                        //     于是复合弓"其实在撤、但每次只挪一点点、大部分时间站着等敌"，
                        //     视觉上就是"复合弓兵不会后撤"(对比投石车 1.6R、撤幅 5 格，明显有效)。
                        //   改 1.6R=11.2 格 → 撤幅 3.55 格，与投石车(5格)同量级，敌需追约 27 帧才再次触发，
                        //     与 30 帧节流匹配，形成稳定的"撤—射"节奏。
                        // ★ 2026-09-06 五修：后撤倍率 1.6R(11.2格) → 0.85R(复合弓5.95格)。
                        //   旧 1.6R 落点【超出射程 7 格】⇒ 撤完打不到，只能干等敌追近再撤，零输出。
                        //   改 0.85R：撤完仍在射程内（5.95 < 7）可继续射击，形成
                        //   「敌贴脸 3.5 格 → 撤到 6 格 → 继续射 → 敌再贴脸 → 再撤」的标准 kiting。
                        const double KITING_RETREAT_MULT = 0.85;
                        if (cool) {
                            // 后撤方向:从敌位置出发,沿"P→敌"方向的反方向退 1.6R 倍射程
                            // = 离敌 1.6R 安全距离,等敌追近再撤,保持"边撤边射"。
                            double ux = (a.DR - dEx) / (dD + 1e-6), uy = (a.UR - dEy) / (dD + 1e-6);
                            double angs[5] = {0.0, 0.6, -0.6, 1.2, -1.2};   // 多方向试退路防被挡
                            bool kitMoved = false;
                            double kitX = 0, kitY = 0;
                            for (int ai = 0; ai < 5; ++ai) {
                                double ca = std::cos(angs[ai]), sa = std::sin(angs[ai]);
                                double rx = dEx + (ux*ca - uy*sa) * KR * KITING_RETREAT_MULT;
                                double ry = dEy + (uy*ca + ux*sa) * KR * KITING_RETREAT_MULT;
                                rx = max(0.0, min((double)MAP_L * BL, rx));
                                ry = max(0.0, min((double)MAP_U * BL, ry));
                                if (isPassableAt(rx, ry)) {
                                    HumanMove(a.SN, rx, ry);
                                    marchCmdFrame[a.SN] = frame;
                                    lastRetreatFrame[a.SN] = frame;   // ★ 后撤保护期起点
                                    marchIssueDR[a.SN] = a.DR; marchIssueUR[a.SN] = a.UR;
                                    marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
                                    kitMoved = true; kitX = rx; kitY = ry;
                                    break;
                                }
                            }
                            // ★ 诊断：每 50 帧打印一次拉扯决策，便于定位"为何看起来没后撤"
                            if (frame % 50 == 0)
                                DebugText(QString("[KIT f=%1] SN=%2 sort=%3 dD=%4 thr=%5 cool=%6 moved=%7 tgt=(%8,%9)")
                                    .arg(frame).arg(a.SN).arg(a.Sort)
                                    .arg(dD / BL, 0, 'f', 2).arg(retreatThresh / BL, 0, 'f', 2)
                                    .arg(cool ? 1 : 0).arg(kitMoved ? 1 : 0)
                                    .arg(kitX / BL, 0, 'f', 1).arg(kitY / BL, 0, 'f', 1));
                        } else if (frame % 50 == 0) {
                            DebugText(QString("[KIT f=%1] SN=%2 sort=%3 dD=%4 thr=%5 WAIT-COOL(%6)")
                                .arg(frame).arg(a.SN).arg(a.Sort)
                                .arg(dD / BL, 0, 'f', 2).arg(retreatThresh / BL, 0, 'f', 2)
                                .arg(frame - (marchCmdFrame.count(a.SN) ? marchCmdFrame[a.SN] : frame)));
                        }
                        continue;   // 后撤优先,跳过下方常规逻辑(即使未到节流窗口也先不给其它令)
                    }
                }
            }

            if (a.NowState != HUMAN_STATE_IDLE) {
                if (!stuckNow || !canReissue) continue;   // 正常行进中不打断；卡死且到窗口才重下令
            } else if (stuckNow && !canReissue) {
                continue;                                  // IDLE但已判卡死→节流，给引擎时间走
            }

            bool ranged = isRanged(a.Sort);
            if (pass == 0 && !ranged) continue;   // 第一遍：投石车+远程
            if (pass == 1 && ranged) continue;    // 第二遍：近战殿后/补位
            if (marchCmds >= 8) break;

            // ★ 全体反攻门槛未达：全军回 TC 附近集结待命，不推进、不接战（含远程/投石车，
            //   避免单个士兵零散冲出被敌方集火；等 armyCount≥20 或到 24 分钟再统一反攻）。
            if (!readyToAttack) {
                if (calDistance(a.DR, a.UR, rallyCtrDR, rallyCtrUR) > 12 * BL && canReissue) {
                    HumanMove(a.SN, rallyCtrDR, rallyCtrUR);
                    marchCmdFrame[a.SN] = frame;
                }
                marchCmds++;
                continue;
            }

            // 投石车：尽量在最大射程处攻击(standoff/kiting)——脆弱攻城单位不贴脸
            if (a.Sort == AT_STONE_THROWER) {
                const double CAT_RANGE = 10.0 * BL;   // 投石车最大射程(DIS_STONE_THROWER=10格)
                int atkSN   = findCatapultTarget(a.DR, a.UR, 15 * BL);   // 攻击目标(含敌方投石车+箭塔，火力压制优先)
                int threatSN = findNearestEnemySN(a.DR, a.UR, CAT_RANGE * 1.6); // 最近威胁(含一切敌,用于判断要不要后撤)
                double ex = 0, ey = 0; bool gotThreat = false;
                if (threatSN >= 0) {
                    for (auto &e : info.enemy_armies) if (e.SN == threatSN) { ex = e.DR; ey = e.UR; gotThreat = true; break; }
                    if (!gotThreat) for (auto &e : info.enemy_farmers) if (e.SN == threatSN) { ex = e.DR; ey = e.UR; gotThreat = true; break; }
                }
                if (gotThreat) {
                    double d = calDistance(a.DR, a.UR, ex, ey);
                    // ★ 2026-09-04 修：阈值改严 d < 0.9*CAT_RANGE(=9格) → d ≤ CAT_RANGE+1(=11格)。
                    //   原阈值敌已贴到 9 格才后撤——投石车 10 格射程,9 格早挨打。改后"进入射程即撤"。
                    if (d <= CAT_RANGE + 1.0 * BL) {
                        // ★ 2026-09-04 三修：加 30 帧节流,防止近战贴脸反复重发 HumanMove→投石车来不及移动。
                        //   (12 帧≈0.48 秒不够走 1 格；30 帧=1 秒足够完成 1 次 standoff 闭环)
                        const int CAT_COOLDOWN = 30;
                        bool cool = !marchCmdFrame.count(a.SN) ||
                                    (frame - marchCmdFrame[a.SN] >= CAT_COOLDOWN);
                        if (cool) {
                            // 敌已进入或贴近射程→后撤到 1.6*CAT_RANGE(远比默认 0.95 远),投石车比弓兵更脆弱
                            double ux = (a.DR - ex) / (d + 1e-6), uy = (a.UR - ey) / (d + 1e-6);
                            double angs[5] = {0.0, 0.6, -0.6, 1.2, -1.2};   // 多方向试退路防被挡/卡树
                            bool moved = false;
                            for (int ai = 0; ai < 5 && !moved; ++ai) {
                                double ca = std::cos(angs[ai]), sa = std::sin(angs[ai]);
                                double rx = ex + (ux*ca - uy*sa) * CAT_RANGE * 1.6;
                                double ry = ey + (uy*ca + ux*sa) * CAT_RANGE * 1.6;
                                rx = max(0.0, min((double)MAP_L * BL, rx));
                                ry = max(0.0, min((double)MAP_U * BL, ry));
                                if (isPassableAt(rx, ry)) { HumanMove(a.SN, rx, ry); marchCmdFrame[a.SN] = frame; moved = true; }
                            }
                            if (!moved && atkSN >= 0) HumanAction(a.SN, atkSN);   // 退路全挡→原地攻击
                        }
                        marchCmds++;
                        continue;
                    }
                }
                if (atkSN >= 0) {
                    HumanAction(a.SN, atkSN);   // 已在射程内→原地攻击不前进(引擎不再逼近)
                } else if (siege && calDistance(a.DR, a.UR, targetDR, targetUR) <= CAT_RANGE) {
                    HumanAction(a.SN, siege->SN);   // 武器厂进入最大射程→轰炸(不贴近)
                } else if (directMarch && stuckTry <= 0 && canReissue) {
                    // ★ 已知敌基地→引擎全图寻路直奔。⚠ 必须带 canReissue 节流：否则每帧重发 HumanMove
                    //   到同一(可能不可达的)目标点 → 刷新 marchCmdFrame → canReissue 永假 → stuckTry
                    //   永不涨 → 投石车卡死在原地打转(2026-09-03 踩坑)。加节流后，无位移 90 帧
                    //   stuckNow 触发 stuckTry 上涨 → 落下方 marchWaypoint 扇形脱困。
                    HumanMove(a.SN, targetDR, targetUR);
                    marchCmdFrame[a.SN] = frame;
                } else {
                    double wx = 0, wy = 0;
                    if (marchWaypoint(a.DR, a.UR, wx, wy, stuckTry, 5.0)) {
                        HumanMove(a.SN, wx, wy);
                        marchCmdFrame[a.SN] = frame;
                    } else if (stuckTry > 0 && frame % 150 == 0) {
                        DebugText(QString("[MARCH STUCK] catapult SN=%1 try=%2 无可用航点")
                                  .arg(a.SN).arg(stuckTry));
                    }
                }
                marchCmds++;
                continue;
            }

            // ★ 远程兵反攻拉扯(kiting)：把敌方勾引到其基地活动范围边缘,卡最远攻击射程无伤输出。
            //   敌方无法离开基地一定范围(leash),故：敌靠近→后撤到最大射程边缘(把敌拉离基地)；
            //   敌在射程内→站桩输出；无敌/敌太远→推进 or 拆基地。
            //   (投石车已在上方独立 standoff 分支处理,此处只处理弓/复合弓/投石兵/战车弓。)
            //   ★ 2026-09-04 修：删除"敌 d≤R+6 → 主动跟进到 0.95R"分支——此分支就是日志里"反复
            //   HumanMove 到敌附近 + HumanAction 设置攻击目标"的元凶。远程兵不再主动追近落单敌,
            //   大部队朝敌基地推进时(下方 issueMarch)远程兵自然会被拖动。
            //   注：敌贴脸(<KR+1GR)的紧急后撤已由上方 kiting 后撤分支处理,此处只处理常态拉扯。
            if (ranged) {
                const double R = rangedMaxRange(a.Sort);
                int kEnemy = findNearestEnemyNoStone(a.DR, a.UR, 20 * BL);
                bool kActed = false;
                if (kEnemy >= 0) {
                    double ex = 0, ey = 0; bool got = false;
                    for (auto &e : info.enemy_armies) if (e.SN == kEnemy) { ex = e.DR; ey = e.UR; got = true; break; }
                    if (!got) for (auto &e : info.enemy_farmers) if (e.SN == kEnemy) { ex = e.DR; ey = e.UR; got = true; break; }
                    if (got) {
                        double d = calDistance(a.DR, a.UR, ex, ey);
                        // ★ 2026-09-04 修：风筝站位判定扩到 d ≤ R*1.5(=10.5格)，而非仅 d ≤ R*1.05(=7.35格)。
                        //   根因：旧条件只"已进最优射程才站桩"，d 在 7.35~10.5 格之间时 kActed=false
                        //   → 落下方 issueMarch → issueMarch 节流 30 帧内反复把弓兵朝敌基地冲。
                        //   弓兵被拖到 dD=7 格以内→上方 kiting 后撤 1.4R → 节流一过 issueMarch 又拖回去。
                        //   日志表现：「24:45 反复 HumanMove + HumanAction 不后退」(用户实测反馈)。
                        //   修复：1.5R 内一律 kActed=true → 不发任何移动令，由上方 kiting 后撤(R+1 格) 接管
                        //   敌贴脸的威胁处理；d ≤ R*1.05 保持攻击(最优射程)；R*1.05 < d ≤ R*1.5 站位不动。
                        //   d > R*1.5 才 issueMarch 推进——保证弓兵被锁在「1.4R~1.5R 风藄圈」内不冲前线。
                        // ★ 2026-09-05 四修：风藄站位圈 1.5R → 1.75R(复合弓 10.5 → 12.25 格)。
                        //   ★★ 必须与上方后撤倍率 KITING_RETREAT_MULT(1.6R) 配套：后撤落到 1.6R=11.2 格，
                        //     若站位圈仍是旧的 1.5R=10.5 格，则 d=11.2 > 10.5 → kActed=false
                        //     → 落下方 issueMarch → 把刚撤出来的弓兵又朝敌基地推回去(撤了个寂寞)。
                        //   取 1.75R=12.25 格 > 1.6R=11.2 格，留 1 格余量吸收引擎寻路落点误差。
                        //   ★ 铁律：站位圈下限必须 > 后撤倍率，否则"后撤→推进"自相矛盾，拉扯永远闭环不了。
                        // ★ 2026-09-06 五修：风箏站位圈 1.75R(12.25格) → 1.05R(7.35格)。
                        //   旧 1.75R 是为配合 1.6R 后撤落点(11.2 格)才放大的；现在后撤落点只有
                        //   0.85R=5.95 格，圈若仍留 12.25 格，则敌在 8~12 格时我方(射程7)既不推进
                        //   也不开火 → 站着被敌方投石车(射程10)白打。改 1.05R ≈ 射程：
                        //   d>R 才推进，d≤R 站桩输出。（仍满足"站位圈 > 后撤落点"铁律：7.35 > 5.95）
                        if (d <= R * 1.05) {
                            // ★ 2026-09-06 修攻击令打断移动（用户实测："24:50:84 HumanMove→24:50:88
                            //   HumanAction 仅 4 帧(0.16s)间隔,根本来不及移动"）。
                            //   根因：旧版每帧都下 HumanAction(a.SN, kEnemy),即使 a.WorkObjectSN 已经是
                            //   kEnemy。攻击令会打断上方 issueMarch 的拉扯 HumanMove→弓兵永远走不到下一站位。
                            //   修复：仅当 WorkObjectSN != kEnemy 时才下 HumanAction(首次锁定或换敌)；
                            //   已在打它就让引擎内部攻击循环自走,不再每帧重发打断移动。
                            // ★★ 后撤保护期（2026-09-06，本次真正堵住"4 帧被打断"的关键）：
                            //   上轮加的 `a.WorkObjectSN != kEnemy` 去重有个致命前提——WorkObjectSN
                            //   必须保持。但引擎 Core_List::getObjectSN() 在 goalObject==nullptr 时
                            //   返回 -1，即【一下 HumanMove，WorkObjectSN 就被清成 -1】⇒ 该去重在
                            //   "刚下过移动令"之后必然失效 → 攻击令把后撤 HumanMove 打断在半路。
                            //   故改用 AI 自己记的 lastRetreatFrame：撤令下达后 30 帧内不许开火，
                            //   让这一撤真正走完；撤到 0.85R 后仍在射程内，保护期一过即可继续射击。
                            const int RETREAT_PROTECT_FRAMES = 30;   // 与 KITING_COOLDOWN 同值
                            bool retreatProt = lastRetreatFrame.count(a.SN) &&
                                               (frame - lastRetreatFrame[a.SN] < RETREAT_PROTECT_FRAMES);
                            if (!retreatProt && a.WorkObjectSN != kEnemy) {
                                HumanAction(a.SN, kEnemy);   // 最优射程内→站桩输出(引擎不再逼近)
                            }
                            kActed = true;   // ★ 1.05R 内一律风藄站位,不落 issueMarch
                        }
                        // d > R*1.05: 超出射程→落下方 issueMarch 朝敌推进
                    }
                }
                if (!kActed) {
                    // 无敌或敌在射程外→正常推进/拆基地(由主循环拖动大部队)
                    if (directMarch && calDistance(a.DR, a.UR, targetDR, targetUR) <= 12 * BL) {
                        int ebSN = siege ? siege->SN : findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
                        // ★ 拆建筑攻击令去重（2026-09-06）：已在打这建筑就别重发，
                        //   否则每帧 HumanAction 打断上方 issueMarch 的拉扯 HumanMove，
                        //   远程兵永远走不到该到位的站位。同 4099 攻击令打断移动的根因。
                        if (ebSN >= 0 && a.WorkObjectSN != ebSN) HumanAction(a.SN, ebSN);
                        else issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);
                    } else {
                        issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);
                    }
                }
                marchCmds++;
                continue;
            }

            // 近战单位：路径上的敌人
            // ★ 全体反攻门槛(readyToAttack)已在循环前面统一把关：走到这里即"已达标(≥20人或24分钟)"，
            //   近战也一起接战，不再按旧的 MELEE_GATHER_MIN 单独压制(避免24分钟强制进攻时近战仍畏缩不前)。
            int enemySN = findNearestEnemyNoStone(a.DR, a.UR, 15 * BL);
            // ★ 近战接敌攻击令去重（2026-09-06）：已在打这个敌就别重发，
            //   否则每帧 HumanAction 打断 issueMarch 的推进 HumanMove，近战永远贴不上脸。
            //   同 4099 / 4117 攻击令打断移动的根因。
            if (enemySN >= 0 && a.WorkObjectSN != enemySN) {
                HumanAction(a.SN, enemySN);
            } else if (directMarch && calDistance(a.DR, a.UR, targetDR, targetUR) <= 12 * BL) {
                // ★ 已到已知敌方基地附近：主动拆最近的敌方建筑(武器厂优先，否则任意敌建筑)
                int ebSN = siege ? siege->SN : findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
                // ★ 拆建筑攻击令去重（同 4117）
                if (ebSN >= 0 && a.WorkObjectSN != ebSN) HumanAction(a.SN, ebSN);   // 有建筑可打→拆基地
                else issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);  // 无建筑→继续推进
            } else {
                // 向目标推进：已知敌基地→引擎全图寻路直奔；未知→逐格摸索已探索区
                issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);
            }
            marchCmds++;
        }
    }

    // ====== 3. 祭司推进/转化武器厂 ======
    // managePriest 已在 processData 中先处理祭司的保命/治疗/感化；
    // 这里只在祭司真正空闲且无伤员需要治疗时接管推进，避免覆盖刚下发的治疗/撤退指令。
    if (priest) {
        if (priest->NowState != HUMAN_STATE_IDLE) return;   // 行走/引导/治疗中都不打断

        // 有伤兵时把祭司留给 managePriest 治疗，推进下帧再继续
        bool anyInjuredAlly = false;
        for (auto &a : info.armies) {
            if (a.MaxBlood <= 0) continue;
            if (a.Blood > 0 && a.Blood < a.MaxBlood) { anyInjuredAlly = true; break; }
        }
        if (anyInjuredAlly) return;

        double pDist = calDistance(priest->DR, priest->UR, targetDR, targetUR);
        int priestEnemy = findNearestEnemySN(priest->DR, priest->UR, 12 * BL);
        if (priestEnemy >= 0) return;   // 保命由 managePriest 处理，这里不覆盖

        if (siege && pDist < 12 * BL && priest->ConvertCooldown <= 0 && priestMoveCooldown <= 0) {
            // 在感化范围内→感化武器厂！
            HumanAction(priestSN, siege->SN);
            priestMoveCooldown = 120;
            DebugText(">> Priest converting Siege Workshop!");
        } else if (priestMoveCooldown <= 0) {
            // 安全，向目标后方推进（保持距离）
            double targetX = max(0.0, min((double)MAP_L * BL, targetDR - 5 * BL));
            double targetY = max(0.0, min((double)MAP_U * BL, targetUR - 5 * BL));
            if (directMarch) {
                // ★ 已知敌基地→引擎全图寻路直奔(不再逐格摸索)；保持 5 格缓冲避免贴脸
                HumanMove(priestSN, targetX, targetY);
                priestMoveCooldown = 30;
            } else {
                // 未探明→逐格步进(原行为)
                double wx = 0, wy = 0;
                if (nextVisibleStep(priest->DR, priest->UR, targetX, targetY, 5.0, wx, wy))
                    HumanMove(priestSN, wx, wy);
                priestMoveCooldown = 30;
            }
        }
    }

    // ====== 4. 后方支援：继续造兵补充伤亡 ======
    // (已在manageMilitary中持续进行)
}

// ============================================================
// 失败检查
// ============================================================
void UsrAI::checkDefeat() {
    // 检查祭司
    bool priestAlive = false;
    for (auto &a : info.armies) {
        if (a.Sort == AT_PRIEST) { priestAlive = true; break; }
    }
    if (!priestAlive && priestSN != -1) {
        state = DEFEAT;
        DebugText("!!! DEFEAT: Priest killed !!!");
        return;
    }

    // 检查市镇中心
    bool tcAlive = false;
    for (auto &b : info.buildings) {
        if (b.Type == BUILDING_CENTER) { tcAlive = true; break; }
    }
    if (!tcAlive) {
        state = DEFEAT;
        DebugText("!!! DEFEAT: Town Center destroyed !!!");
        return;
    }
}

// ============================================================
// 调试输出（每150帧输出一次）
// ============================================================
void UsrAI::doDebugOutput() {
    debugTimer++;
    if (debugTimer % 150 != 0) return;

    QString s;
    switch (state) {
    case INIT: s="INIT"; break;
    case EARLY_ECONOMY: s="ECO"; break;
    case UPGRADING: s="UPG"; break;
    case DEFENSE_PREP: s="PREP"; break;
    case DEFENSE_WAVE1: s="W1"; break;
    case DEFENSE_WAVE2: s="W2"; break;
    case DEFENSE_WAVE3: s="W3"; break;
    case COUNTERATTACK: s="ATK"; break;
    case VICTORY: s="WIN"; break;
    case DEFEAT: s="LOSE"; break;
    }

    int fCount = 0, idleF = 0, idleCarry = 0, walkingF = 0;
    int workingF = 0, attackingF = 0;
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        fCount++;
        if (f.NowState == HUMAN_STATE_IDLE) {
            idleF++;
            if (f.Resource > 0) idleCarry++;
        } else if (f.NowState == HUMAN_STATE_WALKING) {
            walkingF++;
        } else if (f.NowState == HUMAN_STATE_WORKING) {
            workingF++;
        } else if (f.NowState == HUMAN_STATE_ATTACKING) {
            attackingF++;
        }
    }

    int mil = countAllMilitary();
    int eCount = info.enemy_armies.size() + info.enemy_farmers.size();

    DebugText(QString("[%1] %2 | Fd:%3 Wd:%4 St:%5 Gd:%6 | Frm:%7 Idle:%8(Carry:%9) Walk:%10 Work:%11 Atk:%12 | Mil:%13 E:%14")
        .arg(frame).arg(s)
        .arg((int)info.Meat).arg((int)info.Wood).arg((int)info.Stone).arg((int)info.Gold)
        .arg(fCount).arg(idleF).arg(idleCarry).arg(walkingF).arg(workingF).arg(attackingF)
        .arg(mil).arg(eCount));
}

// ============================================================
// 辅助函数实现
// ============================================================

tagFarmer* UsrAI::findIdleFarmer() {
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN) || f.SN == scoutFarmerSN) continue;
        if (f.NowState == HUMAN_STATE_IDLE && f.Resource <= 0) return &f;
    }
    return nullptr;
}

tagFarmer* UsrAI::findAnyFarmer() {
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN) || waveBlockers.count(f.SN)) continue;
        if (f.Resource > 0) continue;
        if (f.NowState == HUMAN_STATE_WORKING && f.ResourceSort == HUMAN_STONE) return &f;
    }
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN) || waveBlockers.count(f.SN)) continue;
        if (f.Resource > 0) continue;
        if (f.NowState == HUMAN_STATE_WORKING && f.ResourceSort == HUMAN_GOLD) return &f;
    }
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN) || waveBlockers.count(f.SN)) continue;
        if (f.Resource > 0) continue;
        if (f.NowState == HUMAN_STATE_WORKING && f.ResourceSort == HUMAN_WOOD) return &f;
    }
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN) || waveBlockers.count(f.SN)) continue;
        if (f.Resource > 0) continue;
        if (f.NowState != HUMAN_STATE_IDLE && f.NowState != HUMAN_STATE_ATTACKING) return &f;
    }
    return nullptr;
}
tagBuilding* UsrAI::findBuilding(int type) {
    for (auto &b : info.buildings)
        if (b.Type == type && b.Percent == 100) return &b;
    return nullptr;
}

tagBuilding* UsrAI::findBuildingIncludingUnderConstruction(int type) {
    for (auto &b : info.buildings)
        if (b.Type == type) return &b;
    return nullptr;
}

tagBuilding* UsrAI::findEnemyBuilding(int type) {
    for (auto &b : info.enemy_buildings)
        if (b.Type == type) return &b;
    return nullptr;
}

// 范围内最近敌方建筑SN：反攻直奔已知基地后，部队抵达基地附近需主动拆建筑(不仅打兵)。
//   建筑坐标用区块中心 (BlockDR+1)*BL 计算距离；range 内无敌方建筑返回 -1。
int UsrAI::findNearestEnemyBuilding(double dr, double ur, double range) {
    int bestSN = -1;
    double bestDist = range * range;
    for (const auto &b : info.enemy_buildings) {
        double bDR = (b.BlockDR + 1.0) * (double)BLOCKSIDELENGTH;
        double bUR = (b.BlockUR + 1.0) * (double)BLOCKSIDELENGTH;
        double d = (bDR - dr) * (bDR - dr) + (bUR - ur) * (bUR - ur);
        if (d < bestDist) { bestDist = d; bestSN = b.SN; }
    }
    return bestSN;
}

tagResource* UsrAI::findNearestResource(int type, double dr, double ur) {
    tagResource* best = nullptr;
    double bestDist = 1e12;
    for (auto &r : info.resources) {
        if (r.Type == type && r.Cnt > 0) {
            double d = (r.DR - dr) * (r.DR - dr) + (r.UR - ur) * (r.UR - ur);
            if (d < bestDist) { bestDist = d; best = &r; }
        }
    }
    return best;
}

tagResource* UsrAI::findNearestResourceAny(const std::vector<int>& types, double dr, double ur) {
    tagResource* best = nullptr;
    double bestDist = 1e12;
    for (auto &r : info.resources) {
        for (int t : types) {
            if (r.Type == t && r.Cnt > 0) {
                double d = (r.DR - dr) * (r.DR - dr) + (r.UR - ur) * (r.UR - ur);
                if (d < bestDist) { bestDist = d; best = &r; }
            }
        }
    }
    return best;
}

tagArmy* UsrAI::findMyArmy(int sort, bool idleOnly) {
    for (auto &a : info.armies)
        if (a.Sort == sort && (!idleOnly || a.NowState == HUMAN_STATE_IDLE)) return &a;
    return nullptr;
}
// ★ 2026-09-06 砍树选树：优先"离已建成仓库/TC 近"的树，而不是"离村民近"的树。
//   【为什么】findNearestResource(RESOURCE_TREE,...) 只比较"村民→树"。村民在远处打猎/建塔/采金
//   结束变空闲时，最近的树往往是脚边那片远离基地的林子，砍完要横穿半张地图才能卸货到仓库，
//   往返成本极高（用户实测：村民跑到离基地/仓库很远的地方砍树）。
//   【策略】score = (α·村民→树 + β·树→最近锚点) × 拥挤惩罚，取最小。β(1.0) > α(0.5) → 锚点主导；
//   保留村民距离约束，避免"村民在 A 端、唯一近锚点的树在 B 端"时横穿地图。
//   【锚点】Percent==100 的 BUILDING_STOCK / BUILDING_CENTER（在建中的仓库不算，否则围着没盖好的
//   仓库砍树）。建筑只有 Block 坐标，细节坐标取块中心 (BlockDR+1)*BL。
//   【硬闸】树→锚点 > WOOD_MAX_ANCHOR_DIST 个 BLOCK 直接排除；硬闸内无可用树（全满员/被砍光/
//   被标记不可达）时退化为"离锚点最近的那棵树"——★ 绝不退化回"离村民最近的远树"，这是修复关键。
tagResource* UsrAI::findBestWoodTree(double dr, double ur) {
    const double BL = (double)BLOCKSIDELENGTH;
    const double maxAnchor = WOOD_MAX_ANCHOR_DIST * BL;

    tagResource* best = nullptr;
    double bestScore = 1e12;
    tagResource* nearestAnchorTree = nullptr;  // 兜底：全池里离锚点最近的树（不受硬闸/满员限制）
    double bestAnchorDist = 1e12;

    for (auto &r : info.resources) {
        if (r.Type != RESOURCE_TREE || r.Cnt <= 0) continue;
        if (stuckResourceUntil.count(r.SN)) continue;      // 不可达的树，跳过

        // ---- 树 → 最近已建成锚点(STOCK/CENTER) ----
        double anchorD2 = 1e12;
        for (auto &b : info.buildings) {
            if (b.Percent < 100) continue;
            if (b.Type != BUILDING_STOCK && b.Type != BUILDING_CENTER) continue;
            double bx = (b.BlockDR + 1.0) * BL;
            double by = (b.BlockUR + 1.0) * BL;
            double d2 = (r.DR - bx) * (r.DR - bx) + (r.UR - by) * (r.UR - by);
            if (d2 < anchorD2) anchorD2 = d2;
        }
        // 无建成锚点（开局瞬间 / TC 与仓库全毁）→ 不惩罚，等价于纯按村民距离选
        double anchorD = (anchorD2 >= 1e12) ? 0.0 : std::sqrt(anchorD2);
        if (anchorD < bestAnchorDist) { bestAnchorDist = anchorD; nearestAnchorTree = &r; }

        if (anchorD > maxAnchor) continue;   // ★ 硬闸：离仓库/TC 太远的树不派工

        // ---- 单树拥挤：树上已有工人 + 本帧已派，不超过上限 ----
        int workerCount = 0;
        for (auto &other : info.farmers)
            if (other.WorkObjectSN == r.SN) workerCount++;
        if (workerCount + frameWoodCount[r.SN] >= WOOD_MAX_WORKERS_PER_TREE) continue;

        double vd = std::sqrt((r.DR - dr) * (r.DR - dr) + (r.UR - ur) * (r.UR - ur));
        double score = (WOOD_SCORE_ALPHA * vd + WOOD_SCORE_BETA * anchorD) * (1.0 + workerCount * 0.5);
        if (score < bestScore) { bestScore = score; best = &r; }
    }

    if (!best) best = nearestAnchorTree;   // 硬闸内无可用树 → 退化为"离锚点最近的树"
    if (!best) return nullptr;

    frameWoodCount[best->SN]++;            // 同帧去重：防止连续多个村民挤同一棵树

    // ---- 诊断：每 600 帧打印一次选中树的锚点距离（换算回 BLOCK 便于读） ----
    static int lastWoodDiagFrame = -1;
    if (frame != lastWoodDiagFrame && frame % 600 == 0) {
        lastWoodDiagFrame = frame;
        double bd2 = 1e12;
        for (auto &b : info.buildings) {
            if (b.Percent < 100) continue;
            if (b.Type != BUILDING_STOCK && b.Type != BUILDING_CENTER) continue;
            double bx = (b.BlockDR + 1.0) * BL, by = (b.BlockUR + 1.0) * BL;
            double d2 = (best->DR - bx) * (best->DR - bx) + (best->UR - by) * (best->UR - by);
            if (d2 < bd2) bd2 = d2;
        }
        double ad = (bd2 < 1e12) ? (std::sqrt(bd2) / BL) : -1.0;
        double vd = std::sqrt((best->DR - dr) * (best->DR - dr) + (best->UR - ur) * (best->UR - ur)) / BL;
        DebugText(QString("WOOD-TREE | sn=%1 anchor=%2BL villager=%3BL cnt=%4 (maxAnchor=%5BL)")
                  .arg(best->SN).arg(ad, 0, 'f', 1).arg(vd, 0, 'f', 1)
                  .arg(best->Cnt).arg(WOOD_MAX_ANCHOR_DIST));
    }
    return best;
}

int UsrAI::findNearestEnemySN(double dr, double ur, double range) {
    int bestSN = -1;
    double bestDist = range * range;
    for (const auto &e : info.enemy_armies) {
        double d = (e.DR - dr) * (e.DR - dr) + (e.UR - ur) * (e.UR - ur);
        if (d < bestDist) { bestDist = d; bestSN = e.SN; }
    }
    for (const auto &e : info.enemy_farmers) {
        double d = (e.DR - dr) * (e.DR - dr) + (e.UR - ur) * (e.UR - ur);
        if (d < bestDist) { bestDist = d; bestSN = e.SN; }
    }
    return bestSN;
}

// 军事单位选敌：范围内"最近敌方单位(军队优先于村民)"，但永远排除投石车(AT_STONE_THROWER)——
// 投石车留给祭司感化，军事单位即使附近无其它敌也不得攻击投石车。
//   ★ 不做"近战优先"：用户要求取消优先迎击近战，恢复为选最近敌人(含远程兵/村民)。
int UsrAI::findNearestEnemyNoStone(double dr, double ur, double range) {
    int bestSN = -1;
    double bestDist = range * range;
    for (const auto &e : info.enemy_armies) {
        if (e.Sort == AT_STONE_THROWER) continue;   // 投石车留给祭司，军事单位不攻击
        double d = (e.DR - dr) * (e.DR - dr) + (e.UR - ur) * (e.UR - ur);
        if (d < bestDist) { bestDist = d; bestSN = e.SN; }
    }
    if (bestSN >= 0) return bestSN;
    // 无军队敌人→村民(原兜底行为)
    bestDist = range * range;
    for (const auto &e : info.enemy_farmers) {
        double d = (e.DR - dr) * (e.DR - dr) + (e.UR - ur) * (e.UR - ur);
        if (d < bestDist) { bestDist = d; bestSN = e.SN; }
    }
    return bestSN;
}

// 投石车专用选敌(反攻需求)：范围内最近目标 = 任意敌方单位(含敌方投石车) + 敌方箭塔建筑。
// 与 findNearestEnemyNoStone 不同——投石车主动摧毁敌方投石车与箭塔(火力压制，不留给祭司感化)。
//   敌方建筑用 Block 中心坐标 (BlockDR+1)*BL 计算距离。
int UsrAI::findCatapultTarget(double dr, double ur, double range) {
    int bestSN = -1;
    double bestDist = range * range;
    for (const auto &e : info.enemy_armies) {
        double d = (e.DR - dr) * (e.DR - dr) + (e.UR - ur) * (e.UR - ur);
        if (d < bestDist) { bestDist = d; bestSN = e.SN; }
    }
    for (const auto &e : info.enemy_farmers) {
        double d = (e.DR - dr) * (e.DR - dr) + (e.UR - ur) * (e.UR - ur);
        if (d < bestDist) { bestDist = d; bestSN = e.SN; }
    }
    for (const auto &b : info.enemy_buildings) {
        if (b.Type != BUILDING_ARROWTOWER) continue;   // 只打箭塔(其它建筑由后续推进逻辑处理)
        double bDR = (b.BlockDR + 1.0) * (double)BLOCKSIDELENGTH;
        double bUR = (b.BlockUR + 1.0) * (double)BLOCKSIDELENGTH;
        double d = (bDR - dr) * (bDR - dr) + (bUR - ur) * (bUR - ur);
        if (d < bestDist) { bestDist = d; bestSN = b.SN; }
    }
    return bestSN;
}

int UsrAI::countBuildings(int type) {
    int cnt = 0;
    for (auto &b : info.buildings) if (b.Type == type && b.Percent == 100) cnt++;
    return cnt;
}

int UsrAI::countBuildingsAll(int type) {
    int cnt = 0;
    for (auto &b : info.buildings) if (b.Type == type && !deadBuildings.count(b.SN)) cnt++;
    return cnt;
}

// ★ "是否已存在（含地基/待回写指令）"计数：用于唯一建筑(市场/谷仓/兵营/靶场/马厩/学院)的存在性门槛。
//   旧写法 countBuildingsAll()==0 会漏算两类导致重复建造：
//   ① 指令已下发、地基尚未回写进 info.buildings 的窗口期（HumanBuild 是异步的）；
//   ② 地基卡在 0% 被拉黑进 deadBuildings 后，该建筑仍杵在地图上，却被当成"不存在"→原地再建一座。
//   对②给一段宽限(DEAD_BUILDING_GRACE 帧)让"孤儿地基抢救"先尝试补救，超时后才允许另建。
int UsrAI::countBuildingsExisting(int type) {
    int cnt = 0;
    for (auto &b : info.buildings) {
        if (b.Type != type) continue;
        if (deadBuildings.count(b.SN)) {
            auto it = deadBuildingsFrame.find(b.SN);
            if (it != deadBuildingsFrame.end() && frame - it->second > DEAD_BUILDING_GRACE)
                continue;   // 宽限已过：视为彻底废弃，允许另建新址
        }
        cnt++;
    }
    for (auto &kv : pendingBuildIns)
        if (kv.second.second == type) cnt++;
    // 最后一道保险：指令刚下发(≤90帧)但地基/待定条目都还没回写 → 也当作"已存在"，
    // 彻底杜绝"异步窗口内连下两次建造令"导致的重复建造（市场建两座的主因之一）。
    if (cnt == 0) {
        auto it = lastBuildIssueFrame.find(type);
        if (it != lastBuildIssueFrame.end() && frame - it->second <= 90) cnt = 1;
    }
    return cnt;
}

int UsrAI::countUnits(int sort) {
    int cnt = 0;
    for (auto &a : info.armies) if (a.Sort == sort) cnt++;
    return cnt;
}

int UsrAI::countAllMilitary() {
    int cnt = 0;
    for (auto &a : info.armies) if (a.Sort != AT_PRIEST) cnt++;
    return cnt;
}

int UsrAI::countFarmersByState(int state) {
    int cnt = 0;
    for (auto &f : info.farmers) if (f.NowState == state) cnt++;
    return cnt;
}

bool UsrAI::isPositionFree(int blockDR, int blockUR, int size) {
    if (blockDR < 0 || blockUR < 0 || blockDR + size > MAP_L || blockUR + size > MAP_U)
        return false;
    if (info.theMap == nullptr) return false;

    // 地形检查：草地 + 高度一致
    int firstHeight = (*info.theMap)[blockDR][blockUR].height;
    for (int i = blockDR; i < blockDR + size; ++i) {
        for (int j = blockUR; j < blockUR + size; ++j) {
            auto &t = (*info.theMap)[i][j];
            if (t.type != MAPPATTERN_GRASS) return false;
            if (t.height < 0) return false;
            if (t.height != firstHeight) return false;
        }
    }

    // ★ 建筑间距检查：候选 footprint 外扩 BUILD_GAP 格内不得与任何建筑相交(含边界)，
    //   否则建筑会紧贴成墙、堵死村民/士兵的通行路线。外扩 1 格 = 建筑之间至少留 1 格通道。
    for (auto &b : info.buildings) {
        int bSize = (b.Type == BUILDING_HOME || b.Type == BUILDING_ARROWTOWER) ? 2 : 3;
        for (int i = blockDR - BUILD_GAP; i < blockDR + size + BUILD_GAP; ++i)
            for (int j = blockUR - BUILD_GAP; j < blockUR + size + BUILD_GAP; ++j)
                if (i >= b.BlockDR && i < b.BlockDR + bSize &&
                    j >= b.BlockUR && j < b.BlockUR + bSize) return false;
    }

    // 敌方建筑间距检查（已探索区域内的敌方建筑同样阻挡建造）
    for (auto &b : info.enemy_buildings) {
        int bSize = (b.Type == BUILDING_HOME || b.Type == BUILDING_ARROWTOWER) ? 2 : 3;
        for (int i = blockDR - BUILD_GAP; i < blockDR + size + BUILD_GAP; ++i)
            for (int j = blockUR - BUILD_GAP; j < blockUR + size + BUILD_GAP; ++j)
                if (i >= b.BlockDR && i < b.BlockDR + bSize &&
                    j >= b.BlockUR && j < b.BlockUR + bSize) return false;
    }

    // 资源重叠检查
    for (auto &r : info.resources) {
        if (r.Cnt <= 0) continue;
        for (int i = blockDR; i < blockDR + size; ++i)
            for (int j = blockUR; j < blockUR + size; ++j)
                if (i == r.BlockDR && j == r.BlockUR) return false;
    }

    // ★ 避开狮子周围区域：狮子会攻击靠近的建筑/村民，建在狮子附近会导致建好即被骚扰、
    //   村民往返送死。候选点中心离任一 RESOURCE_LION(Cnt>0) 过近即判为不可建。
    //   用距离平方比较，避免引入 <cmath> 依赖；半径见 LION_AVOID_RADIUS。
    {
        int cr = blockDR + size / 2, cu = blockUR + size / 2;
        long long rr = (long long)LION_AVOID_RADIUS * LION_AVOID_RADIUS;
        for (auto &r : info.resources) {
            if (r.Type != RESOURCE_LION || r.Cnt <= 0) continue;
            long long dd = (long long)(cr - r.BlockDR) * (cr - r.BlockDR) +
                           (long long)(cu - r.BlockUR) * (cu - r.BlockUR);
            if (dd < rr) return false;
        }
    }

    // ★ 单位重叠检查（村民/士兵站在建造位置上也导致失败）★
    for (auto &f : info.farmers) {
        int fbDR = (int)(f.DR / (double)BLOCKSIDELENGTH);
        int fbUR = (int)(f.UR / (double)BLOCKSIDELENGTH);
        if (fbDR >= blockDR && fbDR < blockDR + size &&
            fbUR >= blockUR && fbUR < blockUR + size) return false;
    }
    for (auto &a : info.armies) {
        int abDR = (int)(a.DR / (double)BLOCKSIDELENGTH);
        int abUR = (int)(a.UR / (double)BLOCKSIDELENGTH);
        if (abDR >= blockDR && abDR < blockDR + size &&
            abUR >= blockUR && abUR < blockUR + size) return false;
    }

    // ★ 可达性预检：地基旁须有路可走，否则村民永远走不到=卡死（选址被建筑围死）
    if (!isSiteReachable(blockDR, blockUR, size)) return false;

    return true;
}

// 地基可达性预检：确保村民能走到地基旁（避免选址被建筑围死、村民永远走不到=卡死）。
//   做法：在 footprint 外扩 1 格的"接近环"上找空闲瓦片作多源起点，
//         从这些起点向"可行走"瓦片做有界 BFS；若能走出足够远(连通分量够大=通到开阔地)即视为可达。
//         被建筑完全围死时连通分量很小 → 拒绝该点，迫使 tryBuild 另择新址（而非建在死胡同里卡死）。
bool UsrAI::isSiteReachable(int blockDR, int blockUR, int size) {
    if (info.theMap == nullptr) return true;   // 无地图数据则放行(不误杀)
    if (blockDR < 0 || blockUR < 0 || blockDR + size > MAP_L || blockUR + size > MAP_U) return false;

    int firstHeight = (*info.theMap)[blockDR][blockUR].height;

    // 某瓦片是否不可行走（被建筑/地形/悬崖阻挡）
    auto tileBlocked = [&](int i, int j) -> bool {
        if (i < 0 || j < 0 || i >= MAP_L || j >= MAP_U) return true;
        auto &t = (*info.theMap)[i][j];
        if (t.type != MAPPATTERN_GRASS) return true;
        if (t.height < 0) return true;
        if (t.height != firstHeight) return true;   // 高度不一致=悬崖，不可越
        // 地基本身也视为障碍：村民必须从外侧接近，不能"穿地基"逃出包围
        if (i >= blockDR && i < blockDR + size && j >= blockUR && j < blockUR + size) return true;
        // 我方建筑（含未完工地基）
        for (auto &b : info.buildings) {
            int bs = (b.Type == BUILDING_HOME || b.Type == BUILDING_ARROWTOWER) ? 2 : 3;
            if (i >= b.BlockDR && i < b.BlockDR + bs &&
                j >= b.BlockUR && j < b.BlockUR + bs) return true;
        }
        // 敌方建筑（已探索区域内同样阻挡）
        for (auto &b : info.enemy_buildings) {
            int bs = (b.Type == BUILDING_HOME || b.Type == BUILDING_ARROWTOWER) ? 2 : 3;
            if (i >= b.BlockDR && i < b.BlockDR + bs &&
                j >= b.BlockUR && j < b.BlockUR + bs) return true;
        }
        return false;
    };

    // 起点：footprint 外扩 1 格接近环上、未被占用的瓦片（村民站这里即可施工）
    const int R = 1;
    std::vector<std::pair<int,int>> starts;
    for (int i = blockDR - R; i < blockDR + size + R; ++i)
        for (int j = blockUR - R; j < blockUR + size + R; ++j) {
            bool inFoot = (i >= blockDR && i < blockDR + size && j >= blockUR && j < blockUR + size);
            if (inFoot) continue;           // 地基占用的瓦片不算接近点
            if (tileBlocked(i, j)) continue;
            starts.push_back({i, j});
        }
    if (starts.empty()) return false;      // 接近环全被建筑占 → 不可达

    // 多源 BFS，探索连通的可行走区域；连通分量够大即认为"通到开阔地"
    const int ESCAPE_N = 300;
    std::vector<std::pair<int,int>> q = starts;
    std::unordered_set<long long> vis;
    for (auto &s : starts) vis.insert((long long)s.first * 100003 + s.second);
    int head = 0, visited = 0;
    const int dirs[4][2] = {{1,0},{-1,0},{0,1},{0,-1}};
    while (head < (int)q.size()) {
        auto cur = q[head++]; ++visited;
        if (visited >= ESCAPE_N) return true;   // 已逃出建筑包围 → 可达
        for (int d = 0; d < 4; ++d) {
            int ni = cur.first + dirs[d][0], nj = cur.second + dirs[d][1];
            if (tileBlocked(ni, nj)) continue;
            long long k = (long long)ni * 100003 + nj;
            if (vis.count(k)) continue;
            vis.insert(k); q.push_back({ni, nj});
        }
    }
    // 连通分量很小：被建筑围死的死胡同 → 不可达
    return false;
}

// 建筑选址：偏向 TC→地图中心方向、离 TC 更远，避免挤在 TC 边角堵路。
//   minR/maxR = 距 TC 的最小/最大环半径(单位:block)；在 [minR,maxR] 范围内收集所有空闲点，
//   按 score = 朝向中心方向的对齐度*100 + 距TC超出minR的距离 选最优——方向优先、其次更远。
bool UsrAI::findBuildSiteTowardCenter(int &x, int &y, int size, int minR, int maxR) {
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return false;
    int cx = center->BlockDR, cy = center->BlockUR;
    // 地图中心方向(单位向量)
    double mcx = MAP_L * 0.5, mcy = MAP_U * 0.5;
    double gx = mcx - cx, gy = mcy - cy;
    double glen = std::sqrt(gx * gx + gy * gy);
    if (glen < 1e-6) { gx = 1.0; gy = 0.0; glen = 1.0; }
    gx /= glen; gy /= glen;

    int bestX = -1, bestY = -1;
    double bestScore = -1e18;
    for (int r = minR; r <= maxR; ++r) {
        for (int dx = -r; dx <= r; ++dx) {
            for (int dy = -r; dy <= r; ++dy) {
                if (std::abs(dx) != r && std::abs(dy) != r) continue;   // 只扫该半径外环
                int nx = cx + dx, ny = cy + dy;
                if (nx < 0 || ny < 0 || nx >= MAP_L || ny >= MAP_U) continue;
                int key = nx * 1000 + ny;
                if (triedBuildPositions.count(key)) continue;
                if (!isPositionFree(nx, ny, size)) continue;
                // 候选点方向对齐度(与中心方向点积, ∈[-1,1])；正对中心方向得分最高
                double len = std::sqrt((double)(dx * dx + dy * dy));
                double align = (len > 1e-6) ? (dx * gx + dy * gy) / len : 0.0;
                double score = align * 100.0 + (double)(r - minR);     // 方向优先，其次更远
                if (score > bestScore) { bestScore = score; bestX = nx; bestY = ny; }
            }
        }
    }
    if (bestX < 0) return false;
    x = bestX; y = bestY;
    return true;
}

bool UsrAI::findBuildSite(int &x, int &y, int size) {
    if (townCenterSN == -1) return false;
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return false;
    int cx = center->BlockDR, cy = center->BlockUR;

    // 从TC向外螺旋搜索（扩大范围到50，适应密集地图；r=8 避开农场6格保护区）
    for (int r = 8; r < 50; ++r) {
        for (int dx = -r; dx <= r; ++dx) {
            for (int dy = -r; dy <= r; ++dy) {
                if (std::abs(dx) != r && std::abs(dy) != r) continue;
                int nx = cx + dx, ny = cy + dy;
                int key = nx * 1000 + ny;
                if (triedBuildPositions.count(key)) continue;
                if (isPositionFree(nx, ny, size)) {
                    x = nx; y = ny;
                    return true;
                }
            }
        }
    }

    // 清空黑名单重试
    if (!triedBuildPositions.empty()) {
        triedBuildPositions.clear();
        DebugText("Cleared build blacklist, retrying...");
    }
    return false;
}

bool UsrAI::findDefenseBuildSite(int &x, int &y, int size) {
    // 箭塔选址（2026-09-04 用户反馈"第2座一直没人建"修复）：
    //   史上：
    //     · 上一版只扫 r=4~8 外环，但 BUILD_GAP=1 → 箭塔(2×2)外扩1格=BUILD_GAP+size=3格内不得有建筑；
    //       r=4 时塔 footprint=BlockDR+4~+5，gap=BlockDR+3~+6，与 TC footprint=BlockDR~+3 重叠 → isPositionFree 永 false（实际可用最小 r=5）。
    //     · 即使 r=5~8，TC 周围早期经济建筑(房屋/谷仓/市场/仓库/马厩/农场环)层层占据，整圈外环 0 个可用 → findDefenseBuildSite return false。
    //     · tryBuild 回退到默认 findBuildSite 时仍受 triedBuildPositions 旧 ban 影响 → 第 2 座彻底卡死。
    //   修：
    //     ① 范围放宽到 r=4~12（4~8 优先，9~12 兜底贴近 TC，仍受箭塔射程 8 格覆盖 TC 周边，不再坚持外环——2×2 塔用正方形外环难以表达，
    //        改用 max(|dx|,|dy|)==r 的"钻石形"外圈，覆盖所有候选）；② findDefenseBuildSite 失败前清空 triedBuildPositions 让 tryBuild 默认兜底不受旧 ban 卡；
    //       ③ 加 debug 日志便于后续定位。
    //   选址策略：第1座朝地图中心，第2座取反方向；都贴身 TC（4~8 优先）、次选 9~12 远离。
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return findBuildSite(x, y, size);
    int cx = center->BlockDR, cy = center->BlockUR;

    // 收集已建成/在建的箭塔位置（判断当前是第几座）
    std::vector<std::pair<int,int>> existingTowers;
    for (auto &b : info.buildings)
        if (b.Type == BUILDING_ARROWTOWER)
            existingTowers.push_back({b.BlockDR, b.BlockUR});

    // 基准方向 = 朝地图中心。第2座取反，与第1座分守 TC 两侧
    double gx = MAP_L * 0.5 - cx, gy = MAP_U * 0.5 - cy;
    double glen = std::sqrt(gx * gx + gy * gy);
    if (glen < 1e-6) { gx = 1.0; gy = 0.0; glen = 1.0; }
    gx /= glen; gy /= glen;
    if (!existingTowers.empty()) { gx = -gx; gy = -gy; }   // 第2座：背离地图中心

    // 钻石形外圈扫描 r=4~12（贴近 TC 4~8 优先；超 8 格候选位置略减分，但仍可建——箭塔射程 8 格覆盖 TC 周边）
    int bestX = -1, bestY = -1;
    double bestScore = -1e18;
    int triedCount = 0, blockedCount = 0;
    for (int r = 4; r <= 12; ++r) {
        for (int dx = -r; dx <= r; ++dx) {
            for (int dy = -r; dy <= r; ++dy) {
                if (std::max(std::abs(dx), std::abs(dy)) != r) continue;   // 钻石形外圈(覆盖 |dx|≤r 且 |dy|≤r 的外边界)
                int nx = cx + dx, ny = cy + dy;
                if (nx < 0 || ny < 0 || nx >= MAP_L - size || ny >= MAP_U - size) continue;
                int key = nx * 1000 + ny;
                ++triedCount;
                if (triedBuildPositions.count(key)) { ++blockedCount; continue; }
                if (!isPositionFree(nx, ny, size)) { ++blockedCount; continue; }

                double len = std::sqrt((double)(dx * dx + dy * dy));
                double align = (len > 1e-6) ? (dx * gx + dy * gy) / len : 0.0;
                // 近圈(r=4~8)略加优先分,远圈(r=9~12)减分但仍可作为兜底
                double score = align * 100.0 - (double)r * 0.5;
                if (score > bestScore) { bestScore = score; bestX = nx; bestY = ny; }
            }
        }
    }
    if (bestX < 0) {
        // ★ 失败前清空 triedBuildPositions，让外层 tryBuild 的默认 findBuildSite 兜底不受旧 ban 卡住
        int oldBlacklistSize = (int)triedBuildPositions.size();
        if (oldBlacklistSize > 0) triedBuildPositions.clear();
        if (frame % 50 == 0) {   // 节流避免刷屏
            DebugText(QString("TowerSite FAIL (no free site in r=4~12) tried=%1 blocked=%2 blacklist_cleared=%3 existingTowers=%4")
                .arg(triedCount).arg(blockedCount).arg(oldBlacklistSize).arg((int)existingTowers.size()));
        }
        return false;
    }
    x = bestX; y = bestY;
    return true;
}
// 谷仓选址：靠近浆果丛最密集处，减少村民往返时间
bool UsrAI::findGranarySite(int &x, int &y) {
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return false;
    double BL = (double)BLOCKSIDELENGTH;
    double tcDR = (center->BlockDR + 1) * BL;
    double tcUR = (center->BlockUR + 1) * BL;

    // ★ 收集已有仓库位置（斥力：避免重复在同一集群旁建仓库）
    std::vector<std::pair<double,double>> existingGranaries;
    for (auto &b : info.buildings) {
        if (b.Type == BUILDING_GRANARY && b.Percent == 100) {
            existingGranaries.push_back({(b.BlockDR + 1.0) * BL, (b.BlockUR + 1.0) * BL});
        }
    }
    bool hasGranary = !existingGranaries.empty();

    // 统计聚类密度
    // ★ 第一座仓库：只考虑浆果（保证主食物来源效率，瞪羚距离远不打紧）
    // ★ 第二座仓库：也考虑瞪羚（2x加权，已有仓库排斥会让它自然选在瞪羚旁）
    int bestScore = -1;
    int bestBX = 0, bestBY = 0;
    for (auto &r : info.resources) {
        if (r.Cnt <= 0) continue;
        bool isBush = (r.Type == RESOURCE_BUSH);
        bool isGazelle = (r.Type == RESOURCE_GAZELLE);
        if (!isBush && !isGazelle) continue;
        // 第一座仓库不选瞪羚——必须保证浆果采集效率！
        if (isGazelle && !hasGranary) continue;
        // ★ 2026-09-04 瞪羚仓库选址放宽：30→GAZELLE_HUNT_RANGE(50) 格（与猎人选取同步），
        //   浆果丛保留 30 格（快速周转需求不变）。
        double resRange = isGazelle ? GAZELLE_HUNT_RANGE * BL : 30 * BL;
        if (calDistance(tcDR, tcUR, r.DR, r.UR) > resRange) continue;

        int cluster = 0;
        for (auto &r2 : info.resources) {
            if (r2.Cnt <= 0) continue;
            if ((isBush && r2.Type == RESOURCE_BUSH) ||
                (isGazelle && r2.Type == RESOURCE_GAZELLE))
                if (calDistance(r.DR, r.UR, r2.DR, r2.UR) < 5 * BL) cluster++;
        }
        if (cluster <= 0) continue;

        // 第二座及以后：瞪羚2x加权（减少猎人运输时间）
        if (hasGranary && isGazelle) cluster *= 2;

        // 已有仓库排斥：12格内有仓库则大幅降分
        for (auto &gd : existingGranaries) {
            if (calDistance(r.DR, r.UR, gd.first, gd.second) < 12 * BL) {
                cluster /= 4;
                break;
            }
        }

        if (cluster > bestScore) {
            bestScore = cluster;
            bestBX = r.BlockDR;
            bestBY = r.BlockUR;
        }
    }
    if (bestScore <= 0) return false;

    // 在最佳浆果丛四侧尝试放置3x3谷仓
    int offsets[4][2] = {{1,0}, {-1,0}, {0,1}, {0,-1}};
    for (int d = 0; d < 4; d++) {
        int nx = bestBX + offsets[d][0] * 3;
        int ny = bestBY + offsets[d][1] * 3;
        if (triedBuildPositions.count(nx * 1000 + ny)) continue;
        if (isPositionFree(nx, ny, 3)) {
            x = nx; y = ny;
            return true;
        }
    }
    // 四侧都被占→扩大搜索范围
    for (int r = 4; r < 10; r++) {
        for (int dx = -r; dx <= r; dx++) {
            for (int dy = -r; dy <= r; dy++) {
                if (std::abs(dx) != r && std::abs(dy) != r) continue;
                int nx = bestBX + dx, ny = bestBY + dy;
                if (nx < 0 || ny < 0) continue;
                if (triedBuildPositions.count(nx * 1000 + ny)) continue;
                if (isPositionFree(nx, ny, 3)) {
                    x = nx; y = ny;
                    return true;
                }
            }
        }
    }
    return false;
}

// 房屋选址：偏向 TC→地图中心方向、离 TC 更远(12~45格)，不堵 TC 边角出口
bool UsrAI::findHouseSite(int &x, int &y) {
    return findBuildSiteTowardCenter(x, y, 2, 12, 45);
}

// 市场选址：偏向 TC→地图中心方向、离 TC 更远(12~40格)
bool UsrAI::findMarketSite(int &x, int &y) {
    return findBuildSiteTowardCenter(x, y, 3, 12, 40);
}

// 农场不相邻检查：候选农场(3x3)外扩1格范围内不得有其他农场(含在建地基)，保证农场之间至少隔1格。
//   农场 footprint = [blockDR, blockDR+2] x [blockUR, blockUR+2]，外扩1格 = [blockDR-1, blockDR+3] x [blockUR-1, blockUR+3]。
//   与任一已有农场的 footprint 有交集(含边界)即判"相邻" → 拒绝。
bool UsrAI::isFarmAdjacent(int blockDR, int blockUR) {
    for (auto &b : info.buildings) {
        if (b.Type != BUILDING_FARM) continue;
        bool separatedX = (blockDR - 1 > b.BlockDR + 2) || (blockDR + 3 < b.BlockDR);
        bool separatedY = (blockUR - 1 > b.BlockUR + 2) || (blockUR + 3 < b.BlockUR);
        if (!separatedX && !separatedY) return true;   // X/Y 轴都有交集 → 相邻
    }
    return false;
}

// ============================================================
// 农场环形选址：TC周围隔1格，从紧贴TC的环向外扩展
// ============================================================
bool UsrAI::findFarmRingSite(int &x, int &y) {
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return findBuildSite(x, y, 3);
    int cx = center->BlockDR, cy = center->BlockUR;
    // TC 3x3 占据 [cx, cx+2] x [cy, cy+2]
    // 隔1格：农场3x3从 cx+4 / cx-4 / cy+4 / cy-4 开始（gap = 1 block）

    // 从内圈向外搜索（r=4 = 隔1格后最内圈）
    for (int r = 4; r < 30; ++r) {
        // 上下两行
        for (int dx = -r; dx <= r + 2; ++dx) {
            int nx = cx + dx;
            // 上行：farm bottom = cy+r, farm occupies [cy+r, cy+r+2]
            int key = nx * 1000 + (cy + r);
            if (!triedBuildPositions.count(key) && isPositionFree(nx, cy + r, 3) && !isFarmAdjacent(nx, cy + r)) {
                x = nx; y = cy + r; return true;
            }
            // 下行：farm bottom = cy-r, farm occupies [cy-r, cy-r+2]（隔1格）
            key = nx * 1000 + (cy - r);
            if (!triedBuildPositions.count(key) && isPositionFree(nx, cy - r, 3) && !isFarmAdjacent(nx, cy - r)) {
                x = nx; y = cy - r; return true;
            }
        }
        // 左右两列（不含四角，避免重复）
        for (int dy = -r + 1; dy <= r + 1; ++dy) {
            int ny = cy + dy;
            // 右列：farm left = cx+r
            int key = (cx + r) * 1000 + ny;
            if (!triedBuildPositions.count(key) && isPositionFree(cx + r, ny, 3) && !isFarmAdjacent(cx + r, ny)) {
                x = cx + r; y = ny; return true;
            }
            // 左列：farm left = cx-r, farm occupies [cx-r, cx-r+2]（隔1格）
            key = (cx - r) * 1000 + ny;
            if (!triedBuildPositions.count(key) && isPositionFree(cx - r, ny, 3) && !isFarmAdjacent(cx - r, ny)) {
                x = cx - r; y = ny; return true;
            }
        }
    }
    // 环形找不到→回退到默认选址
    return findBuildSite(x, y, 3);
}

bool UsrAI::tryBuild(int buildingType, int size, bool ignoreCooldown, int prefX, int prefY) {
    if (buildCooldown > 0 && !ignoreCooldown) return false;
    // 农场硬上限：无论哪条建造路径，超过 MAX_FARMS 一律不再下发
    if (buildingType == BUILDING_FARM) {
        int farmCount = 0;
        for (auto &b : info.buildings)
            if (b.Type == BUILDING_FARM) farmCount++;
        for (auto &kv : pendingBuildIns)
            if (kv.second.second == BUILDING_FARM) farmCount++;
        if (farmCount >= MAX_FARMS) return false;
    }

    auto f = findIdleFarmer();
    if (!f) f = findAnyFarmer();
    if (!f) return false;

    int x, y;
    bool placed = false;
    // 指定目标（块坐标）：在目标点及其周围优先放置（用于瞪羚群中心仓库等场景）
    if (prefX >= 0 && prefY >= 0) {
        int offs[][2] = {{0,0},{3,0},{-3,0},{0,3},{0,-3},{6,0},{-6,0},{0,6},{0,-6},
                         {-3,-3},{3,3},{-3,3},{3,-3}};
        for (auto &o : offs) {
            int nx = prefX + o[0], ny = prefY + o[1];
            if (nx < 0 || ny < 0) continue;
            if (isPositionFree(nx, ny, size)) { x = nx; y = ny; placed = true; break; }
        }
    }
    // 谷仓：优先建在浆果密集处（未指定目标时）
    if (!placed && buildingType == BUILDING_GRANARY)
        placed = findGranarySite(x, y);
    // 市场：建在TC 8格外（避开农场6格保护区）
    if (!placed && buildingType == BUILDING_MARKET)
        placed = findMarketSite(x, y);
    // 房屋：TC 8格外（避开农场6格保护区）
    if (!placed && buildingType == BUILDING_HOME)
        placed = findHouseSite(x, y);
    if (!placed && buildingType == BUILDING_FARM)
        placed = findFarmRingSite(x, y);
    if (!placed && buildingType == BUILDING_ARROWTOWER)
        placed = findDefenseBuildSite(x, y, size);
    // 兵营/靶场/马厩：偏向 TC→地图中心方向、离 TC 更远(12~45格)，成片铺开不堵 TC 周边
    if (!placed && (buildingType == BUILDING_ARMYCAMP || buildingType == BUILDING_RANGE ||
                    buildingType == BUILDING_STABLE))
        placed = findBuildSiteTowardCenter(x, y, size, 12, 45);
    if (!placed) placed = findBuildSite(x, y, size);
    if (!placed) return false;

    buildingFarmerType[f->SN] = buildingType;
    int buildInsId = HumanBuild(f->SN, buildingType, x, y);
    pendingBuildIns[buildInsId] = {f->SN, buildingType};
    pendingBuildInsFrame[buildInsId] = frame;
    lastBuildIssueFrame[buildingType] = frame;

    // 记录尝试过的位置，防止反复在同一位置建造失败
    int key = x * 1000 + y;
    triedBuildPositions.insert(key);

    buildCooldown = 5;   // 5帧冷却（单位碰撞检测已防止重复失败）
    return true;
}

// ============================================================
// 处理建造指令执行结果：失败则释放建造者并换位置重试
// ============================================================
void UsrAI::handleBuildResults() {
    // 极端安全：待定建造指令异常堆积则清空，避免无限增长
    if (pendingBuildIns.size() > 64) { pendingBuildIns.clear(); pendingBuildInsFrame.clear(); }

    for (auto it = pendingBuildIns.begin(); it != pendingBuildIns.end(); ) {
        int insId = it->first;
        int farmerSN = it->second.first;

        // ★ 结果迟迟不回（引擎未回执）→ 超时清理，否则该名额会被 countBuildingsExisting 永久虚占，
        //   导致建筑被毁后永远无法重建。
        if (!info.ins_ret.count(insId)) {
            auto fit = pendingBuildInsFrame.find(insId);
            if (fit != pendingBuildInsFrame.end() && frame - fit->second > PENDING_BUILD_TIMEOUT) {
                pendingBuildInsFrame.erase(fit);
                it = pendingBuildIns.erase(it);
                continue;
            }
            ++it; continue;
        }

        int ret = info.ins_ret[insId];
        if (ret == ACTION_SUCCESS) {
            // 内核已接受并放下地基
            pendingBuildInsFrame.erase(insId);
            it = pendingBuildIns.erase(it);
            continue;
        }

        // 建造失败：释放建造者，让下一帧重新选址
        buildingFarmerType.erase(farmerSN);

        // 位置类错误才立即换位置重试（该位置已在 tryBuild 中加入黑名单）
        // 资源不足/未解锁类错误则等 manageBuildings 的条件恢复后再自然重试
        if (ret == ACTION_INVALID_HUMANBUILD_DIFFERENTHIGH ||
            ret == ACTION_INVALID_HUMANBUILD_OVERBORDER ||
            ret == ACTION_INVALID_HUMANBUILD_UNEXPLORE ||
            ret == ACTION_INVALID_HUMANBUILD_OVERLAP ||
            ret == ACTION_INVALID_POSITION_NOT_FIT) {
            buildCooldown = 0;   // 解除冷却，允许下一帧立即重试
        }
        pendingBuildInsFrame.erase(insId);
        it = pendingBuildIns.erase(it);
    }

    // 已建成/已消失的建筑：清掉对应的孤儿地基/废弃地基追踪，避免 map 无限增长
    if (frame % 300 == 0) {
        for (auto it = orphanBuildFrame.begin(); it != orphanBuildFrame.end(); ) {
            bool alive = false;
            for (auto &b : info.buildings)
                if (b.SN == it->first && b.Percent < 100) { alive = true; break; }
            if (!alive) it = orphanBuildFrame.erase(it); else ++it;
        }
        for (auto it = deadBuildingsFrame.begin(); it != deadBuildingsFrame.end(); ) {
            bool alive = false;
            for (auto &b : info.buildings)
                if (b.SN == it->first) { alive = true; break; }
            if (!alive) it = deadBuildingsFrame.erase(it); else ++it;
        }
    }
}

// ---- 资源采集分配 ----

// ============================================================
// 检测寻路卡死的采集村民：空手且长时间非空闲 → 判定目标不可达，强制打断 + 拉黑
// ============================================================
void UsrAI::detectStuckGatherers() {
    // 到期解禁（临时拉黑，避免永久丢失只是暂时被堵的资源）
    for (auto it = stuckResourceUntil.begin(); it != stuckResourceUntil.end(); ) {
        if (it->second <= frame) it = stuckResourceUntil.erase(it);
        else ++it;
    }

    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return;

    for (auto &f : info.farmers) {
        // 跳过：建造者 / 引诱者 / 探路者（本就非空闲+空手，不是采集卡死）
        if (buildingFarmerType.count(f.SN) || f.SN == scoutFarmerSN) {
            gatherStuckFrame.erase(f.SN);
            continue;
        }
        // ★ 猎狮村民：同样是"空手+非空闲"，但属于正常战斗行为，不能当成寻路卡死(否则会被拉回TC并拉黑狮子)
        if (lionHunterSN.count(f.SN)) {
            gatherStuckFrame.erase(f.SN);
            continue;
        }
        // 已采到东西(Resource>0) 或 空闲(IDLE) → 正常，清空计时
        if (f.Resource > 0 || f.NowState == HUMAN_STATE_IDLE) {
            gatherStuckFrame.erase(f.SN);
            continue;
        }
        // 空手 + 非空闲：累计时长，超时判定寻路卡死
        if (gatherStuckFrame.find(f.SN) == gatherStuckFrame.end()) {
            gatherStuckFrame[f.SN] = frame;
        } else if (frame - gatherStuckFrame[f.SN] > STUCK_GATHER_TIMEOUT) {
            int targetSN = f.WorkObjectSN;
            if (targetSN > 0) stuckResourceUntil[targetSN] = frame + STUCK_BLACKLIST_FRAMES;
            HumanAction(f.SN, center->SN);  // 打断卡死关系，回TC重新待命
            gatherStuckFrame.erase(f.SN);
            DebugText(QString("[STUCK f=%1] 村民SN=%2 寻路卡死, 目标资源SN=%3 已拉黑").arg(frame).arg(f.SN).arg(targetSN));
        }
    }
}

bool UsrAI::tryAssignFood(tagFarmer* f) {
    if (!f) return false;

    // ★ 每帧清理：已完成狩猎的农民移出狩猎组（防止卡死在组内无法再次狩猎）
    for (auto it = huntingGroup.begin(); it != huntingGroup.end(); ) {
        bool still = false;
        for (auto &x : info.farmers)
            if (x.SN == *it && x.NowState == HUMAN_STATE_ATTACKING) { still = true; break; }
        if (!still) it = huntingGroup.erase(it); else ++it;
    }

    bool isWarTime = (state >= DEFENSE_WAVE1 && state <= DEFENSE_WAVE3);

    double BL = (double)BLOCKSIDELENGTH;
    auto center = findBuilding(BUILDING_CENTER);
    double tcDR = center ? (center->BlockDR + 1) * BL : f->DR;
    double tcUR = center ? (center->BlockUR + 1) * BL : f->UR;

    // ★ 优先级1：浆果丛（TC 30格内，每丛≤2人，满2人后按优先级转大象/农场/瞪羚）★
    tagResource* bestBush = nullptr;
    double bestBDist = 1e12;
    for (auto &r : info.resources) {
        if (r.Type != RESOURCE_BUSH || r.Cnt <= 0) continue;
        if (stuckResourceUntil.count(r.SN)) continue;  // 不可达的浆果，跳过
        if (calDistance(tcDR, tcUR, r.DR, r.UR) > 30 * BL) continue;
        int realCount = 0;
        for (auto &other : info.farmers)
            if (other.WorkObjectSN == r.SN) realCount++;
        if (realCount + frameBushCount[r.SN] >= 2) continue;  // 每丛≤2人（含本帧已分，满2人转其他事）
        double d = (r.DR - f->DR)*(r.DR - f->DR) + (r.UR - f->UR)*(r.UR - f->UR);
        if (d < bestBDist) { bestBDist = d; bestBush = &r; }
    }
    if (bestBush) {
        HumanAction(f->SN, bestBush->SN);
        frameBushCount[bestBush->SN]++;  // 本帧标记该丛已分1人
        return true;
    }

    // ★ 优先级2：狩猎大象（优先于瞪羚！每头200~300食物，波次期间禁止）★
    if (!isWarTime) {
        auto elephant = findNearestResource(RESOURCE_ELEPHANT, f->DR, f->UR);
        if (elephant && elephant->Cnt > 0 &&
            calDistance(tcDR, tcUR, elephant->DR, elephant->UR) <= 30 * BL &&
            !frameFoodTargets.count(elephant->SN) && !stuckResourceUntil.count(elephant->SN)) {
            HumanAction(f->SN, elephant->SN);
            frameFoodTargets.insert(elephant->SN);
            return true;
        }
    }

    // ★ 优先级3：农场（每块≤1人，实时扫描+同帧去重）★
    for (auto &b : info.buildings) {
        if (b.Type != BUILDING_FARM || b.Percent < 100) continue;
        if (frameFoodTargets.count(b.SN)) continue;  // 本帧已分配
        int realCount = 0;
        for (auto &other : info.farmers)
            if (other.WorkObjectSN == b.SN) realCount++;
        if (realCount >= 1) continue;
        HumanAction(f->SN, b.SN);
        frameFoodTargets.insert(b.SN);  // 本帧标记
        return true;
    }

    // ★ 优先级4：狩猎瞪羚（每只≤2人，WorkObjectSN实时统计）★
    if (!huntingGroup.count(f->SN)) {
        // 找最近的瞪羚（每只≤2人，含本帧已分）—— ★ 范围 2026-09-04 放宽到 GAZELLE_HUNT_RANGE=50
        tagResource* bestGazelle = nullptr;
        double bestGDist = 1e12;
        for (auto &r : info.resources) {
            if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) continue;
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > GAZELLE_HUNT_RANGE * BL) continue;
            if (stuckResourceUntil.count(r.SN)) continue;  // 不可达的瞪羚，跳过
            int realCount = 0;
            for (auto &other : info.farmers)
                if (other.WorkObjectSN == r.SN) realCount++;
            if (realCount + frameGazelleCount[r.SN] >= 2) continue;  // 每只≤2人（含本帧已分）
            double d = (r.DR - f->DR)*(r.DR - f->DR) + (r.UR - f->UR)*(r.UR - f->UR);
            if (d < bestGDist) { bestGDist = d; bestGazelle = &r; }
        }
        if (bestGazelle) {
            HumanAction(f->SN, bestGazelle->SN);
            huntingGroup.insert(f->SN);
            frameGazelleCount[bestGazelle->SN]++;
            return true;
        }
    }

    return false;
}

bool UsrAI::tryAssignWood(tagFarmer* f) {
    // ★ 2026-09-06：原实现(锚点评分)已上提为公共函数 findBestWoodTree()，本函数仅保留兼容入口，
    //   避免同一套选树逻辑出现两份分叉实现。详见 findBestWoodTree() 注释。
    if (!f) return false;
    tagResource* t = findBestWoodTree(f->DR, f->UR);
    if (t) { HumanAction(f->SN, t->SN); return true; }
    return false;
}

bool UsrAI::tryAssignGold(tagFarmer* f) {
    if (!f) return false;
    auto res = findNearestResource(RESOURCE_GOLD, f->DR, f->UR);
    if (res && !stuckResourceUntil.count(res->SN)) { HumanAction(f->SN, res->SN); return true; }
    return false;
}


