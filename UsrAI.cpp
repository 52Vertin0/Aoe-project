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
#define MAX_FARMS 12            // 农场上限：7→12（2026-09-12 用户需求"农场上限是否可以提升，基地附近位置不够的话可以建在谷仓周围"）
                               //   ⮕ R5 末 5+20+30 = 340 食 vs TC 用率 25%：上限放宽至 12 给更多食物通道；
                               //   ⮕ 选址回退链：findFarmRingSite（TC 环）→ findFarmNearGranarySite（谷仓环）→ findBuildSite（兜底）。
                               //   ⮕ 谷仓环绕允许：解决"TC 周围 5 圈已被房屋/兵营/市场/箭塔挤满"的边界 case。
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
// ★★★ 2026-09-13 用户要求「木材加工科技解锁应排在建造农场之前」★★★
//   农场每座吃掉 75 木；市场·木材加工（120食+75木）给伐木 +50%。
//   用【未加成】的伐木速度去铺农场＝低效 ⇒ 农场加闸：marketWoodUpgraded 未完成前不建农场。
//   ★ 实测时序（16 局）：市场 f≈5200~5600 建成 → 木材加工 f≈12440~15395 研究完；
//     而农场前置【瞪羚仓库】f≈9000 就绪 ⇒ 旧逻辑下农场会抢在科技之前开始铺，正是本次要修的顺序。
//   ★ 必须配超时兜底：市场未建成 / 长期缺木 / 市场被摧毁 → 科技永不完成 → 农场永久冻结 → 食物崩盘。
//     兜底取 18000(12min)，比实测最晚研究帧 15395 留 2600 帧余量；触发后本闸自动失效。
#define FARM_WAIT_WOOD_TECH_FRAME 18000
// ★★★ 2026-09-13 用户要求「复合弓兵科技解锁太慢」——农场给复合弓科技让木 ★★★
//   实测根因：12 座农场（每座 75 木）从 f≈13500 连续建造，把木材长期压在 2~112 区间
//   （k1: f=16380 wood=15 / f=20070 wood=2 / f=20970 wood=2），而复合弓科技要求 wood≥100
//   ⇒ 木闸成为真实瓶颈（食物早已 208→621 远超 180），科技被拖到 f=24759（16.5 分钟）才发令。
//   修复：复合弓科技【尚未研究/排队】期间，农场建造额外要求"造完仍留得住 100 木"，
//   即 info.Wood >= FARM_WOOD_NEED + COMPOSITE_BOW_WOOD_RESERVE。
//   ★ 超时兜底：靶场长期被占/被拆 / 木头长期枯竭 → 科技永不完成 → 农场永久冻结 → 食物崩盘。
//     兜底帧取 21000（= WAVE3_TIME，反攻线；实测最晚科技帧 24759 之前的保守值），
//     触发后本闸自动失效，农场恢复正常节奏。
#define FARM_WAIT_CB_FRAME 21000
#define COMPOSITE_BOW_WOOD_RESERVE 100   // = BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_WOOD
// ★★★ 2026-09-13 用户要求：「我方军队不要攻击敌方武器厂」★★★
//   现状：全军（近战/远程/投石车）在建筑选择里都写 `siege ? siege->SN : ...`——
//   一旦侦察到敌方武器厂，**全军一律优先轰武器厂**（实测 k8 局 347 条"设置攻击目标为 攻城武器厂"）。
//   用户要求改成：军队**不**把武器厂当攻击目标（武器厂留给祭司感化）。
//   ⇒ 把武器厂从"军队建筑目标选择"里剔除，军队改打【箭塔 → 其它任意敌建筑】。
//   ⚠ 仍保留 seize 作为【反攻推进锚点】(targetDR/targetUR/rallyDR/rallyUR/directMarch)，
//     否则 `directMarch` 失去依据 → 军队退回"对角角落猜测"（见 tower_nearest 轮 run4 的教训）。
#define ARMY_IGNORE_SIEGE_WORKSHOP true
// ★★★ 2026-09-13 用户要求：「敌方军队全灭且箭塔全拆后，祭司应去感化敌方武器厂」★★★
//   根因：祭司"安全距离 PRIEST_MIN_DIST_TARGET=18 格"与"感化武器厂需 pDist<12 格"**互相矛盾**，
//   实测 [PRST-REAR] 的 dTgt 恒在 22.6~36.4 格 ⇒ 祭司永远够不到 12 格 ⇒ 感化武器厂 0 次。
//   修复：当【敌方已无军事威胁】(敌方军队+敌方箭塔均为 0) 时解除安全距离约束，
//   祭司允许主动前出到武器厂旁感化（此时无威胁，前出不会送命——这正是用户描述的场景）。
#define PRIEST_CONVERT_SIEGE_WHEN_CLEAR true
#define PRIEST_CONVERT_SIEGE_RANGE 12.0  // 引擎感化射程口径（DIS_PRIEST=12），须 ≤ 此值才能感化
// ★ 打猎瞪羚选取范围（2026-09-04 用户要求"扩大一些"）：30→50 格，覆盖远距未建仓库的瞪羚群。
//   仓库覆盖判断（1547/1705 nearStock）也用此常量同步，避免猎人跑出去 50 格打、仓库仍卡 30 格内。
#define GAZELLE_HUNT_RANGE  50
// ★★★ 2026-09-12 用户需求：「在村民开始狩猎瞪羚前尽量先建仓库，仓库可以比其他建筑先建」★★★
//   参考录像 build order（见 `detail_2026-09-12_scoring_meta.md §3`）：
//     01:35 村民抵达猎场开始猎瞪羚 → 01:47 猎人【就地】建仓库 → 02:05 仓库落成
//     → 之后才是市场 03:58 / 兵营 05:17 / 靶场 05:58。即"仓库抢在一切其他建筑之前落地"。
//   旧实现有两处顺序是反的：
//     ① 【打猎在前】建造闸门是 `!huntingGroup.empty()`（已经有人在打猎才肯建仓库）
//        ⇒ 仓库永远晚于打猎，猎人先空跑「TC↔瞪羚群」往返(2×距离)直到仓库建成；
//     ② 【优先级在后】块埋在 `if(postW1)`(≥3.33min) 内、排在房屋/兵营/靶场【之后】
//        ⇒ 木材被下游建筑抢光（builtThisFrame 互斥），仓库常常建不出来。
//   新实现：块上移到【所有建筑之前】(preW1 起就检查)，闸门由"有猎人"改为"TC 可猎范围内有瞪羚"。
#define GAZELLE_STOCK_MIN_HOUSES    1     // 抢跑前提：至少已有 N 座房屋（先保人口线，再抢仓库）
#define GAZELLE_STOCK_WINDOW_END    16500 // 仓库建造窗口截止(帧)=11游戏分（原为硬编码 16500）
// ★ 打猎解禁兜底（防止闸门把食物经济饿死）：仓库迟迟建不出时，不能无限期卡住打猎——
//   frame ≥ 此值 或 木头不够造价 或 已过建造窗口 ⇒ 允许先打猎（仓库仍会继续尝试建造）。
#define GAZELLE_STOCK_GATE_DEADLINE 9000  // 6游戏分 = 9000 帧
// ★ 组队猎象（2026-09-03 用户需求）：大象血45/攻10/射程10/不逃跑/掉肉300，性价比远超瞪羚(血8会逃跑)。
//   单挑村民(血25)必死，须凑够 ELEPHANT_HUNT_GROUP 人围猎快速击杀。每头象最多派此人数，集中火力不分散。
//   ★ 2026-09-08 用户新需求"大象一定要4个人以上狩猎"：增设 ELEPHANT_HUNT_MIN=4 作为凑人门槛，
//     1~3 人在打时优先补位；0 人在打时本帧允许派 1 人开团，但限 ELEPHANT_HUNT_MIN 累计防单挑送命。
#define ELEPHANT_HUNT_GROUP 5
#define ELEPHANT_HUNT_MIN   4   // ★ 打大象的最低人数门槛(开团/补位都遵循)
// ★ 2026-09-13 用户需求强化「狩猎大象必须 4 个人一起狩猎，单个村民狩猎会死」：
//   旧实现是"逐帧凑人"（0 人在打时本帧先派 1 人开团，其余人随后才到）⇒ 先到者在 1~3 人状态下被打死。
//   现改为【整队一次性出击】：同一帧下 min 条令 ⇒ 同时出发 ⇒ 同时抵达 ⇒ 同时开打；凑不齐一人不派。
#define ELEPHANT_RESCUE_MAX_ON 1  // ★ 只有"孤兵/双人"(在打人数≤此值)才强制救援：能补则补，补不齐则召回+拉黑
#define ELEPHANT_BAN_FRAMES    1500  // ★ 孤兵救援后的拉黑时长：1500 帧 = 60 秒内不再往这头象派人
#define MAX_TOWERS 3            // 箭塔数量（2026-09-13 用户改需求：从2座再多建1座=3座；上限抬至3，多采150石建第3座）
#define MAX_RANGES 3            // 反攻阶段靶场上限(并行产弓线，越多弓兵越快)
// ★ 2026-09-13 用户需求「士兵攻击箭塔时选择距离自己最近的箭塔为目标」：
//   此前士兵在反攻期打建筑只有两个来源——① findNearestEnemyBuilding(范围内任意类型最近建筑)、
//   ② 「武器厂(siege)绝对优先」覆盖。后果：a) 更近的房屋/农场/谷仓会把箭塔顶掉 ⇒ 挨塔射却不还手；
//   b) 一旦找到敌方武器厂，全军改打武器厂、附近箭塔被无视 ⇒ 攻城时持续被塔白嫖输出。
//   新规则：士兵选建筑目标时，【距离自己最近的敌方箭塔】优先于 武器厂 与 任意其它敌建筑；
//   仅在 TOWER_TARGET_RANGE 格内生效（超出则该塔不构成即时威胁，维持"直奔武器厂"的反攻目标语义）。
//   ⚠ 只影响"选建筑目标"，不改变打敌方【单位】的优先级(单位永远优先于建筑)。
#define TOWER_TARGET_RANGE 12   // 士兵把敌方箭塔纳入攻击目标的最大距离(格)；箭塔射程≈8格
// ★★★ 2026-09-12 改：允许多群瞪羚各建 1 座仓库，1+3=MAX_STOCK=4 座上限。
//   原 MAX_STOCK=2 限制下，多群瞪羚（典型地图 3~4 群）只能有 2 群被覆盖、其余猎人空跑回最近仓库。
//   现在 4 座可覆盖近距（首发块）+ 远距（远距块）所有主要聚类，无聚类猎人空跑交肉。
#define MAX_STOCK 4             // 仓库上限：每群覆盖 1 座 + TC 旁首仓 1 座 + 远距覆盖 1~2 座 = 4 座
                                  // ★ 2026-09-04 实测补：此前缺此上限，旧"第二仓库"段（1676）每帧重发令+不传坐标，
                                  //   导致贴 TC 多建 3 座仓库（地图多群远距瞪羚就触发多次）
// ★ 第二仓库（远距瞪羚群仓库）的最少瞪羚数门槛（2026-09-07 用户需求"如果没瞪羚就跳过建造第二仓库"）。
//   判定用的是"距 TC>20 且 距所有现有 Stock>20"的远距瞪羚数量；
//   低于此数则【完全跳过】第二仓库（既不建、也不让 needSecondStock 阻塞市场/靶场）。
//   默认 2：为 1 只离群瞪羚花 150 木 + 村民长途跋涉不划算。
//   ⚠ 想改成"只要有 1 只远距瞪羚就建"→ 把值改为 1；想更保守（必须是成群的）→ 改 3 或更大。
#define MIN_GAZELLE_FOR_SECOND_STOCK 2
// ★ 远距浆果群第二谷仓（2026-09-07 用户需求："除了 TC 附近还有 >=6 丛浆果地的话，在旁边建谷仓，派村民去采集"）
//   浆果 resourceSort = HUMAN_GRANARYFOOD → 交付建筑就是【谷仓】(StaticRes.cpp:NUM_STATICRES_Bush)，
//   所以在远处浆果群旁建谷仓能直接把往返距离压到 20 格内，比跑回 TC/第一座谷仓高效得多。
#define MAX_GRANARY 2                   // 谷仓上限：1 座服务 TC 附近浆果 + 1 座服务远距浆果群
#define MIN_BUSH_FOR_SECOND_GRANARY 6   // 远距浆果群最少丛数（<6 丛不值得花 120 木）
#define SECOND_GRANARY_TC_MIN_DIST 25   // "TC 之外"判据：浆果群中心须距 TC ≥ 25 格(BL)
#define BUSH_CLUSTER_RADIUS 5           // 浆果群聚类半径(BL)：5 格内的丛算同一片
#define BUSH_NEAR_GRANARY_DIST 20       // 派工放宽：浆果距任一【已建成】谷仓 ≤ 20 格即可派人采集
// ★ 不训练棍棒兵【后期】（2026-09-03 用户要求）：棍棒兵改为由箭塔替代防守，省下食物/人口转向箭塔+复合弓。
//   ⚠ 此开关只管【后期三处】：工具时代填线块(3019) / 优先级2.5 廉价填线(3163) / 优先级3 食物溢出爆近战(3181)。
//     前期过渡用的棍棒兵由下面 ENABLE_EARLY_CLUBMAN 独立控制，两者互不干扰。
#define DISABLE_CLUBMAN_TRAIN true
// ★ 前期棍棒兵过渡：复合弓 15 分钟前完全停产(COMPOSITE_BOW_MIN_FRAME)，而 DISABLE_CLUBMAN_TRAIN 又关了兵营
//   → 前 15 分钟【零自产兵力】，只能靠 2 座箭塔 + 祭司感化扛三波（W2 前只有 2 个棍棒兵 → 曾致祭司被杀）。
//   棍棒兵 50 食物、无石头/黄金依赖 → 不吃复合弓的黄金，是空窗期唯一可行的填线兵。
//   ★ 起始 4 分钟：更早造会拖慢村民生产与 800 食物升铜器。
//   ★ 停造 15 分钟(COMPOSITE_BOW_MIN_FRAME)：复合弓一投产就停，食物/人口全留给复合弓＝"过渡"语义。
#define ENABLE_EARLY_CLUBMAN true
#define EARLY_CLUBMAN_START_FRAME 6000   // 4 分钟 × 1500 帧/分钟 = 6000 帧
#define EARLY_CLUBMAN_TARGET 4           // 前期棍棒兵目标数（用户 2026-09-08 指定：4 个；改此行即调数量）
// ★ 建造/地基保护常量
#define DEAD_BUILDING_GRACE 1800  // 废弃地基宽限期(帧,30秒)：拉黑后这段时间内仍算"已存在"，
                                  // 给"孤儿地基抢救"时间补救；超时才允许另择新址重建(避免重复建造)
#define ORPHAN_REDISPATCH_CD 120  // 孤儿地基(在建但无人施工)补派村民的节流间隔(帧，纯空闲村民)
#define ORPHAN_STEAL_CD 300       // ★ 2026-09-13 关键建筑"抽人"抢救的节流(帧)：空闲村民取不到时，
                                  //   允许从采集岗抽 1 人施工。间隔更长(5秒)以免经济被反复抽干。
#define BUILDER_HARD_TIMEOUT 1800 // ★ 2026-09-13 建造者硬超时(帧,72秒)：从下达建造令起算，
                                  //   无论处于何种状态(WALKING 走不到 / 被改派 / 反复卡顿)，
                                  //   只要该地基仍未完工且本人不在施工 → 判作废(拉黑+释放)，
                                  //   让 manageBuildings 另择新址重建。修"地基永久卡 0% 无人施工"。
#define PENDING_BUILD_TIMEOUT 300 // 建造指令结果迟迟不回的超时(帧)：超时则清掉占位，防止永久虚占名额
#define BUILD_GAP 1              // 建筑间距：候选建筑footprint外扩1格内不得有其他建筑(含敌我)，避免建筑成墙堵死路
#define MELEE_OVERFLOW_FOOD 150      // 后期/反攻"爆近战"食物溢出阈值：食物≥此值才大规模造近战兵(棍棒/方阵)
// ★★★ 2026-09-13 方阵兵编制比例（用户要求"放宽方阵兵数量"，选定 3:4 温和档）★★★
//   上限公式：hop < NUM/DEN × comp + FLOOR
//     旧版硬编码 (comp+4)/2 ⇒ 长期趋近 1:2（复合弓为主、方阵为辅，o8 局实测 hop 只到 4）
//     新版 3/4×comp + 2  ⇒ 长期趋近 3:4，方阵兵约 +50%，仍保证"复合弓为主"不被反超
//   逐点对照(comp→hop上限)：0→2 / 2→3 / 4→5 / 6→6 / 8→8 / 10→9 / 20→17 / 40→32
//     （comp≤2 时与旧版完全一致：开局零弓兵也先出 2 个方阵顶前排，不断肉盾）
//   ★ 同时作用于【反攻期】与【后期(lateGame)】两个方阵产线块；黄金预留策略保持严格不变。
#define HOPLITE_RATIO_NUM   3    // 比例分子：hop 上限 ≈ comp × NUM/DEN
#define HOPLITE_RATIO_DEN   4    // 比例分母
#define HOPLITE_RATIO_FLOOR 2    // 保底基数：comp=0 时也先出 2 个方阵挡刀（与旧版一致）
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
// ★ 2026-09-07 由 20 下调到 12（用户实测驱动）：
//   反攻态已由 updateState 在「三波全清 / frame>COUNTER_ATTACK_FORCE_TIME 强制」时进入，此时敌方主力已被消灭，
//   再等 20 人已无意义；而实测军队长期停在 12 人左右（复合弓 15 分钟前停产 + 战损），
//   导致 readyToAttack 恒 false ⇒ ① kiting 整段被跳过（"反攻时不会后撤"）
//   ② 全军被 4143 段反复 HumanMove 回 TC 同一点（"复合弓兵在 TC 附近来回走"）。
//   ⚠ 改小=更早推进、更零散；改大=更保守但要等更久（24 分钟强制兜底仍在）。
#define COUNTER_ATTACK_MIN_ARMY 12   // ★ 全体反攻门槛：非祭司军队(含远程/近战/投石车)≥此数才一起反攻，避免单个士兵零散冲出被集火
#define COUNTER_ATTACK_FORCE_TIME 33000 // 22分钟强制反攻(=33000帧,1500帧/分钟)：即使人数不足也一起进攻
                                        // （2026-09-14 用户要求：24分钟→22分钟，提前2分钟反攻，
                                        //   目的是给"发现敌方武器厂"留更长的窗口——实测胜局均在
                                        //   26~28.5 分钟才探到武器厂，距 45000 帧上限仅剩 1~4 分钟）
                                        // 沿革：2026-09-04 用户要求 22→24 分钟(多留2分钟集结攒兵)；
                                        //       本次按新需求回调至 22 分钟。
// ★ 祭司护驾三级半径(格)：祭司死=立刻失败，故护驾优先于士兵自卫/守家/前出等一切军事行为
#define PRIEST_GUARD_URGENT 8.0   // 紧急：敌进入祭司此半径 → 所有兵(可打断战斗)立即回防
#define PRIEST_GUARD_ALERT  15.0  // 预警：敌进入祭司此半径 → 空闲/行军兵前往护驾(不打断正在战斗的兵，防反复横跳)
#define PRIEST_GUARD_RECALL 30.0  // 召回上限：只调距祭司此半径内的兵回防(避免把反攻大军从全图拉回)
#define PRIEST_GUARD_MAX_CMDS 12  // 护驾指令每帧上限(独立于普通 attackCmds，保证护驾不被限流饿死)
// ★ 祭司感化目标选取范围(格)：从 20 扩到 28，让祭司更主动地去感化远处的投石车等高价值目标。
//   (投石车射程10格、感化射程14格；28格仍在护驾召回半径 PRIEST_GUARD_RECALL=30 内，不会脱离保护。)
#define PRIEST_CONVERT_RANGE 28.0
// ★ 2026-09-12 反攻期祭司安全距离（用户需求"祭司反攻不要太靠前，尽量在安全距离"）：
//   旧版把祭司推到 target(敌基地)-5格(仅沿 DR 轴退5格)，祭司几乎与大军一起冲到敌基地外5格 → 前线一崩即被秒。
//   新方案：祭司跟随【己方大部队重心】(排除自身)，始终位于大队【后方】(朝 TC 方向) PRIEST_SAFE_BEHIND 格；
//   且强制与反攻目标(敌基地/武器厂)保持 ≥ PRIEST_MIN_DIST_TARGET 格 —— 祭司永远在大部队身后，不单独前出、不冲进敌射程。
#define PRIEST_SAFE_BEHIND     8.0   // 祭司在大队【身后】(朝 TC 方向)的安全距离(格)
#define PRIEST_COUNTER_FLEE_HP 0.6  // 2026-09-13 保祭司：反攻期被远程集火时的撤退血量阈值(<=此值且在敌射程内即撤)
#define PRIEST_MIN_DIST_TARGET 18.0  // 祭司与反攻目标(敌基地/武器厂)的最小安全距离(格)
// ★★★ 临时封禁开关：改 true→false 即可恢复建造 ★★★
// ★ 2026-09-13 解封（用户要求"解锁马厩和学院，并在后期建造方阵兵"）：
//   马厩 = 学院前置（Development.cpp:804 addPreCondition(STABLE.buildCon)），不解马厩则学院永远建不出。
//   学院 = 方阵兵唯一产线（Development.cpp:807-810，BRONZEAGE + 60食+40金，无额外科技依赖）。
//   骑兵训练仍由 DISABLE_CAVALRY_TRAIN=true 独立封禁 → 建马厩不会偷吃复合弓的黄金。
//   回滚：两个宏改回 true 即可。
#define DISABLE_STABLE_BUILD  false   // 2026-09-13 解封：恢复马厩建造（作学院前置；骑兵仍不训练）
#define DISABLE_COLLAGE_BUILD false   // 2026-09-13 解封：恢复学院建造（方阵兵产线，后期即可投产）
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
// ★ 2026-09-06 用户定案：只研究少数几项科技，其余全部封禁。
//   ★ 2026-09-13 用户要求：解锁【步兵护甲+鳞甲、弓兵护甲+鳞甲】共四项护甲科技（见下方 ARMOR_* 成本宏）。
//   各开关与上方 DISABLE_BROADSWORD_TECH / DISABLE_TOWER_UPGRADE 同风格，单独恢复只需改回 false。
#define DISABLE_USETOOL_TECH true         // 仓库·工具使用（100食物，近战+2）—— 仍封禁（用户未要求；其二柄为金属加工 200食+120金）
#define DISABLE_INFANTRY_ARMOR_TECH false // 仓库·步兵护甲链（护甲→鳞甲）—— ★ 2026-09-13 解锁
#define DISABLE_ARCHER_ARMOR_TECH   false // 仓库·弓兵护甲链（护甲→鳞甲）—— ★ 2026-09-13 解锁（此前无独立开关，恒开）
// ---------------------------------------------------------------------------
// ★ 仓库护甲链成本（对齐 config.json:126-143，引擎实际扣费口径）
//   引擎事实：BUILDING_STOCK_UPGRADE_DEFENSE_INFANTRY / _ARCHER 都是"两柄动作"——
//   第 1 次调用 = 护甲(+2 近战防御)，第 2 次调用 = 鳞甲(再 +2)，同一建筑动作 ID 共用。
//   （见 AI接口使用指南.md:352、Building.h:137-158、Development.cpp:158-180）
//   顺序（用户 2026-09-13 定案）：一级先铺满 —— 步兵护甲 → 弓兵护甲 → 步兵鳞甲 → 弓兵鳞甲。
// ---------------------------------------------------------------------------
#define ARMOR_INF_T1_FOOD   75    // 步兵护甲：近战单位近战防御 +2
#define ARMOR_INF_T2_FOOD   100   // 步兵鳞甲：再 +2
#define ARMOR_INF_T2_GOLD   50
#define ARMOR_ARC_T1_FOOD   100   // 弓兵护甲：弓兵近战防御 +2
#define ARMOR_ARC_T2_FOOD   125   // 弓兵鳞甲：再 +2
#define ARMOR_ARC_T2_GOLD   50
// 发令后等多少帧仍未"仓库变忙"即判定引擎拒令 → 回滚级数、下帧重试（铁律：绝不"发令即置真"）
#define ARMOR_ACCEPT_TIMEOUT 120
#define DISABLE_MARKET_TECH true          // 市场其余 4 项经济科技（驯养/车轮/犁/工艺）—— 封禁
#define DISABLE_MARKET_WOOD_TECH false    // 市场·木材加工（120食物+75木材，伐木+50%）—— 已解禁(能解锁就解锁)
//   ⚠ 注意：市场【建筑本身】不能停建！1483 行 `marketReady` 是农场建造的前置闸门，
//     停建市场会导致农场永远建不出来。封禁的只是市场里的科技研究。
// ★ 2026-09-12 用户要求：伐木科技（市场·木材加工）提为【解锁类科技最优先】。
//   实现：判定块已从 TIER3 末尾上移到【铜器后第一个被检查的科技】位置，
//   越过了原 `frame < WAVE3_TIME`(14min) 前置锁与 `milUnlocked`(军事解锁) 锁 ——
//   铜器一完成，只要市场已建成且资源够，伐木就是全场第一个研究的科技。
//   本开关只控制"与复合弓(P0)抢食物"时的行为：
//     true  = 绝对最优先（默认）：食物≥120 且木≥75 即研究，不与复合弓比较。
//             ★ 实测依据（2026-09-12，map.njust rotate0）：木材在 f≈12800~14000 就 ≥75，
//             但 false 档的 300食物 门槛使伐木拖到 f=22168/18753 才研究 —— 被拖后 3~6 游戏分。
//             ⇒ 用户要求"最优先"，故默认 true。
//     false = 让路保护：复合弓尚未研究/排队时，需食物同时负担两项
//             (复合弓180 + 伐木120 = 300) 才允许伐木插队；否则让复合弓先走。
//             ⚠ 实测该门槛过高（铜器后食物常年在 158~257），会把伐木压成"永远晚于复合弓"。
#define WOOD_TECH_ABSOLUTE_FIRST true
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
#define STONE_CAP_STOP 300   // 石头≥300 不再采石（2026-09-13 用户需求「再多建一座箭塔」：3座箭塔=开局150石建第1座+额外采300石建第2~3座，故上限300）
// ★ 2026-09-03 用户需求："木头维持150左右、优先食物"。木头是"够用就行"的资源：
//   日常水位 150（够房屋30/谷仓120/兵营125/靶场150/马厩150/市场150/农场75），省下人力全投食物。
//   但后期有高木头门槛：反攻多靶场(WAVE3_TIME后 Wood≥230)、学院(反攻期 Wood≥210)，
//   故 WAVE3_TIME 后临时放宽到 250，避免这些关键建筑被 150 水位卡死、永远建不了。
#define WOOD_CAP_STOP  220   // 木头≥220 日常停采（2026-09-12 用户需求"提高上限"150→220：多存 70 木覆盖多靶场+学院同时建）
#define WOOD_CAP_STOP_LATE 320 // 反攻准备期(WAVE3_TIME后)木头水位（2026-09-12 250→320：反攻期 5~6 靶场并发 + 学院 + 马厩 80~250 木余量）
#define WOOD_KEEP_MIN  2     // 木头达上限回撤时保留的伐木工人数
#define GOLD_CAP_STOP  1000  // ★ 黄金≥1000 不再派金工（2026-09-12 800→1000：一场反攻 20 CB + 10 方阵 + 1 投石车 ≈ 800~900 黄金花完，留 100 余量）
                                //   ★【2026-09-11 3.0.7f 改】每矿堆 200→400，黄金总量上限同步翻倍(400→800)。
                                //     若仍 400，则采完一矿堆就立即触发 goldRich → 黄金被压到 MIN_GOLD_WORKERS，
                                //     矿堆才采一半就转采其他资源 → 效率浪费。
                                //     设 800 = 2 矿堆满额 = 实际反攻所需黄金(800)安全储备。
#define FOOD_CAP_STOP  650   // ★ 铜器后：食物≥650 不再派新食物工（2026-09-12 500→650：解 65% 食物 rebalance 后过囤）
#define FOOD_CAP_STOP_PREBRONZE 850 // ★ 铜器前：食物停采阈值提到 850(>800升级费)，否则食物到500就停采、永远攒不够800升铜器
// ★★ 2026-09-13 铜器升级防卡死（修 o3 局整局 UPGRADING / score=224 的根因）
//   引擎侧 Development::get_isBuildActionAble() 对 BUILDING_CENTER_UPGRADE 有硬前置：
//   工具时代须已【建成】MARKET/RANGE/STABLE 中至少 2 座（hasAgeUpgradeBuildings），
//   否则返回 false 直接拒令。旧代码只查 Meat>=800 就发令并立刻 hasUpgraded=true，
//   被拒后所有升级入口的 !hasUpgraded 守卫全失效 → 永不重试、整局停在 UPGRADING。
#define BRONZE_MIN_AGE_BUILDINGS 2     // 引擎前置：市场/靶场/马厩 已存在数（缺则必然被拒，勿发令）
#define BRONZE_RETRY_INTERVAL 120      // UPGRADING 中指令未被引擎接受时的重试间隔（帧）
#define BRONZE_GIVEUP_FRAMES  3600     // 连续未确认施工超时（帧）→ 退出 UPGRADING 回 DEFENSE_PREP（继续发育/补前置）
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
// ★【2026-09-11 3.0.7f 改】每棵树最多派 2 个人砍（原为 1，3.0.7f 引擎修了"多人挤同一资源"卡死后放宽）。
//   一棵树血量 25（原版假设 1 人砍足矣），但实际派 1 人的效率不如 2 人接力；
//   3.0.7e 之前的引擎会让 2 人挤同一棵树相互卡位/原地振动，3.0.7f 修好后 2 人可正常协作，效率 +30~50%。
//   仍保留 2 人上限（不是 4/8）—— 太多人挤同一树仍然效率低（往返路径重叠、砍光后空跑）。
#define WOOD_MAX_WORKERS_PER_TREE 2   // 单棵树同帧累计工人数上限（3.0.7f: 1→2）
#define GOLD_RICH_TOL   1.25 // 黄金相对 5:3 目标配比的宽容系数：超出 1.25 倍即判定"黄金相对过剩"
// ★ 食物:黄金 目标配比 = 复合弓兵(40食+20金) 与 方阵兵(60食+40金) 成本综合 = 100:60 = 5:3
//   即 食物工数 : 黄金工数 ≈ 5 : 3（黄金工目标 = 食物工数 * 3/5，向上取整）
#define FOOD_GOLD_NUM 5
#define FOOD_GOLD_DEN 3
// ★ 石头保底采集（仅在不达停采上限时生效）：石头现仅用于
//   箭塔(150)/投石兵(10)/铜器箭塔升级(50)/采石科技(50)/建筑维修。
//   2026-09-13 用户改需求"再多建一座箭塔"：从2→3座需多采150石=总计300石。1人持续采即可
//   （边采边建，不是攒齐再建；塔建满后由 STONE_CAP_STOP/towersDone 永久停采）。
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
// ★★ 铜器升级辅助（2026-09-13 防卡死）
// ============================================================
// 引擎 Development::hasAgeUpgradeBuildings(CIVILIZATION_TOOLAGE) 要求
// MARKET/RANGE/STABLE 中至少 BRONZE_MIN_AGE_BUILDINGS 座【已建成】，否则
// get_isBuildActionAble() 直接拒令。此处用 AI 侧 countBuildingsExisting 逼近该前置
// （它把在建地基/90帧内新下发的建造令也算入，故属"乐观"判据，仅作发令前预检，
//   真正的成功判据仍是引擎回写 tc->Project == BUILDING_CENTER_UPGRADE）。
int UsrAI::countAgeUpgradeBuildings() {
    int n = 0;
    if (countBuildingsExisting(BUILDING_MARKET) > 0) n++;
    if (countBuildingsExisting(BUILDING_RANGE)  > 0) n++;
    if (countBuildingsExisting(BUILDING_STABLE) > 0) n++;
    return n;
}

// 铜器升级统一发起入口：所有状态（EARLY_ECONOMY / DEFENSE_PREP / WAVE1 / WAVE2）与
// UPGRADING 重试共用。返回 true = 本帧确实发出了升级令（或引擎已在施工）。
// ★ 绝不在此处置 hasUpgraded=true —— 只有确认引擎施工/已达铜器才由调用点锁定。
bool UsrAI::tryStartBronzeUpgrade() {
    if (info.civilizationStage >= CIVILIZATION_BRONZEAGE) return false;
    if (hasUpgraded) return false;                                     // 已确认在执行/已达成
    if (info.Meat < BUILDING_CENTER_UPGRADE_BRONZEAGE_FOOD) return false;
    auto tc = findBuilding(BUILDING_CENTER);
    if (!tc) return false;
    if (tc->Project == BUILDING_CENTER_UPGRADE) {                      // 引擎已在升级 → 视为成功
        hasUpgraded = true;
        return true;
    }
    if (tc->Project != ACT_NULL) return false;                         // TC 忙（造村民/研究），本帧不发
    if (countAgeUpgradeBuildings() < BRONZE_MIN_AGE_BUILDINGS) return false;  // 引擎硬前置未满足
    BuildingAction(tc->SN, BUILDING_CENTER_UPGRADE);
    bronzeIssuedFrame = frame;
    bronzeAttemptCount++;
    return true;
}

// ============================================================
// 阶段切换（改进版：更稳健的状态转换）
// ============================================================
void UsrAI::updateState() {
    switch (state) {
    case EARLY_ECONOMY: {
        // ★ 食物够800且引擎前置(市场/靶场/马厩≥2座)满足 → 统一入口发令
        //   （旧版只查 Meat>=800 就发令并立刻 hasUpgraded=true，被引擎拒后永不重试 → 整局卡 UPGRADING）
        if (tryStartBronzeUpgrade()) {
            state = UPGRADING;
            DebugText(QString(">> Upgrading to Bronze Age! Frame=%1, Meat=%2, Farmers=%3, ageBld=%4")
                .arg(frame).arg((int)info.Meat).arg((int)info.farmers.size())
                .arg(countAgeUpgradeBuildings()));
        }
        // 超时保护：frame > WAVE1_TIME → 进入第一波防御准备
        if (frame > WAVE1_TIME && state == EARLY_ECONOMY) {
            state = DEFENSE_PREP;
            DebugText("!! Force DEFENSE_PREP (timeout from ECONOMY)");
        }
        break;
    }
    case UPGRADING: {
        auto tc = findBuilding(BUILDING_CENTER);
        // ① 达成铜器 → 完成
        if (info.civilizationStage >= CIVILIZATION_BRONZEAGE) {
            hasUpgraded = true;
            bronzeIssuedFrame = -999999; bronzeAttemptCount = 0; bronzeStallFrames = 0;
            state = DEFENSE_PREP;
            DebugText(">> Bronze Age reached!");
            break;
        }
        // ② 引擎确认正在施工 → 正常等待（复位卡顿计时）
        if (tc && tc->Project == BUILDING_CENTER_UPGRADE) {
            hasUpgraded = true;
            bronzeStallFrames = 0;
            break;
        }
        // ③ 引擎未在施工：指令被拒/丢失 → 计卡顿并按间隔重试
        hasUpgraded = false;
        bronzeStallFrames++;
        if (bronzeStallFrames == 1 || bronzeStallFrames % BRONZE_RETRY_INTERVAL == 0) {
            bool issued = tryStartBronzeUpgrade();
            DebugText(QString("!! BRONZE-RETRY f=%1 issued=%2 try#%3 stall=%4 meat=%5 tcProj=%6 ageBld=%7(m%8 r%9 s%10)")
                .arg(frame).arg((int)issued).arg(bronzeAttemptCount).arg(bronzeStallFrames)
                .arg((int)info.Meat).arg(tc ? tc->Project : -99)
                .arg(countAgeUpgradeBuildings())
                .arg(countBuildingsExisting(BUILDING_MARKET))
                .arg(countBuildingsExisting(BUILDING_RANGE))
                .arg(countBuildingsExisting(BUILDING_STABLE)));
        }
        // ④ 兜底：长时间无法开工 → 退出 UPGRADING，恢复常规状态机（继续攒资源 + 补建前置建筑），
        //    后续 WAVE1/WAVE2/PREP 入口会自然再次尝试，绝不会像旧版那样整局卡死。
        if (bronzeStallFrames >= BRONZE_GIVEUP_FRAMES) {
            hasUpgraded = false;
            bronzeIssuedFrame = -999999; bronzeAttemptCount = 0; bronzeStallFrames = 0;
            state = DEFENSE_PREP;
            DebugText(QString("!! BRONZE-GIVEUP f=%1 → DEFENSE_PREP (need %2 of MARKET/RANGE/STABLE, have m%3 r%4 s%5)")
                .arg(frame).arg(BRONZE_MIN_AGE_BUILDINGS)
                .arg(countBuildingsExisting(BUILDING_MARKET))
                .arg(countBuildingsExisting(BUILDING_RANGE))
                .arg(countBuildingsExisting(BUILDING_STABLE)));
        }
        break;
    }

    case DEFENSE_WAVE1:
        // ★ 食物够800且引擎前置满足 → 统一入口发令（含防卡死重试）
        if (tryStartBronzeUpgrade()) {
            state = UPGRADING;
            DebugText(QString(">> WAVE1 Bronze Age! Frame=%1, Meat=%2, ageBld=%3")
                .arg(frame).arg((int)info.Meat).arg(countAgeUpgradeBuildings()));
            break;
        }
        // 第一波结束条件：敌人稀少 或 超时强制结束
        if (frame > WAVE1_TIME + 3500) {
            int eCount = info.enemy_armies.size() + info.enemy_farmers.size();
            if (eCount < 3 || frame > WAVE1_TIME + 6000) {
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
        // ★ 食物够800且引擎前置满足 → 统一入口发令（含防卡死重试）
        //   ★ 必须 break：旧版发令后继续落回下方波次检测，会把刚设的 UPGRADING
        //     立刻覆盖成 DEFENSE_WAVE1/2/3，导致升级状态机永远进不去。
        if (tryStartBronzeUpgrade()) {
            state = UPGRADING;
            DebugText(QString(">> LATE Bronze Age! Frame=%1, Meat=%2, ageBld=%3")
                .arg(frame).arg((int)info.Meat).arg(countAgeUpgradeBuildings()));
            break;
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
        // 铜器升级（统一入口：含引擎前置检查 + 防卡死重试）
        if (tryStartBronzeUpgrade()) {
            state = UPGRADING;
            DebugText(QString(">> W2 Bronze Age! Frame=%1, Meat=%2, ageBld=%3")
                .arg(frame).arg((int)info.Meat).arg(countAgeUpgradeBuildings()));
            break;
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
        // 第三波必须全部消灭；【修正 2026-09-08】+ COUNTER_ATTACK_FORCE_TIME 对齐，下方两处强制反攻都用同阈值，
        //   避免在 14~24 分钟(集结期)期间被敌数 < 3 假条件骗进 COUNTERATTACK。
        if (frame > COUNTER_ATTACK_FORCE_TIME) {
            int eCount = info.enemy_armies.size() + info.enemy_farmers.size();
            if (eCount < 3 || frame > COUNTER_ATTACK_FORCE_TIME + 6000) {
                state = COUNTERATTACK;
                DebugText(QString(">> ALL WAVES DEFEATED! Counterattack! Frame=%1").arg(frame));
            }
        }
        // 超时强制反击：与 COUNTER_ATTACK_FORCE_TIME 对齐(=22 分钟=33000 帧)
        //   【修正 2026-09-08】原 27000 帧(18 分钟)与反攻内部门槛 36000 不一致 →
        //     用户实测 19 分钟(28500 帧)就触发反攻，导致 armyCount 远未达 12 即提前全军出击，
        //     零散士兵+祭司被敌方集火送命。改：对齐 COUNTER_ATTACK_FORCE_TIME，
        //     给 W3~CounterAttack 之间留足集结时间(14 分 W3 开打 → 22 分反攻，整 8 分钟缓冲)。
        //   【2026-09-14】用户要求提前 2 分钟反攻(24→22)，缓冲由 10 分钟收缩到 8 分钟；
        //     兵力门槛 COUNTER_ATTACK_MIN_ARMY=12 不变——早于门槛仍会被 readyToAttack 拦住，
        //     不会出现"兵力不足强推"的旧问题(旧问题源于 27000 与内部门槛不一致)。
        if (frame > COUNTER_ATTACK_FORCE_TIME && state == DEFENSE_WAVE3) {
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
    bool inCounter = (state == COUNTERATTACK);   // ★ 反攻期：祭司须跟随大军推进，不被后方/远程威胁吸在基地

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
        // ★ 转化优先级（2026-09-12 用户连续需求：先"投石车不再最优先"，再"方阵兵为感化最优先"）：
        //   ① 方阵兵(AT_HOPLITE)最高优先——克制骑兵，转过来即我方反骑主力（挡敌方骑兵冲祭司/弓兵）。
        //   ② 其余近战(非远程)次之——贴身 2.5 格威胁祭司（祭司死=立刻失败），护驾优先。
        //   ③ 远程军队(弓/复合弓/战车弓/投石兵)第三——削输出、保祭司与箭塔。
        //   ④ 投石车降为第四——SPEED 1.63 慢、不直接威胁祭司。
        //      多同型单位选血量最高者(更耐打、转来更强)，同血取近者。
        //   ⑤ 兜底：最近敌方村民。
        // 0) 方阵兵最高优先（克制骑兵，转过来即我方反骑主力）
        int bestHopSN = -1; int bestHopBlood = -1; double bestHopDist = 1e12;
        for (auto &e : info.enemy_armies) {
            if (e.Blood <= 0) continue;
            if (e.Sort != AT_HOPLITE) continue;
            double d = calDistance(dr, ur, e.DR, e.UR);
            if (d > range) continue;
            if (e.Blood > bestHopBlood || (e.Blood == bestHopBlood && d < bestHopDist)) {
                bestHopBlood = e.Blood; bestHopSN = e.SN; bestHopDist = d;
            }
        }
        if (bestHopSN >= 0) return bestHopSN;                      // 0) 方阵兵第一优先
        // 1) 其余近战（投石车/方阵兵已排除）
        int bestSN = -1; int bestBlood = -1; double bestDist = 1e12;
        for (auto &e : info.enemy_armies) {
            if (e.Blood <= 0) continue;
            if (e.Sort == AT_STONE_THROWER) continue;            // 投石车已移到 ④
            if (e.Sort == AT_HOPLITE) continue;                 // 方阵兵已在 0) 处理
            // 近战判定：非远程（远程=弓/复合弓/战车弓/投石兵；投石车虽 DIS=10 但已在 ④ 排除）
            bool isMelee = !(e.Sort == AT_BOWMAN || e.Sort == AT_CHARIOT_ARCHER ||
                             e.Sort == AT_COMPOSITE_BOWMAN || e.Sort == AT_SLINGER);
            if (!isMelee) continue;                              // 只挑近战
            double d = calDistance(dr, ur, e.DR, e.UR);
            if (d > range) continue;
            if (e.Blood > bestBlood || (e.Blood == bestBlood && d < bestDist)) {
                bestBlood = e.Blood; bestSN = e.SN; bestDist = d;
            }
        }
        if (bestSN >= 0) return bestSN;                          // 1) 其余近战（保命）
        // 2) 远程军队（投石车/方阵兵/近战已排除）
        for (auto &e : info.enemy_armies) {
            if (e.Blood <= 0) continue;
            if (e.Sort == AT_STONE_THROWER) continue;
            if (e.Sort == AT_HOPLITE) continue;
            bool isMelee = !(e.Sort == AT_BOWMAN || e.Sort == AT_CHARIOT_ARCHER ||
                             e.Sort == AT_COMPOSITE_BOWMAN || e.Sort == AT_SLINGER);
            if (isMelee) continue;                               // 近战已在 1) 处理
            double d = calDistance(dr, ur, e.DR, e.UR);
            if (d > range) continue;
            if (e.Blood > bestBlood || (e.Blood == bestBlood && d < bestDist)) {
                bestBlood = e.Blood; bestSN = e.SN; bestDist = d;
            }
        }
        if (bestSN >= 0) return bestSN;                          // 2) 远程
        // 3) 投石车（虽远程输出强，但慢、不直接威胁祭司）
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
        if (bestCatSN >= 0) return bestCatSN;                     // 3) 投石车降为第四
        // 兜底：无敌方军队时，最近敌方村民（保留原行为）
        int bestVilSN = -1; double bestVilDist = 1e12;
        for (auto &e : info.enemy_farmers) {
            double d = calDistance(dr, ur, e.DR, e.UR);
            if (d > range) continue;
            if (d < bestVilDist) { bestVilDist = d; bestVilSN = e.SN; }
        }
        return bestVilSN;
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
        // ★★ 2026-09-13 保祭司（本轮第 1 瓶颈：祭司死亡率 43.8%）· 落点粘滞 ★★
        //   旧逻辑每 18 帧(cooldown)用【当前】威胁集合重算 baseAng(斥力合力方向)与落点；
        //   敌人一移动，合力方向就可能整体翻转 → 落点从地图一侧跳到另一侧 → 祭司 A→B→A 往返，
        //   净位移≈0，被多个远程单位围在原地打死（tw4 f=15909 / sg2 f=43165 均为此型：
        //   500 帧内落点在 (472~1138, 453~1291) 反复横跳，最后满血被 4 个敌人围殴致死）。
        //   修：上次落点【仍安全】(不在任何威胁射程+1 格内、未被占用) 且祭司【尚未抵达】(>3 格)
        //   → 直接沿用，不重算。只有落点变不安全 / 已抵达 / 卡住不动，才走下方重算换扇区。
        if (priestFleeLastFrame > -999999) {
            double dLast = calDistance(pDR, pUR, priestFleeLastX, priestFleeLastY);
            // 卡在旧落点上(IDLE 且远离)不算粘滞对象，交给下方死锁检测换扇区
            bool stuckAtLast = (priest->NowState == HUMAN_STATE_IDLE && dLast > 2.0 * BL);
            if (!stuckAtLast && dLast > 3.0 * BL) {
                bool lastSafe = true;
                for (int t = 0; t < nT; ++t)
                    if (calDistance(priestFleeLastX, priestFleeLastY, thX[t], thY[t]) < thR[t] + 1.0 * BL) { lastSafe = false; break; }
                if (lastSafe && !occupiedLanding(priestFleeLastX, priestFleeLastY)) {
                    HumanMove(priestSN, priestFleeLastX, priestFleeLastY);
                    priestMoveCooldown = 18;
                    return;   // 沿用旧落点：不再重算，杜绝方向翻转导致的原地抖动
                }
            }
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
        double pBRx = (priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0;   // ★ 必须 (double)：int32 整除会截断成 0/1
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
        double pBR = (priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0;   // ★ 必须 (double)：int32 整除会截断成 0/1
        {
            // ★ 诊断（只读，不改行为）：查"为什么治疗档从不触发"
            int nAlly = 0, nWound = 0; double nearAlly = 1e12;
            for (auto &a : info.armies) {
                if (a.SN == priestSN || a.MaxBlood <= 0 || a.Blood <= 0) continue;
                double dd = calDistance(pDR, pUR, a.DR, a.UR);
                if (dd < nearAlly) nearAlly = dd;
                double rr = (double)a.Blood / a.MaxBlood;
                if (rr < 0.9 && dd <= 25.0 * BL) nWound++;
                nAlly++;
            }
            if (frame % 100 == 0)
            DebugText(QString("Priest st=%1 hp=%2 nearE=%3 threat=%4 mode=%5 | ally=%6 wound25=%7 nearAlly=%8BL cd=%9")
                      .arg(priest->NowState).arg(pBR, 0, 'f', 2)
                      .arg(nearestE / BL, 0, 'f', 1).arg(threatDist / BL, 0, 'f', 1).arg(priestMode)
                      .arg(nAlly).arg(nWound).arg(nearAlly / BL, 0, 'f', 1).arg(priestMoveCooldown));
        }
        auto locateNearest = [&](double &ox, double &oy) {
            ox = 0; oy = 0;
            if (nearestE >= 1e11) return;
            for (auto &e : info.enemy_armies)
                if (calDistance(pDR, pUR, e.DR, e.UR) <= nearestE + 0.01) { ox = e.DR; oy = e.UR; return; }
            for (auto &e : info.enemy_farmers)
                if (calDistance(pDR, pUR, e.DR, e.UR) <= nearestE + 0.01) { ox = e.DR; oy = e.UR; return; }
        };
        // 感化检测(无安全门槛)：冷却好+视野内有可感化敌(≤20格)即可，直接感化/靠近感化。
        //   ★ 用户要求"不用安全感化，能感化直接感化"：感化绝对优先，不再要求逃出敌射程、
        //     不再看血量——冷却好了就转(贴身敌≤3时转走攻击者本身往往就是最好的保命)。
        int safeConv = -1;
        if (priest->ConvertCooldown <= 0 && nearestE <= PRIEST_CONVERT_RANGE * BL) {
            int t = findConvertTarget(pDR, pUR, PRIEST_CONVERT_RANGE * BL);
            if (t >= 0) safeConv = t;
        }
        // 1) ★ 感化无条件最高优先（用户要求：不用安全感化，能感化直接感化）：
        //    附近(≤20格)有可感化敌→直接感化或靠近感化。
        //    冷却好即转：不看血量、不要求逃出敌射程——贴身敌≤3时转走攻击者本身往往就是最好的保命；
        //    即便上帧在逃(priestMode==1)也优先转，彻底消除"该感化却只逃"的问题。
        int convSN = -1; double convDR = 0, convUR = 0;
        if (safeConv >= 0) {
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
                    DebugText(QString("Priest CONVERT(defense) SN=%1").arg(convSN));
                return;
            } else {
                double stopDist = 12.0;   // 停12格正好进入引擎感化射程(DIS_PRIEST=12)
                priestApproachMove(convDR, convUR, stopDist); return;
            }
        }
        // ==== 以下均为"无法感化"(冷却中/视野内无目标)时才轮到的保命/待命逻辑 ====
        // 2) ★ 强制撤退闸：仅【残血 pBR≤0.25】才无条件逃命。
        //   ⚠ 不可加 `nearestE <= 3*BL ||` 之类的 OR：贴脸时祭司血量往往还高，加 OR 会抢先 fled
        //     → 压制下方趋近治疗/闲时治友军两档 → 观感"祭司不满血就不治友军"。
        //     正常贴脸由下方"威胁射程+2"的 flee 闸（第4步）精细接管。
        //   ★ 治档铁律：治疗调用只能用 `HumanAction(priestSN, allySN)`
        //     （引擎 Core.cpp:1091-1096 判定祭司对同阵营人类走"治疗"而非"攻击"）。
        //     ★ 目标 SN 绝不能是祭司自身（非祭司军队自指＝自毁）。HumanBuild/Upgrade 都不是入口。
        if (pBR <= 0.25) {
            double feDR = 0, feUR = 0; locateNearest(feDR, feUR);
            priestMode = 1; priestFlee(feDR, feUR); return;
        }
        // ★ 2.5) 主动趋近治疗重伤友军（即便自身未满血，只要不在即时危险中就该去救人）
        //   【根因·再修 2026-09-08】原判据 `threatDist > nearestThreatR + 2`(逃出远程敌射程)
        //     在反攻/混战中永远不成立(祭司跟军→一直被远程射程覆盖) → 治档 100% 走不到；
        //     "满血才治"完全是视觉错觉——一旦血被削就开始无限 flee，治档永远轮不到。
        //   改：只看"是否被任意近战敌人贴身"(<4 格)，远距离交战允许治友军
        //     (治疗射程≈0.6 格，必须贴脸，远程敌对祭司威胁小)；箭塔/远程威胁由下方 flee 闸接管。
        //   【保命红线】(缺一不可)：pBR>0.25(濒死仍归顶部 canAct 闸强制逃命)
        //     + 不被近战贴身(<4 格)=不被近战追着屁股就能去救人。
        {
            bool closeQuarters = false;
            for (auto &e : info.enemy_armies)
                if (calDistance(pDR, pUR, e.DR, e.UR) < 4.0 * BL) { closeQuarters = true; break; }
            if (priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0 && pBR > 0.25 && !closeQuarters) {
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
                    // ★ 2026-09-12 修"治疗 0 次"：原禁区 4.0 格 → 伤兵几乎总在敌人身边，
                    //   任意落点都落在禁区里 → 治疗档 100% 被否掉（实测 4013 帧闸门全开却 0 次治疗）。
                    //   2.0 格 = 仍在近战贴身(≈1格)之外，但允许祭司靠近交火线上的伤兵。
                    for (auto &e : info.enemy_armies)
                        if (calDistance(x, y, e.DR, e.UR) < 2.0 * BL) return false;
                    for (auto &e : info.enemy_farmers)
                        if (calDistance(x, y, e.DR, e.UR) < 2.0 * BL) return false;
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
    }   // ★ 闭合 cpp:818 新加的外层 `{`(closeQuarters 局部作用域)
        // 3) 撤退迟滞：上帧在逃且仍处近战贴身(<4 格)或箭塔近距(<14 格)→继续逃，不切回(消除往返走)
        //   【再修 2026-09-08】与 4) 同判据：原 `threatDist <= nearestThreatR + 2` 永远成立会卡死 mode=1
        //   ★ 再修 2026-09-11：新增"治优先于逃"——若自身非濒死(pBR>0.25)、无近战贴身(<4格)、
        //     且 25 格内有可治伤兵(<90%)，则不延续逃跑，改走下方治疗档(边挨远程打边治)。
        bool meleeAdj = false;
        for (auto &e : info.enemy_armies)
            if (calDistance(pDR, pUR, e.DR, e.UR) < 4.0 * BL) { meleeAdj = true; break; }
        bool woundedNear = false;
        for (auto &a : info.armies) {
            if (a.SN == priestSN || a.MaxBlood <= 0 || a.Blood <= 0) continue;
            double r = (double)a.Blood / a.MaxBlood;
            if (r >= 0.9) continue;
            // ★ 2026-09-11 修"反攻期祭司在家箭塔附近转圈不反攻"：反攻期只认重伤(<50%)，
            //   不把基地里轻伤的后方单位当"有伤兵可治"，避免祭司滞留基地不推进
            if (inCounter && r >= 0.5) continue;
            if (calDistance(pDR, pUR, a.DR, a.UR) > 25.0 * BL) continue;
            woundedNear = true; break;
        }
        bool healOverFlee = (pBR > 0.25 && !meleeAdj && woundedNear);
        bool fleeLag = false;
        for (auto &e : info.enemy_armies)
            if (calDistance(pDR, pUR, e.DR, e.UR) < 4.0 * BL) { fleeLag = true; break; }
        if (!fleeLag)
            for (auto &b : info.enemy_buildings)
                if (b.Type == BUILDING_ARROWTOWER) {
                    double bx = (b.BlockDR + 1) * BL, by = (b.BlockUR + 1) * BL;
                    if (calDistance(pDR, pUR, bx, by) < 14.0 * BL) { fleeLag = true; break; }
                }
        // ★★ 2026-09-13 保祭司 · mustFlee 计算【提前】：下方迟滞锁复位需要用到它 ★★
        bool mustFlee = (threatDist <= nearestThreatR + 2.0 * BL);
        if (inCounter) {
            // ★★ 2026-09-13 保祭司：旧版反攻期【只有近战贴身才逃】(mustFlee = meleeAdj)，
            //   于是祭司被多个远程单位(弓/战车弓/复合弓 12 格射程)集火时完全不撤 -> 满血被秒
            //   (sg2 f=43165 被 Prof.Lu 击杀、tw3 f=24136 被 3 个远程单位围殴均属此型)。
            //   保留"不因远程威胁就缩回基地"的原意(否则祭司永远待在箭塔旁不反攻)，
            //   但增加【掉血退出】条件：已掉到 PRIEST_COUNTER_FLEE_HP 以下且仍在敌人射程内 -> 立即撤。
            double pBRc = (priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0;
            mustFlee = meleeAdj || (pBRc <= PRIEST_COUNTER_FLEE_HP && threatDist <= nearestThreatR);
        }
        // 迟滞延续：已处于撤退态且威胁仍在(近战贴身 / 箭塔 / 远程射程) → 继续逃
        if (priestMode == 1 && (fleeLag || mustFlee) && !healOverFlee) {
            double feDR = 0, feUR = 0; locateNearest(feDR, feUR);
            priestFlee(feDR, feUR); return;
        }
        // ★★ 2026-09-13 保祭司：原 `priestMode = 0;` 是【无条件】执行 → 迟滞锁形同虚设 ★★
        //   撤退中(priestMode=1)只要本帧 fleeLag 不成立(无近战贴身/无箭塔)就立刻解锁；
        //   而 mustFlee 用的是【含远程】的 threatDist ⇒ 形成逐帧交替：
        //   "flee(远程威胁) → 解锁 → 走到【待命回塔】分支 → 再 mustFlee → flee"
        //   实测 pv2 f=15611~15929：落点在固定待命点 (581.611,653.02) 与 flee 落点之间
        //   每 30 帧翻转一次，祭司原地抖动，f=15997 被 3 个远程单位打死。
        //   修：只有【真正脱离全部威胁】才解锁撤退迟滞锁。
        if (priestMode == 1 && !fleeLag && !mustFlee) priestMode = 0;
        // 4) 有威胁且无法感化(冷却中/无目标)→保命撤退
        //   ★ 再修 2026-09-11：原闸"任意敌在射程+2内→无条件逃"会压制下方治疗档，
        //     造成"祭司只有脱离威胁(和平期满血)才治友军"的观感。改为：自身非濒死+无近战贴身+
        //     25 格内有可治伤兵(<90%)时，跳过逃跑、优先治疗(边挨远程打边治)；
        //     仅"无伤兵可治 / 近战贴身 / 濒死"才真正逃命保命。
        // ★ 2026-09-11 修"反攻期祭司在家箭塔附近转圈不反攻"：反攻期祭司须跟随大军推进，
        //   不因子弹/箭塔等远程威胁就缩回基地(那会让它永远待在箭塔旁)；只在"近战贴身(<4格)"这种
        //   会瞬秒祭司的死亡威胁下才逃命(meleeAdj)，远程威胁下仍随军前进(军队已在前方提供掩护)。
        //   (mustFlee 的计算已上移至本节开头)
        if (mustFlee && !healOverFlee) {
            double feDR = 0, feUR = 0; locateNearest(feDR, feUR);
            priestMode = 1; priestFlee(feDR, feUR); return;
        }
        // ★ 闲时治疗友军：位于感化/逃跑之后、回 TC 等其它逻辑之前。本分支只治疗友军。
        //   ★ 祭司本职＝治友军：不设自身血量门槛，只要 25 格内受伤友军(<90%)即治。
        //   ★ 再修 2026-09-11：上方威胁撤退闸已改为"有伤兵且自身非濒死/无近战贴身则跳过逃跑"，
        //     故本档在交火中也可达(边挨远程打边治)；真正保命仍由 canAct 闸(pBR≤0.25 强制逃命)
        //     与"近战贴身/濒死才逃"兜底，不会让祭司带险送命。
        //   ★ 治疗铁律：必须用 `HumanAction(priestSN, allySN)`（见上文治档铁律），
        //     换成 HumanBuild/Upgrade 等任何其它动作都不触发治疗。
        //   ★ 再修 2026-09-11：放宽到 WALKING——被撤退闸打断成行走中的祭司也能立即改向去治伤兵，
        //     不必等回到 IDLE(否则交火中永远卡在"走-逃"循环、治不到)。
        if ((priest->NowState == HUMAN_STATE_IDLE || priest->NowState == HUMAN_STATE_WALKING)
            && priestMoveCooldown <= 0) {
            int bestAlly = -1; double worstRatio = 1.0; double bestAllyDist = 1e12;
            double bestAllyDR = 0, bestAllyUR = 0;
            for (auto &a : info.armies) {
                if (a.SN == priestSN) continue;      // ★ 铁律：绝不把祭司自己当治疗目标(=自毁)
                if (a.MaxBlood <= 0) continue;       // 防除零
                if (a.Blood <= 0) continue;          // 已死亡/血量为0，不治疗
                double r = (double)a.Blood / a.MaxBlood;
                if (r >= 0.9) continue;              // 仅治疗明显受伤(血<90%)友军,免为小伤跨图奔波
                // ★ 2026-09-11 修"反攻期祭司在家箭塔附近转圈不反攻"：反攻期只治重伤(<50%)前线单位，
                //   不治轻伤后方单位(否则祭司回头追后方伤兵、滞留基地)
                if (inCounter && r >= 0.5) continue;
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
                    // ★ 2026-09-12 修"治疗 0 次"：禁区由 4.0 格收到 2.0 格（同 healLandOk）。
                    for (auto &e : info.enemy_armies)
                        if (calDistance(x, y, e.DR, e.UR) < 2.0 * BL) return false;
                    for (auto &e : info.enemy_farmers)
                        if (calDistance(x, y, e.DR, e.UR) < 2.0 * BL) return false;
                    return true;
                };
                bool issued = false;
                if (bestAllyDist > 1.0 * BL) {
                    // ★ 反攻期：不回头追后方轻伤单位——治疗移动令落空，本函数结束，推进交给 manageCounterAttack
                    if (!inCounter) {
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
                    // ★ 2026-09-12 修"治疗 0 次"兜底：5 个小偏移全被否 → 不再放弃，改选
                    //   "离最近敌人最远"的那个偏移强行贴近伤兵（此处已保证 pBR>0.25，非濒死）。
                    if (!issued) {
                        int bestO = 0; double bestClear = -1e18;
                        for (int o = 0; o < 5; ++o) {
                            double cx = bestAllyDR - ux * 0.6 * BL - uy * OFF[o] * BL;
                            double cy = bestAllyUR - uy * 0.6 * BL + ux * OFF[o] * BL;
                            cx = max(0.0, min((double)MAP_L * BL, cx));
                            cy = max(0.0, min((double)MAP_U * BL, cy));
                            double clear = 1e12;
                            for (auto &e : info.enemy_armies)
                                clear = std::min(clear, calDistance(cx, cy, e.DR, e.UR));
                            for (auto &e : info.enemy_farmers)
                                clear = std::min(clear, calDistance(cx, cy, e.DR, e.UR));
                            if (clear > bestClear) { bestClear = clear; bestO = o; }
                        }
                        double cx = bestAllyDR - ux * 0.6 * BL - uy * OFF[bestO] * BL;
                        double cy = bestAllyUR - uy * 0.6 * BL + ux * OFF[bestO] * BL;
                        cx = max(0.0, min((double)MAP_L * BL, cx));
                        cy = max(0.0, min((double)MAP_U * BL, cy));
                        HumanMove(priestSN, cx, cy);
                        issued = true;
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
        // ★ 2026-09-11 修"反攻期祭司在家箭塔附近转圈不反攻"：反攻期祭司须跟随大军推进，
        //   不再回基地箭塔待命(那是和平期保命待命行为)；移动完全交给 manageCounterAttack 的推进段。
        if (inCounter) return;
        // 6) ★ 无事可做→回【己方箭塔】旁待命（祭司躲在基地的箭塔附近）。
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
            // ★★ 2026-09-13 保祭司：加 `priestMode == 0` —— 撤退中(priestMode=1)绝不能走【回塔待命】，
            //   否则与 flee 逐帧交替成原地抖动(pv2 死因)。待命是和平行为，撤退态禁止。
            if (priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0 && dAnchor > 6 * BL && priestMode == 0) {
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
    // ⚠ 本函数末尾是无条件 return：改祭司逻辑请只动上方统一决策块内，勿在其后补代码（不会执行）。
}

// ============================================================
// 经济管理（农民生产 + 建筑 + 分配 + 科技）
// ============================================================
void UsrAI::manageEconomy() {
    // 1. 村民生产：有50食物就造人，冲到目标数量
    //    ★ 铜器升级条件已满足时优先升级：暂停造村民，把TC和食物留给升级指令
    auto center = findBuilding(BUILDING_CENTER);
    //   ★ 2026-09-13：新增两条 —— ①前置建筑就绪才"攒升级费"（否则食物够也升不了，
    //     白停产、空转）；②UPGRADING 重试期同样停产，避免新村民吃掉 800 升级费。
    bool bronzeUpgradeReady = (info.civilizationStage < CIVILIZATION_BRONZEAGE && !hasUpgraded &&
                               info.Meat >= BUILDING_CENTER_UPGRADE_BRONZEAGE_FOOD &&
                               countAgeUpgradeBuildings() >= BRONZE_MIN_AGE_BUILDINGS &&
                               (state == EARLY_ECONOMY || state == DEFENSE_PREP ||
                                state == DEFENSE_WAVE1 || state == DEFENSE_WAVE2 ||
                                state == UPGRADING));
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
            builderDispatchFrame.erase(sn);
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

        // ★ 2026-09-13 建造者硬超时（总钥匙）：从本次建造令下发起，超过 BUILDER_HARD_TIMEOUT(1800帧)
        //   仍未完工、且本人当前也不在该地基上施工 → 判定该地基作废：拉黑 + 释放村民，
        //   交由 manageBuildings 另择新址重建。
        //   旧逻辑只在 IDLE 状态累计空闲(builderIdleFrame, 900帧)才超时；建造者若长期处于
        //   WALKING（地基不可达 / 被单位挡死）或被中途改派去干别的，则永远不释放
        //   ⇒ 建筑永久卡 0%、且 countBuildingsExisting 仍把它算作"已存在"、不会再发建造令
        //   ⇒ 下游建筑被引擎前置链连锁卡死（靶场←兵营、农场←市场，见 Development.cpp:727/765）。
        {
            auto dsp = builderDispatchFrame.find(sn);
            bool workingNow = (myB && f->NowState == HUMAN_STATE_WORKING && f->WorkObjectSN == myB->SN);
            // ★ 关键防误杀：只要【该地基上有任何村民正在施工】就不算超时。
            //   2026-09-13 实证：l_r90 中农场 SN=11353 被本判据误判 —— 登记建造者走了，
            //   但另一村民仍在施工（percent=91），63 帧后农场正常建完。若只看"本人是否 WORKING"
            //   就会把别的村民正在推进的进度判死。
            //   ⚠ 必须同时要求 NowState==WORKING：WorkObjectSN 会被引擎长期保留为"上次目标"，
            //     只看 SN 匹配会让本判据恒真、硬超时永不触发。
            bool anyoneWorking = false;
            if (myB)
                for (auto &g : info.farmers)
                    if (g.NowState == HUMAN_STATE_WORKING && g.WorkObjectSN == myB->SN) { anyoneWorking = true; break; }
            if (workingNow || anyoneWorking) {
                // 有人在建 → 保持登记、不超时（刻意不续期：一旦彻底无人施工立即触发兜底）
            } else if (dsp != builderDispatchFrame.end() &&
                       frame - dsp->second > BUILDER_HARD_TIMEOUT) {
                if (myB && myB->Percent < 100) {
                    // ★ 分档处置：percent==0（纯卡死，材料未投入）→ 拉黑另址重建；
                    //   percent>0（已有进度）→ 不拉黑，仅释放登记，交由孤儿抢救派人接手建完，
                    //   避免丢弃已投入的建造进度（该地基仍会被 countBuildingsExisting 计入，
                    //   不会重复建造；且 deadBuildings 清理逻辑见 percent>0 即自动复活）。
                    if (myB->Percent == 0) {
                        deadBuildings.insert(myB->SN);
                        if (!deadBuildingsFrame.count(myB->SN)) deadBuildingsFrame[myB->SN] = frame;
                    }
                    DebugText(QString("[BUILDER-HARD f=%1] 建造者SN=%2 type=%3 地基SN=%4 percent=%5 超时%6帧 → %7")
                              .arg(frame).arg(sn).arg(buildType).arg(myB->SN).arg(myB->Percent)
                              .arg(frame - dsp->second)
                              .arg(myB->Percent == 0 ? "作废另址重建" : "仅释放登记(交孤儿抢救接手)"));
                }
                releaseBuilder(sn);
                it = buildingFarmerType.erase(it);
                continue;
            }
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
            // 是否已有村民【正在施工】这个地基
            //   ★ 2026-09-13 收紧：旧版只判 `f.WorkObjectSN == b.SN`，而 WorkObjectSN 在引擎里
            //     会作为"上次工作目标"长期保留（村民早已离开/改派，字段仍指着它）
            //     ⇒ hasWorker 恒为 true ⇒ 孤儿抢救永不触发 ⇒ 地基永久卡在 0% 无人施工。
            //     现要求必须【处于 WORKING 状态且目标就是该地基】才算有人在施工。
            bool hasWorker = false;
            for (auto &f : info.farmers) {
                if (f.NowState == HUMAN_STATE_WORKING && f.WorkObjectSN == b.SN) { hasWorker = true; break; }
                // 刚下发指令、WorkObjectSN 尚未回写的同类型建造者：也算有人在管
                auto bt = buildingFarmerType.find(f.SN);
                if (bt != buildingFarmerType.end() && bt->second == b.Type && f.WorkObjectSN <= 0) {
                    hasWorker = true; break;
                }
            }
            if (hasWorker) continue;

            // ★ 2026-09-13：关键建筑允许"抽人"抢救。
            //   旧版只调 findIdleFarmer()，经济满载（所有村民都在采集/施工）时恒返回 null
            //   ⇒ 地基永久无人施工(卡 0%)，而下游建筑被引擎前置链连锁卡死
            //     （靶场←兵营 Development.cpp:727、农场←市场 :765、市场←谷仓 :635）。
            //   这里对关键建筑放宽到 findAnyFarmer()（从木/金/石采集岗抽 1 人），
            //   并用更长的节流(ORPHAN_STEAL_CD=5 秒)避免把经济抽干。
            //   ★ 农场也纳入：tryBuild 的农场硬上限把【所有】FARM 建筑都计入名额(含 0% 卡死的)，
            //     一座卡死农场会永久占用一个农场名额 ⇒ 后半段农场建不出来。
            bool crit = (b.Type == BUILDING_ARMYCAMP || b.Type == BUILDING_RANGE ||
                         b.Type == BUILDING_MARKET  || b.Type == BUILDING_GRANARY ||
                         b.Type == BUILDING_HOME    || b.Type == BUILDING_STOCK ||
                         b.Type == BUILDING_FARM);
            tagFarmer* of = findIdleFarmer();
            bool steal = false;
            if (!of && crit) { of = findAnyFarmer(); steal = true; }
            if (!of) continue;
            // 同一地基的重派节流（不 reset，避免卡住时每帧刷指令）
            auto oit = orphanBuildFrame.find(b.SN);
            int cd = steal ? ORPHAN_STEAL_CD : ORPHAN_REDISPATCH_CD;
            if (oit != orphanBuildFrame.end() && frame - oit->second < cd) continue;
            buildingFarmerType[of->SN] = b.Type;
            builderDispatchFrame[of->SN] = frame;   // ★ 硬超时起点
            HumanBuild(of->SN, b.Type, (int)b.BlockDR, (int)b.BlockUR);
            orphanBuildFrame[b.SN] = frame;
            if (frame % 60 == 0)
                DebugText(QString("[ORPHAN f=%1] 地基SN=%2 type=%3 percent=%4 补派村民SN=%5%6")
                          .arg(frame).arg(b.SN).arg(b.Type).arg(b.Percent).arg(of->SN)
                          .arg(steal ? " (抽采集岗)" : ""));
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

    // ====== ★★★ 瞪羚群中心仓库：全建筑最高优先级（2026-09-12 用户需求）★★★ ======
    //   需求原文：「在村民开始狩猎瞪羚前尽量先建仓库，仓库可以比其他建筑先建」。
    //   ① 【先建】块放在 preW1 之前 ⇒ 抢在房屋/兵营/靶场/市场/农场【之前】消耗木材
    //      （builtThisFrame 互斥锁 + 本块在最前 = 本帧只能先建仓库，其余建筑下一帧再说）；
    //   ② 【先于打猎】闸门由旧的 `!huntingGroup.empty()`（=已经在打猎）改为
    //      「TC 可猎范围内有瞪羚」⇒ 仓库在猎人出发前就落地，猎人不再空跑 TC↔猎场往返；
    //   ③ 【选群范围收敛】群中心聚类只在【距 TC ≤ GAZELLE_HUNT_RANGE】的瞪羚里选，
    //      与 manageHunting()/assignIdleFarmers()/tryAssignFood() 的猎人选取范围一致——
    //      否则会把仓库建在"全图最密但村民根本不会去打"的假群里（旧版 bug）。
    //   建的是 BUILDING_STOCK 而非谷仓：瞪羚产物 ProductSort=HUMAN_STOCKFOOD（Core.cpp:506），
    //   只能交付给仓库（Building.cpp:549）。
    //   ⚠ 即使 50 格内已有现成仓库，只要 MAX_STOCK 还有余地仍要在瞪羚中心补一座——
    //     否则猎人要空跑 50 格回老仓库交肉。
    if (!builtThisFrame && storageNearGazelleBuilt == 0 && frame < GAZELLE_STOCK_WINDOW_END &&
        houseCount >= GAZELLE_STOCK_MIN_HOUSES && info.Wood >= BUILD_STOCK_WOOD) {
        const double gBL = (double)BLOCKSIDELENGTH;
        auto gCenter = findBuilding(BUILDING_CENTER);
        double gtcDR = gCenter ? (gCenter->BlockDR + 1) * gBL : -1.0;
        double gtcUR = gCenter ? (gCenter->BlockUR + 1) * gBL : -1.0;
        if (gtcDR >= 0) {
            // 只收集【TC 可猎范围内】的存活瞪羚（与猎人选取范围同步）
            std::vector<tagResource*> gaz;
            for (auto &r : info.resources)
                if (r.Type == RESOURCE_GAZELLE && r.Cnt > 0 &&
                    calDistance(gtcDR, gtcUR, r.DR, r.UR) <= GAZELLE_HUNT_RANGE * gBL)
                    gaz.push_back(&r);
            // ★★★ 多聚类算法（2026-09-12 用户需求"如果有多处瞪羚聚集地可以多建几座仓库"）★★★
            //   6 格邻域聚类得到【所有聚类中心】几何中心，不再只取最大 1 群；
            //   按瞪羚数从多到少排序；逐个尝试建造（已有仓库覆盖的聚类跳过）。
            //   逐座建造、每帧受 builtThisFrame 互斥锁限制 ⇒ 多群仓库天然分散到多帧建造完成。
            if (!gaz.empty()) {
                struct Cluster { double dr, ur; int cnt; };
                int N = (int)gaz.size();
                // union-find：6 格连通分量
                std::vector<int> parent(N);
                for (int i = 0; i < N; ++i) parent[i] = i;
                // 两段式路径压缩（无 lambda 自调用，开销可控）
                for (int i = 0; i < N; ++i)
                    for (int j = i + 1; j < N; ++j)
                        if (calDistance(gaz[i]->DR, gaz[i]->UR, gaz[j]->DR, gaz[j]->UR) < 6 * gBL) {
                            int a = i; while (parent[a] != a) { parent[a] = parent[parent[a]]; a = parent[a]; }
                            int b = j; while (parent[b] != b) { parent[b] = parent[parent[b]]; b = parent[b]; }
                            if (a != b) parent[a] = b;
                        }
                // 二次定位 root：方便后续 sum/cnt
                std::vector<int> root(N);
                for (int i = 0; i < N; ++i) {
                    int r = i; while (parent[r] != r) r = parent[r];
                    root[i] = r;
                }
                std::map<int, std::pair<double,double>> csum;
                std::map<int, int> ccnt;
                for (int i = 0; i < N; ++i) {
                    int r = root[i];
                    csum[r].first  += gaz[i]->DR;
                    csum[r].second += gaz[i]->UR;
                    ccnt[r]++;
                }
                std::vector<Cluster> clusters;
                clusters.reserve(csum.size());
                for (auto &kv : csum) {
                    int c = ccnt[kv.first];
                    clusters.push_back({ kv.second.first / c, kv.second.second / c, c });
                }
                // 按瞪羚数从多到少排序（优先满足最缺肉的群）
                std::sort(clusters.begin(), clusters.end(),
                          [](const Cluster &a, const Cluster &b){ return a.cnt > b.cnt; });

                int existingStocks = countBuildingsExisting(BUILDING_STOCK);
                // 单帧内循环尝试建各未覆盖聚类（受 builtThisFrame / MAX_STOCK / 木 三重闸）
                for (auto &cl : clusters) {
                    if (builtThisFrame) break;
                    if (info.Wood < BUILD_STOCK_WOOD) break;
                    if (existingStocks >= MAX_STOCK) break;
                    // ★ 该聚类是否已被现成仓库（任何已有者均视为前置库存，含初始化遗留）
                    bool covered = false;
                    for (auto &b : info.buildings)
                        if (b.Type == BUILDING_STOCK && b.Percent == 100 &&
                            calDistance(cl.dr, cl.ur, (b.BlockDR + 1) * gBL, (b.BlockUR + 1) * gBL)
                                < GAZELLE_HUNT_RANGE * gBL) {
                            covered = true; break;
                        }
                    if (covered) continue;   // 已覆盖则跳过本簇、继续下一簇（多重覆盖无意义）
                    int tBlockDR = (int)(cl.dr / gBL) - 1;
                    int tBlockUR = (int)(cl.ur / gBL) - 1;
                    // 第 7 参 preferNearBuilder=true：优先派【离猎场最近】的空闲村民去建
                    if (tryBuild(BUILDING_STOCK, 3, false, tBlockDR, tBlockUR, false, true)) {
                        existingStocks++;
                        builtThisFrame = true;
                        if (frame % 60 == 0)
                            DebugText(QString("[GAZELLE-STOCK f=%1] 群中心块(%2,%3) 群内瞪羚=%4 已建仓=%5/%6 木=%7")
                                      .arg(frame).arg(tBlockDR).arg(tBlockUR).arg(cl.cnt)
                                      .arg(existingStocks).arg(MAX_STOCK).arg((int)info.Wood));
                    }
                    // tryBuild 失败（位置冲突等）→ 继续试下一簇，不能 break
                }

                // ★ storageNearGazelleBuilt 释义（解锁农场阈）：任一条件满足即置 1
                //   ① existingStocks>0（任一仓库已建好）② 已达 MAX_STOCK（4）
                //   ③ 所有近距聚类均已被覆盖 ④ 本帧无近距瞪羚（无法判定）
                if (existingStocks > 0 ||
                    countBuildingsExisting(BUILDING_STOCK) >= MAX_STOCK ||
                    clusters.empty()) {
                    storageNearGazelleBuilt = 1;
                } else {
                    bool allCovered = true;
                    for (auto &cl : clusters) {
                        bool cov = false;
                        for (auto &b : info.buildings)
                            if (b.Type == BUILDING_STOCK && b.Percent == 100 &&
                                calDistance(cl.dr, cl.ur, (b.BlockDR + 1) * gBL, (b.BlockUR + 1) * gBL)
                                    < GAZELLE_HUNT_RANGE * gBL) {
                                cov = true; break;
                            }
                        if (!cov) { allCovered = false; break; }
                    }
                    if (allCovered) storageNearGazelleBuilt = 1;
                }
            }   // ★★★ 闭合 !gaz.empty()（2026-09-12 多聚类版）
            // ★ 2026-09-13 兜底 A：TC 猎场(GAZELLE_HUNT_RANGE=50 格)内【始终没有存活瞪羚】。
            //   本局根本不会派猎人出发 ⇒ 近距仓库永远建不出 ⇒ storageNearGazelleBuilt 永远停在 0
            //   ⇒ 农场闸(cpp:1637 / 1856 两处均要求 ==1) 永久卡死，食物只能靠浆果/猎象。
            //   口径复用 gazelleDropoffReady() 的超时兜底 GAZELLE_STOCK_GATE_DEADLINE(9000 帧 = 6 游戏分)：
            //   到点仍未找到近距瞪羚就解锁农场阈，不再陪等一个不会发生的仓库。
            else if (frame >= GAZELLE_STOCK_GATE_DEADLINE) {
                storageNearGazelleBuilt = 1;
                if (frame % 300 == 0)
                    DebugText(QString("[GAZELLE-STOCK f=%1] 近场无存活瞪羚 → 兜底解锁农场阈").arg(frame));
            }
        }
    }

    // ★ 2026-09-13 兜底 B（硬保证）：建造窗口已关(11 分钟)时若仍未解锁，直接解锁。
    //   上方块整体带 `frame < GAZELLE_STOCK_WINDOW_END(16500)` 闸，窗口一过就再也不会执行；
    //   若窗口期内因木材不足 / 房屋不足等原因一次都没跑到，标志会永久停在 0 → 农场闸同样卡死。
    //   窗口关闭后本标志已无任何"等待仓库"的意义（仓库也不会再建），故无条件解锁。
    if (storageNearGazelleBuilt == 0 && frame >= GAZELLE_STOCK_WINDOW_END) {
        storageNearGazelleBuilt = 1;
        DebugText(QString("[GAZELLE-STOCK f=%1] 建造窗口已关 → 硬解锁农场阈").arg(frame));
    }

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

        // ⚠ 注：瞪羚群中心仓库已【上移】到本函数最前面（preW1 之前，全建筑最高优先级），
        //   见上方「★★★ 瞪羚群中心仓库（全建筑最高优先级）」段。原块位置（此处）已移除。

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

            // ★ 2026-09-13（根因 A）：rushMilitary 期间不再整块跳过"经济前置建筑"。
            //   旧版 rushMilitary=true 时整个 else 分支被跳过 ⇒ 谷仓/市场在整个 postW1 窗口
            //   零机会，只能等 postW2(9 分钟) 才补；而农场依赖市场(Development.cpp:765)、
            //   市场依赖谷仓(:635) ⇒ 整条食物经济链被推迟到 9 分钟后才启动。
            //   这里把「谷仓 → 市场」按最低优先级放行：排在兵营/靶场/房屋之后，
            //   仅当本帧尚无建造令(builtThisFrame==false)且木材充足时触发，不抢军事资源。
            //   同时去掉 `Meat >= 100` 前置（与 postW2 市场闸 1835 段口径对齐）——
            //   铜器期肉常被优先喂军，100 肉门槛会让市场在肉低谷反复跳空。
            bool canAffordEcon = (info.Meat >= 80 && info.Wood >= 50);
            if (!builtThisFrame && canAffordEcon &&
                countBuildingsExisting(BUILDING_MARKET) == 0 && countBuildingsExisting(BUILDING_GRANARY) == 0 &&
                info.Wood >= BUILD_GRANARY_WOOD && !DISABLE_GRANARY_BUILD) {
                builtThisFrame = tryBuild(BUILDING_GRANARY, 3);
            }
            if (!builtThisFrame && canAffordEcon &&
                countBuildingsExisting(BUILDING_MARKET) == 0 &&
                countBuildingsExisting(BUILDING_GRANARY) >= 1 && info.Wood >= 150) {
                builtThisFrame = tryBuild(BUILDING_MARKET, 3);
                if (builtThisFrame)
                    DebugText(QString("[MARKET f=%1] rushMilitary 期放行市场 wood=%2").arg(frame).arg((int)info.Wood));
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
                countBuildingsExisting(BUILDING_GRANARY) >= 1 && info.Wood >= 150) {  // 造市场
                // ★ 2026-09-13：去掉 `info.Meat >= 100` 前置（原为"已去掉所有限制条件"却仍留着肉闸）。
                //   铜器期肉常被优先喂军，100 肉门槛会让市场在肉低谷反复跳空；postW2 市场闸(1835段)
                //   本就没有肉闸，此处对齐，避免同一建筑两套门槛。
                builtThisFrame = tryBuild(BUILDING_MARKET, 3);
                if (builtThisFrame)
                    DebugText(QString("[MARKET f=%1] postW1 经济期建市场 wood=%2").arg(frame).arg((int)info.Wood));
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
            //   2026-09-13 解封（DISABLE_STABLE_BUILD=false）：建马厩只作学院前置，骑兵仍不训练。
            //   ★ 时代闸（引擎 Development.cpp:696 buildCon 要求 CIVILIZATION_TOOLAGE）：缺此闸时
            //     时代未达 → 引擎拒绝建造、countBuildingsExisting 的 90 帧防重窗口一过就归零 → 无限重试扫格。
            if (!builtThisFrame && countBuildingsExisting(BUILDING_STABLE) == 0 &&
                info.civilizationStage >= CIVILIZATION_TOOLAGE &&
                countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_STABLE_WOOD && !DISABLE_STABLE_BUILD) {
                builtThisFrame = tryBuild(BUILDING_STABLE, 3);
                if (builtThisFrame)
                    DebugText(QString("[STABLE f=%1] postW1 建马厩(学院前置) wood=%2").arg(frame).arg((int)info.Wood));
            }

            bool marketReady = (countBuildings(BUILDING_MARKET) >= 1);
// ★ 农场：市场已建 + 木材/食物够才建。
        //   2026-09-04 用户新需求："在建造瞪羚中心谷仓前不要建农场"——
        //   ★ 注：瞪羚中心实际建的是【仓库 BUILDING_STOCK】（2026-09-03 纠正：瞪羚肉 ProductSort=HUMAN_STOCKFOOD
        //     交付仓库，不是谷仓 GRANARY），故此处闸用 storageNearGazelleBuilt == 1。
        //   ★ 强制约束：仓库建好前不允许建农场——避免农民先造农场后仓库才落地，
        //     期间猎人空跑 TC↔瞪羚群（仓库未建的窗口期农场抢食物资源没意义）。
        // ★ 农场前置用地图上【任意】一座我方仓库解锁（不限 AI 自建）：地图初始已存在仓库时，
        //   1547 段会算"30格内有库存→tryBuild 跳过" → storageNearGazelleBuilt 永远停在 0 → 农场闸永远卡死。
        //   ★ 2026-09-13 加闸（用户要求"木材加工科技解锁排在建农场之前"）：见 FARM_WAIT_WOOD_TECH_FRAME 注释。
        //   ★★ 2026-09-13 再加闸（用户要求"复合弓兵科技解锁太慢"）：见 COMPOSITE_BOW_WOOD_RESERVE 宏注释。
        bool cbSkillPending = (!compositeBowResearched && !compositeBowQueued && frame < FARM_WAIT_CB_FRAME);
        int farmWoodNeed2 = FARM_WOOD_NEED(storageNearGazelleBuilt == 1)
                          + (cbSkillPending ? COMPOSITE_BOW_WOOD_RESERVE : 0);
        if (!builtThisFrame && marketReady && storageNearGazelleBuilt == 1 &&
                (marketWoodUpgraded || frame >= FARM_WAIT_WOOD_TECH_FRAME) &&
                (compositeBowResearched || compositeBowQueued || frame >= FARM_WAIT_CB_FRAME) &&
                info.Wood >= farmWoodNeed2 && info.Meat >= 100) {
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

        // ★ 第二仓库的"是否需要建"预判定：市场闸前置，避免远距瞪羚存在时市场抢 builtThisFrame 而仓库被架空
        //   （前置过严 → 每帧 tryBuild 失败 → 下一建筑接力 = 历史上"农场被饿死"同源问题）。
        //   ⚠ 时机闸必须与下方实际建造块【同步】（同为 frame > WAVE2_TIME）：靶场也是 9 分钟起、木材门槛同为 150，
        //     预判定早于建造块会变成"市场被挡、仓库也没建"的空转；晚于则靶场必然抢先落地。
        //   needSecondStock = true 当：仓库数<MAX_STOCK 且 已过 WAVE2_TIME 且
        //   远距瞪羚(距 TC>20 且 距所有现有 Stock>20)数量 >= MIN_GAZELLE_FOR_SECOND_STOCK。
        //   ★ 无瞪羚闸门：① 远距瞪羚不足 MIN_GAZELLE_FOR_SECOND_STOCK 只 → 不建、也不让位；
        //     ② gazelleAlive==0（一只存活瞪羚都没有）→ needSecondStock 恒 false，市场/靶场让位闸同步失效，
        //        否则会被一个永远建不出来的仓库饿死。
        //   ★ 木料闸门（2026-09-13 补）：本判据必须与下方【实际建造块】的木材前置同步
        //     （建造块 gate = `info.Wood >= BUILD_STOCK_WOOD + 30`，见 1727 段）。
        //     ⚠ 旧的致命不对称：needSecondStock 只看"该不该建"、不看"建不建得起"，
        //       木材落在 [BUILD_STOCK_WOOD, BUILD_STOCK_WOOD+30) 区间时判定为"让位"、
        //       而建造块却因木材不足整块跳过 ⇒ 市场被永久冻结、靶场冻结到 14 分钟。
        //       同源原则早已在 gazelleDropoffReady()(5767 段) 落地（建不起就放行猎人），此处补齐。
        //   性能：单帧扫完瞪羚即止（瞪羚≤30 / 仓库≤3 / 单帧成本 O(90)）。
        int gazelleAlive = 0;
        for (auto &r : info.resources)
            if (r.Type == RESOURCE_GAZELLE && r.Cnt > 0) gazelleAlive++;

        bool needSecondStock = false;
        if (gazelleAlive > 0 && info.Wood >= BUILD_STOCK_WOOD + 30 &&
            countBuildingsExisting(BUILDING_STOCK) < MAX_STOCK && frame > WAVE2_TIME) {
            int farGazCnt = 0;
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
                    if (!nearAnyStock) {
                        farGazCnt++;
                        if (farGazCnt >= MIN_GAZELLE_FOR_SECOND_STOCK) { needSecondStock = true; break; }
                    }
                }
            }
        }

        // ★ 2026-09-13 闸门可观测性（新增，用于实证"市场/靶场是否被让位闸饿死"）：
        //   每 300 帧打印一次让位闸全量状态。needStock=1 且 market/range 长期=0 ⇒ 就是被饿死。
        if (frame % 300 == 0)
            DebugText(QString("[GATE f=%1] needStock=%2 gazAlive=%3 stock=%4 wood=%5 | market=%6 range=%7 granary=%8 | snGB=%9")
                      .arg(frame).arg(needSecondStock ? 1 : 0).arg(gazelleAlive)
                      .arg(countBuildingsExisting(BUILDING_STOCK)).arg((int)info.Wood)
                      .arg(countBuildingsExisting(BUILDING_MARKET))
                      .arg(countBuildingsExisting(BUILDING_RANGE))
                      .arg(countBuildingsExisting(BUILDING_GRANARY))
                      .arg(storageNearGazelleBuilt));

        // ★ 第二仓库：为"距现有 Stock 均>20格的远距瞪羚群"建一座，仓库落在群中心。
        //   ⚠ 三要素缺一不可（旧版缺陷导致贴 TC 多建 3 座）：① MAX_STOCK 闸；
        //     ② 不能每帧 `if(!builtThisFrame) tryBuild(...)`（木材一回就再发令）；
        //     ③ 必须传 prefX/prefY（走默认 findBuildSite 会落 TC 附近空地）。
        //   ⚠ 时机闸须与 needSecondStock 预判定同步（同为 WAVE2_TIME），否则预判定为真时本块仍被时间闸挡住。
        //   ★ 无瞪羚闸门：① gazelleAlive==0 整块跳过；② 远距瞪羚不足 MIN_GAZELLE_FOR_SECOND_STOCK 只
        //     也跳过（不为 1 只离群瞪羚建 150 木仓库）。
        if (!builtThisFrame && gazelleAlive > 0 &&
            countBuildingsExisting(BUILDING_STOCK) < MAX_STOCK &&
            frame > WAVE2_TIME && info.Wood >= BUILD_STOCK_WOOD + 30) {
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
            // ★ 2026-09-07：数量闸——远距瞪羚不足 MIN_GAZELLE_FOR_SECOND_STOCK 只就不建
            if ((int)farGaz.size() >= MIN_GAZELLE_FOR_SECOND_STOCK) {
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

        // ★ 第二谷仓：为"TC 之外 ≥6 丛的远距浆果群"建一座，谷仓落在群中心（2026-09-07 用户需求）
        //   浆果 resourceSort = HUMAN_GRANARYFOOD → 只往【谷仓】交（StaticRes.cpp:NUM_STATICRES_Bush /
        //   Resource.cpp:get_ReturnBuildingType）。远距浆果群若没有就近谷仓，村民要抱着食物跑回 TC 附近，
        //   往返 40+ 格几乎没产出；在群边建谷仓后往返压到 20 格内，等于白捡一片食物区。
        //   前置：第一座谷仓已存在（先保证 TC 附近主食物区）+ 未达 MAX_GRANARY 上限 + 木材够 120。
        //   !needSecondStock 让位：远距瞪羚仓库优先级更高（与市场 1660 段同源），避免抢走它的 builtThisFrame。
        //   ⚠ 必须传 prefX/prefY（群中心块坐标），否则 tryBuild 会 fallback 到 findGranarySite 落回 TC 附近。
        if (!builtThisFrame && !needSecondStock && !DISABLE_GRANARY_BUILD &&
            countBuildingsExisting(BUILDING_GRANARY) >= 1 &&
            countBuildingsExisting(BUILDING_GRANARY) < MAX_GRANARY &&
            info.Wood >= BUILD_GRANARY_WOOD) {
            int clX = -1, clY = -1, clCnt = 0;
            if (findRemoteBushCluster(clX, clY, clCnt)) {
                // noFallback=true：群边放不下就本帧不建（下帧重试），绝不回退到 findGranarySite——
                // 该函数在第二座谷仓时会去选【瞪羚】密集处，而瞪羚肉交仓库，建谷仓在那纯属浪费 120 木。
                builtThisFrame = tryBuild(BUILDING_GRANARY, 3, false, clX, clY, true);
            }
        }

        // 市场
        //   ★ 2026-09-05 加前置 !needSecondStock：远距瞪羚存在 + 仓库未满时不让市场抢 builtThisFrame
        //     （修"市场先于第二仓库落地"——同源问题：前置条件严苛→目标建筑被下游接力建出）
        //   ★ 2026-09-13 改：由 `!needSecondStock`（无时间上界）→ `!(needSecondStock && frame < WAVE3_TIME)`。
        //     原因：原写法在"远距瞪羚≥2 但仓库迟迟建不出（位置冲突）"时会把市场【无限期】冻在 0%，
        //     而仓库的解禁条件（瞪羚死光 / 仓库数达 MAX_STOCK）可能整局都不成立。
        //     现在与靶场(1811 段)口径完全对齐——让位只在 14 分钟反攻期前有效，进入反攻期市场优先级反超。
        if (!builtThisFrame && !(needSecondStock && frame < WAVE3_TIME) &&
            countBuildingsExisting(BUILDING_MARKET) == 0 &&
            countBuildingsExisting(BUILDING_GRANARY) >= 1 && info.Wood >= 150) {  // 造市场（已去掉11分钟时间限制）
            builtThisFrame = tryBuild(BUILDING_MARKET, 3);
            if (builtThisFrame) DebugText(QString("[MARKET f=%1] 下令建造市场 wood=%2").arg(frame).arg((int)info.Wood));
        }

        // 兵营
        if (!builtThisFrame && upgradeStarted && countBuildingsExisting(BUILDING_ARMYCAMP) == 0 &&
            info.Wood >= BUILD_ARMYCAMP_WOOD) {
            builtThisFrame = tryBuild(BUILDING_ARMYCAMP, 3);
        }

        // 靶场（不限铜器，兵营已有即可建）
        //   ★ 2026-09-07 加前置 !(needSecondStock && frame < WAVE3_TIME)：
        //     与"市场让位第二仓库"(1627 段)同源——远距瞪羚存在 + 仓库未满时，靶场不许抢 builtThisFrame，
        //     否则第二仓库被下游接力饿死、猎人继续空跑 20+ 格。
        //     ★ 但只在 14 分钟(WAVE3_TIME)前让位：进入反攻期后靶场产能优先级反超经济，
        //       也避免"仓库位置不可建 → 靶场被永久阻塞"的死锁。
        if (!builtThisFrame && !(needSecondStock && frame < WAVE3_TIME) &&
            countBuildingsExisting(BUILDING_RANGE) == 0 &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_RANGE_WOOD) {
            builtThisFrame = tryBuild(BUILDING_RANGE, 3);
            if (builtThisFrame) DebugText(QString("[RANGE f=%1] 下令建造首座靶场 wood=%2").arg(frame).arg((int)info.Wood));
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
            if (builtThisFrame)
                DebugText(QString("[STABLE f=%1] postW2 建马厩(学院前置) wood=%2").arg(frame).arg((int)info.Wood));
        }

        // ★ 学院：后期/反攻核心近战兵种(方阵兵=强力近战)。铜器后、兵营已建、且**马厩已建**(前置)才建，
        //   与靶场并列；建好后训练块检测学院存在即自动产方阵兵，配合"爆近战"反攻。
        //   ★ 2026-09-13 用户要求"解锁学院 + 后期建造方阵兵"：
        //     ① DISABLE_COLLAGE_BUILD 已解封(false)；
        //     ② 建造时机由 `state >= COUNTERATTACK` 放宽为【后期即可】：state>=DEFENSE_WAVE3
        //        或 frame>=WAVE3_TIME(14min)。旧闸要求先进入反攻态，而反攻态门槛是全军≥12人
        //        (COUNTER_ATTACK_MIN_ARMY)，前期军队长期不足 → 学院迟迟建不出 → 方阵兵产线整条空转
        //        （这正是"方阵兵在后期完全没出现"的主因之一）。
        //     ③ 引擎侧确认（Development.cpp:803-811）：学院 BRONZEAGE + 180木、前置马厩；
        //        产方阵兵 BRONZEAGE + 60食+40金，无额外科技依赖 ⇒ 建成即可投产。
        //   ★★ 2026-09-13 实测补闸（必须）：引擎 buildCon 要求 CIVILIZATION_BRONZEAGE，
        //     缺 postBronze 闸时若铜器未升完，引擎拒绝建造而 countBuildingsExisting 的 90 帧防重窗口
        //     一过就归零 → AI 沿坐标轴逐格扫描重试（o3_r180 实证：22581~45002 帧连发 235 次，
        //     坐标 (71,11)→(71,12)→…→(73,11)），每次吞掉 builtThisFrame → 饿死 postW2 后续建造
        //     （该局农场只有 3 座）。加时代闸后时代未达即完全跳过。
        if (!builtThisFrame && countBuildingsExisting(BUILDING_COLLAGE) == 0 && !DISABLE_COLLAGE_BUILD &&
            postBronze &&
            (state >= DEFENSE_WAVE3 || frame >= WAVE3_TIME) &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 &&
            countBuildingsExisting(BUILDING_STABLE) >= 1 &&   // ★ 学院前置：必须先建好马厩
            info.Wood >= BUILD_COLLAGE_WOOD + 30) {
            builtThisFrame = tryBuild(BUILDING_COLLAGE, 3);
            if (builtThisFrame)
                DebugText(QString("[COLLAGE f=%1] 建学院(方阵兵产线) wood=%2 state=%3")
                          .arg(frame).arg((int)info.Wood).arg((int)state));
        }

        // 农场
        //   ★ 2026-09-06 用户要求「建造瞪羚的仓库前先不要建农场，预留120木头」：
        //     本块原先【完全没有】storageNearGazelleBuilt 闸，只有 Wood>=75；而本块处于 if(postW2)，
        //     postW2 自 WAVE2_TIME(13500, 9分钟) 起成立，瞪羚仓库窗口却要到 frame<16500(11分钟) 才结束
        //     ⇒ 9~11 分钟两者并存，农场抢光木材 → 瞪羚仓库永远建不出、猎人来回空跑。
        //     故补上与 1487 段一致的双重闸：瞪羚仓库已建 + 木材预留
        //     （★ 预留仅仓库【未】建成时生效，仓库已建则恢复原阈值，见 FARM_WOOD_NEED 宏注释）。
        //   ★ 2026-09-13 加闸（用户要求"木材加工科技解锁排在建农场之前"）：见 FARM_WAIT_WOOD_TECH_FRAME 注释。
        //   ★★ 2026-09-13 再加闸（用户要求"复合弓兵科技解锁太慢"）：复合弓科技未就绪时农场须再让出 100 木
        //       （见 COMPOSITE_BOW_WOOD_RESERVE 宏注释）。farmWoodTechOk 与 farmBowWoodOk 两道闸并联，
        //       任一超时兜底触发即放行，防食物崩盘。
        bool farmWoodTechOk = (marketWoodUpgraded || frame >= FARM_WAIT_WOOD_TECH_FRAME);
        bool farmBowWoodOk = (compositeBowResearched || compositeBowQueued ||
                              frame >= FARM_WAIT_CB_FRAME);
        bool cbSkillPending2 = (!compositeBowResearched && !compositeBowQueued && frame < FARM_WAIT_CB_FRAME);
        int farmWoodNeed = FARM_WOOD_NEED(storageNearGazelleBuilt == 1)
                         + (cbSkillPending2 ? COMPOSITE_BOW_WOOD_RESERVE : 0);
        if (!builtThisFrame && storageNearGazelleBuilt == 1 && farmWoodTechOk && farmBowWoodOk) {
            int currentFarms = countFarmsForCap();
            if (currentFarms < farmTarget &&
                info.Wood >= farmWoodNeed) {
                builtThisFrame = tryBuild(BUILDING_FARM, 3);
            }
        } else if (!builtThisFrame && !marketWoodUpgraded && frame < FARM_WAIT_WOOD_TECH_FRAME &&
                   storageNearGazelleBuilt == 1 && frame % 300 == 0) {
            // 诊断：农场被"等木材加工科技"挡住时的现场（每 300 帧一条）
            DebugText(QString("[FARM-TECHWAIT f=%1] 农场等木材加工科技 wood=%2 meat=%3 farms=%4/%5 mkt=%6")
                      .arg(frame).arg((int)info.Wood).arg((int)info.Meat)
                      .arg(countFarmsForCap()).arg(farmTarget).arg(countBuildings(BUILDING_MARKET)));
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
    std::map<int,int> assignedFarm;   // ★ 本帧已派往农场的 <farmSN, workerSN>，防同场重复派工导致>1人
    double BL = (double)BLOCKSIDELENGTH;
    // ★ 伐木工目标动态化（2026-09-01）：缺木(<120)时拉到 10 人抢木，常态 6 人。
    const int woodTarget = (info.Wood < WOOD_LOW_LINE) ? WOOD_TARGET_LOW : WOOD_TARGET_BASE;
    auto center = findBuilding(BUILDING_CENTER);
    double tcDR = center ? (center->BlockDR + 1) * BL : 0;
    double tcUR = center ? (center->BlockUR + 1) * BL : 0;

    // ★ 已建成谷仓(Percent==100)位置（2026-09-07）：浆果是 HUMAN_GRANARYFOOD，只往谷仓交。
    //   有了远距谷仓后，浆果派工不再受"距 TC ≤20 格"限制——改为"距 TC ≤20 格 或 距任一已建成谷仓
    //   ≤BUSH_NEAR_GRANARY_DIST(20) 格"即可派人。此处只扫一次建筑表，供下面浆果循环复用（≤2 个元素）。
    std::vector<std::pair<double,double>> builtGranaries;
    for (auto &b : info.buildings)
        if (b.Type == BUILDING_GRANARY && b.Percent == 100)
            builtGranaries.push_back({(b.BlockDR + 1.0) * BL, (b.BlockUR + 1.0) * BL});

    // 狮子防御统一由 manageLionDefense() 处理；此处只负责"跳过正在猎狮的村民"，
    // 避免刚派出去的猎手被采集分配立刻改派去砍树/挖金。
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
    // ★ 石头停采：14分钟(WAVE3_TIME)后不再采石，或存量≥STONE_CAP_STOP，或【建满 MAX_TOWERS 座箭塔后永久停采】。
    //   塔建满后石头再无用途（箭塔是唯一活的石头消耗：铜器塔升级被 DISABLE_TOWER_UPGRADE 封禁、
    //   投石兵无训练代码、维修未实现）→ 继续采石纯属浪费人力。
    //   ⚠ 判据须用 countBuildings（仅 Percent==100 的"已建成"），**不能并列 countBuildingsExisting**：
    //     countBuildingsExisting 含【地基+在建+pending 90帧兜底】，MAX_TOWERS=3 时第2座地基后
    //     就会叠加到 3（已建1+地基1+pending1）→ towersDone 提前触发 → S=0、St=0 → 第3座永远拿不到150石
    //     → 第3座建不出。改用 countBuildings 后只算"已建成的塔"，第3座实际建成时才停采。
    //     ⚠ towerCount 成员也不能用：tryBuild 成功即++、塔被摧毁不回退 → "第2座被打掉"会永久误停采。
    //   stoneStop 同时驱动「派工跳过采石」+「回撤撤走采石工」两个方向，一处改两处生效。
    const bool towersDone = (countBuildings(BUILDING_ARROWTOWER) >= MAX_TOWERS);
    const bool stoneStop = (frame >= WAVE3_TIME) || (info.Stone >= STONE_CAP_STOP) || towersDone;
    // ★ 黄金过剩判定（后期实测"黄金堆到 700+、木头食物都不够"）：
    //   ⚠ 不得给反攻期加豁免：反攻期食物才是造兵瓶颈（复合弓40食/方阵60食，食物需求≈黄金2倍），
    //   豁免会让金工无上限开采 → 食物跟不上 → 兵造不出 → 黄金只进不出。
    //   复核需求：一场反攻(20复合弓+10方阵)黄金 ≈ 800，GOLD_CAP_STOP=400 储备 + MIN_GOLD_WORKERS 持续产出够用。
    //   命中→goldTarget 压到 MIN_GOLD_WORKERS，人力转去木头+食物。判定两种过剩：
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

    // ============================================================
    // ★★★ 猎象整队（2026-09-13 用户需求：「狩猎大象必须 4 个人一起狩猎，单个村民狩猎会死」）
    //   引擎事实：大象 45 血 / 攻 10 / 不逃跑 / 掉肉 300；村民 25 血 ⇒ 单人、双人必死。
    //   旧实现是"逐帧凑人"：0 人在打时本帧先派 1 人开团，其余人随后几帧才到
    //   ⇒ 先到者在 1~3 人状态下被磨死（实测 run7：1 头象 + 2 个村民死亡）。
    //   现改为【整队一次性出击】：同一帧下发 MIN 条令 ⇒ 同时出发 ⇒ 同时抵达 ⇒ 同时开打：
    //     ① on==0：本帧空闲村民 ≥ ELEPHANT_HUNT_MIN 才一次性派 4 人；凑不齐则【一人不派】；
    //     ② 0<on<MIN（开团后战损）：本帧能补齐到 MIN 就整批补上；
    //        补不齐且 on ≤ ELEPHANT_RESCUE_MAX_ON ⇒【孤兵必救】召回该村民 + 把大象拉黑，绝不让他独自送死；
    //     ③ MIN≤on<GROUP：已成团，允许整批补位到 GROUP(5)。
    //   优先级与主循环严格一致：仅当"附近浆果/瞪羚已满员、吃不下人力"时才开新团。
    //   出击名额写入 elephantPartyPending，主循环据此跳过这些村民，防止同帧被改派去砍树/农场。
    // ============================================================
    std::set<int> elephantPartyPending;   // 本帧已编入猎象队的村民SN
    {
        std::vector<int> elePool;         // 本帧真正空闲、可编队的村民（info.farmers 下标）
        for (size_t i = 0; i < info.farmers.size(); ++i) {
            auto &g = info.farmers[i];
            if (g.FarmerSort != FARMERTYPE_FARMER) continue;
            if (g.Resource > 0) continue;                             // 手上有资源，先送回
            if (g.NowState != HUMAN_STATE_IDLE) continue;              // 只动真正空闲的
            if (waveBlockers.count(g.SN) || g.SN == scoutFarmerSN) continue;
            if (lionHunterSN.count(g.SN)) continue;
            if (buildingFarmerType.count(g.SN)) continue;
            elePool.push_back((int)i);
        }
        // 附近浆果(≤3人/丛, 30格内) 与 瞪羚(≤2人/只, 50格内) 是否都吃满人力；
        // 没吃满 ⇒ 人力优先给它们（与主循环 bush→gazelle→elephant 顺序一致），本帧不开新象团。
        bool bushGazelleFull = true;
        for (auto &r : info.resources) {
            if (r.Cnt <= 0) continue;
            if (r.Type != RESOURCE_BUSH && r.Type != RESOURCE_GAZELLE) continue;
            double lim = (r.Type == RESOURCE_BUSH) ? 30.0 : (double)GAZELLE_HUNT_RANGE;
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > lim * BL) continue;
            int on = 0;
            for (auto &o : info.farmers) if (o.WorkObjectSN == r.SN) on++;
            if (on < ((r.Type == RESOURCE_BUSH) ? 3 : 2)) { bushGazelleFull = false; break; }
        }
        // ★ 与主循环「木头→黄金→石头→食物」的优先级严格对齐（见下面主循环的派工顺序）：
        //   只有伐木/采金/采石目标人数都已吃满、且浆果瞪羚也都满员时，空闲村民才会落到"大象"这一档。
        //   否则本帧不开新团 —— 不得让猎象抢走伐木/采金/采石的人力（严格保持改动前的优先级行为）。
        bool laborFull = bushGazelleFull
                      && (woodStop  || woodWorkers  >= woodTarget)
                      && (goldWorkers >= goldTarget)
                      && (stoneStop || stoneWorkers >= STONE_WORKERS_LATE);
        // 按"到该象的距离"由近到远，同一帧一次性派出 need 人（同时下令 ⇒ 同时抵达 ⇒ 同时开打）
        auto eleDispatch = [&](tagResource* tgt, int need)->int {
            std::sort(elePool.begin(), elePool.end(), [&](int a, int b) {
                return calDistance(info.farmers[a].DR, info.farmers[a].UR, tgt->DR, tgt->UR)
                     < calDistance(info.farmers[b].DR, info.farmers[b].UR, tgt->DR, tgt->UR);
            });
            int sent = 0;
            for (size_t k = 0; k < elePool.size() && sent < need; ++k) {
                int sn = info.farmers[elePool[k]].SN;
                HumanAction(sn, tgt->SN);
                elephantPartyPending.insert(sn);
                sent++;
            }
            if (sent > 0) elePool.erase(elePool.begin(), elePool.begin() + sent);
            return sent;
        };
        for (auto &r : info.resources) {
            if (elePool.empty()) break;
            if (r.Type != RESOURCE_ELEPHANT || r.Cnt <= 0) continue;
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > 30 * BL) continue;
            auto bit = elephantBanUntil.find(r.SN);
            if (bit != elephantBanUntil.end() && frame < bit->second) continue;   // 拉黑期内不提这头象
            int on = 0;
            for (auto &o : info.farmers) if (o.WorkObjectSN == r.SN) on++;
            if (on >= ELEPHANT_HUNT_GROUP) continue;                    // 已满员(5) → 不再加人
            if (on < ELEPHANT_HUNT_MIN) {
                if (on == 0 && (foodStop || !laborFull)) continue;   // 食物过剩/人力还没被伐木采金采石浆果瞪羚吃满 → 不开新团
                int need = ELEPHANT_HUNT_MIN - on;
                if ((int)elePool.size() < need) {
                    // 本帧凑不齐 4 人 ⇒ 绝不放人过去；若已有 1~2 人在挨打，立刻救回来
                    if (on > 0 && on <= ELEPHANT_RESCUE_MAX_ON && center) {
                        std::vector<int> lone;
                        for (auto &o : info.farmers)
                            if (o.WorkObjectSN == r.SN) lone.push_back(o.SN);
                        for (size_t k = 0; k < lone.size(); ++k) HumanAction(lone[k], center->SN);
                        elephantBanUntil[r.SN] = frame + ELEPHANT_BAN_FRAMES;
                        DebugText(QString("[ELEPHANT-RESCUE f=%1] 象SN=%2 仅%3人在打(凑不齐%4人)→召回孤兵%5人,拉黑%6帧")
                                  .arg(frame).arg(r.SN).arg(on).arg(ELEPHANT_HUNT_MIN)
                                  .arg((int)lone.size()).arg(ELEPHANT_BAN_FRAMES));
                    }
                    continue;
                }
                int sent = eleDispatch(&r, need);
                DebugText(QString("[ELEPHANT-PARTY f=%1] 整队出击 象SN=%2 已在打%3人 本帧一次派%4人(同帧出发) 空闲池余%5 meat=%6 pop=%7")
                          .arg(frame).arg(r.SN).arg(on).arg(sent).arg((int)elePool.size())
                          .arg((int)info.Meat).arg((int)info.farmers.size()));
            } else {
                if (foodStop) continue;                                  // 食物过剩 → 不再补人打肉
                int need = std::min(ELEPHANT_HUNT_GROUP - on, (int)elePool.size());
                if (need <= 0) continue;
                int sent = eleDispatch(&r, need);
                DebugText(QString("[ELEPHANT-TOPUP f=%1] 已成团补位 象SN=%2 已在打%3人 补%4人 空闲池余%5")
                          .arg(frame).arg(r.SN).arg(on).arg(sent).arg((int)elePool.size()));
            }
        }
    }

    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (f.Resource > 0) continue;
        if (f.NowState != HUMAN_STATE_IDLE) continue;
        if (waveBlockers.count(f.SN) || f.SN == scoutFarmerSN) continue;
        if (elephantPartyPending.count(f.SN)) continue;   // ★ 本帧已编入猎象队，禁止同帧改派
        if (lionHunterSN.count(f.SN)) continue;   // ★ 正在猎狮，不要改派去采集

        // ★ 木头达停采上限(日常≥150 / WAVE3后≥250)则不再派新伐木工，人力优先留作食物
        if (!woodStop && woodWorkers < woodTarget) {
            auto treeFirst = findBestWoodTree(f.DR, f.UR);
            if (treeFirst) {
                HumanAction(f.SN, treeFirst->SN); villLastTreeSN[f.SN] = treeFirst->SN;
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
                if (tree) { HumanAction(f.SN, tree->SN); villLastTreeSN[f.SN] = tree->SN; woodWorkers++; continue; }
            }
            continue;  // 食物过剩：不再派食物，直接跳过（木头满则保持空闲，木头缺则已被上面派去伐木）
        }

        tagResource* bestBush = nullptr;
        double bestBushScore = 1e12;
        for (auto &r : info.resources) {
            if (r.Type != RESOURCE_BUSH || r.Cnt <= 0) continue;
            // ★ 2026-09-07 放宽：原"距 TC >20 格即跳过"会让远距浆果群(已在其旁建第二谷仓)无人采集。
            //   现在：距 TC ≤20 格 **或** 距任一【已建成】谷仓 ≤BUSH_NEAR_GRANARY_DIST(20) 格 → 可派。
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > 20 * BL) {
                bool nearGranary = false;
                for (auto &gd : builtGranaries)
                    if (calDistance(r.DR, r.UR, gd.first, gd.second) <= BUSH_NEAR_GRANARY_DIST * BL) {
                        nearGranary = true; break;
                    }
                if (!nearGranary) continue;
            }
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
        // ★ 2026-09-12「先建仓库再打猎」：交付仓库没就位就本帧不派猎人（continue 到下一资源类型/兜底），
        //   仓库块已在 manageBuildings 最前面以最高优先级抢建。
        if (bestGazelle && gazelleDropoffReady(bestGazelle)) {
            HumanAction(f.SN, bestGazelle->SN);
            assignedGazelle[bestGazelle->SN]++;
            continue;
        }

        // ★ 组队猎象已【上移】到本函数主循环之前的"猎象整队"块（2026-09-13）：
        //   旧实现在这里逐帧凑人（先派 1 人开团、其余随后到）→ 先到者单人被打死；
        //   现在统一由整队块【同一帧一次性派够 4 人】出击，此处不再单独下发，避免出现 1~3 人的散兵。

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
                    if (t) { HumanAction(w.SN, t->SN); villLastTreeSN[w.SN] = t->SN; return true; }
                }
                if (tryAssignFood(&w)) return true;
                if (!woodStop) {                          // ★ 木头达标时不把人塞回树（避免无意义重派刷屏）
                    auto t2 = findBestWoodTree(w.DR, w.UR);
                    if (t2) { HumanAction(w.SN, t2->SN); villLastTreeSN[w.SN] = t2->SN; return true; }
                }
                return false;
            };
            bool reassigned = false;
            if (foodStop && isFood) {
                // ★ 食物过剩：食物工直接转伐木（木头偏少时补木；木头满则转黄金，黄金也满才罢休）
                auto t = findBestWoodTree(f.DR, f.UR);
                if (t && !woodStop) {
                    HumanAction(f.SN, t->SN); villLastTreeSN[f.SN] = t->SN; reassigned = true;
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
                    if (tree) { HumanAction(wSN, tree->SN); villLastTreeSN[wSN] = tree->SN; woodWorkers++; }
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

    // ★ 2026-09-12「先建仓库再打猎」：交付仓库未就位 → 本帧不派猎人（仓库优先建，见 manageBuildings）。
    //   参考录像同一动作：01:35 抵达猎场 → 01:47 就地建仓库 → 02:05 仓库落成。
    if (!gazelleDropoffReady(bestGazelle)) {
        if (frame % 300 == 0)
            DebugText(QString("[GAZELLE f=%1] 暂缓打猎：等猎场仓库落地 (目标SN=%2)")
                      .arg(frame).arg(bestGazelle->SN));
        return;
    }

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
// ★ 狮子防御：狮子逼近/攻击我方单位时立刻就近派人猎杀。
//   引擎事实（Animal.cpp::isMonitorObject）：狮子只攻击【村民】与【非祭司军队】，不攻击祭司/建筑。
//   两级威胁：紧急级(已掉血且狮子≤2格 → 可打断采集/赶路强行抽人) / 预警级(≤6格 → 只派空闲村民)。
//   人力：每只狮 4 人（狮 20 血，2 人打不完会送命）；贴脸(≤4格)的空闲军队优先上。
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
    // ★★★ 2026-09-13 用户要求：【复合弓科技与护甲科技同一解锁窗口，不再互相阻塞】★★★
    //   用户观察：「复合弓兵科技解锁得太慢」——实测 8 局复合弓科技发令帧
    //   13768 / 14928 / 16954 / 17234 / 18255 / 18815 / 19212 / 20317 / 20407 / 24759，
    //   **中位数 ≈ 19000 帧（12.7 分钟）**，最晚 24759（16.5 分钟，已过 WAVE3=21000 反攻线）
    //   ⇒ 反攻期前半段靶场只能产【普通弓兵】（射程 5、无科技），正是"复合弓科技慢"的体感来源。
    //
    //   ★ 根因（不是本块的位置问题，而是【两道顺序锁】把复合弓压在了伐木科技之后）：
    //     ① 本块原在 `if (!done && ...)` 门控内，且排在【伐木科技块之后】——
    //        伐木块一旦本帧发令就 `done = true`，本块当帧被跳过；而伐木科技(120食+75木)
    //        与复合弓(180食+100木) 都要木/肉，两者在同一资源池里【串行排队】。
    //     ② 更致命的是**木材供给**：12 座农场（每座 75 木）从 f≈13500 连续建造，
    //        实测把木材长期压在 2~112 区间（k1: f=16380 wood=15 / f=20070 wood=2 /
    //        f=20970 wood=2），而复合弓科技要求 wood≥100 ⇒ 木闸成为真实瓶颈，
    //        食物反而早已满足（同期 meat 一路 208→621，远超 180）。
    //        ⇒ 本块从 f=13500 开始每 30 帧空转（[CB] 日志 232~367 行），一直等到
    //          农场铺完（f≈21078 最后一座农场）+ 木材回血，才在 f=24759 发令。
    //
    //   ★ 修复思路：**解锁类科技（复合弓 / 护甲链）不看 `done`，各发各的**——
    //     它们分属不同建筑（靶场 / 仓库），本项目既有"同帧多建筑下发"先例（tryBuild 段），
    //     且 `done` 只用于 `techCooldown` 节流目的，对"解锁类"没有必要串行。
    //     保留的闸门：`!postBronze` 铜器前置（上方已 return）/ 靶场自身 Project 忙闲 /
    //     资源成本 / 函数首的 techCooldown 与 FOOD_PAUSE_TECH_TRAIN。
    //     ⇒ 效果：靶场空闲且木肉够的那一刻立即发令，不再等伐木科技让路。
    //   ★ 与伐木科技（WOOD_TECH_ABSOLUTE_FIRST）的关系**不变**：伐木仍在其块内、仍是
    //     "铜器后第一个被检查"的科技（本块发令**不影响**伐木块——它只 `done=true` 自己）；
    //     但若本帧伐木与复合弓同时可下单，伐木会先被检查、先执行，保持用户既定优先序。
    // ==================================================================
    // ★ 引擎真实成本（Development.cpp:739-740）：只需「铜器时代 + 木材 + 食物」，**不需要黄金**，
    //   且引擎层无阔剑前置 → 旧代码的 info.Gold>=40 是伪门槛，黄金不足时复合弓永远研究不了。
    //   （构造函数签名 (civ, building, time, wood, food, stone, gold)，见 GlobalVariate.h:346）
    // --- Range: 复合弓科技（解锁类：不被 done 阻塞）---
    if (!compositeBowResearched && !compositeBowQueued) {
        auto r = findBuilding(BUILDING_RANGE);
        // ★ 复合弓科技诊断：每 30 帧打印一次闸门状态，定位"为什么不立刻升级"
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

    // ==================================================================
    // ★★★ 2026-09-12 用户要求：【伐木科技 = 解锁类科技最优先】★★★
    //   市场·木材加工（120食物+75木材 → 伐木+2 / 远程攻击距离+1）
    //   原位置在 TIER3 末尾，且被两道锁压住：
    //     ① `frame < WAVE3_TIME`(21000帧=14min) 前置锁
    //     ② `milUnlocked`(军事解锁) 锁
    //   ⇒ 最坏要 14 分钟以后、且军事科技全部研究完才轮得到它。
    //   现将判定块整体上移到【铜器后第一个被检查的科技】位置，越过上述两锁，
    //   成为全场最高优先科技。原 TIER3 处的判定块已删除（避免重复研究）。
    //   ★ 保留未破的闸门：函数首 techCooldown 节流 / FOOD_PAUSE_TECH_TRAIN(<60食物)
    //     / `if (!postBronze) return;` 铜器门槛 —— 800 食物升级费仍受保护（用户既定铁律，
    //     铜器前一粒食物都不许被科技吃掉）。
    //   ★ 硬依赖：必须先有【市场】建筑且 Project==ACT_NULL（研究中的建筑不能再接指令）。
    //     市场建造条件见 tryBuild 段（谷仓已有 + 木≥150 + 食≥100，约 4~6 分钟落地）。
    //   ★ 与复合弓(P0)的食物/木材竞争：见宏 WOOD_TECH_ABSOLUTE_FIRST。
    // ==================================================================
    if (!DISABLE_MARKET_WOOD_TECH && !done && !marketWoodUpgraded) {
        auto mw = findBuilding(BUILDING_MARKET);
        if (mw && mw->Project == ACT_NULL && info.Meat >= 120 && info.Wood >= 75) {
            bool bowPending = (!compositeBowResearched && !compositeBowQueued);
            bool okToGo = true;
            if (bowPending && !WOOD_TECH_ABSOLUTE_FIRST) {
                // 复合弓未就绪 → 要求"两项都负担得起"才允许伐木插队：
                // 食物(伐木120 + 复合弓180) 与 木材(伐木75 + 复合弓100) 都不能被伐木吃掉，
                // 否则会出现"伐木研究完，复合弓的木/食不够，反而延后"的负优化。
                okToGo = (info.Meat >= 120 + BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_FOOD) &&
                         (info.Wood >= 75 + BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_WOOD);
            }
            if (okToGo) {
                BuildingAction(mw->SN, BUILDING_MARKET_WOOD_UPGRADE);
                marketWoodUpgraded = true; done = true;
                DebugText(QString("!! TECH WoodProcessing(伐木+2) f=%1 meat=%2 wood=%3 bowPending=%4 absFirst=%5")
                    .arg(frame).arg((int)info.Meat).arg((int)info.Wood)
                    .arg(bowPending ? 1 : 0).arg(WOOD_TECH_ABSOLUTE_FIRST ? 1 : 0));
            }
        }
    }

    // ★ 伐木科技诊断（每 100 帧，只读）：定位"为何迟迟不研究" —— 市场是否就绪 / 资源差多少
    if (!marketWoodUpgraded && frame % 100 == 0) {
        auto mwd = findBuilding(BUILDING_MARKET);
        int mktProj = -9;
        if (mwd) mktProj = (int)mwd->Project;
        DebugText(QString("[WP f=%1] mkt=%2 proj=%3 meat=%4 wood=%5 bowPend=%6 abs=%7")
            .arg(frame).arg(mwd ? 1 : 0).arg(mktProj)
            .arg((int)info.Meat).arg((int)info.Wood)
            .arg((!compositeBowResearched && !compositeBowQueued) ? 1 : 0)
            .arg(WOOD_TECH_ABSOLUTE_FIRST ? 1 : 0));
    }


    // ==================================================================
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

    // --- 仓库：护甲科技链（步兵/弓兵 各两级：护甲 → 鳞甲）★ 2026-09-13 用户要求解锁 ---
    //   ① 引擎两柄机制：同一动作 ID 调两次 = 一级护甲 → 二级鳞甲；靠 `Project` 闸门天然串行
    //      （研究期间 Project != ACT_NULL ⇒ 不可能同帧连发两级，也不会重复发令）。
    //   ② 顺序（用户定案）：一级先铺满 —— 步兵护甲 → 弓兵护甲 → 步兵鳞甲 → 弓兵鳞甲。
    //   ③ 防"发令即置真"卡死（同铜器升级铁律）：发令只记 pending，下一帧看仓库是否变忙来确认
    //      引擎已受理；ARMOR_ACCEPT_TIMEOUT 帧内仓库仍空闲 ⇒ 回滚刚加的级数，下帧重试。
    //   ④ ★ 必须【锁定仓库 SN】：多仓库阵型（MAX_STOCK=4）下 `findBuilding(BUILDING_STOCK)`
    //      在不同帧可能返回不同仓库 —— 实测 2 座仓库时 Project 会在"研究中(15)/空闲(0)"
    //      之间抖动，制造大量伪"完成"边沿（run2 曾误报 144 条 [ARMOR-DONE]）。
    //      锁定后只读同一座仓库的 Project，边沿才真实。
    if (!done) {
        //   ⑤ ⚠ 完成度过滤不可省：`findBuilding` 的真实过滤是 `Percent == 100`；若按裸 Type
        //      选到【在建地基】的仓库，引擎会拒研（实测 run2/run4 因此回滚 11~12 次，
        //      直到地基完工才受理，白等 ~1450 帧）。故两处选择都要求 Percent==100。
        //   ⑥ 注意：① 锁定查找【不能】加 Percent==100 过滤 —— 研究期间该仓库的 Percent
        //      可能短暂 !=100，若加过滤会导致整块被跳过（实测 run1 [ARMOR-ACK] 因此迟了 421 帧）。
        //      过滤只用在②初始挑选（此时必须完工才能接研究令）。
        tagBuilding *armSt = nullptr;
        // ① 优先沿用已锁定的仓库（只要还存在就用它，不加完成度过滤）
        if (armorStockSN >= 0) {
            for (auto &b : info.buildings)
                if (b.Type == BUILDING_STOCK && b.SN == armorStockSN) { armSt = &b; break; }
        }
        // ② 未锁定 / 已失效（被拆）/ 未完工 → 取第一座【已完工且空闲】仓库并锁定
        if (!armSt) {
            armorStockSN = -1;   // 清掉旧锁，避免下次又选中同一座坏目标
            for (auto &b : info.buildings)
                if (b.Type == BUILDING_STOCK && b.Percent == 100 && b.Project == ACT_NULL) {
                    armSt = &b; armorStockSN = b.SN; break;
                }
        }
        if (armSt) {
            // ① 确认受理 / 超时回滚
            if (armorPendingKind != 0) {
                if (armSt->Project != ACT_NULL) {
                    DebugText(QString("[ARMOR-ACK f=%1] 链=%2 引擎已受理，开始研究(~40s)")
                        .arg(frame).arg(armorPendingKind == 1 ? "步兵" : "弓兵"));
                    armorPendingKind = 0;
                } else if (frame - armorPendingFrame > ARMOR_ACCEPT_TIMEOUT) {
                    if (armorPendingKind == 1) { if (infArmorLevel > 0) infArmorLevel--; }
                    else                       { if (arcArmorLevel > 0) arcArmorLevel--; }
                    DebugText(QString("[ARMOR-RETRY f=%1] 链=%2 引擎未受理→回滚级数 inf=%3 arc=%4 meat=%5 gold=%6")
                        .arg(frame).arg(armorPendingKind == 1 ? "步兵" : "弓兵")
                        .arg(infArmorLevel).arg(arcArmorLevel)
                        .arg((int)info.Meat).arg((int)info.Gold));
                    armorPendingKind = 0;
                    armorStockSN = -1;   // 换一座仓库重试（坏目标不重复锁）
                }
            }
            // ② 逐级下发（同一帧最多一项；仓库忙则整段跳过）
            if (armorPendingKind == 0 && armSt->Project == ACT_NULL) {
                int wantKind = 0, wantID = 0, wantLvl = 0;
                if (!DISABLE_INFANTRY_ARMOR_TECH && infArmorLevel == 0 &&
                    info.Meat >= ARMOR_INF_T1_FOOD) {
                    wantKind = 1; wantLvl = 1; wantID = BUILDING_STOCK_UPGRADE_DEFENSE_INFANTRY;
                } else if (!DISABLE_ARCHER_ARMOR_TECH && arcArmorLevel == 0 &&
                           info.Meat >= ARMOR_ARC_T1_FOOD) {
                    wantKind = 2; wantLvl = 1; wantID = BUILDING_STOCK_UPGRADE_DEFENSE_ARCHER;
                } else if (!DISABLE_INFANTRY_ARMOR_TECH && infArmorLevel == 1 &&
                           info.Meat >= ARMOR_INF_T2_FOOD && info.Gold >= ARMOR_INF_T2_GOLD) {
                    wantKind = 1; wantLvl = 2; wantID = BUILDING_STOCK_UPGRADE_DEFENSE_INFANTRY;
                } else if (!DISABLE_ARCHER_ARMOR_TECH && arcArmorLevel == 1 &&
                           info.Meat >= ARMOR_ARC_T2_FOOD && info.Gold >= ARMOR_ARC_T2_GOLD) {
                    wantKind = 2; wantLvl = 2; wantID = BUILDING_STOCK_UPGRADE_DEFENSE_ARCHER;
                }
                if (wantKind != 0) {
                    BuildingAction(armSt->SN, wantID);
                    if (wantKind == 1) infArmorLevel = wantLvl; else arcArmorLevel = wantLvl;
                    armorPendingKind = wantKind;
                    armorPendingFrame = frame;
                    done = true;
                    DebugText(QString("[ARMOR f=%1] 研发 %2%3 meat=%4 gold=%5 wood=%6")
                        .arg(frame)
                        .arg(wantKind == 1 ? "步兵" : "弓兵")
                        .arg(wantLvl == 1 ? "护甲(近战防御+2)" : "鳞甲(再+2)")
                        .arg((int)info.Meat).arg((int)info.Gold).arg((int)info.Wood));
                }
            }
            // ③ 观测：仓库科技完成边沿（验证"确实研成"）
            int curStockProj = (int)armSt->Project;
            if (prevStockProject != ACT_NULL && curStockProj == ACT_NULL) {
                DebugText(QString("[ARMOR-DONE f=%1] 上一条仓库科技完成(prevID=%2) meat=%3 gold=%4 infLvl=%5 arcLvl=%6")
                    .arg(frame).arg(prevStockProject)
                    .arg((int)info.Meat).arg((int)info.Gold)
                    .arg(infArmorLevel).arg(arcArmorLevel));
            }
            prevStockProject = curStockProj;
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
    // ★ 2026-09-12 用户要求：市场·木材加工（伐木）已【上移】到本函数铜器后第一位
    //   （见上方 "伐木科技 = 解锁类科技最优先" 段，越过 WAVE3 与 milUnlocked 两锁）。
    //   此处不再重复判定，避免二次研究/重复扣资源。

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

        // ============================================================
        // ★ 前期棍棒兵过渡：放在训练链【最前面】——4~15 分钟空窗期这是唯一自产兵力途径
        //   （复合弓被 COMPOSITE_BOW_MIN_FRAME 停产，工具时代填线/优先级2.5 又被 DISABLE_CLUBMAN_TRAIN 关掉）。
        //   ★ 只统计【存活】棍棒兵 → 战损自动补造，不会因一次团灭永久断兵。
        // ============================================================
        if (ENABLE_EARLY_CLUBMAN && !trained &&
            frame >= EARLY_CLUBMAN_START_FRAME && frame < COMPOSITE_BOW_MIN_FRAME) {
            int nClubNow = 0;
            for (auto &a : info.armies) if (a.Sort == AT_CLUBMAN) nClubNow++;
            if (nClubNow < EARLY_CLUBMAN_TARGET) {
                auto acEarly = findBuilding(BUILDING_ARMYCAMP);
                if (acEarly && acEarly->Project == ACT_NULL &&
                    info.Meat >= BUILDING_ARMYCAMP_CREATE_CLUBMAN_FOOD) {
                    BuildingAction(acEarly->SN, BUILDING_ARMYCAMP_CREATE_CLUBMAN);
                    trained = true;
                }
            }
        }

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
            // ★★ 反攻期专用编制：只产 复合弓兵(主) + 方阵兵(副) ★★
            //   必须走独立分支：优先级3"爆近战"不检查 trained，反攻期照样产棍棒/骑兵；
            //   优先级4 骑兵吃掉 80 黄金 = 4 个复合弓的黄金 → 黄金长期 <20 → 复合弓判据失败 → 退化成停产。
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
                //    b) ★ 数量比例闸：现役方阵数 < HOPLITE_RATIO_NUM/DEN × 复合弓数 + HOPLITE_RATIO_FLOOR。
                //       ★ 2026-09-13 由硬编码 (comp+4)/2（1:2）放宽为 3:4 温和档（见常量区注释），
                //         comp≤2 时结果与旧版一致 —— 开局零弓兵也先出 2 个方阵顶前排，不断肉盾。
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
                int hopLimitNow = (HOPLITE_RATIO_NUM * nCompNow) / HOPLITE_RATIO_DEN + HOPLITE_RATIO_FLOOR;
                if (colC && colC->Project == ACT_NULL &&
                    nHopNow < hopLimitNow &&
                    info.Meat >= BUILDING_COLLAGE_CREATE_HOPLITE_FOOD + BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_FOOD &&
                    info.Gold >= BUILDING_COLLAGE_CREATE_HOPLITE_GOLD + goldKeep) {
                    BuildingAction(colC->SN, BUILDING_COLLAGE_CREATE_HOPLITE);
                    trained = true;
                    DebugText(QString("[HOPLITE-ATK f=%1] 反攻期产方阵兵 现役hop=%2 comp=%3 limit=%4 meat=%5 gold=%6(kept%7)")
                              .arg(frame).arg(nHopNow).arg(nCompNow).arg(hopLimitNow)
                              .arg((int)info.Meat).arg((int)info.Gold).arg(goldKeep));
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

            // 优先级2.8：★ 2026-09-13 新增「后期方阵兵产线」（用户要求"在后期建造方阵兵"）
            //   ★ 为何与优先级3 分开：优先级3 的进入门槛是"食物溢出 MELEE_OVERFLOW_FOOD=150"，
            //     而方阵兵本身只需 60 食 —— 没有理由等到食物溢出才敢产，肉盾应当提前积攒。
            //     独立块把门槛降到 Meat >= HOPLITE_FOOD+60(=120)，让【14 分钟后】(lateGame) 即投产。
            //   ★ 沿用反攻期同款双保险（保证"复合弓为主、方阵为辅"，不抢复合弓资源）：
            //     a) 黄金预留：付完方阵后，黄金仍须够【所有空闲靶场各产一个复合弓】(方阵40金 vs 复合弓20金)；
            //     b) 数量比例闸：现役方阵 < HOPLITE_RATIO_NUM/DEN × 复合弓数 + HOPLITE_RATIO_FLOOR，
            //        ★ 2026-09-13 由 1:2 放宽为 3:4（见常量区），开局零弓兵时同样先出 2 个方阵顶前排。
            //   ★ 与优先级1(复合弓) 并行：不同建筑(靶场/学院)各产各的，共用"逐栋下发"风格不检查 trained。
            if (lateGame) {
                int idleRanges2 = 0;
                for (auto &b : info.buildings)
                    if (b.Type == BUILDING_RANGE && b.Project == ACT_NULL) idleRanges2++;
                int goldKeep2 = BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_GOLD * std::max(1, idleRanges2);
                int nComp2 = 0, nHop2 = 0;
                for (auto &a : info.armies) {
                    if (a.Sort == AT_COMPOSITE_BOWMAN)      nComp2++;
                    else if (a.Sort == AT_HOPLITE)          nHop2++;
                }
                auto colLate = findBuilding(BUILDING_COLLAGE);
                int hopLimit2 = (HOPLITE_RATIO_NUM * nComp2) / HOPLITE_RATIO_DEN + HOPLITE_RATIO_FLOOR;
                if (colLate && colLate->Project == ACT_NULL &&
                    nHop2 < hopLimit2 &&
                    info.Meat >= BUILDING_COLLAGE_CREATE_HOPLITE_FOOD + 60 &&
                    info.Gold >= BUILDING_COLLAGE_CREATE_HOPLITE_GOLD + goldKeep2) {
                    BuildingAction(colLate->SN, BUILDING_COLLAGE_CREATE_HOPLITE);
                    trained = true;
                    DebugText(QString("[HOPLITE-LATE f=%1] 后期(lateGame)产方阵兵 现役hop=%2 comp=%3 limit=%4 meat=%5 gold=%6(kept%7)")
                              .arg(frame).arg(nHop2).arg(nComp2).arg(hopLimit2)
                              .arg((int)info.Meat).arg((int)info.Gold).arg(goldKeep2));
                }
            }

            // 优先级3：后期/反攻「爆近战」——食物溢出时主攻近战兵，与弓兵混编反攻。
            //   ★ 不依赖全局 trained 闸门(否则单次只能产1弓、近战被饿死)：改为按"建筑空闲"逐栋下发，
            //     与弓兵并行产出；每下发一次置 trained=true 触发 trainCooldown，避免同帧对同建筑重复下令。
            //   - 兵营→棍棒兵(50食物,纯近战填线,无石头/黄金依赖,溢出首选)
            //   - 马厩→骑兵(70食物+80黄金;受 DISABLE_CAVALRY_TRAIN 门禁，当前不训练)
            //   ★ 2026-09-13：学院→方阵兵 已上移为独立块"优先级2.8"（门槛更低、更早投产），此处不再重复下发。
            if (lateGame && info.Meat >= MELEE_OVERFLOW_FOOD) {
                // 兵营→棍棒兵：★ 2026-09-03 用户要求"不训棍棒兵"，DISABLE_CLUBMAN_TRAIN 关掉，
                //   近战肉盾由优先级2.8 的学院方阵兵承担。
                if (!DISABLE_CLUBMAN_TRAIN) {
                    auto acMelee = findBuilding(BUILDING_ARMYCAMP);
                    if (acMelee && acMelee->Project == ACT_NULL &&
                        info.Meat >= BUILDING_ARMYCAMP_CREATE_CLUBMAN_FOOD) {
                        BuildingAction(acMelee->SN, BUILDING_ARMYCAMP_CREATE_CLUBMAN);
                        trained = true;
                    }
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
            //   ★ 2026-09-07 修（反攻期"复合弓兵在家里乱走"根因）：本分支【原本无任何距离闸】
            //     （3307 注释：为"祭司在哪就保到哪"刻意取消了 enemyNearTC 门槛），
            //     于是反攻期只要祭司 15 格内有任何一个敌人，【全图远征军】都会被 HumanAction 拉回来，
            //     清完敌再推进、又来敌再拉回 ⇒ 观感"在基地附近来回乱走"。
            //     修复：反攻期(COUNTERATTACK)加 PRIEST_GUARD_RECALL(30格) 闸——远征军交给
            //     manageCounterAttack 的推进调度，护驾只由祭司身边的就近兵力承担。
            //     ⚠ 优先级1（敌已锁祭司）不受此限——祭司死=立刻失败，铁律优先。
            if (priestThreatened) {
                bool tooFarInCounter = (state == COUNTERATTACK) &&
                    (calDistance(a.DR, a.UR, priestDR, priestUR) > PRIEST_GUARD_RECALL * BL);
                if (!tooFarInCounter && a.WorkObjectSN != priestEnemySN2) {    // 已在打它→不重发，防打断输出
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

    // 可走判定：非海(OCEAN)且不在树林/石矿/金矿内。
    // ★ 2026-09-08 简化（7e 更新说明第4条）：引擎 HumanMove 现可穿越未探索区(自动寻路)，
    //   故 MAPPATTERN_UNKNOWN 不再是障碍、不再拒绝——只有坐标本身不可达(海/林/矿)才卡住。
    // 关键：树林/石矿/金矿在引擎里都是放在 GRASS 格上的独立资源对象，地图格类型仍是 GRASS，
    //   故"已探索"≠"可走"——不额外排除这些资源，落点选到其格上→引擎无法寻路、单位卡死。
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
        if (t == MAPPATTERN_OCEAN) return false;   // 海不可走（★ 7e 未探索格可穿越，不再拒绝 UNKNOWN）
        if (forestGrid[bx][by]) return false;       // 林内不可走
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
    //   或到 COUNTER_ATTACK_FORCE_TIME(22分钟) 强制一起进攻——避免人数不足时零散冲出被敌方集火。
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
        // ★ 2026-09-07 再修（用户实测"复合弓兵还是在 TC 附近来回走"，上次已标注此处未修）：
        //   旧扫描有两个缺陷：
        //   ① **slot=4 是正后方 180°**（base+180°）→ 档位涨到 4 时航点直接指向"背离目标"方向，
        //      观感就是"往回走/朝家里走"，而且它同样满足 isPassableAt，会被优先采纳（off 顺序命中即 return）。
        //   ② **只判"格子可走"、不判"是否更接近目标"** → 可能选到绕远路的档位，越走越远。
        //   修复：① 显式跳过 slot=4(正后方)；② 优先采纳【比当前更接近目标】的档位，
        //      若 7 个档位都不更接近，才退而求其次用"任一可走点"（避免全拒后只能 BFS）。
        const double curD = calDistance(fx, fy, targetDR, targetUR);
        bool anyOk = false; double anyX = 0, anyY = 0;
        for (int off = 0; off < 8; ++off) {
            int slot = (startSlot + off) % 8;
            if (slot == 4) continue;                       // ① 禁用正后方
            double ang = base + (double)slot * (3.141592653589793 / 4.0);
            double tx = fx + std::cos(ang) * fanR * BL;
            double ty = fy + std::sin(ang) * fanR * BL;
            tx = max(0.0, min((double)MAP_L * BL, tx));
            ty = max(0.0, min((double)MAP_U * BL, ty));
            if (!isPassableAt(tx, ty)) continue;
            if (!anyOk) { anyOk = true; anyX = tx; anyY = ty; }
            // ② 更接近目标 → 立刻采用
            if (calDistance(tx, ty, targetDR, targetUR) < curD) { wx = tx; wy = ty; return true; }
        }
        if (anyOk) { wx = anyX; wy = anyY; return true; }   // 都不更接近 → 用任一可走点(仍排除正后方)
        // 8 个扇形角度全不可走 → BFS 兜底找"任何可达且离目标最近"的航点（不限定方向）
        return findDetourWaypoint(fx, fy, targetDR, targetUR, wx, wy);
    };

    // 统一推进出口：直接 HumanMove(目标坐标)，交给引擎全图寻路直奔目标（7e 起 HumanMove 可穿越
    //   未探索区全图寻路，无需再逐格摸索已探索区）；卡死(stuckTry>0)才退回 marchWaypoint 扇形脱困。
    //   ★ 2026-09-08 改（用户需求"反攻寻路不要一步步走，直接以敌方基地附近为目标点"）：
    //     去掉 `directMarch` 条件——旧版未探到敌基地时(directMarch=false)走 marchWaypoint 逐格步进，
    //     现在 7e 引擎全图寻路直达，目标点(武器厂/已探基地/对角角落猜测)一律直接 HumanMove。
    //   ★ canReissue：直奔必须节流——否则每帧重发同一(可能不可达)目标点→刷新 marchCmdFrame
    //     → canReissue 永假 → stuckTry 永不涨 → 单位卡死打转(2026-09-03 踩坑)。
    auto issueMarch = [&](double fx, double fy, int sn, int sort, int stuckTry, bool canReissue) {
        if (stuckTry <= 0 && canReissue) {
            HumanMove(sn, targetDR, targetUR);   // ★ 引擎完整寻路：直接走到目标(敌方基地附近)
            marchCmdFrame[sn] = frame;
        } else if (stuckTry <= 0) {
            // 未到节流窗口：本帧静默，不重复发指令，等 stuckNow 累积 stuckTry 触发脱困
            ;
        } else if (canReissue) {
            // ★ 2026-09-07 修：本分支原先【完全没有节流】——只要 marchWaypoint 返回 true 就每帧
            //   HumanMove。卡死(stuckTry>0)时单位原地不动 → wx,wy 每帧算出来都一样 →
            //   AI 每帧下发同一坐标的移动令（用户日志"每 4 帧 HumanMove 至 (2396.82,1973.67)"即此），
            //   既刷屏又让引擎不断重置寻路、单位永远走不出去。加上与直奔分支一致的 30 帧节流。
            double wx = 0, wy = 0;
            if (marchWaypoint(fx, fy, wx, wy, stuckTry, 5.0)) {
                HumanMove(sn, wx, wy);
                marchCmdFrame[sn] = frame;
            } else if (stuckTry > 0 && frame % 150 == 0) {
                DebugText(QString("[MARCH STUCK] army SN=%1 sort=%2 try=%3 无可用航点")
                          .arg(sn).arg(sort).arg(stuckTry));
            }
        }
        // 未到节流窗口 → 本帧静默（等 canReissue），不再重复下发
    };

    for (int pass = 0; pass < 2 && marchCmds < 8; ++pass) {
        for (auto &a : info.armies) {
            if (a.Sort == AT_PRIEST) { priest = &a; continue; }
            if (lionHunterSN.count(a.SN)) continue;   // ★ 正在猎狮，别把推进指令盖掉

            // ★ 卡死检测（独立表 marchIssue*/marchMoveFrame，绝不复用 armyIssue*）。
            //   判据＝"有没有朝推进目标靠近"(marchIssueDist)，【不是】绝对位移：原地抖动 A→B→A 每步位移
            //   都 >0.5BL，会持续刷新计时 → 永不判卡死 → 反复 HumanMove 同一坐标（用户实测日志正是此现象）。
            //   ⚠ 旧逻辑 `NowState != IDLE → continue` 有致命漏洞：领到走不到的航点会一直停在 WALKING，
            //   永不变回 IDLE → 再也收不到新指令 → 永久卡死。故必须"长时间无推进即强制重下令脱困"。
            const double curDistToTgt = calDistance(a.DR, a.UR, targetDR, targetUR);
            if (!marchIssueDist.count(a.SN)) {          // 首次见到→建立基准
                marchIssueDist[a.SN] = curDistToTgt;
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
            } else if (marchIssueDist[a.SN] - curDistToTgt > 0.5 * BL) {
                marchIssueDist[a.SN] = curDistToTgt;    // 朝目标靠近了→刷新基准
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0; // 并清卡死档，回正常寻路
            }
            // ⚠ ATTACKING(正在开火)绝不算卡死：投石车/弓兵按最大射程站桩输出时本就不位移，
            //   若计入卡死，90帧后会被拽走去移动，直接破坏投石车的 standoff 输出。
            //   这里同时刷新基准，使其停火后重新计时而非立刻被判卡死。
            if (a.NowState == HUMAN_STATE_ATTACKING) {
                marchIssueDist[a.SN] = curDistToTgt;
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
            }
            bool stuckNow = (frame - marchMoveFrame[a.SN] > 90);        // 90帧无位移→判定卡死
            bool canReissue = !marchCmdFrame.count(a.SN) ||
                              (frame - marchCmdFrame[a.SN] >= 30);      // 30帧节流，防每帧换方向抖动
            if (stuckNow && canReissue) marchStuckTry[a.SN]++;          // 升档：换个方向试
            int stuckTry = marchStuckTry[a.SN];

            // ===== ★ 高机动单位"先锋探路"（独立于集结/接战，最优先调度） =====
            //   不造侦察骑兵，改派感化的战车弓兵/骑兵探路；投石车 SPEED 极慢，不参与（会把攻城火力锁死在 TC）。
            //   ★ 7e 起引擎 HumanMove 可穿越未探索区全图寻路，旧的"4格小步贴已探索边界"机制已删除：
            //     stuckTry==0 → 直奔目标(对角角落猜测)，探到 enemy_buildings 即点亮 enemyBaseScouted → directMarch；
            //     stuckTry >0 → 目标本身不可达(海/林/矿)，退回 marchWaypoint 扇形脱困。
            if ((a.Sort == AT_CHARIOT_ARCHER || a.Sort == AT_CAVALRY) &&
                !enemyBaseScouted && enemySiegeSN == -1) {
                if (stuckTry <= 0 && canReissue) {
                    HumanMove(a.SN, targetDR, targetUR);
                    marchCmdFrame[a.SN] = frame;
                } else if (stuckTry > 0 && canReissue) {
                    double wx = 0, wy = 0;
                    if (marchWaypoint(a.DR, a.UR, wx, wy, stuckTry, 5.0)) {
                        HumanMove(a.SN, wx, wy);
                        marchCmdFrame[a.SN] = frame;
                    } else if (frame % 150 == 0) {
                        DebugText(QString("[SCOUT STUCK] SN=%1 sort=%2 try=%3 无可用航点")
                                  .arg(a.SN).arg(a.Sort).arg(stuckTry));
                    }
                }
                marchCmds++;
                continue;
            }

            // ===== ★ 远程兵"打-拉"双状态机相位优先段(2026-09-08 重写) =====
            //   必须在 continue 闸(NowState != IDLE → continue)【之前】,否则弓兵开火后变成 ATTACKING
            //   → 永远被 continue 跳过 → 相位机 60 帧触发不了,RETREAT 永不切。
            //   旧版 cpp:3952 贴脸紧急后撤段也是相类似的"高优先级优先"机制,这里合并到相位机。
            //   状态机:
            //     • SHOOT(=0)   → 在射程内攻击,持续 30 帧(≈1.2 秒@25fps)【主动】切 RETREAT ("打一下就走"——2026-09-08 用户最新指示)
            //     • RETREAT(=1) → 沿"远离敌"方向撤到敌距≥R+1.5 ("敌出射程外再射") 切回 SHOOT
            //     • 任意相位 dK≤0.5R(贴脸/紧急)→ 无条件切 RETREAT 作【终止触发】
            if (isRanged(a.Sort) && a.Sort != AT_STONE_THROWER) {
                const double R = rangedMaxRange(a.Sort);
                const double BREATH = 1.5 * BL;             // "敌出射程外"额外缓冲
                // ★【修 2026-09-08 时间换算】AoE3 7e 引擎是 25 fps(1500 帧/分钟),60 帧=2.4 秒;
                //   30 帧=1.2 秒。原注释误写"60 帧=4秒"会导致后续想"每秒/每 4 秒一拉"的调参师算错。
                //   工程铁律：frame→秒一律 ÷25。
                const int SHOOT_FRAMES = 30;               // SHOOT 相位持续 ≈1.2 秒@25fps（用户需求"打一下就走"——打一发就走，不多停留）
                const int PHASE_COOLDOWN = 20;             // 相位内不重发指令 ≈0.8 秒（让一撤走完）
                // ★【2026-09-08 用户最新】"回撤时间调长 / 攻击目标间隔扩大"→ RETREAT 阶段持续 ≥ 2.4 秒兜底
                //   （vs 原 SHOOT_FRAMES=30 帧 1.2 秒更激进——弓兵过度频繁切换，撤不到位)
                const int RETREAT_FRAMES = 60;             // RETREAT 相位兜底切回 SHOOT 时长 ≈2.4 秒@25fps（撤得更远更久）
                int phase = kitingPhase.count(a.SN) ? kitingPhase[a.SN] : 0;
                // ============ ★★★【修 2026-09-13 · 拉扯从未生效的第一性根因】★★★ ============
                //   2026-09-08 那次"修复"是错的：`phaseFrame 默认即 frame` 只保证"本帧不取到 -999999",
                //   但【从未把进入帧写回 map】→ 下一帧 count 仍为 0 → 又取 frame → **phaseAged 恒等于 0**。
                //   后果：三个"依赖 phaseAged"的相位转移全部恒不成立 ——
                //     • 4733 敌近提前撤(需 phaseAged>=6)  ✗
                //     • 4742 SHOOT 满 30 帧切 RETREAT(需 phaseAged>=30)  ✗ ← 【主症状】
                //     • 4753 RETREAT 兜底 60 帧(需 phaseAged>=60)  ✗
                //   于是弓兵一旦进入射程就【永远停在 SHOOT 站桩输出、一次 HumanMove 都不发】,
                //   只有当敌人贴到 0.5R(=3.5 格)时,由 4725 那条【无 phaseAged 条件】的终止触发
                //   强制写一次 map,phaseAged 才"复活",撤退才开始 —— 这正是用户观察到的
                //   「反攻时从没见复合弓成功拉扯过」。实测铁证(AIText.log)：
                //     复合弓 91658 在 f=37051~37521 连续 470 帧内 0 次 HumanMove、全程开火;
                //     同场 91654/91674 的 HumanMove 落点每 30 帧单调变化(=真的在走) —— 差别只在
                //     它们曾跌到 0.5R 以内被强制"点火"过。
                //   ✅ 正解:首次进入即把进入帧写回 map,此后 phaseAged 正常累加,
                //     "射 30 帧 → 撤 60 帧 → 再射"的 kiting 循环才真正启动。
                if (!kitingPhase.count(a.SN)) kitingPhase[a.SN] = 0;
                if (!kitingPhaseFrame.count(a.SN)) kitingPhaseFrame[a.SN] = frame;
                phase = kitingPhase[a.SN];
                int phaseFrame = kitingPhaseFrame[a.SN];
                int phaseAged = frame - phaseFrame;
                int kEnemy = findNearestEnemyNoStone(a.DR, a.UR, 20 * BL);
                double kEX = 0, kEY = 0; bool kGot = false;
                bool kMelee = false;
                if (kEnemy >= 0) {
                    for (auto &e : info.enemy_armies) if (e.SN == kEnemy) {
                        kEX = e.DR; kEY = e.UR; kMelee = isMeleeSort(e.Sort); kGot = true; break;
                    }
                    if (!kGot)
                        for (auto &e : info.enemy_farmers) if (e.SN == kEnemy) { kEX = e.DR; kEY = e.UR; kGot = true; break; }
                }
                // ★【修 2026-09-08】投石车兜底：findNearestEnemyNoStone 写死了 continue 投石车,
                //   当射程内"只有投石车"时 kGot=false → dK=1e12 → 全部相位转移不触发 → 走 issueMarch
                //   推进而不是攻击。改为：noStone 找不到时,在 R+1.5 格内找最近的投石车补位攻击,
                //   （投石车射程 10, 复合弓 7 → 我方能在 0.85R 边到 7 格内安全打到,但会被反击）。
                //   ⚠ 祭司不在场时复合弓打投石车是合理的——有祭司则祭司优先感化（这里不影响,
                //     投石车的 HumanAction 优先级与 managePriest 解耦,只要发动就生效）。
                if (!kGot) {
                    double bestSD = 1e12; int bestSSN = -1; double bestSEx = 0, bestSEy = 0;
                    for (auto &e : info.enemy_armies) {
                        if (e.Sort != AT_STONE_THROWER) continue;
                        double dd = calDistance(a.DR, a.UR, e.DR, e.UR);
                        if (dd < bestSD) { bestSD = dd; bestSSN = e.SN; bestSEx = e.DR; bestSEy = e.UR; }
                    }
                    // 找投石车 + 在 R+1.5 内（稍大些允许打一下就撤）
                    if (bestSSN >= 0 && bestSD <= R + 1.5 * BL) {
                        kEnemy = bestSSN;
                        kEX = bestSEx; kEY = bestSEy;
                        kMelee = false;   // 投石车当作远程处理
                        kGot = true;
                    }
                }
                double dK = kGot ? calDistance(a.DR, a.UR, kEX, kEY) : 1e12;

                // —— 终止触发(无条件、无节流):从 SHOOT 贴身<0.5R 立即切 RETREAT ——
                // ★【修 2026-09-13】加 `phase != 1` 守卫。原实现每帧都执行 => kitingPhaseFrame 被
                //   反复重置为当前帧 => 贴身对峙期间 phaseAged 恒 0 => 4753 的 RETREAT 60 帧兜底
                //   永不触发 => 相位被永久钉死在 1(弓兵一直撤、不再输出)。只在"从 0 切 1"时重置一次。
                if (kGot && dK <= 0.5 * R && phase != 1) {
                    phase = 1; kitingPhase[a.SN] = 1; kitingPhaseFrame[a.SN] = frame;
                    phaseFrame = frame; phaseAged = 0;
                }
                // ★【2026-09-12 新增：敌近提前撤】SHOOT 相位内若敌已逼近到 0.9R(=复合弓 6.3 格)内,
                //   不必等满 30 帧——远程敌可能 0.5 秒就贴到 5 格,30 帧够吃两箭。立即切 RETREAT。
                //   这是用户最新确认方案：「打满 30 帧 OR 敌近立即撤」双触发。
                //   ⚠ 只在 phase=0(SHOOT)内触发,RETREAT 段本身不会重复触发此分支(已切出去)。
                if (phase == 0 && kGot && dK > 0.5 * R && dK <= 0.9 * R && phaseAged >= 6) {
                    // phaseAged>=6 帧≈0.24 秒最小驻留,避免刚切进 SHOOT 立刻因敌近距离又撤回去,
                    // 造成"反复横跳"震荡(每帧切相位,实际伤害 0)。
                    phase = 1; kitingPhase[a.SN] = 1; kitingPhaseFrame[a.SN] = frame;
                    phaseFrame = frame; phaseAged = 0;
                }
                bool coolPhase = (frame - phaseFrame >= PHASE_COOLDOWN);
                // —— 状态转移 ——
                //   SHOOT 持续 ≥ 30 帧(≈1.2 秒@25fps)主动切 RETREAT("打一下→往回走"触发):命中用户原话"打一下就走"
                if (phase == 0 && kGot && phaseAged >= SHOOT_FRAMES) {
                    phase = 1; kitingPhase[a.SN] = 1; kitingPhaseFrame[a.SN] = frame;
                    phaseFrame = frame; phaseAged = 0;
                }
                //   RETREAT 阶段退出条件【双路径】(命中用户原话"直到敌出射程外再攻击"):
                //     ① 优选:敌距 ≥ R+BREATH(=1.5 格,即"敌出射程外")——正常情况
                //     ② 兜底:RETREAT 持续 ≥ 60 帧(≈2.4 秒,RETREAT_FRAMES)也强制切回——敌追着我(撤也撤不到 d≥R+BREATH)时不至于永远 RETREAT
                //   没敌/在 RETREAT 阶段:走下方推进 (issueMarch)
                if (phase == 1 && kGot && dK >= R + BREATH) {
                    phase = 0; kitingPhase[a.SN] = 0; kitingPhaseFrame[a.SN] = frame;
                    phaseFrame = frame; phaseAged = 0;
                } else if (phase == 1 && phaseAged >= RETREAT_FRAMES) {
                    // ⚠ RETREAT 兜底:用"相位节流"的上限做兜底,避免敌追近时永远 RETREAT 触发不到 dK 检查。
                    //   RETREAT_FRAMES=60 帧(≈2.4 秒)挡一手——撤令已发,2.4 秒后再允许切回去给"再射"机会。
                    //   即使落入此分支:本帧也只切相位,真正撤/射判断在下一相位段(节流让一射走完)。
                    if (coolPhase) {
                        phase = 0; kitingPhase[a.SN] = 0; kitingPhaseFrame[a.SN] = frame;
                        phaseFrame = frame; phaseAged = 0;
                    }
                }

                if (phase == 1 && kGot && canReissue) {
                    // —— RETREAT 阶段:沿"远离敌"方向撤,落点 = 敌 + KITING_RETREAT_MULT*R × unitVector ——
                    // ★【修 2026-09-11】原 0.85(远程敌)/1.1(近战敌) < 1 → 撤退落点落在【自身射程 R 之内】,
                    //   且当单位在射程边缘(dK≈R)开火时,撤到 0.85R 反而【更靠近】敌人;落点 < R+BREATH(复合弓=8.5格)
                    //   → 退出条件 dK>=R+BREATH 永远无法满足 → 单位退不出 RETREAT、永远在射程内被贴脸打,
                    //   观感"拉扯不成功/不往后走"。改为 >1:落点 = 1.4R(远程敌)/1.5R(近战敌) 均 > R+BREATH,
                    //   单位真正向后拉开到【射程外】,触发退出条件→回 SHOOT→重新接敌 = 标准 kiting。
                    //   节流改用 canReissue(30帧march)而非 coolPhase(phase内20帧):撤退【当帧即发令】,拉扯更跟手。
                    // ★【2026-09-12 新增 fallback 链】旧版 5 个角度都不可走就 kitMoved=0 退出 → 实测 b_r90 KIT-R 8 次全 0:
                    //   复合弓被压在地图边角/林缘时,"远离敌"方向可能撞海/林,整段 RETREAT 落空 → 单位永远站桩被打。
                    //   新增二级 fallback:朝己方 TC 方向撤(更安全的方向,TC 永远在已探索且空旷)。
                    //   三级 fallback:朝己方祭司方向撤(若祭司在场,与大军同向)。
                    //   终极兜底:全失败则本帧不下令(下一帧再试),不让单位往海里走。
                    const double KITING_RETREAT_MULT = kMelee ? 1.5 : 1.4;
                    double ux = (a.DR - kEX) / (dK + 1e-6), uy = (a.UR - kEY) / (dK + 1e-6);
                    const double angs[5] = {0.0, 0.6, -0.6, 1.2, -1.2};
                    const double angsT[5] = {0.0, 0.5, -0.5, 1.0, -1.0};  // TC fallback 用更窄角度(TC 必存在,角度越准越好)
                    bool kitMoved = false;
                    double kitX = 0, kitY = 0;
                    int kitStage = 0;  // 1=远离敌 2=朝TC 3=朝祭司 0=失败
                    // ★【修 2026-09-13】撤退有效性校验（"点可走 ≠ 路径可达"）：
                    //   isPassableAt 只判【落点所在格】(非海/非林)，不判【单位→落点的路径】。
                    //   反攻期弓兵多在敌方基地附近，落点本身可走却常被海/林/建筑隔断 →
                    //   HumanMove 被引擎静默丢弃 → 弓兵原地站桩挨打。
                    //   度量用"与最近敌的距离 dK"：本窗口若未比上一窗口拉开 ≥0.3 格，判该方向撤不动。
                    //   ⚠ 不用"单位是否有位移"：引擎的攻击令同样驱动位移，会把"撤不动"误判成"在撤"
                    //     （实测 run1：20 次撤退令全被引擎丢弃 MM_move=0、dK 4.6→0.7，位移判据却始终清零）。
                    //   连续撤不动 → 累计 stuck → 下一轮跳过第 1 档，直接朝己方 TC 撤（路径必然可达）。
                    if (kitingRetPrevDK.count(a.SN)) {
                        if (dK < kitingRetPrevDK[a.SN] + 0.3 * BL)
                            kitingRetStuck[a.SN] = (kitingRetStuck.count(a.SN) ? kitingRetStuck[a.SN] : 0) + 1;
                        else
                            kitingRetStuck[a.SN] = 0;                 // 确实拉开了 → 复位
                    }
                    kitingRetPrevDK[a.SN] = dK;
                    bool skipAwayStage = (kitingRetStuck.count(a.SN) && kitingRetStuck[a.SN] > 0);
                    // —— 第 1 档:沿"远离敌"方向撤（上一轮撤不动则跳过，改走第 2 档） ——
                    for (int ai = 0; ai < 5 && !kitMoved && !skipAwayStage; ++ai) {
                        double ca = std::cos(angs[ai]), sa = std::sin(angs[ai]);
                        double rx = kEX + (ux*ca - uy*sa) * R * KITING_RETREAT_MULT;
                        double ry = kEY + (uy*ca + ux*sa) * R * KITING_RETREAT_MULT;
                        rx = max(0.0, min((double)MAP_L * BL, rx));
                        ry = max(0.0, min((double)MAP_U * BL, ry));
                        if (isPassableAt(rx, ry)) {
                            HumanMove(a.SN, rx, ry);
                            marchCmdFrame[a.SN] = frame;
                            lastRetreatFrame[a.SN] = frame;
                            marchIssueDist[a.SN] = calDistance(a.DR, a.UR, targetDR, targetUR);
                            marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
                            kitMoved = true; kitStage = 1; kitX = rx; kitY = ry;
                        }
                    }
                    // —— 第 2 档:朝己方 TC 方向撤 12 格(TC 必在已探索空旷区,几乎总可走) ——
                    if (!kitMoved) {
                        double tcUX = rallyCtrDR - a.DR, tcUY = rallyCtrUR - a.UR;
                        double tcLen = std::sqrt(tcUX*tcUX + tcUY*tcUY);
                        if (tcLen > 1e-6) {
                            tcUX /= tcLen; tcUY /= tcLen;
                            const double TC_STEP = 12.0 * BL;
                            for (int ai = 0; ai < 5 && !kitMoved; ++ai) {
                                double ca = std::cos(angsT[ai]), sa = std::sin(angsT[ai]);
                                double rx = a.DR + (tcUX*ca - tcUY*sa) * TC_STEP;
                                double ry = a.UR + (tcUY*ca + tcUX*sa) * TC_STEP;
                                rx = max(0.0, min((double)MAP_L * BL, rx));
                                ry = max(0.0, min((double)MAP_U * BL, ry));
                                if (isPassableAt(rx, ry)) {
                                    HumanMove(a.SN, rx, ry);
                                    marchCmdFrame[a.SN] = frame;
                                    lastRetreatFrame[a.SN] = frame;
                                    marchIssueDist[a.SN] = calDistance(a.DR, a.UR, targetDR, targetUR);
                                    marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
                                    kitMoved = true; kitStage = 2; kitX = rx; kitY = ry;
                                }
                            }
                        }
                    }
                    // —— 第 3 档:朝己方祭司方向撤 6 格(若祭司在视野内) ——
                    if (!kitMoved && priest && calDistance(a.DR, a.UR, priest->DR, priest->UR) < 20 * BL) {
                        double prUX = priest->DR - a.DR, prUY = priest->UR - a.UR;
                        double prLen = std::sqrt(prUX*prUX + prUY*prUY);
                        if (prLen > 1e-6) {
                            prUX /= prLen; prUY /= prLen;
                            const double PR_STEP = 6.0 * BL;
                            for (int ai = 0; ai < 3 && !kitMoved; ++ai) {  // 3 个角度足够(祭司附近通常没障碍)
                                double ca = std::cos(angsT[ai]), sa = std::sin(angsT[ai]);
                                double rx = a.DR + (prUX*ca - prUY*sa) * PR_STEP;
                                double ry = a.UR + (prUY*ca + prUX*sa) * PR_STEP;
                                rx = max(0.0, min((double)MAP_L * BL, rx));
                                ry = max(0.0, min((double)MAP_U * BL, ry));
                                if (isPassableAt(rx, ry)) {
                                    HumanMove(a.SN, rx, ry);
                                    marchCmdFrame[a.SN] = frame;
                                    lastRetreatFrame[a.SN] = frame;
                                    marchIssueDist[a.SN] = calDistance(a.DR, a.UR, targetDR, targetUR);
                                    marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
                                    kitMoved = true; kitStage = 3; kitX = rx; kitY = ry;
                                }
                            }
                        }
                    }
                    // —— 终极兜底:三档全失败 → 本帧不下令,让相位机下一帧再试,不让单位往海里走 ——
                    // ★【2026-09-13 观测增强】原 `frame % 50 == 0` 采样率仅 1/50，反攻期常整段漏掉
                    //   RETREAT 窗口 → 无法判断"拉扯到底有没有拉开距离"。改为每次进入撤退窗口必打；
                    //   该块已被 canReissue(30 帧节流)限制，每弓兵每 30 帧最多一条，不会刷屏。
                    //   字段含 aged(相位已持续帧数)/stuck/self/tgt，可直接验证 phaseAged 是否恢复累加。
                    if (true)
                        DebugText(QString("[KIT-R f=%1] SN=%2 dK=%3 R=%4 stage=%5 stuck=%6 aged=%7 self=(%8,%9) tgt=(%10,%11)")
                                  .arg(frame).arg(a.SN).arg(dK / BL, 0, 'f', 1).arg(R / BL, 0, 'f', 1)
                                  .arg(kitStage).arg(kitingRetStuck.count(a.SN) ? kitingRetStuck[a.SN] : 0)
                                  .arg(phaseAged)
                                  .arg(a.DR / BL, 0, 'f', 1).arg(a.UR / BL, 0, 'f', 1)
                                  .arg(kitX / BL, 0, 'f', 1).arg(kitY / BL, 0, 'f', 1));
                    marchCmds++;
                    continue;   // RETREAT 段不落站桩/推进
                }

                if (phase == 0 && kGot && dK <= R) {
                    // —— SHOOT 阶段射程内攻击(撤完保护期 60 帧内不重发,符合用户"攻击目标间隔扩大"指示) ——
                    const int RETREAT_PROTECT_FRAMES = 60;   // ★ 60 帧 ≈2.4 秒(原 30 帧=1.2 秒)——撤完等久一点再开火
                    bool retreatProt = lastRetreatFrame.count(a.SN) &&
                                       (frame - lastRetreatFrame[a.SN] < RETREAT_PROTECT_FRAMES);
                    if (!retreatProt && a.WorkObjectSN != kEnemy) {
                        HumanAction(a.SN, kEnemy);            // 射程内→攻击,引擎不再逼近
                    }
                    if (frame % 100 == 0)
                        DebugText(QString("[KIT-S f=%1] SN=%2 phaseAged=%3 dK=%4 R=%5")
                                  .arg(frame).arg(a.SN).arg(phaseAged).arg(dK / BL, 0, 'f', 1).arg(R / BL, 0, 'f', 1));
                    marchCmds++;
                    continue;   // 射程内→站桩射,不落下方推进
                }
                // 射程外 / 无敌 / SHOOT 但脱战:落入下方常规推进段
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
            //   ★ 2026-09-07 修：原实现让【所有】单位 HumanMove 到同一个 rallyCtr(TC 中心) 点——
            //     实测日志铁证：复合弓 91456/91457/91458、方阵兵 91052、投石车 91077
            //     **全部** HumanMove 至同一坐标 (751.319,2754.84)。多单位抢同一点会互相挤占、
            //     引擎寻路反复失败 → 原地抖动/绕圈 → 观感"在 TC 附近来回走"。
            //   新实现：每个单位的目标点 = TC 中心 + 朝【该单位自己】方向外推 12 格，
            //     并按 SN 再做 ±0.36rad 扇形散开 ⇒ 目标点互不相同，到位即停（距离不再 >12 格）。
            if (!readyToAttack) {
                if (calDistance(a.DR, a.UR, rallyCtrDR, rallyCtrUR) > 12 * BL && canReissue) {
                    double ux = a.DR - rallyCtrDR, uy = a.UR - rallyCtrUR;
                    double baseAng = (std::sqrt(ux*ux + uy*uy) > 1e-6) ? std::atan2(uy, ux) : 0.0;
                    bool moved = false;
                    double angTries[3] = {0.0, 0.25, -0.25};          // 主方向 + 两侧微调，防落点被占
                    for (int ti = 0; ti < 3 && !moved; ++ti) {
                        double ang = baseAng + ((a.SN % 7) - 3) * 0.12 + angTries[ti];  // SN 散开 + 微调
                        double gx = rallyCtrDR + std::cos(ang) * 12 * BL;
                        double gy = rallyCtrUR + std::sin(ang) * 12 * BL;
                        gx = max(0.0, min((double)MAP_L * BL, gx));
                        gy = max(0.0, min((double)MAP_U * BL, gy));
                        if (isPassableAt(gx, gy)) {
                            HumanMove(a.SN, gx, gy);
                            marchCmdFrame[a.SN] = frame;
                            moved = true;
                        }
                    }
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
                            if (!moved && atkSN >= 0 && a.WorkObjectSN != atkSN) HumanAction(a.SN, atkSN);   // 退路全挡→原地攻击(去重防刷屏)
                        }
                        marchCmds++;
                        continue;
                    }
                }
                if (atkSN >= 0) {
                    // ★ 攻击令去重（2026-09-08）：只在 WorkObjectSN != atkSN 时下发，
                    //   否则每帧重发同一目标（箭塔/敌投石车不变时 atkSN 恒同）→ 日志刷屏
                    //   "HumanAction:投石车 ... 设置攻击目标为 箭塔 ..."（用户实测 24:24 每 4 帧刷一次）。
                    if (a.WorkObjectSN != atkSN) HumanAction(a.SN, atkSN);   // 已在射程内→原地攻击不前进(引擎不再逼近)
                } else if (ARMY_IGNORE_SIEGE_WORKSHOP ? false
                                                      : (siege && calDistance(a.DR, a.UR, targetDR, targetUR) <= CAT_RANGE)) {
                    if (a.WorkObjectSN != siege->SN) HumanAction(a.SN, siege->SN);   // 武器厂进入最大射程→轰炸(不贴近，去重防刷屏)
                } else if (stuckTry <= 0 && canReissue) {
                    // ★ 直接引擎全图寻路直奔目标（7e 起 HumanMove 可穿越未探索区，不再逐格摸索）。
                    //   ⚠ 必须带 canReissue 节流：否则每帧重发 HumanMove 到同一(可能不可达的)目标点
                    //   → 刷新 marchCmdFrame → canReissue 永假 → stuckTry 永不涨 → 投石车卡死打转
                    //   (2026-09-03 踩坑)。加节流后，无位移 90 帧 stuckNow 触发 stuckTry 上涨
                    //   → 落下方 marchWaypoint 扇形脱困。
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

            // ★ 远程兵推进 / 拆基地（cpp:3952 之前已重写为"打-拉"双状态机,本段只承接相位机没管的"射程外"流程）：
            //   双状态机未触发(射程外/无敌)→走 issueMarch 推进;到敌基地附近→拆建筑。
            //   ★ 拆建筑攻击令去重(2026-09-06)：已在打这建筑就别重发,否则每帧 HumanAction 打断上方的拉扯 HumanMove,
            //     远程兵永远走不到该到位的站位。
            if (ranged) {
                // ★ 2026-09-13「士兵攻击箭塔 → 选距离自己最近的箭塔」：
                //   先查【最近敌方箭塔】(TOWER_TARGET_RANGE 格内)。命中则打塔，且【优先于武器厂/任意敌建筑】——
                //   旧逻辑里武器厂(siege)必然覆盖一切，更近的房屋/农场也会顶掉箭塔 ⇒ 挨塔射不还手。
                //   仍保留去重：已在打这座塔就不重发，避免每帧 HumanAction 打断上方拉扯 HumanMove。
                int towerSN = findNearestEnemyTower(a.DR, a.UR, TOWER_TARGET_RANGE * BL);
                if (towerSN >= 0) {
                    if (a.WorkObjectSN != towerSN) {
                        HumanAction(a.SN, towerSN);
                        DebugText(QString("[TOWER-TGT f=%1] 复合弓兵/远程 SN=%2 攻击最近敌塔 %3 (R<=%4格)")
                                  .arg(frame).arg(a.SN).arg(towerSN).arg(TOWER_TARGET_RANGE));
                    }
                } else if (directMarch && calDistance(a.DR, a.UR, targetDR, targetUR) <= 12 * BL) {
                    // ★ 2026-09-13 用户要求「军队不要攻击敌方武器厂」：不再优先选武器厂(ARMY_IGNORE_SIEGE_WORKSHOP)，
                    //   改打【最近任意敌建筑】（箭塔已在上面 towerSN 分支优先命中）。
                    int ebSN;
                    if (ARMY_IGNORE_SIEGE_WORKSHOP) {
                        int nb = findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
                        // ★ 武器厂专留给祭司感化——军队即使最近建筑是武器厂也跳过它(不打武器厂)
                        ebSN = (nb >= 0 && siege != nullptr && nb == siege->SN) ? -1 : nb;
                    } else {
                        ebSN = siege ? siege->SN : findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
                    }
                    if (ebSN >= 0 && a.WorkObjectSN != ebSN) HumanAction(a.SN, ebSN);
                    else issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);
                } else {
                    issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);
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
            if (enemySN >= 0) {
                // 有敌【单位】可打 → 单位永远优先于建筑（保持原语义，含去重）
                if (a.WorkObjectSN != enemySN) HumanAction(a.SN, enemySN);
            } else {
                // ★ 2026-09-13「士兵攻击箭塔 → 选距离自己最近的箭塔」：
                //   15 格内无敌方单位时，先查【最近敌方箭塔】(TOWER_TARGET_RANGE 格内)并打它，
                //   优先于武器厂(siege)与任意其它敌建筑。近战打塔需要走过去，故给 12 格窗口。
                int towerSN = findNearestEnemyTower(a.DR, a.UR, TOWER_TARGET_RANGE * BL);
                if (towerSN >= 0) {
                    if (a.WorkObjectSN != towerSN) {
                        HumanAction(a.SN, towerSN);
                        DebugText(QString("[TOWER-TGT f=%1] 近战 SN=%2 攻击最近敌塔 %3 (R<=%4格)")
                                  .arg(frame).arg(a.SN).arg(towerSN).arg(TOWER_TARGET_RANGE));
                    }
                } else if (directMarch && calDistance(a.DR, a.UR, targetDR, targetUR) <= 12 * BL) {
                    // ★ 2026-09-13 用户要求「军队不要攻击敌方武器厂」：不再优先选武器厂(ARMY_IGNORE_SIEGE_WORKSHOP)，
                    //   改拆【最近任意敌建筑】（箭塔已在上方 towerSN 分支优先命中）。武器厂留给祭司感化。
                    int ebSN;
                    if (ARMY_IGNORE_SIEGE_WORKSHOP) {
                        int nb = findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
                        // ★ 武器厂专留给祭司感化——军队即使最近建筑是武器厂也跳过它(不打武器厂)
                        ebSN = (nb >= 0 && siege != nullptr && nb == siege->SN) ? -1 : nb;
                    } else {
                        ebSN = siege ? siege->SN : findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
                    }
                    // ★ 拆建筑攻击令去重（同 4117）
                    if (ebSN >= 0 && a.WorkObjectSN != ebSN) HumanAction(a.SN, ebSN);   // 有建筑可打→拆基地
                    else issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);  // 无建筑→继续推进
                } else {
                    // 向目标推进：已知敌基地→引擎全图寻路直奔；未知→逐格摸索已探索区
                    issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);
                }
            }
            marchCmds++;
        }
    }

    // ====== 3. 祭司推进/转化武器厂 ======
    // managePriest 已在 processData 中先处理祭司的保命/治疗/感化；
    // 这里只在祭司真正空闲或行走时接管推进/感化武器厂，避免覆盖 ATTACKING/CONVERTING 等
    // 引擎托管动作。【修 2026-09-08】原 `if (NowState != IDLE) return;` 写得太严格——祭司跟军
    //   时 NowState=WALKING,几乎每帧都触发 return → 整段祭司推进/感化武器厂 100% 走不到 →
    //   祭司长期滞留后方,感化武器厂永不触发。改为：WALKING 也允许本段进入（攻击令不会打断
    //   行走中的单位,只会覆盖目标,managePriest 对 WALKING 单位的治疗/感化也照常生效）。
    if (priest) {
        if (priestCounterCooldown > 0) priestCounterCooldown--;   // ★ 反攻推进专用节流（与 priestMoveCooldown 解耦）
        if (priest->NowState != HUMAN_STATE_IDLE && priest->NowState != HUMAN_STATE_WALKING) {
            // 祭司在 ATTACKING（治愈）或 CONVERTING（感化）中,避免本段覆盖其引擎托管动作
            return;
        }

        // ★★ 2026-09-13 保祭司 · 跨块互斥闸 ★★
        //   managePriest(379) 与 manageCounterAttack(410) 在同一主循环里先后调用，旧代码两者用
        //   【两套独立冷却】(priestMoveCooldown / priestCounterCooldown) ⇒ 同一帧可给祭司下发两个
        //   相反的移动令（本段前出武器厂 vs managePriest 后撤）⇒ 祭司原地抖动、净位移 0。
        //   实测 sg2 f=42668~42868：落点在固定武器厂点 (2156.85,2055.22) 与平滑后撤点之间每 10 帧
        //   翻转一次，f=43165 祭司被 Prof.Lu 击杀。
        //   修：统一到同一闸 —— managePriest 本帧已给祭司发过令，本段整体跳过。
        if (priestMoveCooldown > 0) return;

        // 有伤兵时把祭司留给 managePriest 治疗，推进下帧再继续
        bool anyInjuredAlly = false;
        for (auto &a : info.armies) {
            if (a.MaxBlood <= 0) continue;
            if (a.Blood > 0 && a.Blood < a.MaxBlood) { anyInjuredAlly = true; break; }
        }
        // ★ 2026-09-07 修（反攻期"复合弓兵在家里乱走"根因链起点）：
        //   原逻辑【只要队伍里有一个兵掉血就 return】——反攻期掉血是常态 ⇒ 祭司几乎每帧都停，
        //   永远跟不上大部队 ⇒ 祭司长期滞留后方 ⇒ 敌人摸到祭司 15 格 → priestThreatened 恒真
        //   ⇒ 护驾令把全军拉回（死锁，见 D0 优先级2 的 30 格闸修复）。
        //   改为：反攻期只有【重伤(血量<50%)】才停下来治疗，轻度掉血继续跟随大部队推进。
        //   ⚠ 非反攻期行为完全不变（仍是"有伤就治"）；治疗本身仍由 managePriest 全程负责，
        //     这里只是决定"祭司要不要继续朝目标移动"。
        if (anyInjuredAlly) {
            bool criticalInjured = false;
            for (auto &a : info.armies) {
                if (a.MaxBlood <= 0 || a.Blood <= 0) continue;
                if (a.Blood < a.MaxBlood * 0.5) { criticalInjured = true; break; }
            }
            if (state != COUNTERATTACK) return;   // ★【修 2026-09-08】反攻期 criticalInjured 不再 return——
                                                    //   否则战场激烈时几乎每帧都有兵 < 50% → 祭司段永远不跑
        }

        double pDist = calDistance(priest->DR, priest->UR, targetDR, targetUR);
        // ★★★ 2026-09-13 用户需求：「敌方军队全灭且箭塔全拆后，祭司应去感化敌方武器厂」★★★
        //   根因：本段原有两个互斥条件 ——
        //     ① `siege && pDist < 12*BL` 才能感化武器厂（引擎感化射程 DIS_PRIEST=12）；
        //     ② 下方 else 分支强制祭司"距反攻目标 ≥ PRIEST_MIN_DIST_TARGET(18) 格"。
        //   12 < 18 ⇒ 二者**永远不可能同时成立**！实测 k8/cb8 的 [PRST-REAR] dTgt 恒在 22.6~36.4 格，
        //   祭司被安全距离钉死在后方 ⇒ 感化武器厂 0 次（全部 9 局 352 条转换令**无一条是建筑**）。
        //   修复：当祭司【自身周边无军事威胁】时，解除 18 格安全距离约束，允许祭司主动前出感化武器厂。
        //   ★ 判据用【祭司周边 20 格内无敌方军队 + 无敌方箭塔】（局部清场），而非"全局敌全灭"——
        //     实测 8 局里"全局敌全灭"从未出现的概率极高（7/8 局敌军队一直存在），
        //     而用户描述的场景本质是"祭司身边已经安全了，就该去干活"。
        //     ⇒ 局部清场判据既覆盖用户场景，又不会让祭司在有兵有塔时莽撞前出。
        int enemyMil = 0;
        for (auto &e : info.enemy_armies) if (e.Blood > 0) enemyMil++;
        int enemyTowers = 0;
        for (auto &b : info.enemy_buildings) if (b.Type == BUILDING_ARROWTOWER) enemyTowers++;
        // 局部清场：祭司 20 格内无活敌军队、无箭塔
        bool localClear = true;
        for (auto &e : info.enemy_armies)
            if (e.Blood > 0 && calDistance(priest->DR, priest->UR, e.DR, e.UR) < 20.0 * BL) { localClear = false; break; }
        if (localClear)
            for (auto &b : info.enemy_buildings)
                if (b.Type == BUILDING_ARROWTOWER &&
                    calDistance(priest->DR, priest->UR, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL) < 20.0 * BL) { localClear = false; break; }
        bool allowConvertSiege = PRIEST_CONVERT_SIEGE_WHEN_CLEAR && localClear;
        // ★【2026-09-08 二次修】原"扩到 28 格后 priestEnemy>=0 return"——WRONG-LAYER return 又踩坑:
        //   反攻期祭司前出后 28 格内**恒有敌** → return 几乎每帧触发 → 祭司段永远跑不到 → 停在 TC 不动。
        //   改为：只查询,不 return——managePriest 仍独立按"投石车→近战→远程→村民"优先级感化
        //   (原 12~28 格盲区已扩到 28 格),本段继续走感化武器厂 / HumanMove 推进(与 managePriest 并行)。
        int priestEnemy = findNearestEnemySN(priest->DR, priest->UR, PRIEST_CONVERT_RANGE * BL);
        // 注: priestEnemy 暂不直接使用——managePriest 已独立感化,本段只关心武器厂 + 推进

        // ★ 2026-09-12 安全距离优先（用户需求"祭司反攻不要太靠前，尽量在安全距离"）：
        //   旧版把祭司推到 target-5格，且"感化武器厂"(pDist<12)会把祭司长期钉在武器厂旁=太靠前。
        //   新方案：祭司冲到反攻目标 PRIEST_MIN_DIST_TARGET 格内(太靠前)→本帧强制后撤到【大队后方安全距离】，
        //   不感化武器厂(避免被钉在前线送命)；只有已在安全范围才允许【被动】感化武器厂(不主动前出)。
        bool priestTooClose = (pDist < PRIEST_MIN_DIST_TARGET * BL);
        // ★ 2026-09-13：敌方已清场(enemyMil==0 && enemyTowers==0)时，安全距离约束失效 ——
        //   否则 18 格安全 > 12 格感化射程，祭司永远够不到武器厂（这就是"不感化"的根因）。
        if (allowConvertSiege) priestTooClose = false;

        // ★★★ 2026-09-13 用户需求：敌方军队全灭 + 箭塔全拆 → 祭司主动前出感化武器厂 ★★★
        //   优先级高于"后撤保命"（清场后无威胁，前出不会送命）。
        if (allowConvertSiege && siege && priest->ConvertCooldown <= 0) {
            double dSiege = calDistance(priest->DR, priest->UR, targetDR, targetUR);
            if (dSiege <= PRIEST_CONVERT_SIEGE_RANGE * BL) {
                // 已在感化射程内 → 直接感化武器厂
                HumanAction(priestSN, siege->SN);
                priestCounterCooldown = 60; priestMoveCooldown = 60;
                if (frame % 50 == 0)
                    DebugText(QString(">> Priest converting Siege Workshop! f=%1 d=%2 敌已清场(mil=%3 twr=%4)")
                              .arg(frame).arg(dSiege / BL, 0, 'f', 1).arg(enemyMil).arg(enemyTowers));
            } else if (priestCounterCooldown <= 0) {
                // 在射程外 → 主动朝武器厂推进（清场状态，不怕前出）
                double ux2 = (targetDR - priest->DR), uy2 = (targetUR - priest->UR);
                double ul2 = std::sqrt(ux2 * ux2 + uy2 * uy2) + 1e-6;
                ux2 /= ul2; uy2 /= ul2;
                double stopD = (PRIEST_CONVERT_SIEGE_RANGE - 1.0) * BL;   // 停在感化射程内 1 格处
                double tx = targetDR - ux2 * stopD;
                double ty = targetUR - uy2 * stopD;
                tx = max(0.0, min((double)MAP_L * BL, tx));
                ty = max(0.0, min((double)MAP_U * BL, ty));
                if (isPassableAt(tx, ty)) {
                    HumanMove(priestSN, tx, ty);
                    priestCounterCooldown = 30; priestMoveCooldown = 30;
                    if (frame % 100 == 0)
                        DebugText(QString(">> Priest ADVANCE to Siege f=%1 d=%2 enemy_cleared")
                                  .arg(frame).arg(dSiege / BL, 0, 'f', 1));
                }
            }
            return;   // 清场期：本帧祭司任务就是感化武器厂，不走下方后撤逻辑
        }

        if (siege && pDist < 12 * BL && priest->ConvertCooldown <= 0) {
            // 在感化范围内→感化武器厂！
            HumanAction(priestSN, siege->SN);
            priestCounterCooldown = 60; priestMoveCooldown = 60;
            DebugText(">> Priest converting Siege Workshop!");
        } else if (priestCounterCooldown <= 0 || priestTooClose) {
            // ★ 2026-09-12 改（用户需求"祭司反攻不要太靠前，尽量在安全距离"）：
            //   旧版把祭司推到 target(敌基地)-5格(仅沿 DR 轴退5格)——祭司几乎与大军一起冲到敌基地外5格，
            //   前线一崩、祭司暴露在敌塔/敌兵火力下 = 立即失败。
            //   新方案：祭司跟随【己方大部队重心】(排除自身)，始终位于大队【后方】(朝 TC 方向) PRIEST_SAFE_BEHIND 格；
            //   且强制与反攻目标(敌基地/武器厂)保持 ≥ PRIEST_MIN_DIST_TARGET 格 —— 祭司永远在大部队身后，
            //   不单独前出、不冲进敌基地射程。感化武器厂那段(上方 if)保留但改为【被动】：只有祭司随大队推进后
            //   自然进入感化范围才感化，不再主动前出到武器厂。
            double tcDR = rallyCtrDR, tcUR = rallyCtrUR;   // ★ 后方锚点 = 集结 TC（己方基地方向），祭司朝此方向退
            double sumDR = 0, sumUR = 0; int nArmy = 0;
            for (auto &a : info.armies) {
                if (a.SN == priestSN) continue;       // 重心不算祭司自己
                sumDR += a.DR; sumUR += a.UR; nArmy++;
            }
            double armyDR = (nArmy > 0) ? sumDR / nArmy : tcDR;
            double armyUR = (nArmy > 0) ? sumUR / nArmy : tcUR;
            // 大队→TC 方向单位向量（即"大队身后"方向）
            double ux = tcDR - armyDR, uy = tcUR - armyUR;
            double ul = std::sqrt(ux * ux + uy * uy) + 1e-6;
            ux /= ul; uy /= ul;
            // 祭司目标 = 大队重心 朝 TC 退 SAFE_BEHIND 格
            double px = armyDR + ux * PRIEST_SAFE_BEHIND * BL;
            double py = armyUR + uy * PRIEST_SAFE_BEHIND * BL;
            // 安全距离约束：距反攻目标 ≥ MIN_DIST_TARGET（不满足则沿身后方向继续退，直到满足）
            double dTgt = calDistance(px, py, targetDR, targetUR);
            if (dTgt < PRIEST_MIN_DIST_TARGET * BL) {
                double need = (PRIEST_MIN_DIST_TARGET * BL - dTgt) + 2.0 * BL;
                px += ux * need; py += uy * need;
            }
            px = max(0.0, min((double)MAP_L * BL, px));
            py = max(0.0, min((double)MAP_U * BL, py));
            if (isPassableAt(px, py))
                HumanMove(priestSN, px, py);
            if (frame % 100 == 0)
                DebugText(QString("[PRST-REAR f=%1] army=(%2,%3) tgt=(%4,%5) dTgt=%6 tooClose=%7")
                          .arg(frame).arg(armyDR / BL, 0, 'f', 0).arg(armyUR / BL, 0, 'f', 0)
                          .arg(targetDR / BL, 0, 'f', 0).arg(targetUR / BL, 0, 'f', 0)
                          .arg(dTgt / BL, 0, 'f', 1).arg(priestTooClose ? 1 : 0));
            priestCounterCooldown = 30; priestMoveCooldown = 30;
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

// ★ 2026-09-12：离指定点【最近】的空闲村民（远距选址建筑的建造者选取）。
//   动机：findIdleFarmer 返回的是本帧(每帧随机打乱)列表里的【第一个】空闲村民 ——
//   对"必须建在 40+ 格外的猎场"这类远距选址，随机抽人会派到 TC 附近的村民，
//   村民长征数十格期间仓库建不出来、打猎闸门一直挂着（食物经济空转）。
tagFarmer* UsrAI::findIdleFarmerNear(double dr, double ur) {
    tagFarmer* best = nullptr;
    double bestD = 1e18;
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN) || f.SN == scoutFarmerSN) continue;
        if (f.NowState != HUMAN_STATE_IDLE || f.Resource > 0) continue;
        double d = (f.DR - dr) * (f.DR - dr) + (f.UR - ur) * (f.UR - ur);
        if (d < bestD) { bestD = d; best = &f; }
    }
    return best;
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

// ★ 2026-09-13 用户需求「士兵攻击箭塔时选择距离自己最近的箭塔为目标」。
//   只扫 info.enemy_buildings 中 Type==BUILDING_ARROWTOWER 的项，取【距 (dr,ur) 最近】者。
//   距离口径与 findNearestEnemyBuilding 一致：建筑中心 =(BlockDR+1, BlockUR+1)×BL
//   （箭塔是 2×2，+1 即中心；见 cpp:5405 bSize 判据）。
//   range 为"格"换算后的像素距离（调用方传 N*BL），超出该半径的塔视为不构成即时威胁→返回 -1。
int UsrAI::findNearestEnemyTower(double dr, double ur, double range) {
    int bestSN = -1;
    double bestDist = range * range;
    for (const auto &b : info.enemy_buildings) {
        if (b.Type != BUILDING_ARROWTOWER) continue;
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

// ★ 砍树选树：优先"离已建成仓库/TC 近"的树，而不是"离村民近"的树。
//   【为什么】只比"村民→树"时，村民在远处干活结束变空闲，最近的树往往是脚边远离基地的林子，
//   砍完要横穿半张地图才能卸货到仓库，往返成本极高（用户实测：村民跑到离基地很远的地方砍树）。
//   【策略】score = (α·村民→树 + β·树→最近锚点) × 拥挤惩罚，取最小。β(1.0) > α(0.5) → 锚点主导。
//   【锚点】Percent==100 的 BUILDING_STOCK / BUILDING_CENTER（在建中的不算）。细节坐标 =(BlockDR+1)*BL。
//   【硬闸】树→锚点 > WOOD_MAX_ANCHOR_DIST 个 BLOCK 直接排除；硬闸内无可用树时退化为"离锚点最近的树"
//   ——★ 绝不退化回"离村民最近的远树"，这是修复关键。
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

        // ---- 单树拥挤：树上已有工人 + 本帧已派，不超过上限 ----
        int workerCount = 0;
        for (auto &other : info.farmers)
            if (other.WorkObjectSN == r.SN) workerCount++;
        const bool treeFull = (workerCount + frameWoodCount[r.SN] >= WOOD_MAX_WORKERS_PER_TREE);

        // 兜底：全池里离锚点最近【且未满员】的树（不受硬闸限制，避免跑远树）。
        //   ★ 2026-09-08：原实现不判满员——硬闸内树全满员时会退到这棵树，反而挤成 2 人，
        //     与"每棵树最多 1 人"冲突。故此处同步遵守人数上限。
        if (!treeFull && anchorD < bestAnchorDist) { bestAnchorDist = anchorD; nearestAnchorTree = &r; }

        if (anchorD > maxAnchor) continue;   // ★ 硬闸：离仓库/TC 太远的树不派工
        if (treeFull) continue;              // ★ 满员 → 本帧不再往这棵树派人

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

// 非祭司军队总数（含伤兵）
int UsrAI::countAllMilitary() {
    int cnt = 0;
    for (auto &a : info.armies) if (a.Sort != AT_PRIEST) cnt++;
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
    // 箭塔选址（第2座一直没人建的修复）：
    //   ⚠ 只扫 r=4~8 外环会失败：BUILD_GAP=1 → 箭塔(2×2)外扩1格=gap 3格内不得有建筑，r=4 时与 TC footprint
    //     重叠 → isPositionFree 永 false（实际可用最小 r=5）；且 TC 周围经济建筑层层占据，整圈可能 0 可用。
    //   修：① 放宽到 r=4~12（4~8 优先、9~12 兜底，均在箭塔射程 8 格覆盖内），2×2 塔改用
    //      max(|dx|,|dy|)==r 的"钻石形"外圈覆盖所有候选；② 失败前清空 triedBuildPositions，让 tryBuild 兜底不受旧 ban 卡。
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

// 远距浆果群定位（第二座谷仓专用，2026-09-07）
//   需求：除 TC 附近的浆果地外，若别处还有 ≥MIN_BUSH_FOR_SECOND_GRANARY 丛的浆果群，
//   就在它旁边建第二座谷仓，让采集村民就近交食物（浆果 → HUMAN_GRANARYFOOD → 谷仓）。
//   判据三条同时成立才算"远距浆果群"：
//     ① 距 TC ≥ SECOND_GRANARY_TC_MIN_DIST (25) 格 —— 排除 TC 附近那一片（第一座谷仓已覆盖）
//     ② 距【任一已有谷仓(含在建地基)】> 12 格 —— 避免在同一片重复建
//     ③ 以该丛为中心 BUSH_CLUSTER_RADIUS(5) 格内的存活浆果丛数 ≥ 6
//   命中多片时取丛数最多的一片，输出该中心丛的块坐标（供 tryBuild 的 prefX/prefY 使用）。
bool UsrAI::findRemoteBushCluster(int &bx, int &by, int &outCnt) {
    bx = by = -1; outCnt = 0;
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return false;
    double BL = (double)BLOCKSIDELENGTH;
    double tcDR = (center->BlockDR + 1) * BL;
    double tcUR = (center->BlockUR + 1) * BL;

    // 已有谷仓位置（含在建地基，避免对同一片重复下令）
    std::vector<std::pair<double,double>> exist;
    for (auto &b : info.buildings)
        if (b.Type == BUILDING_GRANARY)
            exist.push_back({(b.BlockDR + 1.0) * BL, (b.BlockUR + 1.0) * BL});

    int best = 0, bestX = -1, bestY = -1;
    for (auto &r : info.resources) {
        if (r.Type != RESOURCE_BUSH || r.Cnt <= 0) continue;
        if (calDistance(tcDR, tcUR, r.DR, r.UR) < SECOND_GRANARY_TC_MIN_DIST * BL) continue;   // ①
        bool nearExist = false;
        for (auto &e : exist) {
            if (calDistance(r.DR, r.UR, e.first, e.second) < 12 * BL) { nearExist = true; break; }
        }
        if (nearExist) continue;                                                               // ②
        int cluster = 0;
        for (auto &r2 : info.resources)
            if (r2.Type == RESOURCE_BUSH && r2.Cnt > 0 &&
                calDistance(r.DR, r.UR, r2.DR, r2.UR) < BUSH_CLUSTER_RADIUS * BL) cluster++;
        if (cluster > best) { best = cluster; bestX = r.BlockDR; bestY = r.BlockUR; }
    }
    if (best < MIN_BUSH_FOR_SECOND_GRANARY) return false;                                      // ③
    bx = bestX; by = bestY; outCnt = best;
    return true;
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

// ★★★ 2026-09-12：谷仓周围农场选址（MAX_FARMS 7→12 后必用）
//   场景：TC 周围 4~30 块格已被经济建筑挤满（findFarmRingSite 返回 false），
//         而 MAX_FARMS=12 还要再建 ⇒ 在已有谷仓（GRANARY 3x3）外扩找 3x3 农场位。
//   设计要点：
//   ① 遍历全部已建成谷仓（缺位 fallback ⇒ false 走 tryBuild 后续兜底 findBuildSite）；
//   ② 在谷仓 3x3 外扩 1~10 块格（即谷仓边缘 1~10 格外）环形搜索；
//   ③ 必须 isPositionFree + 不与现有农场 footprint 相邻（沿用 isFarmAdjacent）；
//   ④ 不在 triedBuildPositions 集合中（避免反复在不可建点丢令）；
//   ⑤ 优先级：谷仓 > TC 距离（先扫近 TC 的谷仓），避免农场分布过散。
bool UsrAI::findFarmNearGranarySite(int &x, int &y) {
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return false;
    int cx = center->BlockDR, cy = center->BlockUR;

    // 收集已建成谷仓
    struct GranaryRef { int bx, by; int dTC; };
    std::vector<GranaryRef> granaries;
    for (auto &b : info.buildings) {
        if (b.Type != BUILDING_GRANARY || b.Percent < 100) continue;
        GranaryRef g;
        g.bx = b.BlockDR;
        g.by = b.BlockUR;
        int dx = g.bx - cx, dy = g.by - cy;
        g.dTC = dx * dx + dy * dy;
        granaries.push_back(g);
    }
    if (granaries.empty()) return false;   // ★ 没有谷仓 → false 让 tryBuild 走 findBuildSite 兜底
    // 按距 TC 由近到远排序（先尝试 TC 附近的谷仓，农场分布不散）
    std::sort(granaries.begin(), granaries.end(),
              [](const GranaryRef &a, const GranaryRef &b){ return a.dTC < b.dTC; });

    for (auto &g : granaries) {
        // 谷仓 footprint = [g.bx, g.bx+2] x [g.by, g.by+2]（谷仓 3x3）；
        // 农场 footprint = [nx, nx+2] x [ny, ny+2]；
        // 相邻条件：两 footprint 在 X/Y 任一轴有交集（含边界）即不可；
        // 安全候选：nx <= g.bx-3 或 nx >= g.bx+3（隔 1 块格 gap），ny 同理。
        // 实际上 isFarmAdjacent 已经做了"外扩 1 格"判定（cpp:5422），
        // 这里直接 nx ∈ [g.bx-r-2, g.bx+r+2] 探测即可，让 isFarmAdjacent 兜底判断。
        for (int r = 1; r <= 10; ++r) {
            // 上侧 + 下侧：nx 在 [g.bx-r, g.bx+r+2] 扫描
            for (int dx = -r; dx <= r + 2; ++dx) {
                int nx = g.bx + dx;
                int ny = g.by - r - 1;         // 上方：农场 footprint 顶 = ny+2 ≤ g.by - 1 ⇒ ny ≤ g.by - 3 ⇒ 起始 ny = g.by - r - 1
                int key = nx * 1000 + ny;
                if (!triedBuildPositions.count(key) && isPositionFree(nx, ny, 3) && !isFarmAdjacent(nx, ny)) {
                    x = nx; y = ny; return true;
                }
                ny = g.by + r + 1;             // 下方（对称）
                key = nx * 1000 + ny;
                if (!triedBuildPositions.count(key) && isPositionFree(nx, ny, 3) && !isFarmAdjacent(nx, ny)) {
                    x = nx; y = ny; return true;
                }
            }
            // 左侧 + 右侧
            for (int dy = -r; dy <= r + 2; ++dy) {
                int ny = g.by + dy;
                int nx = g.bx - r - 1;         // 左侧（对称）
                int key = nx * 1000 + ny;
                if (!triedBuildPositions.count(key) && isPositionFree(nx, ny, 3) && !isFarmAdjacent(nx, ny)) {
                    x = nx; y = ny; return true;
                }
                nx = g.bx + r + 1;             // 右侧
                key = nx * 1000 + ny;
                if (!triedBuildPositions.count(key) && isPositionFree(nx, ny, 3) && !isFarmAdjacent(nx, ny)) {
                    x = nx; y = ny; return true;
                }
            }
        }
    }
    return false;
}

bool UsrAI::tryBuild(int buildingType, int size, bool ignoreCooldown, int prefX, int prefY, bool noFallback,
                     bool preferNearBuilder) {
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

    // ★ 2026-09-12：指定坐标的远距建筑优先派【离该点最近的】空闲村民当建造者
    //   （瞪羚群仓库等：打猎闸门在等它落地，不能让建造者从 TC 长征几十格）。
    tagFarmer* f = nullptr;
    if (preferNearBuilder && prefX >= 0 && prefY >= 0)
        f = findIdleFarmerNear((prefX + 1) * (double)BLOCKSIDELENGTH, (prefY + 1) * (double)BLOCKSIDELENGTH);
    if (!f) f = findIdleFarmer();
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
        // ★ 指定坐标却无处可放 + 调用方要求不回退 → 直接失败（避免建到与意图无关的位置）
        if (!placed && noFallback) return false;
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
    if (!placed && buildingType == BUILDING_FARM) {
        // ★★★ 2026-09-12 三段式选址（MAX_FARMS 7→12 后）：TC 环 → 谷仓环 → 兜底 ★★★
        //   ① findFarmRingSite：TC 周围隔 1 格环形（已被房屋/兵营/市场/箭塔挤满时常常 false）
        //   ② findFarmNearGranarySite：现有谷仓外扩 1~10 块格（基地附近放不下时的扩展位）
        //   ③ findBuildSite：最后兜底（应很少触发；触发即说明地图已极密）
        placed = findFarmRingSite(x, y);
        if (!placed) placed = findFarmNearGranarySite(x, y);
    }
    if (!placed && buildingType == BUILDING_ARROWTOWER)
        placed = findDefenseBuildSite(x, y, size);
    // 兵营/靶场/马厩：偏向 TC→地图中心方向、离 TC 更远(12~45格)，成片铺开不堵 TC 周边
    if (!placed && (buildingType == BUILDING_ARMYCAMP || buildingType == BUILDING_RANGE ||
                    buildingType == BUILDING_STABLE))
        placed = findBuildSiteTowardCenter(x, y, size, 12, 45);
    if (!placed) placed = findBuildSite(x, y, size);
    if (!placed) return false;

    buildingFarmerType[f->SN] = buildingType;
    builderDispatchFrame[f->SN] = frame;   // ★ 硬超时起点（本次建造令下发帧）
    int buildInsId = HumanBuild(f->SN, buildingType, x, y);
    pendingBuildIns[buildInsId] = {f->SN, buildingType};
    pendingBuildInsFrame[buildInsId] = frame;
    lastBuildIssueFrame[buildingType] = frame;

    // 记录尝试过的位置，防止反复在同一位置建造失败
    int key = x * 1000 + y;
    triedBuildPositions.insert(key);

    buildCooldown = 5;   // 5帧冷却（单位碰撞检测已防止重复失败）
    // ★ 2026-09-13 建造下令观测：记录每次 HumanBuild 的类型/村位/坐标，
    //   用于对照"地基何时放下 / 何时完工"，定位长期卡住的地基。
    DebugText(QString("[BUILD-ISSUE f=%1] type=%2 size=%3 村民SN=%4 at=(%5,%6) wood=%7")
              .arg(frame).arg(buildingType).arg(size).arg(f->SN).arg(x).arg(y).arg((int)info.Wood));
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
            // ★ WorkObjectSN 在寻路失败/目标丢失时已被引擎清零(-1)，无法据此拉黑不可达树
            //   → 用 villLastTreeSN 兜底：取本村民最近一次被派去的树SN拉黑，避免同一棵不可达树被反复重选
            if (targetSN <= 0 && villLastTreeSN.count(f.SN)) targetSN = villLastTreeSN[f.SN];
            if (targetSN > 0) stuckResourceUntil[targetSN] = frame + STUCK_BLACKLIST_FRAMES;
            HumanAction(f.SN, center->SN);  // 打断卡死关系，回TC重新待命
            gatherStuckFrame.erase(f.SN);
            DebugText(QString("[STUCK f=%1] 村民SN=%2 寻路卡死, 目标资源SN=%3 已拉黑").arg(frame).arg(f.SN).arg(targetSN));
        }
    }
}

// ============================================================
// ★★★ 2026-09-12「先建仓库、再打猎」闸门（用户需求）
//   「在村民开始狩猎瞪羚前尽量先建仓库」——猎人出发前交付点必须已就位，
//   否则猎人抱着肉空跑「猎场↔TC」往返（往返 2×距离），食物效率腰斩。
//   返回 true = 现在可以去打这只瞪羚；false = 本帧先别派猎人，等仓库落地
//   （manageBuildings 的最高优先级仓库块每帧都会重试建造）。
//   判据顺序（任一成立即放行，确保【永远不会把食物经济饿死】）：
//     ① 木头 < 仓库造价 → 根本建不起，不能拿食物陪葬；
//     ② frame ≥ 解禁兜底(6游戏分) 或 已过建造窗口(11游戏分) → 仓库不会来了，放行；
//     ③ storageNearGazelleBuilt==1 → 已建好 / 已被现成仓库覆盖 / 已达 MAX_STOCK；
//     ④ 该瞪羚 GAZELLE_HUNT_RANGE 内已有仓库（含在建地基）→ 交付点已就位。
//   ⚠ 判据④把"在建"也算通过：地基已在群边、村民正在施工，此时去打猎不会长距离空跑。
// ============================================================
bool UsrAI::gazelleDropoffReady(tagResource* r) {
    if (!r) return true;
    if (info.Wood < BUILD_STOCK_WOOD) return true;                         // ① 建不起
    if (frame >= GAZELLE_STOCK_GATE_DEADLINE) return true;                 // ② 超时兜底
    if (frame >= GAZELLE_STOCK_WINDOW_END) return true;                    // ② 窗口已关
    if (storageNearGazelleBuilt == 1) return true;                         // ③ 已建/已覆盖
    const double BL = (double)BLOCKSIDELENGTH;
    for (auto &b : info.buildings) {
        if (b.Type != BUILDING_STOCK) continue;
        if (b.Percent < 100 && deadBuildings.count(b.SN)) continue;        // 废弃地基不算
        double bDR = (b.BlockDR + 1) * BL, bUR = (b.BlockUR + 1) * BL;
        if (calDistance(r->DR, r->UR, bDR, bUR) < GAZELLE_HUNT_RANGE * BL) return true;   // ④ 就近已有交付点
    }
    return false;
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

    // ★ 优先级1：浆果丛（TC 30格内 或 已建成谷仓 20格内，每丛≤2人，满2人后按优先级转大象/农场/瞪羚）★
    //   ★ 2026-09-07 放宽：远距浆果群旁建了第二谷仓后，这里的"距 TC ≤30 格"会把它们全挡掉，
    //     导致谷仓建了却没人去采。改为：距 TC ≤30 格 或 距任一已建成谷仓 ≤20 格。
    std::vector<std::pair<double,double>> builtGranaries2;
    for (auto &b : info.buildings)
        if (b.Type == BUILDING_GRANARY && b.Percent == 100)
            builtGranaries2.push_back({(b.BlockDR + 1.0) * BL, (b.BlockUR + 1.0) * BL});
    tagResource* bestBush = nullptr;
    double bestBDist = 1e12;
    for (auto &r : info.resources) {
        if (r.Type != RESOURCE_BUSH || r.Cnt <= 0) continue;
        if (stuckResourceUntil.count(r.SN)) continue;  // 不可达的浆果，跳过
        if (calDistance(tcDR, tcUR, r.DR, r.UR) > 30 * BL) {
            bool nearGranary = false;
            for (auto &gd : builtGranaries2)
                if (calDistance(r.DR, r.UR, gd.first, gd.second) <= BUSH_NEAR_GRANARY_DIST * BL) {
                    nearGranary = true; break;
                }
            if (!nearGranary) continue;
        }
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
    //   ★ 2026-09-13 用户需求「必须 4 个人一起狩猎」：本函数【只补已成团的队】(已在打 ≥ ELEPHANT_HUNT_MIN 人)，
    //     【绝不单独开团】——开新团由 assignIdleSimple() 的"猎象整队"块在同一帧一次性派 4 人完成。
    if (!isWarTime) {
        tagResource* bestEle = nullptr;
        double bestEDist = 1e12;
        for (auto &r : info.resources) {
            if (r.Type != RESOURCE_ELEPHANT || r.Cnt <= 0) continue;
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > 30 * BL) continue;
            if (stuckResourceUntil.count(r.SN)) continue;
            int realCount = 0;
            for (auto &other : info.farmers)
                if (other.WorkObjectSN == r.SN) realCount++;
            if (realCount < ELEPHANT_HUNT_MIN) continue;      // ★ 未成团(0~3人)一律不派人：单人/双人必死
            if (realCount >= ELEPHANT_HUNT_GROUP) continue;   // 已满员(5)
            double d = calDistance(f->DR, f->UR, r.DR, r.UR);
            if (d < bestEDist) { bestEDist = d; bestEle = &r; }
        }
        if (bestEle) {
            HumanAction(f->SN, bestEle->SN);
            frameFoodTargets.insert(bestEle->SN);
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
        // ★ 2026-09-12「先建仓库再打猎」：仓库没就位就不派人（本函数返回 false，交由伐木/兜底接住）
        if (bestGazelle && gazelleDropoffReady(bestGazelle)) {
            HumanAction(f->SN, bestGazelle->SN);
            huntingGroup.insert(f->SN);
            frameGazelleCount[bestGazelle->SN]++;
            return true;
        }
    }

    return false;
}


