#ifndef USRAI_H
#define USRAI_H

#include "ai.h"
#include <set>
#include <map>
#include <vector>
#include <algorithm>
#include <cmath>

extern tagGame tagUsrGame;
extern ins UsrIns;

class UsrAI : public AI
{
public:
    UsrAI() : frame(0), state(INIT), townCenterSN(-1), priestSN(-1),
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
              wheelResearched(false), broadswordResearched(false),
              compositeBowResearched(false),
              broadswordQueued(false), compositeBowQueued(false),
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
              priestConvSN(-1), priestConvFrame(-999999), priestSiegeApproach(0)
    { this->id = 0; }
    ~UsrAI() {}

private:
    void processData() override;

    static int buildingFootprintSize(int type);
    static bool footprintsOverlap(int ax, int ay, int aw, int ah,
                                 int bx, int by, int bw, int bh);
    static bool inBounds(int blockDR, int blockUR, int size);
    bool isBlockedByBuildings(int blockDR, int blockUR, int size,
                              const std::vector<tagBuilding>& buildings) const;
    bool isBlockedByResources(int blockDR, int blockUR, int size,
                              const std::vector<tagResource>& resources) const;
    int countBuildings(int type, bool includePending, bool includeDead,
                       bool countUnderConstruction);

    tagInfo getInfo() {
        return tagUsrGame.getInfo();
    }

    int AddToIns(instruction ins) override {
        UsrIns.lock.lock();
        ins.id = UsrIns.g_id;
        UsrIns.g_id++;
        UsrIns.instructions.push(ins);
        UsrIns.lock.unlock();
        return ins.id;
    }

    void clearInsRet() override {
        tagUsrGame.clearInsRet();
    }

    // ==================== 用户策略代码区 ====================

    // 当前游戏状态（每帧刷新！注意列表顺序每帧随机打乱）
    tagInfo info;
    int frame;

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
    bool enemyBaseScouted;        // ★ 敌方基地已被探到过(持久化：一旦探明即便暂失视野也记得方位)
    double enemyBaseDR, enemyBaseUR;  // 已探明敌方基地坐标(区块中心→细节坐标)，供反攻直奔
    bool hasUpgraded;
    // ★★ 2026-09-13 铜器升级防卡死状态（引擎有"工具时代需市场/靶场/马厩≥2座"硬前置）
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
    std::set<int> waveBlockers;
    std::map<int,int> buildingFarmerType;
    std::map<int,int> builderIdleFrame; // 建造者空闲且不匹配任何在建建筑的起始帧（累计空闲时间，重派不重置）
    std::map<int,int> buildRedispatchFrame; // 建造者空闲时重新下发建造指令的节流帧（每60帧一次）
    std::set<int> releasedBuilders;   // 本帧刚完成建造/释放的村民，允许跳过 IDLE 限制立即重新分配
    std::map<int,int> gatherStuckFrame;   // 村民SN → 空手且非空闲的起始帧（寻路卡死检测）
    std::map<int,int> stuckResourceUntil; // 资源SN → 拉黑截止帧（判定不可达，暂不派）
    std::map<int,int> villLastTreeSN;     // 村民SN → 最近一次被派去的树SN（STUCK时WorkObjectSN已清零，兜底拉黑用）
    std::map<int, std::pair<int,int>> pendingBuildIns; // 建造指令id → {建造者SN, 建筑类型}
    std::map<int,int> pendingBuildInsFrame; // 建造指令id → 下发帧号（结果迟迟不回时超时清理，避免永久占位）
    std::map<int,int> deadBuildingsFrame;   // 废弃地基SN → 拉黑帧号（宽限期内仍计入"已存在"，超时才允许另建）
    std::map<int,int> orphanBuildFrame;     // 孤儿地基SN → 上次补派村民的帧号（重派节流）
    std::map<int,int> builderDispatchFrame; // ★ 建造者SN → 本次建造令下发帧（硬超时起点；重派不重置）
    std::map<int,int> lastBuildIssueFrame;  // 建筑类型 → 最近一次下发建造指令的帧号（防异步回写窗口内重复建造）
    // ★★★ 2026-09-22「避免一个瞪羚群附近重复建 2 个仓库」：最近 N 次【仓库】建造令的落点（块坐标）+ 下发帧。
    //   唯一用途 = 喂 stockOrderPending()：窗口内把"距落点 ≤20 块"的瞪羚判为该群刚下过令 ⇒ 不再重复下单。
    //   为什么必须自己记：tryBuild 成功 ≠ 仓库出现在 info.buildings（村民在路上时连地基都没有），
    //   而 isFarGazelle 的锚点只能看 info.buildings ⇒ 不看落点就一定漏。
    //   ⚠ 三只数组严格同下标（平行数组一旦被 sort/去重就错位）；此处只 push_back + 裁头，绝不排序。
    std::vector<int> stockOrderDR;      // 落点块 DR
    std::vector<int> stockOrderUR;      // 落点块 UR
    std::vector<int> stockOrderFrame;   // 落点下发帧（窗口 STOCK_ORDER_SETTLE 到期即自动失效 ⇒ 静默失败可重发）
    // ★★★ 2026-09-22「金矿旁边没有仓库的话也要建仓库」：金矿仓库的【已下单数】= 独立预算的计数器。
    //   为什么不判"距金矿 ≤20 块的仓库数"：剧本预置首仓在 (13,34)，距最近的近距金矿格只有 19.4 块
    //   （实测 gst 批 3/3 局开局即 1）⇒ 用邻近判据等于闸门自锁、金矿仓永远建不出。
    //   为什么不用 MAX_STOCK：全库 764 局 stock 吃满 4 的占 73.6% ⇒ 共用预算时瞪羚先吃光、金矿排不上队。
    int goldStockOrders = 0;            // 金矿仓库已成功下单数（上限 MAX_GOLD_STOCK，不占用 MAX_STOCK 预算）
    std::set<int> deadBuildings;      // 卡在0%的废弃地基SN（超时后忽略，避免阻塞后续建造）
    std::set<int> depositFarmers;
    std::map<int,int> depositStartFrame;
    int farmTarget;          // 目标农场数量
    int storageNearGazelleBuilt; // 瞪羚群中心仓库是否已建（0=未建，每局仅建1座）

    // 祭司移动防抖（防止HumanMove死循环）
    int priestMoveCooldown;
    // ★ 反攻推进专用防抖（与 priestMoveCooldown 解耦）：防止 managePriest 的感化/治疗
    //   节流把反攻段的"跟随大军推进"饿死——否则祭司感化一次就被锁 150 帧、永不在反攻时跟进。
    int priestCounterCooldown;

    // 科技追踪（避免重复下达科技指令）
    bool wheelResearched;
    bool broadswordResearched;
    bool compositeBowResearched;
    bool broadswordQueued;         // 阔剑已排队（防重复发指令，不等同已研究）
    bool compositeBowQueued;       // 复合弓已排队
    bool marketFarmUpgraded;
    bool marketWoodUpgraded;       // 市场·木材加工（2026-09-06 补：此前漏了幂等标志位，会重复研究扣资源）
    bool marketPlowUpgraded;
    bool useToolDone;
    bool craftResearched;          // 工艺科技（铜器木材加工）
    int  infArmorLevel;            // 步兵护甲链：0=未研 1=护甲已研 2=鳞甲已研（级数=引擎已受理的发令数）
    int  arcArmorLevel;            // 弓兵护甲链：0=未研 1=护甲已研 2=鳞甲已研
    int  armorPendingKind;         // 待确认发令：0=无 1=步兵链 2=弓兵链（下帧用 Project 确认受理，超时回滚重试）
    int  armorPendingFrame;        // 待确认发令的帧号
    int  prevStockProject;         // 上一帧仓库 Project（观测"仓库科技完成"边沿，用于验证）
    int  armorStockSN;             // ★ 锁定用于研究护甲的仓库 SN（多仓库下 findBuilding 会跨帧返回不同仓库）
    bool bronzeTowerUpgraded;      // 铜器箭塔升级

    // 新增：完整版策略变量
    bool scoutBuilt;           // 侦察骑兵已生产
    int rallyDR, rallyUR;      // 反攻集结点
    bool towerTechResearched;  // 箭塔科技已研究
    int towerCount;            // 已建箭塔数量
    int scoutFarmerSN;         // 探路村民SN
    int scoutPhase;            // 0-7: 4方向+回TC交替
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
    // ★ 2026-09-14 前出感化武器厂【迟滞锁】：0=关, 1=正在前出感化
    //   背景：allowConvertSiege 由 localClear(周边无敌军) 决定，而祭司一靠近武器厂，
    //   守在厂旁的敌人就进半径 ⇒ 判据逐帧翻转 ⇒ 祭司在【前出】与【后撤】间抖动、
    //   净位移≈0，永远够不到 12 格感化射程（ll5 f=44531~44981 实测落点每 30 帧翻转）。
    //   修：一旦成立就锁定，除非【真贴身(<=PRIEST_SIEGE_ABORT_R)】或【血量过低】才解除。
    int priestSiegeApproach;
    // ★ 军事单位回TC旁待命的绕路状态（与主城建筑中心不可达导致的刷屏卡死对应，刀斧兵/弓箭手等通用）★
    std::map<int,int> armyReturnTry;      // 单位SN → 多半径×多角度螺旋重试计数(0~23)
    std::map<int,double> armyIssueDR, armyIssueUR; // 上次下发回TC移动指令时的位置（卡死检测）
    std::map<int,int> armyIssueFrame;     // 上次下发回TC移动指令的帧号
    // ★ 2026-09-17 待命指令去重（用户：「避免刷屏」+「停驻集结时不要站在同一点」）：
    //   原 holdNearBase 无任何节流 ⇒ 单位在向落点行军期间（WALKING）每帧重发同一条 HumanMove，
    //   实测单局重复日志 577~1349 条、且同档位多单位落点完全重合。此处记录上次下发的落点与帧号。
    std::map<int,double> armyHoldGoalDR, armyHoldGoalUR;  // 上次下发的待命落点（判"是否同一目标"）
    std::map<int,int> armyHoldCmdFrame;                   // 上次下发待命指令的帧号（重发节流窗口）
    // ★ 村民撤退TC旁的绕路状态（与军队同理：TC建筑中心不可达→改环上可达空地，防刷屏卡死）★
    std::map<int,int> farmerReturnTry;    // 村民SN → 螺旋重试计数
    std::map<int,double> farmerIssueDR, farmerIssueUR; // 上次下发撤退指令位置（卡死检测）
    std::map<int,int> farmerIssueFrame;   // 上次下发撤退指令帧号
    // ★ 反攻推进(manageCounterAttack)的寻路卡死检测 ★
    // ⚠ 必须独立一套，绝不可复用上面的 armyIssue*：
    //   processData 中 manageMilitary() 每帧都跑(反攻期也一样)，若共用 map，同帧内后者会覆盖前者，
    //   导致 "frame - issueFrame" 永远很小 → 卡死判定永不触发 → 单位永久卡死。
    std::map<int,int> marchStuckTry;      // 单位SN → 卡死重试档位(逐档换方向，绕出死角)
    std::map<int,double> marchIssueDR, marchIssueUR; // 上次记录的位置（判定是否真的有位移）
    // ★ 2026-09-07：单位SN → 上次记录的"距推进目标(targetDR/targetUR)的距离"。
    //   卡死判据已由此字段接管（取代 marchIssueDR/UR 的"绝对位移"判据）——
    //   只有【距目标真的变近】才算有效推进，原地来回抖动不再刷新计时。
    //   详见 manageCounterAttack() 内卡死检测处的注释。
    std::map<int,double> marchIssueDist;
    std::map<int,int> marchMoveFrame;     // 单位SN → 上次"位置发生变化"的帧号
    std::map<int,int> marchCmdFrame;      // 单位SN → 上次下发推进指令的帧号（卡死重发节流，防每帧改方向抖动）
    // 单位SN → 上次下发【后撤】指令的帧号（2026-09-06：专用于"后撤保护期"）。
    // ★ 为什么不能只用 marchCmdFrame：它同时被推进/后撤/集结共用，若拿它做攻击令保护，
    //   会导致兵推进到射程内也不开火。后撤必须单独记，只有后撤才需要"撤完之前不许开火"。
    std::map<int,int> lastRetreatFrame;
    // ★ 2026-09-08 加：远程兵"打-拉"循环状态机(SHOOT/RETREAT)与起始帧
    //   主动拉撤节奏：SHOOT ≥ SHOOT_FRAMES(60 帧=4 秒)后自动切 RETREAT；
    //   RETREAT 直到敌距≥R+1.5 格后再切回 SHOOT。
    //   替代旧版"贴脸才撤(被动)"模式——新模式主动制造距离窗口，让敌"出射程外"再压制。
    std::map<int,int> kitingPhase;        // SN → 0=SHOOT/IDLE, 1=RETREAT
    std::map<int,int> kitingPhaseFrame;   // SN → 进入当前相位的帧号(相位内不重发指令)
    // ★ 2026-09-13 加：撤退落点"路径可达性"校验（"点可走 ≠ 路径可达"）。
    //   反攻期弓兵常在敌方基地附近，撤退落点本身可走、但被海/林/建筑隔断 →
    //   HumanMove 被引擎静默丢弃 → 弓兵原地站桩挨打。
    //   度量方式：以"与最近敌的距离 dK"为准——本撤退窗口 dK 若未比上一窗口拉开
    //   （< +0.3 格），判定该方向撤不动，累计 kitingRetStuck；下一轮跳过"远离敌"档、
    //   直接朝己方 TC 撤（TC 在开阔腹地，路径必然可达）。
    //   ⚠ 不用"单位是否有位移"做判据：引擎的攻击令也会驱动位移，会把"撤不动"误判成"在撤"
    //     （实测 run1：20 次撤退令全被丢弃、单位零撤退位移，位移判据却始终清零）。
    std::map<int,int>    kitingRetStuck;     // SN → 连续"发令却没拉开距离"的次数(>0 则跳过第 1 档)
    std::map<int,double> kitingRetPrevDK;    // SN → 上一个撤退窗口的 dK（本窗口据此判断是否拉开）
    // ★★★★★ 2026-09-14「反攻期拉扯必须成功」（用户需求）★★★★★
    //   实测铁证（ln1/ln7 反攻窗口 f≥33000）：
    //     • 复合弓：HumanAction 共 6827 条 / 目标在 22 个敌之间跳变 ⇒ 每帧换目标；
    //     • 投石车：586 条攻击令 / 13 个目标，引擎每 1~3 帧记一条"开始向X攻击" ⇒ 零命中；
    //   机制：`HumanAction(X,目标)` 是"设置攻击目标"，每帧重设 ⇒ 引擎施法/瞄准进度永远归零
    //        （铁律 14 的同一陷阱，祭司感化武器厂那次已踩过）。
    //   解法＝目标粘滞 + 攻击令节流：沿用旧目标，仅在"目标消失/跑出范围/新目标明显更近"时才切换。
    std::map<int,int> kitingTargetSN;   // 复合弓 SN → 粘滞目标 SN（反攻拉扯的目标锚）
    std::map<int,int> kitingAtkFrame;   // 复合弓 SN → 上次下发攻击令的帧号（节流，防每帧重发）
    // ★ 2026-09-15「复合弓兵不要拉扯箭塔」：SN → 最近一次因"射程 < 箭塔射程"而放弃的敌塔 SN。
    //   仅用于日志去重（同一塔只打一条 [TOWER-SKIP]），不参与任何决策。
    std::map<int,int> towerSkipSN;
    // ★ 2026-09-21「复合弓兵不要拉扯战车弓兵和投石车」：SN → 最近一次因"射程不占优"而放弃拉扯的【敌方兵种】。
    //   仅用于 [KIT-NO] 日志去重（同一兵同兵种只打一条），不参与任何决策。
    std::map<int,int> kiteSkipSort;
    // ★ 2026-09-20 方案 B【Tier-2 推进偏置】：SN → 当前正被用作"落点偏置目标"的敌塔 SN。
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
    std::map<int,int> lionHunterSN;    // ★ 猎狮任务：单位SN → 目标狮子SN（期间不再重复下令、不被采集模块抢走）
    std::map<int,int> lionHunterExpire; // ★ 猎狮任务：单位SN → 任务保底到期帧（到期或狮死/单位空闲即释放）
    // ★ 2026-09-13 猎象整队：大象SN → 解禁帧。孤兵救援(召回)后短期拉黑，
    //   防止"召回→立刻又派人→再召回"的来回送死循环。
    std::map<int,int> elephantBanUntil;

    // ---- 基础辅助函数 ----
    tagFarmer* findIdleFarmer();
    tagFarmer* findAnyFarmer();
    // ★ 2026-09-12：离指定点【最近】的空闲村民（用于远距选址建筑的建造者选取，
    //   如瞪羚群中心仓库——避免随机抽人导致村民从 TC 长途跋涉、仓库迟迟落不了地）。
    tagFarmer* findIdleFarmerNear(double dr, double ur);
    // ★ 2026-09-12「先建仓库、再打猎」闸门：该瞪羚的交付仓库是否已就位（含在建/木不够/超时兜底）。
    bool gazelleDropoffReady(tagResource* r);
    tagBuilding* findBuilding(int type);
    tagBuilding* findBuildingIncludingUnderConstruction(int type);
    tagBuilding* findEnemyBuilding(int type);
    int findNearestEnemyBuilding(double dr, double ur, double range);  // 范围内最近敌方建筑SN(反攻直奔基地后拆建筑用)
    // ★ 2026-09-15 去重：敌方建筑里找距 (dr,ur) 最近者。
    //   findNearestEnemyBuilding / findNearestEnemyTower / findCatapultTarget 三者原先各抄一份
    //   同样的"建筑中心距离"扫描（口径 = (BlockDR+1, BlockUR+1) × BLOCKSIDELENGTH），改一处易漏两处。
    //   bestD2 传入【当前最优距离²(像素)】并在命中时被更新 —— 便于与"单位候选"混在同一池里比较；
    //   typeFilter < 0 = 不限建筑类型，否则只看该 Type。返回 SN，无命中返回 -1。
    int nearestEnemyBuildingFrom(double dr, double ur, double &bestD2, int typeFilter);
    // ★ 2026-09-13：范围内【距离自己最近的敌方箭塔】SN（无则 -1）。士兵选建筑目标时优先打它。
    int findNearestEnemyTower(double dr, double ur, double range);
    tagResource* findNearestResource(int type, double dr, double ur);
    tagResource* findBestWoodTree(double dr, double ur);   // ★ 2026-09-06：砍树按"离仓库/TC 近"选树（带硬闸）
    int findNearestEnemySN(double dr, double ur, double range);
    int findNearestEnemyNoStone(double dr, double ur, double range);  // 军事单位选敌：范围内最近敌人(军队优先于村民)，但排除投石车(留给祭司感化)，不做近战优先
    int findCatapultTarget(double dr, double ur, double range);  // 投石车专用选敌(反攻)：范围内最近目标=任意敌方单位(含敌投石车)+敌方箭塔建筑
    int countBuildings(int type);
    int countBuildingsAll(int type);
    // ★ "该类型是否已存在"判定（唯一建筑的存在性门槛）：统计一切实际存在的该类型建筑
    //   （含 0% 地基、被拉黑的废弃地基、已下发未回写的指令），避免"卡住的0%地基"被漏算而原地再建一座。
    int countBuildingsExisting(int type);
    int countAllMilitary();
    bool isPositionFree(int blockDR, int blockUR, int size);
    bool isSiteReachable(int blockDR, int blockUR, int size);  // 地基可达性预检：地基旁须有路可走，避免选址被建筑围死、村民永远走不到(卡死)
    // avoidFarmAdjacent=true：额外跳过与已有农场"相邻"的位置（3x3 外扩 1 格内不得有农场）。
    //   ★ 2026-09-15：农场兜底选址用 —— 旧链第一步的 findBuildSite 兜底不做此检查，
    //     一旦 TC 内圈被占就会把农场紧贴着排成一片，破坏 isFarmAdjacent 的"隔 1 格"设计。
    bool findBuildSite(int &x, int &y, int size = 2, bool avoidFarmAdjacent = false);
    bool findBuildSiteTowardCenter(int &x, int &y, int size, int minR, int maxR);  // 建筑选址偏向 TC→地图中心方向且离TC更远(避免堵角)
    bool findDefenseBuildSite(int &x, int &y, int size = 2);
    bool findGranarySite(int &x, int &y);
    // 远距浆果群定位（第二座谷仓专用）：找到距 TC ≥ SECOND_GRANARY_TC_MIN_DIST、距任一已有谷仓 >12 格、
    // 且 5 格内丛数 ≥ MIN_BUSH_FOR_SECOND_GRANARY 的最密集浆果群，输出其块坐标与丛数。
    bool findRemoteBushCluster(int &bx, int &by, int &outCnt);
    bool findMarketSite(int &x, int &y);
    bool findHouseSite(int &x, int &y);
    // ★ 2026-09-15（用户需求「优化农场布局，尽量分布在 TC 和谷仓周围」）：
    //   统一锚点候选 + 评分择优 —— 锚点 = TC + 全部已建成谷仓(GRANARY)/仓库(STOCK)，
    //   在 [FARM_ANCHOR_R_MIN, FARM_ANCHOR_R_MAX] 环上枚举空位，评分 = 到 TC 的距离
    //   （不用"到最近锚点"：该口径实测被证伪，会让 39.2% 的农场飞到 52 格外的谷仓旁）。
    //   ★ 取代旧三段式链 findFarmRingSite → findFarmNearGranarySite → findBuildSite：
    //     旧链第一步 findFarmRingSite 内部自带 findBuildSite 兜底 ⇒ 恒返回 true ⇒
    //     第二步 findFarmNearGranarySite 永不可达。
    //   旧两函数已于 2026-09-15 清理中删除（它们只被上面这条失效链调用，链一换即为死代码）。
    //   回滚参照：UsrAI.cpp.bak_20260915_pre_cleanup。
    bool findFarmSiteBest(int &x, int &y);
    bool isFarmAdjacent(int blockDR, int blockUR);  // 农场不相邻：候选农场外扩1格内不得有其他农场(至少隔1格)
    // noFallback=true：指定 prefX/prefY 但周边放不下时【直接失败】，不再回退到默认选址
    //   （用于"必须建在某片资源旁"的场景，否则回退可能建到完全无关的位置）
    // preferNearBuilder=true：优先派【离 prefX/prefY 最近】的空闲村民当建造者（默认 false=原行为）
    bool tryBuild(int buildingType, int size, bool ignoreCooldown = false, int prefX = -1, int prefY = -1,
                  bool noFallback = false, bool preferNearBuilder = false);
    void handleBuildResults();        // 处理建造指令执行结果（失败换位置重试）
    void detectStuckGatherers();      // 检测寻路卡死的采集村民，强制打断并拉黑目标资源

    // ---- 资源采集辅助 ----
    bool tryAssignFood(tagFarmer* f);

    // ---- 核心策略函数 ----
    void updateState();            // 阶段切换
    // ★ 铜器升级统一入口（含引擎前置检查+幂等）；返回 true = 本帧确实发出了升级令
    int  countAgeUpgradeBuildings();   // 市场/靶场/马厩 已存在数（引擎升级硬前置）
    bool tryStartBronzeUpgrade();
    void manageEconomy();          // 经济（农民生产+分配+科技）
    void manageBuildings();        // 建造管理
    void assignIdleFarmers();      // 空闲村民分配
    void assignIdleSimple();       // 最后兜底：无视复杂标记，派所有空闲村民到最近资源
    void manageTechUpgrade();      // 科技升级
    void managePriest();           // 祭司管理（最高优先级）
    void manageMilitary();         // military training and combat
    void manageFirstWaveDefense(); // first-wave priest protection
    void manageCarriedResources();
    void manageCounterAttack();    // 反攻
    void manageHunting();          // 打猎模块
    void manageLionDefense();      // ★ 狮子防御：有狮子逼近/攻击我方单位时立刻就近派人猎杀
    void checkDefeat();            // 失败检查
    void doDebugOutput();          // 调试输出
};

#endif // USRAI_H
