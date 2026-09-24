#include "UsrAI.h"
#include <unordered_set>
#include <map>
#include <mutex>

tagGame tagUsrGame;
ins UsrIns;
/*##########DO NOT MODIFY THE CODE ABOVE##########*/

// ★★★ 2026-09-23 OJ 崩溃自救：主线程代取快照所依赖的 QtCore 头（不引用任何引擎新增符号）★★★
#include <QCoreApplication>   // QCoreApplication::postEvent（跨线程投递到主线程事件循环）
#include <QEvent>

namespace {
struct SnapState {
    tagInfo buf;
    QMutex mutex;
    QWaitCondition cond;
    bool ready = false;
    int failStreak = 0;
    int mainCount = 0;
    int fallbackCount = 0;
    int skipCount = 0;
};
std::map<const UsrAI*, SnapState> g_snapStates;
std::mutex g_snapStatesMutex;
SnapState& snapState(const UsrAI* self) {
    std::lock_guard<std::mutex> lock(g_snapStatesMutex);
    return g_snapStates[self];
}
}  // namespace

// ★★★ 兵种分类 / 射程判据（2026-09-23 重构：由 manageCounterAttack 内的局部 λ 提升为文件级 static）★★★
//   提升原因：原 isRanged / isMeleeSort / rangedMaxRange / kiteRangeAdvantage 四个 λ 只在反攻函数体内可见，
//   而 lookupEnemySN() / findKiteTarget() 提升为成员函数后仍要这批判据 ⇒ 不外提就得在两处各抄一份（铁律 21/26）。
//   提升后各判据的表达式逐字未改，仅换了名字（前缀 sort 以示"按兵种编号判定"）。
//
// 远程兵种分类：有攻击距离、能隔着距离输出者。近战 / 村民 / 祭司 / 建筑不在此列。
static inline bool sortIsRanged(int sort) {
    return sort == AT_STONE_THROWER || sort == AT_BOWMAN ||
           sort == AT_COMPOSITE_BOWMAN || sort == AT_SLINGER ||
           sort == AT_CHARIOT_ARCHER;
}

// 近战兵种(短手、贴身肉搏)：用于判断敌是否会"冲过来贴身打我们"。
// 拉扯(kiting)时对近战敌要更早后撤、后撤更远——它们射程极短但会持续追击贴身。
static inline bool sortIsMelee(int sort) {
    return sort == AT_CLUBMAN || sort == AT_SCOUT || sort == AT_SWORDSMAN ||
           sort == AT_IMPROVED || sort == AT_CAVALRY || sort == AT_HOPLITE ||
           sort == AT_CHARIOT || sort == AT_BROADSWORDSMAN;
}

// 各远程兵种最大攻击射程(格)：投石车10 / 复合弓7 / 战车弓7 / 弓5 / 投石兵4。
// ★ 2026-09-21 已对 config.json 回代核验（技能 §0：任何"代码常量==外部配置"的断言必须抓真值）：
//   DIS_STONE_THROWER=10、DIS_COMPOSITE_BOWMAN=7、DIS_CHARIOT_ARCHER=7、DIS_BOWMAN=5、DIS_SLINGER=4 —— 全部一致。
// 用于反攻拉扯(kiting)：把敌方保持在最远射程边缘无伤输出。
static inline double sortMaxRangedRange(int sort, double BL) {
    switch (sort) {
        case AT_STONE_THROWER:   return 10.0 * BL;
        case AT_COMPOSITE_BOWMAN: return 7.0 * BL;
        case AT_CHARIOT_ARCHER:  return 7.0 * BL;
        case AT_BOWMAN:          return 5.0 * BL;
        case AT_SLINGER:         return 4.0 * BL;
        default:                 return 5.0 * BL;
    }
}

// ★★★★★ 2026-09-21 用户需求「复合弓兵不要拉扯战车弓兵和投石车（攻击距离比它们小）」★★★★★
//   拉扯(kiting)的收益前提是【我方射程严格大于对方】：把敌保持在最远射程边缘，自己挨不到打。
//   射程相等或更短时，逼近到自身射程边缘必然同时进入对方射程 ⇒ 挨打却没有输出优势，纯亏（撤了打不着、不撤就被打）。
//   故"射程不占优"的敌单位【不进拉扯目标候选】。
//   真值（config.json）：复合弓 7 vs 战车弓 7（相等）、vs 投石车 10（更长）⇒ 两者皆不拉扯。
//   ⚠ 近战 / 村民 / 祭司等无射程单位（sortIsRanged=false）永远可拉扯；本判据只对远程敌生效。
//   ⚠ 同一判据对所有远程兵种生效（复合弓7/战车弓7/弓兵5/投石兵4 vs 投石车10 全部不占优）
//     —— 避免"改了复合弓、弓兵照样去拉投石车"的同源漏改（铁律 21/26）。
static inline bool sortHasKiteRangeAdvantage(int selfSort, int enemySort, double BL) {
    if (enemySort < 0 || !sortIsRanged(enemySort)) return true;
    return sortMaxRangedRange(selfSort, BL) > sortMaxRangedRange(enemySort, BL);
}


// 距离²（只在"比大小"时用，省一次 sqrt）。凡与内联 (a-b)*(a-b)+(c-d)*(c-d) 等价的点一律改用它。
namespace {
inline double dist2(double x1, double y1, double x2, double y2) {
    const double dx = x1 - x2;
    const double dy = y1 - y2;
    return dx * dx + dy * dy;
}
}  // namespace

// 波次时间（帧）- 来自任务文档
// ★ 实测三波发动帧恒为 6001/13501/21001（敌方为脚本部队预生成），与 AI 侧常量无关。
// ⚠ 一词两义：①「波次是否已开始」判据（EARLY_ECONOMY/wave1Started/postW1）严格讲应 6000；②「战备提前量」判据旧值 5000（敌实攻前 1000 帧转战时）。
// ★★ 定案 5000（09-24 w1 臂 19 局）：胜率 26.3% vs 6000 批 20.0% **无差异**(p=0.539)；败率 42.1% vs 79.2% **显著下降**(p=0.025)，代价是未决率 8.3%→31.6%
//    ⇒ 5000 买到的是"更能扛"（少被打死）而非"更能赢"（多出来的是打满 45000 帧的僵局）。语义拆分（WAVE1_PULSE 6000 + WAVE1_PREP 5000）预期无收益 ⇒ 暂不拆。
#define WAVE1_TIME 5000
#define WAVE2_TIME 13500
#define WAVE3_TIME 21000

// ★★★ 完整版：PPT策略——房→市→兵营→靶场→马厩→箭塔 ★★★
#define MAX_FARMERS 22          // 目标村民数量（PPT建议20-28）
#define MAX_HOUSES 12           // +2：60人口=12房（2026-09-16，原 10→12）
#define POP_HEADROOM_BUILD 2    // 人口余量≤此值即补房屋（即 人口达到 人口上限-2 时建房）
// ★ 农场上限：2026-09-01 二改 8 → 12；2026-09-24 用户要求 12 → 10。
// 后期野生食物枯竭后，食物产能 = 农场座数 × 1人/座（代码强制"每座农场有且仅有一人"），   10 座 = 10 个食物工；上限过高会抢占木材/建造工位。
// 农场间隔 1 格（isFarmAdjacent）仍需选址空间，若实测建不满 10 座可继续下调。
#define MAX_FARMS 10            // 农场上限：7→12→10（2026-09-24 用户要求降为 10 座）
// ⮕ 食物通道：R5 末 5+20+30 = 340 食 vs TC 用率 25% ⇒ 上限放宽至 12；选址链 = findFarmSiteBest → findBuildSite(兜底)。
// ★★★ 2026-09-19 农场选址（用户要求「尽量分布在 TC 和谷仓周围」「只隔一格」）★★★ 候选 = TC 环 ∪ 已建成【谷仓】环（★ 仓库 STOCK 不作锚点），仅取紧邻环 r = R_MIN = 4（隔 1 格几何）。
// 评分基准 =【到 TC 的距离】：农场原地生产、食物自动入库，村民从 TC 出发 ⇒ 真代价是 TC→农场通勤。
// 若按"到最近锚点"评分，谷仓旁 r=4 会压过 TC 旁 r=5 ⇒ 实测被甩到 >10 格占 39.2%、中位 5.7→12.4 格（已证伪）。 ⇒ TC 旁优先；TC 环满才轮谷仓环 = 用户原话「基地附近位置不够的话」。
#define FARM_ANCHOR_R_MIN 4      // 锚点外的最近可行环（3x3 锚点 + 隔 1 格 + 3x3 农场）
// ★★★ 2026-09-19 用户需求「农场只能建在谷仓和 TC 周围隔一格的地方」⇒ R_MAX 由 18 收到 = R_MIN（只允许紧邻环）★★★
// 依据（kd 23 局 / 251 座）：紧邻环 r=4 几何上仅 8 槽，其中 TC 正下 (-4,-4) 常被初始箭塔占 ⇒ 实际 6~7 座。
// 旧 R_MAX=18 时 r=5/6/7 与紧邻环错位相邻而几乎不可用（10.8/3.2/2.4%），下一对齐层是 r=8 ⇒ 30.3% 农场落到 8~11.3 格。
// ★ 座数补偿：TC 环满后吃【谷仓环】（同 r=4 口径），见 findFarmSiteBest 第 2 段。
#define FARM_ANCHOR_R_MAX 4      // 搜索半径上限 = R_MIN ⇒ 只允许紧邻环（2026-09-19 用户硬限制）
// ★★★ 2026-09-19 用户需求追加：「农场可以建在谷仓附近，但不能建在仓库附近」⇒ 锚点 = TC + 谷仓，仓库一律排除 ★★★
// 理由（口径而非实现细节）：仓库是按【瞪羚群】布点的猎场节点（MAX_STOCK=4），为覆盖远处兽群而建、天然远离 TC 通勤圈；
// 而农场原地生产食物、村民从 TC 出发 ⇒ 把农场挂到仓库旁等于把食物产出绑在远距通勤上。谷仓则服务浆果群、在基地圈内。
// 实测（fc 6 局 / 87 次落位）：两座非 TC 锚点 (13,34)/(23,32) 合计吃掉 37.9%，其类型由 FARM-PICK 的 ty= 字段给出（ty=[C,G]）。
// ★ 建农场须为【瞪羚中心仓库】预留木头（用户要求，WOOD_RESERVE_FOR_GAZELLE_STOCK=120）：判据 info.Wood >= BUILD_FARM_WOOD + 预留 ⇒ "造完农场后仍留得住 120 木"，保证瞪羚仓库永远有料可建。
// 背景：旧 postW2 农场块只有 Wood>=75 且【无此闸】，而瞪羚仓库窗口是 frame<16500(11分)、postW2 自 13500(9分) 就成立 ⇒ 9~11 分钟两者并存，农场抢光木材 → 仓库永远建不出。
#define WOOD_RESERVE_FOR_GAZELLE_STOCK 120
// ★ 农场木材判据：预留 120 木【只】在瞪羚仓库未建成时有意义；仓库已建成则恢复原阈值 BUILD_FARM_WOOD。 ⚠ 若无条件 +120 ⇒ 门槛永久抬高到 195 木，仓库建好后农场会严重滞后（农场建造点本身已带仓库闸）。
#define FARM_WOOD_NEED(gazelleStockBuilt) \
    ((gazelleStockBuilt) ? BUILD_FARM_WOOD : (BUILD_FARM_WOOD + WOOD_RESERVE_FOR_GAZELLE_STOCK))
// ★★★ 2026-09-13 用户要求「木材加工科技解锁应排在建造农场之前」⇒ 农场加闸：marketWoodUpgraded 未完成不建农场。
// 实测时序（16 局）：市场 f≈5200~5600 建成 → 木材加工 f≈12440~15395 研究完；而农场前置【瞪羚仓库】f≈9000 就绪
// ⇒ 旧逻辑下农场会抢在科技之前铺开。★ 必须配超时兜底（市场未建成/长期缺木/市场被摧毁 ⇒ 农场永久冻结 -> 食物崩盘）。
// 兜底 FARM_WAIT_WOOD_TECH_FRAME = 18000(12min)，比实测最晚研究帧 15395 留 2600 帧余量；触发后本闸自动失效。
#define FARM_WAIT_WOOD_TECH_FRAME 18000
// ★★★ 2026-09-13 用户要求「复合弓兵科技解锁太慢」——农场给复合弓科技让木 ★★★ 旧况：12 座农场（每座 75 木）从 f≈13500 连续建造，把木材长期压在 2~112 区间，而复合弓科技要求 wood≥100
// ⇒ 木闸成为真实瓶颈（食物早已 208→621 远超 180），科技被拖到 f=24759（16.5 分钟）才发令。 修复：复合弓科技【尚未研究/排队】期间，农场建造额外要求"造完仍留得住 100 木"（COMPOSITE_BOW_WOOD_RESERVE）。
// ★ 超时兜底 FARM_WAIT_BOWWOOD_FRAME=21000（= WAVE3_TIME）：靶场长期被占 / 木头长期枯竭时本闸自动失效，防食物崩盘。
#define FARM_WAIT_CB_FRAME 21000
#define COMPOSITE_BOW_WOOD_RESERVE 100   // = BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_WOOD
// ★★★ 2026-09-13 用户要求：「我方军队不要攻击敌方武器厂」★★★ 旧状：全军建筑选择写 `siege ? siege->SN : ...` —— 侦察到武器厂后全军一律优先轰它（k8 局 347 条攻厂令）。
// ⇒ 把武器厂从"军队建筑目标选择"里剔除，军队改打【箭塔 → 其它任意敌建筑】。 ⚠ 仍保留 siege 作为【反攻推进锚点】(targetDR/targetUR/rallyDR/rallyUR/directMarch)，否则 directMarch 失去依据。
#define ARMY_IGNORE_SIEGE_WORKSHOP true
// ★★★ 2026-09-13 用户要求：敌方军队全灭且箭塔全拆后，祭司应去感化敌方武器厂 ★★★
// 根因：祭司"安全距离 PRIEST_MIN_DIST_TARGET=18 格"与"感化需 pDist<12 格"互相矛盾，实测 [PRST-REAR] dTgt 恒 22.6~36.4 格。
// 修复：当【敌方已无军事威胁】(敌方军队 + 敌方箭塔均为 0) 时解除安全距离约束，允许前出感化。
#define PRIEST_CONVERT_SIEGE_WHEN_CLEAR true
#define PRIEST_CONVERT_SIEGE_RANGE 12.0  // 引擎感化射程口径（DIS_PRIEST=12），须 ≤ 此值才能感化
// ★ 打猎瞪羚选取范围（2026-09-04 用户要求"扩大一些"）：30→50 格，覆盖远距未建仓库的瞪羚群。 仓库覆盖判断（1547/1705 nearStock）也用此常量同步，避免猎人跑出去 50 格打、仓库仍卡 30 格内。
#define GAZELLE_HUNT_RANGE  50
// ★★★ 2026-09-12 用户需求：「在村民开始狩猎瞪羚前尽量先建仓库，仓库可以比其他建筑先建」★★★ 参考录像 build order：抵达猎场 01:35 → 就地建仓库 → 02:05 落成 → 之后才是市场/兵营/靶场。
// 旧实现两处顺序相反：① 闸门 `!huntingGroup.empty()`（已在打猎才建）⇒ 猎人先空跑往返； ② 块埋在 if(postW1) 内、排在房屋/兵营/靶场【之后】⇒ 木材被抢光。新：块上移到【所有建筑之前】。
#define GAZELLE_STOCK_MIN_HOUSES    1     // 抢跑前提：至少已有 N 座房屋（先保人口线，再抢仓库）
#define GAZELLE_STOCK_WINDOW_END    16500 // 仓库建造窗口截止(帧)=11游戏分（原为硬编码 16500）
// ★ 打猎解禁兜底（防止闸门把食物经济饿死）：仓库迟迟建不出时，不能无限期卡住打猎—— frame ≥ 此值 或 木头不够造价 或 已过建造窗口 ⇒ 允许先打猎（仓库仍会继续尝试建造）。
#define GAZELLE_STOCK_GATE_DEADLINE 9000  // 6游戏分 = 9000 帧
// ★ 组队猎象（2026-09-03 用户需求）：大象血45/攻10/射程10/不逃跑/掉肉300，性价比远超瞪羚(血8会逃跑)。
// 单挑村民(血25)必死，须凑够 ELEPHANT_HUNT_GROUP 人围猎快速击杀。每头象最多派此人数，集中火力不分散。
// ★ 2026-09-08 用户新需求"大象一定要4个人以上狩猎"：增设 ELEPHANT_HUNT_MIN=4 作为凑人门槛， 1~3 人在打时优先补位；0 人在打时本帧允许派 1 人开团，但限 ELEPHANT_HUNT_MIN 累计防单挑送命。
#define ELEPHANT_HUNT_GROUP 5
#define ELEPHANT_HUNT_MIN   4   // ★ 打大象的最低人数门槛(开团/补位都遵循)
// ★ 2026-09-13 用户需求强化「狩猎大象必须 4 个人一起狩猎，单个村民狩猎会死」： 旧实现是"逐帧凑人"（0 人在打时本帧先派 1 人开团，其余人随后才到）⇒ 先到者在 1~3 人状态下被打死。
// 现改为【整队一次性出击】：同一帧下 min 条令 ⇒ 同时出发 ⇒ 同时抵达 ⇒ 同时开打；凑不齐一人不派。
#define ELEPHANT_RESCUE_MAX_ON 1  // ★ 只有"孤兵/双人"(在打人数≤此值)才强制救援：能补则补，补不齐则召回+拉黑
#define ELEPHANT_BAN_FRAMES    1500  // ★ 孤兵救援后的拉黑时长：1500 帧 = 60 秒内不再往这头象派人
#define MAX_TOWERS 3            // 箭塔数量（2026-09-13 用户改需求：从2座再多建1座=3座；上限抬至3，多采150石建第3座）
#define MAX_RANGES 3            // 反攻阶段靶场上限(并行产弓线，越多弓兵越快)
// ★ 2026-09-13 用户需求「士兵攻击箭塔时选择距离自己最近的箭塔为目标」： 旧状建筑目标只有两个来源 —— findNearestEnemyBuilding（任意类型最近）+「武器厂绝对优先」⇒ a) 更近的房屋/农场顶掉箭塔、
// 挨塔射却不还手；b) 找到武器厂后全军改打它、附近箭塔被无视。   新规则：【距离自己最近的敌方箭塔】优先于武器厂与任意其它敌建筑，仅在 TOWER_TARGET_RANGE 格内生效。
// ⚠ 只影响"选建筑目标"，不改变打敌方【单位】的优先级（单位永远优先于建筑）。
#define TOWER_TARGET_RANGE 12   // 士兵把敌方箭塔纳入攻击目标的最大距离(格)；箭塔射程≈8格
// ★ 2026-09-16 用户纠正「复合弓兵还是要攻击箭塔，只是不拉扯撤退、直接攻击」：09-15 曾实现成"射程<塔(8格)的兵种全禁打塔"——用户本意是【允许打塔、只禁拉扯】。
// "拉扯箭塔"根因：选塔后走 issueMarch 推进段会绕塔圈被动接战 ⇒ 现改为选塔即 return 站桩直接打（不进推进段），天然不拉扯；故只【复合弓兵 AT_COMPOSITE_BOWMAN】恢复打塔。
// ★ 2026-09-21「复合弓兵不要拉扯战车弓兵和投石车」：拉扯收益前提 = 我方射程【严格大于】对方；真值(config.json 已回代) 复合弓 DIS=7 ｜ 战车弓 DIS=7(相等) ｜ 投石车 DIS=10(更长) ⇒ 二者不进"拉扯目标"候选。
//   实现：拉扯目标选取改用 sortHasKiteRangeAdvantage 过滤（findKiteTarget 取代 findNearestEnemyNoStone），原「投石车兜底」段删除；对【所有】远程兵种生效（避免同源漏改）。
//   观测：[KIT-R]/[KIT-S] 新增 tSort=（目标兵种）；验收判据 = tSort 永不出现 8(投石车)/12(战车弓)。投石车仍留给祭司感化 / 我方投石车压制。
// ⚠ 2026-09-21 注释纠错（**仅注释，值未动**）：原注释写"与 config.json DIS_ARROWTOWER 一致"，真值为 **7**，与 8.0 **不一致**；
//   代码保持 8.0 是有意的保守取值（本文件多处依赖"塔射程 8"做站位/打塔判定）⇒ 改值属行为变更，须独立成批验证（遗留 #8）。
#define ARROWTOWER_RANGE 8.0    // 本文件内部使用的"敌箭塔射程"口径(格)；config.json DIS_ARROWTOWER=7（见上，勿再声称一致）
// ★★★ 2026-09-20 方案 B【分层】：修「反攻时攻击箭塔时有部分士兵不攻击」（用户拍板 B）★★★ Tier-1（d ≤ TOWER_TARGET_RANGE = 12）：语义完全不变 —— 发 HumanAction(塔) 站桩打塔（不拉扯）。
// Tier-2（12 < d ≤ TOWER_APPROACH_RANGE = 30）：① **不发攻击令**（不打断上游 kiting / 接敌带 / 攻击令节流）；
// ② 只把【推进落点】改成"该塔靠我方一侧的 STANDOFF(10 格) 环上" ⇒ 兵自然朝塔走，进 12 格后由 Tier-1 无缝接管；
// ③ 仅对 canHitTower 兵种生效（近战 / 复合弓兵 / 投石车）；射程 < 塔的兵种 (战车弓7/弓兵5/投石兵4) 绝不往塔上送。
// ⚠ 刻意不放大攻击半径：放大 ⇒ 引擎主动逼近 ⇒ 冲塔脱队、被塔集火，与 2026-09-18 的 kiting 修复互相抵消。
#define TOWER_APPROACH_RANGE 30.0     // Tier-2【推进偏置】生效上限(格)。与只读诊断 [TOWER-CHANCE] 的 30 格对照桶同源
#define TOWER_APPROACH_STANDOFF 10.0  // Tier-2 落点距塔(格)。必须 < TOWER_TARGET_RANGE(12) 才能一步进环
// （findNearestEnemyTower 是严格 `d2 < r2`，落点恰在 12.0 格不触发；且 > ARROWTOWER_RANGE(8) ⇒ 走路这段不被塔白嫖）
// ★★★ 2026-09-12 改：允许多群瞪羚各建 1 座仓库，1+3 = MAX_STOCK = 4 座上限。 原 MAX_STOCK=2 下多群瞪羚（典型 3~4 群）只能有 2 群被覆盖、其余猎人空跑回最近仓库。
#define MAX_STOCK 4             // 仓库上限：每群覆盖 1 座 + TC 旁首仓 1 座 + 远距覆盖 1~2 座 = 4 座
// ★ 实测补（2026-09-04）：此前缺此上限，旧"第二仓库"段每帧重发令 + 不传坐标 ⇒ 贴 TC 多建 3 座仓库。
// ★★★ 2026-09-22 用户需求「避免一个瞪羚群附近重复建 2 个仓库」★★★ 根因（三类判据各自失明，缺一不可）： ① "远距群"判据 isFarGazelle 的锚点只看【已完工 Percent==100】的仓库；
// ② tryBuild 成功 ≠ 仓库出现在 info.buildings —— 村民还在路上时连地基都没有（乐观判据缺失）； ③ 唯一拦得住的是总量闸 `countBuildingsExisting < MAX_STOCK`——它把"在途"算进去了，但【不认坐标】
// ⇒ 只能等凑满 4 座才停。 ⇒ buildCooldown(5 帧) 一过，同一群再次满足"距所有已完工仓库>20" ⇒ 对同一个群重复下单， 落点又被 findBuildSite 兜底/偏移表挪 1~9 格 ⇒ 肉眼看到的"同一群旁边并排 2~3 座仓库"。
// 改前基线（795 局 / 706 批，探针 stock_order_probe.py）：多仓局 645 局中，同点(块距≤9) 46.0% ＋ 同群(10~20) 8.8% = 54.9%；典型 dm8 f33369(51,49) → f33374(51,49) 同块、仅隔 5 帧（= buildCooldown）。
// 修法（落点记忆，唯一真源在 tryBuild）：见 stockOrderPending() / stockOrderDR-UR-Frame。
#define STOCK_ORDER_SETTLE     3000   // 落点记忆有效窗口(帧)=120 游戏秒（覆盖最远村民走到工地的时间）
#define STOCK_ORDER_MERGE_BLK  20.0   // 与落点块距 ≤ 此值 ⇒ 判为"同一个群"（块；与 isFarGazelle 的 20 格锚点同口径）
#define STOCK_ORDER_RING       4      // 只记最近 N 次仓库令落点（= 最多同时在建的仓库数 = MAX_STOCK）
// ★★★ 2026-09-22 用户需求「金矿旁边没有仓库的话也要建仓库」★★★ 机制依据（引擎侧已核实，非推测）：矿工背包满后由 `Core_List::findResourceBuiding()`
// （Core_List.cpp:736）在【距资源处最近】的已完工建筑里选交付点，候选 = TC ∪ `Resource::get_ReturnBuildingType()`（Resource.cpp:8）：金/木/石/兽肉 → STOCK；浆果·农田 → GRANARY；鱼肉 → DOCK。
// ⇒ 仓库必须落在【金矿旁】才缩短往返；落 TC 旁对金矿毫无意义（本图 8 簇金矿距 TC 16.7~100.1 块）。
// ⛔ 预算必须【额外】给，不能与瞪羚共用 MAX_STOCK：全库 764 局实测 562 局(73.6%) 已吃满 MAX_STOCK=4 ⇒ 共用则金矿仓永远排不上队（**结构不可达，非概率低**）。
//   故用独立计数器 `goldStockOrders < MAX_GOLD_STOCK`，总量闸 = MAX_STOCK+MAX_GOLD_STOCK。⚠ 不能用"距金矿 ≤20 块的仓库数"当判据：预置首仓 (13,34) 距最近金矿仅 19.4 块（gst 批 3/3 开局即计到 1）⇒ 开局自锁。
//   已知代价：少数局里金矿仓会顶掉 1 座瞪羚仓（总量仍 ≤ MAX_STOCK+MAX_GOLD_STOCK）；是否给瞪羚补偿 1 个名额待实测。
// ★ 触发源 = 「村民此刻正在开采的远金矿」—— 有人在那采本身就是"值得建"的证明 ⇒ 不需瞪羚那样的"至少 N 只"数量闸；按"最密簇"选会建在 AI 根本不去的矿旁（白发 120 木）。
#define GOLD_STOCK_ANCHOR_RANGE  20.0  // 金矿格距 TC / 距现有任意仓库 均须 > 此值（块；与第二仓库 20 格同口径）
#define MAX_GOLD_STOCK           1     // 金矿仓库额外名额（不吃 MAX_STOCK 的瞪羚预算 ⇒ 总量上限 = MAX_STOCK + 1）
#define GOLD_STOCK_WOOD_MARGIN   30    // 木材余量保险（口径同第二仓库：info.Wood ≥ BUILD_STOCK_WOOD + 30）
// ★ 第二仓库（远距瞪羚群仓库）的最少瞪羚数门槛（2026-09-07 用户需求"没瞪羚就跳过建造第二仓库"）。
// 判定用"距 TC>20 且 距所有现有 Stock>20"的远距瞪羚数量；低于此数则【完全跳过】（既不建、也不让 needSecondStock 阻塞市场/靶场）。
// 默认 2：为 1 只离群瞪羚花 150 木 + 村民长途跋涉不划算。⚠ 改 1 = 有 1 只就建；改 3+ = 必须成群。
#define MIN_GAZELLE_FOR_SECOND_STOCK 2
// ★ 远距浆果群第二谷仓（2026-09-07 用户需求："除了 TC 附近还有 >=6 丛浆果地的话，在旁边建谷仓，派村民去采集"）
// 浆果 resourceSort = HUMAN_GRANARYFOOD → 交付建筑就是【谷仓】(StaticRes.cpp:NUM_STATICRES_Bush)， 所以在远处浆果群旁建谷仓能直接把往返距离压到 20 格内，比跑回 TC/第一座谷仓高效得多。
#define MAX_GRANARY 2                   // 谷仓上限：1 座服务 TC 附近浆果 + 1 座服务远距浆果群
#define MIN_BUSH_FOR_SECOND_GRANARY 6   // 远距浆果群最少丛数（<6 丛不值得花 120 木）
#define SECOND_GRANARY_TC_MIN_DIST 25   // "TC 之外"判据：浆果群中心须距 TC ≥ 25 格(BL)
#define BUSH_CLUSTER_RADIUS 5           // 浆果群聚类半径(BL)：5 格内的丛算同一片
#define BUSH_NEAR_GRANARY_DIST 20       // 派工放宽：浆果距任一【已建成】谷仓 ≤ 20 格即可派人采集
// ★ 不训练棍棒兵【后期】（2026-09-03 用户要求）：棍棒兵改为由箭塔替代防守，省下食物/人口转向箭塔+复合弓。
// ⚠ 此开关只管【后期三处】：工具时代填线块(3019) / 优先级2.5 廉价填线(3163) / 优先级3 食物溢出爆近战(3181)。 前期过渡用的棍棒兵由下面 ENABLE_EARLY_CLUBMAN 独立控制，两者互不干扰。
#define DISABLE_CLUBMAN_TRAIN true
// ★ 前期棍棒兵过渡：复合弓 15 分钟前停产(COMPOSITE_BOW_MIN_FRAME) + DISABLE_CLUBMAN_TRAIN 关了兵营 ⇒ 前 15 分钟零自产兵力 （只能靠 2 座箭塔 + 祭司感化扛三波，W2 前仅 2 个棍棒兵 → 曾致祭司被杀）。
// 棍棒兵 50 食物、无石头/黄金依赖 ⇒ 不吃复合弓的黄金，是空窗期唯一可行的填线兵。★ 起始 4 分钟（更早会拖慢村民与 800 食升铜器）。
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
                                  // 无论处于何种状态(WALKING 走不到 / 被改派 / 反复卡顿)，   只要该地基仍未完工且本人不在施工 → 判作废(拉黑+释放)，
                                  // 让 manageBuildings 另择新址重建。修"地基永久卡 0% 无人施工"。
#define PENDING_BUILD_TIMEOUT 300 // 建造指令结果迟迟不回的超时(帧)：超时则清掉占位，防止永久虚占名额
#define BUILD_GAP 1              // 建筑间距：候选建筑footprint外扩1格内不得有其他建筑(含敌我)，避免建筑成墙堵死路
#define MELEE_OVERFLOW_FOOD 150      // 后期/反攻"爆近战"食物溢出阈值：食物≥此值才大规模造近战兵(棍棒/方阵)
// ★★★ 2026-09-22 拉扯距离重标定：「撤得开」与「打得到」的平衡 ★★★
// 实测基线（12 局 gsk / 10919 撤退窗口，探针 kite_range_probe.py）：旧退出阈值 R+BREATH = 7+4 = 11 格、落点 R×1.9 = 13.3 格，
//   而自身射程 R = 7 ⇒ **90.3% 的撤退窗口撤出自身射程**（撤完还得走 4~6.3 格才能开火）；窗口间隔中位 60 帧恰好压住旧的
//   60 帧攻击保护期（窗口后 ≤60 帧才拿到同 SN 攻击令的仅 37.8%）⇒ 这就是"拉扯远了打不到"的来源。
// 平衡口径：撤退距离改由【威胁半径】决定、以【自身射程】为硬上限 ⇒ RET_D = clamp(威胁半径 + SAFE_MARGIN, MIN_KEEP, R)，
//   落点 KIT_LAND = min(RET_D + SLACK, R) ≤ R ⇒ 不变量「撤完即在自身射程内」按构造成立：实测「落点 > 自身射程」100.0% → 0.0%。
//   （威胁半径：远程敌 = 其最大射程；近战/村民 = 0，由下方 0.5R 无条件撤退兜底）
// ⚠ 已知副作用（**有意保留，非 bug**）：T_IN = max(0.5R, RET_D − HYST)。对近战靶 RET_D = MIN_KEEP = 5.0 ⇒ T_IN = 0.5R ⇒
//   「敌近提前撤」与「贴脸无条件撤」退化成同一条 ⇒ 拉扯频率大降（窗口 10919→1410，−87%）、停在 SHOOT 段变多（射程内占比 22.6%→55.7%）。
// ⚠ 本图(map3.njust) 敌方全近战 + 塔：1410 个窗口 100% 是近战靶 ⇒ **远程分支只能解析推导、本图无法实测**（需换含敌弓兵/投石兵的关卡）。
//   调参：要"更早撤"抬 KITING_MIN_KEEP（T_OUT/T_IN 一起抬），勿改 0.5R 兜底线；要双侧余量把 SAFE_MARGIN 2.0→1.0。
#define KITING_SAFE_MARGIN   2.0   // 脱离威胁射程后的安全余量(格)
#define KITING_MIN_KEEP      5.0   // 撤退后至少保持的距离(格)：防贴脸，同时不越过自身射程
#define KITING_HYST          2.0   // 迟滞带宽度(格)：T_IN = T_OUT − 本值，必须为正否则"一撤就被打回"
#define KITING_LANDING_SLACK 0.5   // 撤退落点相对退出阈值的余量(格)：确保落点真的越过 T_OUT
// ★★★ 2026-09-13 方阵兵编制比例（用户要求"放宽方阵兵数量"，选定 3:4 温和档）★★★
// 上限公式：hop < HOPLITE_RATIO_NUM/DEN × comp + FLOOR（旧版硬编码 (comp+4)/2 ⇒ 长期趋近 1:2；新版 3/4×comp+2 ⇒ 趋近 3:4）
// 逐点对照(comp→hop上限)：0→2 / 2→3 / 4→5 / 6→6 / 8→8 / 10→9 / 20→17 / 40→32（comp≤2 时与旧版一致，不断肉盾）。
// ★ 同时作用于【反攻期】与【后期(lateGame)】两条方阵产线；黄金预留策略保持严格不变。
#define HOPLITE_RATIO_NUM   3    // 比例分子：hop 上限 ≈ comp × NUM/DEN
#define HOPLITE_RATIO_DEN   4    // 比例分母
#define HOPLITE_RATIO_FLOOR 2    // 保底基数：comp=0 时也先出 2 个方阵挡刀（与旧版一致）
// ★ 反攻期兵种编制（2026-09-02 用户要求）：反攻**只训练 复合弓兵(主) + 方阵兵(副)**，不训练其他兵种。
// 原因：旧逻辑里骑兵(70食+80金)与棍棒兵(50食)会抢占复合弓兵(40食+20金)的资源与人口，   骑兵单次吃掉 4 个复合弓兵的黄金 → 复合弓兵判据长期不过 → 退化成普通弓兵/停产。
#define DISABLE_CAVALRY_TRAIN true  // 全局不训练骑兵【主力】(骑兵/战车等)：性价比低且严重挤占复合弓兵黄金
// ★ 远程兵最早训练时间 COMPOSITE_BOW_MIN_FRAME（2026-09-06 用户要求「15min 前先不训练复合弓兵，避免被打死」）：
// 早期弓兵会被打死、白费食物 + 20 黄金 ⇒ 资源全留给村民/铜器升级/复合弓科技。用户已选【完全停产】（连普通弓兜底也停）。
// 注意：只停产【造兵】，不影响靶场建造与科技研究 —— 靶场闲置反而更利于科技判据(Project==ACT_NULL)。
#define COMPOSITE_BOW_MIN_FRAME 22500   // 15 分钟 × 1500 帧/分钟 = 22500 帧
// ★ 探路先锋（2026-09-03 用户改需求）：不再造侦察骑兵，改派【感化的战车弓兵(优先,SPEED 4.07)或投石车(视野13)】
// 去探路。未探明敌基地时，这些单位快速奔袭敌基地方向 → 探到 enemy_buildings → 点亮 enemyBaseScouted → 大部队直接全图寻路直达，省去逐格摸索。故侦察骑兵训练开关设 false。
#define ENABLE_SCOUT_RECON false
// ★ MIN_ARMY 2026-09-07 由 20 下调到 12（用户实测驱动）：反攻态已由 updateState 在「三波全清 / frame>27000 强制」时进入，
// 此时敌方主力已被消灭，再等 20 人无意义；而实测军队长期停在 12 人左右（复合弓 15 分钟前停产 + 战损）⇒ readyToAttack 恒 false
// ⇒ ① kiting 整段被跳过（"反攻时不会后撤"）② 全军被反复 HumanMove 回 TC 同一点。   ⚠ 改小=更早推进更零散；改大=更保守但等更久（24 分钟强制兜底仍在）。
#define COUNTER_ATTACK_MIN_ARMY 12   // ★ 全体反攻门槛：非祭司军队(含远程/近战/投石车)≥此数才一起反攻，避免单个士兵零散冲出被集火
#define COUNTER_ATTACK_FORCE_TIME 33000 // 22分钟强制反攻(=33000帧,1500帧/分钟)：即使人数不足也一起进攻
                                        // ★ 2026-09-14 用户要求「提早反攻的时机 2 分钟」⇒ COUNTER_ATTACK_FORCE_TIME 36000→33000。
                                        // 实测（ce1~8）：发现武器厂中位 42743→40166（提前 1.7 分）；祭司死亡率 25%→25% 未恶化。
                                        // 反攻【唯一】触发路径是超时（40 局全 frame=36001，MIN_ARMY=12 从未达标）⇒ 改常量确定生效。
                                        // ⚠ 2026-09-14 lj 轮回滚曾误把本值连带撤回到 36000 ⇒ 今后回滚务必核对本常量。
// ★★★ 2026-09-19 用户需求：「反攻时 27 分钟派所有农民进攻敌方基地」⇒ FARMER_ATTACK_TIME = 40500 帧 ★★★
// 目标三级：① 敌方 TC > ② 最近的【软目标】敌建筑 (非箭塔/非武器厂) > ③ 最近的【箭塔】（本图敌方无 TC，靠 ③ 才可达）； 全部不可见 → 行军到 enemyBaseScouted 记忆方位；仍无则不动。
// ⚠ 绝不把武器厂当目标：exam 胜条件唯一 = 祭司感化敌方武器厂，农民拆了它 = 自毁胜因（同 ARMY_IGNORE_SIEGE_WORKSHOP）。
// ⚠ 与 COUNTER_ATTACK_FORCE_TIME(33000/22分) 配合：22 分军队强制反攻，27 分农民跟上。 ⚠ 不排除 buildingFarmerType 里的农民（用户要求"所有"）⇒ 未完工建筑会烂尾。
#define COUNTER_FARMER_ATTACK true
#define COUNTER_FARMER_ATTACK_FRAME 40500   // 27 分钟 × 1500 帧/分钟
#define COUNTER_FARMER_ATTACK_GAP 90        // 同一农民的重复下发节流(帧)：防幂等判据失效时刷屏，
                                            // 重发会 reset 引擎攻击关系并打断动作(铁律 14)
// ★ 祭司护驾三级半径(格)：祭司死=立刻失败，故护驾优先于士兵自卫/守家/前出等一切军事行为
#define PRIEST_GUARD_URGENT 8.0   // 紧急：敌进入祭司此半径 → 所有兵(可打断战斗)立即回防
#define PRIEST_GUARD_ALERT  15.0  // 预警：敌进入祭司此半径 → 空闲/行军兵前往护驾(不打断正在战斗的兵，防反复横跳)
#define PRIEST_GUARD_RECALL 30.0  // 召回上限：只调距祭司此半径内的兵回防(避免把反攻大军从全图拉回)
#define PRIEST_GUARD_MAX_CMDS 12  // 护驾指令每帧上限(独立于普通 attackCmds，保证护驾不被限流饿死)
// ★ 祭司感化目标选取范围(格)：从 20 扩到 28，让祭司更主动地去感化远处的投石车等高价值目标。 (投石车射程10格、感化射程14格；28格仍在护驾召回半径 PRIEST_GUARD_RECALL=30 内，不会脱离保护。)
#define PRIEST_CONVERT_RANGE 28.0
// ★ 2026-09-12 反攻期祭司安全距离（用户需求"祭司反攻不要太靠前，尽量在安全距离"）： 旧版把祭司推到 target(敌基地)-5格(仅沿 DR 轴退5格)，祭司几乎与大军一起冲到敌基地外5格 → 前线一崩即被秒。
// 新方案：祭司跟随【己方大部队重心】(排除自身)，始终位于大队【后方】(朝 TC 方向) PRIEST_SAFE_BEHIND 格；
// 且强制与反攻目标(敌基地/武器厂)保持 ≥ PRIEST_MIN_DIST_TARGET 格 —— 祭司永远在大部队身后，不单独前出、不冲进敌射程。
#define PRIEST_SAFE_BEHIND     8.0   // 祭司在大队【身后】(朝 TC 方向)的安全距离(格)
#define PRIEST_COUNTER_FLEE_HP 0.6  // 2026-09-13 保祭司：反攻期被远程集火时的撤退血量阈值(<=此值且在敌射程内即撤)
// ★★★ 2026-09-14 感化武器厂的【施法静默期】(帧) ★★★ 铁证：成功案例 lc3 只发 1 次感化令 → 340 帧后收编成功；失败案例 lk6 发 2155 次(每帧重发) → 持续 2150 帧从未收编。
// 机制：`HumanAction(祭司, 建筑)` 是"设置转换目标"，重发 = 引擎每帧被重设目标打断、施法进度永远重置。   ⇒ 发令后必须进入静默期，让引擎把整段施法做完（实测需 ~340~440 帧）。
#define PRIEST_SIEGE_CONVERT_LOCKOUT 400
// ★★★ 2026-09-14 前出感化武器厂：清场半径 / 迟滞锁参数 ★★★ 铁证 ll5/ll6/ll8：已发现武器厂 + 转换冷却 0，但祭司与厂距离恒在 20~28 格（感化射程仅 12 格）⇒ 够不到。
// 根因：旧 localClear 半径 20 格 > 感化射程 12 格 —— 结构死锁：祭司一进 20 格内，守在厂旁的敌人就进半径 ⇒
// localClear 翻假 ⇒ 转"后撤"；一退出 20 格又翻真 ⇒ 转"前出" ⇒ 逐帧交替、净位移≈0、永远够不到 12 格。
// 修 ①：清场半径压到 12 格以下（军队 8 / 箭塔 14），使"前出到 11 格"成为可能；   修 ②：加迟滞锁 priestSiegeApproach，防止半径缩小后仍在边界处逐帧翻转。
#define PRIEST_SIEGE_CLEAR_ARMY_R  8.0   // 清场判据：敌【军队】须距祭司 < 此值才算"未清场"
#define PRIEST_SIEGE_CLEAR_TOWER_R 14.0  // 清场判据：敌【箭塔】须距祭司 < 此值才算"未清场"（塔是静态远程，留更大余量）
#define PRIEST_SIEGE_ABORT_R       4.5   // 迟滞锁解除阈值：敌贴到祭司此半径内 ⇒ 视为真危险，解除前出
#define PRIEST_SIEGE_ABORT_HP      0.35  // 迟滞锁解除阈值：祭司血量低于此值 ⇒ 解除前出（交给保命逻辑）
// ★★★ 2026-09-15「起手保护」：低血 + 敌塔压近 ⇒ 暂不起手 ★★★ 证据（fc/dm/sba/sb 四批 32 局）：祭司共 10 次起手，7 次成功、3 次死于施法期；起手→收编需 ~333~343 帧(≈14 秒)。
// 同批：10 次起手里 9 次敌方箭塔正在射击祭司，且塔基本拆不完 ⇒ "等塔清完再感化" = 永不感化（死锁），
// 故**不设"有塔就不去"的硬闸**（towerlock 轮已证伪两次）。本闸只拦最没希望的一种：**已残血 + 塔就在 14 格内**。
// 半径复用 PRIEST_SIEGE_CLEAR_TOWER_R（同一语义单一真源）。已起手(WorkObjectSN==武器厂)时不打断（中断施法会重置进度）。
#define PRIEST_SIEGE_GUARD_HP      0.45  // 起手血量闸：低于此值且最近敌塔 <= CLEAR_TOWER_R 格 ⇒ 本帧不起手
// ★★★ 2026-09-16 用户需求：「祭司感化武器厂的【唯一】限制条件 = 敌方全部箭塔拆完」★★★ 用户原话：「在敌方全部箭塔拆完后再感化，箭塔拆完意味着敌方军队已全灭」⇒ 只留"塔全拆"一道闸（塔是最后防线）。
// 实测 ps1 `f=44900 [SIEGE-WAIT] alive=0 towers=4` ⇒ 敌兵确实先归零而塔恒在。 ② 判据必须是【全局】敌塔数（不是祭司周边 14 格的局部 localClear），否则等于把塔从 14 格外放过。
// ③ ⚠ 塔数取 info.enemy_buildings，**受 explored||visible 约束** ⇒ 必须叠加【已探明保险】（见下一条注释）。
#define PRIEST_SIEGE_REQUIRE_TOWERS_CLEAR true   // true = 启用「敌塔清够」唯一闸；false = 回退为旧的局部清场
// ★★★ 2026-09-21 用户需求：「剩余 2 座箭塔时祭司就可以感化敌方武器厂了」⇒ 阈值 0 → PRIEST_TOWERS_CLEAR_MAX(=2)。 依据（全库 vf_* 共 40 条 [SIEGE-WAIT]，探针 siewgate_probe.py，本轮实测）：
// ① 40/40 条 dS<=12 ⇒ 祭司【真的走到了】感化射程内（12 格），瓶颈就是这道闸本身， 而不是"门外的前出"⇒ 旧备选方案 A（把前出门改成 localClear）不必要，只放宽本阈值即可；
// ② 40/40 条 alive==0 ⇒ 旧注释的依据「箭塔拆完意味着敌方军队已全灭」成立：被拦下的时刻敌军确实已全灭；
// ③ 可达样本的塔数分布 = 1:27 / 2:6 / 3:3 / 4:4，**towers==0 出现 0 次** ⇒ 旧闸 `==0` 是【结构性死锁】而非概率低 （同 N-1 判断：塔被拆会重建 ⇒ "瞬时归零"在本关卡不可达）；
// ④ 放宽到 <=2 可放行 33/40 = 82%（<=1 则 68%）⇒ 取 2，与用户口径一致。 ⚠ 语义边界：改的是"允许起手"的门槛，不是"塔不用管了" —— 剩余 3/4 座时仍然拦（[SIEGE-WAIT] 日志带 lim= 自描述）。
#define PRIEST_TOWERS_CLEAR_MAX 2   // ★ 2026-09-21：剩余敌箭塔 <= 此值即视为"塔已清够"（原为硬编码 ==0 ⇒ 结构性死锁）
// 已探明保险：要求【当前帧】info.enemy_buildings 里至少有这么多条目，才相信"塔已清够"。   ★★★ 2026-09-17 修复：由 2 改为 1 ★★★
// enemyBldSeenN 是【当前帧列表长度】(受 explored||visible 约束)，**不是历史累计**。而终局状态恰恰是
// "塔被拆光 ⇒ 基地只剩武器厂 1 个建筑" ⇒ seen 必然掉到 1 ⇒ 要求 >=2 等于要求"除武器厂外还剩 ≥1 个建筑"，
// 与"塔全拆"互斥 ⇒ **结构死锁**。铁证 fd4：f=43500 起恒 gT=0 seen=1（祭司 dS=6.9 格、hp=1.00 却不出手），
// 日志 [SIEGE-WAIT] 直接坐实是本保险项在拦；全库 220 条 gT==0 样本中 seen>=2 者 **0 条** ⇒ 上线至今通过率 0%
// （加闸后各批起手均 0；修为 1 后 th6 首次起手并获胜）。   保留 seen>=1 的意义：列表全空(seen=0) 时无法区分"真拆光"与"视野丢失" ⇒ 仍须拦截（保守）。
// 组合语义：①武器厂坐标已持久记忆(ssn!=-1 ⇒ 确实推进过) ②当前仍看得见敌建筑(seen>=1) ③视野内敌塔数 <= MAX ⇒ 放行。
#define PRIEST_TOWERS_CLEAR_MIN_SEEN 1
#define PRIEST_MIN_DIST_TARGET 18.0  // 祭司与反攻目标(敌基地/武器厂)的最小安全距离(格)
// ★★★ 临时封禁开关：改 true→false 即可恢复建造 ★★★
// ★ 2026-09-13 解封（用户要求"解锁马厩和学院，并在后期建造方阵兵"）：马厩 = 学院前置（Development.cpp:804）， 学院 = 方阵兵唯一产线（BRONZEAGE + 60食+40金，无额外科技依赖）。
// 骑兵训练仍由 DISABLE_CAVALRY_TRAIN=true 独立封禁 ⇒ 建马厩不会偷吃复合弓的黄金。回滚：两个宏改回 true。
#define DISABLE_STABLE_BUILD  false   // 2026-09-13 解封：恢复马厩建造（作学院前置；骑兵仍不训练）
#define DISABLE_COLLAGE_BUILD false   // 2026-09-13 解封：恢复学院建造（方阵兵产线，后期即可投产）
#define DISABLE_GRANARY_BUILD false   // 已解封(2026-09-03)：恢复谷仓建造，实现"瞪羚群中间建仓库优先于农场"
// ★ 暂时封禁阔剑科技：引擎解锁条件有 bug——Development.cpp:602-603 把 历史上的引擎 bug（黄金被错传进石头槽）已修正：Development.cpp:602-603/607-608 现写为
// (..._FOOD, 0, ..._GOLD) → 阔剑科技/阔剑兵实际扣 食物+黄金（need_Stone=0）。 仍保留封禁（DISABLE_BROADSWORD_TECH）仅因用户此前"暂不研究该科技"决策；引擎条件已正确，可随时改 false 解禁。
#define DISABLE_BROADSWORD_TECH true  // 暂不研究阔剑科技（引擎条件已修正：现真扣 食物+黄金，解禁只需改 false）
// ★ 箭塔只要"解锁"(BUILDING_GRANARY_ARROWTOWER)，不研究"铜器箭塔升级"
// (BUILDING_GRANARY_ARROWTOWE_UPGRADE，120食物+50石头)——用户要求：解锁即可，不升级。   恢复升级：改 false 即可（两处调用点均已用此开关封禁）。
#define DISABLE_TOWER_UPGRADE true
// ★ 2026-09-06 用户定案：只研究少数几项科技，其余全部封禁。
// ★ 2026-09-13 用户要求：解锁【步兵护甲+鳞甲、弓兵护甲+鳞甲】共四项护甲科技（见下方 ARMOR_* 成本宏）。 各开关与上方 DISABLE_BROADSWORD_TECH / DISABLE_TOWER_UPGRADE 同风格，单独恢复只需改回 false。
#define DISABLE_USETOOL_TECH true         // 仓库·工具使用（100食物，近战+2）—— 仍封禁（用户未要求；其二柄为金属加工 200食+120金）
#define DISABLE_INFANTRY_ARMOR_TECH false // 仓库·步兵护甲链（护甲→鳞甲）—— ★ 2026-09-13 解锁
#define DISABLE_ARCHER_ARMOR_TECH   false // 仓库·弓兵护甲链（护甲→鳞甲）—— ★ 2026-09-13 解锁（此前无独立开关，恒开）
// ★ 仓库护甲链成本（对齐 config.json:126-143，引擎实际扣费口径） 引擎事实：BUILDING_STOCK_UPGRADE_DEFENSE_INFANTRY / _ARCHER 都是"两柄动作"——第 1 次调用 = 护甲(+2)，
// 第 2 次调用 = 鳞甲(再 +2)，同一建筑动作 ID 共用（见 AI接口使用指南.md:352、Building.h:137-158）。 顺序（用户 2026-09-13 定案）：一级先铺满 —— 步兵护甲 → 弓兵护甲 → 步兵鳞甲 → 弓兵鳞甲。
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
// ⚠ 注意：市场【建筑本身】不能停建！`marketReady` 是农场建造的前置闸门 —— 封禁的只是市场里的科技研究。
// ★ 2026-09-12 用户要求：伐木科技（市场·木材加工）提为【解锁类科技最优先】。 判定块已从 TIER3 末尾上移到【铜器后第一个被检查的科技】，越过 `frame < WAVE3_TIME`(14min) 与 `milUnlocked` 两锁。
// 开关 WOOD_TECH_ABSOLUTE_FIRST： true  = 绝对最优先（默认）：食物≥120 且木≥75 即研究，不与复合弓比较（实测 false 档 300 食物门槛把伐木拖后 3~6 分）。
// false = 让路保护：复合弓未研究/排队时需食物同时负担两项 (180+120=300) 才允许插队； ⚠ 实测该门槛过高（铜器后食物常年在 158~257）⇒ 会把伐木压成"永远晚于复合弓"。
#define WOOD_TECH_ABSOLUTE_FIRST true
#define LION_AVOID_RADIUS 10         // 建造选点避开狮子的半径(block)；狮子会攻击靠近的建筑/村民，留缓冲
// ★ 狮子防御（2026-09-01）：引擎事实 Animal.cpp::isMonitorObject —— 狮子只攻击【村民】与【非祭司军队】，
// 不攻击祭司、不攻击建筑；狮子视野 3 格(VISION_LION)、血量 20(BLOOD_LION)，村民单挑必死，须成组出动。
#define LION_THREAT_RADIUS 6    // 狮子距我方任一单位 ≤6 格 → 预警级威胁，派空闲村民猎杀
#define LION_ATTACK_RADIUS 2    // 我方单位已受伤且狮子 ≤2 格 → 判定"正在被咬"，紧急级(可打断采集/赶路)
#define LION_HUNTER_GROUP 4     // 每只威胁狮的猎手目标人数（狮子20血，2个村民打不完还会送命）
#define LION_HUNTER_RANGE 22    // 只派距狮 ≤22 格的村民，避免全图奔波、经济被抽空
#define LION_ARMY_RANGE  4      // 空闲军队距狮 ≤4 格才派（军队战力高，就近秒狮，不抽调远处部队）
#define LION_TASK_FRAMES 300    // 猎狮任务保底时长(帧)：期间不重复下令、不被采集模块抢走(10秒)
#define MIN_GOLD_WORKERS 1      // 至少1人挖金！复合弓兵/阔剑兵/方阵兵/投石车/后勤科技真扣黄金
// ★ 资源停采上限（2026-09-01）：存量达到即停止派/补采该资源，人力转向其他资源
#define STONE_CAP_STOP 300   // 石头≥300 不再采石（2026-09-13 用户需求「再多建一座箭塔」：3座箭塔=开局150石建第1座+额外采300石建第2~3座，故上限300）
// ★ 木头水位沿革（当前值见下方两个宏）： 2026-09-03 用户需求"木头维持150左右、优先食物"⇒ 日常 150（够房屋30/谷仓120/兵营125/靶场150/马厩150/市场150/农场75），省人力投食物。
// 2026-09-12 150→220（多存 70 木覆盖多靶场+学院同时建）。 2026-09-21 220→400（用户需求，见下）。 ⚠ 木头水位不是"越低越省人力"：水位同时是【停采门禁】，水位越低 ⇒ 死区（四门齐关）来得越早。
// ★ 2026-09-21 用户需求「提高木头上限为400」：日常 220→400、反攻期 320→400（两档并档）。 动机（实测，见 aoe3_idle_deadzone_20260921.html）：9~13 分钟出现「四道采集门禁同时关闭」的死区 —
// 木≥220 锁死 / 金（未升铜器 goldTarget 恒 0）/ 石（3 塔满⇒永久停采）/ 食物（浆果3+瞪羚2+农场1 全满员）， 而兜底分支 `if (tree && !woodStop)` 被同一个木闸反杀 ⇒ 村民原地 IDLE（峰值 15/22 = 68%）。
// 抬高木闸的直接效果：木头继续囤到 400 ⇒ 靶场150/学院180/马厩150 这类大额木耗更易被一次性付清， 木耗越快 ⇒ 木位越快跌破上限 ⇒ 死区窗口越短（此为正相关的预期机制，需实测确认，见验证批）。
// ⚠ 两档必须同时抬：`woodStop` 用三目取 LATE 档（frame>=WAVE3_TIME），若只抬日常档， 14 分时上限反而从 400 掉回 320 ⇒ 木位落在 320~400 就会出现新的"到点即回撤"扰动。
#define WOOD_CAP_STOP  400   // 木头≥400 日常停采（2026-09-12 150→220；2026-09-21 用户需求 220→400）
#define WOOD_CAP_STOP_LATE 400 // 反攻准备期(WAVE3_TIME后)木头水位（2026-09-12 250→320；2026-09-21 320→400 与日常并档）
#define WOOD_KEEP_MIN  2     // 木头达上限回撤时保留的伐木工人数
#define GOLD_CAP_STOP  1000  // ★ 黄金≥1000 不再派金工（2026-09-12 800→1000：一场反攻 20 CB + 10 方阵 + 1 投石车 ≈ 800~900 黄金花完，留 100 余量）
                                // ★【2026-09-11 3.0.7f 改】每矿堆 200→400，黄金总量上限同步翻倍(400→800)。 若仍 400，则采完一矿堆就立即触发 goldRich → 黄金被压到 MIN_GOLD_WORKERS，
                                // 矿堆才采一半就转采其他资源 → 效率浪费。     设 800 = 2 矿堆满额 = 实际反攻所需黄金(800)安全储备。
#define FOOD_CAP_STOP  650   // ★ 铜器后：食物≥650 不再派新食物工（2026-09-12 500→650：解 65% 食物 rebalance 后过囤）
#define FOOD_CAP_STOP_PREBRONZE 850 // ★ 铜器前：食物停采阈值提到 850(>800升级费)，否则食物到500就停采、永远攒不够800升铜器
// ★★ 2026-09-13 铜器升级防卡死（修 o3 局整局 UPGRADING / score=224 的根因）： 引擎 Development::get_isBuildActionAble() 对 BUILDING_CENTER_UPGRADE 有硬前置 —— 工具时代须已【建成】
// MARKET/RANGE/STABLE 中至少 2 座，否则直接拒令。旧代码只查 Meat>=800 就发令并立刻 hasUpgraded=true， 被拒后所有升级入口的 !hasUpgraded 守卫全失效 → 永不重试、整局停在 UPGRADING。
#define BRONZE_MIN_AGE_BUILDINGS 2     // 引擎前置：市场/靶场/马厩 已存在数（缺则必然被拒，勿发令）
#define BRONZE_RETRY_INTERVAL 120      // UPGRADING 中指令未被引擎接受时的重试间隔（帧）
#define BRONZE_GIVEUP_FRAMES  3600     // 连续未确认施工超时（帧）→ 退出 UPGRADING 回 DEFENSE_PREP（继续发育/补前置）
#define WOOD_LOW_LINE  100   // 木头<100 判定"缺木"，临时提高伐木工目标
#define WOOD_TARGET_BASE 4   // 常态伐木工目标人数（优先食物，木头只保底）
#define WOOD_TARGET_LOW  8   // 缺木(<WOOD_LOW_LINE)时的伐木工目标人数
// ★ 2026-09-06 砍树选树：树到最近已建成仓库/TC 的距离上限（单位=地图区块 BLOCK）。
// 超过此距离的树一律不派工（宁可让村民干等/转采别的），避免长距离搬运拖垮伐木效率。   若实测"附近树砍光后全员闲置"，适当上调；若仍嫌远，下调到 10。
#define WOOD_MAX_ANCHOR_DIST 15
// ★ 选树评分权重：score = (α·村民→树 + β·树→最近仓库/TC) × 拥挤惩罚 β > α → 锚点距离主导（砍树成本主要在"树↔仓库"的往返搬运，而非村民走过去）。
#define WOOD_SCORE_ALPHA 0.5   // 村民→树 权重（保留约束：避免村民横穿半张地图去砍一棵"离仓库近"的树）
#define WOOD_SCORE_BETA  1.0   // 树→最近仓库/TC 权重（主导项）
// ★【2026-09-11 3.0.7f 改】每棵树最多派 2 个人砍（原为 1，3.0.7f 引擎修了"多人挤同一资源"卡死后放宽）。 一棵树血量 25（原版假设 1 人砍足矣），但实际派 1 人的效率不如 2 人接力；
// 3.0.7e 之前的引擎会让 2 人挤同一棵树相互卡位/原地振动，3.0.7f 修好后 2 人可正常协作，效率 +30~50%。 仍保留 2 人上限（不是 4/8）—— 太多人挤同一树仍然效率低（往返路径重叠、砍光后空跑）。
#define WOOD_MAX_WORKERS_PER_TREE 2   // 单棵树同帧累计工人数上限（3.0.7f: 1→2）
#define GOLD_RICH_TOL   1.25 // 黄金相对 食物:黄金 目标配比的宽容系数：超出 1.25 倍即判定"黄金相对过剩"
// ⛔ 2026-09-18 已实测证伪并撤销的两项尝试（勿重犯）： ① `GOLD_RICH_FOOD_FLOOR 200`（要求食物≥200 才算"黄金相对过剩"）—— 实测全线更差：金工 6.2→5.8、
// 达标 85%→82%、负局 4→7。教训：goldRich 命中的"食物低谷"正是它**该**触发的场景，不是误判 （全库 61/61 命中都在食物<200）。回代要问两遍：命中在哪？**命中在那，合理吗？**
// ② 方案A 配比 5:3 → 5:4（goldTarget 抬 +33%）—— 24 局 vs 24 局，金工 6.4→6.4 **完全无变化**，
// 代价却是食物 −17%、木头 −16%、金矿令 +26%。   根因（逐帧铁证）：中期(14~22分) 引擎实况 `Idle=0` 占 **98.0%**、空闲村民均值 **0.03 人** ⇒
// 黄金派工段只对【空闲村民】生效 ⇒ **根本无人可派**；且 foodStop/woodStop 命中各仅 1.3% ⇒ 无过剩岗位可抽。
// ⇒ 真实分配由「派工优先级顺序 + 资源点容量 + 在岗人员不回撤」决定，`goldTarget` 中期**根本不参与决策**；
// 抬高它只让 `goldWorkers < goldTarget` 更频繁成立 ⇒ 对已在采金者反复下单 ⇒ 命令 +26% 而人数零变化。
// ⇒ 结论：**"提高配比目标"这条路在架构上不成立**（动作日志量 ≠ 实际工作量）。详见 aoe3_goldplan_20260918.html。 现值 5:3 = 复合弓(40食+20金)/方阵(60食+40金) 的纯成本比（黄金需求 ≈ 食物的 50%~67%）。
#define FOOD_GOLD_NUM 5
#define FOOD_GOLD_DEN 3
// ★ 石头保底采集（仅在不达停采上限时生效）：石头现仅用于
// 箭塔(150)/投石兵(10)/铜器箭塔升级(50)/采石科技(50)/建筑维修。   2026-09-13 用户改需求"再多建一座箭塔"：从2→3座需多采150石=总计300石。1人持续采即可
// （边采边建，不是攒齐再建；塔建满后由 STONE_CAP_STOP/towersDone 永久停采）。
#define STONE_WORKERS_LATE 1    // 后期保底采石人数（只需1人采够150石建第2座箭塔）
#define FOOD_PAUSE_TECH_TRAIN 60 // 食物<60暂停科技/训练
#define STUCK_GATHER_TIMEOUT 1500     // 空手且非空闲超时(帧)→判定寻路卡死(60秒)
#define STUCK_BLACKLIST_FRAMES 15000  // 不可达资源拉黑时长(10分钟,到期可重试)
// ============================================================================================
// ★★★ 2026-09-23 OJ(Linux/gcc13) SIGSEGV 自救：快照深拷贝改由"写侧线程"（主线程）执行 ★★★
// --------------------------------------------------------------------------------------------
// 现象：OJ 上 AI 线程在 `info = getInfo()` 处 SIGSEGV（backtrace 行号属 OJ 那一版，与本文件重构后不对应）。
// 根因（本机引擎源码逐行核对）：双缓冲"主线程写、AI 线程读"，唯一互斥 tagGame::Locker 保护不住这条路径 ——
//   ① tagGame::update() 的 QMutexLocker 被注释掉（GlobalVariate.cpp:1117）；② getInfo() 的锁只覆盖引擎自己那层拷贝，
//   调用点（processData）的深拷贝在锁外 ⇒ 与写侧 clear()/push_back() 的释放/重分配竞争 ⇒ memcpy 读到已释放页。
//   引擎侧根治 = 恢复 update() 内的锁（待评测机版本）。UsrAI 侧碰不到 Locker（tagGame 私有成员），
//   改用 tryLock()+getInfo() 会因非递归 QMutex "同线程二次加锁"自锁死（实测整局冻在 frame 1）⇒ 站内靠加锁自救不可行。
// 本修法：不改引擎、不碰锁，只换"深拷贝发生在哪个线程"——
//   UsrAI 由主线程创建（MainWidget.cpp:1540 `UsrAi = new UsrAI();`）⇒ postEvent 给它的事件由主线程派发；
//   AI 线程 postEvent(this) → 主线程在 event() 里 getInfo()（此刻不在 infoShare 内 ⇒ 读写同线程、天然串行）→ 唤醒 AI 取走副本
//   ⇒ 与引擎版本 / NOWPLAYER / Buffer 尺寸无关。
// 兜底：连续 5 帧拿不到快照则退回旧直读路径（宁可保留原崩溃概率，也不让 AI 停摆）；单帧超时 1 秒，绝不死等（AI 线程持有 AI::mutex）。
// ============================================================================================
bool UsrAI::refreshSnapshot(tagInfo& dst) {
    SnapState& st = snapState(this);
    {
        QMutexLocker lk(&st.mutex);
        st.ready = false;
    }

    // 请主线程代取（UsrAI 归属主线程 ⇒ 事件由主线程事件循环处理，QEvent::User+731 为本类专用）
    QCoreApplication::postEvent(this, new QEvent(QEvent::Type(kSnapEventType)));

    bool ok = false;
    {
        QMutexLocker lk(&st.mutex);
        if (!st.ready) {
            st.cond.wait(&st.mutex, 1000);   // 1 秒上限：绝不死等
        }
        ok = st.ready;
        if (ok) {
            swapTagInfo(dst, st.buf);         // 只交换容器所有权，避免 AI 线程再次 memcpy
        }
    }

    if (ok) {
        st.failStreak = 0;
        return true;
    }

    // 主线程回环失联时只跳过本帧；绝不回退到跨线程直读，避免重现 OJ 崩溃。
    ++st.failStreak;
    st.skipCount++;
    return false;   // 本帧不动作（processData 直接返回）
}

// 主线程执行：真正的快照获取。此时主线程不在 infoShare() 内 ⇒ 与写侧天然串行，无需任何锁配合。
bool UsrAI::event(QEvent* e) {
    if (e && e->type() == QEvent::Type(kSnapEventType)) {
        tagInfo fresh = tagUsrGame.getInfo();
        SnapState& st = snapState(this);
        {
            QMutexLocker lk(&st.mutex);
            st.buf = fresh;
            st.ready = true;
            st.mainCount++;
            st.cond.wakeAll();
        }
        return true;
    }
    return QThread::event(e);
}

// processData - 主循环（每帧调用） 规则：祭司保命 > 失败检查 > 阶段切换 > 打猎 > 经济 > 军事 > 反攻
void UsrAI::processData() {
    // ★★★ 2026-09-23 环境自证：必须放在**首次 getInfo() 之前**。理由：OJ 上的崩溃发生在 getInfo() 内部
    //   的深拷贝里，若把诊断放在 getInfo() 之后，那一局就什么线索都留不下。
    //   零新增链接符号：GAME_VERSION / NOWPLAYER / MAXPLAYER 与文件里已在用的 MAP_L / MAP_U /
    //   BLOCKSIDELENGTH 同属 RuntimeConfig 访问器（RuntimeConfig.h:38/51/54/81），已在同一链接单元。
    //   目的：把评测机的**引擎版本 + 运行期玩家数**钉死，用于判定 Core.cpp 的 Buffer0/Buffer1[2]
    //   是否与运行期 NOWPLAYER 不匹配（不匹配 ⇒ currentBuff[i] i>=2 越界 ⇒ 快照被踩 ⇒ 崩在 getInfo）。
    {
        static bool envLogged = false;
        if (!envLogged) {
            envLogged = true;
            DebugText(QString("[ENV] engine=%1 NOWPLAYER=%2 MAXPLAYER=%3 represent=%4")
                      .arg(QString::fromStdString(GAME_VERSION))
                      .arg(NOWPLAYER).arg(MAXPLAYER).arg(NOWPLAYERREPRESENT));
        }
    }

    if (!refreshSnapshot(info)) return;   // ★ 2026-09-23：快照由主线程代取（见上方说明）；未取到则本帧不动作
    frame = info.GameFrame;

    // ★★★ 2026-09-23 机制量自证（每 1500 帧一档，供 OJ 日志核对）★★★
    //   main>0  ⇒ "主线程代取快照"这条替代路径真的在跑（崩溃路径已被换掉）
    //   fallback>0 ⇒ 该环境的主线程事件回环失效，已退回旧直读路径（需另想办法）
    //   skip>0  ⇒ 单帧 1 秒超时、主动放弃的帧数
    {
        static int lastSnapBeat = -1;
        if (frame > 0 && frame / 1500 != lastSnapBeat) {
            lastSnapBeat = frame / 1500;
            DebugText(QString("[SNAP f=%1] main=%2 fallback=%3 skip=%4").arg(frame)
                      .arg(snapState(this).mainCount).arg(snapState(this).fallbackCount).arg(snapState(this).skipCount));
        }
    }

    // ★★★ 2026-09-19 诊断（可观测机制量；UsrAI 自洽，不引用任何引擎新增符号）★★★ 崩溃场景：OJ(Linux/gcc13) 上 AI 线程在 getInfo() 的深拷贝里 SIGSEGV（源 vector len=6/cap=6）。
    // 根因在引擎侧（tagGame::update() 的 QMutexLocker 被注释掉 + infoShare() 的 clear()/push_back() 构成数据竞争）
    // ⇒ **站内修不了**。⚠ 提交范围只有 UsrAI.cpp + UsrAI.h ⇒ 严禁引用引擎新增符号（悬空 extern ⇒ undefined reference ⇒ 整个提交链接失败，比崩溃更严重）。故本诊断只依赖 UsrAI 自身可观测的两条判据：
    // (a) 已跑过非 0 帧、却收到 GameFrame==0 —— 加固版引擎拦下脏快照时返回默认 tagInfo（GameFrame 恒 0）； (b) 帧号回退（本帧 < 上帧）—— 读到过期/错乱 buffer 的直接迹象，原始引擎下同样有效。
    // 崩溃后查 ait 里最后一条 [DIRTY-SNAP] 的计数：>0 ⇒ 证明"读到的快照确实异常"。
    {
        static int localDirtySnap = 0;
        static int lastNonzeroFrame = 0;
        static int lastBeatBucket = -1;
        const int curF = info.GameFrame;
        if (curF > 0) {
            if (lastNonzeroFrame > 0 && curF < lastNonzeroFrame) localDirtySnap++;  // (b) 帧号回退
            lastNonzeroFrame = curF;                                                // 正常快照：推进基准帧
        } else if (lastNonzeroFrame > 0) {
            localDirtySnap++;                                                       // (a) 空快照
        }
        // 每分钟一行心跳（lastNonzeroFrame 不动时不重复打，防刷屏）
        if (lastNonzeroFrame > 0 && lastNonzeroFrame / 1500 != lastBeatBucket) {
            lastBeatBucket = lastNonzeroFrame / 1500;
            DebugText(QString("[DIRTY-SNAP f=%1] 累计脏快照拦截=%2").arg(lastNonzeroFrame).arg(localDirtySnap));
        }
    }

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

    // ★ 战/反攻期间强制结束探路：探路模块只在 !isWar && state != COUNTERATTACK 时驱动祭司， 而 managePriest 又要求 scoutPhase>=20 才运行 → 开战时若探路未完，祭司两头都不管，
    // 被敌人贴脸也一动不动（表现为"敌人来了祭司也不跑"）。开战即结束探路，交还祭司管理保命。
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

// ★★ 铜器升级辅助（2026-09-13 防卡死）：引擎 Development::hasAgeUpgradeBuildings(CIVILIZATION_TOOLAGE) 要求
// MARKET/RANGE/STABLE 中至少 BRONZE_MIN_AGE_BUILDINGS 座【已建成】，否则 get_isBuildActionAble() 直接拒令。
// 此处用 AI 侧 countBuildingsExisting 逼近该前置（它把在建地基/90 帧内新下发的建造令也算入 ⇒ 属"乐观"判据， 仅作发令前预检）；真正的成功判据仍是引擎回写 tc->Project == BUILDING_CENTER_UPGRADE。
int UsrAI::countAgeUpgradeBuildings() {
    int n = 0;
    if (countBuildingsExisting(BUILDING_MARKET) > 0) n++;
    if (countBuildingsExisting(BUILDING_RANGE)  > 0) n++;
    if (countBuildingsExisting(BUILDING_STABLE) > 0) n++;
    return n;
}

// 铜器升级统一发起入口：所有状态（EARLY_ECONOMY / DEFENSE_PREP / WAVE1 / WAVE2）与 UPGRADING 重试共用。返回 true = 本帧确实发出了升级令（或引擎已在施工）。
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

// 阶段切换（改进版：更稳健的状态转换）
void UsrAI::updateState() {
    switch (state) {
    case EARLY_ECONOMY: {
        // ★ 食物够800且引擎前置(市场/靶场/马厩≥2座)满足 → 统一入口发令 （旧版只查 Meat>=800 就发令并立刻 hasUpgraded=true，被引擎拒后永不重试 → 整局卡 UPGRADING）
        if (tryStartBronzeUpgrade()) {
            state = UPGRADING;
            DebugText(QString(">> Upgrading to Bronze Age! Frame=%1, Meat=%2, Farmers=%3, ageBld=%4").arg(frame).arg((int)info.Meat).arg((int)info.farmers.size()).arg(countAgeUpgradeBuildings()));
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
            DebugText(QString("!! BRONZE-RETRY f=%1 issued=%2 try#%3 stall=%4 meat=%5 tcProj=%6 ageBld=%7(m%8 r%9 s%10)").arg(frame).arg((int)issued).arg(bronzeAttemptCount).arg(bronzeStallFrames)
                .arg((int)info.Meat).arg(tc ? tc->Project : -99).arg(countAgeUpgradeBuildings()).arg(countBuildingsExisting(BUILDING_MARKET)).arg(countBuildingsExisting(BUILDING_RANGE))
                .arg(countBuildingsExisting(BUILDING_STABLE)));
        }
        // ④ 兜底：长时间无法开工 → 退出 UPGRADING，恢复常规状态机（继续攒资源 + 补建前置建筑），    后续 WAVE1/WAVE2/PREP 入口会自然再次尝试，绝不会像旧版那样整局卡死。
        if (bronzeStallFrames >= BRONZE_GIVEUP_FRAMES) {
            hasUpgraded = false;
            bronzeIssuedFrame = -999999; bronzeAttemptCount = 0; bronzeStallFrames = 0;
            state = DEFENSE_PREP;
            DebugText(QString("!! BRONZE-GIVEUP f=%1 → DEFENSE_PREP (need %2 of MARKET/RANGE/STABLE, have m%3 r%4 s%5)").arg(frame).arg(BRONZE_MIN_AGE_BUILDINGS)
                .arg(countBuildingsExisting(BUILDING_MARKET)).arg(countBuildingsExisting(BUILDING_RANGE)).arg(countBuildingsExisting(BUILDING_STABLE)));
        }
        break;
    }

    case DEFENSE_WAVE1:
        // ★ 食物够800且引擎前置满足 → 统一入口发令（含防卡死重试）
        if (tryStartBronzeUpgrade()) {
            state = UPGRADING;
            DebugText(QString(">> WAVE1 Bronze Age! Frame=%1, Meat=%2, ageBld=%3").arg(frame).arg((int)info.Meat).arg(countAgeUpgradeBuildings()));
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
        // ★ 必须 break：旧版发令后继续落回下方波次检测，会把刚设的 UPGRADING     立刻覆盖成 DEFENSE_WAVE1/2/3，导致升级状态机永远进不去。
        if (tryStartBronzeUpgrade()) {
            state = UPGRADING;
            DebugText(QString(">> LATE Bronze Age! Frame=%1, Meat=%2, ageBld=%3").arg(frame).arg((int)info.Meat).arg(countAgeUpgradeBuildings()));
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
            DebugText(QString(">> W2 Bronze Age! Frame=%1, Meat=%2, ageBld=%3").arg(frame).arg((int)info.Meat).arg(countAgeUpgradeBuildings()));
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
        // 第三波必须全部消灭；【修正 2026-09-08】+ COUNTER_ATTACK_FORCE_TIME 对齐，下方两处强制反攻都用同阈值， 避免在 14~24 分钟(集结期)期间被敌数 < 3 假条件骗进 COUNTERATTACK。
        if (frame > COUNTER_ATTACK_FORCE_TIME) {
            int eCount = info.enemy_armies.size() + info.enemy_farmers.size();
            if (eCount < 3 || frame > COUNTER_ATTACK_FORCE_TIME + 6000) {
                state = COUNTERATTACK;
                DebugText(QString(">> ALL WAVES DEFEATED! Counterattack! Frame=%1").arg(frame));
            }
        }
// 超时强制反击：与 COUNTER_ATTACK_FORCE_TIME 对齐。   【修正 2026-09-08】原 27000 帧(18 分钟) 与反攻内部门槛不一致 → 用户实测 19 分钟就触发反攻，
// armyCount 远未达 12 即提前全军出击、零散士兵+祭司被集火送命。⇒ 对齐后给 W3~CounterAttack 留足集结时间。
        if (frame > COUNTER_ATTACK_FORCE_TIME && state == DEFENSE_WAVE3) {
            state = COUNTERATTACK;
            DebugText("!! Force COUNTERATTACK (timeout)");
        }
        break;

    default: break;
    }
}

// 祭司管理（W1感化刀斧兵 > 反攻感化 > 逃跑保命 > 治疗）
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

    // ★ 2026-09-15 去重（铁律 21/26）：远程兵种判定 + "该敌对我的威胁半径"原先在
    // 【感化目标选择】/【威胁扫描 chkThreat】/【逃跑 priestFlee 的威胁收集】三处各写一遍，   改一处漏一处即口径分叉。此处收口为两个 lambda。
    // ⚠ 威胁半径口径：远程(弓/战车弓/复合弓/投石兵/投石车)≈12 格；近战≈2.5 格（贴身）。
    // ⚠ 口径提示：本集合 = 文件头 sortIsRanged(s) 【再排除投石车 AT_STONE_THROWER】——
    //   投石车在此单独判（威胁半径同为 12 格，见下一行）。两处形状相同属历史遗留，
    //   若要收口请统一走 sortIsRanged()（铁律 21/26），改一处别忘了另一处。
    auto isRangedSort = [&](int s) -> bool {
        return s == AT_BOWMAN || s == AT_CHARIOT_ARCHER ||
               s == AT_COMPOSITE_BOWMAN || s == AT_SLINGER;
    };
    auto enemyThreatRange = [&](int s) -> double {
        return (isRangedSort(s) || s == AT_STONE_THROWER) ? 12.0 * BL : 2.5 * BL;
    };
    // ★ 2026-09-15 去重：落点的【己方】占用判据（建筑 2.5 格 / 我方军队 2.0 / 我方村民 2.0）。 两处共用：occupiedLanding（前出感化落点）与 badLanding（逃跑落点）。原先各抄一份（铁律 26）。
    auto ownOccupied = [&](double x, double y) -> bool {
        for (auto &b : info.buildings)
            if (calDistance(x, y, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL) < 2.5 * BL) return true;
        for (auto &a : info.armies)
            if (a.SN != priestSN && calDistance(x, y, a.DR, a.UR) < 2.0 * BL) return true;
        for (auto &f : info.farmers)
            if (calDistance(x, y, f.DR, f.UR) < 2.0 * BL) return true;
        return false;
    };

    // ★ 落点合法性过滤：目标格被建筑/单位占据时引擎判定移动失败（"被占据/不可达"）→单位原地不动、 每次冷却到期又重发同一坐标刷屏。所有祭司移动指令的落点都必须先过这一关。
    auto occupiedLanding = [&](double x, double y) {
        if (ownOccupied(x, y)) return true;
        for (auto &e : info.enemy_armies)
            if (calDistance(x, y, e.DR, e.UR) < 4.0 * BL) return true;
        for (auto &e : info.enemy_farmers)
            if (calDistance(x, y, e.DR, e.UR) < 4.0 * BL) return true;
        return false;
    };

    // ★ 2026-09-15 去重（铁律 21/26）：治疗落点合法性（地图边界 + 己方建筑 2.5 格 + 敌单位 2.0 格）。 原先在【趋近治疗】与【闲时治疗】两档各写一份（后者注释还自称"同 healLandOk"）。
    // ⚠ 2.0 格是 2026-09-12 从 4.0 格收紧后的值：伤兵几乎总在交火线上，4.0 格会把所有落点 判否(实测 4013 帧 0 次治疗)；2.0 格仍在近战贴身(≈1 格)之外，允许靠近交火线救人。
    auto healLandingOk = [&](double x, double y) -> bool {
        if (x < 0 || y < 0 || x > MAP_L * BL || y > MAP_U * BL) return false;
        for (auto &b : info.buildings)
            if (calDistance(x, y, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL) < 2.5 * BL) return false;
        for (auto &e : info.enemy_armies)
            if (calDistance(x, y, e.DR, e.UR) < 2.0 * BL) return false;
        for (auto &e : info.enemy_farmers)
            if (calDistance(x, y, e.DR, e.UR) < 2.0 * BL) return false;
        return true;
    };

// ★ 2026-09-15 去重：选"最该治的伤兵"= 血量比最低者，同血取近者（原先两档各写一份筛选循环）。 maxRatio    ：只治血量比低于该值的友军（趋近档 0.8=只救明显重伤；闲时档 0.9=本职治疗）。
// counterRule ：闲时档在反攻期只认重伤(<50%)，避免祭司回头追基地里的轻伤单位而滞留不推进；趋近档不带此规则。 输出 outRatio = 命中伤兵的血量比（未命中时 1.0，与原文初值一致，供日志使用）。
    auto pickHealTarget = [&](double maxRatio, bool counterRule,
                              double &outDR, double &outUR, double &outRatio) -> int {
        int bestSN = -1; double worst = 1.0, bestD = 1e12;
        outDR = 0; outUR = 0;
        for (auto &a : info.armies) {
            if (a.SN == priestSN) continue;              // ★ 铁律：绝不把祭司自己当治疗目标(=自毁)
            if (a.MaxBlood <= 0 || a.Blood <= 0) continue;
            double r = (double)a.Blood / a.MaxBlood;
            if (r >= maxRatio) continue;
            if (counterRule && inCounter && r >= 0.5) continue;
            double d = calDistance(pDR, pUR, a.DR, a.UR);
            if (d > 25.0 * BL) continue;                 // 太远不追，防送命/离 TC 过远
            if (r < worst || (r == worst && d < bestD)) {
                worst = r; bestSN = a.SN; bestD = d; outDR = a.DR; outUR = a.UR;
            }
        }
        outRatio = worst;
        return bestSN;
    };

// ★ 2026-09-15 去重：贴到伤兵身边。落点 = 伤兵身后 0.6 格，再沿垂直方向 0/±1/±2 格微调，取首个合法落点
// （治疗射程极短：引擎 Core_List.cpp 仅校验 isAttackable 标志、无距离判定 ⇒ 必须贴到 ≈0.6 格才发得出治疗令）。
// allowFallback：5 档全被否时是否"强行贴近"——闲时档 true（伤兵总在交火线上，不贴上去治不到，且已保证非濒死）；趋近档 false。
    auto moveAdjacentToAlly = [&](double allyX, double allyY, double dist, bool allowFallback) -> bool {
        double ux = (allyX - pDR) / dist;
        double uy = (allyY - pUR) / dist;
        const double OFF[5] = {0.0, 1.0, -1.0, 2.0, -2.0};
        int bestO = 0; double bestClear = -1e18;
        for (int o = 0; o < 5; ++o) {
            double cx = allyX - ux * 0.6 * BL - uy * OFF[o] * BL;
            double cy = allyY - uy * 0.6 * BL + ux * OFF[o] * BL;
            cx = max(0.0, min((double)MAP_L * BL, cx));
            cy = max(0.0, min((double)MAP_U * BL, cy));
            if (healLandingOk(cx, cy)) { HumanMove(priestSN, cx, cy); return true; }
            if (!allowFallback) continue;
            double clear = 1e12;
            for (auto &e : info.enemy_armies)
                clear = std::min(clear, calDistance(cx, cy, e.DR, e.UR));
            for (auto &e : info.enemy_farmers)
                clear = std::min(clear, calDistance(cx, cy, e.DR, e.UR));
            if (clear > bestClear) { bestClear = clear; bestO = o; }
        }
        if (!allowFallback) return false;
        double cx = allyX - ux * 0.6 * BL - uy * OFF[bestO] * BL;
        double cy = allyY - uy * 0.6 * BL + ux * OFF[bestO] * BL;
        cx = max(0.0, min((double)MAP_L * BL, cx));
        cy = max(0.0, min((double)MAP_U * BL, cy));
        HumanMove(priestSN, cx, cy);
        return true;
    };

    auto findConvertTarget = [&](double dr, double ur, double range) -> int {
// ★ 转化优先级（2026-09-12 用户连续需求）：① 方阵兵(AT_HOPLITE，转来即反骑主力) → ② 其余近战(贴身 2.5 格，威胁祭司性命)
// → ③ 远程军队(削输出) → ④ 投石车(慢，不直接威胁祭司) → 兜底：最近敌方村民。   ⚠ 前四档的循环体完全相同（"同型里选血量最高者，同血取近者"），原先各写一份共 ~50 行；
// 收口为 pickByBlood(mode)，筛选条件用显式 mode 区分（不改变任何一档的判定与顺序）。
        auto pickByBlood = [&](int mode) -> int {
            int bSN = -1, bBlood = -1; double bD = 1e12;
            for (auto &e : info.enemy_armies) {
                if (e.Blood <= 0) continue;
                bool want;
                switch (mode) {
                    case 0:  want = (e.Sort == AT_HOPLITE); break;                        // 方阵兵
                    case 1:  want = (e.Sort != AT_HOPLITE && e.Sort != AT_STONE_THROWER &&
                                     !isRangedSort(e.Sort)); break;                       // 其余近战
                    case 2:  want = (e.Sort != AT_HOPLITE && e.Sort != AT_STONE_THROWER &&
                                     isRangedSort(e.Sort)); break;                        // 远程军队
                    default: want = (e.Sort == AT_STONE_THROWER); break;                  // 投石车
                }
                if (!want) continue;
                double d = calDistance(dr, ur, e.DR, e.UR);
                if (d > range) continue;
                if (e.Blood > bBlood || (e.Blood == bBlood && d < bD)) {
                    bBlood = e.Blood; bSN = e.SN; bD = d;
                }
            }
            return bSN;
        };
        int t;
        if ((t = pickByBlood(0)) >= 0) return t;   // 0) 方阵兵最高优先
        if ((t = pickByBlood(1)) >= 0) return t;   // 1) 其余近战（保命）
        if ((t = pickByBlood(2)) >= 0) return t;   // 2) 远程军队
        if ((t = pickByBlood(3)) >= 0) return t;   // 3) 投石车降为第四
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
    // → 祭司原地刷屏、永远走不进感化距离(表现为"一直移动却不动+不感化")。   ★ 用户要求"能感化直接感化"：已移除"身处威胁不主动迎敌"守卫——冷却好了就朝感化目标靠近。
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
            chkThreat(e.DR, e.UR, enemyThreatRange(e.Sort));
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
    // ★ 祭司逃跑（v7）：螺旋避障+朝安全区+卡死检测；节流(冷却期内不重发)+状态判定死锁(下发的点被引擎拒收→ 祭司仍是 IDLE 且离该点远→换下一扇区)。根治"每帧重发同一不可达点刷屏、一直移动却不动"。
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
            double r = enemyThreatRange(e.Sort);
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
// ★ 逃跑安全锚点（2026-09-03 用户需求"绕着箭塔走"）：优先朝【最近己方箭塔】跑(≤30格)，无箭塔/太远则退回 TC。 箭塔既是掩体(挡在祭司与追兵之间)又是火力点(追兵进 8 格射程被打)，比一味跑回 TC 更有效。
// ★ 2026-09-04 加安全过滤：若所有可用箭塔都被围攻(在威胁射程内+4)，仍退回 TC —— 否则祭司朝"正在被攻的箭塔"跑 → 深入敌火送命。
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
// ★★ 2026-09-13 保祭司（本轮第 1 瓶颈：祭司死亡率 43.8%）· 落点粘滞 ★★ 旧逻辑每 18 帧(cooldown) 用【当前】威胁集合重算 baseAng 与落点；敌人一移动合力方向就可能整体翻转 →
// 落点从地图一侧跳到另一侧 → 祭司 A→B→A 往返、净位移≈0，被多个远程单位围在原地打死。 修：上次落点【仍安全】(不在任何威胁射程+1 格内、未被占用) 且祭司【尚未抵达】(>3 格) → 直接沿用，不重算。
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
        // 死锁检测(基于"下发点是否被引擎拒收"):上一帧下发 flee 点后,本帧祭司仍是 IDLE 且离该点>2格 → 说明该落点不可达/被占(引擎拒收、祭司原地不动)→换下一扇区重试;若已抵达/正在接近→重置。
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
            if (ownOccupied(x, y)) return true;   // 己方建筑/单位占用（与 occupiedLanding 共用同一判据）
            for (int t = 0; t < nT; ++t)
                if (calDistance(x, y, thX[t], thY[t]) < thR[t]) return true;  // 仍在威胁射程内→不安全
            return false;
        };
        // 扫描 24 方向(±165°,15°/档) × 7 半径:挑"完全安全(逃出所有威胁射程)且最靠近TC"的落点; 若无一完全安全,挑"相对最安全(离威胁射程余量最大)"的。从 priestFleeTry 起旋转,卡死时换扇区。
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
        // 彻底卡死(已轮换全部24扇区仍原地不动)→本帧不再发令,长冷却静默待命,避免刷屏;   下帧逻辑(感化/待命)仍可接管,不再死磕同一不可达点。
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
            DebugText(QString("Priest FLEE hp=%1 safe=%2 dAnchor=%3").arg((priest->MaxBlood > 0 ? (double)priest->Blood / priest->MaxBlood : 1.0), 0, 'f', 2)
                      .arg(foundSafe ? 1 : 0).arg(bestAnchor / BL, 0, 'f', 0));
    };


    // ★ 祭司引导中(WORKING=感化/治疗引导、ATTACKING)→绝不下发新命令打断引导。
    // 感化是"随机时段"的引导过程，期间 ConvertCooldown 仍为0；若此时重发   HumanAction/移动命令，引导会被打断重来→永远转不完(本次bug"一直设置转换目标却没感化")。
    // 唯一例外：残血(≤0.25)强制打断逃命(祭司死=立刻失败，保命高于感化)。
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
            DebugText(QString("Priest st=%1 hp=%2 nearE=%3 threat=%4 mode=%5 | ally=%6 wound25=%7 nearAlly=%8BL cd=%9").arg(priest->NowState).arg(pBR, 0, 'f', 2)
                      .arg(nearestE / BL, 0, 'f', 1).arg(threatDist / BL, 0, 'f', 1).arg(priestMode).arg(nAlly).arg(nWound).arg(nearAlly / BL, 0, 'f', 1).arg(priestMoveCooldown));
        }
        auto locateNearest = [&](double &ox, double &oy) {
            ox = 0; oy = 0;
            if (nearestE >= 1e11) return;
            for (auto &e : info.enemy_armies)
                if (calDistance(pDR, pUR, e.DR, e.UR) <= nearestE + 0.01) { ox = e.DR; oy = e.UR; return; }
            for (auto &e : info.enemy_farmers)
                if (calDistance(pDR, pUR, e.DR, e.UR) <= nearestE + 0.01) { ox = e.DR; oy = e.UR; return; }
        };
        // 感化检测(无安全门槛)：冷却好+视野内有可感化敌(≤28格=PRIEST_CONVERT_RANGE)即可，直接感化/靠近感化。⚠ 旧注释写"≤20格"与常量不符，09-24 已订正。   ★ 用户要求"不用安全感化，能感化直接感化"：感化绝对优先，不再要求逃出敌射程、
        // 不再看血量——冷却好了就转(贴身敌≤3时转走攻击者本身往往就是最好的保命)。
        int safeConv = -1;
        if (priest->ConvertCooldown <= 0 && nearestE <= PRIEST_CONVERT_RANGE * BL) {
            int t = findConvertTarget(pDR, pUR, PRIEST_CONVERT_RANGE * BL);
            if (t >= 0) safeConv = t;
        }
        // 1) ★ 感化无条件最高优先（用户要求：不用安全感化，能感化直接感化）：    附近(≤28格=PRIEST_CONVERT_RANGE)有可感化敌→直接感化或靠近感化。
        // 冷却好即转：不看血量、不要求逃出敌射程——贴身敌≤3时转走攻击者本身往往就是最好的保命；    即便上帧在逃(priestMode==1)也优先转，彻底消除"该感化却只逃"的问题。
        int convSN = -1; double convDR = 0, convUR = 0;
        if (safeConv >= 0) {
            convSN = safeConv;
            for (auto &e : info.enemy_armies) if (e.SN == convSN) { convDR = e.DR; convUR = e.UR; break; }
            if (convDR == 0 && convUR == 0)
                for (auto &e : info.enemy_farmers) if (e.SN == convSN) { convDR = e.DR; convUR = e.UR; break; }
        }
        if (convSN >= 0) {
            // ★ 节流闸(本次bug根因)：感化引导期间 ConvertCooldown 仍为0，若无此闸会每帧
            // 重发 HumanAction 把引导反复打断重来，转换永远完不成。冷却期内绝不再发令。   拒收检测：下发感化后≥15帧祭司仍是 IDLE 且目标未变→指令被引擎拒收
            // (真在引导会进入 WORKING 被上方 canAct 闸拦住)→提前放行重发，不白等150帧。
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
// ==== 以下均为"无法感化"(冷却中/视野内无目标)时才轮到的保命/待命逻辑 ==== 2) ★ 强制撤退闸：仅【残血 pBR≤0.25】才无条件逃命。
// ⚠ 不可加 `nearestE <= 3*BL ||` 之类的 OR：贴脸时血量往往还高，加 OR 会抢先 fled → 压制下方两档治疗 → 观感"祭司不满血就不治友军"。正常贴脸由下方"威胁射程+2"的 flee 闸（第4步）接管。
// ★ 治档铁律：治疗只能用 `HumanAction(priestSN, allySN)`（Core.cpp:1117-1121 判定祭司对同阵营人类走"治疗"） ；目标 SN 绝不能是祭司自身；HumanBuild/Upgrade 都不是入口。
        if (pBR <= 0.25) {
            double feDR = 0, feUR = 0; locateNearest(feDR, feUR);
            priestMode = 1; priestFlee(feDR, feUR); return;
        }
// ★ 2.5) 主动趋近治疗重伤友军（即便自身未满血，只要不在即时危险中就该去救人）。 【根因·再修 2026-09-08】原判据 `threatDist > nearestThreatR + 2` 在反攻/混战中永远不成立
// （祭司跟军→一直被远程射程覆盖）→ 治档 100% 走不到；"满血才治"完全是视觉错觉。   改：只看"是否被任意近战敌人贴身"(<4 格)，远距离交战允许治友军（治疗射程≈0.6 格，必须贴脸）。
// 【保命红线】(缺一不可)：pBR>0.25（濒死仍归顶部 canAct 闸强制逃命）+ 不被近战贴身(<4 格)。
        {
            bool closeQuarters = false;
            for (auto &e : info.enemy_armies)
                if (calDistance(pDR, pUR, e.DR, e.UR) < 4.0 * BL) { closeQuarters = true; break; }
            if (priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0 && pBR > 0.25 && !closeQuarters) {
                double allyDR = 0, allyUR = 0, worstRatio = 1.0;
                int needAlly = pickHealTarget(0.8, false, allyDR, allyUR, worstRatio);
                if (needAlly >= 0) {
                    double bestAllyDist = calDistance(pDR, pUR, allyDR, allyUR);
                    if (bestAllyDist <= 1.0 * BL) {
                        HumanAction(priestSN, needAlly);
                        priestMoveCooldown = 30;
                        if (frame % 50 == 0)
                            DebugText(QString("Priest HEAL(approach) SN=%1 ratio=%2 hp=%3").arg(needAlly).arg(worstRatio, 0, 'f', 2).arg(pBR, 0, 'f', 2));
                        return;
                    }
                    if (moveAdjacentToAlly(allyDR, allyUR, bestAllyDist, false)) {
                        priestMoveCooldown = 30;
                        if (frame % 50 == 0)
                            DebugText(QString("Priest MOVE->HEAL SN=%1 ratio=%2 hp=%3 d=%4").arg(needAlly).arg(worstRatio, 0, 'f', 2).arg(pBR, 0, 'f', 2).arg(bestAllyDist / BL, 0, 'f', 1));
                        return;
                    }
                }
            }
    }   // ★ 闭合 cpp:818 新加的外层 `{`(closeQuarters 局部作用域)
        // 3) 撤退迟滞：上帧在逃且仍处近战贴身(<4 格)或箭塔近距(<14 格)→继续逃，不切回(消除往返走) 【再修 2026-09-08】与 4) 同判据：原 `threatDist <= nearestThreatR + 2` 永远成立会卡死 mode=1
        // ★ 再修 2026-09-11：新增"治优先于逃"——若自身非濒死(pBR>0.25)、无近战贴身(<4格)、 且 25 格内有可治伤兵(<90%)，则不延续逃跑，改走下方治疗档(边挨远程打边治)。
        bool meleeAdj = false;
        for (auto &e : info.enemy_armies)
            if (calDistance(pDR, pUR, e.DR, e.UR) < 4.0 * BL) { meleeAdj = true; break; }
        bool woundedNear = false;
        for (auto &a : info.armies) {
            if (a.SN == priestSN || a.MaxBlood <= 0 || a.Blood <= 0) continue;
            double r = (double)a.Blood / a.MaxBlood;
            if (r >= 0.9) continue;
            // ★ 2026-09-11 修"反攻期祭司在家箭塔附近转圈不反攻"：反攻期只认重伤(<50%)， 不把基地里轻伤的后方单位当"有伤兵可治"，避免祭司滞留基地不推进
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
// ★★ 2026-09-13 保祭司：旧版反攻期【只有近战贴身才逃】(mustFlee = meleeAdj) ⇒ 祭司被多个远程单位(12 格射程)集火时
// 完全不撤、满血被秒。保留"不因远程威胁就缩回基地"的原意（否则祭司永远待在箭塔旁不反攻），   但增加【掉血退出】条件：已掉到 PRIEST_COUNTER_FLEE_HP 以下且仍在敌人射程内 → 立即撤。
            double pBRc = (priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0;
            mustFlee = meleeAdj || (pBRc <= PRIEST_COUNTER_FLEE_HP && threatDist <= nearestThreatR);
        }
        // 迟滞延续：已处于撤退态且威胁仍在(近战贴身 / 箭塔 / 远程射程) → 继续逃
        if (priestMode == 1 && (fleeLag || mustFlee) && !healOverFlee) {
            double feDR = 0, feUR = 0; locateNearest(feDR, feUR);
            priestFlee(feDR, feUR); return;
        }
// ★★ 2026-09-13 保祭司：原 `priestMode = 0;` 是【无条件】执行 → 迟滞锁形同虚设 ★★ 撤退中(priestMode=1) 只要本帧 fleeLag 不成立(无近战贴身/无箭塔) 就立刻解锁；而 mustFlee 用的是【含远程】的 threatDist
// ⇒ 形成逐帧交替："flee(远程威胁) → 解锁 → 走到待命回塔分支 → 再 mustFlee → flee"（实测 pv2 落点每 30 帧翻转一次，被围殴致死）。 修：只有【真正脱离全部威胁】才解锁撤退迟滞锁。
        if (priestMode == 1 && !fleeLag && !mustFlee) priestMode = 0;
        // 4) 有威胁且无法感化(冷却中/无目标)→保命撤退   闸已改为：自身非濒死 + 无近战贴身 + 25 格内有可治伤兵(<90%) ⇒ 跳过逃跑、优先治疗（边挨远程打边治）；
        // 仅"无伤兵可治 / 近战贴身 / 濒死"才真正逃命。   反攻期祭司须随军推进，不因子弹/箭塔等远程威胁缩回基地；只在近战贴身(<4格)这种会瞬秒的死亡威胁下才逃。
        if (mustFlee && !healOverFlee) {
            double feDR = 0, feUR = 0; locateNearest(feDR, feUR);
            priestMode = 1; priestFlee(feDR, feUR); return;
        }
        // ★ 闲时治疗友军：位于感化/逃跑之后、回 TC 等其它逻辑之前。本分支只治疗友军。
        // ★ 祭司本职＝治友军：不设自身血量门槛，只要 25 格内有受伤友军(<90%) 即治；     被撤退闸打断成 WALKING 的祭司也能立即改向（否则交火中永远卡在"走-逃"循环、治不到）。
        // ★ 治疗铁律：必须用 `HumanAction(priestSN, allySN)`（见下文治档铁律），换成 HumanBuild/Upgrade 等任何其它动作都不触发治疗。真正保命由 canAct 闸(pBR≤0.25 强制逃命) 与"近战贴身/濒死才逃"兜底。
        if ((priest->NowState == HUMAN_STATE_IDLE || priest->NowState == HUMAN_STATE_WALKING)
            && priestMoveCooldown <= 0) {
            double bestAllyDR = 0, bestAllyUR = 0, worstRatio = 1.0;
            int bestAlly = pickHealTarget(0.9, true, bestAllyDR, bestAllyUR, worstRatio);
            if (bestAlly >= 0) {
                double bestAllyDist = calDistance(pDR, pUR, bestAllyDR, bestAllyUR);
                bool issued = false;
                if (bestAllyDist > 1.0 * BL) {
                    // ★ 反攻期：不回头追后方轻伤单位——治疗移动令落空，本函数结束，推进交给 manageCounterAttack
                    if (!inCounter) issued = moveAdjacentToAlly(bestAllyDR, bestAllyUR, bestAllyDist, true);
                } else {
                    HumanAction(priestSN, bestAlly);
                    issued = true;
                }
                if (!issued) return;
                priestMoveCooldown = 30;
                if (frame % 50 == 0)
                    DebugText(QString("Priest HEAL (idle) SN=%1 ratio=%2").arg(bestAlly).arg(worstRatio, 0, 'f', 2));
                return;
            }
        }
        // ★ 2026-09-11 修"反攻期祭司在家箭塔附近转圈不反攻"：反攻期祭司须跟随大军推进， 不再回基地箭塔待命(那是和平期保命待命行为)；移动完全交给 manageCounterAttack 的推进段。
        if (inCounter) return;
// 6) ★ 无事可做 → 回【己方箭塔】旁待命：优先最近己方箭塔(≤30 格)，无箭塔/太远退回 TC。   箭塔有 8 格火力覆盖又能当掩体，比 TC 中心暴露安全得多；探完路/战斗结束后不能滞留野外。
// 用锚点旁"空地"而非锚点中心（中心不可达 → 引擎拒收、原地不动），多半径×多角度螺旋找可走点。
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
            // ★★ 2026-09-13 保祭司：加 `priestMode == 0` —— 撤退中(priestMode=1)绝不能走【回塔待命】， 否则与 flee 逐帧交替成原地抖动(pv2 死因)。待命是和平行为，撤退态禁止。
            if (priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0 && dAnchor > 6 * BL && priestMode == 0) {
                // 卡死检测：记录点只在祭司真正挪窝后刷新——否则每次重发都刷新时间戳， 45帧窗口永远走不满→priestNearTCTry 永不递增→永远重发同一被占落点。
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
                    DebugText(QString("Priest RETURN-TOWER dA=%1 anchor=(%2,%3)").arg(dAnchor / BL, 0, 'f', 0).arg(anchorX / BL, 0, 'f', 0).arg(anchorY / BL, 0, 'f', 0));
                return;
            }
        }
        return;
    }
    // ⚠ 本函数末尾是无条件 return：改祭司逻辑请只动上方统一决策块内，勿在其后补代码（不会执行）。
}

// 经济管理（农民生产 + 建筑 + 分配 + 科技）
void UsrAI::manageEconomy() {
    // 1. 村民生产：有50食物就造人，冲到目标数量    ★ 铜器升级条件已满足时优先升级：暂停造村民，把TC和食物留给升级指令
    auto center = findBuilding(BUILDING_CENTER);
    //   ★ 2026-09-13：新增两条 —— ①前置建筑就绪才"攒升级费"（否则食物够也升不了，     白停产、空转）；②UPGRADING 重试期同样停产，避免新村民吃掉 800 升级费。
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
            // 乐观布尔值在 BuildingAction 发出时就设为 true，但资源尚未扣除 必须查建筑的实际 Project 状态，确认科技已经"付款"正在执行
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

                // ★ 阔剑科技已封禁(DISABLE_BROADSWORD_TECH)，军事解锁改由复合弓科技承担， 故食物预留额改为按复合弓科技真实食物成本 + 50 缓冲（不再硬编码 190=阔剑140+50）。
                if (!militaryTechPaid)
                    minFood = BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_FOOD + 50;

                if (frame % 50 == 0) {
                    DebugText(QString("[FARMER f=%1] postBr=%2 paid=%3(brRun=%4 cbRun=%5 brd=%6 cmp=%7) minFd=%8 meat=%9 fCnt=%10").arg(frame).arg((int)postBronze).arg((int)militaryTechPaid)
                        .arg((int)broadswordRunning).arg((int)compositeBowRunning).arg((int)broadswordResearched).arg((int)compositeBowResearched).arg(minFood).arg((int)info.Meat).arg(farmerCount));
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

// 建造管理（PPT顺序：房屋→谷仓→市场→兵营→靶场→马厩→箭塔→学院）
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
    auto releaseBuilderAndErase = [&](int sn, std::map<int,int>::iterator &it) {
        releaseBuilder(sn);
        it = buildingFarmerType.erase(it);
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
        // 其次退化为"该类型里离他最近的在建建筑"（旧代码取"第一处在建"，   多座同类地基并存时会把建造者绑到别人的地基上，造成互相抢/都建不完）。
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
            // 此时绝不能释放登记：否则村民走到一半就被当成"空闲可采集"，   地基从此无人施工、永久卡在"建设中"（房屋建不完/人口卡顶的根因）。
            bool pendingNow = false;
            for (auto &kv : pendingBuildIns)
                if (kv.second.first == sn && kv.second.second == buildType) { pendingNow = true; break; }
            if (pendingNow) { ++it; continue; }

            // 建筑已建成或已不存在 → 真正"建完才释放"
            releaseBuilderAndErase(sn, it);
            continue;
        }

// ★ 建造者硬超时（总钥匙）：自本次建造令下发起超过 BUILDER_HARD_TIMEOUT(1800 帧) 仍未完工、且地基上无人施工 →
// 判该地基作废：percent==0 拉黑另址重建 / percent>0 仅释放登记（交孤儿抢救接手，不丢弃已投入进度）。 旧逻辑只在 IDLE 累计 900 帧才超时：建造者长期 WALKING 或被改派时永不释放 ⇒ 建筑永久卡 0%，
// 而 countBuildingsExisting 仍算它"已存在" ⇒ 下游被引擎前置链连锁卡死。
        {
            auto dsp = builderDispatchFrame.find(sn);
            bool workingNow = (myB && f->NowState == HUMAN_STATE_WORKING && f->WorkObjectSN == myB->SN);
// ★ 关键防误杀：只要【该地基上有任何村民正在施工】就不算超时。 2026-09-13 实证 l_r90：农场 SN=11353 被本判据误判（登记建造者走了，但另一村民仍在施工 percent=91，63 帧后正常建完）。
// ⚠ 必须同时要求 NowState==WORKING：WorkObjectSN 会被引擎长期保留为"上次目标" ⇒ 只看 SN 匹配会让本判据恒真、硬超时永不触发。
            bool anyoneWorking = false;
            if (myB)
                for (auto &g : info.farmers)
                    if (g.NowState == HUMAN_STATE_WORKING && g.WorkObjectSN == myB->SN) { anyoneWorking = true; break; }
            if (workingNow || anyoneWorking) {
                // 有人在建 → 保持登记、不超时（刻意不续期：一旦彻底无人施工立即触发兜底）
            } else if (dsp != builderDispatchFrame.end() &&
                       frame - dsp->second > BUILDER_HARD_TIMEOUT) {
                if (myB && myB->Percent < 100) {
                    // ★ 分档处置：percent==0（纯卡死，材料未投入）→ 拉黑另址重建； percent>0（已有进度）→ 不拉黑，仅释放登记，交由孤儿抢救派人接手建完，
                    // 避免丢弃已投入的建造进度（该地基仍会被 countBuildingsExisting 计入， 不会重复建造；且 deadBuildings 清理逻辑见 percent>0 即自动复活）。
                    if (myB->Percent == 0) {
                        deadBuildings.insert(myB->SN);
                        if (!deadBuildingsFrame.count(myB->SN)) deadBuildingsFrame[myB->SN] = frame;
                    }
                    DebugText(QString("[BUILDER-HARD f=%1] 建造者SN=%2 type=%3 地基SN=%4 percent=%5 超时%6帧 → %7").arg(frame).arg(sn).arg(buildType).arg(myB->SN).arg(myB->Percent)
                              .arg(frame - dsp->second).arg(myB->Percent == 0 ? "作废另址重建" : "仅释放登记(交孤儿抢救接手)"));
                }
                releaseBuilderAndErase(sn, it);
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
                releaseBuilderAndErase(sn, it);
                continue;
            }
            ++it; continue;
        }

        // 其他状态（WALKING/ATTACKING 等）：保持登记等待；不清除 builderIdleFrame，让其继续累计空闲时间
        ++it;
    }

    // ---- 孤儿地基抢救：在建(Percent<100)但没有任何村民在施工 → 补派村民，避免永久卡在"建设中" ---- 成因：建造者登记因异步回写/被打断/死亡而丢失后，原地基不会有任何代码再派人过去，
    // 而 houseBuildingInProgress 又把它算作"在建中"，于是新房也不建 → 人口卡顶。
    {
        for (auto &b : info.buildings) {
            if (b.Percent >= 100) continue;
            // 被判定为废弃地基(卡0%)的：宽限期内仍尝试换人补救；过了宽限期就放弃它、改由另建新址解决
            if (deadBuildings.count(b.SN)) {
                auto dit = deadBuildingsFrame.find(b.SN);
                if (dit != deadBuildingsFrame.end() && frame - dit->second > DEAD_BUILDING_GRACE) continue;
            }
// 是否已有村民【正在施工】这个地基。   ★ 2026-09-13 收紧：旧版只判 `f.WorkObjectSN == b.SN`，而该字段在引擎里会作为"上次工作目标"长期保留
// （村民早已离开/改派，字段仍指着它）⇒ hasWorker 恒 true ⇒ 孤儿抢救永不触发、地基永久卡 0%。
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

// ★ 2026-09-13：关键建筑允许"抽人"抢救。旧版只调 findIdleFarmer()，经济满载时恒返回 null
// ⇒ 地基永久无人施工(卡 0%)，而下游建筑被引擎前置链连锁卡死（靶场←兵营 Development.cpp:727、农场←市场 :765、市场←谷仓 :635）。
// 对关键建筑放宽到 findAnyFarmer()（从木/金/石采集岗抽 1 人），用更长节流(ORPHAN_STEAL_CD=5 秒) 避免把经济抽干。
// ★ 农场也纳入：tryBuild 的农场硬上限把【所有】FARM(含 0% 卡死的) 都计入名额 ⇒ 一座卡死农场会永久占用名额。
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
                DebugText(QString("[ORPHAN f=%1] 地基SN=%2 type=%3 percent=%4 补派村民SN=%5%6").arg(frame).arg(b.SN).arg(b.Type).arg(b.Percent).arg(of->SN).arg(steal ? " (抽采集岗)" : ""));
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

    // ====== ★ 2026-09-15 精简：建造块收口（铁律 21/26）====== 同一建筑的"该不该建/建不建得起"判据此前在 preW1 / postW1 / postW2 各写一遍（房屋4处、谷仓3、市场3、
    // 靶场3、兵营3、箭塔2、马厩2、农场2）—— 漏改一处就让"阶段之间的行为悄悄分叉"。此处收口为 9 个 lambda，   判据与原块【逐字等价】，调用点保持原位置 + 原阶段守卫 ⇒ 行为不变。
    // ⚠ 条件求值顺序一律保持原样：短路顺序决定 countBuildingsExisting() 的被调用次数（该函数带"90 帧防重窗口"副作用）。
    // ⚠ 各阶段条件确有差异（preW1 兵营多一道 houseCount 闸、postW2 市场要避让第二仓库）⇒ 差异一律做成显式参数，     不做"想当然的合并"。
    const bool popHeadroomLowNow = (info.Human_MaxNum - humanPop <= POP_HEADROOM_BUILD);
    const bool canAffordEconNow  = (info.Meat >= 80 && info.Wood >= 50);
    auto tryBuildHouse = [&]() {
        if (!builtThisFrame && houseCount < MAX_HOUSES && !houseBuildingInProgress && popHeadroomLowNow &&
            info.Wood >= BUILD_HOUSE_WOOD)
            builtThisFrame = tryBuild(BUILDING_HOME, 2);
    };
    // ★ requireNoMarket：preW1/rushMilitary 的谷仓块带 `市场==0` 前置（谷仓必须先于市场），
    // 而 postW2 的谷仓块【没有】这个前置（此时市场早已判定过、只补谷仓）。   两者原先各写一遍，收口时必须用参数区分，否则 postW2 会被多加一道市场闸 →
    // "市场已建但谷仓缺失"时 postW2 永远补不出谷仓（食物链断裂）。
    auto tryBuildGranary = [&](bool requireAfford, bool requireNoMarket) {
        if (!builtThisFrame && (!requireAfford || canAffordEconNow) &&
            (!requireNoMarket || countBuildingsExisting(BUILDING_MARKET) == 0) &&
            countBuildingsExisting(BUILDING_GRANARY) == 0 &&
            info.Wood >= BUILD_GRANARY_WOOD && !DISABLE_GRANARY_BUILD)
            builtThisFrame = tryBuild(BUILDING_GRANARY, 3);
    };
    auto tryBuildMarket = [&](const char *tag) {
        if (!builtThisFrame &&
            countBuildingsExisting(BUILDING_MARKET) == 0 &&
            countBuildingsExisting(BUILDING_GRANARY) >= 1 && info.Wood >= 150) {
            builtThisFrame = tryBuild(BUILDING_MARKET, 3);
            if (builtThisFrame)
                DebugText(QString("[MARKET f=%1] %2 wood=%3").arg(frame).arg(tag).arg((int)info.Wood));
        }
    };
    auto tryBuildArmyCamp = [&](bool requireHouse) {
        if (!builtThisFrame && countBuildingsExisting(BUILDING_ARMYCAMP) == 0 &&
            (!requireHouse || houseCount >= 1) && info.Wood >= BUILD_ARMYCAMP_WOOD)
            builtThisFrame = tryBuild(BUILDING_ARMYCAMP, 3);
    };
    auto tryBuildRange = [&](const char *tag) {
        if (!builtThisFrame && countBuildingsExisting(BUILDING_RANGE) == 0 &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_RANGE_WOOD) {
            builtThisFrame = tryBuild(BUILDING_RANGE, 3);
            if (builtThisFrame && tag)
                DebugText(QString("[RANGE f=%1] %2 wood=%3").arg(frame).arg(tag).arg((int)info.Wood));
        }
    };
    auto tryBuildTower = [&]() {
        if (!builtThisFrame && towerCount < MAX_TOWERS && frame < WAVE3_TIME && info.Stone >= 150) {
            builtThisFrame = tryBuild(BUILDING_ARROWTOWER, 2);
            if (builtThisFrame) towerCount++;
        }
    };
    auto tryBuildStable = [&](bool requireToolAge, const char *tag) {
        if (!builtThisFrame && countBuildingsExisting(BUILDING_STABLE) == 0 &&
            (!requireToolAge || info.civilizationStage >= CIVILIZATION_TOOLAGE) &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_STABLE_WOOD && !DISABLE_STABLE_BUILD) {
            builtThisFrame = tryBuild(BUILDING_STABLE, 3);
            if (builtThisFrame)
                DebugText(QString("[STABLE f=%1] %2 wood=%3").arg(frame).arg(tag).arg((int)info.Wood));
        }
    };
    // 农场"木材需求额"：两处（postW1 / postW2）此前各算一遍同样的 6 行，口径必须同源。
    auto farmWoodNeedNow = [&]() {
        bool cbPending = (postBronze && !compositeBowResearched && !compositeBowQueued && frame < FARM_WAIT_CB_FRAME);
        return FARM_WOOD_NEED(storageNearGazelleBuilt == 1) + (cbPending ? COMPOSITE_BOW_WOOD_RESERVE : 0);
    };
    auto farmerCountNow = [&]() {
        int n = 0;
        for (auto &f : info.farmers) if (f.FarmerSort == FARMERTYPE_FARMER) n++;
        return n;
    };

// ★★★ 2026-09-22 用户需求「避免一个瞪羚群附近重复建 2 个仓库」：仓库令【落点记忆】判据（唯一真源）★★★ 给定块坐标，判断"最近下发的仓库令是否就落在这里/附近（且仍在有效窗口内）"。
// 本函数两条建仓路径（下方近场块 + postW2 第二仓库块）共用它 ⇒ 判据只写一遍（铁律 21/26）。 ⚠ 窗口到期后自动放行重发：村民阵亡 / 选址被判非法导致仓库始终没落地时，不会永久锁死。
    auto stockOrderPending = [&](double blkDR, double blkUR) -> bool {
        int nOrd = (int)stockOrderFrame.size();
        for (int i = 0; i < nOrd; ++i)
            if (frame - stockOrderFrame[i] <= STOCK_ORDER_SETTLE &&
                calDistance(blkDR, blkUR, (double)stockOrderDR[i], (double)stockOrderUR[i]) < STOCK_ORDER_MERGE_BLK)
                return true;
        return false;
    };

// ====== ★★★ 瞪羚群中心仓库：全建筑最高优先级（用户需求：村民打猎前先建仓库）★★★ ====== ① 块放在 preW1 之前 ⇒ 抢在房屋/兵营/靶场/市场/农场之前消耗木材；
// ② 闸门用"TC 可猎范围内有瞪羚"而非"已经在打猎" ⇒ 仓库在猎人出发前落地，不再空跑往返；
// ③ 聚类只在距 TC ≤ GAZELLE_HUNT_RANGE 的瞪羚里选（与猎人选取范围一致），否则会建在"全图最密但村民根本不会去"的假群上。
// ★ 2026-09-24 用户需求「存放狩猎瞪羚物资的仓库要尽早建」：删掉 `storageNearGazelleBuilt == 0` 外层闸。
//   旧闸在剧本预置仓库(11097)存在时当帧就被 `existingStocks > 0` 置 1 ⇒ 本块直接不可达，近场仓库只能等 postW2 第二仓库块。
//   现在 11 分钟窗口内、有房屋、木≥BUILD_STOCK_WOOD 就允许本块运行；建不建仍由 `clusterCovered` 逐簇判断，已有近场仓库的簇不会重复建。
    if (!builtThisFrame && frame < GAZELLE_STOCK_WINDOW_END &&
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
            // 6 格邻域聚类得到【所有聚类中心】几何中心，不再只取最大 1 群；   按瞪羚数从多到少排序；逐个尝试建造（已有仓库覆盖的聚类跳过）。
            // 逐座建造、每帧受 builtThisFrame 互斥锁限制 ⇒ 多群仓库天然分散到多帧建造完成。
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

                // ★ 2026-09-15 收口：同一"本簇是否已被现成仓库覆盖"判据原先在本块内写了两遍 （建造循环 1 次 + allCovered 判定 1 次）——判据写两遍即等于只剩一遍生效。
                auto clusterCovered = [&](double cdr, double cur) {
                    // ★ 2026-09-22：① 刚下过仓库令、村民还在路上的落点也算覆盖（本块虽因 snGB 闸实务不可达， 但两条路径的锚点口径必须一致，否则哪天闸一松开重复建造立刻复发）；② 去掉 `Percent == 100`
                    // —— 在建（已下地基）的仓库同样是锚点。
                    if (stockOrderPending(cdr / gBL, cur / gBL)) return true;
                    for (auto &b : info.buildings)
                        if (b.Type == BUILDING_STOCK &&
                            calDistance(cdr, cur, (b.BlockDR + 1) * gBL, (b.BlockUR + 1) * gBL)
                                < GAZELLE_HUNT_RANGE * gBL)
                            return true;
                    return false;
                };
                int existingStocks = countBuildingsExisting(BUILDING_STOCK);
                // 单帧内循环尝试建各未覆盖聚类（受 builtThisFrame / MAX_STOCK / 木 三重闸）
                for (auto &cl : clusters) {
                    if (builtThisFrame) break;
                    if (info.Wood < BUILD_STOCK_WOOD) break;
                    if (existingStocks >= MAX_STOCK) break;
                    // 该聚类已被现成仓库覆盖（任何已有者均视为前置库存，含初始化遗留）→ 跳过本簇
                    if (clusterCovered(cl.dr, cl.ur)) continue;
                    int tBlockDR = (int)(cl.dr / gBL) - 1;
                    int tBlockUR = (int)(cl.ur / gBL) - 1;
                    // 第 7 参 preferNearBuilder=true：优先派【离猎场最近】的空闲村民去建
                    if (tryBuild(BUILDING_STOCK, 3, false, tBlockDR, tBlockUR, false, true)) {
                        existingStocks++;
                        builtThisFrame = true;
                        if (frame % 60 == 0)
                            DebugText(QString("[GAZELLE-STOCK f=%1] 群中心块(%2,%3) 群内瞪羚=%4 已建仓=%5/%6 木=%7").arg(frame).arg(tBlockDR).arg(tBlockUR).arg(cl.cnt)
                                      .arg(existingStocks).arg(MAX_STOCK).arg((int)info.Wood));
                    }
                    // tryBuild 失败（位置冲突等）→ 继续试下一簇，不能 break
                }

                // ★ storageNearGazelleBuilt 释义（解锁农场阈）：任一条件满足即置 1 ① existingStocks>0（任一仓库已建好）② 已达 MAX_STOCK（4） ③ 所有近距聚类均已被覆盖 ④ 本帧无近距瞪羚（无法判定）
                if (existingStocks > 0 ||
                    countBuildingsExisting(BUILDING_STOCK) >= MAX_STOCK ||
                    clusters.empty()) {
                    storageNearGazelleBuilt = 1;
                } else {
                    bool allCovered = true;
                    for (auto &cl : clusters)
                        if (!clusterCovered(cl.dr, cl.ur)) { allCovered = false; break; }
                    if (allCovered) storageNearGazelleBuilt = 1;
                }
            }   // ★★★ 闭合 !gaz.empty()（2026-09-12 多聚类版）
// ★ 2026-09-13 兜底 A：TC 猎场(GAZELLE_HUNT_RANGE=50 格)内【始终没有存活瞪羚】⇒ 本局根本不派猎人 ⇒
// 近距仓库永远建不出 ⇒ storageNearGazelleBuilt 永远停在 0 ⇒ 农场闸(两处均要求 ==1) 永久卡死，食物只能靠浆果/猎象。
// 口径复用 gazelleDropoffReady() 的超时兜底 GAZELLE_STOCK_GATE_DEADLINE(9000 帧 = 6 游戏分)：到点即解锁农场阈。
            else if (frame >= GAZELLE_STOCK_GATE_DEADLINE) {
                storageNearGazelleBuilt = 1;
                if (frame % 300 == 0)
                    DebugText(QString("[GAZELLE-STOCK f=%1] 近场无存活瞪羚 → 兜底解锁农场阈").arg(frame));
            }
        }
    }

    // ★ 2026-09-13 兜底 B（硬保证）：建造窗口已关(11 分钟)时若仍未解锁，直接解锁。 上方块整体带 `frame < GAZELLE_STOCK_WINDOW_END(16500)` 闸，窗口一过就再也不会执行；
    // 若窗口期内因木材不足 / 房屋不足等原因一次都没跑到，标志会永久停在 0 → 农场闸同样卡死。   窗口关闭后本标志已无任何"等待仓库"的意义（仓库也不会再建），故无条件解锁。
    if (storageNearGazelleBuilt == 0 && frame >= GAZELLE_STOCK_WINDOW_END) {
        storageNearGazelleBuilt = 1;
        DebugText(QString("[GAZELLE-STOCK f=%1] 建造窗口已关 → 硬解锁农场阈").arg(frame));
    }

    // ====== 第一波前：房屋→兵营（工具时代就能建），不建其他 ======
    if (preW1) {
        // 人口余量≤POP_HEADROOM_BUILD(=人口上限-2)时补房屋
        tryBuildHouse();
        // 有房屋后尽早造兵营（木材够就建，不等人满）
        tryBuildArmyCamp(true);
        // ★ 兵营建好后立刻建靶场（工具时代即可，不等铜器）
        tryBuildRange(nullptr);
    }

    // ====== 第一波后~第二波前：铜器启动即优先军事（工具时代就能建兵营） ======
    if (postW1) {
        bool rushMilitary = (upgradeStarted && frame < 16500 && !wave2Defeated);  // 升级已启动即可建兵营

        // ⚠ 注：瞪羚群中心仓库已【上移】到本函数最前面（preW1 之前，全建筑最高优先级），   见上方「★★★ 瞪羚群中心仓库（全建筑最高优先级）」段。原块位置（此处）已移除。

        if (rushMilitary) {
            // ★ 铜器后军事优先：兵营→靶场→阔剑科技，不建市场农场
            tryBuildArmyCamp(false);
            tryBuildRange(nullptr);
            // 人口余量≤POP_HEADROOM_BUILD(=人口上限-2)时补房屋
            tryBuildHouse();

            // ★ 2026-09-13（根因 A）：rushMilitary 期间不再整块跳过"经济前置建筑"。 旧版整个 else 分支被跳过 ⇒ 谷仓/市场在整个 postW1 窗口零机会，只能等 postW2(9 分钟)；
            // 而农场依赖市场、市场依赖谷仓（Development.cpp:765 / :635）⇒ 整条食物经济链被推迟。 现按最低优先级放行「谷仓 → 市场」：排在兵营/靶场/房屋之后，本帧无建造令且资源够才触发。
            tryBuildGranary(true, true);
            if (!builtThisFrame && canAffordEconNow) tryBuildMarket("rushMilitary 期放行市场");
        } else {
            // ★ 铜器前/11分钟后/W2结束后：正常市场→农场

            tryBuildGranary(true, true);
            if (!builtThisFrame && canAffordEconNow) tryBuildMarket("postW1 经济期建市场");

            // ★ 箭塔优先于农场：石头够就造（数量上限 MAX_TOWERS）。 反攻阶段(游戏时间≥14分钟=WAVE3_TIME)起不再新建箭塔——反攻应集中资源爆兵推进。
            tryBuildTower();

            // ★ 靶场优先于农场：兵营已有、木材够就建（不等铜器）
            tryBuildRange(nullptr);

            // ★ 马厩（postW1 经济阶段即可建：兵营已有 + 木材≥150 就建；学院前置需马厩，故早于学院） 2026-09-13 解封（DISABLE_STABLE_BUILD=false）：建马厩只作学院前置，骑兵仍不训练。
            // ★ 时代闸（引擎 Development.cpp:696 buildCon 要求 CIVILIZATION_TOOLAGE）：缺此闸时 时代未达 → 引擎拒绝建造、countBuildingsExisting 的 90 帧防重窗口一过就归零 → 无限重试扫格。
            tryBuildStable(true, "postW1 建马厩(学院前置)");

            bool marketReady = (countBuildings(BUILDING_MARKET) >= 1);
// ★ 农场：市场已建 + 木材/食物够才建。 前置 = 瞪羚中心【仓库 BUILDING_STOCK】已建（2026-09-03 纠正：瞪羚肉 ProductSort=HUMAN_STOCKFOOD 交付仓库）。
// ⚠ 用"地图上【任意】一座我方仓库"解锁（不限 AI 自建）：否则 tryBuild 段判"30 格内有库存→跳过" 会让 storageNearGazelleBuilt 永远停在 0 → 农场闸永远卡死。
        // ★ 2026-09-13 另加两道闸：木材加工科技（FARM_WAIT_WOOD_TECH_FRAME）+ 复合弓让木（COMPOSITE_BOW_WOOD_RESERVE）。
        int farmWoodNeed2 = farmWoodNeedNow();
        if (!builtThisFrame && marketReady && storageNearGazelleBuilt == 1 &&
                (marketWoodUpgraded || frame >= FARM_WAIT_WOOD_TECH_FRAME) &&
                (!postBronze || compositeBowResearched || compositeBowQueued || frame >= FARM_WAIT_CB_FRAME) &&
                info.Wood >= farmWoodNeed2 && info.Meat >= 100) {
            int currentFarms = countFarmsForCap();
                int targetFarms = std::min(std::max(0, farmerCountNow() - 2), MAX_FARMS);
                if (currentFarms < targetFarms) {
                    builtThisFrame = tryBuild(BUILDING_FARM, 3);
                }
            }

            tryBuildHouse();
        }
    }

    // ====== 第二波后：正常军事建筑 ======
    if (postW2) {
        // 房屋：人口余量≤POP_HEADROOM_BUILD(=人口上限-2)时优先补，不军事建筑木材预留挤掉， 否则人口将满时村民/军队会卡住无法训练。
        tryBuildHouse();

        // 谷仓（postW2：只判"还没有谷仓"，不受市场闸约束——市场闸只属于 preW1/rush 段）
        tryBuildGranary(false, false);

// ★ 第二仓库「是否需要建」的预判定：市场/靶场按此让位，避免远距瞪羚存在时被它们抢走 builtThisFrame （前置过严 → 每帧 tryBuild 失败 → 下一建筑接力 = 历史上"农场被饿死"的同源问题）。
// ⚠ 时机闸(WAVE2_TIME) 与木材闸(BUILD_STOCK_WOOD+30) 必须与下方【实际建造块】同步：旧版只有"该不该建"、
// 没有"建不建得起"，木材卡在中间区间时市场会被永久冻结、靶场冻到 14 分钟。   ⚠ gazelleAlive==0 ⇒ 恒 false，让位闸同步失效，否则会被一个永远建不出来的仓库饿死。
// ★ 2026-09-15 收口："远距瞪羚"判据（距 TC>20 且 距所有已建成仓库>20）原先在【预判定】与【实际建造】两处各写一遍 —— 两处口径必须完全一致，否则会出现"预判定说该建、建造块却不建"的空转。
        // ★ 2026-09-22 加 `pGateHit` 出参（默认 nullptr，**被挡下的只数**）：让调用方能量出"被落点闸挡下的 瞪羚数"，这是验收③的量化证据 —— 否则"没下单"分不清【本来就没远距群】还是【被闸挡下】。
        // ⚠ 只在【一处】实现判据、两处调用（预判定不传 / 建造块传 &gateHit），不写第二遍。
        auto isFarGazelle = [&](const tagResource &r, double tcDRx, double tcURx, double blx,
                                int *pGateHit = nullptr) -> bool {
            if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) return false;
            // ★ 2026-09-22「避免一个瞪羚群附近重复建 2 个仓库」主修点：刚给这个群下过仓库令 （村民还在路上、地基都还没出现）⇒ 本帧不再判为"远距"，否则 buildCooldown(5 帧) 一到
            // 就对同一个群重复下单（改前 795 局实测 54.9% 的多仓局有此现象）。 窗口 STOCK_ORDER_SETTLE 到期后自动放行重发 ⇒ 静默失败（村民阵亡/选址非法）不构成死锁。
            if (stockOrderPending(r.DR / blx, r.UR / blx)) {
                if (pGateHit) ++(*pGateHit);
                return false;
            }
            if (calDistance(tcDRx, tcURx, r.DR, r.UR) < 20 * blx) return false;
            // ★ 2026-09-22：去掉 `Percent == 100` —— 在建/已下地基的仓库同样是锚点， 否则首座未完工时，同一批远距瞪羚会再次满足"距所有已完工仓库>20"。
            for (auto &b : info.buildings)
                if (b.Type == BUILDING_STOCK) {
                    double gDR = (b.BlockDR + 1) * blx, gUR = (b.BlockUR + 1) * blx;
                    if (calDistance(r.DR, r.UR, gDR, gUR) < 20 * blx) return false;
                }
            return true;
        };
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
                    if (!isFarGazelle(r, tcDRp, tcURp, BLp)) continue;
                    farGazCnt++;
                    if (farGazCnt >= MIN_GAZELLE_FOR_SECOND_STOCK) { needSecondStock = true; break; }
                }
            }
        }

        // ★ 2026-09-13 闸门可观测性（新增，用于实证"市场/靶场是否被让位闸饿死"）： 每 300 帧打印一次让位闸全量状态。needStock=1 且 market/range 长期=0 ⇒ 就是被饿死。
        if (frame % 300 == 0) {
            // ★ 2026-09-22：补"仓库令落点记忆"的自描述 —— 判据的输入量必须能从日志直接读到（铁律 53）， 否则"本帧没下单"分不清【没远距群】还是【被落点闸挡下】。
            QString ordTxt;
            for (int i = 0; i < (int)stockOrderFrame.size(); ++i)
                ordTxt += QString("(%1,%2)Δ%3 ").arg(stockOrderDR[i]).arg(stockOrderUR[i]).arg(frame - stockOrderFrame[i]);
            if (ordTxt.isEmpty()) ordTxt = QString("无");
            DebugText(QString("[GATE f=%1] needStock=%2 gazAlive=%3 stock=%4 wood=%5 | market=%6 range=%7 granary=%8 | snGB=%9 | 仓库令落点=%10")
                      .arg(frame).arg(needSecondStock ? 1 : 0).arg(gazelleAlive).arg(countBuildingsExisting(BUILDING_STOCK)).arg((int)info.Wood).arg(countBuildingsExisting(BUILDING_MARKET))
                      .arg(countBuildingsExisting(BUILDING_RANGE)).arg(countBuildingsExisting(BUILDING_GRANARY)).arg(storageNearGazelleBuilt).arg(ordTxt));
        }

        // ★ 第二仓库：为"距现有 Stock 均 >20 格的远距瞪羚群"建一座，落在群中心。 ⚠ 三要素缺一不可（旧版缺陷导致贴 TC 多建 3 座）：① MAX_STOCK 闸；② 不能每帧重发令
        // （木材一回就再 tryBuild）；③ 必须传 prefX/prefY，否则 findBuildSite 会落回 TC 附近。 ⚠ 时机闸须与 needSecondStock 预判定同步（同为 WAVE2_TIME），否则预判定为真时本块仍被挡住。
        if (!builtThisFrame && gazelleAlive > 0 &&
            countBuildingsExisting(BUILDING_STOCK) < MAX_STOCK &&
            frame > WAVE2_TIME && info.Wood >= BUILD_STOCK_WOOD + 30) {
            auto center = findBuilding(BUILDING_CENTER);
            double BL = (double)BLOCKSIDELENGTH;
            double tcDR = center ? (center->BlockDR + 1) * BL : 0;
            double tcUR = center ? (center->BlockUR + 1) * BL : 0;
            // 收集"距 TC>20 且 距所有现有 Stock>20"的瞪羚
            std::vector<std::pair<double,double>> farGaz;
            int gateHit = 0;   // ★ 2026-09-22：被"落点记忆"闸挡下的瞪羚数（验收③的量化证据）
            for (auto &r : info.resources)
                if (isFarGazelle(r, tcDR, tcUR, BL, &gateHit))
                    farGaz.emplace_back(r.DR, r.UR);
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
                    // ★★ 2026-09-22（本轮第二处修因）第 6 参 noFallback = **true** ★★ 原为 false ⇒ 13 个偏移位都放不下时，会落到 `findBuildSite()` 的**通用兜底**（TC 旁）——
                    // 于是"给 (50,55) 的群下单、实际建到 (11,15)"（实测 vf_sd_3：群中心块 (50,55) → 建在距 TC 8.5 块处）。危害有二：① 仓库离它要服务的兽群 50+ 块 = **150 木白发**；
                    // ② 两条"不同群"的令都跑飞到 TC 旁 ⇒ 并排 4 块 = 肉眼看到的"同一个群附近建了 2 座仓库" （vf_sd_3 f18024(11,15) / f18029(11,19)，间隔 5 帧 —— 只靠"落点记忆"拦不住，因为落点
                    // 记的是**选址**、闸判的是**瞪羚位置**，两者被兜底彻底解耦）。 与第二谷仓同口径（它早已用 noFallback=true）：群边放不下 ⇒ 本帧不建、下帧重试，绝不乱落。
                    builtThisFrame = tryBuild(BUILDING_STOCK, 3, false, tBlockDR, tBlockUR, true);
                    // ★ 2026-09-22 下单观测（无条件）：验收判据必须是【产物量】而不是"日志有没有打" （本块原无任何日志，导致此前只能从 [BUILD-ISSUE] 反推，且近场块的日志带 frame%60 采样）。
                    if (builtThisFrame)
                        DebugText(QString("[STOCK-ORD f=%1] 第二仓库 群中心块(%2,%3) 远距瞪羚=%4 现存仓=%5/%6 木=%7").arg(frame).arg(tBlockDR).arg(tBlockUR).arg((int)farGaz.size())
                                  .arg(countBuildingsExisting(BUILDING_STOCK)).arg(MAX_STOCK).arg((int)info.Wood));
                    else if (frame % 300 == 0)
                        // 有候选却建不出 ⇒ 选址冲突/没空闲村民/木不够。不打印就分不清"没候选"还是"发令失败"。
                        DebugText(QString("[STOCK-ORD-FAIL f=%1] 群中心块(%2,%3) 远距瞪羚=%4 木=%5 ⇒ tryBuild 失败")
                                  .arg(frame).arg(tBlockDR).arg(tBlockUR).arg((int)farGaz.size()).arg((int)info.Wood));
                }
            }
            // ★ 2026-09-22 可观测性（铁律 53）：远距瞪羚被落点闸整批挡下时也要留痕， 否则"本帧没下单"分不清【本帧没远距群】还是【被落点闸过滤】。
            // gateHit = 只被"落点记忆"挡下（而非因太靠近 TC/既有仓库）的那部分 ⇒ 闸生效的直接计数。
            else if (gateHit > 0 && frame % 300 == 0)
                DebugText(QString("[STOCK-SUPPRESS f=%1] 远距瞪羚=%2 < 阈值%3（其中被落点闸挡下 %4 只；落点记忆 %5 条）").arg(frame).arg((int)farGaz.size()).arg(MIN_GAZELLE_FOR_SECOND_STOCK)
                          .arg(gateHit).arg((int)stockOrderFrame.size()));
        }

        // ====== ★★★ 金矿仓库（2026-09-22 用户需求「金矿旁边没有仓库的话也要建仓库」）★★★ ====== 机制依据（引擎侧已核实，非推测）：矿工背包满后由 `Core_List::findResourceBuiding()`
        // （Core_List.cpp:736）在【距资源所在处最近】的已完工建筑里选交付点（Manhattan 距离）， 候选 = TC ∪ `Resource::get_ReturnBuildingType()`（Resource.cpp:8）：
        // 金/木/石/兽肉 → BUILDING_STOCK【仓库】；浆果·农田 → GRANARY；鱼肉 → DOCK。 ⇒ 仓库必须落在【金矿旁】才缩短往返；落在 TC 旁对金矿毫无意义（本图 8 簇金矿距 TC 16.7~100 块）。
        // ★ 触发源 = 「村民此刻正在开采的远金矿」，不是"最密的远金矿"（与瞪羚侧唯一的实质差异）： 本图 64 格金矿里 55 格满足"距 TC>20 且 距仓库>20"，最密的簇心在 (11,94)（离 TC 76 块）
        // —— 按密度选会建在一座 AI 根本不会去采的矿旁（120 木白发）。按"在用"选，落点必然被用到。
        // ★ 独立预算（MAX_GOLD_STOCK）：全库 764 局 stock 吃满 MAX_STOCK=4 的占 562 局(73.6%)， 与瞪羚共用预算等于永远排不上队 ⇒ 用「服务金矿的仓库数」单独计数，总量闸放到 MAX_STOCK+1。
        // ⚠ 本块【不参与】needSecondStock 让位闸（市场/靶场不被它阻塞）⇒ 不引入新的饿死路径。
        if (postBronze && frame > WAVE2_TIME) {
            const double BLg = (double)BLOCKSIDELENGTH;
            // 只在"可能下单"或"该打自检行"时才做重活（farmers × 金矿 的两重遍历不便宜）
            const bool wantGoldEval =
                (frame % 300 == 0) ||
                (!builtThisFrame && info.Wood >= BUILD_STOCK_WOOD + GOLD_STOCK_WOOD_MARGIN);
            if (wantGoldEval) {
                auto gc = findBuilding(BUILDING_CENTER);
                const double tcDRg = gc ? (gc->BlockDR + 1) * BLg : 0;
                const double tcURg = gc ? (gc->BlockUR + 1) * BLg : 0;
                // ② 存活金矿快照（③④⑤ 三处共用，避免反复遍历 info.resources）
                std::vector<tagResource *> goldAliveV;
                for (auto &r : info.resources)
                    if (r.Type == RESOURCE_GOLD && r.Cnt > 0) goldAliveV.push_back(&r);
                // ③ 远金矿集 = 距 TC>20 且 距所有仓库>20（＝引擎交付口径下往返 >40 块），并套落点闸
                std::vector<tagResource *> farGoldV;
                const int goldAliveN = (int)goldAliveV.size();
                int gateHitG = 0;
                for (auto *r : goldAliveV) {
                    // 刚给这座矿下过仓库令（村民还在路上）⇒ 不再判为"远"（与瞪羚侧共用同一把闸）
                    if (stockOrderPending(r->DR / BLg, r->UR / BLg)) { ++gateHitG; continue; }
                    if (calDistance(tcDRg, tcURg, r->DR, r->UR) < GOLD_STOCK_ANCHOR_RANGE * BLg) continue;
                    bool nearStock = false;
                    for (auto &b : info.buildings)
                        if (b.Type == BUILDING_STOCK &&
                            calDistance(r->DR, r->UR, (b.BlockDR + 1) * BLg, (b.BlockUR + 1) * BLg)
                                < GOLD_STOCK_ANCHOR_RANGE * BLg) { nearStock = true; break; }
                    if (nearStock) continue;
                    farGoldV.push_back(r);
                }
                // ④ 在用远金矿格 = 某村民当前工作目标（WorkObjectSN）指向的远金矿
                std::vector<std::pair<double,double>> inUse;
                for (auto &fm : info.farmers) {
                    if (fm.WorkObjectSN <= 0) continue;
                    for (auto *r : farGoldV)
                        if (r->SN == fm.WorkObjectSN) { inUse.emplace_back(r->DR, r->UR); break; }
                }
                // ⑤ 候选 = 在用格 ∪ 与其同簇(6 格)的远金矿格（扩到整簇，簇中心才是有意义的落点）
                std::vector<std::pair<double,double>> cand;
                if (!inUse.empty())
                    for (auto *r : farGoldV)
                        for (auto &p : inUse)
                            if (calDistance(r->DR, r->UR, p.first, p.second) < 6 * BLg) {
                                cand.emplace_back(r->DR, r->UR); break;
                            }
                // ⑥ 下单（四闸：有人在采 / 独立预算未用满 / 总量未超 / 木够）
                if (!builtThisFrame && !cand.empty() &&
                    goldStockOrders < MAX_GOLD_STOCK &&
                    countBuildingsExisting(BUILDING_STOCK) < MAX_STOCK + MAX_GOLD_STOCK &&
                    info.Wood >= BUILD_STOCK_WOOD + GOLD_STOCK_WOOD_MARGIN) {
                    // 6 格邻域聚类 → 取最大簇中心（与第二仓库同算法）
                    double bestSumDR = 0, bestSumUR = 0; int bestCnt = 0;
                    for (auto &seed : cand) {
                        double sumDR = 0, sumUR = 0; int cnt = 0;
                        for (auto &g : cand)
                            if (calDistance(seed.first, seed.second, g.first, g.second) < 6 * BLg) {
                                sumDR += g.first; sumUR += g.second; cnt++;
                            }
                        if (cnt > bestCnt) { bestCnt = cnt; bestSumDR = sumDR; bestSumUR = sumUR; }
                    }
                    if (bestCnt > 0 && info.Wood >= BUILD_STOCK_WOOD) {
                        const int tGDR = (int)(bestSumDR / bestCnt / BLg) - 1;
                        const int tGUR = (int)(bestSumUR / bestCnt / BLg) - 1;
                        // noFallback=true：矿旁放不下就本帧不建（下帧重试），绝不落回 TC 旁 —— 落回 TC 旁 = 120 木白发（矿工仍旧往返几十块），与第二仓库/第二谷仓同口径。
                        builtThisFrame = tryBuild(BUILDING_STOCK, 3, false, tGDR, tGUR, true);
                        if (builtThisFrame) {
                            goldStockOrders++;   // ★ 只有真下单才计数（tryBuild 失败 = 没花木，下帧重试）
                            DebugText(QString("[GOLD-STOCK f=%1] 在用金矿簇心块(%2,%3) 簇内=%4 在用格=%5 远金矿格=%6 金矿仓令=%7/%8 木=%9")
                                      .arg(frame).arg(tGDR).arg(tGUR).arg(bestCnt).arg((int)inUse.size()).arg((int)farGoldV.size()).arg(goldStockOrders).arg(MAX_GOLD_STOCK).arg((int)info.Wood));
                        } else if (frame % 300 == 0)
                            DebugText(QString("[GOLD-STOCK-FAIL f=%1] 在用金矿簇心块(%2,%3) 在用格=%4 远金矿格=%5 木=%6 ⇒ tryBuild 失败").arg(frame).arg(tGDR).arg(tGUR).arg((int)inUse.size())
                                      .arg((int)farGoldV.size()).arg((int)info.Wood));
                    }
                }
                // ⑦ 自描述（铁律 53）：判据输入集必须能从日志直接读到，否则"没建金矿仓"分不清 【本来就没有远金矿】/【没有人在采远金矿】/【独立预算已用满】/【被落点闸挡下】/【木不够】。
                if (frame % 300 == 0)
                    DebugText(QString("[GOLD-GATE f=%1] 存活金矿格=%2 远金矿格=%3 在用远金矿格=%4 金矿仓令=%5/%6 被落点闸挡下=%7 木=%8")
                              .arg(frame).arg(goldAliveN).arg((int)farGoldV.size()).arg((int)inUse.size()).arg(goldStockOrders).arg(MAX_GOLD_STOCK).arg(gateHitG).arg((int)info.Wood));
            }
        }

        // ★ 第二谷仓：为"TC 之外 ≥6 丛的远距浆果群"建一座，落在群中心（用户需求 2026-09-07）。 浆果 resourceSort=HUMAN_GRANARYFOOD → 只往谷仓交；远距浆果群没有就近谷仓时村民往返 40+ 格几乎没产出。
        // 前置：首座谷仓已在 + 未达 MAX_GRANARY + 木材够；!needSecondStock 让位（远距瞪羚仓库优先级更高）。 ⚠ 必须传群中心块坐标，否则 tryBuild 会 fallback 回 findGranarySite 落回 TC 附近。
        if (!builtThisFrame && !needSecondStock && !DISABLE_GRANARY_BUILD &&
            countBuildingsExisting(BUILDING_GRANARY) >= 1 &&
            countBuildingsExisting(BUILDING_GRANARY) < MAX_GRANARY &&
            info.Wood >= BUILD_GRANARY_WOOD) {
            int clX = -1, clY = -1, clCnt = 0;
            if (findRemoteBushCluster(clX, clY, clCnt)) {
                // noFallback=true：群边放不下就本帧不建（下帧重试），绝不回退到 findGranarySite—— 该函数在第二座谷仓时会去选【瞪羚】密集处，而瞪羚肉交仓库，建谷仓在那纯属浪费 120 木。
                builtThisFrame = tryBuild(BUILDING_GRANARY, 3, false, clX, clY, true);
            }
        }

        // 市场   ★ 让位闸 !(needSecondStock && frame < WAVE3_TIME)：远距瞪羚存在 + 仓库未满时不许市场抢 builtThisFrame（修"市场先于第二仓库落地"）。⚠ 必须有时间上界：否则"远距瞪羚≥2 但仓库迟迟
        // 建不出(位置冲突)"会把市场无限期冻住；现在与靶场口径完全对齐，14 分钟反攻期后市场优先级反超。
        if (!builtThisFrame && !(needSecondStock && frame < WAVE3_TIME)) tryBuildMarket("下令建造市场");

        // 兵营
        if (!builtThisFrame && upgradeStarted) tryBuildArmyCamp(false);

        // 靶场（不限铜器，兵营已有即可建）   ★ 让位闸同市场：远距瞪羚存在 + 仓库未满时不许抢 builtThisFrame（否则第二仓库被下游接力饿死）；
        // 但只在 14 分钟(WAVE3_TIME)前让位——反攻期靶场产能优先，     也避免"仓库位置不可建 → 靶场被永久阻塞"的死锁。
        if (!builtThisFrame && !(needSecondStock && frame < WAVE3_TIME))
            tryBuildRange("下令建造首座靶场");

        // 箭塔：石头够就造（已解除 铜器/箭塔科技/兵营/靶场 前置；数量上限 MAX_TOWERS 保留）。   反攻阶段(≥14分钟=WAVE3_TIME)起不再新建——资源转向爆兵反攻。
        tryBuildTower();

        // ★ 反攻多线产弓：游戏时间≥14分钟(=WAVE3_TIME)起增建靶场(最多 MAX_RANGES 座)， 形成并行产线，弓兵产量随靶场数线性提升。木材留 80 余量避免饿死房屋/马厩。
        if (!builtThisFrame && frame >= WAVE3_TIME &&
            countBuildingsExisting(BUILDING_RANGE) < MAX_RANGES &&
            info.Wood >= BUILD_RANGE_WOOD + 80) {
            builtThisFrame = tryBuild(BUILDING_RANGE, 3);
        }

        // ★ 马厩（postW2 反攻准备）：兵营已有 + 木材≥150 就建（同 postW1 段，已恢复建造，供学院前置）
        tryBuildStable(false, "postW2 建马厩(学院前置)");

// ★ 学院：后期/反攻核心近战兵种(方阵兵)。铜器后 + 兵营已建 + 【马厩已建】(前置) + 时代闸。 ⚠ 时代闸必须留：引擎 buildCon 要求 BRONZEAGE，缺闸时引擎拒绝建造、而 countBuildingsExisting 的 90 帧防重
// 窗口一过就归零 ⇒ AI 沿坐标轴逐格扫描重试（o3_r180 实证连发 235 次），每次吞掉 builtThisFrame → 饿死 postW2 后续建造。
// ⚠ 建造时机已放宽为"后期即可"（state>=DEFENSE_WAVE3 或 frame>=WAVE3_TIME）：反攻态门槛是全军≥12 人， 前期长期不足会让整条方阵兵产线空转，这正是"后期没有方阵兵"的主因之一。
        if (!builtThisFrame && countBuildingsExisting(BUILDING_COLLAGE) == 0 && !DISABLE_COLLAGE_BUILD &&
            postBronze &&
            (state >= DEFENSE_WAVE3 || frame >= WAVE3_TIME) &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 &&
            countBuildingsExisting(BUILDING_STABLE) >= 1 &&   // ★ 学院前置：必须先建好马厩
            info.Wood >= BUILD_COLLAGE_WOOD + 30) {
            builtThisFrame = tryBuild(BUILDING_COLLAGE, 3);
            if (builtThisFrame)
                DebugText(QString("[COLLAGE f=%1] 建学院(方阵兵产线) wood=%2 state=%3").arg(frame).arg((int)info.Wood).arg((int)state));
        }

        // 农场   ★ 2026-09-06 用户要求「建造瞪羚的仓库前先不要建农场，预留120木头」：本块原先【完全没有】此闸、
        // 只有 Wood>=75；而它处于 if(postW2)，postW2 自 13500(9分) 成立、瞪羚仓库窗口却到 16500(11分) 才结束
        // ⇒ 9~11 分钟两者并存，农场抢光木材 → 仓库永远建不出、猎人来回空跑。     故补上与市场段一致的双重闸：瞪羚仓库已建 + 木材预留（★ 预留仅在仓库【未】建成时生效）。
        // ★ 2026-09-13 再加闸：木材加工科技（FARM_WAIT_WOOD_TECH_FRAME）+ 复合弓科技未就绪时再让出 100 木
        // （COMPOSITE_BOW_WOOD_RESERVE）。farmWoodTechOk 与 farmBowWoodOk 两道闸并联，任一超时兜底触发即放行。
        bool farmWoodTechOk = (marketWoodUpgraded || frame >= FARM_WAIT_WOOD_TECH_FRAME);
        bool farmBowWoodOk = (!postBronze || compositeBowResearched || compositeBowQueued ||
                              frame >= FARM_WAIT_CB_FRAME);
        int farmWoodNeed = farmWoodNeedNow();
        if (!builtThisFrame && storageNearGazelleBuilt == 1 && farmWoodTechOk && farmBowWoodOk) {
            int currentFarms = countFarmsForCap();
            if (currentFarms < farmTarget &&
                info.Wood >= farmWoodNeed) {
                builtThisFrame = tryBuild(BUILDING_FARM, 3);
            }
        } else if (!builtThisFrame && !marketWoodUpgraded && frame < FARM_WAIT_WOOD_TECH_FRAME &&
                   storageNearGazelleBuilt == 1 && frame % 300 == 0) {
            // 诊断：农场被"等木材加工科技"挡住时的现场（每 300 帧一条）
            DebugText(QString("[FARM-TECHWAIT f=%1] 农场等木材加工科技 wood=%2 meat=%3 farms=%4/%5 mkt=%6").arg(frame).arg((int)info.Wood).arg((int)info.Meat)
                      .arg(countFarmsForCap()).arg(farmTarget).arg(countBuildings(BUILDING_MARKET)));
        }
    }
}

// 每帧维护三件事：①重置资源分配去重表(供下游分配函数计数) ②动态农场目标 ③祭司探路状态机   ⚠ 本函数【不做】村民分配——旧分配逻辑已全部移除，分配统一由 assignIdleSimple() 负责。
// 经济段入口（由 manageEconomy 调用）：每帧清计数 → 重算农场目标 → 跑祭司探路。
// ★ 2026-09-23 重构：主体已拆成下面两个函数，本函数只做"清计数 + 转发"。
void UsrAI::assignIdleFarmers() {
    frameFoodTargets.clear();  // ★ 每帧重置：防同帧多农民分配到同一目标
    frameBushCount.clear();    // ★ 每帧重置浆果每丛分配计数
    frameWoodCount.clear();    // ★ 每帧重置木材分配计数
    frameGazelleCount.clear(); // ★ 每帧重置瞪羚每只分配计数

    updateFarmTarget();
    managePriestScout();
}

// 每帧重算 farmTarget（目标农场数）。2026-09-23 从 manageEconomy 抽出，逻辑未改。
// 判据顺序（自上而下，命中即返回）：① 基地附近(≤30 格)仍有浆果 ⇒ 0；② 没市场 ⇒ 0（农场是市场下游）；
//   ③ 前 5 分钟(帧<7500)且野生食物>300 ⇒ 0；④ 否则食物紧张(野生<300 或肉<200) ⇒ MAX_FARMS，否则 0。
void UsrAI::updateFarmTarget() {
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

}

// 祭司探路：8 方向放射状前进 + 回 TC 交替。2026-09-23 从 manageEconomy 抽出，逻辑未改。
// 门禁：非战时(!isWar) 且 未进入反攻 且 scoutPhase < 16。
//   ⚠ 战时由 processData 直接把 scoutPhase 推到 20（结束探路）—— 否则 managePriest 因 scoutPhase>=20 恒不运行，
//     表现为"敌人贴脸祭司也一动不动"。
// 结束条件：探完全部 8 个外向方向(scoutDirsDone>=8) 或 战时强推，置 scoutPhase = 20，交还 managePriest 接管保命/感化。
void UsrAI::managePriestScout() {
    // ====== 祭司探路：8方向放射状，祭司视野远，覆盖更广 ======
    bool isWar = (state >= DEFENSE_WAVE1 && state <= DEFENSE_WAVE3);
    if (!isWar && state != COUNTERATTACK && scoutPhase < 16) {
        double BL = (double)BLOCKSIDELENGTH;

        // ★ 2026-09-15 去重：路径 (sDR,sUR)→(wx,wy) 的【前 8 格】内是否撞上狮/象（1.5 格容差）。
        // 两处共用（去程绕障判定 / 返程绕障判定）。原先各抄一份（铁律 26）。   口径：把资源点投影到路径线段上，t<0（在身后）或 t*pathLen>8格（远端）一律不管。
        auto beastOnPathAhead = [&](double sDR, double sUR, double wx, double wy) -> bool {
            double pathDX = wx - sDR, pathDY = wy - sUR;
            double pathLen = std::sqrt(pathDX*pathDX + pathDY*pathDY);
            if (pathLen <= 0.01) return false;
            for (auto &r : info.resources) {
                if (r.Cnt <= 0) continue;
                if (r.Type != RESOURCE_LION && r.Type != RESOURCE_ELEPHANT) continue;
                double t = ((r.DR - sDR)*pathDX + (r.UR - sUR)*pathDY) / (pathLen*pathLen);
                if (t < 0 || t * pathLen > 8 * BL) continue;   // 只检查前8格，远端不管
                if (t > 1) t = 1;
                double nearX = sDR + t * pathDX;
                double nearY = sUR + t * pathDY;
                if (calDistance(r.DR, r.UR, nearX, nearY) < 1.5 * BL) return true;
            }
            return false;
        };

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
        // 而是探完全部 8 个外向方向(scoutDirsDone>=8)才结束探路、回 TC 待命。   (到达某方向终点时，由下方 nearTarget 分支执行 scoutDirsDone++。)
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

            // ★ 2026-09-15 去重：探路祭司「背向威胁点走 12 格」逃跑（两处共用：遇野兽 / 被缠斗）。
            // 含越界夹取与下发记账；调用方按需补 fledThisFrame。原先两处各抄一份（铁律 26）。   ⚠ 必须定义在 scout 解析【之后】——lambda 体内解引用 scout。
            auto scoutStepAwayFrom = [&](double fromX, double fromY) {
                double dx = scout->DR - fromX, dy = scout->UR - fromY;
                double len = std::sqrt(dx*dx + dy*dy);
                if (len < 0.01) { dx = 1; dy = 0; len = 1; }
                double tx = scout->DR + (dx / len) * 12 * BL;
                double ty = scout->UR + (dy / len) * 12 * BL;
                tx = max(0.0, min((double)MAP_L * BL, tx));
                ty = max(0.0, min((double)MAP_U * BL, ty));
                HumanMove(scout->SN, tx, ty);
                scoutIssueDR = scout->DR; scoutIssueUR = scout->UR; scoutIssueFrame = frame;
                scoutCooldown = 30;
                scoutWalkTimer = 0;
            };

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
                        // ★ 发现敌军→立刻回TC，跳过此方向（下一轮探另一方向） 遇敌返回：移到TC旁空地（避开建筑中心/石头），用多半径螺旋绕路
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
                        scoutStepAwayFrom(beastX, beastY);
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
            // ★ 关键修复：目标不可达时祭司保持 IDLE（不进入 WALKING）， 原 scoutWalkTimer 永远为0、scoutLegStartFrame 又被每帧重发重置，   卡死检测失效→scoutReturnTry 不前进→同一不可达点无限重发。
            // 改用"下发移动指令后祭司实际没挪窝"的位置进度检测，即使 IDLE 也能识别卡死。
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
                scoutStepAwayFrom(fleeX, fleeY);
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
                            // ★ 关键：每步只朝终点走 ~9 格（< 祭司 12 格视野）， 保证目标始终在已探索范围内可达；到达后再走下一步，逐步推进
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

                            // ★ 危险检测：目标12格+路径前8格避开狮/象 威胁 = 目标点 12 格内有狮/象，或路径前 8 格撞上狮/象
                            bool dangerNearby = false;
                            for (auto &r : info.resources) {
                                if (r.Cnt <= 0) continue;
                                if (r.Type != RESOURCE_LION && r.Type != RESOURCE_ELEPHANT) continue;
                                if (calDistance(wx, wy, r.DR, r.UR) < 12 * BL) { dangerNearby = true; break; }
                            }
                            if (!dangerNearby) dangerNearby = beastOnPathAhead(sDR, sUR, wx, wy);

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
                                // ★ 记录点/计时器只在祭司真正挪窝(>1格)后才刷新—— 原来每次重发指令(冷却15帧)都刷新 scoutIssueFrame 与 scoutLegStartFrame，
                                // 导致 20 帧的 noProgress 窗口永远走不满、leg 超时也被不断重置→ 卡死永不识别，同一不可达落点无限重发（日志里同一坐标刷屏）。
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
                        bool dangerNearby = beastOnPathAhead(sDR, sUR, wx, wy);

                        if (nearTarget || dangerNearby) {
                            scoutReturnTry = 0;  // 成功回到TC旁→重置绕路计数
                            scoutPhase++;  // 回到TC或遇险→下一个外向方向
                            if (scoutPhase >= 16) scoutPhase = 20;  // 全部探完→结束探路回TC待命
                            scoutCooldown = 10;
                        } else {
                            HumanMove(scout->SN, wx, wy);
                            // ★ 同样只在真正挪窝后才刷新记录点/计时器，否则 noProgress 与 leg 超时双双失效， 返回路径被堵时会无限重发同一个 scoutReturnPoint 落点。
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
    }
}

// 统计各类资源的在职村民数（出参：金/木/石/食）。2026-09-23 从 assignIdleSimple 抽出，逻辑未改。
// ⚠ 每个村民至多贡献 1：优先级 =【工作目标(WorkObjectSN)】>【手持资源(ResourceSort)】；
//   两者语义不同，绝不可相加（旧写法两条并列 if ⇒ 同一人被数两次、采金计数虚高约 2 倍）。
// 调用的判据必须与本处口径一致，改一处别忘了另一处（铁律 21/26）。
void UsrAI::countFarmerWorkKinds(int &goldWorkers, int &woodWorkers, int &stoneWorkers, int &foodWorkers) const {
    goldWorkers = woodWorkers = stoneWorkers = foodWorkers = 0;
    // ★★★ 2026-09-17 修「采金人数偏少」：本计数块【每个村民只数一次】★★★ ⚠ 陷阱：`ResourceSort` = 人物【手持】资源种类；`WorkObjectSN` = 【工作目标】—— 语义不同，绝不可相加/互换。
    // 旧写法是两条**并列 if**：一个正在采金的村民【同时】满足"手持 GOLD"与"工作目标=金矿" ⇒ 被数两次； 若粮仓里还存着黄金（ResourceSort 仍为 GOLD），往返途中再数一次 ⇒ goldWorkers 虚高
    // ⇒ 派工判据 `goldWorkers < goldTarget` 提前满足 ⇒ 不再派人。同理 foodWorkers 虚高 ⇒ `goldTarget = foodWorkers*3/5` 也被抬高，两个错误叠加（实测金工达成率仅 50.7%，与"虚高约 2 倍"量级吻合）。
    // 修法：改为 else if 链 + workObject 局部映射表把"目标→资源类型"算一次，优先级 = 工作目标 > 手持资源。
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        // ① 先判定【工作目标】属于哪类资源（唯一权威来源）
        int kind = 0;   // 0=未知 1=金 2=木 3=石 4=食
        if (f.WorkObjectSN > 0) {
            for (auto &r : info.resources)
                if (r.SN == f.WorkObjectSN) {
                    if (r.Type == RESOURCE_GOLD) kind = 1;
                    else if (r.Type == RESOURCE_TREE) kind = 2;
                    else if (r.Type == RESOURCE_STONE) kind = 3;
                    else if (r.Type == RESOURCE_BUSH || r.Type == RESOURCE_GAZELLE || r.Type == RESOURCE_ELEPHANT) kind = 4;
                    break;
                }
            if (kind == 0)
                for (auto &b : info.buildings)
                    if (b.SN == f.WorkObjectSN && b.Type == BUILDING_FARM) { kind = 4; break; }
        }
        // ② 没有工作目标时才退化为看【手持资源种类】
        if (kind == 0) {
            if (f.ResourceSort == HUMAN_GOLD) kind = 1;
            else if (f.ResourceSort == HUMAN_WOOD) kind = 2;
            else if (f.ResourceSort == HUMAN_STONE) kind = 3;
            else if (f.ResourceSort == HUMAN_GRANARYFOOD || f.ResourceSort == HUMAN_STOCKFOOD) kind = 4;
        }
        // ③ 每个村民至多贡献 1
        if (kind == 1) goldWorkers++;
        else if (kind == 2) woodWorkers++;
        else if (kind == 3) stoneWorkers++;
        else if (kind == 4) foodWorkers++;
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

    // ★ 已建成谷仓(Percent==100)位置（2026-09-07）：浆果是 HUMAN_GRANARYFOOD，只往谷仓交。 有了远距谷仓后，浆果派工不再受"距 TC ≤20 格"限制——改为"距 TC ≤20 格 或 距任一已建成谷仓
    // ≤BUSH_NEAR_GRANARY_DIST(20) 格"即可派人。此处只扫一次建筑表，供下面浆果循环复用（≤2 个元素）。
    std::vector<std::pair<double,double>> builtGranaries;
    for (auto &b : info.buildings)
        if (b.Type == BUILDING_GRANARY && b.Percent == 100)
            builtGranaries.push_back({(b.BlockDR + 1.0) * BL, (b.BlockUR + 1.0) * BL});

    // 狮子防御统一由 manageLionDefense() 处理；此处只负责"跳过正在猎狮的村民"， 避免刚派出去的猎手被采集分配立刻改派去砍树/挖金。
    int goldWorkers = 0, woodWorkers = 0, stoneWorkers = 0, foodWorkers = 0;
    countFarmerWorkKinds(goldWorkers, woodWorkers, stoneWorkers, foodWorkers);

    // ★ 资源停采门禁（2026-09-01）：存量达上限即停止派/补采该资源，人力转向其他资源
    const bool woodStop  = (info.Wood >= (frame >= WAVE3_TIME ? WOOD_CAP_STOP_LATE : WOOD_CAP_STOP));
    // ★ 石头停采：14分钟(WAVE3_TIME)后不再采石，或存量≥STONE_CAP_STOP，或【建满 MAX_TOWERS 座箭塔后永久停采】。
    // 塔建满后石头再无用途（箭塔是唯一活的石头消耗，铜器塔升级被 DISABLE_TOWER_UPGRADE 封禁）⇒ 继续采石纯属浪费人力。
    // ⚠ 判据须用 countBuildings（仅 Percent==100 的"已建成"），**不能并列 countBuildingsExisting**：
    // 后者含【地基+在建+pending 90帧兜底】⇒ MAX_TOWERS=3 时第 2 座地基后就会叠加到 3 ⇒ towersDone 提前触发
    // ⇒ S=0、St=0 ⇒ 第 3 座永远拿不到 150 石。   ⚠ towerCount 成员也不能用：tryBuild 成功即 ++、塔被摧毁不回退 ⇒ "第2座被打掉"会永久误停采。
    // stoneStop 同时驱动「派工跳过采石」+「回撤撤走采石工」两个方向，一处改两处生效。
    const bool towersDone = (countBuildings(BUILDING_ARROWTOWER) >= MAX_TOWERS);
    const bool stoneStop = (frame >= WAVE3_TIME) || (info.Stone >= STONE_CAP_STOP) || towersDone;
    // ★ 黄金过剩判定（后期实测"黄金堆到 700+、木头食物都不够"）：命中 ⇒ goldTarget 压到 MIN_GOLD_WORKERS， 人力转去木头+食物。判定两种过剩： ① 绝对：存量 ≥ GOLD_CAP_STOP(1000)；
    // ② 相对：黄金/食物 超出 食物:黄金=5:3 目标配比的 1.25 倍（+50 基数避免早期食物为 0 误判）。
    // ⚠ 不得给反攻期加豁免：反攻期食物才是造兵瓶颈（复合弓40食/方阵60食，需求≈黄金 2 倍），     豁免会让金工无上限开采 → 食物跟不上 → 兵造不出 → 黄金只进不出。
    // 复核需求：一场反攻(20复合弓+10方阵) 黄金 ≈ 800，GOLD_CAP_STOP=1000 储备 + MIN_GOLD_WORKERS 持续产出够用。
    // ⛔【2026-09-18 已撤销的尝试，勿重犯】曾给相对分支加"食物≥200"前置（GOLD_RICH_FOOD_FLOOR）， 以为"食物低谷时判黄金过剩"是误判。**实测证伪**：不加守卫 G=6.2人(30%)/达标85%/负局4，
    // 加守卫 G=5.8人(28%)/达标82%/负局7 —— 每一项都更差。原因：goldRich 的语义本就是"黄金相对食物 过多 ⇒ 把金工调去食物"，而"食物低谷"恰恰是它**应该**触发的场景（全库 61/61 命中都在食物<200）。
    // ⇒ 把「设计语义」误读成「判据缺陷」（铁律 38 反面案例：回代只看了"命中在哪"，没看"命中是否合理"）。
    const bool goldRich =
        (info.Gold >= GOLD_CAP_STOP) ||
        ((double)info.Gold > (double)(info.Meat + 50) * (double)FOOD_GOLD_DEN
                             / (double)FOOD_GOLD_NUM * GOLD_RICH_TOL);
    // ★ 铜器时代前不采集黄金（2026-09-03 用户要求）：黄金是铜器主货币，铜器前用不上； 故 goldTarget 强制为 0，人力全投食物/木头/石头，加速攒 800 食物升铜器。
    const bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
    // ★ 食物停采门禁（2026-09-02）：食物≥阈值即不再派新食物工（浆果/瞪羚/大象/农场），
    // 已派食物工由下方回撤块逐步转去伐木——修"食物堆 1500+ 而木头只 50 不够"的失衡。   ★ 2026-09-03 修正：铜器升级要 800 食物，铜器前停采阈值必须 >800，
    // 否则食物到 500 就停采+撤食物工，永远攒不到 800 → 升级拖到 20 分钟。铜器前 850、铜器后 500。
    const bool foodStop = (info.Meat >= (postBronze ? FOOD_CAP_STOP : FOOD_CAP_STOP_PREBRONZE));
    // ★ 黄金目标人数：与食物工数按 5:3 配比（复合弓40食+20金 / 方阵60食+40金 ⇒ 100:60）。
    // ⚠⚠ 2026-09-18 实测结论：本目标在【中期基本不参与决策】——     中期(14~22分)空闲村民均值仅 0.03 人（Idle=0 占 98.0%），且无任何工种过剩
    // ⇒ 把它抬高 33%（5:3→5:4）后金工人数仍为 6.4、**零变化**，只多出 +26% 的重复金矿令
    // ⇒ 方案A 已回滚。要真正加人必须另建"显式转岗"机制，见 FOOD_GOLD_DEN 处记录。   黄金过剩时压到保底人数，把人力让给食物与木头。★
    int goldTarget = (!postBronze) ? 0
        : goldRich ? MIN_GOLD_WORKERS
        : std::max(MIN_GOLD_WORKERS,
                   (int)((double)foodWorkers * FOOD_GOLD_DEN / FOOD_GOLD_NUM + 0.999));

    // ★★★ 猎象整队（2026-09-13 用户需求：「狩猎大象必须 4 个人一起狩猎，单个村民狩猎会死」）★★★ 引擎事实：大象 45 血 / 攻 10 / 不逃跑 / 掉肉 300；村民 25 血 ⇒ 单人、双人必死。
    // 旧"逐帧凑人"（0 人在打时先派 1 人开团、其余随后几帧才到）⇒ 先到者在 1~3 人状态下被磨死（run7 实测）。 现改为【整队一次性出击】（同一帧下发 MIN 条令 ⇒ 同时出发/抵达/开打）：
    // ① on==0：本帧空闲村民 ≥ ELEPHANT_HUNT_MIN 才一次性派 4 人；凑不齐则【一人不派】； ② 0<on<MIN（战损）：能补齐到 MIN 就整批补上；补不齐且 on ≤ ELEPHANT_RESCUE_MAX_ON ⇒【孤兵必救】
    // 召回该村民 + 把大象拉黑，绝不让他独自送死； ③ MIN≤on<GROUP：已成团，允许整批补位到 GROUP(5)。   优先级与主循环严格一致：仅当"附近浆果/瞪羚已满员"时才开新团；出击名额写入 elephantPartyPending，
    // 主循环据此跳过这些村民，防止同帧被改派去砍树/农场。
    std::set<int> elephantPartyPending;   // 本帧已编入猎象队的村民SN
    {
        std::vector<int> elePool;         // 本帧真正空闲、可编队的村民（info.farmers 下标）
        for (size_t i = 0; i < info.farmers.size(); ++i) {
            auto &g = info.farmers[i];
            if (g.FarmerSort != FARMERTYPE_FARMER) continue;
            if (g.Resource > 0) continue;                             // 手上有资源，先送回
            if (g.NowState != HUMAN_STATE_IDLE) continue;              // 只动真正空闲的
            if (lionHunterSN.count(g.SN)) continue;
            if (buildingFarmerType.count(g.SN)) continue;
            elePool.push_back((int)i);
        }
        // 附近浆果(≤3人/丛, 30格内) 与 瞪羚(≤2人/只, 50格内) 是否都吃满人力； 没吃满 ⇒ 人力优先给它们（与主循环 bush→gazelle→elephant 顺序一致），本帧不开新象团。
        bool bushGazelleFull = true;
        for (auto &r : info.resources) {
            if (r.Cnt <= 0) continue;
            if (r.Type != RESOURCE_BUSH && r.Type != RESOURCE_GAZELLE) continue;
            double lim = (r.Type == RESOURCE_BUSH) ? 30.0 : (double)GAZELLE_HUNT_RANGE;
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > lim * BL) continue;
            int on = countFarmersOnTarget(r.SN);
            if (on < ((r.Type == RESOURCE_BUSH) ? 3 : 2)) { bushGazelleFull = false; break; }
        }
        // ★ 与主循环「木头→黄金→石头→食物」的优先级严格对齐（见下面主循环的派工顺序）：
        // 只有伐木/采金/采石目标人数都已吃满、且浆果瞪羚也都满员时，空闲村民才会落到"大象"这一档。   否则本帧不开新团 —— 不得让猎象抢走伐木/采金/采石的人力（严格保持改动前的优先级行为）。
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
            int on = countFarmersOnTarget(r.SN);
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
                        DebugText(QString("[ELEPHANT-RESCUE f=%1] 象SN=%2 仅%3人在打(凑不齐%4人)→召回孤兵%5人,拉黑%6帧").arg(frame).arg(r.SN).arg(on).arg(ELEPHANT_HUNT_MIN)
                                  .arg((int)lone.size()).arg(ELEPHANT_BAN_FRAMES));
                    }
                    continue;
                }
                int sent = eleDispatch(&r, need);
                DebugText(QString("[ELEPHANT-PARTY f=%1] 整队出击 象SN=%2 已在打%3人 本帧一次派%4人(同帧出发) 空闲池余%5 meat=%6 pop=%7")
                          .arg(frame).arg(r.SN).arg(on).arg(sent).arg((int)elePool.size()).arg((int)info.Meat).arg((int)info.farmers.size()));
            } else {
                if (foodStop) continue;                                  // 食物过剩 → 不再补人打肉
                int need = std::min(ELEPHANT_HUNT_GROUP - on, (int)elePool.size());
                if (need <= 0) continue;
                int sent = eleDispatch(&r, need);
                DebugText(QString("[ELEPHANT-TOPUP f=%1] 已成团补位 象SN=%2 已在打%3人 补%4人 空闲池余%5").arg(frame).arg(r.SN).arg(on).arg(sent).arg((int)elePool.size()));
            }
        }
    }

    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (f.Resource > 0) continue;
        if (f.NowState != HUMAN_STATE_IDLE) continue;
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

        // ★ 黄金：与食物按 5:3 配比（复合弓兵+方阵兵成本综合）；不受木头/石头门禁影响， 但受「黄金过剩」约束——goldRich 时 goldTarget 已被压到 MIN_GOLD_WORKERS，人力自动落到食物/木头。
        if (goldWorkers < goldTarget) {
            auto gold = findNearestResource(RESOURCE_GOLD, f.DR, f.UR);
            if (gold) {
                HumanAction(f.SN, gold->SN);
                goldWorkers++;
                continue;
            }
        }

// ★ 石头供给（箭塔/投石兵/建筑维修需要）：复合弓兵/阔剑兵引擎现已修正为扣「食物 + 黄金」(非石头)， 故不再把采金工转去采石（旧逻辑会在金≥200 时把所有金矿工每帧重派去采石，造成重复下令刷屏）。
// 采石仅由本保底块负责：不达停采上限(!stoneStop) 就保底派 STONE_WORKERS_LATE 人采石。
// ★ 2026-09-03 修复"前期没人采石"：删掉过时门槛 —— 那是"石头只用于投石兵/铜器塔升级"时代的产物， 现在箭塔前期就要建、投石兵已取消 ⇒ 该门槛恒 false、第 2 座箭塔(需额外 150 石)一直建不出。
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
        // 本空闲村民改派伐木（修"食物堆 1500+ 而木头只 50 不够"）。木头也满时才跳过（此时食/木都过剩，无需再采）。
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
            // ★ 2026-09-07 放宽：原"距 TC >20 格即跳过"会让远距浆果群(已在其旁建第二谷仓)无人采集。 现在：距 TC ≤20 格 **或** 距任一【已建成】谷仓 ≤BUSH_NEAR_GRANARY_DIST(20) 格 → 可派。
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > 20 * BL) {
                bool nearGranary = false;
                for (auto &gd : builtGranaries)
                    if (calDistance(r.DR, r.UR, gd.first, gd.second) <= BUSH_NEAR_GRANARY_DIST * BL) {
                        nearGranary = true; break;
                    }
                if (!nearGranary) continue;
            }
            int onBush = countFarmersOnTarget(r.SN);
            int totalOnBush = onBush + assignedBush[r.SN];
            if (totalOnBush >= 3) continue;
            double d = dist2(r.DR, r.UR, f.DR, f.UR);
            double score = d * (1.0 + totalOnBush * 0.8);
            if (score < bestBushScore) { bestBushScore = score; bestBush = &r; }
        }
        if (bestBush) {
            HumanAction(f.SN, bestBush->SN);
            assignedBush[bestBush->SN]++;
            frameBushCount[bestBush->SN]++;
            continue;
        }

        tagResource* bestGazelle = nullptr;
        double bestGazelleDist = 1e12;
        for (auto &r : info.resources) {
            if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) continue;
            // ★ 2026-09-04 范围放宽：30→GAZELLE_HUNT_RANGE(50) 格，覆盖远距未建仓库的瞪羚群
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > GAZELLE_HUNT_RANGE * BL) continue;
            int onGazelle = countFarmersOnTarget(r.SN);
            if (onGazelle + assignedGazelle[r.SN] >= 2) continue;
            double d = dist2(r.DR, r.UR, f.DR, f.UR);
            if (d < bestGazelleDist) { bestGazelleDist = d; bestGazelle = &r; }
        }
        // ★ 2026-09-12「先建仓库再打猎」：交付仓库没就位就本帧不派猎人（continue 到下一资源类型/兜底）， 仓库块已在 manageBuildings 最前面以最高优先级抢建。
        if (bestGazelle && gazelleDropoffReady(bestGazelle)) {
            HumanAction(f.SN, bestGazelle->SN);
            assignedGazelle[bestGazelle->SN]++;
            frameGazelleCount[bestGazelle->SN]++;
            continue;
        }

        // ★ 组队猎象已【上移】到本函数主循环之前的"猎象整队"块（2026-09-13）：
        // 旧实现在这里逐帧凑人（先派 1 人开团、其余随后到）→ 先到者单人被打死；   现在统一由整队块【同一帧一次性派够 4 人】出击，此处不再单独下发，避免出现 1~3 人的散兵。

        // ★ 农场：每座农场"有且仅有一人"。跳过本帧已派的农场，且已有≥1工人(实时)的也跳过，杜绝重复派工
        tagBuilding* farm = nullptr;
        for (auto &b : info.buildings) {
            if (b.Type != BUILDING_FARM || b.Percent < 100) continue;
            if (assignedFarm.count(b.SN)) continue;        // 本帧已派过，跳过
            int onFarm = countFarmersOnTarget(b.SN);
            if (onFarm >= 1) continue;                     // 已有工人，不再加派
            farm = &b; break;
        }
        if (farm) {
            HumanAction(f.SN, farm->SN);
            assignedFarm[farm->SN] = f.SN;                 // 记录，本帧内后续空闲村民不会再来这座
            frameFoodTargets.insert(farm->SN);
            continue;
        }

        // ★ 兜底：前面所有食物来源(BUSH/GAZELLE/ELEPHANT/FARM)都不可用→伐木，绝不空闲。
        // 不受 woodTarget 上限约束：食物耗尽时即便已有 ≥woodTarget 个伐木工，也把多余空闲村民派去伐木，   避免村民站在原地空耗（用户需求：村民没有可选食物采集的目标时伐木）。
        // ★ 兜底：前面食物来源都不可用 → 优先黄金(5:3配比)，其次伐木。
        // ⚠ 兜底伐木不受 woodStop 限制：木闸只负责"有其它出口时不主动补采"，
        //   不能反过来让四类出口全关时村民原地 IDLE（见 aoe3_idle_deadzone_20260921.html 方案 A）。
        auto goldRes = findNearestResource(RESOURCE_GOLD, f.DR, f.UR);
        if (goldRes && goldWorkers < goldTarget) {
            HumanAction(f.SN, goldRes->SN); goldWorkers++;
        } else {
            auto tree = findBestWoodTree(f.DR, f.UR);
            if (tree) {
                HumanAction(f.SN, tree->SN);
                woodWorkers++;
            }
        }
    }

    // ========== ★ 资源达上限回撤：把多余伐木/采石/采金工转移到缺口资源 ========== 木头≥WOOD_CAP_STOP / 石头≥STONE_CAP_STOP / 黄金过剩 时，已派工人应停采，人力转去"当前最缺的资源"：
    // 缺木(<120) 时直接去伐木，否则先食物、食物接不住再伐木（不再转黄金，黄金正是过剩方）。 节流：每 10 帧最多撤 1 人（防震荡）；伐木保留 WOOD_KEEP_MIN 保底，采石全撤，采金保留 MIN_GOLD_WORKERS。
    // ★★★ 2026-09-17 修「采金人数偏少」：撤销 "woodOverTarget" 入口闸 ★★★ ⚠⚠ 血泪：第一版把内层条件 `woodWorkers > woodTarget` 并进入口闸 ⇒ 伐木令暴涨 7 倍、金工达成率反降 5.6~16pt。
    // 回代根因：woodWorkers 是【当前帧还在伐木的人数】，被撤的村民当帧变 WALKING、下一帧主循环见他"空闲"
    // 又派回伐木 ⇒ 判据每 10 帧重新为真 ⇒ 回撤块每轮撤 1 人、随即被补回（gx2：24 人发出 1735 条树令）。
    // ⇒ **"用当期计数判超编"在本架构下是正反馈，不成立**（计数滞后于人员调度）。   故入口闸恢复原状；"伐木滞留区"改由【派工端限流】处理（见主循环 woodTarget 处）。
    if ((woodStop || stoneStop || goldRich || foodStop) && frame % 10 == 0) {
        const bool woodHungry = (info.Wood < WOOD_LOW_LINE);
        for (auto &f : info.farmers) {
            if (f.FarmerSort != FARMERTYPE_FARMER) continue;
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
            // ★★★ 2026-09-17 修「采金人数偏少」：本 lambda 必须【同步维护计数】★★★ ⚠⚠ 真坑（第一版实跑把伐木令抬高了 587%、金工反而少 4 成）：旧 lambda 只做 `HumanAction(...)`，
            // **从不修正 goldWorkers/woodWorkers/foodWorkers**。而调用方（回撤块）判据里用到的正是这些计数： `woodOverTarget = (woodWorkers > woodTarget)`
            // ⇒ 把人从伐木撤走后 woodWorkers 不降 ⇒ 闸【恒真】⇒ 回撤块每 10 帧都进来白撤 1 人 ⇒
            // 伐木令雪崩 1055 → 7248 条，金工达成率 50.7% → 45.1%。   铁律 26 的推广：**判据与被判据的对象必须由同一份状态维护**。
            // 调用方传入 `fromKind`（该村民撤走前属于哪类）以便 `--` 对应计数：0=未知(不动账) 1=金 2=木 3=石 4=食
            auto reassignToDeficit = [&](tagFarmer &w, int fromKind)->bool {
                // 辅助：成功转岗后同步扣减原岗计数、增加新岗计数
                auto commit = [&](int toKind) {
                    if (fromKind == 1) goldWorkers--;
                    else if (fromKind == 2) woodWorkers--;
                    else if (fromKind == 3) stoneWorkers--;
                    else if (fromKind == 4) foodWorkers--;
                    if (toKind == 1) goldWorkers++;
                    else if (toKind == 2) woodWorkers++;
                    else if (toKind == 3) stoneWorkers++;
                    else if (toKind == 4) foodWorkers++;
                };
                // ★ 黄金缺口优先（放在最前）：本 lambda 的调用场景是"该资源已过剩、要把人挪去缺口"，
                // 而 goldTarget 由 foodWorkers 推算 ⇒ 若先补食物，会让食物工更多、goldTarget 更高、   黄金缺口更大，形成正反馈。故黄金缺口必须最先判定。
                // ⚠ 本项是"挪岗"的必要出路：若连它都不成立，说明黄金也满了，再谈食物/伐木。
                if (goldWorkers < goldTarget) {
                    auto g = findNearestResource(RESOURCE_GOLD, w.DR, w.UR);
                    if (g) { HumanAction(w.SN, g->SN); commit(1); return true; }
                }
                if (woodHungry) {
                    auto t = findBestWoodTree(w.DR, w.UR);
                    if (t) { HumanAction(w.SN, t->SN); villLastTreeSN[w.SN] = t->SN; commit(2); return true; }
                }
                if (tryAssignFood(&w)) { commit(4); return true; }
                if (!woodStop) {                          // ★ 木头达标时不把人塞回树（避免无意义重派刷屏）
                    auto t2 = findBestWoodTree(w.DR, w.UR);
                    if (t2) { HumanAction(w.SN, t2->SN); villLastTreeSN[w.SN] = t2->SN; commit(2); return true; }
                }
                return false;
            };

            bool reassigned = false;
            if (foodStop && isFood) {
                // ★ 2026-09-24 用户反馈：14 分钟一到农场的人全跑去伐木。
                //   食物停采只应停止【新派】食物工，不应把每座农场最后的 1 个工人也抽走；
                //   否则 postW3 反攻期食物断供。这里保留正在农场工作的村民。
                bool onFarm = false;
                for (auto &b : info.buildings)
                    if (b.SN == f.WorkObjectSN && b.Type == BUILDING_FARM) { onFarm = true; break; }
                if (onFarm) continue;
// ★ 食物过剩：食物工直接转伐木（木头偏少时补木；木头满则转黄金，黄金也满才罢休）。
// ★★★ 2026-09-17：本条【独立分支】同样必须维护计数 ★★★ 旧写法只发 HumanAction 不动账 ⇒ foodWorkers 不减 ⇒
// `goldTarget = foodWorkers*3/5` 被永久抬高 ⇒ 黄金目标虚高却没人去采（实测食物工 7~10 人而食物存量只剩 10）。 铁律 26/37 的同一形态：**凡是"把人挪岗"的地方都要动账，一处不动就留下永久偏差**。
                auto t = findBestWoodTree(f.DR, f.UR);
                if (t && !woodStop) {
                    HumanAction(f.SN, t->SN); villLastTreeSN[f.SN] = t->SN;
                    foodWorkers--; woodWorkers++;           // ★ 动账
                    reassigned = true;
                } else {
                    auto g = findNearestResource(RESOURCE_GOLD, f.DR, f.UR);
                    if (g && postBronze && !goldRich) {
                        HumanAction(f.SN, g->SN);
                        foodWorkers--; goldWorkers++;       // ★ 动账
                        reassigned = true;
                    }
                }
            } else if (stoneStop && isStone) {
                // 石头达标：采石工全撤
                reassigned = reassignToDeficit(f, 3);
            } else if (goldRich && isGold && goldWorkers > MIN_GOLD_WORKERS) {
                // 黄金过剩：采金工撤到只剩保底人数
                reassigned = reassignToDeficit(f, 1);
            } else if (woodStop && isWood && woodWorkers > WOOD_KEEP_MIN) {
// ★★★ 2026-09-17 撤销 "woodWorkers > woodTarget" 条件 ★★★ 原写法：`(woodStop || woodWorkers > woodTarget) && isWood && ...` —— 实测把伐木令抬高 7 倍、金工达成率反降。
// "木头 100~220 滞留区"改由【派工端】解决：主循环 `if (!woodStop && woodWorkers < woodTarget)` 已限制"不超目标就加人"。
// ⚠ 教训：**"超标"用"每帧撤一点"的方式修正，只要存在"补人"的反向路径，就必然震荡**。
                reassigned = reassignToDeficit(f, 2);
            }
            if (reassigned) break;  // 每 10 帧最多撤 1 人，防震荡
        }
    }

    // ★ 资源调度自检打印（便于实测调参）：存量 / 各资源工数 / 门禁状态
    if (frame % 600 == 0) {
        DebugText(QString("ECO | Fd:%1 Wd:%2 St:%3 Gd:%4 || workers F%5 W%6 G%7 S%8 || goldRich:%9 woodStop:%10 stoneStop:%11 foodStop:%12 woodTarget:%13 twr:%14/%15")
                  .arg((int)info.Meat).arg((int)info.Wood).arg((int)info.Stone).arg((int)info.Gold).arg(foodWorkers).arg(woodWorkers).arg(goldWorkers).arg(stoneWorkers)
                  .arg(goldRich ? 1 : 0).arg(woodStop ? 1 : 0).arg(stoneStop ? 1 : 0).arg(foodStop ? 1 : 0).arg(woodTarget).arg(countBuildingsExisting(BUILDING_ARROWTOWER)).arg(MAX_TOWERS));
    }

    // ========== ★ 农场"有且仅有一人"强制校验（兜底） ========== 任何一帧若发现某农场工人数≥2，立即把多余工人转移到空农场或伐木；
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
        int realCount = countFarmersOnTarget(r.SN);
        if (realCount >= 2) continue;  // 每只≤2人
        if (d < bestDist) { bestDist = d; bestGazelle = &r; }
    }
    if (!bestGazelle) return;

    // ★ 2026-09-12「先建仓库再打猎」：交付仓库未就位 → 本帧不派猎人（仓库优先建，见 manageBuildings）。 参考录像同一动作：01:35 抵达猎场 → 01:47 就地建仓库 → 02:05 仓库落成。
    if (!gazelleDropoffReady(bestGazelle)) {
        if (frame % 300 == 0)
            DebugText(QString("[GAZELLE f=%1] 暂缓打猎：等猎场仓库落地 (目标SN=%2)").arg(frame).arg(bestGazelle->SN));
        return;
    }

    // ★ 只用空闲农民，不抢采浆果的 ★
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN)) continue;
        if (huntingGroup.count(f.SN)) continue;  // 已分配过，不重复设
        if (f.Resource > 0) continue;
        if (f.NowState != HUMAN_STATE_IDLE) continue;  // 只等空闲

        HumanAction(f.SN, bestGazelle->SN);
        huntingGroup.insert(f.SN);
        return;  // 每帧最多分配1个猎人
    }
}

// ★ 狮子防御：狮子逼近/攻击我方单位时立刻就近派人猎杀。 引擎事实（Animal.cpp::isMonitorObject）：狮子只攻击【村民】与【非祭司军队】，不攻击祭司/建筑。
// 两级威胁：紧急级(已掉血且狮子≤2格 → 可打断采集/赶路强行抽人) / 预警级(≤6格 → 只派空闲村民)。   人力：每只狮 4 人（狮 20 血，2 人打不完会送命）；贴脸(≤4格)的空闲军队优先上。
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
            DebugText(QString("Lion DEFENSE lion=%1 dist=%2 attacking=%3 victim=%4 hunters=%5/%6").arg(th.lion->SN).arg(th.dist / BL, 0, 'f', 1).arg(th.attacking ? 1 : 0).arg(th.victimSN)
                      .arg(LION_HUNTER_GROUP - need).arg(LION_HUNTER_GROUP));
    }
}

// 科技升级（铜器后三级制：军事解锁 > 军事强化 > 经济）
void UsrAI::manageTechUpgrade() {
    if (techCooldown > 0) return;
    if (info.Meat < FOOD_PAUSE_TECH_TRAIN) return;

    bool done = false;
    bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
    // ★ 2026-09-24 用户需求：铜器前也第一时间研究木材加工 —— 只要市场就绪、食物≥120、木≥75 就直接研究，
    //   不再等 postBronze；代价是会提前消耗 120 食物/75 木，800 食物升铜节奏可能略受影响。
    // ★★★ 2026-09-12 用户要求：【伐木科技 = 解锁类科技最优先】★★★ 市场·木材加工（120食物+75木材 → 伐木+2 / 远程攻击距离+1）。原位置在 TIER3 末尾，且被两道锁压住：
    // ① `frame < WAVE3_TIME`(21000帧=14min) 前置锁 ② `milUnlocked`(军事解锁) 锁   ⇒ 最坏要 14 分钟以后、且军事科技全部研究完才轮得到它。
    // 该块现在位于所有科技检查之前，Tool/Bronze 两个阶段都会尝试。
    // 仍然保留：函数首 techCooldown 节流 / FOOD_PAUSE_TECH_TRAIN / 市场空闲与成本闸。
    // 硬依赖：必须先有【市场】建筑且 Project==ACT_NULL。
    // ★ 与复合弓(P0)的食物/木材竞争：见宏 WOOD_TECH_ABSOLUTE_FIRST。
    if (!DISABLE_MARKET_WOOD_TECH && !done && !marketWoodUpgraded) {
        auto mw = findBuilding(BUILDING_MARKET);
        if (mw && mw->Project == ACT_NULL && info.Meat >= 120 && info.Wood >= 75) {
            bool bowPending = (!compositeBowResearched && !compositeBowQueued);
            bool okToGo = true;
            if (bowPending && !WOOD_TECH_ABSOLUTE_FIRST) {
                // 复合弓未就绪 → 要求"两项都负担得起"才允许伐木插队： 食物(伐木120 + 复合弓180) 与 木材(伐木75 + 复合弓100) 都不能被伐木吃掉，
                // 否则会出现"伐木研究完，复合弓的木/食不够，反而延后"的负优化。
                okToGo = (info.Meat >= 120 + BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_FOOD) &&
                         (info.Wood >= 75 + BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_WOOD);
            }
            if (okToGo) {
                BuildingAction(mw->SN, BUILDING_MARKET_WOOD_UPGRADE);
                marketWoodUpgraded = true; done = true;
                DebugText(QString("!! TECH WoodProcessing(伐木+2) f=%1 meat=%2 wood=%3 bowPending=%4 absFirst=%5").arg(frame).arg((int)info.Meat).arg((int)info.Wood)
                    .arg(bowPending ? 1 : 0).arg(WOOD_TECH_ABSOLUTE_FIRST ? 1 : 0));
            }
        }
    }

    // ★ 伐木科技诊断（每 100 帧，只读）：定位"为何迟迟不研究" —— 市场是否就绪 / 资源差多少
    if (!marketWoodUpgraded && frame % 100 == 0) {
        auto mwd = findBuilding(BUILDING_MARKET);
        int mktProj = -9;
        if (mwd) mktProj = (int)mwd->Project;
        DebugText(QString("[WP f=%1] mkt=%2 proj=%3 meat=%4 wood=%5 bowPend=%6 abs=%7").arg(frame).arg(mwd ? 1 : 0).arg(mktProj).arg((int)info.Meat).arg((int)info.Wood)
            .arg((!compositeBowResearched && !compositeBowQueued) ? 1 : 0).arg(WOOD_TECH_ABSOLUTE_FIRST ? 1 : 0));
    }


    // ★ 2026-09-20 精简：谷仓箭塔科技链收口 —— 同一判据原先在 3 处（preW3 / milUnlocked 前 / TIER2）各写一遍， 逐字等价 ⇒ 抽为 lambda，调用点保持原位置 + 原守卫。findBuilding 为纯查找（只读循环），
    // 故 TIER2 那处把 `info.Meat >= 50` 提到外层与放在内层无行为差异，一并收口。
    // ⚠ 2026-09-24 **守卫已改**：新增 `!done &&` ⇒ 塔科技改为**受 done 串行**（本帧已发伐木/复合弓令则跳过），原先不受此限。
    auto tryArrowTowerTech = [&]() {
        if (!done && !towerTechResearched) {
            auto g = findBuilding(BUILDING_GRANARY);
            if (g && g->Project == ACT_NULL && info.Meat >= 50) {
                BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWER);
                towerTechResearched = true; done = true;
            }
        }
    };
    auto tryBronzeTowerUpgrade = [&]() {
        if (!DISABLE_TOWER_UPGRADE && !done && !bronzeTowerUpgraded && towerTechResearched) {
            auto g = findBuilding(BUILDING_GRANARY);
            if (g && g->Project == ACT_NULL && info.Meat >= 120 && info.Stone >= 50) {
                BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWE_UPGRADE);
                bronzeTowerUpgraded = true; done = true;
            }
        }
    };

    // ★ 原 preW1（第一波前只许阔剑科技）门槛已移除：复合弓科技现在「能解锁就解锁」，不再受波次阶段限制。
    // ★ 开局即研究箭塔科技（不等铜器/第3波/军事解锁）：有谷仓+50食物就研究，解锁箭塔建造 ★
    if (!done && !towerTechResearched) {
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

    // ★ 从游戏状态同步布尔值（检查建筑是否真在研究中，已扣资源）★ 不使用乐观标记！必须确认科技已经"付款"正在执行
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
            compositeBowQueued = false;   // ★ 引擎未受理（时代/资源被拒）⇒ 允许重试，不能乐观判成已研究
        }
    }

    // ==================================================================
    // ★★★ 2026-09-13 用户要求：【复合弓科技与护甲科技同一解锁窗口，不再互相阻塞】★★★
    // 体感来源：实测 8 局发令帧中位 ≈ 19000(12.7 分)、最晚 24759，已过 WAVE3=21000 反攻线 ⇒ 反攻期前半段只能产【普通弓兵】(射程 5、无科技)；
    //   ⚠ 2026-09-24 起**普通弓兵兜底分支已删** ⇒ 现在那个空窗是"**一个弓兵都产不出**"（靶场空转），不再是产普通弓兵。
    // 根因二：① 本块原排在伐木块之后且受 `done` 串行（伐木本帧发令 ⇒ 本块当帧跳过）；② **木材供给才是真瓶颈** —— 12 座农场从 f≈13500 连建把木材长期压在 2~112
    //   （k1: f=16380 wood=15 / f=20970 wood=2），而复合弓要 wood≥100（食物早已 208→621 远超 180）⇒ 从 f=13500 每 30 帧空转到 f=24759 才发令。
    // ★ 解锁类科技（复合弓/护甲链）互不阻塞；但本帧已下其他科技令时 (`done`) 不再抢同帧资源，下一帧重试。
    // ★ 引擎硬前置：复合弓科技要求 CIVILIZATION_BRONZEAGE（Development.cpp），
    //   因此本块必须放在 `if (!postBronze) return;` 之后；铜器前只做木材加工，不碰复合弓。
    // ==================================================================
    // ★ 引擎真实成本（Development.cpp:739-740）：只需「铜器时代 + 木材 + 食物」，**不需要黄金**，
    // 且引擎层无阔剑前置 ⇒ 旧代码的 info.Gold>=40 是伪门槛，黄金不足时复合弓永远研究不了。 --- Range: 复合弓科技（解锁类：不被 done 阻塞）---
    if (!done && !compositeBowResearched && !compositeBowQueued) {
        auto r = findBuilding(BUILDING_RANGE);
        // ★ 复合弓科技诊断：每 30 帧打印一次闸门状态，定位"为什么不立刻升级"
        if (frame % 30 == 0) {
            int rngPct = -1, rngProj = -2;
            auto rngAll = findBuildingIncludingUnderConstruction(BUILDING_RANGE);
            if (rngAll) { rngPct = rngAll->Percent; rngProj = rngAll->Project; }
            bool meatOK = (info.Meat >= BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_FOOD);
            bool woodOK = (info.Wood >= BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_WOOD);
            bool readyOK = (r && r->Project == ACT_NULL && meatOK && woodOK);
            DebugText(QString("[CB f=%1] rngFound=%2 rngPct=%3 rngProj=%4 meat=%5(%6) wood=%7(%8) techCD=%9 ready=%10").arg(frame).arg(r ? 1 : 0).arg(rngPct).arg(rngProj)
                .arg((int)info.Meat).arg(meatOK ? 1 : 0).arg((int)info.Wood).arg(woodOK ? 1 : 0).arg(techCooldown).arg(readyOK ? 1 : 0));
        }
        if (r && r->Project == ACT_NULL &&
            info.Meat >= BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_FOOD &&
            info.Wood >= BUILDING_RANGE_UPGRADE_COMPOSITE_BOW_WOOD) {
            BuildingAction(r->SN, BUILDING_RANGE_UPGRADE_COMPOSITE_BOW);
            compositeBowQueued = true;
            done = true;
            DebugText(QString("!! TECH CompositeBow f=%1 meat=%2 wood=%3").arg(frame).arg((int)info.Meat).arg((int)info.Wood));
        }
    }


    // ================================================================== --- Army camp: 阔剑科技（封禁中，见 DISABLE_BROADSWORD_TECH）---
    // 引擎条件已修正：阔剑科技现真扣 食物+黄金（need_Stone=0）。若解禁：把开关改 false，   且下方判据应改回 info.Gold（而非当前 info.Stone）。
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

    // ★ 箭塔科技提前（已解除门槛）：铜器后立即可研究，不等第3波、不要求军事解锁 ★ 铜器箭塔升级：用户要求"箭塔只用解锁就行，不用升级"→ 用 DISABLE_TOWER_UPGRADE 封禁（省120食物+50石头）
    tryArrowTowerTech();
    tryBronzeTowerUpgrade();

    // ==================================================================
    // ★ TIER 2+3 前置锁：军事解锁前不研究任何其他科技 ★
    // ================================================================== Before wave 3, only military unlock techs may be researched.
    if (frame < WAVE3_TIME) {
        if (done) techCooldown = 25;
        return;
    }

    bool milUnlocked = (broadswordResearched || compositeBowResearched);
    if (!milUnlocked) {
        tryArrowTowerTech();
        if (done) techCooldown = 25;
        return;
    }

    // ★ TIER 2：军事强化 ★

    // --- 仓库：工具使用（近战+2） ---
    if (!DISABLE_USETOOL_TECH && !done && !useToolDone && info.Meat >= 100) {
        auto s = findBuilding(BUILDING_STOCK);
        if (s && s->Project == ACT_NULL) {
            BuildingAction(s->SN, BUILDING_STOCK_UPGRADE_USETOOL);
            useToolDone = true; done = true;
        }
    }

    // --- 仓库：护甲科技链（步兵/弓兵 各两级：护甲 → 鳞甲）★ 2026-09-13 用户要求解锁 --- ① 引擎两柄机制：同一动作 ID 调两次 = 一级护甲 → 二级鳞甲；靠 `Project` 闸门天然串行。
    // ② 顺序（用户定案）：一级先铺满 —— 步兵护甲 → 弓兵护甲 → 步兵鳞甲 → 弓兵鳞甲。 ③ 防"发令即置真"卡死（同铜器升级铁律）：发令只记 pending，下一帧看仓库是否变忙来确认引擎已受理；
    // ARMOR_ACCEPT_TIMEOUT 帧内仓库仍空闲 ⇒ 回滚刚加的级数，下帧重试。 ④ ★ 必须【锁定仓库 SN】：多仓库阵型（MAX_STOCK=4）下 findBuilding(BUILDING_STOCK) 在不同帧可能返回
    // 不同仓库 —— 实测 2 座仓库时 Project 会在"研究中(15)/空闲(0)"之间抖动，制造大量伪"完成"边沿 （run2 曾误报 144 条 [ARMOR-DONE]）。锁定后只读同一座仓库的 Project，边沿才真实。
    if (!done) {
// ⑤ ⚠ 完成度过滤不可省：`findBuilding` 的真实过滤是 `Percent == 100`；若按裸 Type 选到【在建地基】的仓库，
// 引擎会拒研（实测 run2/run4 因此回滚 11~12 次，直到地基完工才受理，白等 ~1450 帧）。故两处选择都要求 Percent==100。
// ⑥ 注意：① 锁定查找【不能】加 Percent==100 过滤 —— 研究期间该仓库的 Percent 可能短暂 !=100， 若加过滤会导致整块被跳过（实测 run1 [ARMOR-ACK] 因此迟了 421 帧）。过滤只用在②初始挑选。
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
                    DebugText(QString("[ARMOR-ACK f=%1] 链=%2 引擎已受理，开始研究(~40s)").arg(frame).arg(armorPendingKind == 1 ? "步兵" : "弓兵"));
                    armorPendingKind = 0;
                } else if (frame - armorPendingFrame > ARMOR_ACCEPT_TIMEOUT) {
                    if (armorPendingKind == 1) { if (infArmorLevel > 0) infArmorLevel--; }
                    else                       { if (arcArmorLevel > 0) arcArmorLevel--; }
                    DebugText(QString("[ARMOR-RETRY f=%1] 链=%2 引擎未受理→回滚级数 inf=%3 arc=%4 meat=%5 gold=%6").arg(frame).arg(armorPendingKind == 1 ? "步兵" : "弓兵")
                        .arg(infArmorLevel).arg(arcArmorLevel).arg((int)info.Meat).arg((int)info.Gold));
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
                    DebugText(QString("[ARMOR f=%1] 研发 %2%3 meat=%4 gold=%5 wood=%6").arg(frame).arg(wantKind == 1 ? "步兵" : "弓兵").arg(wantLvl == 1 ? "护甲(近战防御+2)" : "鳞甲(再+2)")
                        .arg((int)info.Meat).arg((int)info.Gold).arg((int)info.Wood));
                }
            }
            // ③ 观测：仓库科技完成边沿（验证"确实研成"）
            int curStockProj = (int)armSt->Project;
            if (prevStockProject != ACT_NULL && curStockProj == ACT_NULL) {
                DebugText(QString("[ARMOR-DONE f=%1] 上一条仓库科技完成(prevID=%2) meat=%3 gold=%4 infLvl=%5 arcLvl=%6").arg(frame).arg(prevStockProject).arg((int)info.Meat).arg((int)info.Gold)
                    .arg(infArmorLevel).arg(arcArmorLevel));
            }
            prevStockProject = curStockProj;
        }
    }

    // --- 谷仓：箭塔科技链（解锁 + 铜器升级），判据已收口到函数首的两个 lambda ---
    tryArrowTowerTech();
    tryBronzeTowerUpgrade();

    // ==================================================================
    // ★ TIER 3：经济科技 — 成本价即研究 ★
    // ==================================================================
    // ★ 2026-09-12 用户要求：市场·木材加工（伐木）已【上移】到本函数铜器后第一位
    // （见上方 "伐木科技 = 解锁类科技最优先" 段，越过 WAVE3 与 milUnlocked 两锁）。   此处不再重复判定，避免二次研究/重复扣资源。

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

// 军事管理（训练 + 箭塔防御 + 护祭司 + 自动作战）
// 军事训练的 A 段：训练链。2026-09-23 从 manageMilitary 抽出，逻辑未改；由 manageMilitary 每帧调用。
// 入参 isWarTime = (state ∈ [DEFENSE_WAVE1, DEFENSE_WAVE3])。
// 只负责"发训练令"；箭塔指挥 / 军队搜敌 / 回基地待命仍留在 manageMilitary 的 B~D 段。
void UsrAI::trainMilitaryUnits(bool isWarTime) {
    bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
    int humanPop = info.farmers.size() + info.armies.size();
    // ====== A. 军事训练 ======
    if (trainCooldown > 0) trainCooldown--;
    // ★ 反攻阶段「能产弓就产弓」：不再受 FOOD_PAUSE_TECH_TRAIN(60食物) 经济保护闸压制， 只要食物够一个弓箭手成本就开产（反攻期把资源变成兵比屯食物更有价值）。
    int trainMinFood = (state >= COUNTERATTACK)
                     ? BUILDING_RANGE_CREATE_BOWMAN_FOOD
                     : FOOD_PAUSE_TECH_TRAIN;
    if (info.Meat >= trainMinFood && trainCooldown <= 0 && humanPop < info.Human_MaxNum) {
        bool trained = false;

// ★ 前期棍棒兵过渡：放在训练链最前 —— 4~15 分钟空窗期这是唯一自产兵力途径
// （复合弓被 COMPOSITE_BOW_MIN_FRAME 停产、工具时代填线被 DISABLE_CLUBMAN_TRAIN 关掉）。   只统计【存活】棍棒兵 → 战损自动补造，不会因一次团灭永久断兵。
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
            // 工具时代练兵上限：W1 前 2 个(不拖慢 800 食物升铜器)，W1 开始后提到 6 个—— 铜器未升完前本块是唯一产出(廉价填线块 postBronze 才生效)，W1→W2 约 8500 帧够补到 6 个护祭司。
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

            // ★★ 反攻期专用编制：只产 复合弓兵(主) + 方阵兵(副)，必须走独立分支 ★★
            // 优先级3"爆近战"不检查 trained 会照样产棍棒/骑兵；优先级4 骑兵吃掉 80 黄金   = 4 个复合弓的黄金 → 黄金长期 <20 → 复合弓判据失败 → 退化成停产。
            if (counterAtk) {
                // ① 复合弓兵（主 DPS）：遍历所有空闲靶场并行产，产量随靶场数(MAX_RANGES)线性提升。 真实扣费 = 食物 + 黄金(20)，不扣石头(Development.cpp:744-745，引擎已修正)。
                // ★ 2026-09-24 用户要求：靶场只产复合弓兵，不产普通弓箭手；黄金不足或科技未出时宁可空转。
                for (auto &b : info.buildings) {
                    if (b.Type != BUILDING_RANGE || b.Project != ACT_NULL) continue;
                    // ★ 15 分钟前完全停产（2026-09-06 用户要求）：见 COMPOSITE_BOW_MIN_FRAME
                    if (frame < COMPOSITE_BOW_MIN_FRAME) continue;
                    if (compositeBowResearched &&
                        info.Meat >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_FOOD &&
                        info.Gold >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_GOLD) {
                        BuildingAction(b.SN, BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN);
                        trained = true;
                    }
                }

                // ② 方阵兵（副，肉盾挡刀）：双保险保证"复合弓兵为主"——   a) 黄金预留：付完方阵后仍须够【所有空闲靶场各产一个复合弓】(方阵40金 vs 复合弓20金)；
                // b) 比例闸：现役方阵 < HOPLITE_RATIO_NUM/DEN × 复合弓数 + HOPLITE_RATIO_FLOOR （2026-09-13 由 1:2 放宽为 3:4；comp≤2 时与旧版一致，零弓兵也先出 2 个顶前排）。
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
                    DebugText(QString("[HOPLITE-ATK f=%1] 反攻期产方阵兵 现役hop=%2 comp=%3 limit=%4 meat=%5 gold=%6(kept%7)").arg(frame).arg(nHopNow).arg(nCompNow).arg(hopLimitNow)
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
                                      "|| ranges:%7/idle:%8 gold:%9 compositeTech:%10").arg(nComp).arg(nBow).arg(nHop).arg(nClub).arg(nCav).arg(nOther)
                              .arg(countBuildingsExisting(BUILDING_RANGE)).arg(idleRanges).arg((int)info.Gold).arg((int)compositeBowResearched));
                }
            } else {
            // ============ 非反攻期：沿用原优先级链（骑兵受 DISABLE_CAVALRY_TRAIN 门禁）============
            // ★ 2026-09-24 用户需求：**删掉"未研究出复合弓时造普通弓兵"的兜底分支** ⇒ 现在**只产复合弓兵**；
            //   复合弓未就绪/黄金不足时靶场闲置，trained 仍 false → 下方转产其他兵种，不浪费产能（旧注释"普通弓兜底"已失实）。
            //   真实扣费 = 食物 + 黄金(20)，不扣石头。
            // ★ 15 分钟前完全停产（2026-09-06 用户要求）：见 COMPOSITE_BOW_MIN_FRAME
            if (lateGame && !trained && frame >= COMPOSITE_BOW_MIN_FRAME) {
                for (auto &b : info.buildings) {
                    if (b.Type != BUILDING_RANGE || b.Project != ACT_NULL) continue;
                    if (compositeBowResearched &&
                        info.Meat >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_FOOD &&
                        info.Gold >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_GOLD) {
                        BuildingAction(b.SN, BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN);
                        trained = true;
                    }
                }
            }

            // 优先级1：复合弓兵（远程DPS，PPT重点）——判据为 info.Gold（引擎真实扣费：食物+黄金）
            // ★ 15 分钟前完全停产（2026-09-06 用户要求）：见 COMPOSITE_BOW_MIN_FRAME
            if (!trained && compositeBowResearched && frame >= COMPOSITE_BOW_MIN_FRAME) {
                auto r = findBuilding(BUILDING_RANGE);
                if (r && r->Project == ACT_NULL &&
                    info.Meat >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_FOOD &&
                    info.Gold >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_GOLD) {
                    BuildingAction(r->SN, BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN);
                    trained = true;
                }
            }

            // 优先级2：阔剑兵（近战肉盾）   ★ 引擎已修正：训练阔剑兵(Development.cpp:607-608)现真扣 食物+黄金（need_Stone=0）。
            // 若解禁本块：判据应改 info.Gold。注：阔剑科技当前封禁，broadswordResearched 恒 false，本块不会触发。
            if (!trained && broadswordResearched) {
                auto ac = findBuilding(BUILDING_ARMYCAMP);
                if (ac && ac->Project == ACT_NULL &&
                    info.Meat >= BUILDING_ARMYCAMP_CREATE_BROADSWORD_FOOD &&
                    info.Stone >= BUILDING_ARMYCAMP_CREATE_BROADSWORD_GOLD) {
                    BuildingAction(ac->SN, BUILDING_ARMYCAMP_CREATE_BROADSWORD);
                    trained = true;
                }
            }

            // 优先级2.5：PREP/W1/W2/W3期间训练廉价填线兵（前期投石兵已全改为棍棒兵）   ★ 用户要求：前期不再造投石兵，改用棍棒兵填线（无石头依赖、更扛揍、便宜）。
            // ★ 本块不封顶：W1/W2 复合弓未解锁时仍需廉价近战填线，否则会断兵（反攻期由优先级3 爆近战接管）。
            // ★ 2026-09-03 用户改需求"不训棍棒兵、改箭塔防守"：DISABLE_CLUBMAN_TRAIN 关掉本块。
            bool canTrainCheap = (isWarTime || state == DEFENSE_PREP);
            if (!DISABLE_CLUBMAN_TRAIN && !trained && canTrainCheap &&
                info.Meat >= BUILDING_ARMYCAMP_CREATE_CLUBMAN_FOOD) {
                auto ac = findBuilding(BUILDING_ARMYCAMP);
                if (ac && ac->Project == ACT_NULL) {
                    BuildingAction(ac->SN, BUILDING_ARMYCAMP_CREATE_CLUBMAN);
                    trained = true;
                }
            }

            // 优先级2.8：★ 2026-09-13 新增「后期方阵兵产线」（用户要求"在后期建造方阵兵"） 与优先级3 分开的理由：优先级3 门槛是"食物溢出 MELEE_OVERFLOW_FOOD=150"，而方阵兵只需
            // 60 食 —— 没有理由等溢出才产。本块门槛降到 Meat >= HOPLITE_FOOD+60(=120)，14 分钟后即投产。 沿用反攻期同款双保险（黄金预留 + HOPLITE_RATIO_NUM/DEN 比例闸），与优先级1 并行各产各的。
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
                    DebugText(QString("[HOPLITE-LATE f=%1] 后期(lateGame)产方阵兵 现役hop=%2 comp=%3 limit=%4 meat=%5 gold=%6(kept%7)").arg(frame).arg(nHop2).arg(nComp2).arg(hopLimit2)
                              .arg((int)info.Meat).arg((int)info.Gold).arg(goldKeep2));
                }
            }

            // 优先级3：后期/反攻「爆近战」——食物溢出时主攻近战兵，与弓兵混编反攻。   不依赖全局 trained 闸门(否则单次只能产 1 弓、近战被饿死)：按"建筑空闲"逐栋下发，与弓兵并行。
            // 兵营→棍棒兵(50食物填线)；马厩→骑兵(受 DISABLE_CAVALRY_TRAIN 门禁)。   ★ 2026-09-13：学院→方阵兵 已上移为优先级2.8，此处不再重复下发。
            if (lateGame && info.Meat >= MELEE_OVERFLOW_FOOD) {
                // 兵营→棍棒兵：★ 2026-09-03 用户要求"不训棍棒兵"，DISABLE_CLUBMAN_TRAIN 关掉，   近战肉盾由优先级2.8 的学院方阵兵承担。
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

            // 侦察骑兵训练【已禁用 ENABLE_SCOUT_RECON=false】：2026-09-03 用户改需求， 不再造侦察骑兵，改派感化的战车弓兵/投石车探路（见 manageCounterAttack 先锋分支）。
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
}

// 军事管理（每帧调用）：A=训练（已抽到 trainMilitaryUnits）→ B=箭塔指挥 → C/D=军队搜敌与回基地待命。
void UsrAI::manageMilitary() {
    bool isWarTime = (state >= DEFENSE_WAVE1 && state <= DEFENSE_WAVE3);
    double BL = (double)BLOCKSIDELENGTH;

    trainMilitaryUnits(isWarTime);

    // ====== B. 箭塔防御：所有波次手动指挥箭塔攻击进入射程的敌人 ======
    // ★ 引擎箭塔攻击必须用 HumanAction(箭塔SN, 目标SN)，不能用 BuildingAction——后者第二参是 "动作编号"而非目标 SN。★ 箭塔的 tagBuilding.Project 被引擎改写为"当前攻击目标 SN"
    // (Core.cpp:603 getObjectSN)：空闲=-1、攻击中=目标SN，故"已在攻击"判据是 Project != -1。
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

    // ★ 2026-09-15 删死代码（铁律 27）：原 enemyNearTC lambda 只被紧随其后的 `(void)enemyNearTC;` 显式引用，无任何实际调用点（护驾早已取消"敌须在 TC 25 格内"门槛），保留只会误导后续维护。
    // ★ 2026-09-15 去重（铁律 21/26）：以下三组在 D-1 / D0 内原本各写一遍。 ①「有无敌人以祭司为目标」= 敌 WorkObjectSN == priestSN（D-1 扫一遍；D0 更每兵各扫一遍队列）
    int priestAttackerSN = -1;
    if (priestAlive)
        for (auto &e : info.enemy_armies)
            if (e.WorkObjectSN == priestSN) { priestAttackerSN = e.SN; break; }
    //   ② 护驾取敌 = "优先非投石车（留给祭司感化），没有再退化为任意敌(含投石车)"（紧急/预警两档各一遍）
    auto nearestGuardTarget = [&](double r) -> int {
        int t = findNearestEnemyNoStone(priestDR, priestUR, r);
        return (t >= 0) ? t : findNearestEnemySN(priestDR, priestUR, r);
    };
// ③ 回基地外围待命螺旋（W2/W3 前出拦截搜不到敌、W1/非战时就近搜敌搜不到敌，各一遍） 落点 = 半径 8/11/14 格 × 8 角 = 24 档，全在 TC 建筑之外 → 杜绝"走进 TC 导致不可达失败"；
// 8 帧内没挪窝(>1 格) 就换下一档，24 档全失败则放弃移动、就地待命（防无限刷屏）。   ★ 2026-09-17 两处修正（用户：「避免刷屏」+「停驻集结时不要站在同一点」）：
// ① 落点按 SN 散开（角度+半径双微扰）—— 原同档位多单位落点逐位相同 ⇒ 挤作一团卡位； ② 跨帧去重（同一落点 60 帧内不重发）—— 原无节流，行军途中每帧一条，单局 577~1349 条。
    auto holdNearBase = [&](tagArmy &a) {
        double distTC = calDistance(a.DR, a.UR, centerDR, centerUR);
        if (distTC <= 16 * BL) { armyReturnTry[a.SN] = 0; return; }   // 已在外围待命区，清卡死计数
        if (armyReturnTry[a.SN] >= 24) return;                        // 24 档全失败 → 就地待命
        int atry = armyReturnTry[a.SN];
        int aang = atry % 8;
        int arad = atry / 8; if (arad > 2) arad = 2;
        const int ARADII[3] = {8, 11, 14};
        // ★ 2026-09-17 SN 散开：原落点只由 armyReturnTry 决定 ⇒ 同档位的多个单位落点【逐位相同】 （实测多个复合弓兵挤在同一点互相卡位）。角度加 (SN%11)*0.055 rad、半径加 (SN%5)*0.4 格。
        double ara = (double)aang * 3.141592653589793 / 4.0 + (double)(a.SN % 11) * 0.055;
        double aR = (ARADII[arad] + (double)(a.SN % 5) * 0.4) * BL;
        double atx = centerDR + std::cos(ara) * aR;
        double aty = centerUR + std::sin(ara) * aR;
        atx = max(0.0, min((double)MAP_L * BL, atx));
        aty = max(0.0, min((double)MAP_U * BL, aty));
        // ★ 2026-09-17 跨帧去重（用户：「避免刷屏」）：原实现无任何节流 ⇒ 单位向落点行军期间 （WALKING，不满足下方 8 帧卡死检测的 IDLE 条件 ⇒ try 不增 ⇒ 落点不变）每帧重发同一条
        // HumanMove，实测单局 577~1349 条重复日志。同一落点 60 帧(≈2.4s)内不重发；   保留兜底重发是防"引擎丢弃一次性指令 ⇒ 单位永久静止"。换档致落点变化时立即发。
        const int HOLD_RESEND_FRAMES = 60;
        const bool holdSameGoal = armyHoldGoalDR.count(a.SN) &&
            calDistance(armyHoldGoalDR[a.SN], armyHoldGoalUR[a.SN], atx, aty) < 0.5 * BL;
        const bool holdResendOk = !armyHoldCmdFrame.count(a.SN) ||
            (frame - armyHoldCmdFrame[a.SN] >= HOLD_RESEND_FRAMES);
        if (!holdSameGoal || holdResendOk) {
            HumanMove(a.SN, atx, aty);
            armyHoldCmdFrame[a.SN] = frame;
            armyHoldGoalDR[a.SN] = atx; armyHoldGoalUR[a.SN] = aty;
        }
        // 卡死检测：不可达/被堵时快速换档（8帧，避免同一不可达点失败刷屏）   ⚠ 基准在【每次调用】刷新（含本帧未发令时）：否则停发期间基准陈旧，"8 帧内位移<1格"
        // 会拿旧坐标比对 ⇒ 误判/漏判卡死（去重只拦 HumanMove，不得改变本判据语义）。
        if (armyIssueFrame.count(a.SN) && a.NowState == HUMAN_STATE_IDLE &&
            frame - armyIssueFrame[a.SN] > 8 &&
            calDistance(a.DR, a.UR, armyIssueDR[a.SN], armyIssueUR[a.SN]) < 1.0 * BL) {
            armyReturnTry[a.SN]++;
        }
        armyIssueDR[a.SN] = a.DR; armyIssueUR[a.SN] = a.UR; armyIssueFrame[a.SN] = frame;
    };

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

    // --- D-1: 祭司护驾（★最高优先级，先于士兵自卫/守家/前出；祭司死=立刻失败） ---   三级：紧急(敌≤8格)→所有兵回防(可打断战斗)；预警(敌≤15格)→空闲/行军兵前往护驾。
    // 目标优先选非投石车(留给祭司感化)；若威胁祭司的只有投石车，保命优先照打。   只召回距祭司 PRIEST_GUARD_RECALL 内的兵，避免把反攻大军从全图拉回。
    std::map<int,int> guardIssued;   // 本帧已下达护驾令的兵：下方 D1/D2 不得抢占覆盖

    // ★ 2026-09-15 去重：D1/D2 共用的「可被就近攻击调度」过滤链 （排除祭司/投石车/已派护驾/正在猎狮/非空闲）。两处原先各抄一份，改一处漏一处就出事（铁律 26）。
    auto autoAttackEligible = [&](const tagArmy &a) -> bool {
        if (a.Sort == AT_PRIEST) return false;
        if (a.Sort == AT_STONE_THROWER) return false;   // ★ 投石车只在反攻期攻击（2026-09-06）
        if (guardIssued.count(a.SN)) return false;      // 本帧已去护驾→不得抢占覆盖
        if (lionHunterSN.count(a.SN)) return false;     // ★ 正在猎狮，别把指令覆盖掉
        if (a.NowState != HUMAN_STATE_IDLE) return false;
        return true;
    };

    // ★★★★★ 2026-09-18 M5：拉扯撤退锁（全局真源）★★★★★
    // 用户症状：「复合弓兵一旦与敌方军队交手后就完全不撤退了」。   铁证（kc 批 24 局 / 6758 个撤退窗口，口径：同一 SN 相邻 [KIT-R] 两窗口 25~45 帧内）：
    // • 区间内【无】攻击令 → 位移中位 1.50 格、89.3% 位移 >1 格、dK 变化 +0.60 格（真的拉开了） • 区间内【有】攻击令 → 位移中位 0.00 格、85.5% 位移 <0.2 格（原地钉死）；90.9% 的区间夹着攻击令。
    // 机制：manageMilitary 每帧先于 manageCounterAttack 运行，攻击令（本帧最后写入的指令）会把上一帧的 撤退 HumanMove 顶掉 ⇒ 单位永远走不出那一步（打-拉相位机被"焊死"）。
    // 锁覆盖两段：① RETREAT 相位（kitingPhase==1）② 撤退令后 KITING_HOLD_FRAMES 帧。   ⚠ 祭司保命路径不受锁约束（祭司死=立刻失败，保命优先于拉扯）。
    const int KITING_HOLD_FRAMES = 40;   // ≈1.6 秒@25fps，够走完一个撤步（落点 12.6 格）
    auto kiteRetreatLocked = [&](int sn) -> bool {
        if (kitingPhase.count(sn) && kitingPhase[sn] == 1) return true;
        return lastRetreatFrame.count(sn) && (frame - lastRetreatFrame[sn] < KITING_HOLD_FRAMES);
    };
    if (priestAlive) {
        // ★★ 最高优先级：有敌人正以祭司为目标(WorkObjectSN==priestSN) → 立刻全军扑上拉仇恨。 无视 8/15 距离门槛(远程敌可站 12 格外射祭司)、打断一切战斗、不计召回距离(生死攸关)。
        const int attackingPriestSN = priestAttackerSN;   // 已在上方统一扫描（D0 亦复用）
        int urgentSN = nearestGuardTarget(PRIEST_GUARD_URGENT * BL);
        int alertSN  = nearestGuardTarget(PRIEST_GUARD_ALERT * BL);

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
                // 已接令/正在攻击该目标(引擎 Core.cpp:459 会把 WorkObjectSN 设为目标SN)→不重发， 否则每帧重复 HumanAction 会不断打断攻击动作→兵原地横跳、输出为零。
                if (a.WorkObjectSN == guardSN) continue;
                // 预警级不打断正在战斗的兵；紧急级(敌已锁祭司/贴到8格内)一律召回
                if (a.NowState == HUMAN_STATE_ATTACKING && !urgent) continue;
                // ★ 2026-09-18 M5：拉扯撤退锁——预警级不得覆盖正在撤退的弓兵； 紧急级(敌已锁祭司/贴到祭司 8 格内)仍可覆盖（祭司保命优先于拉扯）。
                if (!urgent && kiteRetreatLocked(a.SN)) continue;
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
            // ★ 投石车非反攻期不参战（2026-09-06 用户要求"只在反攻阶段攻击敌人"）：反攻期由 manageCounterAttack 的 standoff 分支负责；非反攻期自卫/前出拦截/就近搜敌全跳过
            // （SPEED 1.63 极慢且脆弱，派出去等于送掉）。⚠ D-1 祭司护驾仍对它生效（保命高于一切）。
            if (a.Sort == AT_STONE_THROWER) continue;
            if (attackCmds >= maxAttackCmds) break;
            if (lionHunterSN.count(a.SN)) continue;   // ★ 正在猎狮，别把指令覆盖掉

            // ★ 状态闸：WORKING 跳过；ATTACKING(正在输出)不打断；IDLE/WALKING 正常接令。 (WALKING 允许接令：否则敌人在眼前砍祭司/队友，兵却要先把待命路走完→"站着看戏不挡刀")
            if (a.NowState == HUMAN_STATE_WORKING) continue;
            if (a.NowState == HUMAN_STATE_ATTACKING) continue;

            // ★ 优先级1（护驾）：正在攻击祭司的敌人 → 全军扑上去 （★取消原 enemyNearTC "敌须在TC 25格内"门槛：祭司在哪就保到哪，保命高于守家）
            const int attackingPriest = priestAttackerSN;   // 已在上方统一扫描
            if (attackingPriest >= 0) {
                if (a.WorkObjectSN != attackingPriest) {   // 已在打它→不重发，防打断输出
                    HumanAction(a.SN, attackingPriest);
                    attackCmds++;
                }
                continue;
            }

            // ★ 2026-09-18 M5：拉扯撤退锁（定义见上方 kiteRetreatLocked）。 本行刻意放在【优先级1 之后】：敌已锁祭司时不锁（保命优先），其余全部让位于撤退。
            if (kiteRetreatLocked(a.SN)) continue;

// ★ 优先级2（护驾）：祭司预警范围有敌（D-1 因限流/超距未召回到的兵）→ 也去护驾。
// ★ 2026-09-07 修（反攻期"复合弓兵在家里乱走"根因）：本分支【原本无任何距离闸】（为"祭司在哪就保到哪"刻意取消），
// 于是反攻期只要祭司 15 格内有任何一个敌人，【全图远征军】都会被 HumanAction 拉回来，清完再推进、又来敌再拉回。
// 修复：反攻期(COUNTERATTACK) 加 PRIEST_GUARD_RECALL(30格) 闸 —— 远征军交给 manageCounterAttack 的推进调度。 ⚠ 优先级1（敌已锁祭司）不受此限 —— 祭司死=立刻失败，铁律优先。
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

            // W2/W3：主动前出拦截远处敌人   ★ 反攻期(COUNTERATTACK)跳过：前出拦截的 HumanAction 会与 manageCounterAttack 的后撤 HumanMove 同帧打架，导致远程兵被反复拉去攻击、无法后撤(被贴脸输出)。
            if (state >= DEFENSE_WAVE2 && state <= DEFENSE_WAVE3) {
                int farEnemy = findNearestEnemyNoStone(centerDR, centerUR, 25 * BL);
                if (farEnemy >= 0) {
                    HumanAction(a.SN, farEnemy);
                    attackCmds++;
                    continue;
                }
                holdNearBase(a);
                attackCmds++;
                continue;
            }

// W1/非战时：就近搜敌攻击 + 回基地待命。   ★ 反攻期(COUNTERATTACK) 跳过：此分支在反攻期会掉进来（这里无 state 门禁），给"25 格内无敌人"的军队
// (含投石车) 下发"回基地螺旋待命"HumanMove，与 manageCounterAttack 的推进/standoff 同帧打架 → 来回抽搐。 反攻期单位调度完全交给 manageCounterAttack，此处不额外下发攻击/回撤令。
            if (state == COUNTERATTACK) {
                // 反攻期：不在此处发令（交给 manageCounterAttack 统一调度拉扯/推进）
            } else {
                int nearbyEnemy = findNearestEnemyNoStone(centerDR, centerUR, 25 * BL);
                if (nearbyEnemy >= 0) {
                    HumanAction(a.SN, nearbyEnemy);
                } else {
                    holdNearBase(a);
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
                if (!autoAttackEligible(a)) continue;
                if (kiteRetreatLocked(a.SN)) continue;   // ★ 2026-09-18 M5：不覆盖撤退中的弓兵
                if (attackCmds >= maxAttackCmds) break;
                HumanAction(a.SN, tcEnemy);
                attackCmds++;
            }
        }
    }

    // --- D2: 每个空闲士兵搜敌攻击 ---   ★ 反攻期(COUNTERATTACK)跳过：此块给 IDLE 兵就近下 HumanAction 攻击令， 会覆盖 manageCounterAttack 的后撤 HumanMove，导致远程兵站着打对面不逃跑。
    if (state == COUNTERATTACK) {
        // 反攻期单位调度完全交给 manageCounterAttack 的拉扯逻辑，此处不额外下发攻击令。
    } else
    for (auto &a : info.armies) {
        if (!autoAttackEligible(a)) continue;
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

// 反攻管理（PPT策略：侦察→集结→推进→祭司转化武器厂）
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

// ★ 就近交付（2026-09-03 修）：按资源类型就近选交付建筑，而非 TC 无条件优先。 原逻辑 TC 放最前 break ⇒ 瞪羚肉/浆果(均 HUMAN_STOCKFOOD)/木/金/石都优先交回 TC，瞪羚群中心的仓库形同虚设。
// 资源→建筑映射（引擎确认）：瞪羚/大象/浆果/树/石/金 → 仓库 STOCK；农场 → 谷仓 GRANARY；鱼 → 码头 DOCK。
// 故：STOCKFOOD/WOOD/STONE/GOLD → 就近仓库；GRANARYFOOD → 就近谷仓；DOCKFOOD → 就近码头；无匹配则退回最近 TC。
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

void UsrAI::counterFarmerAttack(double BL, double targetDR, double targetUR) {
    // ====== 反攻前置：★ 农民总攻（27 分钟后全部农民投入进攻，2026-09-19 用户需求）======
    // 调用位置：manageCounterAttack() 中排在 counterPriestGuard() 【之前】 —— 护驾紧急时后者会直接 return 停止推进，
    //   但"农民已出发"不该被撤回，故必须先发农民令。
    // ① 目标选取四级（逐条见下方注释）：敌方 TC > 最近软目标(非箭塔/非武器厂) > 最近箭塔 > 记忆方位行军。
    //   ⚠ 一律不含武器厂：拆了就没了 exam 胜因（与 ARMY_IGNORE_SIEGE_WORKSHOP 同源语义）。
    //   ⚠ 箭塔【必须】留在候选里：本图敌方没有 TC，其基地结构只有箭塔 + 武器厂；把箭塔也排除则目标恒为 -1、整段静默失效。
    //     （旧注释曾写"不含箭塔：农民撑不住塔火力"—— 该口径在 fa 批被实测推翻，代码从未按它实现，此处已更正。）
    if (COUNTER_FARMER_ATTACK && frame >= COUNTER_FARMER_ATTACK_FRAME) {
        static std::map<int, int> farmerAtkFrame;   // 农民 SN → 上次下发帧（节流）
// ★ 目标选取三级 + 兜底行军（2026-09-19 fa 批修正）：① 敌方 TC（"基地"本体）；② 最近的【软目标】敌建筑（非箭塔/非武器厂）；
// ③ 最近的【箭塔】—— 必须保留：本图敌方【没有 TC】，其基地结构只有箭塔 + 武器厂，若把箭塔也排除则目标恒为 -1、
// 整个功能静默失效（fa 批实证：14 局触发、0 条指令下发）。④ ①②③ 全空（敌建筑全部失去视野）→ 行军到
// enemyBaseScouted 的记忆方位，抵达后自然重新发现。⚠ ①②③ 一律不含武器厂（exam 胜条件唯一 = 祭司感化武器厂）。
        int farmerTgtSN = -1;
        int tgtKind = 0;                        // 0=无 1=TC 2=软目标 3=箭塔 4=行军
        double bestSoft = 1e18, bestTower = 1e18;
        int softSN = -1, towerSN = -1;
        tagBuilding* foeTC = findEnemyBuilding(BUILDING_CENTER);
        if (foeTC) { farmerTgtSN = foeTC->SN; tgtKind = 1; }
        for (auto &b : info.enemy_buildings) {
            if (b.Type == BUILDING_SIEGE) continue;              // 永不打武器厂
            double d = calDistance((b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL, targetDR, targetUR);
            if (b.Type == BUILDING_ARROWTOWER) {
                if (d < bestTower) { bestTower = d; towerSN = b.SN; }
            } else if (d < bestSoft) { bestSoft = d; softSN = b.SN; }
        }
        if (farmerTgtSN < 0) {
            if (softSN >= 0)      { farmerTgtSN = softSN;  tgtKind = 2; }
            else if (towerSN >= 0) { farmerTgtSN = towerSN; tgtKind = 3; }
        }
        int nFarmer = 0;
        for (auto &f : info.farmers) if (f.FarmerSort == FARMERTYPE_FARMER) nFarmer++;
        int nEngaged = 0, nSent = 0;
        if (farmerTgtSN >= 0) {
            for (auto &f : info.farmers) {
                if (f.FarmerSort != FARMERTYPE_FARMER) continue;
                if (f.WorkObjectSN == farmerTgtSN) { nEngaged++; continue; }
                if (farmerAtkFrame.count(f.SN) && frame - farmerAtkFrame[f.SN] < COUNTER_FARMER_ATTACK_GAP) continue;
                HumanAction(f.SN, farmerTgtSN);
                farmerAtkFrame[f.SN] = frame;
                nSent++;
            }
        } else if (enemyBaseScouted) {
            tgtKind = 4;
            for (auto &f : info.farmers) {
                if (f.FarmerSort != FARMERTYPE_FARMER) continue;
                if (farmerAtkFrame.count(f.SN) && frame - farmerAtkFrame[f.SN] < COUNTER_FARMER_ATTACK_GAP) continue;
                HumanMove(f.SN, enemyBaseDR, enemyBaseUR);
                farmerAtkFrame[f.SN] = frame;
                nSent++;
            }
        }
        if (frame % 300 == 0)
            DebugText(QString("[FARMER-ATK f=%1] 农民=%2 已投入=%3 本帧下发=%4 tgtSN=%5 kind=%6 敌建筑=%7").arg(frame).arg(nFarmer).arg(nEngaged).arg(nSent).arg(farmerTgtSN).arg(tgtKind)
                      .arg((int)info.enemy_buildings.size()));
    }
}

bool UsrAI::counterPriestGuard(double BL) {
    // ====== 反攻段：★ 祭司护驾（优先于一切推进 —— 祭司死=立刻失败）======
    // 为什么反攻期必须再判一次：processData 每帧【先】跑 manageMilitary()（UsrAI.cpp:633），反攻期【再】追加
    //   manageCounterAttack()（UsrAI.cpp:637）⇒ 本函数后跑，会覆盖 manageMilitary 刚下发的护驾令（跨帧"后跑者覆盖先跑者"）。
    // 触发条件：敌人已锁祭司(WorkObjectSN==priestSN) 或 敌 ≤ PRIEST_GUARD_URGENT 格。
    // 返回：true = 本帧已把全军转为回防祭司，调用方【必须立刻 return】，不再下发任何推进/感化令；false = 无事可做，继续推进。
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
                return true;
            }
        }
    }
    return false;
}

// ★ 2026-09-15 去重（铁律 21/26）：按 SN 在【敌军队 → 敌农民 → 敌建筑】中定位坐标。
//   原代码在 3 处（拉扯粘滞目标 / 投石车粘滞目标 / 投石车威胁点）各抄一份同样的三层循环，语义完全一致。
//   命中敌军队时顺带回填 pMelee（= sortIsMelee，供拉扯对近战敌更早撤）；三类都没有则返回 false。
//   ⚠ SN 全图唯一 ⇒ 多查一类（建筑）不会改变任何原有分支的结果。
// ★ 2026-09-21 追加回填 pSort（命中兵种；村民/建筑 = -1）——供"射程占优"判据与 [KIT-*] 日志用，不改任何原有分支。
//   pMelee / pSort 均为可选出参（默认 nullptr）⇒ 只想取坐标的调用点不必构造哑变量。
bool UsrAI::lookupEnemySN(int sn, double &x, double &y, bool *pMelee, int *pSort) const {
    double BL = (double)BLOCKSIDELENGTH;
    for (auto &e : info.enemy_armies)
        if (e.SN == sn) { x = e.DR; y = e.UR; if (pMelee) *pMelee = sortIsMelee(e.Sort); if (pSort) *pSort = e.Sort; return true; }
    for (auto &e : info.enemy_farmers)
        if (e.SN == sn) { x = e.DR; y = e.UR; if (pSort) *pSort = -1; return true; }
    for (auto &b : info.enemy_buildings)
        if (b.SN == sn) { x = (b.BlockDR + 1.0) * BL; y = (b.BlockUR + 1.0) * BL; if (pSort) *pSort = -1; return true; }
    return false;
}

// ★ 2026-09-21 拉扯专用选敌：只在"射程占优"（sortHasKiteRangeAdvantage）的敌人里取最近者。
//   与 findNearestEnemyNoStone 的差别【只有】这一条过滤 —— 两级兜底语义（军队优先、无军队才退村民）严格保持原样；
//   投石车本来就被该函数排除（留给祭司感化），此处不再单独兜底（原"投石车兜底"段已删，见相位机注释）。
// 出参：osort = 命中目标兵种（村民/未知 = -1）；skipSort = 被"射程不占优"跳过的最近敌方兵种（无 = -1，仅用于日志观测）。
// 返回：目标 SN；射程内既无"占优"敌、也无敌村民时返回 -1。
int UsrAI::findKiteTarget(int selfSort, double dr, double ur, double range, int &osort, int &skipSort) const {
    double BL = (double)BLOCKSIDELENGTH;
    int bestSN = -1; double bestD = range * range; osort = -1; skipSort = -1;
    double skipD = 1e12;
    for (const auto &e : info.enemy_armies) {
        double d = dist2(e.DR, e.UR, dr, ur);
        if (!sortHasKiteRangeAdvantage(selfSort, e.Sort, BL)) {
            if (d < range * range && d < skipD) { skipD = d; skipSort = e.Sort; }
            continue;
        }
        if (d < bestD) { bestD = d; bestSN = e.SN; osort = e.Sort; }
    }
    if (bestSN >= 0) return bestSN;
    bestD = range * range;
    for (const auto &e : info.enemy_farmers) {
        double d = dist2(e.DR, e.UR, dr, ur);
        if (d < bestD) { bestD = d; bestSN = e.SN; osort = -1; }
    }
    return bestSN;
}

// 可走判定 = 非海(OCEAN) 且在 forestGrid 之外。
//   forestGrid 由调用方预建（树±2格 / 石矿·金矿±1格），是 O(1) 查询的可走位图。
// ★ 2026-09-08（7e 第4条）：HumanMove 现可穿越未探索区 ⇒ UNKNOWN 不再拒；只有坐标本身不可达才卡住。
//   林/矿在引擎里是放在 GRASS 格上的资源对象 ⇒ "已探索"≠"可走"，故必须查 forestGrid，只看 theMap 不够。
// ⚠ 入参 (x,y) 为细节坐标（像素），非块坐标；越界返回 false。
bool UsrAI::isPassableAt(double x, double y, const std::vector<std::vector<char>>& forestGrid) const {
    double BL = (double)BLOCKSIDELENGTH;
    if (!info.theMap) return false;
    int bx = (int)(x / BL), by = (int)(y / BL);
    if (bx < 0 || by < 0 || bx >= MAP_L || by >= MAP_U) return false;
    int t = (*info.theMap)[bx][by].type;
    if (t == MAPPATTERN_OCEAN) return false;
    if (forestGrid[bx][by]) return false;
    return true;
}

void UsrAI::counterPriestConvert(double BL, double targetDR, double targetUR,
                                   double rallyCtrDR, double rallyCtrUR,
                                   const std::vector<std::vector<char>>& forestGrid) {
    tagArmy* priest = nullptr;
    for (auto &a : info.armies) if (a.Sort == AT_PRIEST) priest = &a;
    tagBuilding* siege = nullptr;
    if (enemySiegeSN != -1) siege = findEnemyBuilding(BUILDING_SIEGE);
    // ====== 祭司推进 / 转化武器厂（三处下发点：early / front / legacy）======
    // 【修 2026-09-08】原 `if (NowState != IDLE) return;` 太严——祭司跟军时 WALKING 每帧触发 return ⇒ 整段 100% 走不到 ⇒ 祭司长期滞留后方、感化武器厂永不触发。改为 WALKING 也允许进入。
    if (priest) {
        if (priestCounterCooldown > 0) priestCounterCooldown--;   // ★ 反攻推进专用节流（与 priestMoveCooldown 解耦）

        // ★★★ 2026-09-15 敌塔态势扫描（起手判据 + 诊断 + 前出日志共用同一份，避免同语义写三遍）★★★ ⚠ 只统计【已探明】的敌建筑（Core.cpp:622 受 explored||visible 约束）——未侦察到的塔对 AI "不存在"。
        auto scanTowerThreat = [&](double &nearD, int &cnt) {
            nearD = 1e9; cnt = 0;
            for (auto &b : info.enemy_buildings)
                if (b.Type == BUILDING_ARROWTOWER) {
                    cnt++;
                    double d = calDistance(priest->DR, priest->UR, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL);
                    if (d < nearD) nearD = d;
                }
        };

// ★★★ 2026-09-15 态势采样【提到早路径之前】★★★ 原位置在早路径 return 之后 ⇒ 祭司一进 12 格射程就被 return， 采样永远打不到（"起手过程不可观测"）。
// ★ 2026-09-16 修正：原先打印的 towers= 是 scanTowerThreat【祭司周边】塔数，与"塔全拆"这个【全局】判据不是同一个量
// ⇒ 极易误读（历史教训：`[LC-DBG] towers=0` @f=33300 被判成"塔已全拆"，实为未探明伪影，塔是 0→1→2 逐个探明的）。
// 现同时打印两个口径：gT=全局已探明敌箭塔数（判据真源）／seen=已探明敌建筑总数（保险项）／nearT+loc=祭司周边。
        if (frame % 300 == 0) {
            double nearTowerD = 1e9; int towerCnt = 0;
            scanTowerThreat(nearTowerD, towerCnt);   // 祭司周边的塔（态势用，非判据）
            int gT = 0, seen = 0;
            for (auto &b : info.enemy_buildings) {
                seen++;
                if (b.Type == BUILDING_ARROWTOWER) gT++;
            }
            DebugText(QString("[LC-DBG f=%1] siegeSN=%2 mem=(%3,%4) dS=%5 hp=%6 ccd=%7 st=%8 mvcd=%9 gT=%10 seen=%11 nearT=%12 loc=%13").arg(frame).arg(enemySiegeSN).arg(rallyDR).arg(rallyUR)
                      .arg(calDistance(priest->DR, priest->UR, (rallyDR + 1.0) * BL, (rallyUR + 1.0) * BL) / BL, 0, 'f', 1)
                      .arg((priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0, 0, 'f', 2).arg(priest->ConvertCooldown).arg(priest->NowState).arg(priestMoveCooldown)
                      .arg(gT).arg(seen).arg((nearTowerD > 1e8) ? -1.0 : nearTowerD / BL, 0, 'f', 1).arg(towerCnt));
        }

        // ★★★ 2026-09-16 用户需求：祭司感化武器厂的【唯一】限制 = 敌方全部箭塔拆完 ★★★
        // 判据块【必须在 early 路径之前】——early 是实际主力下发点（实测 6/6 起手走它）且原本无任何敌情判据；   闸放在它后面 = 形同虚设（铁律 11：闸的位置决定功能是否活着）。
        // early / front / legacy 三处下发点共用同一个 clearOk（铁律 21/26：同一语义只写一遍）。
        int enemyTowerN = 0;          // 已探明敌箭塔数（未探明不计入，见下方保险）
        int enemyBldSeenN = 0;        // 已探明敌建筑总数（保险用）
        for (auto &b : info.enemy_buildings) {
            enemyBldSeenN++;
            if (b.Type == BUILDING_ARROWTOWER) enemyTowerN++;
        }
        // 局部清场（旧判据，保留作回退与迟滞锁用）
        bool localClear = true;
        for (auto &e : info.enemy_armies)
            if (e.Blood > 0 && calDistance(priest->DR, priest->UR, e.DR, e.UR) < PRIEST_SIEGE_CLEAR_ARMY_R * BL) { localClear = false; break; }
        if (localClear)
            for (auto &b : info.enemy_buildings)
                if (b.Type == BUILDING_ARROWTOWER &&
                    calDistance(priest->DR, priest->UR, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL) < PRIEST_SIEGE_CLEAR_TOWER_R * BL) { localClear = false; break; }
        // 全局闸：敌箭塔数 <= PRIEST_TOWERS_CLEAR_MAX，且已探明保险通过（确实探过敌基地，而非"什么都没看见"）。   ⚠ 保险条件用 enemySiegeSN != -1（武器厂坐标已持久记忆）+ 已探明敌建筑数达标：
        // 否则视野丢失的瞬间 enemy_buildings 会变空 ⇒ enemyTowerN 假性归零 ⇒ 误判"塔已清够" ⇒ 祭司孤身送死。
        // ★ 2026-09-21：阈值由硬编码 ==0 放宽为 <= PRIEST_TOWERS_CLEAR_MAX(2)（用户需求，详见文件头同条注释）。
        // 变量名同步 towersAllDown → towersClearEnough：名字必须与语义一致，否则下一个人会按名字读代码。
        const bool towersClearEnough = (enemyTowerN <= PRIEST_TOWERS_CLEAR_MAX)
                                && (enemySiegeSN != -1)
                                && (enemyBldSeenN >= PRIEST_TOWERS_CLEAR_MIN_SEEN);
        const bool clearOk = PRIEST_SIEGE_REQUIRE_TOWERS_CLEAR ? towersClearEnough : localClear;

// ★★★ 2026-09-14 关键修复：武器厂感化【提前到状态/移动闸之前】★★★ 铁证：[LC-DBG] 8 局仅命中 1 次 ⇒ 下方整段执行率 <1%（被 NowState 闸 + priestMoveCooldown 闸挡住）。
// 而【感化是 HumanAction，与 priestMoveCooldown(移动节流) 无关】—— 引擎侧转换冷却由 ConvertCooldown 管。
// 旧结构把感化放在移动闸之后 ⇒ 祭司只要跟军(WALKING)+冷却中就永远错过感化窗口 ⇒ 这才是"发现了武器厂却感化不了"的最终根因。
        if (enemySiegeSN != -1 && priest->ConvertCooldown <= 0) {
            double sD0 = calDistance(priest->DR, priest->UR, (rallyDR + 1.0) * BL, (rallyUR + 1.0) * BL);
            if (sD0 <= PRIEST_CONVERT_SIEGE_RANGE * BL) {
                // ★★ 2026-09-16 唯一闸：敌塔尚未清够 ⇒ 本帧不起手（不发令 ⇒ 不进入施法 ⇒ 不会被打断重置）
                if (PRIEST_SIEGE_REQUIRE_TOWERS_CLEAR && !clearOk) {
                    if (frame % 100 == 0) {
                        // ★ 2026-09-17：补 alive=（敌活兵数）——用户的场景是"敌军全灭【且】箭塔已拆"， 两个条件必须能在日志里分别核对（原格式只有 towers/seen，无法验证"全灭"）。
                        // ★ 2026-09-21：补 lim=（当前放行阈值）——日志必须自描述，否则阈值改过之后旧探针会把 "上限"读成"上限为 0"（本文件已因注释/口径不自描述踩过多次，见 skill §2.18 ①）。
                        int aliveE0 = 0;
                        for (auto &e : info.enemy_armies) if (e.Blood > 0) aliveE0++;
                        DebugText(QString("[SIEGE-WAIT f=%1] hp=%2 towers=%3 seen=%4 alive=%5 dS=%6 lim=%7")
                                  .arg(frame).arg((priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0, 0, 'f', 2)
                                  .arg(enemyTowerN).arg(enemyBldSeenN).arg(aliveE0).arg(sD0 / BL, 0, 'f', 1).arg(PRIEST_TOWERS_CLEAR_MAX));
                    }
                    return;
                }
                // ★★ 2026-09-14 二次修（lk6 铁证）：感化令【绝不能每帧重发】★★ 引擎语义：HumanAction(祭司, 建筑) = 设置转换目标，重发会重置施法进度。对比：成功 lc3 只发
                // 1 次 → 340 帧后收编；失败 lk6 发 2155 次 → 2150 帧未收编。修：仅当 ①引擎当前目标非该武器厂 ②不在施法静默窗口 才发令；发令后进入 PRIEST_SIEGE_CONVERT_LOCKOUT(400 帧) 静默期。
                if (priest->WorkObjectSN != enemySiegeSN && priestCounterCooldown <= 0) {
                    // 现场量（起手判据与日志共用同一份，避免"同语义写两遍"）
                    double pHp0 = (priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0;
                    double nearT0 = 1e9; int towerN0 = 0;
                    scanTowerThreat(nearT0, towerN0);
                    // ★★★ 2026-09-15 起手保护：已残血 + 敌塔压近 ⇒ 本帧不起手 ★★★ 本分支仅在 WorkObjectSN != 武器厂 时进入 ⇒ 一定"尚未起手"，故不会打断已进行的施法。
                    // 刻意【不设 priestMoveCooldown】⇒ 交回 managePriest 后撤/治疗，撤出塔射程后再来。
                    if (pHp0 < PRIEST_SIEGE_GUARD_HP && nearT0 <= PRIEST_SIEGE_CLEAR_TOWER_R * BL) {
                        if (frame % 100 == 0)
                            DebugText(QString("[SIEGE-HOLD f=%1] hp=%2 nearT=%3 towers=%4 dS=%5").arg(frame).arg(pHp0, 0, 'f', 2).arg(nearT0 / BL, 0, 'f', 1).arg(towerN0).arg(sD0 / BL, 0, 'f', 1));
                        return;   // 本帧不接管祭司
                    }
                    HumanAction(priestSN, enemySiegeSN);
                    priestCounterCooldown = PRIEST_SIEGE_CONVERT_LOCKOUT;
                    // 每次发令必打（原为 frame%50 采样 ⇒ 起手过程不可观测）；发令本身已被 lockout 节流到 <=1/400 帧
                    DebugText(QString(">> Priest converting Siege Workshop! f=%1 d=%2 hp=%3 nearT=%4 towers=%5 path=early").arg(frame).arg(sD0 / BL, 0, 'f', 1).arg(pHp0, 0, 'f', 2)
                              .arg((nearT0 > 1e8) ? -1.0 : nearT0 / BL, 0, 'f', 1).arg(towerN0));
                }
                priestMoveCooldown = 60;   // 钉住：施法期禁止后撤/移动打断（移动会清空 WorkObjectSN）
                return;
            }
        }
        // 诊断（低频/ASCII）：★2026-09-15 已上移到本段最前（早路径之前）——原位置在早路径 return 之后， 导致"起手帧"永远看不到采样；且新增 towers/nearT 两列（敌塔态势）。

        if (priest->NowState != HUMAN_STATE_IDLE && priest->NowState != HUMAN_STATE_WALKING) {
            // 祭司在 ATTACKING（治愈）或 CONVERTING（感化）中,避免本段覆盖其引擎托管动作
            return;
        }

        // ★★ 2026-09-13 保祭司 · 跨块互斥闸 ★★ managePriest 与本函数同在主循环里先后调用，旧代码用【两套独立冷却】⇒ 同一帧可给祭司下发两个
        // 相反的移动令（前出武器厂 vs 后撤）⇒ 原地抖动、净位移 0（实测 sg2 f=42668~42868 每 10 帧翻转）。 修：统一到同一闸 —— managePriest 本帧已发过令，本段整体跳过。
        if (priestMoveCooldown > 0) return;

        // 有伤兵时把祭司留给 managePriest 治疗，推进下帧再继续
        bool anyInjuredAlly = false;
        for (auto &a : info.armies) {
            if (a.MaxBlood <= 0) continue;
            if (a.Blood > 0 && a.Blood < a.MaxBlood) { anyInjuredAlly = true; break; }
        }
        // ★ 2026-09-07 修（反攻期"复合弓兵在家里乱走"根因链起点）： 原逻辑【只要有一个兵掉血就 return】——反攻期掉血是常态 ⇒ 祭司几乎每帧都停、永远跟不上大部队
        // ⇒ 敌人摸到祭司 15 格 → priestThreatened 恒真 → 护驾令把全军拉回（死锁）。 改为：反攻期不再因伤兵 return（原"只有重伤才停"的判据已在 2026-09-08 撤销）；
        // 非反攻期行为不变。治疗本身仍由 managePriest 负责。
        // ★ 2026-09-20 精简：删除已死的 criticalInjured 及其扫描循环 —— 2026-09-08 改判据后 该变量只剩写入、无任何读取，编译器 -Wunused-but-set-variable 直接点名。
        if (anyInjuredAlly && state != COUNTERATTACK) return;

        double pDist = calDistance(priest->DR, priest->UR, targetDR, targetUR);
        // ★★★ 2026-09-13 用户需求：「敌方军队全灭且箭塔全拆后，祭司应去感化敌方武器厂」★★★ 根因：`siege && pDist < 12*BL`(感化条件) 与下方 else 的 `距目标 ≥ PRIEST_MIN_DIST_TARGET(18)`
        // 互斥 —— 12 < 18 ⇒ 二者**永远不可能同时成立**！实测 k8/cb8 的 [PRST-REAR] dTgt 恒在 22.6~36.4 格， 祭司被安全距离钉死在后方 ⇒ 感化武器厂 0 次（9 局 352 条转换令无一条是建筑）。
        // 修：祭司周边无军事威胁时解除 18 格约束。★ 2026-09-14 半径 20→8/14（旧 20 > 感化射程 12 ⇒ 结构死锁）。
        // ★★ 2026-09-16：localClear / clearOk 已在【上方 early 路径之前】统一算好（三处下发点共用一份，铁律 21/26）。
        // ★★ 前出感化【迟滞锁】：防 localClear 在半径边界处逐帧翻转 —— 进入=清场成立+武器厂已发现； 退出=敌人真贴身(<=ABORT_R) 或 血量过低(<ABORT_HP)。
        if (PRIEST_CONVERT_SIEGE_WHEN_CLEAR && clearOk && enemySiegeSN != -1) {
            priestSiegeApproach = 1;
        } else if (priestSiegeApproach == 1) {
            bool hardAbort = false;
            for (auto &e : info.enemy_armies)
                if (e.Blood > 0 && calDistance(priest->DR, priest->UR, e.DR, e.UR) < PRIEST_SIEGE_ABORT_R * BL) { hardAbort = true; break; }
            double pBRap = (priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0;
            // ★ 2026-09-16：全局塔闸模式下，迟滞锁退出必须叠加 !clearOk——否则首次满足后永久放行，闸失效。
            if (hardAbort || pBRap < PRIEST_SIEGE_ABORT_HP || enemySiegeSN == -1
                || (PRIEST_SIEGE_REQUIRE_TOWERS_CLEAR && !clearOk)) priestSiegeApproach = 0;
        }
        bool allowConvertSiege = PRIEST_CONVERT_SIEGE_WHEN_CLEAR && (clearOk || priestSiegeApproach == 1);
        // ★ 2026-09-15 清理：原"扩到 28 格后 priestEnemy>=0 return"是 WRONG-LAYER return——反攻期祭司前出后 28 格内**恒有敌** ⇒ 几乎每帧触发 ⇒ 祭司段永远跑不到 ⇒ 停在 TC 不动。该查询已彻底删除。
        // managePriest 仍独立按"投石车→近战→远程→村民"感化；本段只负责感化武器厂 + HumanMove 推进。

        // ★ 2026-09-12（用户需求"祭司反攻不要太靠前，尽量在安全距离"）：旧版把祭司推到 target-5格，且感化 武器厂(pDist<12)会把它长期钉在武器厂旁 = 太靠前。新：冲进 PRIEST_MIN_DIST_TARGET 格内即本帧
        // 强制后撤到大队后方安全距离；只有已在安全范围才允许【被动】感化（不主动前出）。
        bool priestTooClose = (pDist < PRIEST_MIN_DIST_TARGET * BL);
        // ★ 2026-09-13：局部清场成立时安全距离约束失效（否则 18 格安全 > 12 格感化射程 ⇒ 永远够不到）。
        // ★ 2026-09-14 副作用修复：只有【确实存在武器厂目标】才解除。旧写法 `if (allowConvertSiege)` 在未发现 武器厂时也会解除 ⇒ 祭司不进后撤分支、停在原地挨打（lc8 f=36980 死 / lc4 f=36100 死）。
        if (allowConvertSiege && enemySiegeSN != -1) priestTooClose = false;

        // ★★★ 2026-09-13 用户需求：敌方军队全灭 + 箭塔全拆 → 祭司主动前出感化武器厂 ★★★ 优先级高于"后撤保命"（清场后无威胁，前出不会送命）。
        if (allowConvertSiege && enemySiegeSN != -1 && priest->ConvertCooldown <= 0) {
            // ★ 2026-09-14：目标用【持久记忆】的武器厂 SN + 坐标(rallyDR/rallyUR)， 不再依赖 siege 指针（受实时可见性约束，失去视野即失效；且解引用会空指针崩溃）。
            const double sMemDR = (rallyDR + 1.0) * BL;
            const double sMemUR = (rallyUR + 1.0) * BL;
            double dSiege = calDistance(priest->DR, priest->UR, sMemDR, sMemUR);
            if (dSiege <= PRIEST_CONVERT_SIEGE_RANGE * BL) {
                // 已在感化射程内 → 直接感化武器厂
                HumanAction(priestSN, enemySiegeSN);
                priestCounterCooldown = 60; priestMoveCooldown = 60;
                // ★ 2026-09-15：去掉 frame%50 采样（每次发令必打），附敌塔态势
                double nearT1 = 1e9; int towerN1 = 0;
                scanTowerThreat(nearT1, towerN1);
                DebugText(QString(">> Priest converting Siege Workshop! f=%1 d=%2 hp=%3 nearT=%4 towers=%5 path=front").arg(frame).arg(dSiege / BL, 0, 'f', 1)
                          .arg((priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0, 0, 'f', 2).arg((nearT1 > 1e8) ? -1.0 : nearT1 / BL, 0, 'f', 1).arg(towerN1));
            } else if (priestCounterCooldown <= 0) {
                // 在射程外 → 主动朝武器厂【记忆坐标】推进
                double ux2 = (sMemDR - priest->DR), uy2 = (sMemUR - priest->UR);
                double ul2 = std::sqrt(ux2 * ux2 + uy2 * uy2) + 1e-6;
                ux2 /= ul2; uy2 /= ul2;
                double stopD = (PRIEST_CONVERT_SIEGE_RANGE - 1.0) * BL;   // 停在感化射程内 1 格处
                double tx = sMemDR - ux2 * stopD;
                double ty = sMemUR - uy2 * stopD;
                tx = max(0.0, min((double)MAP_L * BL, tx));
                ty = max(0.0, min((double)MAP_U * BL, ty));
                if (isPassableAt(tx, ty, forestGrid)) {
                    HumanMove(priestSN, tx, ty);
                    priestCounterCooldown = 30; priestMoveCooldown = 30;
                    double nearT2 = 1e9; int towerN2 = 0;
                    scanTowerThreat(nearT2, towerN2);
                    DebugText(QString(">> Priest ADVANCE to Siege f=%1 d=%2 nearT=%3 towers=%4 enemy_cleared").arg(frame).arg(dSiege / BL, 0, 'f', 1)
                              .arg((nearT2 > 1e8) ? -1.0 : nearT2 / BL, 0, 'f', 1).arg(towerN2));
                }
            }
            return;   // 清场期：本帧祭司任务就是感化武器厂，不走下方后撤逻辑
        }

        // ★ 2026-09-16：legacy 路径同样受唯一闸约束（三处下发点共用 clearOk，铁律 21/26）。
        if (siege && pDist < 12 * BL && priest->ConvertCooldown <= 0 && clearOk) {
            // 在感化范围内→感化武器厂！
            HumanAction(priestSN, siege->SN);
            priestCounterCooldown = 60; priestMoveCooldown = 60;
            DebugText(">> Priest converting Siege Workshop! path=legacy");
        } else if (priestCounterCooldown <= 0 || priestTooClose) {
            // ★ 2026-09-12（用户需求"祭司反攻不要太靠前"）：旧版把祭司推到 target(敌基地)-5格(仅沿 DR 轴)， 几乎与大军一起冲到敌方基地外 5 格，前线一崩就暴露在敌塔/敌兵火力下 = 立即失败。
            // 新：祭司跟随【己方大部队重心】(排除自身)，始终位于大队【后方】(朝 TC 方向) PRIEST_SAFE_BEHIND 格， 且与反攻目标保持 ≥ PRIEST_MIN_DIST_TARGET 格。上方感化段保留但改为【被动】。
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
            if (isPassableAt(px, py, forestGrid))
                HumanMove(priestSN, px, py);
            if (frame % 100 == 0)
                DebugText(QString("[PRST-REAR f=%1] army=(%2,%3) tgt=(%4,%5) dTgt=%6 tooClose=%7").arg(frame).arg(armyDR / BL, 0, 'f', 0).arg(armyUR / BL, 0, 'f', 0)
                          .arg(targetDR / BL, 0, 'f', 0).arg(targetUR / BL, 0, 'f', 0).arg(dTgt / BL, 0, 'f', 1).arg(priestTooClose ? 1 : 0));
            priestCounterCooldown = 30; priestMoveCooldown = 30;
        }
    }
}

// 把落点吸附到最近可走格：以 1~4 格半径由内向外逐环扫描，命中即改写 (x,y) 并返回；扫完仍不可走则原样保留。
// 用途：敌建筑的块坐标可能压在资源堆或海格上，HumanMove 直达会被引擎静默拒绝（全军原地不动）。
// 一次性静态修正，不引入步进/绕路（用户 2026-09-15 要求）。
void UsrAI::snapWalkable(double &x, double &y, const std::vector<std::vector<char>>& forestGrid) const {
    if (isPassableAt(x, y, forestGrid)) return;
    double BL = (double)BLOCKSIDELENGTH;
    for (int r = 1; r <= 4; ++r)
        for (int dx = -r; dx <= r; ++dx)
            for (int dy = -r; dy <= r; ++dy) {
                if (dx > -r && dx < r && dy > -r && dy < r) continue;   // 只扫该半径的外环
                double cx = x + dx * BL, cy = y + dy * BL;
                if (isPassableAt(cx, cy, forestGrid)) { x = cx; y = cy; return; }
            }
}

bool UsrAI::counterScoutAndPlan(double BL, double &targetDR, double &targetUR,
                                      const std::vector<std::vector<char>>& forestGrid) {
    // ====== 侦察 / 选址：寻找敌方武器厂 + 定出本轮反攻目标点 ======
    if (enemySiegeSN == -1) {
        auto siege = findEnemyBuilding(BUILDING_SIEGE);
        if (siege) {
            enemySiegeSN = siege->SN;
            rallyDR = siege->BlockDR;
            rallyUR = siege->BlockUR;
            DebugText(QString(">> Enemy Siege Workshop found at (%1,%2)!").arg(rallyDR).arg(rallyUR));
        }
    }

    // 侦察骑兵补造【已禁用 ENABLE_SCOUT_RECON=false】：探路改由感化的战车弓兵/投石车承担 （见下方主循环先锋分支），不再单独造侦察骑兵。
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
            return true;
        }
        // ★★★ 2026-09-14 不再因"失去视野"重置 enemySiegeSN ★★★ 旧代码此处 `enemySiegeSN = -1;` —— findEnemyBuilding 只遍历 info.enemy_buildings，受
        // Core.cpp:622【explored||visible】约束 ⇒ "发现→丢失视野→重置→需再次可见"循环 ⇒ 祭司目标不稳定。 修：失去视野 ≠ 武器厂不存在。方位由 rallyDR/rallyUR 持久记忆，保持 SN 供下游用记忆坐标推进。
    }
    // ★ 探到过敌方基地：一旦 info.enemy_buildings 出现过敌方建筑，记录其方位并【持久化】——
    // 即便之后暂时失去视野/该建筑消失，也记得大致方位，反攻时直接奔袭基地而非盲走对角角落。   定位优先级：武器厂 > 敌方TC > 列表首个敌建筑(任一敌建筑出现即视为探到基地)。
    if (!enemyBaseScouted && info.enemy_buildings.size() > 0) {
        tagBuilding* eb = findEnemyBuilding(BUILDING_SIEGE);
        if (!eb) eb = findEnemyBuilding(BUILDING_CENTER);
        if (!eb) eb = &info.enemy_buildings[0];
        enemyBaseScouted = true;
        enemyBaseDR = (eb->BlockDR + 1) * BL;
        enemyBaseUR = (eb->BlockUR + 1) * BL;
        DebugText(QString(">> Enemy base scouted at (%1,%2)!").arg(enemyBaseDR).arg(enemyBaseUR));
    }

    if (siege) {
        targetDR = (siege->BlockDR + 1) * BL;
        targetUR = (siege->BlockUR + 1) * BL;
    } else if (enemyBaseScouted) {
        targetDR = enemyBaseDR; targetUR = enemyBaseUR;   // ★ 探到过基地→直奔已知方位
    } else {
        auto center = findBuilding(BUILDING_CENTER);
        double tcDR = center ? (center->BlockDR + 1) * BL : MAP_L * BL * 0.5;
        double tcUR = center ? (center->BlockUR + 1) * BL : MAP_U * BL * 0.5;
        // ★ 取 TC 的【真正对角角落】：必须【逐轴独立取反】，不能用一个"坐标和"去二选一 ——
        // 旧逻辑只在主对角线两端 (0,0)↔(L,U) 之间二选一，TC 在反对角线上时目标会落成【相邻角】   （"不会走到对角线、而是走到相邻角落"的根因）；逐轴取反后四种情况全对。
        // CORNER_INSET=3：精确角落 (MAP_L*BL, MAP_U*BL) 的 bx=MAP_L → 越界 → isPassableAt 恒 false。
        const int CORNER_INSET = 3;
        targetDR = (tcDR < MAP_L * BL * 0.5) ? (MAP_L - CORNER_INSET) * BL : CORNER_INSET * BL;
        targetUR = (tcUR < MAP_U * BL * 0.5) ? (MAP_U - CORNER_INSET) * BL : CORNER_INSET * BL;
    }

    // ★ 2026-09-15 直达推进的前提：目标点必须落在可走格上（非海/非林/非矿）。
    // 敌建筑的块坐标可能压在资源堆或海格上，HumanMove 直达会被引擎拒 ⇒ 全军原地不动。   故就近（半径 ≤4 格，由内向外）吸附到最近可走格——一次性静态修正，不引入步进/绕路。
    snapWalkable(targetDR, targetUR, forestGrid);
    return false;
}

// 反攻段总调度（state == COUNTERATTACK 时由 processData 调用）。
// 本函数是【编排器】：真正的逻辑分布在下面几个函数里，调用顺序即语义优先级，勿随意调换 ——
//   ① counterScoutAndPlan()  —— 侦察/选址：定出 targetDR/UR（武器厂 > 记忆基地 > TC 对角角落）并吸附到可走格。
//                              返回 true = 武器厂已被我方转化（本局胜利），调用方须立刻 return。
//   ② counterFarmerAttack()  —— 农民总攻（27 分钟后）。刻意排在护驾之前（见该函数头部）。
//   ③ counterPriestGuard()   —— 祭司护驾。返回 true = 本帧已转为回防，调用方须立刻 return。
//   ④ 【本函数内联】         —— 集结与推进：投石车/远程优先，含拉扯相位机、攻塔、卡死重试。
//   ⑤ counterPriestConvert() —— 祭司推进 / 转化武器厂。
// forestGrid：开头预建的"树±2格 / 矿±1格"可走位图，只建一次，按 const 引用传给上述各段（O(1) 查）。
void UsrAI::manageCounterAttack() {
    double BL = (double)BLOCKSIDELENGTH;

    // 可走判定 = 非海(OCEAN) 且不在树林/石矿/金矿内。
    // ★ 2026-09-08（7e 第4条）：HumanMove 现可穿越未探索区 ⇒ UNKNOWN 不再拒；只有坐标本身不可达才卡住。
    // 林/矿在引擎里是放在 GRASS 格上的资源对象 ⇒ "已探索"≠"可走"。预建 forestGrid(树±2格/矿±1格) O(1) 查。
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

    // ⚠ 下列说明已随定义归位（2026-09-23 重构：λ 提升为文件级/成员函数时注释未同步搬走）：
    //   兵种分类 / 射程 / "射程占优" → 文件头 static sortIsRanged() / sortIsMelee() /
    //   sortMaxRangedRange() / sortHasKiteRangeAdvantage()；"按 SN 三层查找" → lookupEnemySN()；
    //   "拉扯专用选敌" → findKiteTarget()。

    double targetDR, targetUR;
    if (counterScoutAndPlan(BL, targetDR, targetUR, forestGrid)) return;

    // 后续第 2/3 段仍需要 siege 指针与 directMarch 判据，按原语义重新定位一次
    tagBuilding* siege = nullptr;
    if (enemySiegeSN != -1) siege = findEnemyBuilding(BUILDING_SIEGE);
    bool directMarch = (siege != nullptr) || enemyBaseScouted;

    counterFarmerAttack(BL, targetDR, targetUR);
    if (counterPriestGuard(BL)) return;

    // ====== 本函数内联：集结与推进（投石车/远程优先，逐步走已探索区域）======
    int marchCmds = 0;
    int armyCount = 0;
    for (auto &a : info.armies) if (a.Sort != AT_PRIEST) armyCount++;  // 非祭司军队总数(近战集结门槛用)
    // ★ 全体反攻门槛：所有军事单位(非祭司，含远程/近战/投石车)≥COUNTER_ATTACK_MIN_ARMY 才一起反攻； 或到 COUNTER_ATTACK_FORCE_TIME(24分钟) 强制一起进攻——避免人数不足时零散冲出被敌方集火。
    bool readyToAttack = (armyCount >= COUNTER_ATTACK_MIN_ARMY) || (frame >= COUNTER_ATTACK_FORCE_TIME);
    // 集结中心：未达门槛时全军回己方 TC 附近集结待命(形成密集兵力，来敌也能抱团防守)
    tagBuilding* rallyTC = findBuilding(BUILDING_CENTER);
    double rallyCtrDR = rallyTC ? (rallyTC->BlockDR + 1) * BL : MAP_L * BL * 0.5;
    double rallyCtrUR = rallyTC ? (rallyTC->BlockUR + 1) * BL : MAP_U * BL * 0.5;
    tagArmy* priest = nullptr;

// 统一推进出口：直达敌方基地附近目标点，交给引擎全图寻路（可穿越未探索区）。
// ★ 2026-09-15 用户要求「不用步进或绕路」：已删 marchWaypoint/nextVisibleStep/axisAlignedTry/findDetourWaypoint。
// 唯一退路 = 卡死时朝集结 TC 内缩 stuckTry 格重发。canReissue(30帧节流) 必须保留：每帧重发会刷新 marchCmdFrame
// ⇒ stuckTry 永不涨 ⇒ 卡死打转。   ⚠ marchGoal* = 本轮【实际下发点】：卡死判据必须以它为参照，否则退让会被误判为"更卡死"一路退回 TC。
    static std::map<int, double> marchGoalDR, marchGoalUR;
    // ★★★ 2026-09-20 方案 B【Tier-2 优化点】：新增尾参 biasTowerSN（默认 -1 ⇒ 既有全部调用点行为逐字不变）。
    // -1 = 落点 = 敌方基地附近 targetDR/UR（原语义）；   ≥0 = 落点改贴到该敌塔【靠我方一侧】的 standoff 环上（TOWER_APPROACH_STANDOFF 格）。
    // ⚠ 只改【落点】，绝不发攻击令 ⇒ 不碰 kiting 双状态机/接敌带/攻击令节流的任何状态。   落点方向取自【我方集结 TC → 塔】而非"单位当前位置 → 塔"：前者跨帧稳定，后者会随单位移动
    // 每帧微调落点 ⇒ 30 帧节流窗口内反复重锚 marchGoal*，把卡死判据搅乱（铁律 9：同源量同源取）。
    auto issueMarch = [&](double fx, double fy, int sn, int sort, int stuckTry, bool canReissue,
                          int biasTowerSN = -1) {
        (void)sort;
        if (!canReissue) return;                 // 未到节流窗口：本帧静默，不重复下发
        double mx = targetDR, my = targetUR;
        // —— Tier-2 落点偏置：塔外侧 standoff 环（塔在 12 格内时不会走到这里，Tier-1 已 return）——
        if (biasTowerSN >= 0) {
            for (auto &b : info.enemy_buildings) {
                if (b.SN != biasTowerSN || b.Type != BUILDING_ARROWTOWER) continue;   // 塔已消失/已拆→退回原落点
                const double tDR = (b.BlockDR + 1.0) * BL, tUR = (b.BlockUR + 1.0) * BL;  // 与 findNearestEnemyTower 同口径
                double dx = rallyCtrDR - tDR, dy = rallyCtrUR - tUR, d = std::sqrt(dx * dx + dy * dy);
                const double so = TOWER_APPROACH_STANDOFF * BL;
                if (d > 1e-6) { mx = tDR + dx / d * so; my = tUR + dy / d * so; }
                else          { mx = tDR; my = tUR; }        // 塔与集结中心重合(极端)：直取塔心
                mx = max(0.0, min((double)MAP_L * BL, mx));  // 靠地图边缘的塔，外侧落点可能出界 → 夹回
                my = max(0.0, min((double)MAP_U * BL, my));
                snapWalkable(mx, my, forestGrid);                        // 落点可能压海/林/矿 → 吸附到最近可走格
                break;
            }
        }
        // ★ 卡死最小脱困（不引入步进/绕路）：朝我方集结 TC 方向内缩 stuckTry 格后重发同一目标。 语义仍是"直奔敌方基地附近"，只是退一步让引擎重新算一条路；最多退到 TC 前 1 格(不越过集结中心)。
        if (stuckTry > 0) {
            double dx = mx - rallyCtrDR, dy = my - rallyCtrUR, d = std::sqrt(dx * dx + dy * dy);
            double back = (d > BL) ? ((stuckTry * BL < d - BL) ? stuckTry * BL : d - BL) : 0.0;
            if (d > 1e-6) { mx -= dx / d * back; my -= dy / d * back; }
            snapWalkable(mx, my, forestGrid);                // 内缩后可能落进海/林/矿 → 再吸附一次
            // 退让点算一个【新目标】：基准与计时一起重锚，"能否走到退让点"成为新一轮判据；走到即复位，不累积。
            marchIssueDist[sn] = calDistance(fx, fy, mx, my);
            marchMoveFrame[sn] = frame;
        }
        marchGoalDR[sn] = mx; marchGoalUR[sn] = my;   // 判据参照 = 本轮实际下发点
        HumanMove(sn, mx, my);                   // 引擎完整寻路：直奔敌方基地附近目标点
        marchCmdFrame[sn] = frame;
    };

    // ★★★ 2026-09-20 只读诊断：量化"反攻期敌塔可选、却没下发攻塔令"的规模 ★★★ 口径 = 兵×帧（frame-army pairs），采样点放在循环最前（所有 continue 之前）⇒ 统计的是"总机会"。
    // 判读：chance12 占比【高】且 TOWER-TGT 少 ⇒ 上游分支抢走（优先级问题）； chance12 占比【低】、chance30 高 ⇒ 半径太小（已由 [TOWER-APPROACH] 实测验证为真，见 Tier-2 注释）。
    // ⚠ 必须 static：本函数每帧被调用一次，非 static 的局部变量每帧归零 ⇒ 日志退化成"单帧快照"（首版即踩此坑）。
    // ⚠ 声明位置必须在 attackBuildingOrMarch **之前**：Tier-2 分支要 `++twBias`，同函数内"后声明"的变量
    // 在 lambda 体内查不到名字（编译期错误，不是运行期）。   twBias = Tier-2【去重后】的偏置次数；验收判据 = 跑局后 twBias 必须 ≠ 0（否则方案 B 没生效）。
    static long long twArmyFrames = 0, twChance12 = 0, twChance30 = 0, twBias = 0;

    // ★ 2026-09-15 去重（铁律 21/26）：单位无「敌方兵」可打时的统一出口 = 最近敌塔 → 最近敌建筑 → 推进。 原远程分支与近战分支各自抄了一份完全相同的 25 行（连 ARMY_IGNORE_SIEGE_WORKSHOP 分支都一样）。
    // who 仅用于 [TOWER-TGT] 日志标签（"复合弓兵/远程" / "近战"），不改任何决策。   ★ 语义保持原样：打塔后不再推进；打建筑时若"已在打它"则退回推进；否则推进兜底。
    auto attackBuildingOrMarch = [&](tagArmy &a, const char *who, int stuckTry, bool canReissue) {
        // ★ 2026-09-16 用户纠正「复合弓兵要攻击箭塔、直接打不拉扯」： 仅放行 AT_COMPOSITE_BOWMAN(射程7<塔8)直接选塔站桩打（见 canHitTower 判定）；其余射程<塔的远程兵
        // (战车弓7/弓兵5/投石兵slinger4) 仍 canHitTower=false，保持不打塔（避免冲进塔射程白挨打）。 选塔即 return 站桩、不进下方推进段 ⇒ 不拉扯。近战不做此判据，投石车射程 10 > 8 照旧压制箭塔。
        const double selfR = sortMaxRangedRange(a.Sort, BL);
        // ★ 2026-09-16 用户纠正「复合弓兵要攻击箭塔、直接打不拉扯」： 仅放行 AT_COMPOSITE_BOWMAN(射程7<塔8)直接选塔站桩打；其余射程<塔的远程兵(战车弓7/弓兵5/投石兵slinger4)
        // 仍 canHitTower=false（保持不打塔，避免冲进塔射程白挨打）。选塔即 return 站桩、不进推进段 ⇒ 不拉扯。
        const bool canHitTower = !sortIsRanged(a.Sort) || a.Sort == AT_COMPOSITE_BOWMAN || selfR >= ARROWTOWER_RANGE * BL;
        // 第二档"打最近任意建筑"里也要把箭塔摘掉，否则绕一圈又落回同一座塔（SN 全图唯一）。
        auto isTowerSN = [&](int sn) -> bool {
            for (auto &b : info.enemy_buildings)
                if (b.SN == sn) return b.Type == BUILDING_ARROWTOWER;
            return false;
        };
        int towerSN = findNearestEnemyTower(a.DR, a.UR, TOWER_TARGET_RANGE * BL);
        if (towerSN >= 0 && canHitTower) {
            if (a.WorkObjectSN != towerSN) {
                HumanAction(a.SN, towerSN);
                DebugText(QString("[TOWER-TGT f=%1] %2 SN=%3 攻击最近敌塔 %4 (R<=%5格)").arg(frame).arg(who).arg(a.SN).arg(towerSN).arg(TOWER_TARGET_RANGE));
            }
            return;
        }
        // 够不着塔 ⇒ 本帧放弃打塔（不 return，落下方的"非塔建筑 / 推进"）。   日志按【塔 SN 变化】去重：同一兵对同一座塔只记一条，不会刷屏（铁律 34：关键决策点必须可观测）。
        if (towerSN >= 0) {
            if (!towerSkipSN.count(a.SN) || towerSkipSN[a.SN] != towerSN) {
                towerSkipSN[a.SN] = towerSN;
                DebugText(QString("[TOWER-SKIP f=%1] %2 SN=%3 射程%4<塔%5 → 不打塔 SN=%6 (改打非塔建筑/推进)").arg(frame).arg(who).arg(a.SN).arg(selfR / BL, 0, 'f', 1)
                          .arg(ARROWTOWER_RANGE, 0, 'f', 1).arg(towerSN));
            }
        }
// ★★★ 2026-09-20 方案 B【Tier-2】：Tier-1 只看 12 格，实测 85~90% 的机会落在 12~30 格之间被白扔。
// 此处往前再看一档 TOWER_APPROACH_RANGE(30) 格，命中则【不发攻击令】，只把推进落点贴到塔外 standoff 环。
// ⚠ 走到这里且 canHitTower ⇒ 上方 Tier-1 必未命中 ⇒ tier2SN 命中的塔一定落在 (12, 30] 格，与 Tier-1 零重叠。
// ⚠ 仅 canHitTower 的兵种参与：射程<塔且未放行的(战车弓7/弓兵5/投石兵4)不偏置 —— 它们进 12 格也不会打塔。
        int tier2SN = -1;
        if (canHitTower) {
            int t2 = findNearestEnemyTower(a.DR, a.UR, TOWER_APPROACH_RANGE * BL);
            if (t2 >= 0 && t2 != towerSN) tier2SN = t2;   // t2==towerSN 属防御分支（理论上不可达）
        }
        if (directMarch && calDistance(a.DR, a.UR, targetDR, targetUR) <= 12 * BL) {
            // 军队不打武器厂（留给祭司感化）：ARMY_IGNORE_SIEGE_WORKSHOP 时跳过最近的武器厂。
            int ebSN;
            if (ARMY_IGNORE_SIEGE_WORKSHOP) {
                int nb = findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
                ebSN = (nb >= 0 && siege != nullptr && nb == siege->SN) ? -1 : nb;
            } else {
                ebSN = siege ? siege->SN : findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
            }
            // ★ 够不着塔的兵种：最近建筑若是箭塔则同样跳过（否则又是一次白挨打）→ 落到推进。
            if (ebSN >= 0 && a.WorkObjectSN != ebSN && (canHitTower || !isTowerSN(ebSN))) {
                HumanAction(a.SN, ebSN); return;   // 有(非塔)建筑可打→拆
            }
        }
        // —— 推进：Tier-2 命中 ⇒ 落点贴塔；否则原样直奔敌方基地附近 ——   日志按【兵 SN + 塔 SN】去重（同 towerSkipSN 口径），只在"换了偏置目标"时记一条，不刷屏。
        if (tier2SN >= 0 && (!towerBiasSN.count(a.SN) || towerBiasSN[a.SN] != tier2SN)) {
            towerBiasSN[a.SN] = tier2SN;
            DebugText(QString("[TOWER-APPROACH f=%1] %2 SN=%3 塔%4 在%5格内(>%6) → 不发攻击令，落点贴塔外%7格").arg(frame).arg(who).arg(a.SN).arg(tier2SN)
                      .arg(TOWER_APPROACH_RANGE, 0, 'f', 0).arg(TOWER_TARGET_RANGE).arg(TOWER_APPROACH_STANDOFF, 0, 'f', 0));
            ++twBias;
        }
        issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue, tier2SN);   // 无建筑/已在打→继续推进
    };

    for (int pass = 0; pass < 2 && marchCmds < 8; ++pass) {
        for (auto &a : info.armies) {
            if (a.Sort == AT_PRIEST) { priest = &a; continue; }
            if (lionHunterSN.count(a.SN)) continue;   // ★ 正在猎狮，别把推进指令盖掉

            // ★ 2026-09-20 机会采样（只读）：必须在【所有 continue 闸之前】，否则统计到的是"幸存者"而非"机会"。
            if (readyToAttack) {
                ++twArmyFrames;
                if (findNearestEnemyTower(a.DR, a.UR, TOWER_TARGET_RANGE * BL) >= 0) ++twChance12;
                if (findNearestEnemyTower(a.DR, a.UR, 30.0 * BL) >= 0) ++twChance30;
            }

            // ★ 卡死检测（独立表 marchIssue*/marchMoveFrame，绝不复用 armyIssue*）。 判据 = "有没有朝推进目标靠近"(marchIssueDist)，【不是】绝对位移——原地抖动 A→B→A 每步都 >0.5BL。
            // ⚠ 旧 `NowState != IDLE → continue` 有致命漏洞：领到走不到的航点会永久停在 WALKING → 卡死。
            const double gDR = marchGoalDR.count(a.SN) ? marchGoalDR[a.SN] : targetDR;
            const double gUR = marchGoalUR.count(a.SN) ? marchGoalUR[a.SN] : targetUR;
            const double curDistToTgt = calDistance(a.DR, a.UR, gDR, gUR);   // ★ 参照 = 本轮实际下发点
            if (!marchIssueDist.count(a.SN)) {          // 首次见到→建立基准
                marchIssueDist[a.SN] = curDistToTgt;
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
            } else if (marchIssueDist[a.SN] - curDistToTgt > 0.5 * BL) {
                marchIssueDist[a.SN] = curDistToTgt;    // 朝目标靠近了→刷新基准
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0; // 并清卡死档，回正常寻路
            }
            // ⚠ ATTACKING(正在开火)绝不算卡死：投石车/弓兵按最大射程站桩输出时本就不位移，   若计入卡死，90帧后会被拽走去移动，直接破坏投石车的 standoff 输出。
            // 这里同时刷新基准，使其停火后重新计时而非立刻被判卡死。
            if (a.NowState == HUMAN_STATE_ATTACKING) {
                marchIssueDist[a.SN] = curDistToTgt;
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
            }
            bool stuckNow = (frame - marchMoveFrame[a.SN] > 90);        // 90帧无位移→判定卡死
            bool canReissue = !marchCmdFrame.count(a.SN) ||
                              (frame - marchCmdFrame[a.SN] >= 30);      // 30帧节流，防每帧换方向抖动
            if (stuckNow && canReissue) marchStuckTry[a.SN]++;          // 升档：换个方向试
            int stuckTry = marchStuckTry[a.SN];

            // ===== ★ 高机动单位"先锋探路"（独立于集结/接战，最优先调度） =====   不造侦察骑兵，改派感化的战车弓兵/骑兵；投石车 SPEED 极慢不参与（会把攻城火力锁死在 TC）。
            // ★ 7e 起 HumanMove 可全图寻路，旧"4格小步贴已探索边界"已删：stuckTry==0 → 直奔目标， 探到 enemy_buildings 即点亮 enemyBaseScouted → directMarch；stuckTry>0 → 朝集结 TC 内缩重发。
            if ((a.Sort == AT_CHARIOT_ARCHER || a.Sort == AT_CAVALRY) &&
                !enemyBaseScouted && enemySiegeSN == -1) {
                issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);   // 先锋直插敌方基地方位
                marchCmds++;
                continue;
            }

// ===== ★ 远程兵"打-拉"双状态机相位优先段 ===== 必须在 continue 闸(NowState != IDLE → continue)【之前】，
// 否则弓兵开火后变 ATTACKING → 被跳过。• SHOOT(=0) 射程内攻击，持续 30 帧(≈1.2 秒) 后【主动】切 RETREAT；
// • RETREAT(=1) 沿"远离敌"方向撤到敌距 ≥ R+1.5 切回 SHOOT；• 任意相位 dK ≤ 0.5R(贴脸) → 无条件切 RETREAT。
            if (sortIsRanged(a.Sort) && a.Sort != AT_STONE_THROWER) {
                const double R = sortMaxRangedRange(a.Sort, BL);
// ★ 2026-09-18 迟滞带修正（用户：「与敌方军队交手后就完全不撤退了」）。铁证：旧值 1.5 ⇒ 退出阈值 = R+1.5 = 8.5 格，
// 而下方【接敌带】给付线上限是 R+2.0 = 9 格 ⇒ 8.5 < 9 ⇒ 一撤到 8.5 就立刻被判"仍在接敌带" ⇒ 发攻击令、引擎自行逼近 ⇒ 撤退净效果≈0（实测 gi 批 24 局：96.7% 的撤退窗口在 60 帧内出现攻击令）。
// 改为 4.0 ⇒ 退出阈值 11 格 > 接敌带 9 格，形成 +2 格迟滞带（撤到 11 格才允许重新接战）。
                // ★ 2026-09-22 原 `BREATH = 4.0 格`（退出阈值 R+4 = 11 格）已由下方距离模型取代：
                //   退出阈值改由【威胁半径】推导且以自身射程 R 为上限 ⇒ 迟滞带宽度由 KITING_HYST 显式给定，
                //   不再依赖"退出阈值 > 接敌带 2.0 格"这种间接约束（那种写法一旦 R 变化就会再次变成负迟滞带）。
                // ★ AoE3 7e = 25 fps(1500 帧/分钟)：60 帧 = 2.4 秒、30 帧 = 1.2 秒。工程铁律：frame→秒 一律 ÷25。
                const int SHOOT_FRAMES = 30;               // SHOOT 相位持续 ≈1.2 秒@25fps（用户需求"打一下就走"——打一发就走，不多停留）
                const int PHASE_COOLDOWN = 20;             // 相位内不重发指令 ≈0.8 秒（让一撤走完）
                // ★ 用户需求"回撤时间调长/攻击间隔扩大"：RETREAT 兜底 60 帧(2.4 秒) > SHOOT 的 1.2 秒。
                const int RETREAT_FRAMES = 60;             // RETREAT 相位兜底切回 SHOOT 时长 ≈2.4 秒@25fps（撤得更远更久）
                int phase = kitingPhase.count(a.SN) ? kitingPhase[a.SN] : 0;
                // ★★★【2026-09-13 · 拉扯从未生效的第一性根因】★★★ 2026-09-08 那次"修复"是错的：`phaseFrame 默认即 frame` 只保证本帧不取到 -999999，
                // 但【从未把进入帧写回 map】⇒ 下一帧 count 仍为 0 ⇒ 又取 frame ⇒ **phaseAged 恒为 0**。 后果：三个依赖 phaseAged 的相位转移全部恒不成立（敌近提前撤 / SHOOT 满 30 帧切 RETREAT
                // ← 主症状 / RETREAT 兜底 60 帧）⇒ 弓兵进射程后永远站桩输出、一次 HumanMove 都不发。 ✅ 正解：首次进入即把进入帧写回 map（见 `if (!kitingPhaseFrame.count(a.SN)) ...`），
                // 此后 phaseAged 正常累加，"射 30 帧 → 撤 60 帧 → 再射"的 kiting 循环才真正启动。
                if (!kitingPhase.count(a.SN)) kitingPhase[a.SN] = 0;
                if (!kitingPhaseFrame.count(a.SN)) kitingPhaseFrame[a.SN] = frame;
                phase = kitingPhase[a.SN];
                int phaseFrame = kitingPhaseFrame[a.SN];
                int phaseAged = frame - phaseFrame;
                // ★★★★★ 2026-09-14「反攻时拉扯必须成功」第 1 步：目标粘滞 ★★★★★ 旧实现每帧重选"最近敌"⇒ 目标 SN 每帧跳变（实测 ln1：6827 条攻击令落在 22 个目标上）
                // ⇒ HumanAction 每帧重设 ⇒ 引擎瞄准进度永远归零 ⇒ 只走不打。   新实现：先沿用粘滞目标（仍存活且距 ≤20 格），只有它消失/跑远才重选。
                int kEnemy = -1;
                double kEX = 0, kEY = 0; bool kGot = false;
                bool kMelee = false;
                int  kSort = -1;         // ★ 2026-09-21：拉扯目标兵种（判"射程是否占优"+日志用）
                int  kSkipSort = -1;     // ★ 2026-09-21：被"射程不占优"跳过的最近敌方兵种（仅日志）
                if (kitingTargetSN.count(a.SN)) {
                    int cur = kitingTargetSN[a.SN];
                    kGot = lookupEnemySN(cur, kEX, kEY, &kMelee, &kSort);   // 粘滞目标仍存活?
                    // ★ 2026-09-21：跑远→放手；【射程不占优→放手】—— 不变量是"粘滞目标一定是可拉扯目标"
                    // （只有 findKiteTarget 会写这张表，它已按同一判据过滤）；此守卫是防御性断言，防未来改动绕过过滤。
                    if (kGot && (calDistance(a.DR, a.UR, kEX, kEY) > 20 * BL ||
                                 !sortHasKiteRangeAdvantage(a.Sort, kSort, BL))) kGot = false;
                    if (kGot) kEnemy = cur;
                }
                if (!kGot) {
                    // ★ 2026-09-21：改为"射程占优"专用选敌（原 findNearestEnemyNoStone 会把射程 7 的战车弓 选为复合弓(7)的拉扯目标 —— 射程不占优，拉扯纯亏，用户明确要求不拉扯）。
                    kEnemy = findKiteTarget(a.Sort, a.DR, a.UR, 20 * BL, kSort, kSkipSort);
                    if (kEnemy >= 0) kGot = lookupEnemySN(kEnemy, kEX, kEY, &kMelee, &kSort);
                }
                // ★ 2026-09-21 已删「投石车兜底」段：原逻辑在 noStone 找不到目标时，把 R+1.5 格内的投石车 拉进复合弓的打-拉循环（注释原文："射程内只有投石车时 kGot=false → 走推进而非攻击"）。
                // 但投石车射程 10 > 复合弓 7 ⇒ 正属用户本次要求取消的"拉扯射程不占优的敌人"； 投石车按既有设计留给【祭司感化】与【我方投石车压制】(findCatapultTarget)，弓兵不参与。
                // 语义回到：附近只有投石车时不选它 → 落下方推进/打建筑分支（与 findNearestEnemyNoStone 的原有语义一致）。
                if (kEnemy >= 0 && kGot) kitingTargetSN[a.SN] = kEnemy;   // ★ 记录/刷新粘滞目标
                // ★ 观测（铁律 34：关键决策点必须可观测）：附近有敌、却因"射程不占优"一个可拉扯目标都没有 ⇒ 打一条。
                // 按 (SN, 兵种) 去重 ⇒ 每兵每种最多 1 条，不刷屏。   验收判据 = 该行出现的 Sort 恒 ∈ {8 投石车, 12 战车弓}。
                if (kEnemy < 0 && kSkipSort >= 0 &&
                    (!kiteSkipSort.count(a.SN) || kiteSkipSort[a.SN] != kSkipSort)) {
                    kiteSkipSort[a.SN] = kSkipSort;
                    DebugText(QString("[KIT-NO f=%1] SN=%2 无可拉扯目标：附近敌 Sort=%3 射程>我%4格 ⇒ 不拉扯(落推进/打建筑)").arg(frame).arg(a.SN).arg(kSkipSort).arg(R / BL, 0, 'f', 1));
                }
                // ★★★ 2026-09-22 拉扯距离模型（「撤得开」×「打得到」的平衡）★★★
                // 威胁半径：远程敌 = 其最大射程（撤到它射程外即可）；近战/村民 = 0（贴身威胁由下方 0.5R 无条件撤退兜底）。
                // RET_D（=退出阈值=撤退后保持的距离）恒 ≤ R ⇒ 撤完仍在自身射程内 ⇒ 切回 SHOOT 立刻能打，不再空走 4~6.3 格。
                // T_IN / T_OUT 构成 KITING_HYST 格正迟滞带；T_IN 不低于 0.5R（贴脸线），避免两条触发互相打架。
                const double THREAT_R = (kSort >= 0 && sortIsRanged(kSort)) ? sortMaxRangedRange(kSort, BL) : 0.0;
                const double RET_D = min(max(THREAT_R + KITING_SAFE_MARGIN * BL, KITING_MIN_KEEP * BL), R);
                const double T_OUT = RET_D;
                const double T_IN  = max(0.5 * R, RET_D - KITING_HYST * BL);
                double dK = kGot ? calDistance(a.DR, a.UR, kEX, kEY) : 1e12;

                // —— 终止触发（无条件、无节流）：从 SHOOT 贴身 <0.5R 立即切 RETREAT ——
                // ★ 加 `phase != 1` 守卫：原实现每帧都重置 kitingPhaseFrame ⇒ phaseAged 恒 0 ⇒ RETREAT 60 帧兜底永不触发 ⇒ 相位被永久钉死在 1（弓兵一直撤、不再输出）。只在"从 0 切 1"时重置。
                if (kGot && dK <= 0.5 * R && phase != 1) {
                    phase = 1; kitingPhase[a.SN] = 1; kitingPhaseFrame[a.SN] = frame;
                    phaseFrame = frame; phaseAged = 0;
                    kitingRetStuck[a.SN] = 0;   // ★ 2026-09-14：每开一个新撤退窗口都重试"远离目标"档
                    // ★ 2026-09-18 M4（结构修正）：窗口开始必须同时清除 kitingRetPrevDK，否则「撒不动」判定恒为真。
                    // 铁证（gi/kb 各 24 局）：新一轮 RETREAT 由「敌贴身 dK<=0.5R/0.9R」触发，而 prevDK 是上一轮窗口末（撒得最远）的 dK
                    // ⇒ 本轮首帧 dK 必定 < prevDK+0.3 ⇒ stuck 必堆到 1 ⇒ 第 1 档「远离敌」永远被跳过，只能走第 2 档「朝 TC」（方向盲）。
                    // 实测对应：stuck=0 的 1739 次 ≈ stage=1 的 1737 次；stage=2 占 76.3%、其 dK 拉开比仅 15%，而 stage=1 为 90%。
                    kitingRetPrevDK.erase(a.SN);
                                                //   （旧实现 stuck>0 就永久跳过第 1 档 ⇒ 只能朝 TC 撤 ⇒ 越撤越贴敌）
                }
                // ★ 敌近提前撤：SHOOT 内敌逼近到 0.9R(复合弓 6.3 格)就不必等满 30 帧（远程敌 0.5 秒可贴到 5 格）。 与"打满 30 帧"构成双触发。⚠ 只在 phase=0(SHOOT)内触发。
                if (phase == 0 && kGot && dK > 0.5 * R && dK <= T_IN && phaseAged >= 6) {
                    // phaseAged>=6 帧≈0.24 秒最小驻留,避免刚切进 SHOOT 立刻因敌近距离又撤回去, 造成"反复横跳"震荡(每帧切相位,实际伤害 0)。
                    phase = 1; kitingPhase[a.SN] = 1; kitingPhaseFrame[a.SN] = frame;
                    phaseFrame = frame; phaseAged = 0;
                    kitingRetStuck[a.SN] = 0;   // ★ 2026-09-14：每开一个新撤退窗口都重试"远离目标"档
                    // ★ 2026-09-18 M4（结构修正）：窗口开始必须同时清除 kitingRetPrevDK，否则「撒不动」判定恒为真。
                    // 铁证（gi/kb 各 24 局）：新一轮 RETREAT 由「敌贴身 dK<=0.5R/0.9R」触发，而 prevDK 是上一轮窗口末（撒得最远）的 dK
                    // ⇒ 本轮首帧 dK 必定 < prevDK+0.3 ⇒ stuck 必堆到 1 ⇒ 第 1 档「远离敌」永远被跳过，只能走第 2 档「朝 TC」（方向盲）。
                    // 实测对应：stuck=0 的 1739 次 ≈ stage=1 的 1737 次；stage=2 占 76.3%、其 dK 拉开比仅 15%，而 stage=1 为 90%。
                    kitingRetPrevDK.erase(a.SN);
                                                //   （旧实现 stuck>0 就永久跳过第 1 档 ⇒ 只能朝 TC 撤 ⇒ 越撤越贴敌）
                }
                bool coolPhase = (frame - phaseFrame >= PHASE_COOLDOWN);
                // —— 状态转移 ——   SHOOT 持续 ≥ 30 帧(≈1.2 秒@25fps)主动切 RETREAT("打一下→往回走"触发):命中用户原话"打一下就走"
                if (phase == 0 && kGot && phaseAged >= SHOOT_FRAMES) {
                    phase = 1; kitingPhase[a.SN] = 1; kitingPhaseFrame[a.SN] = frame;
                    phaseFrame = frame; phaseAged = 0;
                    kitingRetStuck[a.SN] = 0;   // ★ 2026-09-14：每开一个新撤退窗口都重试"远离目标"档
                    // ★ 2026-09-18 M4（结构修正）：窗口开始必须同时清除 kitingRetPrevDK，否则「撒不动」判定恒为真。
                    // 铁证（gi/kb 各 24 局）：新一轮 RETREAT 由「敌贴身 dK<=0.5R/0.9R」触发，而 prevDK 是上一轮窗口末（撒得最远）的 dK
                    // ⇒ 本轮首帧 dK 必定 < prevDK+0.3 ⇒ stuck 必堆到 1 ⇒ 第 1 档「远离敌」永远被跳过，只能走第 2 档「朝 TC」（方向盲）。
                    // 实测对应：stuck=0 的 1739 次 ≈ stage=1 的 1737 次；stage=2 占 76.3%、其 dK 拉开比仅 15%，而 stage=1 为 90%。
                    kitingRetPrevDK.erase(a.SN);
                                                //   （旧实现 stuck>0 就永久跳过第 1 档 ⇒ 只能朝 TC 撤 ⇒ 越撤越贴敌）
                }
                // RETREAT 退出条件【双路径】（用户原话"直到敌出射程外再攻击"）： ① 优选：dK ≥ T_OUT(=RET_D，威胁半径推导，且恒 ≤ 自身射程 R)
                // ② 兜底：RETREAT 持续 ≥ 60 帧(2.4 秒)强制切回。★ 2026-09-22 旧①为 `R+BREATH`=11 格（> 射程 R=7）⇒ 撤到达标即丢输出，已改为 T_OUT。
                // 没敌/在 RETREAT 阶段：走下方推进 (issueMarch)
                if (phase == 1 && kGot && dK >= T_OUT) {
                    phase = 0; kitingPhase[a.SN] = 0; kitingPhaseFrame[a.SN] = frame;
                    phaseFrame = frame; phaseAged = 0;
                } else if (phase == 1 && phaseAged >= RETREAT_FRAMES) {
                    // ⚠ 用"相位节流"上限做兜底：敌追着我时撤不到 dK≥T_OUT，2.4 秒后再给"再射"机会。   本帧只切相位，真正撤/射在下一相位段（节流让一射走完）。
                    if (coolPhase) {
                        phase = 0; kitingPhase[a.SN] = 0; kitingPhaseFrame[a.SN] = frame;
                        phaseFrame = frame; phaseAged = 0;
                    }
                }

                if (phase == 1 && kGot && canReissue) {
                    // —— RETREAT 阶段：沿"远离敌"方向撤，落点 = 敌 + KIT_LAND × unitVector ——
                    // ★ 2026-09-12 fallback 链：第1档"远离敌"可能撞海/林 ⇒ 二级朝己方 TC 撤、三级朝祭司撤；全失败则本帧不下令（下一帧再试），绝不让单位往海里走。
                    // ★ 落点系数演化史（09-22 定案，保留以便读懂为什么是这个数）：0.85/1.1R(09-11) ⇒ 落点比原地更近敌，退出条件永不满足；
                    //   → 1.4/1.5R(09-18) 9.8/10.5 格 < 旧退出阈值 11 ⇒ 仍撤不到；→ 1.8/1.9R(09-18) 12.6/13.3 格 > 自身射程 7 ⇒ 「撤得开」但「打不到」
                    //   （撤完要走 4~6.3 格才有输出，且撤退窗口 30 帧比攻击保护期 60 帧更密 ⇒ SHOOT 段被结构性封死）；
                    //   → 现版：落点 = RET_D + SLACK，由【威胁半径】推导并以【自身射程】为上限 ⇒ 撤完即在射程内。
                    // ★ 上限钳到 R：RET_D 被钳到 R 时 RET_D+SLACK 可能 > R（如 R=5 弓箭手 ⇒ 落点 5.5 > 5）⇒ 不钳则"撤完即在射程内"不严格成立；
                    //   钳后落点 = min(RET_D+0.5, R) ≥ RET_D = T_OUT ⇒ 退出条件照样满足（相等时也满足）。
                    const double KIT_LAND = min(RET_D + KITING_LANDING_SLACK * BL, R);   // 略越过 T_OUT，且恒 ≤ 自身射程
                    double ux = (a.DR - kEX) / (dK + 1e-6), uy = (a.UR - kEY) / (dK + 1e-6);
                    const double angs[5] = {0.0, 0.6, -0.6, 1.2, -1.2};
                    const double angsT[5] = {0.0, 0.5, -0.5, 1.0, -1.0};  // TC fallback 用更窄角度(TC 必存在,角度越准越好)
                    bool kitMoved = false;
                    double kitX = 0, kitY = 0;
                    int kitStage = 0;  // 1=远离敌 2=朝TC 3=朝祭司 0=失败
// ★ 2026-09-13 撤退有效性校验（"点可走 ≠ 路径可达"）：isPassableAt 只判落点所在格、不判路径；
// 反攻期弓兵常在敌基地附近，落点可走却被海/林/建筑隔断 ⇒ 引擎静默丢弃。度量用 dK（与最近敌距离）：   本窗口未比上窗口拉开 ≥0.3 格即判该方向撤不动 ⇒ stuck++。
// ⚠ 不用"单位是否有位移"：攻击令同样驱动位移，会把"撤不动"误判成"在撤"。
                    if (kitingRetPrevDK.count(a.SN)) {
                        if (dK < kitingRetPrevDK[a.SN] + 0.3 * BL)
                            kitingRetStuck[a.SN] = (kitingRetStuck.count(a.SN) ? kitingRetStuck[a.SN] : 0) + 1;
                        else
                            kitingRetStuck[a.SN] = 0;                 // 确实拉开了 → 复位
                    }
                    kitingRetPrevDK[a.SN] = dK;
                    bool skipAwayStage = (kitingRetStuck.count(a.SN) && kitingRetStuck[a.SN] > 0);
                    // ★ 2026-09-15 去重：三档撤退共用的「落点下发」——夹取到地图内 → 可通行则下令并记账。 落点越界会被引擎丢弃；记账 5 件套（cmdFrame/retreatFrame/issueDist/moveFrame/stuckTry）
                    // 任缺一项都会让卡死检测或节流失效 ⇒ 三处原先各抄一份（铁律 26）。
                    auto tryRetreatLanding = [&](double rx, double ry, int stage) -> bool {
                        rx = max(0.0, min((double)MAP_L * BL, rx));
                        ry = max(0.0, min((double)MAP_U * BL, ry));
                        if (!isPassableAt(rx, ry, forestGrid)) return false;
                        HumanMove(a.SN, rx, ry);
                        marchCmdFrame[a.SN] = frame;
                        lastRetreatFrame[a.SN] = frame;
                        // ★ 判据参照必须同步到"本轮落点"：撤退/退让落点都远离原目标，若仍按原目标算距离， 撤退到位反而被判成"更卡死" ⇒ 90 帧后触发退让，与打-拉相位机互相拉扯。
                        marchIssueDist[a.SN] = calDistance(a.DR, a.UR, rx, ry);
                        marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
                        marchGoalDR[a.SN] = rx; marchGoalUR[a.SN] = ry;
                        kitMoved = true; kitStage = stage; kitX = rx; kitY = ry;
                        return true;
                    };
                    // —— 第 1 档:沿"远离敌"方向撤（上一轮撤不动则跳过，改走第 2 档） ——
                    for (int ai = 0; ai < 5 && !kitMoved && !skipAwayStage; ++ai) {
                        double ca = std::cos(angs[ai]), sa = std::sin(angs[ai]);
                        tryRetreatLanding(kEX + (ux*ca - uy*sa) * KIT_LAND,
                                          kEY + (uy*ca + ux*sa) * KIT_LAND, 1);
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
                                tryRetreatLanding(a.DR + (tcUX*ca - tcUY*sa) * TC_STEP,
                                                  a.UR + (tcUY*ca + tcUX*sa) * TC_STEP, 2);
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
                                tryRetreatLanding(a.DR + (prUX*ca - prUY*sa) * PR_STEP,
                                                  a.UR + (prUY*ca + prUX*sa) * PR_STEP, 3);
                            }
                        }
                    }
                    // —— 终极兜底：三档全失败 → 本帧不下令，相位机下一帧再试 ——
                    // ★ 观测增强：原 `frame % 50` 采样率仅 1/50，反攻期常整段漏掉 RETREAT 窗口。改为每次进入 撤退窗口必打；本块已被 canReissue(30 帧) 限制，每弓兵每 30 帧最多一条，不会刷屏。
                    // ★ 2026-09-21 追加 `tSort=`（目标兵种）：验收"不拉扯射程不占优的敌人"的直接证据 —— 改后 tSort 恒不应出现 8(投石车)/12(战车弓)；12/8 出现在这里 = 判据漏改。
                    // ★ 2026-09-22 追加 retD/tin/thr（距离模型的输出）——验收"撤完是否仍在自身射程内"的直接依据：
                    //   landD = 落点距目标 = KIT_LAND（应与 retD 同量级且 ≤ R）；thr = 目标威胁半径（远程敌=其射程）。
                    DebugText(QString("[KIT-R f=%1] SN=%2 dK=%3 R=%4 stage=%5 stuck=%6 aged=%7 self=(%8,%9) tgt=(%10,%11) tSort=%12 retD=%13 tin=%14 thr=%15 melee=%16")
                              .arg(frame).arg(a.SN).arg(dK / BL, 0, 'f', 1).arg(R / BL, 0, 'f', 1).arg(kitStage).arg(kitingRetStuck.count(a.SN) ? kitingRetStuck[a.SN] : 0).arg(phaseAged)
                              .arg(a.DR / BL, 0, 'f', 1).arg(a.UR / BL, 0, 'f', 1).arg(kitX / BL, 0, 'f', 1).arg(kitY / BL, 0, 'f', 1).arg(kSort)
                              .arg(RET_D / BL, 0, 'f', 1).arg(T_IN / BL, 0, 'f', 1).arg(THREAT_R / BL, 0, 'f', 1).arg(kMelee ? 1 : 0));
                    marchCmds++;
                    continue;   // RETREAT 段不落站桩/推进
                }

                // ★★★★★ 2026-09-14「反攻时拉扯必须成功」第 2 步：接敌带站桩射 ★★★★★ 旧实现只 dK ≤ R 才站桩射，dK∈(R, R+2] 被 issueMarch 接管（目标=敌基地，方向朝前）⇒ 弓兵被
                // 一路推过目标贴脸，RETREAT 与推进互相拉扯=净位移≈0（实测 ln7 SN=91382 全程 882 条撤退令、
                // 仅 27 条 SHOOT 采样、dK 一路 7.9→1.8 被贴脸）。新：dK ≤ R+2 即视为接敌带，只发攻击令不发移动令。
                if (phase == 0 && kGot && dK <= R + 2.0 * BL) {
                    // —— SHOOT 阶段射程内攻击(撤完保护期 60 帧内不重发,符合用户"攻击目标间隔扩大"指示) ——
                    // ★ 2026-09-22 「撤完等久一点再开火」60 帧 → 15 帧（0.6 秒）。这是"打不到"的第二根因：
                    //   同一 SN 的撤退窗口间隔中位 = 60 帧，恰好压住旧保护期 60 帧 ⇒ 保护期卡在临界值上：
                    //   窗口后 ≤15 帧能拿到同 SN 攻击令的仅 2.1%、≤30 帧 4.0%、≤60 帧 37.8%（gsk 12 局 10919 窗口）。
                    //   逐帧例：vf_gsk_1 SN=91396 在 f=33737~34553（816 帧）里撤退令 14 条、攻击令 0 条、移动令 14 条。
                    //   改后（15 帧）≤30 帧内重新开火的比例 = 4.0% → 26.5%。
                    //   保护期的原本目的（"撤完别立刻开火，免得引擎又把单位带回射程"）现在由【撤退距离 ≤ 自身射程】直接保证，
                    //   故只保留最小去抖量。
                    const int RETREAT_PROTECT_FRAMES = 15;
                    const int SHOOT_REISSUE_FRAMES   = 20;   // ★ 2026-09-14 攻击令最小重发间隔(≈0.8 秒)
                    bool retreatProt = lastRetreatFrame.count(a.SN) &&
                                       (frame - lastRetreatFrame[a.SN] < RETREAT_PROTECT_FRAMES);
                    bool atkCool = !kitingAtkFrame.count(a.SN) ||
                                   (frame - kitingAtkFrame[a.SN] >= SHOOT_REISSUE_FRAMES);
                    if (!retreatProt && a.WorkObjectSN != kEnemy && atkCool) {
                        HumanAction(a.SN, kEnemy);            // 接敌带→攻击,引擎自行逼近到射程(不发移动令)
                        kitingAtkFrame[a.SN] = frame;
                    }
                    if (frame % 100 == 0)
                        DebugText(QString("[KIT-S f=%1] SN=%2 phaseAged=%3 dK=%4 R=%5 tSort=%6").arg(frame).arg(a.SN).arg(phaseAged).arg(dK / BL, 0, 'f', 1).arg(R / BL, 0, 'f', 1).arg(kSort));
                    marchCmds++;
                    continue;   // 接敌带→站桩/引擎逼近,绝不落下方推进段
                }
                // ★ 2026-09-14：RETREAT 相位内【绝不落到推进段】——旧实现 phase==1 但 !canReissue 时会 掉进 issueMarch（目标=敌基地=朝前）⇒ 撤退途中被"推回去"，与撤退令互相抵消。
                if (phase == 1) { marchCmds++; continue; }
// ★ 2026-09-18 撤退冷静期 —— 修「交手后完全不撤退」的第二个抵消源。 铁证（gi 批 24 局 7321 个撤退窗口）：40.4% 的窗口在随后 90 帧内【又冒出完全不同落点】的移动令，且都是
// issueMarch 的「朝敌方基地对角角落」推进落点（方向与撤退完全相反）⇒ 把刚撤开的单位又推回敌人堆、净位移≈0。
// 修：撤退后 120 帧(4.8 秒) 内 SHOOT 相位【不落推进段】。接近交给攻击令，由引擎按射程自行处理。
                const int KITING_REGATHER_FRAMES = 120;
                if (phase == 0 && kGot && lastRetreatFrame.count(a.SN) &&
                    (frame - lastRetreatFrame[a.SN] < KITING_REGATHER_FRAMES)) {
                    marchCmds++;
                    continue;
                }
                // 射程外 / 无敌 / SHOOT 但脱战:落入下方常规推进段
            }

            // ★ 2026-09-14：投石车豁免此闸。原实现下投石车开火即进 ATTACKING(≠IDLE)，整段 standoff/后撤 被 continue 跳过 ⇒ 只会站桩挨打、永不拉扯（弓兵相位机在闸之前才有拉扯）。豁免后由下方投石车块
            // 按"≤10.5 格站桩 / ≤7 格后撤"自行节奏，且全程受节流保护，不会每帧换目标或改方向。
            if (a.NowState != HUMAN_STATE_IDLE && a.Sort != AT_STONE_THROWER) {
                if (!stuckNow || !canReissue) continue;   // 正常行进中不打断；卡死且到窗口才重下令
            } else if (stuckNow && !canReissue) {
                continue;                                  // IDLE但已判卡死→节流，给引擎时间走
            }

            bool ranged = sortIsRanged(a.Sort);
            if (pass == 0 && !ranged) continue;   // 第一遍：投石车+远程
            if (pass == 1 && ranged) continue;    // 第二遍：近战殿后/补位
            if (marchCmds >= 8) break;

            // ★ 未达全体反攻门槛：全军回 TC 附近集结待命，不推进不接战（含远程/投石车，避免零散冲出被集火）。
            // ★ 2026-09-07 修：原实现让【所有】单位 HumanMove 到同一个 rallyCtr(TC 中心)点——实测复合弓 91456/91457/91458、方阵兵 91052、投石车 91077 全部到同一坐标 (751.319,2754.84)，互相挤占、
            // 寻路反复失败 ⇒ 原地抖动。新：目标点 = TC 中心 + 朝该单位自己方向外推 12 格 + SN 扇形散开。
            if (!readyToAttack) {
                if (calDistance(a.DR, a.UR, rallyCtrDR, rallyCtrUR) > 12 * BL && canReissue) {
                    double ux = a.DR - rallyCtrDR, uy = a.UR - rallyCtrUR;
                    double baseAng = (std::sqrt(ux*ux + uy*uy) > 1e-6) ? std::atan2(uy, ux) : 0.0;
                    bool moved = false;
                    double angTries[3] = {0.0, 0.25, -0.25};          // 主方向 + 两侧微调，防落点被占
                    // ★ 2026-09-17（用户：「停驻集结时不要站在同一点」）：原 SN 散开只有 7 类 ((SN%7)-3)*0.12 ⇒ 同方向出发的单位大量撞同一点。改为 13 类角度 + 5 类半径
                    // 向内错位（半径 9.6~12 格，不越过下方 `>12格` 的集结到位判据 ⇒ 到达即停止重发）。
                    for (int ti = 0; ti < 3 && !moved; ++ti) {
                        double ang = baseAng + ((a.SN % 13) - 6) * 0.09 + angTries[ti];
                        double holdR = (12.0 - (double)(a.SN % 5) * 0.6) * BL;
                        double gx = rallyCtrDR + std::cos(ang) * holdR;
                        double gy = rallyCtrUR + std::sin(ang) * holdR;
                        gx = max(0.0, min((double)MAP_L * BL, gx));
                        gy = max(0.0, min((double)MAP_U * BL, gy));
                        if (isPassableAt(gx, gy, forestGrid)) {
                            HumanMove(a.SN, gx, gy);
                            marchCmdFrame[a.SN] = frame;
                            moved = true;
                        }
                    }
                }
                marchCmds++;
                continue;
            }

// ================================================================================
// ★★★★★ 2026-09-14 投石车 standoff/拉扯（用户需求：「反攻时投石车一定要能成功拉扯」）★★★★★
// 铁证(ln1 f≥33000)：投石车 91129 发 586 条攻击令落在 13 个目标上，引擎每 1~3 帧一条"开始向X攻击" ⇒ 瞄准进度每帧
// 重设、零命中；同时段撤退令 0 条。三条根因：① 目标每帧重选（铁律 14）；② 撤退线 11 格 < 选取范围 15 格且
// > 射程 10 格 ⇒ 10~15 格区间空转；③ 本块在 `NowState != IDLE → continue` 闸之后 ⇒ 开火中整段被跳过、永不后撤。 修：①目标粘滞(30 帧评估、新目标需近 ≥2 格) ②攻击令 20 帧节流 ③IDLE 闸对投石车豁免
// ④射程带 ≤10.5 格站桩、真贴身 ≤7 格才撤、退到 14 格才停（迟滞）=「打-撤-再打」闭环。
            if (a.Sort == AT_STONE_THROWER) {
                const double CAT_RANGE     = 10.0 * BL;              // 投石车最大射程(DIS_STONE_THROWER=10格)
                const double CAT_FIRE_BAND = CAT_RANGE + 0.5 * BL;   // ≤10.5 格：可站桩输出
                const double CAT_FLEE_TRIG = CAT_RANGE * 0.7;        // ≤7 格：真被贴身→后撤
                const double CAT_FLEE_EXIT = CAT_RANGE * 1.4;        // 退到 14 格才停（迟滞）
                // —— ① 目标粘滞：沿用旧目标，只有"死了/跑出 15 格/新目标近 ≥2 格"才换 ——
                int atkSN = -1; double atkD = 1e12;
                if (catTargetSN.count(a.SN)) {
                    int cur = catTargetSN[a.SN];
                    double cx = 0, cy = 0;
                    bool alive = lookupEnemySN(cur, cx, cy);
                    if (alive) {
                        atkD = calDistance(a.DR, a.UR, cx, cy);
                        if (atkD > 15 * BL) alive = false;      // 目标跑出选取范围→放手
                        else atkSN = cur;
                    }
                }
                bool catReEval = !catTargetFrame.count(a.SN) || (frame - catTargetFrame[a.SN] >= 30);
                if (catReEval) {
                    int cand = findCatapultTarget(a.DR, a.UR, 15 * BL);
                    if (cand >= 0 && cand != atkSN) {
                        double cx = 0, cy = 0;
                        bool found = lookupEnemySN(cand, cx, cy);
                        double cd = found ? calDistance(a.DR, a.UR, cx, cy) : 1e12;
                        if (atkSN < 0 || cd + 2.0 * BL < atkD) { atkSN = cand; atkD = cd; }  // 只有明显更近才换目标
                    }
                    catTargetFrame[a.SN] = frame;
                }
                if (atkSN >= 0) catTargetSN[a.SN] = atkSN;
                // —— ② 威胁判定 + 后撤（迟滞：进入线 7 格 / 退出线 14 格）——
                int threatSN = findNearestEnemySN(a.DR, a.UR, CAT_RANGE * 1.6);
                double ex = 0, ey = 0;
                bool gotThreat = (threatSN >= 0) && lookupEnemySN(threatSN, ex, ey);
                bool catRetreating = (catRetreat.count(a.SN) && catRetreat[a.SN]);
                if (gotThreat) {
                    double d = calDistance(a.DR, a.UR, ex, ey);
                    bool wantRetreat = catRetreating ? (d < CAT_FLEE_EXIT) : (d <= CAT_FLEE_TRIG);
                    if (wantRetreat) {
                        if (!catRetreating) catRetreat[a.SN] = 1;
                        // ★ 30 帧节流：12 帧≈0.48 秒不够走 1 格；30 帧=1 秒足够完成 1 次 standoff 闭环。
                        const int CAT_COOLDOWN = 30;
                        bool cool = !marchCmdFrame.count(a.SN) ||
                                    (frame - marchCmdFrame[a.SN] >= CAT_COOLDOWN);
                        if (cool) {
                            double ux = (a.DR - ex) / (d + 1e-6), uy = (a.UR - ey) / (d + 1e-6);
                            double angs[5] = {0.0, 0.6, -0.6, 1.2, -1.2};   // 多方向试退路防被挡/卡树
                            bool moved = false;
                            for (int ai = 0; ai < 5 && !moved; ++ai) {
                                double ca = std::cos(angs[ai]), sa = std::sin(angs[ai]);
                                double rx = ex + (ux*ca - uy*sa) * CAT_FLEE_EXIT;   // 落点=威胁点+14 格（真出射程）
                                double ry = ey + (uy*ca + ux*sa) * CAT_FLEE_EXIT;
                                rx = max(0.0, min((double)MAP_L * BL, rx));
                                ry = max(0.0, min((double)MAP_U * BL, ry));
                                if (isPassableAt(rx, ry, forestGrid)) { HumanMove(a.SN, rx, ry); marchCmdFrame[a.SN] = frame; moved = true; }
                            }
                            if (!moved && atkSN >= 0 && a.WorkObjectSN != atkSN) HumanAction(a.SN, atkSN);   // 退路全挡→原地攻击
                        }
                        marchCmds++;
                        continue;   // 后撤窗口内不做别的
                    }
                    catRetreat[a.SN] = 0;   // 敌已退到 14 格外 → 解除迟滞（与置位条件同源，铁律 9）
                } else {
                    catRetreat[a.SN] = 0;
                }
                // —— ③ 射程带内(≤10.5 格)：站桩输出。目标粘滞 + 20 帧节流，绝不每帧重发 ——
                if (atkSN >= 0 && atkD <= CAT_FIRE_BAND) {
                    bool cool = !catAtkFrame.count(a.SN) || (frame - catAtkFrame[a.SN] >= 20);
                    if (a.WorkObjectSN != atkSN && cool) {
                        HumanAction(a.SN, atkSN);
                        catAtkFrame[a.SN] = frame;
                    }
                    marchCmds++;
                    continue;   // 射程带内→站桩打，不推进（引擎不再逼近）
                }
                // —— ④ 目标在射程外：靠攻击令让引擎自行逼近（30 帧节流，防每帧重发打断移动）——
                if (atkSN >= 0) {
                    bool cool = !catAtkFrame.count(a.SN) || (frame - catAtkFrame[a.SN] >= 30);
                    if (a.WorkObjectSN != atkSN && cool) {
                        HumanAction(a.SN, atkSN);
                        catAtkFrame[a.SN] = frame;
                    }
                    marchCmds++;
                    continue;
                }
// —— ⑤ 无敌可打：推进 —— ⚠【2026-09-14 修】整段必须包在 canReissue 里！旧写法 `if (stuckTry<=0 && canReissue){...}`
// 的 else 恰是"已被节流"时进入 ⇒ **每帧都发一条移动令**。旧版块在 IDLE 闸之后被掩盖；本轮豁免 IDLE 闸后立刻暴露：
// 实测 kt4 投石车 91129 在 f=33003~45000 每帧一条 HumanMove（9555 条刷屏）⇒ 把 standoff/后撤令顶掉。
                if (canReissue) {
                    HumanMove(a.SN, targetDR, targetUR);   // 投石车：直达敌方基地附近目标点
                    marchCmdFrame[a.SN] = frame;
                    marchGoalDR[a.SN] = targetDR; marchGoalUR[a.SN] = targetUR;   // 判据参照同步
                }
                marchCmds++;
                continue;
            }

            // ★ 远程兵推进 / 拆基地（cpp:3952 之前已重写为"打-拉"双状态机,本段只承接相位机没管的"射程外"流程）： 双状态机未触发(射程外/无敌)→走 issueMarch 推进;到敌基地附近→拆建筑。
            // ★ 拆建筑攻击令去重(2026-09-06)：已在打这建筑就别重发,否则每帧 HumanAction 打断上方的拉扯 HumanMove,     远程兵永远走不到该到位的站位。
            if (ranged) {
                // ★ 2026-09-13「士兵攻击箭塔 → 选距离自己最近的箭塔」+「军队不要攻击敌方武器厂」： 打最近敌塔(TOWER_TARGET_RANGE 格内) → 打最近任意敌建筑(12 格内，武器厂跳过留给祭司) → 推进。
                // 与近战分支共用同一实现（原两处各抄一份 25 行，铁律 21/26）。
                attackBuildingOrMarch(a, "复合弓兵/远程", stuckTry, canReissue);
                marchCmds++;
                continue;
            }

            // 近战单位：路径上的敌人
            // ★ 全体反攻门槛(readyToAttack)已在循环前面统一把关：走到这里即"已达标(≥20人或24分钟)"， 近战也一起接战，不再按旧的 MELEE_GATHER_MIN 单独压制(避免24分钟强制进攻时近战仍畏缩不前)。
            int enemySN = findNearestEnemyNoStone(a.DR, a.UR, 15 * BL);
            // ★ 近战接敌攻击令去重（2026-09-06）：已在打这个敌就别重发， 否则每帧 HumanAction 打断 issueMarch 的推进 HumanMove，近战永远贴不上脸。   同 4099 / 4117 攻击令打断移动的根因。
            if (enemySN >= 0) {
                // 有敌【单位】可打 → 单位永远优先于建筑（保持原语义，含去重）
                if (a.WorkObjectSN != enemySN) HumanAction(a.SN, enemySN);
            } else {
                // 15 格内无敌方单位：打最近敌塔 → 最近敌建筑 → 推进（与远程分支共用实现）。
                attackBuildingOrMarch(a, "近战", stuckTry, canReissue);
            }
            marchCmds++;
        }
    }

    // ★ 2026-09-20 诊断输出（每分钟一行，累计值）：塔"可选机会" vs 实际下达的攻塔令（[TOWER-TGT]）。 判读：① chance12 占比高 且 TOWER-TGT 少 ⇒ 上游分支抢走（H_A 优先级问题）
    // ② chance12 占比低、chance30 高   ⇒ 半径太小（H_B，改 TOWER_TARGET_RANGE） ③ Tier2偏置 长期为 0 ⇒ 方案 B 未生效（要么塔不在 30 格内，要么偏置分支被上游 continue 全吃掉）
    if (twArmyFrames > 0 && frame % 1500 < 2) {
        DebugText(QString("[TOWER-CHANCE f=%1] 累计兵帧=%2 塔<=12格=%3(%4%) 塔<=30格=%5(%6%) Tier2偏置=%7次").arg(frame).arg(twArmyFrames)
                  .arg(twChance12).arg(100.0 * twChance12 / (double)twArmyFrames, 0, 'f', 1).arg(twChance30).arg(100.0 * twChance30 / (double)twArmyFrames, 0, 'f', 1).arg(twBias));
    }

    counterPriestConvert(BL, targetDR, targetUR, rallyCtrDR, rallyCtrUR, forestGrid);

}

// 失败检查
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

// 调试输出（每150帧输出一次）
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

    DebugText(QString("[%1] %2 | Fd:%3 Wd:%4 St:%5 Gd:%6 | Frm:%7 Idle:%8(Carry:%9) Walk:%10 Work:%11 Atk:%12 | Mil:%13 E:%14").arg(frame).arg(s)
        .arg((int)info.Meat).arg((int)info.Wood).arg((int)info.Stone).arg((int)info.Gold).arg(fCount).arg(idleF).arg(idleCarry).arg(walkingF).arg(workingF).arg(attackingF).arg(mil).arg(eCount));
}

// 辅助函数实现

tagFarmer* UsrAI::findIdleFarmer() {
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN)) continue;
        if (f.NowState == HUMAN_STATE_IDLE && f.Resource <= 0) return &f;
    }
    return nullptr;
}

// ★ 2026-09-12：离指定点【最近】的空闲村民（远距选址建筑的建造者选取）。
// 动机：findIdleFarmer 返回的是本帧(每帧随机打乱)列表里的【第一个】空闲村民 ——   对"必须建在 40+ 格外的猎场"这类远距选址，随机抽人会派到 TC 附近的村民，
// 村民长征数十格期间仓库建不出来、打猎闸门一直挂着（食物经济空转）。
tagFarmer* UsrAI::findIdleFarmerNear(double dr, double ur) {
    tagFarmer* best = nullptr;
    double bestD = 1e18;
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN)) continue;
        if (f.NowState != HUMAN_STATE_IDLE || f.Resource > 0) continue;
        double d = dist2(f.DR, f.UR, dr, ur);
        if (d < bestD) { bestD = d; best = &f; }
    }
    return best;
}

tagFarmer* UsrAI::findAnyFarmer() {
    // ★ 2026-09-20 精简：4 轮扫描（石→金→木→非空闲非战斗），轮内条件不同、前缀守卫完全一致 ⇒ 收口为 pass 循环。逐轮全表扫描 + 首个命中即返回 ⇒ 与原先 4 段复制逐字等价。
    for (int pass = 0; pass < 4; ++pass) {
        for (auto &f : info.farmers) {
            if (f.FarmerSort != FARMERTYPE_FARMER) continue;
            if (buildingFarmerType.count(f.SN)) continue;
            if (f.Resource > 0) continue;
            bool hit = (pass == 0) ? (f.NowState == HUMAN_STATE_WORKING && f.ResourceSort == HUMAN_STONE)
                     : (pass == 1) ? (f.NowState == HUMAN_STATE_WORKING && f.ResourceSort == HUMAN_GOLD)
                     : (pass == 2) ? (f.NowState == HUMAN_STATE_WORKING && f.ResourceSort == HUMAN_WOOD)
                                   : (f.NowState != HUMAN_STATE_IDLE && f.NowState != HUMAN_STATE_ATTACKING);
            if (hit) return &f;
        }
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

int UsrAI::buildingFootprintSize(int type) {
    return (type == BUILDING_HOME || type == BUILDING_ARROWTOWER) ? 2 : 3;
}

bool UsrAI::footprintsOverlap(int ax, int ay, int aw, int ah,
                             int bx, int by, int bw, int bh) {
    return !(ax + aw <= bx || bx + bw <= ax || ay + ah <= by || by + bh <= ay);
}

bool UsrAI::inBounds(int blockDR, int blockUR, int size) {
    return blockDR >= 0 && blockUR >= 0 && blockDR + size <= MAP_L && blockUR + size <= MAP_U;
}

bool UsrAI::isBlockedByBuildings(int blockDR, int blockUR, int size,
                                const std::vector<tagBuilding>& buildings) const {
    for (auto &b : buildings) {
        int bSize = buildingFootprintSize(b.Type);
        if (footprintsOverlap(blockDR - BUILD_GAP, blockUR - BUILD_GAP,
                              size + 2 * BUILD_GAP, size + 2 * BUILD_GAP,
                              b.BlockDR, b.BlockUR, bSize, bSize)) {
            return true;
        }
    }
    return false;
}

bool UsrAI::isBlockedByResources(int blockDR, int blockUR, int size,
                                const std::vector<tagResource>& resources) const {
    for (auto &r : resources) {
        if (r.Cnt <= 0) continue;
        for (int i = blockDR; i < blockDR + size; ++i)
            for (int j = blockUR; j < blockUR + size; ++j)
                if (i == r.BlockDR && j == r.BlockUR) return true;
    }
    return false;
}

// ★ 2026-09-15 去重：敌方建筑里找距 (dr,ur) 最近者（= 下列三个查找函数共用的底座）。 距离口径 = 建筑中心 (BlockDR+1, BlockUR+1) × BLOCKSIDELENGTH（与旧代码逐字一致）。
// bestD2 传入当前最优距离²并在命中时更新 ⇒ 调用方可把它与"单位候选"混在同一池里比较。
int UsrAI::nearestEnemyBuildingFrom(double dr, double ur, double &bestD2, int typeFilter) {
    int bestSN = -1;
    for (const auto &b : info.enemy_buildings) {
        if (typeFilter >= 0 && b.Type != typeFilter) continue;
        double bDR = (b.BlockDR + 1.0) * (double)BLOCKSIDELENGTH;
        double bUR = (b.BlockUR + 1.0) * (double)BLOCKSIDELENGTH;
        double d = dist2(bDR, bUR, dr, ur);
        if (d < bestD2) { bestD2 = d; bestSN = b.SN; }
    }
    return bestSN;
}

// 范围内最近敌方建筑SN：反攻直奔已知基地后，部队抵达基地附近需主动拆建筑(不仅打兵)。   建筑坐标用区块中心 (BlockDR+1)*BL 计算距离；range 内无敌方建筑返回 -1。
int UsrAI::findNearestEnemyBuilding(double dr, double ur, double range) {
    double bestD2 = range * range;
    return nearestEnemyBuildingFrom(dr, ur, bestD2, -1);
}

// ★ 2026-09-13 用户需求「士兵攻击箭塔时选择距离自己最近的箭塔为目标」。 只扫 info.enemy_buildings 中 Type==BUILDING_ARROWTOWER 的项，取【距 (dr,ur) 最近】者。
// 距离口径与 findNearestEnemyBuilding 一致：建筑中心 = (BlockDR+1, BlockUR+1)×BL（箭塔 2×2，+1 即中心）。 range 为"格"换算后的像素距离（调用方传 N*BL），超出该半径的塔不构成即时威胁 → 返回 -1。
int UsrAI::findNearestEnemyTower(double dr, double ur, double range) {
    double bestD2 = range * range;
    return nearestEnemyBuildingFrom(dr, ur, bestD2, BUILDING_ARROWTOWER);
}

tagResource* UsrAI::findNearestResource(int type, double dr, double ur) {
    tagResource* best = nullptr;
    double bestDist = 1e12;
    for (auto &r : info.resources) {
        if (r.Type == type && r.Cnt > 0) {
            double d = dist2(r.DR, r.UR, dr, ur);
            if (d < bestDist) { bestDist = d; best = &r; }
        }
    }
    return best;
}

// ★ 砍树选树：优先"离已建成仓库/TC 近"的树，而不是"离村民近"的树。 【为什么】只比"村民→树"时，村民在远处干活结束变空闲，最近的树往往是脚边远离基地的林子，砍完要横穿半张地图卸货。
// 【策略】score = (α·村民→树 + β·树→最近锚点) × 拥挤惩罚，取最小。β(1.0) > α(0.5) → 锚点主导。 【锚点】Percent==100 的 BUILDING_STOCK / BUILDING_CENTER（在建中的不算）。细节坐标 =(BlockDR+1)*BL。
// 【硬闸】树→锚点 > WOOD_MAX_ANCHOR_DIST 个 BLOCK 直接排除；硬闸内无可用树时退化为"离锚点最近的树"   ——★ 绝不退化回"离村民最近的远树"，这是修复关键。
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
            double d2 = dist2(r.DR, r.UR, bx, by);
            if (d2 < anchorD2) anchorD2 = d2;
        }
        // 无建成锚点（开局瞬间 / TC 与仓库全毁）→ 不惩罚，等价于纯按村民距离选
        double anchorD = (anchorD2 >= 1e12) ? 0.0 : std::sqrt(anchorD2);

        // ---- 单树拥挤：树上已有工人 + 本帧已派，不超过上限 ----
        int workerCount = countFarmersOnTarget(r.SN);
        const bool treeFull = (workerCount + frameWoodCount[r.SN] >= WOOD_MAX_WORKERS_PER_TREE);

        // 兜底：全池里离锚点最近【且未满员】的树（不受硬闸限制，避免跑远树）。   ★ 2026-09-08：原实现不判满员——硬闸内树全满员时会退到这棵树，反而挤成 2 人，
        // 与"每棵树最多 1 人"冲突。故此处同步遵守人数上限。
        if (!treeFull && anchorD < bestAnchorDist) { bestAnchorDist = anchorD; nearestAnchorTree = &r; }

        if (anchorD > maxAnchor) continue;   // ★ 硬闸：离仓库/TC 太远的树不派工
        if (treeFull) continue;              // ★ 满员 → 本帧不再往这棵树派人

        double vd = std::sqrt(dist2(r.DR, r.UR, dr, ur));
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
            double d2 = dist2(best->DR, best->UR, bx, by);
            if (d2 < bd2) bd2 = d2;
        }
        double ad = (bd2 < 1e12) ? (std::sqrt(bd2) / BL) : -1.0;
        double vd = std::sqrt(dist2(best->DR, best->UR, dr, ur)) / BL;
        DebugText(QString("WOOD-TREE | sn=%1 anchor=%2BL villager=%3BL cnt=%4 (maxAnchor=%5BL)").arg(best->SN).arg(ad, 0, 'f', 1).arg(vd, 0, 'f', 1).arg(best->Cnt).arg(WOOD_MAX_ANCHOR_DIST));
    }
    return best;
}

// 在【敌军队 → 敌农民】中找最近者；bestD2 传入当前最优距离²并在命中时被更新
//   （便于与"建筑候选"混在同一池里比较）。skipStone=true 时跳过敌方投石车（留给祭司感化）。
// 返回 SN，无命中 -1。2026-09-23 由 findNearestEnemySN / findCatapultTarget 去重抽出。
int UsrAI::findNearestEnemyUnit(double dr, double ur, double &bestD2, bool skipStone) {
    int bestSN = -1;
    for (const auto &e : info.enemy_armies) {
        if (skipStone && e.Sort == AT_STONE_THROWER) continue;
        double d = dist2(e.DR, e.UR, dr, ur);
        if (d < bestD2) { bestD2 = d; bestSN = e.SN; }
    }
    for (const auto &e : info.enemy_farmers) {
        double d = dist2(e.DR, e.UR, dr, ur);
        if (d < bestD2) { bestD2 = d; bestSN = e.SN; }
    }
    return bestSN;
}

int UsrAI::findNearestEnemySN(double dr, double ur, double range) {
    double bestD2 = range * range;
    return findNearestEnemyUnit(dr, ur, bestD2, false);
}

// 军事单位选敌：范围内"最近敌方单位(军队优先于村民)"，但永远排除投石车(AT_STONE_THROWER)—— 投石车留给祭司感化，军事单位即使附近无其它敌也不得攻击投石车。
// ★ 不做"近战优先"：用户要求取消优先迎击近战，恢复为选最近敌人(含远程兵/村民)。
int UsrAI::findNearestEnemyNoStone(double dr, double ur, double range) {
    int bestSN = -1;
    double bestDist = range * range;
    for (const auto &e : info.enemy_armies) {
        if (e.Sort == AT_STONE_THROWER) continue;   // 投石车留给祭司，军事单位不攻击
        double d = dist2(e.DR, e.UR, dr, ur);
        if (d < bestDist) { bestDist = d; bestSN = e.SN; }
    }
    if (bestSN >= 0) return bestSN;
    // 无军队敌人→村民(原兜底行为)
    bestDist = range * range;
    for (const auto &e : info.enemy_farmers) {
        double d = dist2(e.DR, e.UR, dr, ur);
        if (d < bestDist) { bestDist = d; bestSN = e.SN; }
    }
    return bestSN;
}

// 投石车专用选敌(反攻需求)：范围内最近目标 = 任意敌方单位(含敌方投石车) + 敌方箭塔建筑。
// 与 findNearestEnemyNoStone 不同——投石车主动摧毁敌方投石车与箭塔(火力压制，不留给祭司感化)。   敌方建筑用 Block 中心坐标 (BlockDR+1)*BL 计算距离。
int UsrAI::findCatapultTarget(double dr, double ur, double range) {
    double bestD2 = range * range;
    int bestSN = findNearestEnemyUnit(dr, ur, bestD2, false);
    // 建筑候选（只打箭塔，其它建筑由后续推进逻辑处理）——与上面的单位候选共用同一 bestDist 池
    int bSN = nearestEnemyBuildingFrom(dr, ur, bestD2, BUILDING_ARROWTOWER);
    return (bSN >= 0) ? bSN : bestSN;
}

int UsrAI::countBuildings(int type) {
    return countBuildings(type, false, true, false);
}

int UsrAI::countBuildings(int type, bool includePending, bool includeDead,
                          bool countUnderConstruction) {
    int cnt = 0;
    for (auto &b : info.buildings) {
        if (b.Type != type) continue;
        if (!includeDead && deadBuildings.count(b.SN)) continue;
        if (!countUnderConstruction && b.Percent < 100) continue;
        cnt++;
    }
    if (includePending) {
        for (auto &kv : pendingBuildIns)
            if (kv.second.second == type) cnt++;
    }
    return cnt;
}

int UsrAI::countBuildingsAll(int type) {
    return countBuildings(type, false, false, true);
}

// ★ "是否已存在（含地基/待回写指令）"计数：用于唯一建筑(市场/谷仓/兵营/靶场/马厩/学院) 的存在性门槛。
// 旧写法 countBuildingsAll()==0 会漏算两类导致重复建造：① 指令已下发、地基尚未回写进 info.buildings 的窗口期； ② 地基卡 0% 被拉黑进 deadBuildings 后仍杵在地图上，却被当成"不存在"→原地再建一座。
// 对②给一段宽限(DEAD_BUILDING_GRACE 帧) 让"孤儿地基抢救"先尝试补救，超时后才允许另建。
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
    // 最后一道保险：指令刚下发(≤90帧)但地基/待定条目都还没回写 → 也当作"已存在"， 彻底杜绝"异步窗口内连下两次建造令"导致的重复建造（市场建两座的主因之一）。
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

// 统计 WorkObjectSN == sn 的村民数（引擎"工作目标"口径，不含手持资源）。2026-09-23 由 6 处重复循环去重抽出。
int UsrAI::countFarmersOnTarget(int sn) {
    int n = 0;
    for (auto &f : info.farmers)
        if (f.WorkObjectSN == sn) n++;
    return n;
}

bool UsrAI::isPositionFree(int blockDR, int blockUR, int size) {
    if (!inBounds(blockDR, blockUR, size)) return false;
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

    // ★ 建筑间距检查：候选 footprint 外扩 BUILD_GAP 格内不得与任何建筑相交(含边界)， 否则建筑会紧贴成墙、堵死村民/士兵的通行路线。外扩 1 格 = 建筑之间至少留 1 格通道。
    if (isBlockedByBuildings(blockDR, blockUR, size, info.buildings)) return false;

    // 敌方建筑间距检查（已探索区域内的敌方建筑同样阻挡建造）
    if (isBlockedByBuildings(blockDR, blockUR, size, info.enemy_buildings)) return false;

    // 资源重叠检查
    if (isBlockedByResources(blockDR, blockUR, size, info.resources)) return false;

    // ★ 避开狮子周围区域：狮子会攻击靠近的建筑/村民，建在狮子附近会导致建好即被骚扰、
    // 村民往返送死。候选点中心离任一 RESOURCE_LION(Cnt>0) 过近即判为不可建。   用距离平方比较，避免引入 <cmath> 依赖；半径见 LION_AVOID_RADIUS。
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

// 地基可达性预检：确保村民能走到地基旁（避免选址被建筑围死、村民永远走不到=卡死）。   做法：在 footprint 外扩 1 格的"接近环"上找空闲瓦片作多源起点，
// 从这些起点向"可行走"瓦片做有界 BFS；若能走出足够远(连通分量够大=通到开阔地)即视为可达。 被建筑完全围死时连通分量很小 → 拒绝该点，迫使 tryBuild 另择新址（而非建在死胡同里卡死）。
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
            int bs = buildingFootprintSize(b.Type);
            if (i >= b.BlockDR && i < b.BlockDR + bs &&
                j >= b.BlockUR && j < b.BlockUR + bs) return true;
        }
        // 敌方建筑（已探索区域内同样阻挡）
        for (auto &b : info.enemy_buildings) {
            int bs = buildingFootprintSize(b.Type);
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

// 建筑选址：偏向 TC→地图中心方向、离 TC 更远，避免挤在 TC 边角堵路。   minR/maxR = 距 TC 的最小/最大环半径(单位:block)；在 [minR,maxR] 范围内收集所有空闲点，
// 按 score = 朝向中心方向的对齐度*100 + 距TC超出minR的距离 选最优——方向优先、其次更远。
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

bool UsrAI::findBuildSite(int &x, int &y, int size, bool avoidFarmAdjacent) {
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
                if (!isPositionFree(nx, ny, size)) continue;
                // ★ 2026-09-15：农场兜底选址时守住"农场之间至少隔 1 格"（isFarmAdjacent 的刻意设计）
                if (avoidFarmAdjacent && isFarmAdjacent(nx, ny)) continue;
                x = nx; y = ny;
                return true;
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
// 箭塔选址（第2座一直没人建的修复）：⚠ 只扫 r=4~8 外环会失败 —— BUILD_GAP=1 ⇒ 箭塔(2×2)外扩 1 格 = gap 3 格内不得有建筑，
// r=4 时与 TC footprint 重叠 ⇒ isPositionFree 永 false（实际可用最小 r=5）；且 TC 周围经济建筑层层占据，整圈可能 0 可用。
// 修：① 放宽到 r=4~12（4~8 优先、9~12 兜底，均在箭塔射程 8 格覆盖内），2×2 塔改用 max(|dx|,|dy|)==r 的"钻石形"外圈； ② 失败前清空 triedBuildPositions，让 tryBuild 兜底不受旧 ban 卡。
// 选址策略：第1座朝地图中心，第2座取反方向；都贴身 TC（4~8 优先）、次选 9~12 远离。
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
        // ★ 2026-09-04 瞪羚仓库选址放宽：30→GAZELLE_HUNT_RANGE(50) 格（与猎人选取同步）， 浆果丛保留 30 格（快速周转需求不变）。
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

// 远距浆果群定位（第二座谷仓专用，2026-09-07）：除 TC 附近的浆果地外，若别处还有 ≥MIN_BUSH_FOR_SECOND_GRANARY 丛的
// 浆果群，就在它旁边建第二座谷仓，让采集村民就近交食物（浆果 → HUMAN_GRANARYFOOD → 谷仓）。 判据三条同时成立：① 距 TC ≥ SECOND_GRANARY_TC_MIN_DIST(25) 格（排除 TC 附近那一片）；
// ② 距【任一已有谷仓(含在建地基)】> 12 格（避免在同一片重复建）；③ 以该丛为中心 BUSH_CLUSTER_RADIUS(5) 格内的存活丛数 ≥ 6。
// 命中多片时取丛数最多的一片，输出该中心丛的块坐标（供 tryBuild 的 prefX/prefY 使用）。
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
// 农场 footprint = [blockDR, blockDR+2] x [blockUR, blockUR+2]，外扩1格 = [blockDR-1, blockDR+3] x [blockUR-1, blockUR+3]。 与任一已有农场的 footprint 有交集(含边界)即判"相邻" → 拒绝。
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
// ★★★ 2026-09-15 农场选址（用户需求：尽量分布在 TC 和谷仓周围）★★★ 候选空间 = TC 环 ∪ 各已建成【谷仓 GRANARY】环（半径 [R_MIN, R_MAX]，隔 1 格几何）；
// ★ 2026-09-19 用户要求：仓库 STOCK 不再作锚点（详见文件头 FARM_ANCHOR_R_MAX 下方需求块）。
// 评分基准 =【到 TC 的距离最小】—— 刻意不用"到最近锚点最近"：农场原地生产、村民从 TC 出发 ⇒ 代价 = TC→农场通勤。
// 按"到最近锚点"评分会让谷仓旁 r=4(4格) 压过 TC 旁 r=5(5格)，实测 39.2% 农场被甩到 >10 格。 判据顺序（便宜的先做，降开销）：黑名单 → isPositionFree（地形/建筑间距/资源/狮子）→ isFarmAdjacent。
// 全部候选都不可用 ⇒ 返回 false，农场【本帧不建】（通用兜底对农场已禁用，见 tryBuild）。
bool UsrAI::findFarmSiteBest(int &x, int &y) {
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return false;

// ---- 锚点集合（块左下角）：TC 第一（平局优先），其后【谷仓】 ----
// ★★★ 2026-09-19 用户要求：「农场可以建在谷仓附近，但不能建在仓库附近」⇒ 锚点只收 BUILDING_GRANARY，**不再收 STOCK**。
// 排除仓库的理由见文件头 FARM_ANCHOR_R_MAX 下方的需求块（仓库是远距猎场节点，非经济圈）。 ⚠ fc 批实测 (13,34)/(23,32) 两座仓库锚点合计吃掉 33/87 = 37.9% 的农场落位 —— 本次按用户要求一并取消。
    std::vector<std::pair<int, int> > anchors;
    std::vector<int> anchorTypes;          // ★ 与 anchors 严格同下标（0=TC，其余=谷仓）—— 供 FARM-PICK 日志核对
    anchors.push_back(std::make_pair(center->BlockDR, center->BlockUR));
    anchorTypes.push_back(BUILDING_CENTER);
    for (auto &b : info.buildings) {
        if (b.Percent < 100) continue;                       // 只在【已建成】的谷仓旁扩展
        if (b.Type != BUILDING_GRANARY) continue;            // ★ 仓库 BUILDING_STOCK 已按用户要求排除
        anchors.push_back(std::make_pair(b.BlockDR, b.BlockUR));
        anchorTypes.push_back(b.Type);
    }
    // ★★★ 2026-09-19 修复：TC 必须恒居 anchors[0] ★★★ 旧代码对【含 TC 的整个 anchors】做 std::sort ⇒ 块坐标字典序小于 TC 的谷仓/仓库会顶掉 TC。
    // 实测本图第二谷仓 (13,34) 的 x=13 < TC (19,18) 的 x=19 ⇒ anchors[0]=(13,34)，而下游三处全部硬编码假定 [0]==TC：
    // ① 段 1 的 ringOf(anchors[0]...) —— 号称「TC 环」，实际在谷仓周围枚举；② 段 1 的评分基准 base=0；
    // ③ 剪枝 (double)r*r > bestD2。⇒ 农场被建到谷仓旁，相对真 TC 距离高达 16 格（ff1 实证 (9,34)：相对 (13,34) 是 r=4）。 修复：TC 单独置顶不参与排序，其余锚点排序去重后追加。
    // ★ 锚点类型必须随坐标一起搬运（anchorTypes 与 anchors 严格同下标），否则排序后类型错位、FARM-PICK 的 ty= 字段失效。
    if (anchors.size() > 1) {
        std::vector<std::pair<std::pair<int, int>, int> > rest;
        rest.reserve(anchors.size() - 1);
        for (size_t i = 1; i < anchors.size(); ++i)
            rest.push_back(std::make_pair(anchors[i], anchorTypes[i]));
        std::sort(rest.begin(), rest.end());
        rest.erase(std::unique(rest.begin(), rest.end()), rest.end());
        anchors.resize(1);
        anchorTypes.resize(1);
        for (size_t i = 0; i < rest.size(); ++i)
            if (rest[i].first != anchors[0]) {
                anchors.push_back(rest[i].first);
                anchorTypes.push_back(rest[i].second);
            }
    }
    const int NA = (int)anchors.size();

    // ---- 评分基准 = 到【TC】的距离（块格中心坐标）----   为什么不是"到最近锚点最近"？AoE3 农场原地生产、食物自动入库，村民是【从 TC 出发】去农场的
    // ⇒ 真正的代价是「TC→农场的通勤距离」。谷仓恒在 TC 上方约 52 格（96/96 局实测）； 若按"到最近锚点最近"评分，谷仓旁 r=4 的 4 格会胜过 TC 旁 r=5 的 5 格 ⇒ 实测（fl 批）
    // 39.2% 的农场被甩到 >10 格、最远 60.8 格，中位到 TC 从 5.7 恶化到 12.4 —— 已证伪。 ⇒ 谷仓旁只有在"TC 环 [R_MIN, R_MAX] 内全满"时才会胜出，正合用户原话「基地附近位置不够的话」。
    double bestD2 = 1e18;                    // 距离平方（避免 sqrt）
    int bx = -1, by = -1;
    int bestBase = -1;                       // 最优候选所属锚点索引（0=TC）—— 供落位日志使用
    // 候选评定（两段共用）：黑名单 → isPositionFree → isFarmAdjacent → 按「到 base 锚点距离」刷新最优
    // ★ 2026-09-19：base = 评分基准锚点索引（0 = TC；>=1 = 对应的谷仓）。     两段各自【段内】公平比较，段间不比较 ⇒ 第 1 段（TC 环）永远优先。
    auto consider = [&](int nx, int ny, bool useBlack, int base) {
        if (nx < 0 || ny < 0) return;
        if (useBlack && triedBuildPositions.count(nx * 1000 + ny)) return;
        if (!isPositionFree(nx, ny, 3)) return;
        if (isFarmAdjacent(nx, ny)) return;
        double fcx = nx + 1.0, fcy = ny + 1.0;
        double abx = anchors[base].first + 1.0, aby = anchors[base].second + 1.0;
        double d2 = dist2(fcx, fcy, abx, aby);
        if (d2 < bestD2) { bestD2 = d2; bx = nx; by = ny; bestBase = base; }
    };
// 锚点外 r 环的 4 条带（上/下/左/右）—— 真 Chebyshev 环（3x3 + 隔 1 格 ⇒ r>=4）。
// ★ 2026-09-19 收紧：原 `n = 2*r + 3` 让每条带在轴向【多伸 2 格】⇒ 越过角点、溢出到 Chebyshev r+1 / r+2 的格子
// （实测 fc 批 87 次落位里 4 次、ff4 里 1/12 落在 r=5/6）。这些格子虽也满足"离建筑 ≥1 格"，但**不在紧邻环上**。 改为 `n = 2*r + 1` ⇒ k∈[0,2r] ⇒ 轴向偏移 ∈ [-r,+r] ⇒ Chebyshev 距离恰为 r。
// ⚠ 四角会被相邻两条带各枚举一次（重复无害：consider 只做评估，不落位）。
    auto ringOf = [&](int ax, int ay, int r, bool useBlack, int base) {
        const int n = 2 * r + 1;
        for (int side = 0; side < 4; ++side) {
            for (int k = 0; k < n; ++k) {
                int nx, ny;
                if (side == 0)      { nx = ax - r + k; ny = ay + r; }       // 上带
                else if (side == 1) { nx = ax - r + k; ny = ay - r; }       // 下带
                else if (side == 2) { nx = ax - r;     ny = ay - r + k; }   // 左带
                else                { nx = ax + r;     ny = ay - r + k; }   // 右带
                consider(nx, ny, useBlack, base);
            }
        }
    };

    // 两遍：第 1 遍尊重 triedBuildPositions（避免反复在同一失败点丢令）； 第 1 遍完全无解时第 2 遍忽略它（近处位置可能早已空出却被永久拉黑 —— 旧代码外扩的成因之一）。
    for (int pass = 0; pass < 2 && bx < 0; ++pass) {
        const bool useBlack = (pass == 0);
        // ---- 第 1 段：TC 环（主锚点；评分基准 = 到 TC）----   r 层候选到 TC 的最小距离恰为 r（nx==ax 时 Δx=0、Δy=r）⇒ 一旦 r² 超过当前最优， 本层及所有更外层都不可能更优，直接 break。
        for (int r = FARM_ANCHOR_R_MIN; r <= FARM_ANCHOR_R_MAX; ++r) {
            if ((double)r * (double)r > bestD2) break;
            ringOf(anchors[0].first, anchors[0].second, r, useBlack, 0);
        }
        if (bx >= 0) break;                  // ★ TC 环有解 ⇒ 不碰谷仓（保通勤最优）
// ---- 第 2 段：谷仓环（★ 仅当第 1 段彻底无解时才跑；仓库已按用户要求排除）----   评分基准切换为【到该锚点】的距离（段内公平）：谷仓旁 4.0 格与 TC 旁 4.0 格等价，但两段之间不比较
// ⇒ 谷仓旁只在"TC 环真的塞不下"时才被启用。   ⚠ 旧代码在此用三角不等式剪枝（谷仓 dAT≈52 ⇒ lb²≈2007 远超 TC 旁 bestD2≈25）⇒ 该段恒被剪空，
// 这正是 09-15 实测"谷仓旁 0 座农场"的成因。改用"仅当第 1 段无解才进入"控制优先级。
        for (int ai = 1; ai < NA; ++ai) {
            for (int r = FARM_ANCHOR_R_MIN; r <= FARM_ANCHOR_R_MAX; ++r)
                ringOf(anchors[ai].first, anchors[ai].second, r, useBlack, ai);
        }
    }
    if (bx < 0) return false;
    // ★ 2026-09-19 农场落位机制量（不受采样影响，最可靠）：选中锚点索引 / 环号 / 相对 TC 环号 r 设计上恒 = FARM_ANCHOR_R_MIN = 4（紧邻环）；tcR 用于判定是否外溢（谷仓环天然很大）。
    {
        int bbx = anchors[bestBase].first, bby = anchors[bestBase].second;
        int rr  = std::max(std::abs(bx - bbx), std::abs(by - bby));
        int tcR = std::max(std::abs(bx - anchors[0].first), std::abs(by - anchors[0].second));
        // ★ ty=[...] = 本次锚点集合的类型序列（C=TC / G=谷仓 / S=仓库），与 base= 的下标一一对应； 这是"农场绝不再靠仓库"的唯一直接证据 —— 只要 ty 里不出现 S，就不可能落在仓库旁。
        char tyBuf[80];
        int  tp = 0;
        for (size_t i = 0; i < anchorTypes.size() && tp < 76; ++i) {
            if (i) tyBuf[tp++] = ',';
            tyBuf[tp++] = (anchorTypes[i] == BUILDING_CENTER)  ? 'C'
                        : (anchorTypes[i] == BUILDING_GRANARY) ? 'G' : 'S';
        }
        tyBuf[tp] = '\0';
        DebugText(QString("[FARM-PICK f=%1] base=%2(%3,%4) r=%5 tcR=%6 -> (%7,%8) ty=[%9]").arg(frame).arg(bestBase).arg(bbx).arg(bby).arg(rr).arg(tcR).arg(bx).arg(by)
                  .arg(QString::fromLatin1(tyBuf)));
    }
    x = bx; y = by;
    return true;
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

    // ★ 2026-09-12：指定坐标的远距建筑优先派【离该点最近的】空闲村民当建造者 （瞪羚群仓库等：打猎闸门在等它落地，不能让建造者从 TC 长征几十格）。
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
        // ★★★ 2026-09-15 统一锚点就近择优（取代旧三段式 findFarmRingSite → findFarmNearGranarySite）★★★ 旧链因第一步内部自带 findBuildSite 兜底而恒返回 true ⇒ 谷仓环那步【永不可达】（死代码）；
        // 且枚举顺序偏向一侧 + 近处失败位置被 triedBuildPositions 永久拉黑   ⇒ 96 局实测 39.4% 的农场被挤到 >6 格、7.2% >10 格，谷仓旁 0 座。
        // 新逻辑把 TC 与全部已建成谷仓作为并列锚点（★ 仓库已按 2026-09-19 用户要求排除）。
        // ★★★ 2026-09-19 用户需求「农场只能建在谷仓和 TC 周围隔一格的地方」★★★ 只在 findFarmSiteBest 的【两段紧邻环】内落位：第 1 段 TC 环 → 第 2 段谷仓环，两段都是 r = R_MIN = 4。
        // 失败即本帧不建（下方通用兜底对农场已禁用）⇒ 不再出现 8~11 格的散落农场。
        placed = findFarmSiteBest(x, y);
        if (!placed) {
            // ★ 诊断（铁律 53：必须打印判据的输入集合规模，否则"0 输出"分不清没触发/没候选/被过滤）
            static int lastFarmRingLog = -9999;
            if (frame - lastFarmRingLog >= 300) {
                lastFarmRingLog = frame;
                int nFarm = 0, nGr = 0, nSt = 0;
                for (auto &b : info.buildings) {
                    if (b.Type == BUILDING_FARM) nFarm++;
                    else if (b.Type == BUILDING_GRANARY && b.Percent >= 100) nGr++;
                    else if (b.Type == BUILDING_STOCK   && b.Percent >= 100) nSt++;
                }
                DebugText(QString("[FARM-RING f=%1] 锚点紧邻环无空位 farms=%2/%3 谷仓锚点=%4 仓库(已排除)=%5 ⇒ 本帧不建").arg(frame).arg(nFarm).arg(MAX_FARMS).arg(nGr).arg(nSt));
            }
        }
    }
    if (!placed && buildingType == BUILDING_ARROWTOWER)
        placed = findDefenseBuildSite(x, y, size);
    // 兵营/靶场/马厩：偏向 TC→地图中心方向、离 TC 更远(12~45格)，成片铺开不堵 TC 周边
    if (!placed && (buildingType == BUILDING_ARMYCAMP || buildingType == BUILDING_RANGE ||
                    buildingType == BUILDING_STABLE))
        placed = findBuildSiteTowardCenter(x, y, size, 12, 45);
    // ★★★ 2026-09-19 用户需求「农场只能建在谷仓和 TC 周围隔一格的地方」⇒ 农场【禁用】通用兜底。 旧行为：findFarmSiteBest 失败后回落到 findBuildSite(avoidFarmAdjacent=true)，而后者只要
    // 地图上还有空位就恒返回 true ⇒ 农场会落到任意远处（实测 30.3% 掉在 r=8 = 8~11.3 格）。   现在农场只在锚点紧邻环内落位；两段都无解 ⇒ 本帧不建（下一帧有空位时自然重试）。
    if (!placed && buildingType != BUILDING_FARM)
        placed = findBuildSite(x, y, size, false);
    if (!placed) return false;

    buildingFarmerType[f->SN] = buildingType;
    builderDispatchFrame[f->SN] = frame;   // ★ 硬超时起点（本次建造令下发帧）
    int buildInsId = HumanBuild(f->SN, buildingType, x, y);
    pendingBuildIns[buildInsId] = {f->SN, buildingType};
    pendingBuildInsFrame[buildInsId] = frame;
    lastBuildIssueFrame[buildingType] = frame;
    // ★★★ 2026-09-22「避免一个瞪羚群附近重复建 2 个仓库」：仓库令【落点记忆】（唯一真源）★★★ 记在 tryBuild 里 = 任何建仓路径（近场块 / 第二仓库块 / 未来新增）都自动覆盖，判据不会漏。
    // (x,y) 是【最终选址】的块坐标（偏移表 / findBuildSite 之后），与 [BUILD-ISSUE] 的 at= 同一口径。
    // 只记最近 STOCK_ORDER_RING 条（= 最多同时在建的仓库数），更早的裁掉（平行数组一起裁，保持同下标）。
    if (buildingType == BUILDING_STOCK) {
        stockOrderDR.push_back(x);
        stockOrderUR.push_back(y);
        stockOrderFrame.push_back(frame);
        while ((int)stockOrderFrame.size() > STOCK_ORDER_RING) {
            stockOrderDR.erase(stockOrderDR.begin());
            stockOrderUR.erase(stockOrderUR.begin());
            stockOrderFrame.erase(stockOrderFrame.begin());
        }
    }

    // 记录尝试过的位置，防止反复在同一位置建造失败
    int key = x * 1000 + y;
    triedBuildPositions.insert(key);

    buildCooldown = 5;   // 5帧冷却（单位碰撞检测已防止重复失败）
    // ★ 2026-09-13 建造下令观测：记录每次 HumanBuild 的类型/村位/坐标， 用于对照"地基何时放下 / 何时完工"，定位长期卡住的地基。
    DebugText(QString("[BUILD-ISSUE f=%1] type=%2 size=%3 村民SN=%4 at=(%5,%6) wood=%7").arg(frame).arg(buildingType).arg(size).arg(f->SN).arg(x).arg(y).arg((int)info.Wood));
    return true;
}

// 处理建造指令执行结果：失败则释放建造者并换位置重试
void UsrAI::handleBuildResults() {
    // 极端安全：待定建造指令异常堆积则清空，避免无限增长
    if (pendingBuildIns.size() > 64) { pendingBuildIns.clear(); pendingBuildInsFrame.clear(); }

    for (auto it = pendingBuildIns.begin(); it != pendingBuildIns.end(); ) {
        int insId = it->first;
        int farmerSN = it->second.first;

        // ★ 结果迟迟不回（引擎未回执）→ 超时清理，否则该名额会被 countBuildingsExisting 永久虚占， 导致建筑被毁后永远无法重建。
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

        // 位置类错误才立即换位置重试（该位置已在 tryBuild 中加入黑名单） 资源不足/未解锁类错误则等 manageBuildings 的条件恢复后再自然重试
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

// 检测寻路卡死的采集村民：空手且长时间非空闲 → 判定目标不可达，强制打断 + 拉黑
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
        if (buildingFarmerType.count(f.SN)) {
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
            // ★ WorkObjectSN 在寻路失败/目标丢失时已被引擎清零(-1)，无法据此拉黑不可达树 → 用 villLastTreeSN 兜底：取本村民最近一次被派去的树SN拉黑，避免同一棵不可达树被反复重选
            if (targetSN <= 0 && villLastTreeSN.count(f.SN)) targetSN = villLastTreeSN[f.SN];
            if (targetSN > 0) stuckResourceUntil[targetSN] = frame + STUCK_BLACKLIST_FRAMES;
            HumanAction(f.SN, center->SN);  // 打断卡死关系，回TC重新待命
            gatherStuckFrame.erase(f.SN);
            DebugText(QString("[STUCK f=%1] 村民SN=%2 寻路卡死, 目标资源SN=%3 已拉黑").arg(frame).arg(f.SN).arg(targetSN));
        }
    }
}

// ★★★ 2026-09-12「先建仓库、再打猎」闸门（用户需求：村民开始狩猎瞪羚前尽量先建仓库）★★★
// 猎人出发前交付点必须已就位，否则猎人抱着肉空跑「猎场↔TC」往返（2×距离），食物效率腰斩。   返回 true = 现在可以去打这只瞪羚；false = 本帧先别派猎人，等仓库落地（仓库块每帧都会重试建造）。
// 判据顺序（任一成立即放行，确保【永远不会把食物经济饿死】）： ① 木头 < 仓库造价 → 根本建不起，不能拿食物陪葬； ② frame ≥ 解禁兜底(6游戏分) 或 已过建造窗口(11游戏分) → 仓库不会来了，放行；
// ③ storageNearGazelleBuilt==1 → 已建好 / 已被现成仓库覆盖 / 已达 MAX_STOCK；
// ④ 该瞪羚 GAZELLE_HUNT_RANGE 内已有仓库（含在建地基）→ 交付点已就位。   ⚠ 判据④把"在建"也算通过：地基已在群边、村民正在施工，此时去打猎不会长距离空跑。
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

    // ★ 食物已达停采水位 ⇒ 不派新食物工。与 assignIdleSimple 的同名门禁同口径，改一处必须同改另一处（铁律 21/26）。
    //   本函数目前只有一个调用点：assignIdleSimple 的 reassignToDeficit()（资源过剩转岗）——
    //   在那里返回 false 的效果 ="别转食物"，控制流自然落到下一档伐木，与该调用点意图一致。
    //   ⚠ 若将来给 tryAssignFood 增加"常规派工"用途的调用点，必须重新评估此闸该不该留在这里。
    const bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
    const bool foodStop = (info.Meat >= (postBronze ? FOOD_CAP_STOP : FOOD_CAP_STOP_PREBRONZE));
    if (foodStop) return false;

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
    // ★ 2026-09-07 放宽：远距浆果群旁建了第二谷仓后，这里的"距 TC ≤30 格"会把它们全挡掉，     导致谷仓建了却没人去采。改为：距 TC ≤30 格 或 距任一已建成谷仓 ≤20 格。
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
        int realCount = countFarmersOnTarget(r.SN);
        if (realCount + frameBushCount[r.SN] >= 2) continue;  // 每丛≤2人（含本帧已分，满2人转其他事）
        double d = dist2(r.DR, r.UR, f->DR, f->UR);
        if (d < bestBDist) { bestBDist = d; bestBush = &r; }
    }
    if (bestBush) {
        HumanAction(f->SN, bestBush->SN);
        frameBushCount[bestBush->SN]++;  // 本帧标记该丛已分1人
        return true;
    }

    // ★ 优先级2：狩猎大象（优先于瞪羚！每头200~300食物，波次期间禁止）★
    // ★ 2026-09-13 用户需求「必须 4 个人一起狩猎」：本函数【只补已成团的队】(已在打 ≥ ELEPHANT_HUNT_MIN 人)， 【绝不单独开团】——开新团由 assignIdleSimple() 的"猎象整队"块在同一帧一次性派 4 人完成。
    if (!isWarTime) {
        tagResource* bestEle = nullptr;
        double bestEDist = 1e12;
        for (auto &r : info.resources) {
            if (r.Type != RESOURCE_ELEPHANT || r.Cnt <= 0) continue;
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > 30 * BL) continue;
            if (stuckResourceUntil.count(r.SN)) continue;
            int realCount = countFarmersOnTarget(r.SN);
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
        int realCount = countFarmersOnTarget(b.SN);
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
            int realCount = countFarmersOnTarget(r.SN);
            if (realCount + frameGazelleCount[r.SN] >= 2) continue;  // 每只≤2人（含本帧已分）
            double d = dist2(r.DR, r.UR, f->DR, f->UR);
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


