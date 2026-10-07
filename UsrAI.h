#ifndef USRAI_H
#define USRAI_H

#include "ai.h"
#include <QEvent>      // 加固层 UsrAICore 需要 QEvent::User 作为自定义事件类型
#include <memory>      // 零拷贝快照：infoPtr 用 std::shared_ptr
#include <set>
#include <map>
#include <vector>
#include <algorithm>
#include <cmath>

extern tagGame tagUsrGame;
extern ins UsrIns;

// 加固层 UsrAICore：集中承载快照获取、线程生命周期、帧末指令提交与诊断心跳。
//   三点加固：
//     · 快照获取：主线程代取 getInfo() + shared_ptr 零拷贝句柄 + 坏快照完整性哨兵
//     · 线程生命周期：析构体里先停 AI 线程，避免业务成员先析构后被 AI 线程访问
//     · 帧末指令提交：commitInstruction()，提交前逐条体检 instruction 的动态指针
//   为什么"加固类做基类"而不是"新类继承 UsrAI"：引擎侧硬编码 new UsrAI()，
//     若新类去继承 UsrAI，它永远不会被构造、加固层等于未装；做成基类则
//     UsrAI 的构造点/使用点一行都不用改。
//   本类保持抽象（不实现 AI 的纯虚 processData / clearInsRet）⇒ 不可实例化，只能被继承。
class UsrAICore : public AI
{
public:
    UsrAICore() : frame(0) { this->id = 0; }
    // 在派生类析构体里先停 AI 线程。理由：C++ 析构顺序 = 派生类成员先析构 → 基类析构体最后跑；
    //   若只依赖 ~AI() 里的 wait()，UsrAI 的成员（含 infoPtr 引用计数）会在 wait() 之前析构，
    //   而 AI 线程可能仍停在 processData() ⇒ 访问已释放资源。
    //   此处为兜底，重复调用无害（stopThread 置位幂等、wait() 对已停线程立即返回）。
    ~UsrAICore() override { stopThread = true; condition.wakeAll(); wait(); }

// 快照改由"主线程"代取：
//   引擎缓冲区 tagUsrGame.getInfo() 与主线程 Core::infoShare() 的释放-重分配存在数据竞争，
//   直接在 AI 线程里直读会崩溃。AI 对象由主线程创建 ⇒ postEvent 给它的事件由主线程事件循环派发；
//   AI 线程 postEvent(this) → 主线程在 event() 里 getInfo()（读写同线程、天然串行）→ AI 取走副本。
//   AI 侧取快照用非阻塞：有新快照就取走，没有就沿用上一帧（数据最多滞后 1 帧），
//   避免把决策吞吐钳死在主线程帧率上。
enum { kSnapEventType = QEvent::User + 731 };

protected:
    bool refreshSnapshot();                // AI 线程：postEvent 请主线程代取快照；成功则更新 infoPtr（零拷贝）
    bool event(QEvent* e) override;        // 主线程执行：真正执行 tagUsrGame.getInfo()

    // 帧末唯一提交点（由 UsrAI::processData 在每帧业务跑完后调用一次）。
    //   AI::run() 里的 AI::CommitInstruction() 是基类非虚函数且不做校验 ⇒ AI 侧接管不了。
    //   instruction 携带两个裸指针（self / obj）：
    //     · self = g_Object[SN]   —— SN 不存在时是 nullptr（且 map::operator[] 会插节点）
    //     · obj  = g_Object[obSN] —— HumanMove / HumanBuild / BuildingAction / PinPointStrike
    //       这四条构造没给 obj 赋值 ⇒ 未初始化野指针
    //   提交前必须逐条体检，否则野指针递进引擎会崩溃。（实现见 .cpp 内本函数）
    void commitInstruction();

    // 诊断心跳
    void logEnvOnce();                     // [ENV]   引擎版本/运行期玩家数自证（必须在首次 getInfo 之前调）
    void logSnapBeat();                    // [SNAP]  快照机制量心跳（每 1500 帧一档）
    void checkDirtySnapshot();             // [DIRTY-SNAP] 脏快照累计拦截（每 1500 帧一行）

// 【零拷贝快照】当前游戏状态。tagInfo 深拷贝不可靠（目标缓冲会被写坏），
//   故改为 shared_ptr 直达：快照对象由主线程 new 出来、AI 线程独占持有，全程零深拷贝。
//   用法：processFrame 顶部 `if (!refreshSnapshot()) return;` 保证非空；
//         此后全文件以 `infoPtr->xxx` 访问。
    std::shared_ptr<tagInfo> infoPtr;
    int frame;                             // 当前帧号（= infoPtr->GameFrame 的副本；加固层心跳与业务共用）

private:
    // 三条心跳的跨帧状态
    bool envLogged_ = false;               // [ENV] 只打一次
    int  lastSnapBeat_ = -1;               // [SNAP] 分桶去重
    int  localDirtySnap_ = 0;              // [DIRTY-SNAP] 累计脏快照拦截
    int  lastNonzeroFrame_ = 0;
    int  lastBeatBucket_ = -1;
};

class UsrAI : public UsrAICore
{
public:
    UsrAI() : state(INIT), townCenterSN(-1), priestSN(-1),
              enemySiegeSN(-1), enemyBaseScouted(false), enemyBaseDR(0), enemyBaseUR(0),
              hasUpgraded(false),
              bronzeIssuedFrame(-999999), bronzeAttemptCount(0), bronzeStallFrames(0),
              wave1Started(false), wave2Started(false), wave3Started(false),
              wave2Defeated(false),
              buildCooldown(0), techCooldown(0), trainCooldown(0),
              debugTimer(0), farmTarget(0),
              storageNearGazelleBuilt(0),
              priestMoveCooldown(0),
              priestCounterCooldown(0),
              wheelResearched(false), wheelQueued(false),
              broadswordResearched(false), broadswordQueued(false),
              marketFarmUpgraded(false),
              marketWoodUpgraded(false),
              marketPlowUpgraded(false),
              useToolDone(false),
              craftResearched(false),
              infArmorLevel(0), arcArmorLevel(0),
              armorPendingKind(0), armorPendingFrame(-999999), prevStockProject(0),
              armorStockSN(-1),
              bronzeTowerUpgraded(false),
              scoutBuilt(false),
              rallyDR(0), rallyUR(0),
              towerTechResearched(false), towerCount(0),
              scoutFarmerSN(-1), scoutPhase(0), scoutCooldown(0),
              scoutDirsDone(0), scoutWalkTimer(0), scoutLegStartFrame(0), scoutReturnTry(0),
              scoutIssueDR(0), scoutIssueUR(0), scoutIssueFrame(-999999),
              priestIssueDR(0), priestIssueUR(0), priestIssueFrame(-999999),
              priestNearTCTry(0), priestFleeTry(0), priestMode(0), priestFleeLastX(0), priestFleeLastY(0), priestFleeLastFrame(-999999),
              priestConvSN(-1), priestConvFrame(-999999), priestSiegeApproach(0),
              priestAdvBest(1e18), priestAdvBestFrame(-999999), priestEscapeStage(0),
              priestEscapeCd(0), priestEscapeSide(1)
    { }

private:
    void processData() override;           // 引擎入口：跑完一帧业务后调用 commitInstruction()
    void processFrame();                   // 业务主体

    // 隐藏基类 5 个指令入口（机理见 .cpp 同名区块）：
    //   instruction 的构造函数执行 `self = g_Object[SN]`，而 g_Object 是全局 std::map 且零锁保护；
    //   std::map::operator[] 在 key 不存在时会插入节点并旋转红黑树（结构性写），与主线程对 g_Object
    //   的写并发 ⇒ 树被写坏。本组方法转发前用 g_Object.find() 只读确认 SN 存在 ⇒ 引擎构造里的
    //   g_Object[key] 必然命中已有键 ⇒ 退化为纯查找、不再改结构。
    //   基类这 5 个都是非虚 public 函数 ⇒ 派生类同名声明即隐藏，可覆盖 AI 侧全部调用。
    int HumanMove(int SN, double DR0, double UR0);           // 令单位 SN 移动到 (DR0,UR0)
    int HumanAction(int SN, int obSN);                       // 令单位 SN 对目标 obSN 执行动作（攻击/采集等）
    int HumanBuild(int SN, int BuildingNum, int BlockDR, int BlockUR);   // 令村民 SN 在指定区块建造指定建筑
    int BuildingAction(int SN, int Action);                  // 对建筑 SN 执行动作（生产/研究等）
    int PinPointStrike(int SN, double DR0, double UR0);      // 令单位 SN 对坐标 (DR0,UR0) 定点打击

    // 建筑 type 的占地边长（块数）
    static int buildingFootprintSize(int type);
    // 两矩形足迹是否相交
    static bool footprintsOverlap(int ax, int ay, int aw, int ah,
                                 int bx, int by, int bw, int bh);
    // 块矩形是否在地图边界内
    static bool inBounds(int blockDR, int blockUR, int size);
    // 细节坐标 (x,y) 是否可走（含森林栅格）
    bool isPassableAt(double x, double y, const std::vector<std::vector<char>>& forestGrid) const;
    // 查敌方单位 SN 的位置/近战/兵种，命中返回 true
    bool lookupEnemySN(int sn, double &x, double &y, bool *pMelee = nullptr, int *pSort = nullptr) const;
    // 为"打-拉"选目标，输出其兵种与需跳过的档位
    int findKiteTarget(int selfSort, double dr, double ur, double range, int &osort, int &skipSort) const;
    // 把该点吸附到最近的可走块
    void snapWalkable(double &x, double &y, const std::vector<std::vector<char>>& forestGrid) const;
    // 块矩形是否与给定建筑重叠
    bool isBlockedByBuildings(int blockDR, int blockUR, int size,
                              const std::vector<tagBuilding>& buildings) const;
    // 块矩形是否与给定资源重叠
    bool isBlockedByResources(int blockDR, int blockUR, int size,
                              const std::vector<tagResource>& resources) const;
    // 统计建筑数（是否含未回写、已死、在建）
    int countBuildings(int type, bool includePending, bool includeDead,
bool countUnderConstruction);



    // 追加一条指令到 UsrIns 队列，分配自增 id 并返回（加锁保护）
int AddToIns(instruction ins) override {
        UsrIns.lock.lock();
        ins.id = UsrIns.g_id;
        UsrIns.g_id++;
        UsrIns.instructions.push(ins);
        UsrIns.lock.unlock();
        return ins.id;
    }

    // 清空引擎侧的本帧指令返回缓冲
    void clearInsRet() override {
        tagUsrGame.clearInsRet();
    }

        // 用户策略代码区


    // 状态机
    enum State {
        INIT,            // 0: 初始化
        EARLY_ECONOMY,   // 1: 早期经济发展
        UPGRADING,       // 2: 升级铜器时代中
        DEFENSE_PREP,    // 3: 防御准备（波次间）
        DEFENSE_WAVE1,   // 4: 第一波
        DEFENSE_WAVE2,   // 5: 第二波
        DEFENSE_WAVE3,   // 6: 第三波
        COUNTERATTACK,   // 7: 反攻
        VICTORY,         // 8: 胜利
        DEFEAT           // 9: 失败
    } state;

    // 关键对象 SN（每帧通过扫描列表更新，不缓存！）
    int townCenterSN;
    int priestSN;
    int enemySiegeSN;
    bool enemyBaseScouted;        // 敌方基地已被探到过（持久化：一旦探明即便暂失视野也记得方位）
    double enemyBaseDR, enemyBaseUR;  // 已探明敌方基地坐标(区块中心→细节坐标)，供反攻直奔
    bool hasUpgraded;
    // 铜器升级防卡死状态（引擎有"工具时代需市场/靶场/马厩≥2座"硬前置）
    int bronzeIssuedFrame;        // 最近一次铜器升级发令帧
    int bronzeAttemptCount;       // 累计发令次数
    int bronzeStallFrames;        // UPGRADING 中连续"引擎未确认施工"的帧数（超时兜底基准）
    bool wave1Started, wave2Started, wave3Started;
    bool wave2Defeated;

    // 指令节流冷却
    int buildCooldown;
    int techCooldown;
    int trainCooldown;
    int debugTimer;

    // 建造追踪
    std::set<int> triedBuildPositions;
    std::map<int,int> buildingFarmerType;
    std::map<int,int> builderIdleFrame; // 建造者空闲且不匹配任何在建建筑的起始帧（累计空闲时间，重派不重置）
    std::map<int,int> buildRedispatchFrame; // 建造者空闲时重新下发建造指令的节流帧（每60帧一次）
    std::set<int> releasedBuilders;   // 本帧刚完成建造/释放的村民，允许跳过 IDLE 限制立即重新分配
    std::map<int,int> gatherStuckFrame;   // 村民SN → 空手且非空闲的起始帧（寻路卡死检测）
    std::map<int,int> stuckResourceUntil; // 资源SN → 拉黑截止帧（判定不可达，暂不派）
    std::map<int,int> villLastResourceSN; // 村民SN → 最近一次被派去的目标SN（树/浆果/瞪羚/金/石/大象/农场；STUCK时WorkObjectSN已清零，兜底拉黑用）
    std::set<int> pendingRedispatch;      // 卡死待重派村民SN（detectStuckGatherers 注入 → assignIdleSimple 无视 IDLE 优先重派一次）
    std::map<int, std::pair<int,int>> pendingBuildIns; // 建造指令id → {建造者SN, 建筑类型}
    std::map<int,int> pendingBuildInsFrame; // 建造指令id → 下发帧号（结果迟迟不回时超时清理，避免永久占位）
    std::map<int,int> deadBuildingsFrame;   // 废弃地基SN → 拉黑帧号（宽限期内仍计入"已存在"，超时才允许另建）
    std::map<int,int> orphanBuildFrame;     // 孤儿地基SN → 上次补派村民的帧号（重派节流）
    std::map<int,int> builderDispatchFrame; // 建造者SN → 最近一次建造令下发帧（硬超时起点；重派不重置）
    std::map<int,int> lastBuildIssueFrame;  // 建筑类型 → 最近一次下发建造指令的帧号（防异步回写窗口内重复建造）
    // 最近 N 次【仓库】建造令的落点（块坐标）+ 下发帧。
    //   唯一用途 = 喂 stockOrderPending()：窗口内把"距落点 ≤20 块"的瞪羚判为该群刚下过令 ⇒ 不再重复下单。
    //   为什么必须自己记：tryBuild 成功 ≠ 仓库出现在 infoPtr->buildings（村民在路上时连地基都没有），
    //   而 isFarGazelle 的锚点只能看 infoPtr->buildings ⇒ 不看落点就一定漏。
    //   ⚠ 三只数组严格同下标（平行数组一旦被 sort/去重就错位）；此处只 push_back + 裁头，绝不排序。
    std::vector<int> stockOrderDR;      // 落点块 DR
    std::vector<int> stockOrderUR;      // 落点块 UR
    std::vector<int> stockOrderFrame;   // 落点下发帧（窗口 STOCK_ORDER_SETTLE 到期即自动失效 ⇒ 静默失败可重发）
    // 金矿仓库的【已下单数】= 独立预算的计数器。
    //   为什么不判"距金矿 ≤20 块的仓库数"：剧本预置首仓距最近的近距金矿格只有 19.4 块，
    //   用邻近判据等于闸门自锁、金矿仓永远建不出。
    //   为什么不用 MAX_STOCK：stock 常吃满 4，共用预算时瞪羚先吃光、金矿排不上队。
    int goldStockOrders = 0;            // 金矿仓库已成功下单数（上限 MAX_GOLD_STOCK，不占用 MAX_STOCK 预算）
    std::set<int> deadBuildings;      // 卡在0%的废弃地基SN（超时后忽略，避免阻塞后续建造）
    std::set<int> depositFarmers;
    std::map<int,int> depositStartFrame;
    int farmTarget;          // 目标农场数量
    int storageNearGazelleBuilt; // 瞪羚群中心仓库是否已建（0=未建，每局仅建1座）

    // 祭司移动防抖（防止HumanMove死循环）
    int priestMoveCooldown;
    // 反攻推进专用防抖（与 priestMoveCooldown 解耦）：防止 managePriest 的感化/治疗
    //   节流把反攻段的"跟随大军推进"饿死——否则祭司感化一次就被锁 150 帧、永不在反攻时跟进。
    int priestCounterCooldown;

    // 科技追踪（避免重复下达科技指令）
    bool wheelResearched;
    bool broadswordResearched;
    bool broadswordQueued;         // 阔剑已排队（防重复发指令，不等同已研究）
    bool wheelQueued;              // 车轮已排队（主远程兵种解锁科技）
    bool marketFarmUpgraded;
    bool marketWoodUpgraded;       // 市场·木材加工已研究
    bool marketPlowUpgraded;
    bool useToolDone;
    bool craftResearched;          // 工艺科技（铜器木材加工）
    int  infArmorLevel;            // 步兵护甲链：0=未研 1=护甲已研 2=鳞甲已研（级数=引擎已受理的发令数）
    int  arcArmorLevel;            // 弓兵护甲链：0=未研 1=护甲已研 2=鳞甲已研
    int  armorPendingKind;         // 待确认发令：0=无 1=步兵链 2=弓兵链（下帧用 Project 确认受理，超时回滚重试）
    int  armorPendingFrame;        // 待确认发令的帧号
    int  prevStockProject;         // 上一帧仓库 Project（观测"仓库科技完成"边沿，用于验证）
    int  armorStockSN;             // 锁定用于研究护甲的仓库 SN（多仓库下 findBuilding 会跨帧返回不同仓库）
    bool bronzeTowerUpgraded;      // 铜器箭塔升级

    // 新增：完整版策略变量
    bool scoutBuilt;           // 侦察骑兵已生产
    int rallyDR, rallyUR;      // 反攻集结点
    bool towerTechResearched;  // 箭塔科技已研究
    int towerCount;            // 已建箭塔数量
    int scoutFarmerSN;         // 探路村民SN（探路由祭司承担，见 scoutPhase）
    int scoutPhase;            // 探路阶段：<16=探路中（本阶段驱动祭司）；>=20=已结束（战时 processData 强推 20，交还 managePriest）
    int scoutCooldown;         // 探路移动冷却
    int scoutDirsDone;         // 已完成的外向探索次数（探完8方向=8 才结束探路）
    int scoutWalkTimer;        // 走路计时（超时=目标不可达）
    int scoutLegStartFrame;    // 当前探路腿开始的帧号（超时跳过方向，防卡死）
    int scoutReturnTry;        // 返回TC被石头堵时，多半径×多角度螺旋重试绕路的计数(0~23)
    double scoutIssueDR, scoutIssueUR;  // 上次给祭司下发移动指令时的位置（检测"下指令但没动"）
    int scoutIssueFrame;                // 上次给祭司下发移动指令的帧号
    double priestIssueDR, priestIssueUR;// 上次给祭司下发回TC指令时的位置（managePriest防抖）
    int priestIssueFrame;               // 上次给祭司下发回TC指令的帧号
    int priestNearTCTry;               // 待机守TC旁：多半径×多角度螺旋重试绕路的计数(0~23)
    int priestFleeTry;                 // 逃跑螺旋重试计数(0~20)：卡死时换角度/半径重试防卡
    int priestMode;                    // 祭司决策锁：0=常态/感化, 1=撤退中(迟滞用，逃到脱离威胁才解除)
    double priestFleeLastX, priestFleeLastY; // 上次下发的逃跑落点（判断引擎是否拒收该点→祭司原地不动）
    int priestFleeLastFrame;           // 上次下发逃跑指令的帧号
    int priestConvSN;                  // 上次下发感化的目标SN（引导跟踪：拒收检测/防打断重发）
    int priestConvFrame;               // 上次下发感化指令的帧号
    // 前出感化武器厂【迟滞锁】：0=关, 1=正在前出感化。
    //   背景：allowConvertSiege 由 localClear(周边无敌军) 决定，而祭司一靠近武器厂，
    //   守在厂旁的敌人就进半径 ⇒ 判据逐帧翻转 ⇒ 祭司在【前出】与【后撤】间抖动、
    //   净位移≈0，永远够不到 12 格感化射程。
    //   修：一旦成立就锁定，除非【真贴身(<=PRIEST_SIEGE_ABORT_R)】或【血量过低】才解除。
    int priestSiegeApproach;
    // 祭司推进脱困：脱困动作【绝不算进展】—— priestAdvBest 只在"真正逼近武器厂"时降低，
    //   priestEscapeStage 也只有真进展才归零；否则自救会自我抵消（同 issueMarch 退让活锁的病根）。
    double priestAdvBest;      // 到武器厂记忆点的历史最近距离（推进进展判据真源）
    int priestAdvBestFrame;    // 最后一次"真进展"的帧号
    int priestEscapeStage;     // 脱困档位：0=无 / 1=侧移绕开堵点 / 2=清障(挪开贴脸友军)
    int priestEscapeCd;        // 脱困动作后的冷却帧（防每帧重发）
    int priestEscapeSide;      // 侧移方向交替（+1/-1），避免总往同一边撞
    // 军事单位回TC旁待命的绕路状态（与主城建筑中心不可达导致的刷屏卡死对应，刀斧兵/弓箭手等通用）
    std::map<int,int> armyReturnTry;      // 单位SN → 多半径×多角度螺旋重试计数(0~23)
    std::map<int,double> armyIssueDR, armyIssueUR; // 上次下发回TC移动指令时的位置（卡死检测）
    std::map<int,int> armyIssueFrame;     // 上次下发回TC移动指令的帧号
    // 待命指令去重：holdNearBase 无节流时，单位在向落点行军期间（WALKING）会每帧重发同一条
    //   HumanMove，且同档位多单位落点完全重合。此处记录上次下发的落点与帧号。
    std::map<int,double> armyHoldGoalDR, armyHoldGoalUR;  // 上次下发的待命落点（判"是否同一目标"）
    std::map<int,int> armyHoldCmdFrame;                   // 上次下发待命指令的帧号（重发节流窗口）
    // 村民撤退相关的绕路/指令记录（村民撤退机制当前无使用者，字段保留）
    std::map<int,int> farmerReturnTry;    // 村民SN → 螺旋重试计数
    std::map<int,double> farmerIssueDR, farmerIssueUR; // 上次下发撤退指令位置
    std::map<int,int> farmerIssueFrame;   // 上次下发撤退指令帧号
    // 反攻推进(manageCounterAttack)的寻路卡死检测。
    //   必须独立一套，不可复用上面的 armyIssue*：
    //   manageMilitary() 每帧都跑(反攻期也一样)，若共用 map，同帧内后者会覆盖前者，
    //   导致 "frame - issueFrame" 永远很小 → 卡死判定永不触发 → 单位永久卡死。
    std::map<int,int> marchStuckTry;      // 单位SN → 卡死重试档位(逐档换方向，绕出死角)
    std::map<int,double> marchIssueDR, marchIssueUR; // 单位SN → 上次下发推进指令的位置
    // 单位SN → 上次记录的"距推进目标(targetDR/targetUR)的距离"，作为卡死判据：
    //   只有【距目标真的变近】才算有效推进，原地来回抖动不刷新计时。
    std::map<int,double> marchIssueDist;
    std::map<int,int> marchMoveFrame;     // 单位SN → 上次"位置发生变化"的帧号
    std::map<int,int> marchCmdFrame;      // 单位SN → 上次下发推进指令的帧号（卡死重发节流，防每帧改方向抖动）
    // 单位SN → 上次下发【后撤】指令的帧号（专用于"后撤保护期"）。
    //   为什么不能只用 marchCmdFrame：它同时被推进/后撤/集结共用，若拿它做攻击令保护，
    //   会导致兵推进到射程内也不开火。后撤必须单独记，只有后撤才需要"撤完之前不许开火"。
    std::map<int,int> lastRetreatFrame;
    // 远程兵"打-拉"循环状态机(SHOOT/RETREAT)与起始帧。
    //   节奏：SHOOT ≥ SHOOT_FRAMES(60 帧=4 秒)后自动切 RETREAT；
    //   RETREAT 直到敌距≥R+1.5 格后再切回 SHOOT，主动制造距离窗口让敌"出射程外"再压制。
    std::map<int,int> kitingPhase;        // SN → 0=SHOOT/IDLE, 1=RETREAT
    std::map<int,int> kitingPhaseFrame;   // SN → 进入当前相位的帧号(相位内不重发指令)
    // 撤退落点"路径可达性"校验（"点可走 ≠ 路径可达"）。
    //   反攻期弓兵常在敌方基地附近，撤退落点本身可走、但被海/林/建筑隔断 →
    //   HumanMove 被引擎静默丢弃 → 弓兵原地站桩挨打。
    //   度量方式：以"与最近敌的距离 dK"为准——本撤退窗口 dK 若未比上一窗口拉开
    //   （< +0.3 格），判定该方向撤不动，累计 kitingRetStuck；下一轮跳过"远离敌"档、
    //   直接朝己方 TC 撤（TC 在开阔腹地，路径必然可达）。
    //   不用"单位是否有位移"做判据：引擎的攻击令也会驱动位移，会把"撤不动"误判成"在撤"。
    std::map<int,int>    kitingRetStuck;     // SN → 连续"发令却没拉开距离"的次数(>0 则跳过第 1 档)
    std::map<int,double> kitingRetPrevDK;    // SN → 上一个撤退窗口的 dK（本窗口据此判断是否拉开）
    // 反攻期拉扯：`HumanAction(X,目标)` 是"设置攻击目标"，每帧重设 ⇒ 引擎施法/瞄准进度永远归零。
    //   解法＝目标粘滞 + 攻击令节流：沿用上一目标，仅在"目标消失/跑出范围/新目标明显更近"时才切换。
    std::map<int,int> kitingTargetSN;   // 复合弓 SN → 粘滞目标 SN（反攻拉扯的目标锚）
    std::map<int,int> kitingAtkFrame;   // 复合弓 SN → 上次下发攻击令的帧号（节流，防每帧重发）
    // SN → 最近一次因"射程 < 箭塔射程"而放弃的敌塔 SN。
    //   仅用于日志去重（同一塔只打一条 [TOWER-SKIP]），不参与任何决策。
    std::map<int,int> towerSkipSN;
    // SN → 最近一次因"射程不占优"而放弃拉扯的【敌方兵种】。
    //   仅用于 [KIT-NO] 日志去重（同一兵同兵种只打一条），不参与任何决策。
    std::map<int,int> kiteSkipSort;
    // 【Tier-2 推进偏置】：SN → 当前正被用作"落点偏置目标"的敌塔 SN。
    //   仅用于日志去重（同一兵对同一塔只打一条 [TOWER-APPROACH]），不参与任何决策；
    //   决策依据每帧由 findNearestEnemyTower(…, TOWER_APPROACH_RANGE*BL) 现算，绝不读这张表。
    std::map<int,int> towerBiasSN;
    // 投石车 standoff/拉扯（独立表，不与弓兵共用，避免下游串味）
    std::map<int,int> catTargetSN;      // 投石车 SN → 粘滞目标 SN
    std::map<int,int> catTargetFrame;   // 投石车 SN → 上次重新评估目标的帧号（每 30 帧一次）
    std::map<int,int> catAtkFrame;      // 投石车 SN → 上次下发攻击令的帧号
    std::map<int,int> catRetreat;       // 投石车 SN → 撤退迟滞(1=正在后撤，退到 CAT_FLEE_EXIT 才解除)
    std::set<int> huntingGroup; // 正在打猎的村民SN
    std::set<int> frameFoodTargets; // 本帧已分配的食物目标SN（防同帧重复分配）
    std::map<int,int> frameBushCount; // 本帧每丛浆果已分配人数（浆果每丛≤2人，防同帧挤爆单丛）
    std::map<int,int> frameGazelleCount; // 本帧每只瞪羚已分配人数（瞪羚每只≤2人，防同帧+跨帧过度打猎）
    std::map<int,int> frameWoodCount; // 本帧每棵树分配人数（单树≤2人，防同帧挤爆+减少过渡期空闲）
    // 猎象整队：大象SN → 解禁帧。孤兵救援(召回)后短期拉黑，
    //   防止"召回→立刻又派人→再召回"的来回送死循环。
    std::map<int,int> elephantBanUntil;

    // ---- 基础辅助函数 ----
    // 找一个空闲村民（IDLE 无任务），无则 nullptr
    tagFarmer* findIdleFarmer();
    // 找任意一个村民（不限空闲）
    tagFarmer* findAnyFarmer();
    // 离指定点【最近】的空闲村民（用于远距选址建筑的建造者选取，
    //   如瞪羚群中心仓库——避免随机抽人导致村民从 TC 长途跋涉、仓库迟迟落不了地）。
    tagFarmer* findIdleFarmerNear(double dr, double ur);
    // 「先建仓库、再打猎」闸门：该瞪羚的交付仓库是否已就位（含在建/木不够/超时兜底）。
    bool gazelleDropoffReady(tagResource* r);
    int countFarmersOnTarget(int sn);   // 统计 WorkObjectSN==sn 的村民数
    // 找指定类型的已建成建筑，无则 nullptr
    tagBuilding* findBuilding(int type);
    // 找指定类型建筑（含在建），无则 nullptr
    tagBuilding* findBuildingIncludingUnderConstruction(int type);
    // 找指定类型的敌方建筑，无则 nullptr
    tagBuilding* findEnemyBuilding(int type);
    int findNearestEnemyBuilding(double dr, double ur, double range);  // 范围内最近敌方建筑SN(反攻直奔基地后拆建筑用)
    // 敌方建筑里找距 (dr,ur) 最近者。
    //   findNearestEnemyBuilding / findNearestEnemyTower / findCatapultTarget 复用同一"建筑中心距离"扫描
    //   （口径 = (BlockDR+1, BlockUR+1) × BLOCKSIDELENGTH）。
    //   bestD2 传入【当前最优距离²(像素)】并在命中时被更新 —— 便于与"单位候选"混在同一池里比较；
    //   typeFilter < 0 = 不限建筑类型，否则只看该 Type。返回 SN，无命中返回 -1。
    int nearestEnemyBuildingFrom(double dr, double ur, double &bestD2, int typeFilter);
    // 范围内【距离自己最近的敌方箭塔】SN（无则 -1）。士兵选建筑目标时优先打它。
    int findNearestEnemyTower(double dr, double ur, double range);
    int findNearestEnemyUnit(double dr, double ur, double &bestD2, bool skipStone); // findNearestEnemySN/findCatapultTarget 共用
    // 找距 (dr,ur) 最近的指定类型资源，无则 nullptr
    tagResource* findNearestResource(int type, double dr, double ur);
    tagResource* findBestWoodTree(double dr, double ur);   // 砍树按"离仓库/TC 近"选树（带硬闸）
    // 范围内距 (dr,ur) 最近的敌方单位 SN，无则 -1
    int findNearestEnemySN(double dr, double ur, double range);
    int findNearestEnemyNoStone(double dr, double ur, double range);  // 军事单位选敌：范围内最近敌人(军队优先于村民)，但排除投石车(留给祭司感化)，不做近战优先
    int findCatapultTarget(double dr, double ur, double range);  // 投石车专用选敌(反攻)：范围内最近目标=任意敌方单位(含敌投石车)+敌方箭塔建筑
    // 统计指定类型的已建成建筑数
    int countBuildings(int type);
    // 统计指定类型的建筑数（含各状态）
    int countBuildingsAll(int type);
    // "该类型是否已存在"判定（唯一建筑的存在性门槛）：统计一切实际存在的该类型建筑
    //   （含 0% 地基、被拉黑的废弃地基、已下发未回写的指令），避免"卡住的0%地基"被漏算而原地再建一座。
    int countBuildingsExisting(int type);
    // 统计全部军事单位数
    int countAllMilitary();
    // 块矩形位置是否空闲（不与建筑/资源冲突）
    bool isPositionFree(int blockDR, int blockUR, int size);
    // 同上，checkReachability=true 时额外要求可达
    bool isPositionFree(int blockDR, int blockUR, int size, bool checkReachability);
    bool isSiteReachable(int blockDR, int blockUR, int size);  // 地基可达性预检：地基旁须有路可走，避免选址被建筑围死、村民永远走不到(卡死)
    // avoidFarmAdjacent=true：额外跳过与已有农场"相邻"的位置（3x3 外扩 1 格内不得有农场）。
    //   农场兜底选址用 —— 若不检查，一旦 TC 内圈被占就会把农场紧贴着排成一片，
    //   破坏 isFarmAdjacent 的"隔 1 格"设计。
    bool findBuildSite(int &x, int &y, int size = 2, bool avoidFarmAdjacent = false);
    bool findBuildSiteTowardCenter(int &x, int &y, int size, int minR, int maxR);  // 建筑选址偏向 TC→地图中心方向且离TC更远(避免堵角)
    // 选防御建筑（箭塔等）的选址
    bool findDefenseBuildSite(int &x, int &y, int size = 2);
    // 选谷仓的选址
    bool findGranarySite(int &x, int &y);
    // 远距浆果群定位（第二座谷仓专用）：找到距 TC ≥ SECOND_GRANARY_TC_MIN_DIST、距任一已有谷仓 >12 格、
    // 且 5 格内丛数 ≥ MIN_BUSH_FOR_SECOND_GRANARY 的最密集浆果群，输出其块坐标与丛数。
    bool findRemoteBushCluster(int &bx, int &by, int &outCnt);
    // 选市场的选址
    bool findMarketSite(int &x, int &y);
    // 选房屋的选址
    bool findHouseSite(int &x, int &y);
    // 农场布局：统一锚点候选 + 评分择优 —— 锚点 = TC + 全部已建成谷仓(GRANARY)/仓库(STOCK)，
    //   在 [FARM_ANCHOR_R_MIN, FARM_ANCHOR_R_MAX] 环上枚举空位，评分 = 到 TC 的距离
    //   （不用"到最近锚点"：该口径会让农场飞到远处的谷仓旁）。
    bool findFarmSiteBest(int &x, int &y);
    bool isFarmAdjacent(int blockDR, int blockUR);  // 农场不相邻：候选农场外扩1格内不得有其他农场(至少隔1格)
    // noFallback=true：指定 prefX/prefY 但周边放不下时【直接失败】，不再回退到默认选址
    //   （用于"必须建在某片资源旁"的场景，否则回退可能建到完全无关的位置）
    // preferNearBuilder=true：优先派【离 prefX/prefY 最近】的空闲村民当建造者（默认 false=按默认选取）
    bool tryBuild(int buildingType, int size, bool ignoreCooldown = false, int prefX = -1, int prefY = -1,
                  bool noFallback = false, bool preferNearBuilder = false);
    void handleBuildResults();        // 处理建造指令执行结果（失败换位置重试）
    void detectStuckGatherers();      // 检测寻路卡死的采集村民，强制打断并拉黑目标资源

    // ---- 资源采集辅助 ----
    // 尝试给该村民分配一个食物采集目标
    bool tryAssignFood(tagFarmer* f);

    // ---- 核心策略函数 ----
    void updateState();            // 阶段切换
    // 铜器升级统一入口（含引擎前置检查+幂等）；返回 true = 本帧确实发出了升级令
    int  countAgeUpgradeBuildings();   // 市场/靶场/马厩 已存在数（引擎升级硬前置）
    // 尝试发起铜器升级（含引擎前置检查+幂等）
    bool tryStartBronzeUpgrade();
    void manageEconomy();          // 经济（农民生产+分配+科技）
    void manageBuildings();        // 建造管理
    // 更新目标农场数量
    void updateFarmTarget();
    // 祭司探路管理
    void managePriestScout();
    // 统计各类资源（金/木/石/食物）的村民数
    void countFarmerWorkKinds(int &goldWorkers, int &woodWorkers, int &stoneWorkers, int &foodWorkers) const;
    void assignIdleFarmers();      // 空闲村民分配
    void assignIdleSimple();       // 最后兜底：无视复杂标记，派所有空闲村民到最近资源
    void manageTechUpgrade();      // 科技升级
    void managePriest();           // 祭司管理（最高优先级）
    void manageMilitary();         // military training and combat
    // 训练军事单位（按是否战时区分）
    void trainMilitaryUnits(bool isWarTime);
    // 管理携带资源村民的交付
    void manageCarriedResources();
    void manageCounterAttack();    // 反攻
    // 反攻期指挥村民协同进攻
    void counterFarmerAttack(double BL, double targetDR, double targetUR);
    // 反攻期祭司护卫，返回是否已处理
    bool counterPriestGuard(double BL);
    // 反攻期祭司前出感化敌方武器厂
    void counterPriestConvert(double BL, double targetDR, double targetUR,
                              double rallyCtrDR, double rallyCtrUR,
                              const std::vector<std::vector<char>>& forestGrid);
    // 反攻期祭司探路并规划推进目标
    bool counterScoutAndPlan(double BL, double &targetDR, double &targetUR,
                            const std::vector<std::vector<char>>& forestGrid);
    void manageHunting();          // 打猎模块
    void checkDefeat();            // 失败检查
    void doDebugOutput();          // 调试输出
};

#endif // USRAI_H
