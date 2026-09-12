#include "UsrAI.h"
#include <unordered_set>
#include <map>
#include <mutex>
#include <chrono>

tagGame tagUsrGame;
ins UsrIns;
 







static inline bool sortIsRanged(int sort) {
    return sort == AT_STONE_THROWER || sort == AT_BOWMAN ||
           sort == AT_COMPOSITE_BOWMAN || sort == AT_SLINGER ||
           sort == AT_CHARIOT_ARCHER;
}



static inline bool sortIsMelee(int sort) {
    return sort == AT_CLUBMAN || sort == AT_SCOUT || sort == AT_SWORDSMAN ||
           sort == AT_IMPROVED || sort == AT_CAVALRY || sort == AT_HOPLITE ||
           sort == AT_CHARIOT || sort == AT_BROADSWORDSMAN;
}





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









static inline bool sortHasKiteRangeAdvantage(int selfSort, int enemySort, double BL) {
    if (enemySort < 0 || !sortIsRanged(enemySort)) return true;
    return sortMaxRangedRange(selfSort, BL) > sortMaxRangedRange(enemySort, BL);
}



namespace {
inline double dist2(double x1, double y1, double x2, double y2) {
    const double dx = x1 - x2;
    const double dy = y1 - y2;
    return dx * dx + dy * dy;
}
}  


#define WAVE1_TIME 5000
#define WAVE2_TIME 13500
#define WAVE3_TIME 21000


#define MAX_FARMERS 22          
#define MAX_HOUSES 12           
#define POP_HEADROOM_BUILD 2    



#define MAX_FARMS 10            


#define FARM_ANCHOR_R_MIN 4      

#define FARM_ANCHOR_R_MAX 4      

#define WOOD_RESERVE_FOR_GAZELLE_STOCK 125

#define FARM_WOOD_NEED(gazelleStockBuilt) \
    ((gazelleStockBuilt) ? BUILD_FARM_WOOD : (BUILD_FARM_WOOD + WOOD_RESERVE_FOR_GAZELLE_STOCK))

#define FARM_WAIT_WOOD_TECH_FRAME 18000

#define FARM_WAIT_CB_FRAME 21000
#define COMPOSITE_BOW_WOOD_RESERVE 100   


#define ARMY_IGNORE_SIEGE_WORKSHOP true



#define PRIEST_CONVERT_SIEGE_WHEN_CLEAR true
#define PRIEST_CONVERT_SIEGE_RANGE 12.0  

#define GAZELLE_HUNT_RANGE  50


#define GAZELLE_STOCK_MIN_HOUSES    1     
#define GAZELLE_STOCK_WINDOW_END    16500 

#define GAZELLE_STOCK_GATE_DEADLINE 9000  



#define ELEPHANT_HUNT_GROUP 5
#define ELEPHANT_HUNT_MIN   4   


#define ELEPHANT_RESCUE_MAX_ON 1  
#define ELEPHANT_BAN_FRAMES    1500  
#define MAX_TOWERS 3            
#define MAX_RANGES 3            



#define TOWER_TARGET_RANGE 12   







#define ARROWTOWER_RANGE 8.0    





#define TOWER_APPROACH_RANGE 30.0     
#define TOWER_APPROACH_STANDOFF 10.0  


#define MAX_STOCK 4             






#define STOCK_ORDER_SETTLE     3000   
#define STOCK_ORDER_MERGE_BLK  20.0   
#define STOCK_ORDER_RING       4      







#define GOLD_STOCK_ANCHOR_RANGE  20.0  
#define MAX_GOLD_STOCK           1     
#define GOLD_STOCK_WOOD_MARGIN   30    



#define MIN_GAZELLE_FOR_SECOND_STOCK 2


#define MAX_GRANARY 2                   
#define MIN_BUSH_FOR_SECOND_GRANARY 6   
#define SECOND_GRANARY_TC_MIN_DIST 25   
#define BUSH_CLUSTER_RADIUS 5           
#define BUSH_NEAR_GRANARY_DIST 20       


#define DISABLE_CLUBMAN_TRAIN true

#define ENABLE_EARLY_CLUBMAN true
#define EARLY_CLUBMAN_START_FRAME 6000   
#define EARLY_CLUBMAN_TARGET 4           

#define DEAD_BUILDING_GRACE 1800  
                                  
#define ORPHAN_REDISPATCH_CD 120  
#define ORPHAN_STEAL_CD 300       
                                  
#define BUILDER_HARD_TIMEOUT 1800 
                                  
                                  
#define PENDING_BUILD_TIMEOUT 300



#define BUILD_POS_BLACKLIST_FRAMES 1800
 
#define BUILD_GAP 1              
#define MELEE_OVERFLOW_FOOD 150      


#define KITING_SAFE_MARGIN   2.0   
#define KITING_MIN_KEEP      5.0   
#define KITING_HYST          2.0   
#define KITING_LANDING_SLACK 0.5   




#define HOPLITE_RATIO_NUM   3    
#define HOPLITE_RATIO_DEN   4    
#define HOPLITE_RATIO_FLOOR 2    


#define DISABLE_CAVALRY_TRAIN true  


#define EARLY_CLUBMAN_END_FRAME 22500   


#define ENABLE_SCOUT_RECON false







#define SCOUT_MAX_DIST 50.0

#define COUNTER_ATTACK_MIN_ARMY 12   
#define COUNTER_ATTACK_FORCE_TIME 33000 
                                        
                                        
                                        
                                        




#define COUNTER_FARMER_ATTACK true
#define COUNTER_FARMER_ATTACK_FRAME 40500   
#define COUNTER_FARMER_ATTACK_GAP 90        
                                            

#define PRIEST_GUARD_URGENT 8.0   
#define PRIEST_GUARD_ALERT  15.0  
#define PRIEST_GUARD_RECALL 30.0  
#define PRIEST_GUARD_MAX_CMDS 12  

#define PRIEST_CONVERT_RANGE 28.0



#define PRIEST_SAFE_BEHIND     8.0   
#define PRIEST_COUNTER_FLEE_HP 0.6  


#define PRIEST_SIEGE_CONVERT_LOCKOUT 400




#define PRIEST_SIEGE_CLEAR_ARMY_R  8.0   
#define PRIEST_SIEGE_CLEAR_TOWER_R 14.0  
#define PRIEST_SIEGE_ABORT_R       4.5   
#define PRIEST_SIEGE_ABORT_HP      0.35  




#define PRIEST_SIEGE_GUARD_HP      0.45  



#define PRIEST_SIEGE_REQUIRE_TOWERS_CLEAR true   





#define PRIEST_TOWERS_CLEAR_MAX 2   







#define PRIEST_TOWERS_CLEAR_MIN_SEEN 1
#define PRIEST_MIN_DIST_TARGET 18.0  



#define DISABLE_STABLE_BUILD  false   
#define DISABLE_COLLAGE_BUILD false   
#define DISABLE_GRANARY_BUILD false   


#define DISABLE_BROADSWORD_TECH true  


#define DISABLE_TOWER_UPGRADE true


#define DISABLE_USETOOL_TECH true         
#define DISABLE_INFANTRY_ARMOR_TECH false 
#define DISABLE_ARCHER_ARMOR_TECH   false 


#define ARMOR_INF_T1_FOOD   75    
#define ARMOR_INF_T2_FOOD   100   
#define ARMOR_INF_T2_GOLD   50
#define ARMOR_ARC_T1_FOOD   100   
#define ARMOR_ARC_T2_FOOD   125   
#define ARMOR_ARC_T2_GOLD   50

#define ARMOR_ACCEPT_TIMEOUT 120
#define DISABLE_MARKET_TECH true          
#define DISABLE_MARKET_WOOD_TECH false    




#define WOOD_TECH_ABSOLUTE_FIRST true
#define MIN_GOLD_WORKERS 1      

#define STONE_CAP_STOP 300   

#define WOOD_CAP_STOP  400   
#define WOOD_CAP_STOP_LATE 400 
#define WOOD_KEEP_MIN  2     
#define GOLD_CAP_STOP  1000  
                                
                                
#define FOOD_CAP_STOP  650   
#define FOOD_CAP_STOP_PREBRONZE 850 


#define BRONZE_MIN_AGE_BUILDINGS 2     
#define BRONZE_RETRY_INTERVAL 120      
#define BRONZE_GIVEUP_FRAMES  3600     
#define WOOD_LOW_LINE  100   
#define WOOD_TARGET_BASE 4   
#define WOOD_TARGET_LOW  8   


#define WOOD_MAX_ANCHOR_DIST 15

#define WOOD_SCORE_ALPHA 0.5   
#define WOOD_SCORE_BETA  1.0   


#define WOOD_MAX_WORKERS_PER_TREE 2   
#define GOLD_RICH_TOL   1.25 








#define FOOD_GOLD_NUM 5
#define FOOD_GOLD_DEN 3


#define FOOD_REBALANCE_KEEP 7
#define FOOD_GOLD_REBALANCE_INTERVAL 10



#define STONE_WORKERS_LATE 1    
#define FOOD_PAUSE_TECH_TRAIN 60 
#define STUCK_GATHER_TIMEOUT 1500



#define TREE_REASSIGN_WINDOW 600
#define TREE_REASSIGN_MAX 5
#define TREE_REASSIGN_BLACKLIST_FRAMES 900     
#define STUCK_BLACKLIST_FRAMES 15000
#define PROF_SAMPLE_FRAMES 300  

void UsrAI::processData() {
    
    
    
    
    
    
    {
        static bool envLogged = false;
        if (!envLogged) {
            envLogged = true;
            DebugText(QString("[ENV] engine=%1 NOWPLAYER=%2 MAXPLAYER=%3 represent=%4")
                      .arg(QString::fromStdString(GAME_VERSION))
                      .arg(NOWPLAYER).arg(MAXPLAYER).arg(NOWPLAYERREPRESENT));
        }
    }

    typedef std::chrono::steady_clock ProfClock;
    static double profSum[12] = {0.0};
    static double profMax[12] = {0.0};
    static int profSamples = 0;
    auto profNow = []() { return ProfClock::now(); };
    auto profAdd = [](int idx, ProfClock::time_point a, ProfClock::time_point b) {
        double ms = std::chrono::duration<double, std::milli>(b - a).count();
        profSum[idx] += ms;
        if (ms > profMax[idx]) profMax[idx] = ms;
    };
#define AI_PROF_STAGE(idx, call) do { auto _ai_prof_t0 = profNow(); call; profAdd(idx, _ai_prof_t0, profNow()); } while (0)

    auto tGet0 = profNow();
    info = tagUsrGame.getInfo();
    auto tGet1 = profNow();
    profAdd(0, tGet0, tGet1);
    frame = info.GameFrame;

    
    
    
    
    
    {
        static int localDirtySnap = 0;
        static int lastNonzeroFrame = 0;
        static int lastBeatBucket = -1;
        const int curF = info.GameFrame;
        if (curF > 0) {
            if (lastNonzeroFrame > 0 && curF < lastNonzeroFrame) localDirtySnap++;  
            lastNonzeroFrame = curF;                                                
        } else if (lastNonzeroFrame > 0) {
            localDirtySnap++;                                                       
        }
        
        if (lastNonzeroFrame > 0 && lastNonzeroFrame / 1500 != lastBeatBucket) {
            lastBeatBucket = lastNonzeroFrame / 1500;
            DebugText(QString("[DIRTY-SNAP f=%1] 累计脏快照拦截=%2").arg(lastNonzeroFrame).arg(localDirtySnap));
        }
    }

    
    AI_PROF_STAGE(1, handleBuildResults());

    
    AI_PROF_STAGE(2, checkDefeat());
    if (state == VICTORY || state == DEFEAT) return;

    
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

    
    {
        bool found = false;
        for (auto &a : info.armies) {
            if (a.Sort == AT_PRIEST) { priestSN = a.SN; found = true; break; }
        }
        if (!found) priestSN = -1;
    }

    
    
    
    
    
    {
        bool isWarNow = (state >= DEFENSE_WAVE1 && state <= DEFENSE_WAVE3);
        if ((isWarNow || state == COUNTERATTACK) && scoutPhase < 20) {
            scoutPhase = 20;
            scoutReturnTry = 0;
            scoutWalkTimer = 0;
            scoutIssueFrame = -999999;
        }
    }

    
    AI_PROF_STAGE(3, managePriest());

    
    if (buildCooldown > 0) buildCooldown--;
    if (techCooldown  > 0) techCooldown--;
    if (trainCooldown > 0) trainCooldown--;

    
    AI_PROF_STAGE(4, updateState());

    AI_PROF_STAGE(5, manageCarriedResources());

    
    AI_PROF_STAGE(6, manageHunting());


    
    AI_PROF_STAGE(7, detectStuckGatherers());

    
    AI_PROF_STAGE(8, manageEconomy());

    
    AI_PROF_STAGE(9, manageMilitary());

    
    if (state == COUNTERATTACK) {
        AI_PROF_STAGE(10, manageCounterAttack());
    }

    
    AI_PROF_STAGE(11, doDebugOutput());

    ++profSamples;
    if (profSamples >= PROF_SAMPLE_FRAMES) {
        const double n = (double)profSamples;
        DebugText(QString("[PROF f=%1 n=%2] get=%3/%4 build=%5/%6 def=%7/%8 priest=%9/%10 state=%11/%12 carry=%13/%14 hunt=%15/%16 stuck=%17/%18 eco=%19/%20 mil=%21/%22 ca=%23/%24 dbg=%25/%26")
                  .arg(frame).arg(profSamples)
                  .arg(profSum[0]/n, 0, 'f', 3).arg(profMax[0], 0, 'f', 3)
                  .arg(profSum[1]/n, 0, 'f', 3).arg(profMax[1], 0, 'f', 3)
                  .arg(profSum[2]/n, 0, 'f', 3).arg(profMax[2], 0, 'f', 3)
                  .arg(profSum[3]/n, 0, 'f', 3).arg(profMax[3], 0, 'f', 3)
                  .arg(profSum[4]/n, 0, 'f', 3).arg(profMax[4], 0, 'f', 3)
                  .arg(profSum[5]/n, 0, 'f', 3).arg(profMax[5], 0, 'f', 3)
                  .arg(profSum[6]/n, 0, 'f', 3).arg(profMax[6], 0, 'f', 3)
                  .arg(profSum[7]/n, 0, 'f', 3).arg(profMax[7], 0, 'f', 3)
                  .arg(profSum[8]/n, 0, 'f', 3).arg(profMax[8], 0, 'f', 3)
                  .arg(profSum[9]/n, 0, 'f', 3).arg(profMax[9], 0, 'f', 3)
                  .arg(profSum[10]/n, 0, 'f', 3).arg(profMax[10], 0, 'f', 3)
                  .arg(profSum[11]/n, 0, 'f', 3).arg(profMax[11], 0, 'f', 3));
        for (int i = 0; i < 12; ++i) { profSum[i] = 0.0; profMax[i] = 0.0; }
        profSamples = 0;
    }
#undef AI_PROF_STAGE
}




int UsrAI::countAgeUpgradeBuildings() {
    int n = 0;
    if (countBuildingsExisting(BUILDING_MARKET) > 0) n++;
    if (countBuildingsExisting(BUILDING_RANGE)  > 0) n++;
    if (countBuildingsExisting(BUILDING_STABLE) > 0) n++;
    return n;
}



bool UsrAI::tryStartBronzeUpgrade() {
    if (info.civilizationStage >= CIVILIZATION_BRONZEAGE) return false;
    if (hasUpgraded) return false;                                     
    if (info.Meat < BUILDING_CENTER_UPGRADE_BRONZEAGE_FOOD) return false;
    auto tc = findBuilding(BUILDING_CENTER);
    if (!tc) return false;
    if (tc->Project == BUILDING_CENTER_UPGRADE) {                      
        hasUpgraded = true;
        return true;
    }
    if (tc->Project != ACT_NULL) return false;                         
    if (countAgeUpgradeBuildings() < BRONZE_MIN_AGE_BUILDINGS) return false;  
    BuildingAction(tc->SN, BUILDING_CENTER_UPGRADE);
    bronzeIssuedFrame = frame;
    bronzeAttemptCount++;
    return true;
}


void UsrAI::updateState() {
    switch (state) {
    case EARLY_ECONOMY: {
        
        if (tryStartBronzeUpgrade()) {
            state = UPGRADING;
            DebugText(QString(">> Upgrading to Bronze Age! Frame=%1, Meat=%2, Farmers=%3, ageBld=%4").arg(frame).arg((int)info.Meat).arg((int)info.farmers.size()).arg(countAgeUpgradeBuildings()));
        }
        
        if (frame > WAVE1_TIME && state == EARLY_ECONOMY) {
            state = DEFENSE_PREP;
            DebugText("!! Force DEFENSE_PREP (timeout from ECONOMY)");
        }
        break;
    }
    case UPGRADING: {
        auto tc = findBuilding(BUILDING_CENTER);
        
        if (info.civilizationStage >= CIVILIZATION_BRONZEAGE) {
            hasUpgraded = true;
            bronzeIssuedFrame = -999999; bronzeAttemptCount = 0; bronzeStallFrames = 0;
            state = DEFENSE_PREP;
            DebugText(">> Bronze Age reached!");
            break;
        }
        
        if (tc && tc->Project == BUILDING_CENTER_UPGRADE) {
            hasUpgraded = true;
            bronzeStallFrames = 0;
            break;
        }
        
        hasUpgraded = false;
        bronzeStallFrames++;
        if (bronzeStallFrames == 1 || bronzeStallFrames % BRONZE_RETRY_INTERVAL == 0) {
            bool issued = tryStartBronzeUpgrade();
            DebugText(QString("!! BRONZE-RETRY f=%1 issued=%2 try#%3 stall=%4 meat=%5 tcProj=%6 ageBld=%7(m%8 r%9 s%10)").arg(frame).arg((int)issued).arg(bronzeAttemptCount).arg(bronzeStallFrames)
                .arg((int)info.Meat).arg(tc ? tc->Project : -99).arg(countAgeUpgradeBuildings()).arg(countBuildingsExisting(BUILDING_MARKET)).arg(countBuildingsExisting(BUILDING_RANGE))
                .arg(countBuildingsExisting(BUILDING_STABLE)));
        }
        
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
        
        if (tryStartBronzeUpgrade()) {
            state = UPGRADING;
            DebugText(QString(">> WAVE1 Bronze Age! Frame=%1, Meat=%2, ageBld=%3").arg(frame).arg((int)info.Meat).arg(countAgeUpgradeBuildings()));
            break;
        }
        
        if (frame > WAVE1_TIME + 3500) {
            int eCount = info.enemy_armies.size() + info.enemy_farmers.size();
            if (eCount < 3 || frame > WAVE1_TIME + 6000) {
                state = DEFENSE_PREP;
                DebugText(QString(">> Wave 1 defeated at frame %1").arg(frame));
            }
        }
        
        if (frame >= WAVE2_TIME && !wave2Started) {
            wave2Started = true;
            state = DEFENSE_WAVE2;
            DebugText("!! WAVE 2 INCOMING!");
        }
        break;

    case DEFENSE_PREP:
        
        
        if (tryStartBronzeUpgrade()) {
            state = UPGRADING;
            DebugText(QString(">> LATE Bronze Age! Frame=%1, Meat=%2, ageBld=%3").arg(frame).arg((int)info.Meat).arg(countAgeUpgradeBuildings()));
            break;
        }
        
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
        
        if (frame > COUNTER_ATTACK_FORCE_TIME) {
            int eCount = info.enemy_armies.size() + info.enemy_farmers.size();
            if (eCount < 3 || frame > COUNTER_ATTACK_FORCE_TIME + 6000) {
                state = COUNTERATTACK;
                DebugText(QString(">> ALL WAVES DEFEATED! Counterattack! Frame=%1").arg(frame));
            }
        }


        if (frame > COUNTER_ATTACK_FORCE_TIME && state == DEFENSE_WAVE3) {
            state = COUNTERATTACK;
            DebugText("!! Force COUNTERATTACK (timeout)");
        }
        break;

    default: break;
    }
}


void UsrAI::managePriest() {
    if (priestSN == -1) return;

    
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
    bool inCounter = (state == COUNTERATTACK);   

    if (priestMoveCooldown > 0) priestMoveCooldown--;

    
    
    
    
    
    
    auto isRangedSort = [&](int s) -> bool {
        return s == AT_BOWMAN || s == AT_CHARIOT_ARCHER ||
               s == AT_COMPOSITE_BOWMAN || s == AT_SLINGER;
    };
    auto enemyThreatRange = [&](int s) -> double {
        return (isRangedSort(s) || s == AT_STONE_THROWER) ? 12.0 * BL : 2.5 * BL;
    };
    
    auto ownOccupied = [&](double x, double y) -> bool {
        for (auto &b : info.buildings)
            if (calDistance(x, y, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL) < 2.5 * BL) return true;
        for (auto &a : info.armies)
            if (a.SN != priestSN && calDistance(x, y, a.DR, a.UR) < 2.0 * BL) return true;
        for (auto &f : info.farmers)
            if (calDistance(x, y, f.DR, f.UR) < 2.0 * BL) return true;
        return false;
    };

    
    auto occupiedLanding = [&](double x, double y) {
        if (ownOccupied(x, y)) return true;
        for (auto &e : info.enemy_armies)
            if (calDistance(x, y, e.DR, e.UR) < 4.0 * BL) return true;
        
        return false;
    };

    
    
    auto healLandingOk = [&](double x, double y) -> bool {
        if (x < 0 || y < 0 || x > MAP_L * BL || y > MAP_U * BL) return false;
        for (auto &b : info.buildings)
            if (calDistance(x, y, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL) < 2.5 * BL) return false;
        for (auto &e : info.enemy_armies)
            if (calDistance(x, y, e.DR, e.UR) < 2.0 * BL) return false;
        
        return true;
    };



    auto pickHealTarget = [&](double maxRatio, bool counterRule,
                              double &outDR, double &outUR, double &outRatio) -> int {
        int bestSN = -1; double worst = 1.0, bestD = 1e12;
        outDR = 0; outUR = 0;
        for (auto &a : info.armies) {
            if (a.SN == priestSN) continue;              
            if (a.MaxBlood <= 0 || a.Blood <= 0) continue;
            double r = (double)a.Blood / a.MaxBlood;
            if (r >= maxRatio) continue;
            if (counterRule && inCounter && r >= 0.5) continue;
            double d = calDistance(pDR, pUR, a.DR, a.UR);
            if (d > 25.0 * BL) continue;                 
            if (r < worst || (r == worst && d < bestD)) {
                worst = r; bestSN = a.SN; bestD = d; outDR = a.DR; outUR = a.UR;
            }
        }
        outRatio = worst;
        return bestSN;
    };




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



        auto pickByBlood = [&](int mode) -> int {
            int bSN = -1, bBlood = -1; double bD = 1e12;
            for (auto &e : info.enemy_armies) {
                if (e.Blood <= 0) continue;
                bool want;
                switch (mode) {
                    case 0:  want = (e.Sort == AT_HOPLITE); break;                        
                    case 1:  want = (e.Sort != AT_HOPLITE && e.Sort != AT_STONE_THROWER &&
                                     !isRangedSort(e.Sort)); break;                       
                    case 2:  want = (e.Sort != AT_HOPLITE && e.Sort != AT_STONE_THROWER &&
                                     isRangedSort(e.Sort)); break;                        
                    default: want = (e.Sort == AT_STONE_THROWER); break;                  
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
        if ((t = pickByBlood(0)) >= 0) return t;   
        if ((t = pickByBlood(1)) >= 0) return t;   
        if ((t = pickByBlood(2)) >= 0) return t;   
        if ((t = pickByBlood(3)) >= 0) return t;   
        
        
        return -1;
    };

    
    
    double threatDist = 1e12;
    double nearestThreatR = 2.5 * BL;   
    {
        auto chkThreat = [&](double x, double y, double r) {
            double d = calDistance(pDR, pUR, x, y);
            if (d <= r + 4.0 * BL) {
                if (d < threatDist) { threatDist = d; nearestThreatR = r; }  
            }
        };
        for (auto &e : info.enemy_armies) {
            chkThreat(e.DR, e.UR, enemyThreatRange(e.Sort));
        }
        
        
        for (auto &b : info.enemy_buildings)
            if (b.Type == BUILDING_ARROWTOWER) chkThreat((b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL, 12.0 * BL);
    }

    auto priestApproachMove = [&](double eDR, double eUR, double stopDist) -> bool {
        if (priestMoveCooldown > 0) return false;   
        double dx = eDR - pDR, dy = eUR - pUR;
        double len = std::sqrt(dx*dx + dy*dy);
        if (len < 0.01) return false;
        double ux = dx/len, uy = dy/len;
        double bx = pDR + ux * (len - stopDist * BL);
        double by = pUR + uy * (len - stopDist * BL);
        const double OFF[6] = {0.0, 3.0, -3.0, 6.0, -6.0, 9.0};
        double candX = bx, candY = by; bool ok = false;
        for (int o = 0; o < 6; ++o) {
            double cx = bx - uy * OFF[o] * BL;   
            double cy = by + ux * OFF[o] * BL;
            cx = max(0.0, min((double)MAP_L * BL, cx));
            cy = max(0.0, min((double)MAP_U * BL, cy));
            if (!occupiedLanding(cx, cy)) { candX = cx; candY = cy; ok = true; break; }
        }
        if (!ok) return false;   
        HumanMove(priestSN, candX, candY);
        priestMoveCooldown = 20;
        return true;
    };

    
    
    auto priestFlee = [&](double enDR, double enUR) {
        if (priestMoveCooldown > 0) return;   
        
        const int MAXT = 256;
        double thX[MAXT], thY[MAXT], thR[MAXT];
        int nT = 0;
        auto pushThreat = [&](double x, double y, double r) {
            if (nT < MAXT) { thX[nT] = x; thY[nT] = y; thR[nT] = r; nT++; }
        };
        for (auto &e : info.enemy_armies) {
            double d = calDistance(pDR, pUR, e.DR, e.UR);
            double r = enemyThreatRange(e.Sort);
            if (d <= r + 4.0 * BL) pushThreat(e.DR, e.UR, r);   
        }
        
        for (auto &b : info.enemy_buildings)
            if (b.Type == BUILDING_ARROWTOWER) {
                double bx = (b.BlockDR + 1) * BL, by = (b.BlockUR + 1) * BL;
                double d = calDistance(pDR, pUR, bx, by);
                if (d <= 16.0 * BL) pushThreat(bx, by, 12.0 * BL);
            }
        
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
        else return;   


        double anchorX = tcDR, anchorY = tcUR;
        {
            double bestTowerDist = 30.0 * BL;
            for (auto &b : info.buildings)
                if (b.Type == BUILDING_ARROWTOWER && b.Percent == 100) {
                    double bx = (b.BlockDR + 1) * BL, by = (b.BlockUR + 1) * BL;
                    double d = calDistance(pDR, pUR, bx, by);
                    
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
        
        double toAX = anchorX - pDR, toAY = anchorY - pUR;
        double alen = std::sqrt(toAX*toAX + toAY*toAY);
        if (alen > 0.01) {
            double dot = (toAX/alen)*std::cos(baseAng) + (toAY/alen)*std::sin(baseAng);
            if (dot > 0) baseAng = std::atan2(std::sin(baseAng) + toAY/alen*0.9,
                                              std::cos(baseAng) + toAX/alen*0.9);
        }


        if (priestFleeLastFrame > -999999) {
            double dLast = calDistance(pDR, pUR, priestFleeLastX, priestFleeLastY);
            
            bool stuckAtLast = (priest->NowState == HUMAN_STATE_IDLE && dLast > 2.0 * BL);
            if (!stuckAtLast && dLast > 3.0 * BL) {
                bool lastSafe = true;
                for (int t = 0; t < nT; ++t)
                    if (calDistance(priestFleeLastX, priestFleeLastY, thX[t], thY[t]) < thR[t] + 1.0 * BL) { lastSafe = false; break; }
                if (lastSafe && !occupiedLanding(priestFleeLastX, priestFleeLastY)) {
                    HumanMove(priestSN, priestFleeLastX, priestFleeLastY);
                    priestMoveCooldown = 18;
                    return;   
                }
            }
        }
        
        if (priestFleeLastFrame > -999999) {
            double distToLast = calDistance(pDR, pUR, priestFleeLastX, priestFleeLastY);
            if (priest->NowState == HUMAN_STATE_IDLE && distToLast > 2.0 * BL) {
                if (priestFleeTry < 30) priestFleeTry++;   
            } else if (distToLast <= 2.0 * BL) {
                priestFleeTry = 0;   
            }
        }
        
        auto badLanding = [&](double x, double y) -> bool {
            if (x < 0 || y < 0 || x > MAP_L * BL || y > MAP_U * BL) return true;
            if (ownOccupied(x, y)) return true;   
            for (int t = 0; t < nT; ++t)
                if (calDistance(x, y, thX[t], thY[t]) < thR[t]) return true;  
            return false;
        };
        
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
                double margin = 1e9;   
                for (int t = 0; t < nT; ++t)
                    margin = std::min(margin, calDistance(tx, ty, thX[t], thY[t]) - thR[t]);
                double dAnchor = calDistance(tx, ty, anchorX, anchorY);   
                if (margin >= 0 && !foundSafe) { bestX = tx; bestY = ty; bestSafe = margin; bestAnchor = dAnchor; foundSafe = true; found = true; }
                else if (margin >= 0 && dAnchor < bestAnchor) { bestX = tx; bestY = ty; bestSafe = margin; bestAnchor = dAnchor; found = true; }
                else if (!foundSafe && margin > bestSafe) { bestX = tx; bestY = ty; bestSafe = margin; bestAnchor = dAnchor; found = true; }
            }
        }
        if (!found) {
            
            double rad = 40.0 * BL;
            bestX = max(0.0, min((double)MAP_L * BL, pDR + std::cos(baseAng) * rad));
            bestY = max(0.0, min((double)MAP_U * BL, pUR + std::sin(baseAng) * rad));
            if (frame % 50 == 0) DebugText("Priest FLEE: 无安全落点→退回主方向");
        }
        
        if (priestFleeTry >= 24 && priest->NowState == HUMAN_STATE_IDLE &&
            calDistance(pDR, pUR, priestFleeLastX, priestFleeLastY) > 2.0 * BL) {
            priestMoveCooldown = 40;
            if (frame % 50 == 0) DebugText("Priest FLEE: 卡死->本帧静默");
            return;
        }
        HumanMove(priestSN, bestX, bestY);
        priestFleeLastX = bestX; priestFleeLastY = bestY; priestFleeLastFrame = frame;
        priestMoveCooldown = 18;   
        if (frame % 50 == 0)
            DebugText(QString("Priest FLEE hp=%1 safe=%2 dAnchor=%3").arg((priest->MaxBlood > 0 ? (double)priest->Blood / priest->MaxBlood : 1.0), 0, 'f', 2)
                      .arg(foundSafe ? 1 : 0).arg(bestAnchor / BL, 0, 'f', 0));
    };


    
    
    
    if (!canAct) {
        double pBRx = (priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0;   
        
        
        int lockers = 0, near12 = 0;
        for (auto &e : info.enemy_armies) {
            if (e.Blood <= 0) continue;
            double d = calDistance(pDR, pUR, e.DR, e.UR);
            if (e.WorkObjectSN == priestSN) lockers++;
            if (d <= 12.0 * BL) near12++;
        }
        const bool danger = (lockers >= 2) || (near12 >= 4);
        const double abortHp = danger ? 0.60 : 0.25;
        if (pBRx > abortHp) return;

        
        priestMoveCooldown = 0;

        double feDR = 0, feUR = 0, fbest = 1e12;
        for (auto &e : info.enemy_armies) {
            double d = calDistance(pDR, pUR, e.DR, e.UR);
            if (d < fbest) { fbest = d; feDR = e.DR; feUR = e.UR; }
        }
        priestMode = 1;
        priestFlee(feDR, feUR);
        return;
    }

    
    {
        double nearestE = 1e12;   
        for (auto &e : info.enemy_armies)
            nearestE = std::min(nearestE, calDistance(pDR, pUR, e.DR, e.UR));
        for (auto &b : info.enemy_buildings)
            if (b.Type == BUILDING_ARROWTOWER)
                nearestE = std::min(nearestE, calDistance(pDR, pUR, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL));
        double pBR = (priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0;   
        {
            
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
            
        };
        
        
        int safeConv = -1;
        if (priest->ConvertCooldown <= 0 && nearestE <= PRIEST_CONVERT_RANGE * BL) {
            int t = findConvertTarget(pDR, pUR, PRIEST_CONVERT_RANGE * BL);
            if (t >= 0) safeConv = t;
        }
        
        
        int convSN = -1; double convDR = 0, convUR = 0;
        if (safeConv >= 0) {
            convSN = safeConv;
            for (auto &e : info.enemy_armies) if (e.SN == convSN) { convDR = e.DR; convUR = e.UR; break; }
            
        }
        if (convSN >= 0) {
            
            
            
            if (priestMoveCooldown > 0) {
                bool rejected = (priestConvSN == convSN && priest->NowState == HUMAN_STATE_IDLE &&
                                 priestConvFrame > -999999 && frame - priestConvFrame >= 15);
                if (!rejected) return;
            }
            priestMode = 0;   
            double cdist = calDistance(pDR, pUR, convDR, convUR);
            if (cdist <= 12 * BL) {
                HumanAction(priestSN, convSN);
                priestConvSN = convSN; priestConvFrame = frame;
                priestMoveCooldown = 150;
                if (frame % 50 == 0)
                    DebugText(QString("Priest CONVERT(defense) SN=%1").arg(convSN));
                return;
            } else {
                double stopDist = 12.0;   
                priestApproachMove(convDR, convUR, stopDist); return;
            }
        }



        if (pBR <= 0.25) {
            double feDR = 0, feUR = 0; locateNearest(feDR, feUR);
            priestMode = 1; priestFlee(feDR, feUR); return;
        }



        {
            bool closeQuarters = false;
            for (auto &e : info.enemy_armies)
                if (calDistance(pDR, pUR, e.DR, e.UR) < 4.0 * BL) { closeQuarters = true; break; }
            if (!inCounter && priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0 && pBR > 0.25 && !closeQuarters) {
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
    }   
        
        
        bool meleeAdj = false;
        for (auto &e : info.enemy_armies)
            if (calDistance(pDR, pUR, e.DR, e.UR) < 4.0 * BL) { meleeAdj = true; break; }
        bool woundedNear = false;
        for (auto &a : info.armies) {
            if (a.SN == priestSN || a.MaxBlood <= 0 || a.Blood <= 0) continue;
            double r = (double)a.Blood / a.MaxBlood;
            if (r >= 0.9) continue;
            
            if (inCounter && r >= 0.5) continue;
            if (calDistance(pDR, pUR, a.DR, a.UR) > 25.0 * BL) continue;
            woundedNear = true; break;
        }
        bool healOverFlee = (!inCounter && pBR > 0.25 && !meleeAdj && woundedNear);
        bool fleeLag = false;
        for (auto &e : info.enemy_armies)
            if (calDistance(pDR, pUR, e.DR, e.UR) < 4.0 * BL) { fleeLag = true; break; }
        if (!fleeLag)
            for (auto &b : info.enemy_buildings)
                if (b.Type == BUILDING_ARROWTOWER) {
                    double bx = (b.BlockDR + 1) * BL, by = (b.BlockUR + 1) * BL;
                    if (calDistance(pDR, pUR, bx, by) < 14.0 * BL) { fleeLag = true; break; }
                }
        
        bool mustFlee = (threatDist <= nearestThreatR + 2.0 * BL);
        if (inCounter) {


            double pBRc = (priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0;
            mustFlee = meleeAdj || (pBRc <= PRIEST_COUNTER_FLEE_HP && threatDist <= nearestThreatR);
        }
        
        if (priestMode == 1 && (fleeLag || mustFlee) && !healOverFlee) {
            double feDR = 0, feUR = 0; locateNearest(feDR, feUR);
            priestFlee(feDR, feUR); return;
        }


        if (priestMode == 1 && !fleeLag && !mustFlee) priestMode = 0;
        
        
        if (mustFlee && !healOverFlee) {
            double feDR = 0, feUR = 0; locateNearest(feDR, feUR);
            priestMode = 1; priestFlee(feDR, feUR); return;
        }
        
        
        
        if (!inCounter &&
            (priest->NowState == HUMAN_STATE_IDLE || priest->NowState == HUMAN_STATE_WALKING)
            && priestMoveCooldown <= 0) {
            double bestAllyDR = 0, bestAllyUR = 0, worstRatio = 1.0;
            int bestAlly = pickHealTarget(0.9, true, bestAllyDR, bestAllyUR, worstRatio);
            if (bestAlly >= 0) {
                double bestAllyDist = calDistance(pDR, pUR, bestAllyDR, bestAllyUR);
                bool issued = false;
                if (bestAllyDist > 1.0 * BL) {
                    
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
        
        if (inCounter) return;


        {
            
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
            
            if (priest->NowState == HUMAN_STATE_IDLE && priestMoveCooldown <= 0 && dAnchor > 6 * BL && priestMode == 0) {
                
                double pIssueMoved = calDistance(pDR, pUR, priestIssueDR, priestIssueUR);
                if (pIssueMoved > 1.0 * BL) {
                    priestNearTCTry = 0;
                    priestIssueDR = pDR; priestIssueUR = pUR; priestIssueFrame = frame;
                } else if (priestIssueFrame > -999999 && frame - priestIssueFrame > 45) {
                    if (priestNearTCTry + 1 < 24) priestNearTCTry++;
                    priestIssueFrame = frame;   
                }
                
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
    
}


void UsrAI::manageEconomy() {

    typedef std::chrono::steady_clock EcoClock;
    static double ecoSum[5] = {0.0};
    static double ecoMax[5] = {0.0};
    static int ecoSamples = 0;
    auto ecoNow = []() { return EcoClock::now(); };
    auto ecoAdd = [](int idx, EcoClock::time_point a, EcoClock::time_point b) {
        double ms = std::chrono::duration<double, std::milli>(b - a).count();
        ecoSum[idx] += ms;
        if (ms > ecoMax[idx]) ecoMax[idx] = ms;
    };
#define ECO_PROF_STAGE(idx, call) do { auto _eco_t0 = ecoNow(); call; ecoAdd(idx, _eco_t0, ecoNow()); } while (0)
    auto ecoT0 = ecoNow();
    
    auto center = findBuilding(BUILDING_CENTER);
    
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
        int currentMaxFarmers = (frame < 13500) ? 16 : MAX_FARMERS;  
        if (farmerCount < currentMaxFarmers && totalPop < info.Human_MaxNum) {
            
            
            bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
            int minFood = 50;
            if (postBronze) {
                
                bool broadswordRunning = false;
                auto ac = findBuildingIncludingUnderConstruction(BUILDING_ARMYCAMP);
                if (ac && ac->Project == BUILDING_ARMYCAMP_UPGRADE_BROADSWORD)
                    broadswordRunning = true;

                bool compositeBowRunning = false;
                auto rng = findBuildingIncludingUnderConstruction(BUILDING_RANGE);
                if (rng && rng->Project == BUILDING_RANGE_UPGRADE_COMPOSITE_BOW)
                    compositeBowRunning = true;

                
                bool militaryTechPaid = broadswordRunning || compositeBowRunning
                    || broadswordResearched || compositeBowResearched;

                
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

    
    ecoAdd(0, ecoT0, ecoNow());
    ECO_PROF_STAGE(1, manageBuildings());

    
    ECO_PROF_STAGE(2, assignIdleFarmers());
    ECO_PROF_STAGE(3, assignIdleSimple());

    
    ECO_PROF_STAGE(4, manageTechUpgrade());

    ++ecoSamples;
    if (ecoSamples >= PROF_SAMPLE_FRAMES) {
        const double n = (double)ecoSamples;
        DebugText(QString("[PROF-ECO f=%1 n=%2] setup=%3/%4 build=%5/%6 farmers=%7/%8 assign=%9/%10 tech=%11/%12")
                  .arg(frame).arg(ecoSamples)
                  .arg(ecoSum[0]/n, 0, 'f', 3).arg(ecoMax[0], 0, 'f', 3)
                  .arg(ecoSum[1]/n, 0, 'f', 3).arg(ecoMax[1], 0, 'f', 3)
                  .arg(ecoSum[2]/n, 0, 'f', 3).arg(ecoMax[2], 0, 'f', 3)
                  .arg(ecoSum[3]/n, 0, 'f', 3).arg(ecoMax[3], 0, 'f', 3)
                  .arg(ecoSum[4]/n, 0, 'f', 3).arg(ecoMax[4], 0, 'f', 3));
        for (int i = 0; i < 5; ++i) { ecoSum[i] = 0.0; ecoMax[i] = 0.0; }
        ecoSamples = 0;
    }
#undef ECO_PROF_STAGE
}


void UsrAI::manageBuildings() {

    typedef std::chrono::steady_clock BuildClock;
    static double bSum[5] = {0.0};
    static double bMax[5] = {0.0};
    static int bSamples = 0;
    auto bNow = []() { return BuildClock::now(); };
    auto bAdd = [](int idx, BuildClock::time_point a, BuildClock::time_point b) {
        double ms = std::chrono::duration<double, std::milli>(b - a).count();
        bSum[idx] += ms;
        if (ms > bMax[idx]) bMax[idx] = ms;
    };
    auto bT0 = bNow();
    releasedBuilders.clear();

    auto isCriticalBuildType = [](int t) {
        return t == BUILDING_ARMYCAMP || t == BUILDING_RANGE ||
               t == BUILDING_MARKET  || t == BUILDING_GRANARY ||
               t == BUILDING_HOME    || t == BUILDING_STOCK ||
               t == BUILDING_FARM;
    };

    
    auto countFarmsForCap = [&]() {
        int cnt = 0;
        for (auto &b : info.buildings)
            if (b.Type == BUILDING_FARM) cnt++;
        for (auto &kv : pendingBuildIns)
            if (kv.second.second == BUILDING_FARM) cnt++;
        return cnt;
    };

    
    for (auto it = deadBuildings.begin(); it != deadBuildings.end(); ) {
        bool stillDead = false;
        for (auto &b : info.buildings) {
            if (b.SN == *it && b.Percent == 0) { stillDead = true; break; }
        }
        if (!stillDead) it = deadBuildings.erase(it); else ++it;
    }

    
    
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
            
            
            bool pendingNow = false;
            for (auto &kv : pendingBuildIns)
                if (kv.second.first == sn && kv.second.second == buildType) { pendingNow = true; break; }
            if (pendingNow) { ++it; continue; }

            
            releaseBuilderAndErase(sn, it);
            continue;
        }




        {
            auto dsp = builderDispatchFrame.find(sn);
            bool workingNow = (myB && f->NowState == HUMAN_STATE_WORKING && f->WorkObjectSN == myB->SN);


            bool anyoneWorking = false;
            if (myB)
                for (auto &g : info.farmers)
                    if (g.NowState == HUMAN_STATE_WORKING && g.WorkObjectSN == myB->SN) { anyoneWorking = true; break; }
            if (workingNow || anyoneWorking) {
                
            } else if (dsp != builderDispatchFrame.end() &&
                       frame - dsp->second > BUILDER_HARD_TIMEOUT) {
                if (myB && myB->Percent < 100) {
                    
                    
                    if (myB->Percent == 0 && !isCriticalBuildType(myB->Type)) {
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

        
        bool working = (f->NowState == HUMAN_STATE_WORKING && f->WorkObjectSN == myB->SN);
        if (working) {
            builderIdleFrame.erase(sn);
            buildRedispatchFrame.erase(sn);
            ++it; continue;
        }

        
        if (f->NowState == HUMAN_STATE_IDLE && f->Resource <= 0) {
            if (builderIdleFrame.find(sn) == builderIdleFrame.end())
                builderIdleFrame[sn] = frame;   
            
            if (buildRedispatchFrame.find(sn) == buildRedispatchFrame.end() || frame - buildRedispatchFrame[sn] >= 60) {
                HumanBuild(sn, buildType, (int)myB->BlockDR, (int)myB->BlockUR);
                buildRedispatchFrame[sn] = frame;
            }
            
            if (frame - builderIdleFrame[sn] > 900) {
                if (!isCriticalBuildType(myB->Type)) {
                    deadBuildings.insert(myB->SN);
                    if (!deadBuildingsFrame.count(myB->SN)) deadBuildingsFrame[myB->SN] = frame;
                }
                releaseBuilderAndErase(sn, it);
                continue;
            }
            ++it; continue;
        }

        
        ++it;
    }

    
    
    {
        for (auto &b : info.buildings) {
            if (b.Percent >= 100) continue;
            
            if (deadBuildings.count(b.SN)) {
                auto dit = deadBuildingsFrame.find(b.SN);
                if (dit != deadBuildingsFrame.end() && frame - dit->second > DEAD_BUILDING_GRACE) continue;
            }


            bool hasWorker = false;
            for (auto &f : info.farmers) {
                if (f.NowState == HUMAN_STATE_WORKING && f.WorkObjectSN == b.SN) { hasWorker = true; break; }
                
            }
            if (hasWorker) continue;





            bool crit = isCriticalBuildType(b.Type);
            tagFarmer* of = findIdleFarmer();
            bool steal = false;
            if (!of && crit) { of = findAnyFarmer(); steal = true; }
            if (!of) continue;
            
            auto oit = orphanBuildFrame.find(b.SN);
            int cd = steal ? ORPHAN_STEAL_CD : ORPHAN_REDISPATCH_CD;
            if (oit != orphanBuildFrame.end() && frame - oit->second < cd) continue;
            buildingFarmerType[of->SN] = b.Type;
            builderDispatchFrame[of->SN] = frame;   
            HumanBuild(of->SN, b.Type, (int)b.BlockDR, (int)b.BlockUR);
            orphanBuildFrame[b.SN] = frame;
            if (frame % 60 == 0)
                DebugText(QString("[ORPHAN f=%1] 地基SN=%2 type=%3 percent=%4 补派村民SN=%5%6").arg(frame).arg(b.SN).arg(b.Type).arg(b.Percent).arg(of->SN).arg(steal ? " (抽采集岗)" : ""));
            break;   
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

    
    
    
    
    const bool popHeadroomLowNow = (info.Human_MaxNum - humanPop <= POP_HEADROOM_BUILD);
    const bool canAffordEconNow  = (info.Meat >= 80 && info.Wood >= 50);
    auto tryBuildHouse = [&]() {
        if (!builtThisFrame && houseCount < MAX_HOUSES && !houseBuildingInProgress && popHeadroomLowNow &&
            info.Wood >= BUILD_HOUSE_WOOD)
            builtThisFrame = tryBuild(BUILDING_HOME, 2);
    };
    
    
    
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
            postBronze &&   
            (!requireToolAge || info.civilizationStage >= CIVILIZATION_TOOLAGE) &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 && info.Wood >= BUILD_STABLE_WOOD && !DISABLE_STABLE_BUILD) {
            builtThisFrame = tryBuild(BUILDING_STABLE, 3);
            if (builtThisFrame)
                DebugText(QString("[STABLE f=%1] %2 wood=%3").arg(frame).arg(tag).arg((int)info.Wood));
        }
    };
    
    auto farmWoodNeedNow = [&]() {
        bool cbPending = (postBronze && !compositeBowResearched && !compositeBowQueued && frame < FARM_WAIT_CB_FRAME);
        return FARM_WOOD_NEED(storageNearGazelleBuilt == 1) + (cbPending ? COMPOSITE_BOW_WOOD_RESERVE : 0);
    };
    auto farmerCountNow = [&]() {
        int n = 0;
        for (auto &f : info.farmers) if (f.FarmerSort == FARMERTYPE_FARMER) n++;
        return n;
    };



    auto stockOrderPending = [&](double blkDR, double blkUR) -> bool {
        int nOrd = (int)stockOrderFrame.size();
        for (int i = 0; i < nOrd; ++i)
            if (frame - stockOrderFrame[i] <= STOCK_ORDER_SETTLE &&
                calDistance(blkDR, blkUR, (double)stockOrderDR[i], (double)stockOrderUR[i]) < STOCK_ORDER_MERGE_BLK)
                return true;
        return false;
    };







    bAdd(0, bT0, bNow());
    auto bT1 = bNow();

    if (!builtThisFrame && frame < GAZELLE_STOCK_WINDOW_END &&
        houseCount >= GAZELLE_STOCK_MIN_HOUSES && info.Wood >= BUILD_STOCK_WOOD) {
        const double gBL = (double)BLOCKSIDELENGTH;
        auto gCenter = findBuilding(BUILDING_CENTER);
        double gtcDR = gCenter ? (gCenter->BlockDR + 1) * gBL : -1.0;
        double gtcUR = gCenter ? (gCenter->BlockUR + 1) * gBL : -1.0;
        if (gtcDR >= 0) {
            
            std::vector<tagResource*> gaz;
            for (auto &r : info.resources)
                if (r.Type == RESOURCE_GAZELLE && r.Cnt > 0 &&
                    calDistance(gtcDR, gtcUR, r.DR, r.UR) <= GAZELLE_HUNT_RANGE * gBL)
                    gaz.push_back(&r);
            
            
            
            if (!gaz.empty()) {
                struct Cluster { double dr, ur; int cnt; };
                int N = (int)gaz.size();
                
                std::vector<int> parent(N);
                for (int i = 0; i < N; ++i) parent[i] = i;
                
                for (int i = 0; i < N; ++i)
                    for (int j = i + 1; j < N; ++j)
                        if (calDistance(gaz[i]->DR, gaz[i]->UR, gaz[j]->DR, gaz[j]->UR) < 6 * gBL) {
                            int a = i; while (parent[a] != a) { parent[a] = parent[parent[a]]; a = parent[a]; }
                            int b = j; while (parent[b] != b) { parent[b] = parent[parent[b]]; b = parent[b]; }
                            if (a != b) parent[a] = b;
                        }
                
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
                
                std::sort(clusters.begin(), clusters.end(),
                          [](const Cluster &a, const Cluster &b){ return a.cnt > b.cnt; });

                
                auto clusterCovered = [&](double cdr, double cur) {
                    
                    
                    if (stockOrderPending(cdr / gBL, cur / gBL)) return true;
                    for (auto &b : info.buildings)
                        if (b.Type == BUILDING_STOCK &&
                            calDistance(cdr, cur, (b.BlockDR + 1) * gBL, (b.BlockUR + 1) * gBL)
                                < GAZELLE_HUNT_RANGE * gBL)
                            return true;
                    return false;
                };
                int existingStocks = countBuildingsExisting(BUILDING_STOCK);
                
                for (auto &cl : clusters) {
                    if (builtThisFrame) break;
                    if (info.Wood < BUILD_STOCK_WOOD) break;
                    if (existingStocks >= MAX_STOCK) break;
                    
                    if (clusterCovered(cl.dr, cl.ur)) continue;
                    int tBlockDR = (int)(cl.dr / gBL) - 1;
                    int tBlockUR = (int)(cl.ur / gBL) - 1;
                    
                    if (tryBuild(BUILDING_STOCK, 3, false, tBlockDR, tBlockUR, false, true)) {
                        existingStocks++;
                        builtThisFrame = true;
                        if (frame % 60 == 0)
                            DebugText(QString("[GAZELLE-STOCK f=%1] 群中心块(%2,%3) 群内瞪羚=%4 已建仓=%5/%6 木=%7").arg(frame).arg(tBlockDR).arg(tBlockUR).arg(cl.cnt)
                                      .arg(existingStocks).arg(MAX_STOCK).arg((int)info.Wood));
                    }
                    
                }

                
                
                
                if (countBuildingsExisting(BUILDING_STOCK) >= MAX_STOCK ||
                    clusters.empty()) {
                    storageNearGazelleBuilt = 1;
                } else {
                    bool allCovered = true;
                    for (auto &cl : clusters)
                        if (!clusterCovered(cl.dr, cl.ur)) { allCovered = false; break; }
                    if (allCovered) storageNearGazelleBuilt = 1;
                }
            }   



            else if (frame >= GAZELLE_STOCK_GATE_DEADLINE) {
                storageNearGazelleBuilt = 1;
                if (frame % 300 == 0)
                    DebugText(QString("[GAZELLE-STOCK f=%1] 近场无存活瞪羚 → 兜底解锁农场阈").arg(frame));
            }
        }
    }

    
    
    if (storageNearGazelleBuilt == 0 && frame >= GAZELLE_STOCK_WINDOW_END) {
        storageNearGazelleBuilt = 1;
        DebugText(QString("[GAZELLE-STOCK f=%1] 建造窗口已关 → 硬解锁农场阈").arg(frame));
    }

    
    bAdd(1, bT1, bNow());
    auto bT2 = bNow();
    if (preW1) {
        
        tryBuildHouse();
        
        tryBuildArmyCamp(true);
        
        tryBuildRange(nullptr);
    }

    
    bAdd(2, bT2, bNow());
    auto bT3 = bNow();
    if (postW1) {
        bool rushMilitary = (upgradeStarted && frame < 16500 && !wave2Defeated);  

        

        if (rushMilitary) {
            
            tryBuildArmyCamp(false);
            tryBuildRange(nullptr);
            
            tryBuildHouse();

            
            
            tryBuildGranary(true, true);
            if (!builtThisFrame && canAffordEconNow) tryBuildMarket("rushMilitary 期放行市场");
        } else {
            

            tryBuildGranary(true, true);
            if (!builtThisFrame && canAffordEconNow) tryBuildMarket("postW1 经济期建市场");

            
            tryBuildTower();

            
            tryBuildRange(nullptr);

            
            
            tryBuildStable(true, "postW1 建马厩(学院前置)");

            bool marketReady = (countBuildings(BUILDING_MARKET) >= 1);


        
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

    
    bAdd(3, bT3, bNow());
    auto bT4 = bNow();
    if (postW2) {
        
        tryBuildHouse();

        
        tryBuildGranary(false, false);





        
        
        auto isFarGazelle = [&](const tagResource &r, double tcDRx, double tcURx, double blx,
                                int *pGateHit = nullptr) -> bool {
            if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) return false;
            
            
            if (stockOrderPending(r.DR / blx, r.UR / blx)) {
                if (pGateHit) ++(*pGateHit);
                return false;
            }
            if (calDistance(tcDRx, tcURx, r.DR, r.UR) < 20 * blx) return false;
            
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

        
        if (frame % 300 == 0) {
            
            QString ordTxt;
            for (int i = 0; i < (int)stockOrderFrame.size(); ++i)
                ordTxt += QString("(%1,%2)Δ%3 ").arg(stockOrderDR[i]).arg(stockOrderUR[i]).arg(frame - stockOrderFrame[i]);
            if (ordTxt.isEmpty()) ordTxt = QString("无");
            DebugText(QString("[GATE f=%1] needStock=%2 gazAlive=%3 stock=%4 wood=%5 | market=%6 range=%7 granary=%8 | snGB=%9 | 仓库令落点=%10")
                      .arg(frame).arg(needSecondStock ? 1 : 0).arg(gazelleAlive).arg(countBuildingsExisting(BUILDING_STOCK)).arg((int)info.Wood).arg(countBuildingsExisting(BUILDING_MARKET))
                      .arg(countBuildingsExisting(BUILDING_RANGE)).arg(countBuildingsExisting(BUILDING_GRANARY)).arg(storageNearGazelleBuilt).arg(ordTxt));
        }

        
        
        if (!builtThisFrame && gazelleAlive > 0 &&
            countBuildingsExisting(BUILDING_STOCK) < MAX_STOCK &&
            frame > WAVE2_TIME && info.Wood >= BUILD_STOCK_WOOD + 30) {
            auto center = findBuilding(BUILDING_CENTER);
            double BL = (double)BLOCKSIDELENGTH;
            double tcDR = center ? (center->BlockDR + 1) * BL : 0;
            double tcUR = center ? (center->BlockUR + 1) * BL : 0;
            
            std::vector<std::pair<double,double>> farGaz;
            int gateHit = 0;   
            for (auto &r : info.resources)
                if (isFarGazelle(r, tcDR, tcUR, BL, &gateHit))
                    farGaz.emplace_back(r.DR, r.UR);
            
            if ((int)farGaz.size() >= MIN_GAZELLE_FOR_SECOND_STOCK) {
                
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
                    
                    
                    
                    
                    
                    builtThisFrame = tryBuild(BUILDING_STOCK, 3, false, tBlockDR, tBlockUR, true);
                    
                    if (builtThisFrame)
                        DebugText(QString("[STOCK-ORD f=%1] 第二仓库 群中心块(%2,%3) 远距瞪羚=%4 现存仓=%5/%6 木=%7").arg(frame).arg(tBlockDR).arg(tBlockUR).arg((int)farGaz.size())
                                  .arg(countBuildingsExisting(BUILDING_STOCK)).arg(MAX_STOCK).arg((int)info.Wood));
                    else if (frame % 300 == 0)
                        
                        DebugText(QString("[STOCK-ORD-FAIL f=%1] 群中心块(%2,%3) 远距瞪羚=%4 木=%5 ⇒ tryBuild 失败")
                                  .arg(frame).arg(tBlockDR).arg(tBlockUR).arg((int)farGaz.size()).arg((int)info.Wood));
                }
            }
            
            
            else if (gateHit > 0 && frame % 300 == 0)
                DebugText(QString("[STOCK-SUPPRESS f=%1] 远距瞪羚=%2 < 阈值%3（其中被落点闸挡下 %4 只；落点记忆 %5 条）").arg(frame).arg((int)farGaz.size()).arg(MIN_GAZELLE_FOR_SECOND_STOCK)
                          .arg(gateHit).arg((int)stockOrderFrame.size()));
        }

        
        
        
        
        
        
        
        if (postBronze && frame > WAVE2_TIME) {
            const double BLg = (double)BLOCKSIDELENGTH;
            
            const bool wantGoldEval =
                (frame % 300 == 0) ||
                (!builtThisFrame && info.Wood >= BUILD_STOCK_WOOD + GOLD_STOCK_WOOD_MARGIN);
            if (wantGoldEval) {
                auto gc = findBuilding(BUILDING_CENTER);
                const double tcDRg = gc ? (gc->BlockDR + 1) * BLg : 0;
                const double tcURg = gc ? (gc->BlockUR + 1) * BLg : 0;
                
                std::vector<tagResource *> goldAliveV;
                for (auto &r : info.resources)
                    if (r.Type == RESOURCE_GOLD && r.Cnt > 0) goldAliveV.push_back(&r);
                
                std::vector<tagResource *> farGoldV;
                const int goldAliveN = (int)goldAliveV.size();
                int gateHitG = 0;
                for (auto *r : goldAliveV) {
                    
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
                
                std::vector<std::pair<double,double>> inUse;
                for (auto &fm : info.farmers) {
                    if (fm.WorkObjectSN <= 0) continue;
                    for (auto *r : farGoldV)
                        if (r->SN == fm.WorkObjectSN) { inUse.emplace_back(r->DR, r->UR); break; }
                }
                
                std::vector<std::pair<double,double>> cand;
                if (!inUse.empty())
                    for (auto *r : farGoldV)
                        for (auto &p : inUse)
                            if (calDistance(r->DR, r->UR, p.first, p.second) < 6 * BLg) {
                                cand.emplace_back(r->DR, r->UR); break;
                            }
                
                if (!builtThisFrame && !cand.empty() &&
                    goldStockOrders < MAX_GOLD_STOCK &&
                    countBuildingsExisting(BUILDING_STOCK) < MAX_STOCK + MAX_GOLD_STOCK &&
                    info.Wood >= BUILD_STOCK_WOOD + GOLD_STOCK_WOOD_MARGIN) {
                    
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
                        
                        builtThisFrame = tryBuild(BUILDING_STOCK, 3, false, tGDR, tGUR, true);
                        if (builtThisFrame) {
                            goldStockOrders++;   
                            DebugText(QString("[GOLD-STOCK f=%1] 在用金矿簇心块(%2,%3) 簇内=%4 在用格=%5 远金矿格=%6 金矿仓令=%7/%8 木=%9")
                                      .arg(frame).arg(tGDR).arg(tGUR).arg(bestCnt).arg((int)inUse.size()).arg((int)farGoldV.size()).arg(goldStockOrders).arg(MAX_GOLD_STOCK).arg((int)info.Wood));
                        } else if (frame % 300 == 0)
                            DebugText(QString("[GOLD-STOCK-FAIL f=%1] 在用金矿簇心块(%2,%3) 在用格=%4 远金矿格=%5 木=%6 ⇒ tryBuild 失败").arg(frame).arg(tGDR).arg(tGUR).arg((int)inUse.size())
                                      .arg((int)farGoldV.size()).arg((int)info.Wood));
                    }
                }
                
                if (frame % 300 == 0)
                    DebugText(QString("[GOLD-GATE f=%1] 存活金矿格=%2 远金矿格=%3 在用远金矿格=%4 金矿仓令=%5/%6 被落点闸挡下=%7 木=%8")
                              .arg(frame).arg(goldAliveN).arg((int)farGoldV.size()).arg((int)inUse.size()).arg(goldStockOrders).arg(MAX_GOLD_STOCK).arg(gateHitG).arg((int)info.Wood));
            }
        }

        
        
        if (!builtThisFrame && !needSecondStock && !DISABLE_GRANARY_BUILD &&
            countBuildingsExisting(BUILDING_GRANARY) >= 1 &&
            countBuildingsExisting(BUILDING_GRANARY) < MAX_GRANARY &&
            info.Wood >= BUILD_GRANARY_WOOD) {
            int clX = -1, clY = -1, clCnt = 0;
            if (findRemoteBushCluster(clX, clY, clCnt)) {
                
                builtThisFrame = tryBuild(BUILDING_GRANARY, 3, false, clX, clY, true);
            }
        }

        
        
        if (!builtThisFrame && !(needSecondStock && frame < WAVE3_TIME)) tryBuildMarket("下令建造市场");

        
        if (!builtThisFrame && upgradeStarted) tryBuildArmyCamp(false);

        
        
        if (!builtThisFrame && !(needSecondStock && frame < WAVE3_TIME))
            tryBuildRange("下令建造首座靶场");

        
        tryBuildTower();

        
        if (!builtThisFrame && frame >= WAVE3_TIME &&
            countBuildingsExisting(BUILDING_RANGE) < MAX_RANGES &&
            info.Wood >= BUILD_RANGE_WOOD + 80) {
            builtThisFrame = tryBuild(BUILDING_RANGE, 3);
        }

        
        tryBuildStable(false, "postW2 建马厩(学院前置)");




        if (!builtThisFrame && countBuildingsExisting(BUILDING_COLLAGE) == 0 && !DISABLE_COLLAGE_BUILD &&
            postBronze &&
            (state >= DEFENSE_WAVE3 || frame >= WAVE3_TIME) &&
            countBuildings(BUILDING_ARMYCAMP) >= 1 &&
            countBuildingsExisting(BUILDING_STABLE) >= 1 &&   
            info.Wood >= BUILD_COLLAGE_WOOD + 30) {
            builtThisFrame = tryBuild(BUILDING_COLLAGE, 3);
            if (builtThisFrame)
                DebugText(QString("[COLLAGE f=%1] 建学院(方阵兵产线) wood=%2 state=%3").arg(frame).arg((int)info.Wood).arg((int)state));
        }

        
        
        
        
        
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
            
            DebugText(QString("[FARM-TECHWAIT f=%1] 农场等木材加工科技 wood=%2 meat=%3 farms=%4/%5 mkt=%6").arg(frame).arg((int)info.Wood).arg((int)info.Meat)
                      .arg(countFarmsForCap()).arg(farmTarget).arg(countBuildings(BUILDING_MARKET)));
        }
    }
    bAdd(4, bT4, bNow());

    ++bSamples;
    if (bSamples >= PROF_SAMPLE_FRAMES) {
        const double n = (double)bSamples;
        DebugText(QString("[PROF-BUILD f=%1 n=%2] cleanup=%3/%4 gazelle=%5/%6 preW1=%7/%8 postW1=%9/%10 postW2=%11/%12")
                  .arg(frame).arg(bSamples)
                  .arg(bSum[0]/n, 0, 'f', 3).arg(bMax[0], 0, 'f', 3)
                  .arg(bSum[1]/n, 0, 'f', 3).arg(bMax[1], 0, 'f', 3)
                  .arg(bSum[2]/n, 0, 'f', 3).arg(bMax[2], 0, 'f', 3)
                  .arg(bSum[3]/n, 0, 'f', 3).arg(bMax[3], 0, 'f', 3)
                  .arg(bSum[4]/n, 0, 'f', 3).arg(bMax[4], 0, 'f', 3));
        for (int i = 0; i < 5; ++i) { bSum[i] = 0.0; bMax[i] = 0.0; }
        bSamples = 0;
    }
}




void UsrAI::assignIdleFarmers() {
    frameFoodTargets.clear();  
    frameBushCount.clear();    
    frameWoodCount.clear();    
    frameGazelleCount.clear(); 

    updateFarmTarget();
    managePriestScout();
}




void UsrAI::updateFarmTarget() {
    
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

    
    if (nearBushFood > 0) {
        
        farmTarget = 0;
    } else if (!marketBuilt) {
        farmTarget = 0;
    } else if (frame < 7500 && totalWildFood > 300) {
        
        farmTarget = 0;
    } else {
        
        farmTarget = (totalWildFood < 300 || info.Meat < 200) ? MAX_FARMS : 0;
    }

}






void UsrAI::managePriestScout() {
    
    bool isWar = (state >= DEFENSE_WAVE1 && state <= DEFENSE_WAVE3);
    if (!isWar && state != COUNTERATTACK && scoutPhase < 16) {
        double BL = (double)BLOCKSIDELENGTH;

        
        
        auto beastOnPathAhead = [&](double sDR, double sUR, double wx, double wy) -> bool {
            double pathDX = wx - sDR, pathDY = wy - sUR;
            double pathLen = std::sqrt(pathDX*pathDX + pathDY*pathDY);
            if (pathLen <= 0.01) return false;
            for (auto &r : info.resources) {
                if (r.Cnt <= 0) continue;
                if (r.Type != RESOURCE_ELEPHANT) continue;
                double t = ((r.DR - sDR)*pathDX + (r.UR - sUR)*pathDY) / (pathLen*pathLen);
                if (t < 0 || t * pathLen > 8 * BL) continue;   
                if (t > 1) t = 1;
                double nearX = sDR + t * pathDX;
                double nearY = sUR + t * pathDY;
                if (calDistance(r.DR, r.UR, nearX, nearY) < 1.5 * BL) return true;
            }
            return false;
        };

        
        const int SCOUT_RETURN_RADII[3] = {4, 7, 10};   
        const int SCOUT_RETURN_ANGLES = 8;
        const int SCOUT_RETURN_MAX = SCOUT_RETURN_ANGLES * 3;  
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

        
        
        if (scoutDirsDone >= 8) {
            scoutPhase = 20;  
        }

        
        if (priestSN != -1) {
            bool alive = false;
            for (auto &a : info.armies) {
                if (a.SN == priestSN && a.Sort == AT_PRIEST) {
                    alive = true; break;
                }
            }
            if (!alive) { priestSN = -1; scoutWalkTimer = 0; }
        }

        
        if (priestSN == -1) {
            scoutPhase = 20;  
        }

        
        if (priestSN != -1 && scoutPhase < 16) {
            tagArmy* scout = nullptr;
            for (auto &a : info.armies) {
                if (a.SN == priestSN) { scout = &a; break; }
            }

            
            
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

            
            bool fledThisFrame = false;
            if (scout) {
                auto center = findBuilding(BUILDING_CENTER);
                double tcDR = center ? (center->BlockDR + 1) * BL : scout->DR;
                double tcUR = center ? (center->BlockUR + 1) * BL : scout->UR;

                double beastDist = 12 * BL, beastX = scout->DR, beastY = scout->UR;
                bool beastNearby = false;
                double enemyDist = 12 * BL;
                bool enemyNearby = false;

                
                for (auto &r : info.resources) {
                    if (r.Cnt <= 0) continue;
                    if (r.Type != RESOURCE_ELEPHANT) continue;
                    double d = calDistance(scout->DR, scout->UR, r.DR, r.UR);
                    if (d < beastDist) { beastDist = d; beastX = r.DR; beastY = r.UR; beastNearby = true; }
                }
                
                for (auto &e : info.enemy_armies) {
                    if (e.Blood <= 0) continue;
                    double d = calDistance(scout->DR, scout->UR, e.DR, e.UR);
                    if (d < enemyDist) { enemyDist = d; enemyNearby = true; }
                }
                
                for (auto &e : info.enemy_farmers) {
                    if (e.Blood <= 0) continue;
                    double d = calDistance(scout->DR, scout->UR, e.DR, e.UR);
                    if (d < beastDist) { beastDist = d; beastX = e.DR; beastY = e.UR; beastNearby = true; }
                }

                if (scout->NowState != HUMAN_STATE_WALKING) {
                    if (enemyNearby) {
                        
                        double rx = 0, ry = 0;
                        scoutReturnPoint(scoutReturnTry, tcDR, tcUR, rx, ry);
                        HumanMove(scout->SN, rx, ry);
                        scoutIssueDR = scout->DR; scoutIssueUR = scout->UR; scoutIssueFrame = frame;
                        scoutPhase++;
                        if (scoutPhase >= 16) scoutPhase = 20;  
                        scoutReturnTry = 0;
                        scoutCooldown = 20;
                        scoutWalkTimer = 0;
                        fledThisFrame = true;
                    } else if (beastNearby) {
                        
                        scoutStepAwayFrom(beastX, beastY);
                        fledThisFrame = true;
                    }
                }
            }

            if (!fledThisFrame) {
            if (scoutCooldown > 0) {   }
            else {
            
            if (scout) {
                if (scout->NowState == HUMAN_STATE_WALKING) scoutWalkTimer++;
                else scoutWalkTimer = 0;
            }
            
            
            double scoutIssueMoved = calDistance(scout->DR, scout->UR, scoutIssueDR, scoutIssueUR);
            bool noProgress = (scoutIssueFrame > -999999) && (frame - scoutIssueFrame > 20) && (scoutIssueMoved < 1.0 * BL);
            bool scoutStuck = (scoutWalkTimer > 1200 || noProgress ||
                               (scoutLegStartFrame > 0 && frame - scoutLegStartFrame > 2000));

            if (scoutStuck) {
                bool stuckInReturn = (scoutPhase % 2 == 1);  
                if (stuckInReturn && scoutReturnTry + 1 < SCOUT_RETURN_MAX) {
                    
                    scoutReturnTry++;
                    scoutWalkTimer = 0;
                    scoutLegStartFrame = frame;
                    scoutCooldown = 5;
                } else if (stuckInReturn) {
                    
                    scoutPhase = 20;
                    scoutReturnTry = 0;
                    priestNearTCTry = 0;  
                    scoutWalkTimer = 0;
                    scoutIssueFrame = -999999;  
                    scoutCooldown = 10;
                } else if (scoutReturnTry + 1 < 8) {
                    
                    scoutReturnTry++;
                    scoutWalkTimer = 0;
                    scoutLegStartFrame = frame;
                    scoutCooldown = 5;
                } else {
                    
                    scoutPhase++;
                    if (scoutPhase >= 16) scoutPhase = 20;  
                    scoutReturnTry = 0;
                    scoutWalkTimer = 0;
                    scoutLegStartFrame = frame;
                    scoutCooldown = 10;
                }
            } else if (scout && (scout->NowState == HUMAN_STATE_ATTACKING || scout->NowState == HUMAN_STATE_WORKING)) {
                
                double fleeX = scout->DR, fleeY = scout->UR;
                double nearestDist = 1e12;
                
                for (auto &r : info.resources) {
                    if (r.Cnt <= 0) continue;
                    if (r.Type != RESOURCE_ELEPHANT) continue;
                    double d = calDistance(scout->DR, scout->UR, r.DR, r.UR);
                    if (d < nearestDist) { nearestDist = d; fleeX = r.DR; fleeY = r.UR; }
                }
                
                for (auto &e : info.enemy_armies) {
                    if (e.Blood <= 0) continue;
                    double d = calDistance(scout->DR, scout->UR, e.DR, e.UR);
                    if (d < nearestDist) { nearestDist = d; fleeX = e.DR; fleeY = e.UR; }
                }
                
                for (auto &e : info.enemy_farmers) {
                    if (e.Blood <= 0) continue;
                    double d = calDistance(scout->DR, scout->UR, e.DR, e.UR);
                    if (d < nearestDist) { nearestDist = d; fleeX = e.DR; fleeY = e.UR; }
                }
                
                scoutStepAwayFrom(fleeX, fleeY);
            } else if (scout && scout->NowState == HUMAN_STATE_IDLE) {
                auto center = findBuilding(BUILDING_CENTER);
                if (center) {
                    double baseDR = (center->BlockDR + 1) * BL;
                    double baseUR = (center->BlockUR + 1) * BL;
                    double sDR = scout->DR, sUR = scout->UR;

                    
                    double edgeWest  = 0;
                    double edgeEast  = MAP_L * BL;
                    double edgeSouth = 0;
                    double edgeNorth = MAP_U * BL;

                    bool nearTarget = false;
                    const double SCOUT_DIST = SCOUT_MAX_DIST;  

                    
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

                    
                    double range[8];
                    range[0] = distWest;
                    range[1] = (distWest  < distSouth ? distWest  : distSouth) * 1.414;
                    range[2] = distSouth;
                    range[3] = (distEast  < distSouth ? distEast  : distSouth) * 1.414;
                    range[4] = distEast;
                    range[5] = (distEast  < distNorth ? distEast  : distNorth) * 1.414;
                    range[6] = distNorth;
                    range[7] = (distWest  < distNorth ? distWest  : distNorth) * 1.414;

                    
                    int dirOrder[8];
                    bool used[8] = {false};
                    int di = 0;
                    auto addDir = [&](int d) { if (!used[d]) { dirOrder[di++] = d; used[d] = true; } };
                    if (nearWest && nearNorth) {
                        addDir(4); addDir(3);  
                    } else if (nearWest && nearSouth) {
                        addDir(6); addDir(4);  
                    } else if (nearEast && nearSouth) {
                        addDir(6); addDir(0);  
                    } else if (nearEast && nearNorth) {
                        addDir(0); addDir(1);  
                    }
                    
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
                            
                            double dirX[8] = {-1, -1,  0,  1, 1, 1, 0, -1};
                            double dirY[8] = { 0, -1, -1, -1, 0, 1, 1,  1};
                            bool isDiag = (dir % 2 == 1);
                            double dist = SCOUT_DIST * BL;
                            if (isDiag) dist *= 0.707;  

                            double dx = dirX[dir], dy = dirY[dir];
                            
                            double gx = baseDR + dx * dist;
                            double gy = baseUR + dy * dist;
                            gx = max(edgeWest, min(edgeEast, gx));
                            gy = max(edgeSouth, min(edgeNorth, gy));
                            
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

                            
                            bool dangerNearby = false;
                            for (auto &r : info.resources) {
                                if (r.Cnt <= 0) continue;
                                if (r.Type != RESOURCE_ELEPHANT) continue;
                                if (calDistance(wx, wy, r.DR, r.UR) < 12 * BL) { dangerNearby = true; break; }
                            }
                            if (!dangerNearby) dangerNearby = beastOnPathAhead(sDR, sUR, wx, wy);

                            if (nearTarget || dangerNearby) {
                                if (nearTarget) scoutDirsDone++;
                                scoutReturnTry = 0;  
                                scoutPhase++;  
                                scoutCooldown = 10;
                            } else {
                                
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
                                
                                
                                if (calDistance(sDR, sUR, scoutIssueDR, scoutIssueUR) > 1.0 * BL) {
                                    scoutIssueDR = sDR; scoutIssueUR = sUR; scoutIssueFrame = frame;
                                    scoutLegStartFrame = frame;
                                    scoutWalkTimer = 0;
                                }
                                scoutCooldown = 15;
                            }
                    } else {
                        
                        double wx = 0, wy = 0;
                        scoutReturnPoint(scoutReturnTry, baseDR, baseUR, wx, wy);
                        nearTarget = (calDistance(sDR, sUR, wx, wy) < 7 * BL) ||
                                     (calDistance(sDR, sUR, baseDR, baseUR) < 8 * BL);

                        
                        bool dangerNearby = beastOnPathAhead(sDR, sUR, wx, wy);

                        if (nearTarget || dangerNearby) {
                            scoutReturnTry = 0;  
                            scoutPhase++;  
                            if (scoutPhase >= 16) scoutPhase = 20;  
                            scoutCooldown = 10;
                        } else {
                            HumanMove(scout->SN, wx, wy);
                            
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
            } 
            }
        }
    }
}





void UsrAI::countFarmerWorkKinds(int &goldWorkers, int &woodWorkers, int &stoneWorkers, int &foodWorkers) const {
    goldWorkers = woodWorkers = stoneWorkers = foodWorkers = 0;
    
    
    
    
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        
        int kind = 0;   
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
        
        if (kind == 0) {
            if (f.ResourceSort == HUMAN_GOLD) kind = 1;
            else if (f.ResourceSort == HUMAN_WOOD) kind = 2;
            else if (f.ResourceSort == HUMAN_STONE) kind = 3;
            else if (f.ResourceSort == HUMAN_GRANARYFOOD || f.ResourceSort == HUMAN_STOCKFOOD) kind = 4;
        }
        
        if (kind == 1) goldWorkers++;
        else if (kind == 2) woodWorkers++;
        else if (kind == 3) stoneWorkers++;
        else if (kind == 4) foodWorkers++;
    }

}

namespace {
struct TreeReassignState {
    int treeSN;
    int lastFrame;
    double lastDR;
    double lastUR;
    int count;
};
std::mutex g_treeReassignMutex;
std::map<const UsrAI*, std::map<int, TreeReassignState>> g_treeReassign;
}

void UsrAI::assignIdleSimple() {
    std::map<int,int> assignedBush;
    std::map<int,int> assignedGazelle;
    std::map<int,int> assignedFarm;   
    double BL = (double)BLOCKSIDELENGTH;

    
    auto issueTreeOrder = [&](tagFarmer &f, tagResource* tree) -> bool {
        if (!tree) return false;
        bool blacklist = false;
        {
            std::lock_guard<std::mutex> lock(g_treeReassignMutex);
            TreeReassignState &st = g_treeReassign[this][f.SN];
            const bool same = (st.treeSN == tree->SN && frame - st.lastFrame <= TREE_REASSIGN_WINDOW);
            const double moved = calDistance(f.DR, f.UR, st.lastDR, st.lastUR);
            if (same && moved < 8.0 * (double)BLOCKSIDELENGTH) {
                st.count++;
            } else {
                st.treeSN = tree->SN;
                st.count = 1;
            }
            st.lastFrame = frame;
            st.lastDR = f.DR;
            st.lastUR = f.UR;
            if (st.count > TREE_REASSIGN_MAX) {
                st = TreeReassignState{-1, -999999, 0.0, 0.0, 0};
                blacklist = true;
            }
        }
        if (blacklist) {
            stuckResourceUntil[tree->SN] = frame + TREE_REASSIGN_BLACKLIST_FRAMES;
            villLastTreeSN.erase(f.SN);
            DebugText(QString("[TREE-BLACKLIST f=%1] farmer=%2 tree=%3").arg(frame).arg(f.SN).arg(tree->SN));
            return false;
        }
        HumanAction(f.SN, tree->SN);
        villLastTreeSN[f.SN] = tree->SN;
        return true;
    };
    
    const int woodTarget = (info.Wood < WOOD_LOW_LINE) ? WOOD_TARGET_LOW : WOOD_TARGET_BASE;
    auto center = findBuilding(BUILDING_CENTER);
    double tcDR = center ? (center->BlockDR + 1) * BL : 0;
    double tcUR = center ? (center->BlockUR + 1) * BL : 0;

    
    
    std::vector<std::pair<double,double>> builtGranaries;
    for (auto &b : info.buildings)
        if (b.Type == BUILDING_GRANARY && b.Percent == 100)
            builtGranaries.push_back({(b.BlockDR + 1.0) * BL, (b.BlockUR + 1.0) * BL});

    int goldWorkers = 0, woodWorkers = 0, stoneWorkers = 0, foodWorkers = 0;
    static double statSum = 0.0, statMax = 0.0;
    static int statSamples = 0;
    auto _statT0 = std::chrono::steady_clock::now();
    countFarmerWorkKinds(goldWorkers, woodWorkers, stoneWorkers, foodWorkers);
    double _statMs = std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - _statT0).count();
    statSum += _statMs;
    if (_statMs > statMax) statMax = _statMs;
    if (++statSamples >= PROF_SAMPLE_FRAMES) {
        DebugText(QString("[PROF-STAT f=%1 n=%2 count=%3/%4")
                  .arg(frame).arg(statSamples)
                  .arg(statSum / statSamples, 0, 'f', 3)
                  .arg(statMax, 0, 'f', 3));
        statSum = 0.0; statMax = 0.0; statSamples = 0;
    }

    
    const bool woodStop  = (info.Wood >= (frame >= WAVE3_TIME ? WOOD_CAP_STOP_LATE : WOOD_CAP_STOP));
    
    
    
    
    
    
    const bool towersDone = (countBuildings(BUILDING_ARROWTOWER) >= MAX_TOWERS);
    const bool stoneStop = (frame >= WAVE3_TIME) || (info.Stone >= STONE_CAP_STOP) || towersDone;
    
    
    
    
    
    
    
    const bool goldRich =
        (info.Gold >= GOLD_CAP_STOP) ||
        ((double)info.Gold > (double)(info.Meat + 50) * (double)FOOD_GOLD_DEN
                             / (double)FOOD_GOLD_NUM * GOLD_RICH_TOL);
    
    const bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
    
    
    
    const bool foodStop = (info.Meat >= (postBronze ? FOOD_CAP_STOP : FOOD_CAP_STOP_PREBRONZE));
    
    
    
    
    int goldTarget = (!postBronze) ? 0
        : goldRich ? MIN_GOLD_WORKERS
        : std::max(MIN_GOLD_WORKERS,
                   (int)((double)foodWorkers * FOOD_GOLD_DEN / FOOD_GOLD_NUM + 0.999));

    
    
    
    
    
    std::set<int> elephantPartyPending;   
    {
        std::vector<int> elePool;         
        for (size_t i = 0; i < info.farmers.size(); ++i) {
            auto &g = info.farmers[i];
            if (g.FarmerSort != FARMERTYPE_FARMER) continue;
            if (g.Resource > 0) continue;                             
            if (g.NowState != HUMAN_STATE_IDLE) continue;              
            if (buildingFarmerType.count(g.SN)) continue;
            elePool.push_back((int)i);
        }
        
        bool bushGazelleFull = true;
        for (auto &r : info.resources) {
            if (r.Cnt <= 0) continue;
            if (r.Type != RESOURCE_BUSH && r.Type != RESOURCE_GAZELLE) continue;
            double lim = (r.Type == RESOURCE_BUSH) ? 30.0 : (double)GAZELLE_HUNT_RANGE;
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > lim * BL) continue;
            int on = countFarmersOnTarget(r.SN);
            if (on < ((r.Type == RESOURCE_BUSH) ? 3 : 2)) { bushGazelleFull = false; break; }
        }
        
        
        bool laborFull = bushGazelleFull
                      && (woodStop  || woodWorkers  >= woodTarget)
                      && (goldWorkers >= goldTarget)
                      && (stoneStop || stoneWorkers >= STONE_WORKERS_LATE);
        
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
            if (bit != elephantBanUntil.end() && frame < bit->second) continue;   
            int on = countFarmersOnTarget(r.SN);
            if (on >= ELEPHANT_HUNT_GROUP) continue;                    
            if (on < ELEPHANT_HUNT_MIN) {
                if (on == 0 && (foodStop || !laborFull)) continue;   
                int need = ELEPHANT_HUNT_MIN - on;
                if ((int)elePool.size() < need) {
                    
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
                if (foodStop) continue;                                  
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
        if (elephantPartyPending.count(f.SN)) continue;   

        
        if (!woodStop && woodWorkers < woodTarget) {
            auto treeFirst = findBestWoodTree(f.DR, f.UR);
            if (treeFirst && issueTreeOrder(f, treeFirst)) {
                woodWorkers++;
                continue;
            }
        }

        
        if (goldWorkers < goldTarget) {
            auto gold = findNearestResource(RESOURCE_GOLD, f.DR, f.UR);
            if (gold) {
                HumanAction(f.SN, gold->SN);
                goldWorkers++;
                continue;
            }
        }




        if (!stoneStop &&
            stoneWorkers < STONE_WORKERS_LATE) {
            auto stoneR = findNearestResource(RESOURCE_STONE, f.DR, f.UR);
            if (stoneR) {
                HumanAction(f.SN, stoneR->SN);
                stoneWorkers++;
                continue;
            }
        }

        
        
        if (foodStop) {
            if (!woodStop) {
                auto tree = findBestWoodTree(f.DR, f.UR);
                if (tree && issueTreeOrder(f, tree)) { woodWorkers++; continue; }
            }
            continue;  
        }

        tagResource* bestBush = nullptr;
        double bestBushScore = 1e12;
        for (auto &r : info.resources) {
            if (r.Type != RESOURCE_BUSH || r.Cnt <= 0) continue;
            
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
            
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > GAZELLE_HUNT_RANGE * BL) continue;
            int onGazelle = countFarmersOnTarget(r.SN);
            if (onGazelle + assignedGazelle[r.SN] >= 2) continue;
            double d = dist2(r.DR, r.UR, f.DR, f.UR);
            if (d < bestGazelleDist) { bestGazelleDist = d; bestGazelle = &r; }
        }
        
        if (bestGazelle && gazelleDropoffReady(bestGazelle)) {
            HumanAction(f.SN, bestGazelle->SN);
            assignedGazelle[bestGazelle->SN]++;
            frameGazelleCount[bestGazelle->SN]++;
            continue;
        }

        
        

        
        tagBuilding* farm = nullptr;
        for (auto &b : info.buildings) {
            if (b.Type != BUILDING_FARM || b.Percent < 100) continue;
            if (assignedFarm.count(b.SN)) continue;        
            int onFarm = countFarmersOnTarget(b.SN);
            if (onFarm >= 1) continue;                     
            farm = &b; break;
        }
        if (farm) {
            HumanAction(f.SN, farm->SN);
            assignedFarm[farm->SN] = f.SN;                 
            frameFoodTargets.insert(farm->SN);
            continue;
        }

        
        
        
        
        
        auto goldRes = findNearestResource(RESOURCE_GOLD, f.DR, f.UR);
        if (goldRes && goldWorkers < goldTarget) {
            HumanAction(f.SN, goldRes->SN); goldWorkers++;
        } else {
            auto tree = findBestWoodTree(f.DR, f.UR);
            if (tree && issueTreeOrder(f, tree)) {
                woodWorkers++;
            }
        }
    }

    
    
    
    
    
    
    
    
    const bool goldDeficit = (postBronze && !goldRich && goldWorkers < goldTarget);
    if (goldDeficit && frame % FOOD_GOLD_REBALANCE_INTERVAL == 0 &&
        foodWorkers > FOOD_REBALANCE_KEEP) {
        for (auto &f : info.farmers) {
            if (f.FarmerSort != FARMERTYPE_FARMER) continue;
            if (f.NowState != HUMAN_STATE_WORKING && f.NowState != HUMAN_STATE_WALKING) continue;

            bool isFood = (f.ResourceSort == HUMAN_GRANARYFOOD || f.ResourceSort == HUMAN_STOCKFOOD);
            bool onFarm = false;
            if (f.WorkObjectSN > 0) {
                if (!isFood) {
                    for (auto &r : info.resources)
                        if (r.SN == f.WorkObjectSN) {
                            if (r.Type == RESOURCE_BUSH || r.Type == RESOURCE_GAZELLE ||
                                r.Type == RESOURCE_ELEPHANT) isFood = true;
                            break;
                        }
                }
                for (auto &b : info.buildings)
                    if (b.SN == f.WorkObjectSN && b.Type == BUILDING_FARM) {
                        isFood = true; onFarm = true; break;
                    }
            }
            if (!isFood) continue;
            
            if (onFarm && foodWorkers <= FOOD_REBALANCE_KEEP + 4) continue;

            auto g = findNearestResource(RESOURCE_GOLD, f.DR, f.UR);
            if (g) {
                HumanAction(f.SN, g->SN);
                foodWorkers--; goldWorkers++;
                DebugText(QString("[GOLD-REBAL f=%1] farmer=%2 food=%3 gold=%4 target=%5")
                          .arg(frame).arg(f.SN).arg(foodWorkers).arg(goldWorkers).arg(goldTarget));
                break;
            }
        }
    }

    if ((woodStop || stoneStop || goldRich || foodStop) && frame % 10 == 0) {
        const bool woodHungry = (info.Wood < WOOD_LOW_LINE);
        for (auto &f : info.farmers) {
            if (f.FarmerSort != FARMERTYPE_FARMER) continue;
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
            
            
            
            
            
            
            auto reassignToDeficit = [&](tagFarmer &w, int fromKind)->bool {
                
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
                
                
                
                if (goldWorkers < goldTarget) {
                    auto g = findNearestResource(RESOURCE_GOLD, w.DR, w.UR);
                    if (g) { HumanAction(w.SN, g->SN); commit(1); return true; }
                }
                if (woodHungry) {
                    auto t = findBestWoodTree(w.DR, w.UR);
                    if (t && issueTreeOrder(w, t)) { commit(2); return true; }
                }
                if (tryAssignFood(&w)) { commit(4); return true; }
                if (!woodStop) {                          
                    auto t2 = findBestWoodTree(w.DR, w.UR);
                    if (t2 && issueTreeOrder(w, t2)) { commit(2); return true; }
                }
                return false;
            };

            bool reassigned = false;
            if (foodStop && isFood) {
                
                
                
                bool onFarm = false;
                for (auto &b : info.buildings)
                    if (b.SN == f.WorkObjectSN && b.Type == BUILDING_FARM) { onFarm = true; break; }
                if (onFarm) continue;



                auto t = findBestWoodTree(f.DR, f.UR);
                if (t && !woodStop && issueTreeOrder(f, t)) {
                    foodWorkers--; woodWorkers++;           
                    reassigned = true;
                } else {
                    auto g = findNearestResource(RESOURCE_GOLD, f.DR, f.UR);
                    if (g && postBronze && !goldRich) {
                        HumanAction(f.SN, g->SN);
                        foodWorkers--; goldWorkers++;       
                        reassigned = true;
                    }
                }
            } else if (stoneStop && isStone) {
                
                reassigned = reassignToDeficit(f, 3);
            } else if (goldRich && isGold && goldWorkers > MIN_GOLD_WORKERS) {
                
                reassigned = reassignToDeficit(f, 1);
            } else if (woodStop && isWood && woodWorkers > WOOD_KEEP_MIN) {



                reassigned = reassignToDeficit(f, 2);
            }
            if (reassigned) break;  
        }
    }

    
    if (frame % 600 == 0) {
        DebugText(QString("ECO | Fd:%1 Wd:%2 St:%3 Gd:%4 || workers F%5 W%6 G%7 S%8 || goldRich:%9 woodStop:%10 stoneStop:%11 foodStop:%12 woodTarget:%13 twr:%14/%15")
                  .arg((int)info.Meat).arg((int)info.Wood).arg((int)info.Stone).arg((int)info.Gold).arg(foodWorkers).arg(woodWorkers).arg(goldWorkers).arg(stoneWorkers)
                  .arg(goldRich ? 1 : 0).arg(woodStop ? 1 : 0).arg(stoneStop ? 1 : 0).arg(foodStop ? 1 : 0).arg(woodTarget).arg(countBuildingsExisting(BUILDING_ARROWTOWER)).arg(MAX_TOWERS));
    }

    
    
    {
        std::map<int, std::vector<int>> fwMap;   
        for (auto &b : info.buildings)
            if (b.Type == BUILDING_FARM && b.Percent >= 100) fwMap[b.SN];
        for (auto &f : info.farmers) {
            if (f.FarmerSort != FARMERTYPE_FARMER) continue;
            if (f.WorkObjectSN > 0 && fwMap.count(f.WorkObjectSN))
                fwMap[f.WorkObjectSN].push_back(f.SN);
        }
        for (auto &kv : assignedFarm)            
            if (fwMap.count(kv.first)) fwMap[kv.first].push_back(kv.second);

        std::vector<int> emptyFarms;
        for (auto &kv : fwMap) if ((int)kv.second.size() == 0) emptyFarms.push_back(kv.first);

        for (auto &kv : fwMap) {
            auto &workers = kv.second;
            if ((int)workers.size() <= 1) continue;   
            
            for (size_t i = 1; i < workers.size(); ++i) {
                int wSN = workers[i];
                tagFarmer* wf = nullptr;
                for (auto &f : info.farmers) if (f.SN == wSN) { wf = &f; break; }
                if (!wf) continue;
                
                if (wf->NowState != HUMAN_STATE_IDLE && wf->NowState != HUMAN_STATE_WORKING
                    && wf->NowState != HUMAN_STATE_WALKING) continue;
                if (!emptyFarms.empty()) {
                    int dst = emptyFarms.back(); emptyFarms.pop_back();
                    HumanAction(wSN, dst);            
                } else if (woodWorkers < woodTarget) {
                    auto tree = findBestWoodTree(wf->DR, wf->UR);
                    if (tree && issueTreeOrder(*wf, tree)) { woodWorkers++; }
                    else break;
                } else break;                          
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

    
    int bushFood = 0;
    for (auto &r : info.resources)
        if (r.Type == RESOURCE_BUSH && r.Cnt > 0)
            if (calDistance(tcDR, tcUR, r.DR, r.UR) < 30 * BL) bushFood += r.Cnt;
    
    for (auto it = huntingGroup.begin(); it != huntingGroup.end(); ) {
        bool still = false;
        for (auto &f : info.farmers)
            if (f.SN == *it && f.NowState == HUMAN_STATE_ATTACKING) { still = true; break; }
        if (!still) it = huntingGroup.erase(it); else ++it;
    }

    if (bushFood > 400) return;  

    
    tagResource* bestGazelle = nullptr;
    double bestDist = 1e12;
    for (auto &r : info.resources) {
        if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) continue;
        double d = calDistance(tcDR, tcUR, r.DR, r.UR);
        if (d >= GAZELLE_HUNT_RANGE * BL) continue;
        int realCount = countFarmersOnTarget(r.SN);
        if (realCount >= 2) continue;  
        if (d < bestDist) { bestDist = d; bestGazelle = &r; }
    }
    if (!bestGazelle) return;

    
    if (!gazelleDropoffReady(bestGazelle)) {
        if (frame % 300 == 0)
            DebugText(QString("[GAZELLE f=%1] 暂缓打猎：等猎场仓库落地 (目标SN=%2)").arg(frame).arg(bestGazelle->SN));
        return;
    }

    
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN)) continue;
        if (huntingGroup.count(f.SN)) continue;  
        if (f.Resource > 0) continue;
        if (f.NowState != HUMAN_STATE_IDLE) continue;  

        HumanAction(f.SN, bestGazelle->SN);
        huntingGroup.insert(f.SN);
        return;  
    }
}
void UsrAI::manageTechUpgrade() {
    if (techCooldown > 0) return;
    if (info.Meat < FOOD_PAUSE_TECH_TRAIN) return;

    bool done = false;
    bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
    
    
    
    
    
    
    
    
    if (!DISABLE_MARKET_WOOD_TECH && !done && !marketWoodUpgraded) {
        auto mw = findBuilding(BUILDING_MARKET);
        if (mw && mw->Project == ACT_NULL && info.Meat >= 120 && info.Wood >= 75) {
            bool bowPending = (!compositeBowResearched && !compositeBowQueued);
            bool okToGo = true;
            if (bowPending && !WOOD_TECH_ABSOLUTE_FIRST) {
                
                
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

    
    if (!marketWoodUpgraded && frame % 100 == 0) {
        auto mwd = findBuilding(BUILDING_MARKET);
        int mktProj = -9;
        if (mwd) mktProj = (int)mwd->Project;
        DebugText(QString("[WP f=%1] mkt=%2 proj=%3 meat=%4 wood=%5 bowPend=%6 abs=%7").arg(frame).arg(mwd ? 1 : 0).arg(mktProj).arg((int)info.Meat).arg((int)info.Wood)
            .arg((!compositeBowResearched && !compositeBowQueued) ? 1 : 0).arg(WOOD_TECH_ABSOLUTE_FIRST ? 1 : 0));
    }


    
    
    
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

    
    
    if (!done && !towerTechResearched) {
        auto g = findBuilding(BUILDING_GRANARY);
        if (g && g->Project == BUILDING_GRANARY_ARROWTOWER) {
            towerTechResearched = true;  
        } else if (g && g->Project == ACT_NULL && info.Meat >= 50) {
            BuildingAction(g->SN, BUILDING_GRANARY_ARROWTOWER);
            towerTechResearched = true;
            techCooldown = 25;
            return;
        }
    }

    
    if (!postBronze) return;

    
    if (!broadswordResearched) {
        auto ac = findBuildingIncludingUnderConstruction(BUILDING_ARMYCAMP);
        if (ac && ac->Project == BUILDING_ARMYCAMP_UPGRADE_BROADSWORD) {
            broadswordResearched = true;  
        } else if (broadswordQueued && ac && ac->Project == ACT_NULL) {
            
            broadswordResearched = true;
        }
    }
    if (!compositeBowResearched) {
        auto rng = findBuildingIncludingUnderConstruction(BUILDING_RANGE);
        if (rng && rng->Project == BUILDING_RANGE_UPGRADE_COMPOSITE_BOW) {
            compositeBowResearched = true;
        } else if (compositeBowQueued && rng && rng->Project == ACT_NULL) {
            compositeBowQueued = false;   
        }
    }

    
    
    
    
    
    
    
    
    
    
    
    
    if (!done && !compositeBowResearched && !compositeBowQueued) {
        auto r = findBuilding(BUILDING_RANGE);
        
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

    
    tryArrowTowerTech();
    tryBronzeTowerUpgrade();

    
    
    
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

    

    
    if (!DISABLE_USETOOL_TECH && !done && !useToolDone && info.Meat >= 100) {
        auto s = findBuilding(BUILDING_STOCK);
        if (s && s->Project == ACT_NULL) {
            BuildingAction(s->SN, BUILDING_STOCK_UPGRADE_USETOOL);
            useToolDone = true; done = true;
        }
    }

    
    
    
    
    if (!done) {



        tagBuilding *armSt = nullptr;
        
        if (armorStockSN >= 0) {
            for (auto &b : info.buildings)
                if (b.Type == BUILDING_STOCK && b.SN == armorStockSN) { armSt = &b; break; }
        }
        
        if (!armSt) {
            armorStockSN = -1;   
            for (auto &b : info.buildings)
                if (b.Type == BUILDING_STOCK && b.Percent == 100 && b.Project == ACT_NULL) {
                    armSt = &b; armorStockSN = b.SN; break;
                }
        }
        if (armSt) {
            
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
                    armorStockSN = -1;   
                }
            }
            
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
            
            int curStockProj = (int)armSt->Project;
            if (prevStockProject != ACT_NULL && curStockProj == ACT_NULL) {
                DebugText(QString("[ARMOR-DONE f=%1] 上一条仓库科技完成(prevID=%2) meat=%3 gold=%4 infLvl=%5 arcLvl=%6").arg(frame).arg(prevStockProject).arg((int)info.Meat).arg((int)info.Gold)
                    .arg(infArmorLevel).arg(arcArmorLevel));
            }
            prevStockProject = curStockProj;
        }
    }

    
    tryArrowTowerTech();
    tryBronzeTowerUpgrade();

    
    
    
    
    

    
    if (!DISABLE_MARKET_TECH && !done && !marketFarmUpgraded) {
        auto m = findBuilding(BUILDING_MARKET);
        if (m && m->Project == ACT_NULL && info.Meat >= 200 && info.Wood >= 50) {
            BuildingAction(m->SN, BUILDING_MARKET_FARM_UPGRADE);
            marketFarmUpgraded = true; done = true;
        }
    }

    
    if (!DISABLE_MARKET_TECH && !done && !wheelResearched) {
        auto m = findBuilding(BUILDING_MARKET);
        if (m && m->Project == ACT_NULL && info.Meat >= 150 && info.Wood >= 100) {
            BuildingAction(m->SN, BUILDING_MARKET_WHEEL_UPGRADE);
            wheelResearched = true; done = true;
        }
    }

    
    if (!DISABLE_MARKET_TECH && !done && !marketPlowUpgraded) {
        auto m = findBuilding(BUILDING_MARKET);
        if (m && m->Project == ACT_NULL && info.Meat >= 250 && info.Wood >= 75) {
            BuildingAction(m->SN, BUILDING_MARKET_PLOW_UPGRADE);
            marketPlowUpgraded = true; done = true;
        }
    }

    
    if (!DISABLE_MARKET_TECH && !done && !craftResearched) {
        auto m = findBuilding(BUILDING_MARKET);
        if (m && m->Project == ACT_NULL && info.Meat >= 170 && info.Wood >= 150) {
            BuildingAction(m->SN, BUILDING_MARKET_CRAFT_UPGRADE);
            craftResearched = true; done = true;
        }
    }

    if (done) techCooldown = 25;  
}





void UsrAI::trainMilitaryUnits(bool isWarTime) {
    bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
    int humanPop = info.farmers.size() + info.armies.size();
    
    if (trainCooldown > 0) trainCooldown--;
    
    int trainMinFood = (state >= COUNTERATTACK)
                     ? BUILDING_RANGE_CREATE_BOWMAN_FOOD
                     : FOOD_PAUSE_TECH_TRAIN;
    if (info.Meat >= trainMinFood && trainCooldown <= 0 && humanPop < info.Human_MaxNum) {
        bool trained = false;


        if (ENABLE_EARLY_CLUBMAN && !trained &&
            frame >= EARLY_CLUBMAN_START_FRAME && frame < EARLY_CLUBMAN_END_FRAME) {
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

        
        if (!postBronze) {
            int toolArmy = 0;
            for (auto &a : info.armies) if (a.Sort != AT_PRIEST) toolArmy++;
            
            
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

        
        if (postBronze) {
            bool lateGame = (state >= DEFENSE_WAVE3 || frame >= WAVE3_TIME);
            bool counterAtk = (state >= COUNTERATTACK);

            
            
            if (counterAtk) {
                
                
                for (auto &b : info.buildings) {
                    if (b.Type != BUILDING_RANGE || b.Project != ACT_NULL) continue;
                    if (compositeBowResearched &&
                        info.Meat >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_FOOD &&
                        info.Gold >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_GOLD) {
                        BuildingAction(b.SN, BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN);
                        trained = true;
                    }
                }

                
                
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
            
            
            
            
            if (lateGame && !trained) {
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

            
            if (!trained && compositeBowResearched) {
                auto r = findBuilding(BUILDING_RANGE);
                if (r && r->Project == ACT_NULL &&
                    info.Meat >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_FOOD &&
                    info.Gold >= BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN_GOLD) {
                    BuildingAction(r->SN, BUILDING_RANGE_CREATE_COMPOSITE_BOWMAN);
                    trained = true;
                }
            }

            
            
            if (!trained && broadswordResearched) {
                auto ac = findBuilding(BUILDING_ARMYCAMP);
                if (ac && ac->Project == ACT_NULL &&
                    info.Meat >= BUILDING_ARMYCAMP_CREATE_BROADSWORD_FOOD &&
                    info.Stone >= BUILDING_ARMYCAMP_CREATE_BROADSWORD_GOLD) {
                    BuildingAction(ac->SN, BUILDING_ARMYCAMP_CREATE_BROADSWORD);
                    trained = true;
                }
            }

            
            
            
            bool canTrainCheap = (isWarTime || state == DEFENSE_PREP);
            if (!DISABLE_CLUBMAN_TRAIN && !trained && canTrainCheap &&
                info.Meat >= BUILDING_ARMYCAMP_CREATE_CLUBMAN_FOOD) {
                auto ac = findBuilding(BUILDING_ARMYCAMP);
                if (ac && ac->Project == ACT_NULL) {
                    BuildingAction(ac->SN, BUILDING_ARMYCAMP_CREATE_CLUBMAN);
                    trained = true;
                }
            }

            
            
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

            
            
            if (lateGame && info.Meat >= MELEE_OVERFLOW_FOOD) {
                
                if (!DISABLE_CLUBMAN_TRAIN) {
                    auto acMelee = findBuilding(BUILDING_ARMYCAMP);
                    if (acMelee && acMelee->Project == ACT_NULL &&
                        info.Meat >= BUILDING_ARMYCAMP_CREATE_CLUBMAN_FOOD) {
                        BuildingAction(acMelee->SN, BUILDING_ARMYCAMP_CREATE_CLUBMAN);
                        trained = true;
                    }
                }
                
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

            
            if (!trained && !DISABLE_CAVALRY_TRAIN) {
                auto st = findBuilding(BUILDING_STABLE);
                if (st && st->Project == ACT_NULL &&
                    info.Meat >= BUILDING_STABLE_CREATE_CAVALRY_FOOD &&
                    info.Gold >= BUILDING_STABLE_CREATE_CAVALRY_GOLD) {
                    BuildingAction(st->SN, BUILDING_STABLE_CREATE_CAVALRY);
                    trained = true;
                }
            }

            
            if (ENABLE_SCOUT_RECON && !trained && !scoutBuilt && state >= COUNTERATTACK) {
                auto st = findBuilding(BUILDING_STABLE);
                if (st && st->Project == ACT_NULL &&
                    info.Meat >= BUILDING_STABLE_CREATE_SCOUT_FOOD) {
                    BuildingAction(st->SN, BUILDING_STABLE_CREATE_SCOUT);
                    scoutBuilt = true; trained = true;
                }
            }
            }  
        }

        if (trained) trainCooldown = 15;
    }
}


void UsrAI::manageMilitary() {
    bool isWarTime = (state >= DEFENSE_WAVE1 && state <= DEFENSE_WAVE3);
    double BL = (double)BLOCKSIDELENGTH;

    trainMilitaryUnits(isWarTime);

    
    
    
    if (isWarTime) {
        for (auto &tower : info.buildings) {
            if (tower.Type != BUILDING_ARROWTOWER || tower.Percent < 100) continue;
            if (tower.Project != -1) continue; 
            
            double tDR = (tower.BlockDR + 1) * BL;
            double tUR = (tower.BlockUR + 1) * BL;
            int target = findNearestEnemySN(tDR, tUR, 8 * BL); 
            if (target >= 0) {
                HumanAction(tower.SN, target);
            }
        }
    }

    
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

    
    
    int priestAttackerSN = -1;
    if (priestAlive)
        for (auto &e : info.enemy_armies)
            if (e.WorkObjectSN == priestSN) { priestAttackerSN = e.SN; break; }
    
    auto nearestGuardTarget = [&](double r) -> int {
        int t = findNearestEnemyNoStone(priestDR, priestUR, r);
        return (t >= 0) ? t : findNearestEnemySN(priestDR, priestUR, r);
    };



    auto holdNearBase = [&](tagArmy &a) {
        double distTC = calDistance(a.DR, a.UR, centerDR, centerUR);
        if (distTC <= 16 * BL) { armyReturnTry[a.SN] = 0; return; }   
        if (armyReturnTry[a.SN] >= 24) return;                        
        int atry = armyReturnTry[a.SN];
        int aang = atry % 8;
        int arad = atry / 8; if (arad > 2) arad = 2;
        const int ARADII[3] = {8, 11, 14};
        
        double ara = (double)aang * 3.141592653589793 / 4.0 + (double)(a.SN % 11) * 0.055;
        double aR = (ARADII[arad] + (double)(a.SN % 5) * 0.4) * BL;
        double atx = centerDR + std::cos(ara) * aR;
        double aty = centerUR + std::sin(ara) * aR;
        atx = max(0.0, min((double)MAP_L * BL, atx));
        aty = max(0.0, min((double)MAP_U * BL, aty));
        
        
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
        
        
        if (armyIssueFrame.count(a.SN) && a.NowState == HUMAN_STATE_IDLE &&
            frame - armyIssueFrame[a.SN] > 8 &&
            calDistance(a.DR, a.UR, armyIssueDR[a.SN], armyIssueUR[a.SN]) < 1.0 * BL) {
            armyReturnTry[a.SN]++;
        }
        armyIssueDR[a.SN] = a.DR; armyIssueUR[a.SN] = a.UR; armyIssueFrame[a.SN] = frame;
    };

    
    int maxAttackCmds = isWarTime ? 8 : 4;
    int attackCmds = 0;

    
    bool priestThreatened = false;
    int priestEnemySN2 = -1;
    if (priestAlive) {
        priestEnemySN2 = findNearestEnemySN(priestDR, priestUR, 15 * BL);
        priestThreatened = (priestEnemySN2 >= 0);
    }

    
    
    std::map<int,int> guardIssued;   

    auto autoAttackEligible = [&](const tagArmy &a) -> bool {
        if (a.Sort == AT_PRIEST) return false;
        if (a.Sort == AT_STONE_THROWER) return false;   
        if (guardIssued.count(a.SN)) return false;      
        if (a.NowState != HUMAN_STATE_IDLE) return false;
        return true;
    };

    
    
    
    
    
    const int KITING_HOLD_FRAMES = 40;   
    auto kiteRetreatLocked = [&](int sn) -> bool {
        if (kitingPhase.count(sn) && kitingPhase[sn] == 1) return true;
        return lastRetreatFrame.count(sn) && (frame - lastRetreatFrame[sn] < KITING_HOLD_FRAMES);
    };
    if (priestAlive) {
        
        const int attackingPriestSN = priestAttackerSN;   
        int urgentSN = nearestGuardTarget(PRIEST_GUARD_URGENT * BL);
        int alertSN  = nearestGuardTarget(PRIEST_GUARD_ALERT * BL);

        int guardSN = (attackingPriestSN >= 0) ? attackingPriestSN
                    : ((urgentSN >= 0) ? urgentSN : alertSN);
        if (guardSN >= 0) {
            const bool lockedOn = (attackingPriestSN >= 0);   
            const bool urgent = lockedOn || (urgentSN >= 0);
            int guardCmds = 0;
            for (auto &a : info.armies) {
                if (a.Sort == AT_PRIEST) continue;
                if (guardCmds >= PRIEST_GUARD_MAX_CMDS) break;
                if (a.NowState == HUMAN_STATE_WORKING) continue;
                
                if (a.WorkObjectSN == guardSN) continue;
                
                if (a.NowState == HUMAN_STATE_ATTACKING && !urgent) continue;
                
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

    
    if (priestAlive && center) {
        for (auto &a : info.armies) {
            if (a.Sort == AT_PRIEST) continue;
            
            
            if (a.Sort == AT_STONE_THROWER) continue;
            if (attackCmds >= maxAttackCmds) break;

            
            if (a.NowState == HUMAN_STATE_WORKING) continue;
            if (a.NowState == HUMAN_STATE_ATTACKING) continue;

            
            const int attackingPriest = priestAttackerSN;   
            if (attackingPriest >= 0) {
                if (a.WorkObjectSN != attackingPriest) {   
                    HumanAction(a.SN, attackingPriest);
                    attackCmds++;
                }
                continue;
            }

            
            if (kiteRetreatLocked(a.SN)) continue;





            if (priestThreatened) {
                bool tooFarInCounter = (state == COUNTERATTACK) &&
                    (calDistance(a.DR, a.UR, priestDR, priestUR) > PRIEST_GUARD_RECALL * BL);
                if (!tooFarInCounter && a.WorkObjectSN != priestEnemySN2) {    
                    HumanAction(a.SN, priestEnemySN2);
                    attackCmds++;
                }
                continue;
            }

            
            int selfEnemy = findNearestEnemyNoStone(a.DR, a.UR, 8 * BL);
            if (a.NowState != HUMAN_STATE_IDLE && selfEnemy < 0) continue;
            if (selfEnemy >= 0) {
                HumanAction(a.SN, selfEnemy);
                attackCmds++;
                continue;
            }

            
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



            if (state == COUNTERATTACK) {
                
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

    
    if (isWarTime && center && attackCmds < maxAttackCmds) {
        int tcEnemy = findNearestEnemyNoStone(centerDR, centerUR, 25 * BL);
        if (tcEnemy >= 0) {
            for (auto &a : info.armies) {
                if (!autoAttackEligible(a)) continue;
                if (kiteRetreatLocked(a.SN)) continue;   
                if (attackCmds >= maxAttackCmds) break;
                HumanAction(a.SN, tcEnemy);
                attackCmds++;
            }
        }
    }

    
    if (state == COUNTERATTACK) {
        
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




        tagBuilding* depot = nullptr;
        double bestDepotDist = 1e12;
        for (auto &b : info.buildings) {
            if (b.Percent != 100) continue;
            double bDR = (b.BlockDR + 1) * BLOCKSIDELENGTH, bUR = (b.BlockUR + 1) * BLOCKSIDELENGTH;
            double dd = calDistance(f.DR, f.UR, bDR, bUR);
            bool match = false;
            if (f.ResourceSort == HUMAN_GRANARYFOOD) {
                if (b.Type == BUILDING_GRANARY) match = true;         
            } else if (f.ResourceSort == HUMAN_DOCKFOOD) {
                if (b.Type == BUILDING_DOCK) match = true;            
            } else {
                
                if (b.Type == BUILDING_STOCK) match = true;
            }
            if (match && dd < bestDepotDist) { depot = &b; bestDepotDist = dd; }
        }
        if (!depot) {
            
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
    
    
    
    
    
    
    
    if (COUNTER_FARMER_ATTACK && frame >= COUNTER_FARMER_ATTACK_FRAME) {
        static std::map<int, int> farmerAtkFrame;   




        int farmerTgtSN = -1;
        int tgtKind = 0;                        
        double bestSoft = 1e18, bestTower = 1e18;
        int softSN = -1, towerSN = -1;
        tagBuilding* foeTC = findEnemyBuilding(BUILDING_CENTER);
        if (foeTC) { farmerTgtSN = foeTC->SN; tgtKind = 1; }
        for (auto &b : info.enemy_buildings) {
            if (b.Type == BUILDING_SIEGE) continue;              
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
    
    
    
    
    
    {
        double pDR = 0, pUR = 0; bool pAlive = false;
        for (auto &a : info.armies) if (a.Sort == AT_PRIEST) { pDR = a.DR; pUR = a.UR; pAlive = true; break; }
        if (pAlive) {
            
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
                    if (a.WorkObjectSN == guardSN) continue;   
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
    
    
    if (priest) {
        if (priestCounterCooldown > 0) priestCounterCooldown--;   

        
        auto scanTowerThreat = [&](double &nearD, int &cnt) {
            nearD = 1e9; cnt = 0;
            for (auto &b : info.enemy_buildings)
                if (b.Type == BUILDING_ARROWTOWER) {
                    cnt++;
                    double d = calDistance(priest->DR, priest->UR, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL);
                    if (d < nearD) nearD = d;
                }
        };





        if (frame % 300 == 0) {
            double nearTowerD = 1e9; int towerCnt = 0;
            scanTowerThreat(nearTowerD, towerCnt);   
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

        
        
        
        int enemyTowerN = 0;          
        int enemyBldSeenN = 0;        
        for (auto &b : info.enemy_buildings) {
            enemyBldSeenN++;
            if (b.Type == BUILDING_ARROWTOWER) enemyTowerN++;
        }
        
        bool localClear = true;
        for (auto &e : info.enemy_armies)
            if (e.Blood > 0 && calDistance(priest->DR, priest->UR, e.DR, e.UR) < PRIEST_SIEGE_CLEAR_ARMY_R * BL) { localClear = false; break; }
        if (localClear)
            for (auto &b : info.enemy_buildings)
                if (b.Type == BUILDING_ARROWTOWER &&
                    calDistance(priest->DR, priest->UR, (b.BlockDR + 1) * BL, (b.BlockUR + 1) * BL) < PRIEST_SIEGE_CLEAR_TOWER_R * BL) { localClear = false; break; }
        
        
        
        
        const bool towersClearEnough = (enemyTowerN <= PRIEST_TOWERS_CLEAR_MAX)
                                && (enemySiegeSN != -1)
                                && (enemyBldSeenN >= PRIEST_TOWERS_CLEAR_MIN_SEEN);
        const bool clearOk = PRIEST_SIEGE_REQUIRE_TOWERS_CLEAR ? towersClearEnough : localClear;




        if (enemySiegeSN != -1 && priest->ConvertCooldown <= 0) {
            double sD0 = calDistance(priest->DR, priest->UR, (rallyDR + 1.0) * BL, (rallyUR + 1.0) * BL);
            if (sD0 <= PRIEST_CONVERT_SIEGE_RANGE * BL) {
                
                if (PRIEST_SIEGE_REQUIRE_TOWERS_CLEAR && !clearOk) {
                    if (frame % 100 == 0) {
                        
                        
                        int aliveE0 = 0;
                        for (auto &e : info.enemy_armies) if (e.Blood > 0) aliveE0++;
                        DebugText(QString("[SIEGE-WAIT f=%1] hp=%2 towers=%3 seen=%4 alive=%5 dS=%6 lim=%7")
                                  .arg(frame).arg((priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0, 0, 'f', 2)
                                  .arg(enemyTowerN).arg(enemyBldSeenN).arg(aliveE0).arg(sD0 / BL, 0, 'f', 1).arg(PRIEST_TOWERS_CLEAR_MAX));
                    }
                    return;
                }
                
                
                if (priest->WorkObjectSN != enemySiegeSN && priestCounterCooldown <= 0) {
                    
                    double pHp0 = (priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0;
                    double nearT0 = 1e9; int towerN0 = 0;
                    scanTowerThreat(nearT0, towerN0);
                    
                    
                    if (pHp0 < PRIEST_SIEGE_GUARD_HP && nearT0 <= PRIEST_SIEGE_CLEAR_TOWER_R * BL) {
                        if (frame % 100 == 0)
                            DebugText(QString("[SIEGE-HOLD f=%1] hp=%2 nearT=%3 towers=%4 dS=%5").arg(frame).arg(pHp0, 0, 'f', 2).arg(nearT0 / BL, 0, 'f', 1).arg(towerN0).arg(sD0 / BL, 0, 'f', 1));
                        return;   
                    }
                    HumanAction(priestSN, enemySiegeSN);
                    priestCounterCooldown = PRIEST_SIEGE_CONVERT_LOCKOUT;
                    
                    DebugText(QString(">> Priest converting Siege Workshop! f=%1 d=%2 hp=%3 nearT=%4 towers=%5 path=early").arg(frame).arg(sD0 / BL, 0, 'f', 1).arg(pHp0, 0, 'f', 2)
                              .arg((nearT0 > 1e8) ? -1.0 : nearT0 / BL, 0, 'f', 1).arg(towerN0));
                }
                priestMoveCooldown = 60;   
                return;
            }
        }
        

        if (priest->NowState != HUMAN_STATE_IDLE && priest->NowState != HUMAN_STATE_WALKING) {
            
            return;
        }

        
        
        if (priestMoveCooldown > 0) return;

        
        bool anyInjuredAlly = false;
        for (auto &a : info.armies) {
            if (a.MaxBlood <= 0) continue;
            if (a.Blood > 0 && a.Blood < a.MaxBlood) { anyInjuredAlly = true; break; }
        }
        
        
        
        
        if (anyInjuredAlly && state != COUNTERATTACK) return;

        double pDist = calDistance(priest->DR, priest->UR, targetDR, targetUR);
        
        
        
        
        
        if (PRIEST_CONVERT_SIEGE_WHEN_CLEAR && clearOk && enemySiegeSN != -1) {
            priestSiegeApproach = 1;
        } else if (priestSiegeApproach == 1) {
            bool hardAbort = false;
            for (auto &e : info.enemy_armies)
                if (e.Blood > 0 && calDistance(priest->DR, priest->UR, e.DR, e.UR) < PRIEST_SIEGE_ABORT_R * BL) { hardAbort = true; break; }
            double pBRap = (priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0;
            
            if (hardAbort || pBRap < PRIEST_SIEGE_ABORT_HP || enemySiegeSN == -1
                || (PRIEST_SIEGE_REQUIRE_TOWERS_CLEAR && !clearOk)) priestSiegeApproach = 0;
        }
        bool allowConvertSiege = PRIEST_CONVERT_SIEGE_WHEN_CLEAR && (clearOk || priestSiegeApproach == 1);
        
        

        
        
        bool priestTooClose = (pDist < PRIEST_MIN_DIST_TARGET * BL);
        
        
        if (allowConvertSiege && enemySiegeSN != -1) priestTooClose = false;

        
        if (allowConvertSiege && enemySiegeSN != -1 && priest->ConvertCooldown <= 0) {
            
            const double sMemDR = (rallyDR + 1.0) * BL;
            const double sMemUR = (rallyUR + 1.0) * BL;
            double dSiege = calDistance(priest->DR, priest->UR, sMemDR, sMemUR);
            if (dSiege <= PRIEST_CONVERT_SIEGE_RANGE * BL) {
                
                HumanAction(priestSN, enemySiegeSN);
                priestCounterCooldown = 60; priestMoveCooldown = 60;
                
                double nearT1 = 1e9; int towerN1 = 0;
                scanTowerThreat(nearT1, towerN1);
                DebugText(QString(">> Priest converting Siege Workshop! f=%1 d=%2 hp=%3 nearT=%4 towers=%5 path=front").arg(frame).arg(dSiege / BL, 0, 'f', 1)
                          .arg((priest->MaxBlood > 0) ? (double)priest->Blood / priest->MaxBlood : 1.0, 0, 'f', 2).arg((nearT1 > 1e8) ? -1.0 : nearT1 / BL, 0, 'f', 1).arg(towerN1));
            } else if (priestCounterCooldown <= 0) {
                
                double ux2 = (sMemDR - priest->DR), uy2 = (sMemUR - priest->UR);
                double ul2 = std::sqrt(ux2 * ux2 + uy2 * uy2) + 1e-6;
                ux2 /= ul2; uy2 /= ul2;
                double stopD = (PRIEST_CONVERT_SIEGE_RANGE - 1.0) * BL;   
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
            return;   
        }

        
        if (siege && pDist < 12 * BL && priest->ConvertCooldown <= 0 && clearOk) {
            
            HumanAction(priestSN, siege->SN);
            priestCounterCooldown = 60; priestMoveCooldown = 60;
            DebugText(">> Priest converting Siege Workshop! path=legacy");
        } else if (priestCounterCooldown <= 0 || priestTooClose) {
            
            
            double tcDR = rallyCtrDR, tcUR = rallyCtrUR;   
            double sumDR = 0, sumUR = 0; int nArmy = 0;
            for (auto &a : info.armies) {
                if (a.SN == priestSN) continue;       
                sumDR += a.DR; sumUR += a.UR; nArmy++;
            }
            double armyDR = (nArmy > 0) ? sumDR / nArmy : tcDR;
            double armyUR = (nArmy > 0) ? sumUR / nArmy : tcUR;
            
            double ux = tcDR - armyDR, uy = tcUR - armyUR;
            double ul = std::sqrt(ux * ux + uy * uy) + 1e-6;
            ux /= ul; uy /= ul;
            
            double px = armyDR + ux * PRIEST_SAFE_BEHIND * BL;
            double py = armyUR + uy * PRIEST_SAFE_BEHIND * BL;
            
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




void UsrAI::snapWalkable(double &x, double &y, const std::vector<std::vector<char>>& forestGrid) const {
    if (isPassableAt(x, y, forestGrid)) return;
    double BL = (double)BLOCKSIDELENGTH;
    for (int r = 1; r <= 4; ++r)
        for (int dx = -r; dx <= r; ++dx)
            for (int dy = -r; dy <= r; ++dy) {
                if (dx > -r && dx < r && dy > -r && dy < r) continue;   
                double cx = x + dx * BL, cy = y + dy * BL;
                if (isPassableAt(cx, cy, forestGrid)) { x = cx; y = cy; return; }
            }
}

bool UsrAI::counterScoutAndPlan(double BL, double &targetDR, double &targetUR,
                                      const std::vector<std::vector<char>>& forestGrid) {
    
    if (enemySiegeSN == -1) {
        auto siege = findEnemyBuilding(BUILDING_SIEGE);
        if (siege) {
            enemySiegeSN = siege->SN;
            rallyDR = siege->BlockDR;
            rallyUR = siege->BlockUR;
            DebugText(QString(">> Enemy Siege Workshop found at (%1,%2)!").arg(rallyDR).arg(rallyUR));
        }
    }

    
    if (ENABLE_SCOUT_RECON && enemySiegeSN == -1 && !scoutBuilt) {
        auto st = findBuilding(BUILDING_STABLE);
        if (st && st->Project == ACT_NULL && info.Meat >= BUILDING_STABLE_CREATE_SCOUT_FOOD) {
            BuildingAction(st->SN, BUILDING_STABLE_CREATE_SCOUT);
            scoutBuilt = true;
        }
    }

    
    tagBuilding* siege = nullptr;
    if (enemySiegeSN != -1) siege = findEnemyBuilding(BUILDING_SIEGE);
    if (enemySiegeSN != -1 && !siege) {
        
        bool converted = false;
        for (auto &b : info.buildings)
            if (b.Type == BUILDING_SIEGE) { converted = true; break; }
        if (converted) {
            state = VICTORY;
            DebugText("!!! VICTORY! Siege Workshop converted !!!");
            return true;
        }
        
        
    }
    
    
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
        targetDR = enemyBaseDR; targetUR = enemyBaseUR;   
    } else {
        auto center = findBuilding(BUILDING_CENTER);
        double tcDR = center ? (center->BlockDR + 1) * BL : MAP_L * BL * 0.5;
        double tcUR = center ? (center->BlockUR + 1) * BL : MAP_U * BL * 0.5;
        
        
        
        const int CORNER_INSET = 3;
        targetDR = (tcDR < MAP_L * BL * 0.5) ? (MAP_L - CORNER_INSET) * BL : CORNER_INSET * BL;
        targetUR = (tcUR < MAP_U * BL * 0.5) ? (MAP_U - CORNER_INSET) * BL : CORNER_INSET * BL;
    }

    
    
    snapWalkable(targetDR, targetUR, forestGrid);
    return false;
}










void UsrAI::manageCounterAttack() {
    double BL = (double)BLOCKSIDELENGTH;

    
    
    
    std::vector<std::vector<char>> forestGrid(MAP_L, std::vector<char>(MAP_U, 0));
    for (auto &r : info.resources) {
        if (r.Cnt <= 0) continue;
        if (r.Type != RESOURCE_TREE && r.Type != RESOURCE_STONE && r.Type != RESOURCE_GOLD) continue;
        int tx = (int)(r.DR / BL), ty = (int)(r.UR / BL);
        int rad = (r.Type == RESOURCE_TREE) ? 2 : 1;   
        for (int ddx = -rad; ddx <= rad; ++ddx)
            for (int ddy = -rad; ddy <= rad; ++ddy) {
                int cx = tx + ddx, cy = ty + ddy;
                if (cx >= 0 && cy >= 0 && cx < MAP_L && cy < MAP_U) forestGrid[cx][cy] = 1;
            }
    }

    
    
    
    

    double targetDR, targetUR;
    if (counterScoutAndPlan(BL, targetDR, targetUR, forestGrid)) return;

    
    tagBuilding* siege = nullptr;
    if (enemySiegeSN != -1) siege = findEnemyBuilding(BUILDING_SIEGE);
    bool directMarch = (siege != nullptr) || enemyBaseScouted;

    counterFarmerAttack(BL, targetDR, targetUR);
    if (counterPriestGuard(BL)) return;

    
    int marchCmds = 0;
    int armyCount = 0;
    for (auto &a : info.armies) if (a.Sort != AT_PRIEST) armyCount++;  
    
    bool readyToAttack = (armyCount >= COUNTER_ATTACK_MIN_ARMY) || (frame >= COUNTER_ATTACK_FORCE_TIME);
    
    tagBuilding* rallyTC = findBuilding(BUILDING_CENTER);
    double rallyCtrDR = rallyTC ? (rallyTC->BlockDR + 1) * BL : MAP_L * BL * 0.5;
    double rallyCtrUR = rallyTC ? (rallyTC->BlockUR + 1) * BL : MAP_U * BL * 0.5;
    tagArmy* priest = nullptr;





    static std::map<int, double> marchGoalDR, marchGoalUR;
    
    
    
    
    auto issueMarch = [&](double fx, double fy, int sn, int sort, int stuckTry, bool canReissue,
                          int biasTowerSN = -1) {
        (void)sort;
        if (!canReissue) return;                 
        double mx = targetDR, my = targetUR;
        
        if (biasTowerSN >= 0) {
            for (auto &b : info.enemy_buildings) {
                if (b.SN != biasTowerSN || b.Type != BUILDING_ARROWTOWER) continue;   
                const double tDR = (b.BlockDR + 1.0) * BL, tUR = (b.BlockUR + 1.0) * BL;  
                double dx = rallyCtrDR - tDR, dy = rallyCtrUR - tUR, d = std::sqrt(dx * dx + dy * dy);
                const double so = TOWER_APPROACH_STANDOFF * BL;
                if (d > 1e-6) { mx = tDR + dx / d * so; my = tUR + dy / d * so; }
                else          { mx = tDR; my = tUR; }        
                mx = max(0.0, min((double)MAP_L * BL, mx));  
                my = max(0.0, min((double)MAP_U * BL, my));
                snapWalkable(mx, my, forestGrid);                        
                break;
            }
        }
        
        if (stuckTry > 0) {
            double dx = mx - rallyCtrDR, dy = my - rallyCtrUR, d = std::sqrt(dx * dx + dy * dy);
            double back = (d > BL) ? ((stuckTry * BL < d - BL) ? stuckTry * BL : d - BL) : 0.0;
            if (d > 1e-6) { mx -= dx / d * back; my -= dy / d * back; }
            snapWalkable(mx, my, forestGrid);                
            
            marchIssueDist[sn] = calDistance(fx, fy, mx, my);
            marchMoveFrame[sn] = frame;
        }
        marchGoalDR[sn] = mx; marchGoalUR[sn] = my;   
        HumanMove(sn, mx, my);                   
        marchCmdFrame[sn] = frame;
    };

    
    
    
    
    
    static long long twArmyFrames = 0, twChance12 = 0, twChance30 = 0, twBias = 0;

    
    
    auto attackBuildingOrMarch = [&](tagArmy &a, const char *who, int stuckTry, bool canReissue) {
        
        
        const double selfR = sortMaxRangedRange(a.Sort, BL);
        
        
        const bool canHitTower = !sortIsRanged(a.Sort) || a.Sort == AT_COMPOSITE_BOWMAN || selfR >= ARROWTOWER_RANGE * BL;
        
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
        
        if (towerSN >= 0) {
            if (!towerSkipSN.count(a.SN) || towerSkipSN[a.SN] != towerSN) {
                towerSkipSN[a.SN] = towerSN;
                DebugText(QString("[TOWER-SKIP f=%1] %2 SN=%3 射程%4<塔%5 → 不打塔 SN=%6 (改打非塔建筑/推进)").arg(frame).arg(who).arg(a.SN).arg(selfR / BL, 0, 'f', 1)
                          .arg(ARROWTOWER_RANGE, 0, 'f', 1).arg(towerSN));
            }
        }




        int tier2SN = -1;
        if (canHitTower) {
            int t2 = findNearestEnemyTower(a.DR, a.UR, TOWER_APPROACH_RANGE * BL);
            if (t2 >= 0 && t2 != towerSN) tier2SN = t2;   
        }
        if (directMarch && calDistance(a.DR, a.UR, targetDR, targetUR) <= 12 * BL) {
            
            int ebSN;
            if (ARMY_IGNORE_SIEGE_WORKSHOP) {
                int nb = findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
                ebSN = (nb >= 0 && siege != nullptr && nb == siege->SN) ? -1 : nb;
            } else {
                ebSN = siege ? siege->SN : findNearestEnemyBuilding(a.DR, a.UR, 12 * BL);
            }
            
            if (ebSN >= 0 && a.WorkObjectSN != ebSN && (canHitTower || !isTowerSN(ebSN))) {
                HumanAction(a.SN, ebSN); return;   
            }
        }
        
        if (tier2SN >= 0 && (!towerBiasSN.count(a.SN) || towerBiasSN[a.SN] != tier2SN)) {
            towerBiasSN[a.SN] = tier2SN;
            DebugText(QString("[TOWER-APPROACH f=%1] %2 SN=%3 塔%4 在%5格内(>%6) → 不发攻击令，落点贴塔外%7格").arg(frame).arg(who).arg(a.SN).arg(tier2SN)
                      .arg(TOWER_APPROACH_RANGE, 0, 'f', 0).arg(TOWER_TARGET_RANGE).arg(TOWER_APPROACH_STANDOFF, 0, 'f', 0));
            ++twBias;
        }
        issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue, tier2SN);   
    };

    const int maxMarchCmds = readyToAttack ? 8 : (armyCount + 4);
    for (int pass = 0; pass < 2 && marchCmds < maxMarchCmds; ++pass) {
        for (auto &a : info.armies) {
            if (a.Sort == AT_PRIEST) { priest = &a; continue; }

            
            if (readyToAttack) {
                ++twArmyFrames;
                if (findNearestEnemyTower(a.DR, a.UR, TOWER_TARGET_RANGE * BL) >= 0) ++twChance12;
                if (findNearestEnemyTower(a.DR, a.UR, 30.0 * BL) >= 0) ++twChance30;
            }

            
            
            const double gDR = marchGoalDR.count(a.SN) ? marchGoalDR[a.SN] : targetDR;
            const double gUR = marchGoalUR.count(a.SN) ? marchGoalUR[a.SN] : targetUR;
            const double curDistToTgt = calDistance(a.DR, a.UR, gDR, gUR);   
            if (!marchIssueDist.count(a.SN)) {          
                marchIssueDist[a.SN] = curDistToTgt;
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
            } else if (marchIssueDist[a.SN] - curDistToTgt > 0.5 * BL) {
                marchIssueDist[a.SN] = curDistToTgt;    
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0; 
            }
            
            
            if (a.NowState == HUMAN_STATE_ATTACKING) {
                marchIssueDist[a.SN] = curDistToTgt;
                marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
            }
            bool stuckNow = (frame - marchMoveFrame[a.SN] > 90);        
            bool canReissue = !marchCmdFrame.count(a.SN) ||
                              (frame - marchCmdFrame[a.SN] >= 30);      
            if (stuckNow && canReissue) marchStuckTry[a.SN]++;          
            int stuckTry = marchStuckTry[a.SN];

            
            
            if ((a.Sort == AT_CHARIOT_ARCHER || a.Sort == AT_CAVALRY) &&
                !enemyBaseScouted && enemySiegeSN == -1) {
                issueMarch(a.DR, a.UR, a.SN, a.Sort, stuckTry, canReissue);   
                marchCmds++;
                continue;
            }




            if (sortIsRanged(a.Sort) && a.Sort != AT_STONE_THROWER) {
                const double R = sortMaxRangedRange(a.Sort, BL);



                
                
                
                
                const int SHOOT_FRAMES = 30;               
                const int PHASE_COOLDOWN = 20;             
                
                const int RETREAT_FRAMES = 60;             
                int phase = kitingPhase.count(a.SN) ? kitingPhase[a.SN] : 0;
                
                
                
                
                if (!kitingPhase.count(a.SN)) kitingPhase[a.SN] = 0;
                if (!kitingPhaseFrame.count(a.SN)) kitingPhaseFrame[a.SN] = frame;
                phase = kitingPhase[a.SN];
                int phaseFrame = kitingPhaseFrame[a.SN];
                int phaseAged = frame - phaseFrame;
                
                
                int kEnemy = -1;
                double kEX = 0, kEY = 0; bool kGot = false;
                bool kMelee = false;
                int  kSort = -1;         
                int  kSkipSort = -1;     
                if (kitingTargetSN.count(a.SN)) {
                    int cur = kitingTargetSN[a.SN];
                    kGot = lookupEnemySN(cur, kEX, kEY, &kMelee, &kSort);   
                    
                    
                    if (kGot && (calDistance(a.DR, a.UR, kEX, kEY) > 20 * BL ||
                                 !sortHasKiteRangeAdvantage(a.Sort, kSort, BL))) kGot = false;
                    if (kGot) kEnemy = cur;
                }
                if (!kGot) {
                    
                    kEnemy = findKiteTarget(a.Sort, a.DR, a.UR, 20 * BL, kSort, kSkipSort);
                    if (kEnemy >= 0) kGot = lookupEnemySN(kEnemy, kEX, kEY, &kMelee, &kSort);
                }
                
                
                
                if (kEnemy >= 0 && kGot) kitingTargetSN[a.SN] = kEnemy;   
                
                
                if (kEnemy < 0 && kSkipSort >= 0 &&
                    (!kiteSkipSort.count(a.SN) || kiteSkipSort[a.SN] != kSkipSort)) {
                    kiteSkipSort[a.SN] = kSkipSort;
                    DebugText(QString("[KIT-NO f=%1] SN=%2 无可拉扯目标：附近敌 Sort=%3 射程>我%4格 ⇒ 不拉扯(落推进/打建筑)").arg(frame).arg(a.SN).arg(kSkipSort).arg(R / BL, 0, 'f', 1));
                }
                
                
                
                
                const double THREAT_R = (kSort >= 0 && sortIsRanged(kSort)) ? sortMaxRangedRange(kSort, BL) : 0.0;
                const double RET_D = min(max(THREAT_R + KITING_SAFE_MARGIN * BL, KITING_MIN_KEEP * BL), R);
                const double T_OUT = RET_D;
                const double T_IN  = max(0.5 * R, RET_D - KITING_HYST * BL);
                double dK = kGot ? calDistance(a.DR, a.UR, kEX, kEY) : 1e12;

                
                
                if (kGot && dK <= 0.5 * R && phase != 1) {
                    phase = 1; kitingPhase[a.SN] = 1; kitingPhaseFrame[a.SN] = frame;
                    phaseFrame = frame; phaseAged = 0;
                    kitingRetStuck[a.SN] = 0;   
                    
                    
                    
                    
                    kitingRetPrevDK.erase(a.SN);
                                                
                }
                
                if (phase == 0 && kGot && dK > 0.5 * R && dK <= T_IN && phaseAged >= 6) {
                    
                    phase = 1; kitingPhase[a.SN] = 1; kitingPhaseFrame[a.SN] = frame;
                    phaseFrame = frame; phaseAged = 0;
                    kitingRetStuck[a.SN] = 0;   
                    
                    
                    
                    
                    kitingRetPrevDK.erase(a.SN);
                                                
                }
                bool coolPhase = (frame - phaseFrame >= PHASE_COOLDOWN);
                
                if (phase == 0 && kGot && phaseAged >= SHOOT_FRAMES) {
                    phase = 1; kitingPhase[a.SN] = 1; kitingPhaseFrame[a.SN] = frame;
                    phaseFrame = frame; phaseAged = 0;
                    kitingRetStuck[a.SN] = 0;   
                    
                    
                    
                    
                    kitingRetPrevDK.erase(a.SN);
                                                
                }
                
                
                
                if (phase == 1 && kGot && dK >= T_OUT) {
                    phase = 0; kitingPhase[a.SN] = 0; kitingPhaseFrame[a.SN] = frame;
                    phaseFrame = frame; phaseAged = 0;
                } else if (phase == 1 && phaseAged >= RETREAT_FRAMES) {
                    
                    if (coolPhase) {
                        phase = 0; kitingPhase[a.SN] = 0; kitingPhaseFrame[a.SN] = frame;
                        phaseFrame = frame; phaseAged = 0;
                    }
                }

                if (phase == 1 && kGot && canReissue) {
                    
                    
                    
                    
                    
                    
                    
                    
                    const double KIT_LAND = min(RET_D + KITING_LANDING_SLACK * BL, R);   
                    double ux = (a.DR - kEX) / (dK + 1e-6), uy = (a.UR - kEY) / (dK + 1e-6);
                    const double angs[5] = {0.0, 0.6, -0.6, 1.2, -1.2};
                    const double angsT[5] = {0.0, 0.5, -0.5, 1.0, -1.0};  
                    bool kitMoved = false;
                    double kitX = 0, kitY = 0;
                    int kitStage = 0;  



                    if (kitingRetPrevDK.count(a.SN)) {
                        if (dK < kitingRetPrevDK[a.SN] + 0.3 * BL)
                            kitingRetStuck[a.SN] = (kitingRetStuck.count(a.SN) ? kitingRetStuck[a.SN] : 0) + 1;
                        else
                            kitingRetStuck[a.SN] = 0;                 
                    }
                    kitingRetPrevDK[a.SN] = dK;
                    bool skipAwayStage = (kitingRetStuck.count(a.SN) && kitingRetStuck[a.SN] > 0);
                    
                    
                    auto tryRetreatLanding = [&](double rx, double ry, int stage) -> bool {
                        rx = max(0.0, min((double)MAP_L * BL, rx));
                        ry = max(0.0, min((double)MAP_U * BL, ry));
                        if (!isPassableAt(rx, ry, forestGrid)) return false;
                        HumanMove(a.SN, rx, ry);
                        marchCmdFrame[a.SN] = frame;
                        lastRetreatFrame[a.SN] = frame;
                        
                        marchIssueDist[a.SN] = calDistance(a.DR, a.UR, rx, ry);
                        marchMoveFrame[a.SN] = frame; marchStuckTry[a.SN] = 0;
                        marchGoalDR[a.SN] = rx; marchGoalUR[a.SN] = ry;
                        kitMoved = true; kitStage = stage; kitX = rx; kitY = ry;
                        return true;
                    };
                    
                    for (int ai = 0; ai < 5 && !kitMoved && !skipAwayStage; ++ai) {
                        double ca = std::cos(angs[ai]), sa = std::sin(angs[ai]);
                        tryRetreatLanding(kEX + (ux*ca - uy*sa) * KIT_LAND,
                                          kEY + (uy*ca + ux*sa) * KIT_LAND, 1);
                    }
                    
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
                    
                    if (!kitMoved && priest && calDistance(a.DR, a.UR, priest->DR, priest->UR) < 20 * BL) {
                        double prUX = priest->DR - a.DR, prUY = priest->UR - a.UR;
                        double prLen = std::sqrt(prUX*prUX + prUY*prUY);
                        if (prLen > 1e-6) {
                            prUX /= prLen; prUY /= prLen;
                            const double PR_STEP = 6.0 * BL;
                            for (int ai = 0; ai < 3 && !kitMoved; ++ai) {  
                                double ca = std::cos(angsT[ai]), sa = std::sin(angsT[ai]);
                                tryRetreatLanding(a.DR + (prUX*ca - prUY*sa) * PR_STEP,
                                                  a.UR + (prUY*ca + prUX*sa) * PR_STEP, 3);
                            }
                        }
                    }
                    
                    
                    
                    
                    
                    DebugText(QString("[KIT-R f=%1] SN=%2 dK=%3 R=%4 stage=%5 stuck=%6 aged=%7 self=(%8,%9) tgt=(%10,%11) tSort=%12 retD=%13 tin=%14 thr=%15 melee=%16")
                              .arg(frame).arg(a.SN).arg(dK / BL, 0, 'f', 1).arg(R / BL, 0, 'f', 1).arg(kitStage).arg(kitingRetStuck.count(a.SN) ? kitingRetStuck[a.SN] : 0).arg(phaseAged)
                              .arg(a.DR / BL, 0, 'f', 1).arg(a.UR / BL, 0, 'f', 1).arg(kitX / BL, 0, 'f', 1).arg(kitY / BL, 0, 'f', 1).arg(kSort)
                              .arg(RET_D / BL, 0, 'f', 1).arg(T_IN / BL, 0, 'f', 1).arg(THREAT_R / BL, 0, 'f', 1).arg(kMelee ? 1 : 0));
                    marchCmds++;
                    continue;   
                }

                
                
                
                if (phase == 0 && kGot && dK <= R + 2.0 * BL) {
                    
                    
                    
                    
                    
                    
                    
                    
                    const int RETREAT_PROTECT_FRAMES = 15;
                    const int SHOOT_REISSUE_FRAMES   = 20;   
                    bool retreatProt = lastRetreatFrame.count(a.SN) &&
                                       (frame - lastRetreatFrame[a.SN] < RETREAT_PROTECT_FRAMES);
                    bool atkCool = !kitingAtkFrame.count(a.SN) ||
                                   (frame - kitingAtkFrame[a.SN] >= SHOOT_REISSUE_FRAMES);
                    if (!retreatProt && a.WorkObjectSN != kEnemy && atkCool) {
                        HumanAction(a.SN, kEnemy);            
                        kitingAtkFrame[a.SN] = frame;
                    }
                    if (frame % 100 == 0)
                        DebugText(QString("[KIT-S f=%1] SN=%2 phaseAged=%3 dK=%4 R=%5 tSort=%6").arg(frame).arg(a.SN).arg(phaseAged).arg(dK / BL, 0, 'f', 1).arg(R / BL, 0, 'f', 1).arg(kSort));
                    marchCmds++;
                    continue;   
                }
                
                if (phase == 1) { marchCmds++; continue; }



                const int KITING_REGATHER_FRAMES = 120;
                if (phase == 0 && kGot && lastRetreatFrame.count(a.SN) &&
                    (frame - lastRetreatFrame[a.SN] < KITING_REGATHER_FRAMES)) {
                    marchCmds++;
                    continue;
                }
                
            }

            
            
            if (a.NowState != HUMAN_STATE_IDLE && a.Sort != AT_STONE_THROWER) {
                if (!stuckNow || !canReissue) continue;   
            } else if (stuckNow && !canReissue) {
                continue;                                  
            }

            bool ranged = sortIsRanged(a.Sort);
            if (pass == 0 && !ranged) continue;   
            if (pass == 1 && ranged) continue;    
            if (marchCmds >= maxMarchCmds) break;

            
            
            
            if (!readyToAttack) {
                if (calDistance(a.DR, a.UR, rallyCtrDR, rallyCtrUR) > 12 * BL && canReissue) {
                    double ux = a.DR - rallyCtrDR, uy = a.UR - rallyCtrUR;
                    double baseAng = (std::sqrt(ux*ux + uy*uy) > 1e-6) ? std::atan2(uy, ux) : 0.0;
                    bool moved = false;
                    double angTries[3] = {0.0, 0.25, -0.25};          
                    
                    
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







            if (a.Sort == AT_STONE_THROWER) {
                const double CAT_RANGE     = 10.0 * BL;              
                const double CAT_FIRE_BAND = CAT_RANGE + 0.5 * BL;   
                const double CAT_FLEE_TRIG = CAT_RANGE * 0.7;        
                const double CAT_FLEE_EXIT = CAT_RANGE * 1.4;        
                
                int atkSN = -1; double atkD = 1e12;
                if (catTargetSN.count(a.SN)) {
                    int cur = catTargetSN[a.SN];
                    double cx = 0, cy = 0;
                    bool alive = lookupEnemySN(cur, cx, cy);
                    if (alive) {
                        atkD = calDistance(a.DR, a.UR, cx, cy);
                        if (atkD > 15 * BL) alive = false;      
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
                        if (atkSN < 0 || cd + 2.0 * BL < atkD) { atkSN = cand; atkD = cd; }  
                    }
                    catTargetFrame[a.SN] = frame;
                }
                if (atkSN >= 0) catTargetSN[a.SN] = atkSN;
                
                int threatSN = findNearestEnemySN(a.DR, a.UR, CAT_RANGE * 1.6);
                double ex = 0, ey = 0;
                bool gotThreat = (threatSN >= 0) && lookupEnemySN(threatSN, ex, ey);
                bool catRetreating = (catRetreat.count(a.SN) && catRetreat[a.SN]);
                if (gotThreat) {
                    double d = calDistance(a.DR, a.UR, ex, ey);
                    bool wantRetreat = catRetreating ? (d < CAT_FLEE_EXIT) : (d <= CAT_FLEE_TRIG);
                    if (wantRetreat) {
                        if (!catRetreating) catRetreat[a.SN] = 1;
                        
                        const int CAT_COOLDOWN = 30;
                        bool cool = !marchCmdFrame.count(a.SN) ||
                                    (frame - marchCmdFrame[a.SN] >= CAT_COOLDOWN);
                        if (cool) {
                            double ux = (a.DR - ex) / (d + 1e-6), uy = (a.UR - ey) / (d + 1e-6);
                            double angs[5] = {0.0, 0.6, -0.6, 1.2, -1.2};   
                            bool moved = false;
                            for (int ai = 0; ai < 5 && !moved; ++ai) {
                                double ca = std::cos(angs[ai]), sa = std::sin(angs[ai]);
                                double rx = ex + (ux*ca - uy*sa) * CAT_FLEE_EXIT;   
                                double ry = ey + (uy*ca + ux*sa) * CAT_FLEE_EXIT;
                                rx = max(0.0, min((double)MAP_L * BL, rx));
                                ry = max(0.0, min((double)MAP_U * BL, ry));
                                if (isPassableAt(rx, ry, forestGrid)) { HumanMove(a.SN, rx, ry); marchCmdFrame[a.SN] = frame; moved = true; }
                            }
                            if (!moved && atkSN >= 0 && a.WorkObjectSN != atkSN) HumanAction(a.SN, atkSN);   
                        }
                        marchCmds++;
                        continue;   
                    }
                    catRetreat[a.SN] = 0;   
                } else {
                    catRetreat[a.SN] = 0;
                }
                
                if (atkSN >= 0 && atkD <= CAT_FIRE_BAND) {
                    bool cool = !catAtkFrame.count(a.SN) || (frame - catAtkFrame[a.SN] >= 20);
                    if (a.WorkObjectSN != atkSN && cool) {
                        HumanAction(a.SN, atkSN);
                        catAtkFrame[a.SN] = frame;
                    }
                    marchCmds++;
                    continue;   
                }
                
                if (atkSN >= 0) {
                    bool cool = !catAtkFrame.count(a.SN) || (frame - catAtkFrame[a.SN] >= 30);
                    if (a.WorkObjectSN != atkSN && cool) {
                        HumanAction(a.SN, atkSN);
                        catAtkFrame[a.SN] = frame;
                    }
                    marchCmds++;
                    continue;
                }



                if (canReissue) {
                    HumanMove(a.SN, targetDR, targetUR);   
                    marchCmdFrame[a.SN] = frame;
                    marchGoalDR[a.SN] = targetDR; marchGoalUR[a.SN] = targetUR;   
                }
                marchCmds++;
                continue;
            }

            
            
            if (ranged) {
                
                
                attackBuildingOrMarch(a, "复合弓兵/远程", stuckTry, canReissue);
                marchCmds++;
                continue;
            }

            
            
            int enemySN = findNearestEnemyNoStone(a.DR, a.UR, 15 * BL);
            
            if (enemySN >= 0) {
                
                if (a.WorkObjectSN != enemySN) HumanAction(a.SN, enemySN);
            } else {
                
                attackBuildingOrMarch(a, "近战", stuckTry, canReissue);
            }
            marchCmds++;
        }
    }

    
    
    if (twArmyFrames > 0 && frame % 1500 < 2) {
        DebugText(QString("[TOWER-CHANCE f=%1] 累计兵帧=%2 塔<=12格=%3(%4%) 塔<=30格=%5(%6%) Tier2偏置=%7次").arg(frame).arg(twArmyFrames)
                  .arg(twChance12).arg(100.0 * twChance12 / (double)twArmyFrames, 0, 'f', 1).arg(twChance30).arg(100.0 * twChance30 / (double)twArmyFrames, 0, 'f', 1).arg(twBias));
    }

    counterPriestConvert(BL, targetDR, targetUR, rallyCtrDR, rallyCtrUR, forestGrid);

}


void UsrAI::checkDefeat() {
    
    bool priestAlive = false;
    for (auto &a : info.armies) {
        if (a.Sort == AT_PRIEST) { priestAlive = true; break; }
    }
    if (!priestAlive && priestSN != -1) {
        state = DEFEAT;
        DebugText("!!! DEFEAT: Priest killed !!!");
        return;
    }

    
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



tagFarmer* UsrAI::findIdleFarmer() {
    for (auto &f : info.farmers) {
        if (f.FarmerSort != FARMERTYPE_FARMER) continue;
        if (buildingFarmerType.count(f.SN)) continue;
        if (f.NowState == HUMAN_STATE_IDLE && f.Resource <= 0) return &f;
    }
    return nullptr;
}




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


int UsrAI::findNearestEnemyBuilding(double dr, double ur, double range) {
    double bestD2 = range * range;
    return nearestEnemyBuildingFrom(dr, ur, bestD2, -1);
}



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




tagResource* UsrAI::findBestWoodTree(double dr, double ur) {
    const double BL = (double)BLOCKSIDELENGTH;
    const double maxAnchor = WOOD_MAX_ANCHOR_DIST * BL;

    tagResource* best = nullptr;
    double bestScore = 1e12;
    tagResource* nearestAnchorTree = nullptr;  
    double bestAnchorDist = 1e12;

    for (auto &r : info.resources) {
        if (r.Type != RESOURCE_TREE || r.Cnt <= 0) continue;
        if (stuckResourceUntil.count(r.SN)) continue;      

        
        double anchorD2 = 1e12;
        for (auto &b : info.buildings) {
            if (b.Percent < 100) continue;
            if (b.Type != BUILDING_STOCK && b.Type != BUILDING_CENTER) continue;
            double bx = (b.BlockDR + 1.0) * BL;
            double by = (b.BlockUR + 1.0) * BL;
            double d2 = dist2(r.DR, r.UR, bx, by);
            if (d2 < anchorD2) anchorD2 = d2;
        }
        
        double anchorD = (anchorD2 >= 1e12) ? 0.0 : std::sqrt(anchorD2);

        
        int workerCount = countFarmersOnTarget(r.SN);
        const bool treeFull = (workerCount + frameWoodCount[r.SN] >= WOOD_MAX_WORKERS_PER_TREE);

        
        
        if (!treeFull && anchorD < bestAnchorDist) { bestAnchorDist = anchorD; nearestAnchorTree = &r; }

        if (anchorD > maxAnchor) continue;   
        if (treeFull) continue;              

        double vd = std::sqrt(dist2(r.DR, r.UR, dr, ur));
        double score = (WOOD_SCORE_ALPHA * vd + WOOD_SCORE_BETA * anchorD) * (1.0 + workerCount * 0.5);
        if (score < bestScore) { bestScore = score; best = &r; }
    }

    if (!best) best = nearestAnchorTree;   
    if (!best) return nullptr;

    frameWoodCount[best->SN]++;            

    
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



int UsrAI::findNearestEnemyNoStone(double dr, double ur, double range) {
    int bestSN = -1;
    double bestDist = range * range;
    for (const auto &e : info.enemy_armies) {
        if (e.Sort == AT_STONE_THROWER) continue;   
        double d = dist2(e.DR, e.UR, dr, ur);
        if (d < bestDist) { bestDist = d; bestSN = e.SN; }
    }
    if (bestSN >= 0) return bestSN;
    
    bestDist = range * range;
    for (const auto &e : info.enemy_farmers) {
        double d = dist2(e.DR, e.UR, dr, ur);
        if (d < bestDist) { bestDist = d; bestSN = e.SN; }
    }
    return bestSN;
}



int UsrAI::findCatapultTarget(double dr, double ur, double range) {
    double bestD2 = range * range;
    int bestSN = findNearestEnemyUnit(dr, ur, bestD2, false);
    
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




int UsrAI::countBuildingsExisting(int type) {
    int cnt = 0;
    for (auto &b : info.buildings) {
        if (b.Type != type) continue;
        if (deadBuildings.count(b.SN)) {
            auto it = deadBuildingsFrame.find(b.SN);
            if (it != deadBuildingsFrame.end() && frame - it->second > DEAD_BUILDING_GRACE)
                continue;   
        }
        cnt++;
    }
    for (auto &kv : pendingBuildIns)
        if (kv.second.second == type) cnt++;
    
    if (cnt == 0) {
        auto it = lastBuildIssueFrame.find(type);
        if (it != lastBuildIssueFrame.end() && frame - it->second <= 90) cnt = 1;
    }
    return cnt;
}


int UsrAI::countAllMilitary() {
    int cnt = 0;
    for (auto &a : info.armies) if (a.Sort != AT_PRIEST) cnt++;
    return cnt;
}


int UsrAI::countFarmersOnTarget(int sn) {
    int n = 0;
    for (auto &f : info.farmers)
        if (f.WorkObjectSN == sn) n++;
    return n;
}

bool UsrAI::isPositionFree(int blockDR, int blockUR, int size) {
    if (!inBounds(blockDR, blockUR, size)) return false;
    if (info.theMap == nullptr) return false;

    
    int firstHeight = (*info.theMap)[blockDR][blockUR].height;
    for (int i = blockDR; i < blockDR + size; ++i) {
        for (int j = blockUR; j < blockUR + size; ++j) {
            auto &t = (*info.theMap)[i][j];
            if (t.type != MAPPATTERN_GRASS) return false;
            if (t.height < 0) return false;
            if (t.height != firstHeight) return false;
        }
    }

    
    if (isBlockedByBuildings(blockDR, blockUR, size, info.buildings)) return false;

    
    if (isBlockedByBuildings(blockDR, blockUR, size, info.enemy_buildings)) return false;

    
    if (isBlockedByResources(blockDR, blockUR, size, info.resources)) return false;

    
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

    
    if (!isSiteReachable(blockDR, blockUR, size)) return false;

    return true;
}



bool UsrAI::isSiteReachable(int blockDR, int blockUR, int size) {
    if (info.theMap == nullptr) return true;   
    if (blockDR < 0 || blockUR < 0 || blockDR + size > MAP_L || blockUR + size > MAP_U) return false;

    int firstHeight = (*info.theMap)[blockDR][blockUR].height;

    
    auto tileBlocked = [&](int i, int j) -> bool {
        if (i < 0 || j < 0 || i >= MAP_L || j >= MAP_U) return true;
        auto &t = (*info.theMap)[i][j];
        if (t.type != MAPPATTERN_GRASS) return true;
        if (t.height < 0) return true;
        if (t.height != firstHeight) return true;   
        
        if (i >= blockDR && i < blockDR + size && j >= blockUR && j < blockUR + size) return true;
        
        for (auto &b : info.buildings) {
            int bs = buildingFootprintSize(b.Type);
            if (i >= b.BlockDR && i < b.BlockDR + bs &&
                j >= b.BlockUR && j < b.BlockUR + bs) return true;
        }
        
        for (auto &b : info.enemy_buildings) {
            int bs = buildingFootprintSize(b.Type);
            if (i >= b.BlockDR && i < b.BlockDR + bs &&
                j >= b.BlockUR && j < b.BlockUR + bs) return true;
        }
        return false;
    };

    
    const int R = 1;
    std::vector<std::pair<int,int>> starts;
    for (int i = blockDR - R; i < blockDR + size + R; ++i)
        for (int j = blockUR - R; j < blockUR + size + R; ++j) {
            bool inFoot = (i >= blockDR && i < blockDR + size && j >= blockUR && j < blockUR + size);
            if (inFoot) continue;           
            if (tileBlocked(i, j)) continue;
            starts.push_back({i, j});
        }
    if (starts.empty()) return false;      

    
    const int ESCAPE_N = 300;
    std::vector<std::pair<int,int>> q = starts;
    std::unordered_set<long long> vis;
    for (auto &s : starts) vis.insert((long long)s.first * 100003 + s.second);
    int head = 0, visited = 0;
    const int dirs[4][2] = {{1,0},{-1,0},{0,1},{0,-1}};
    while (head < (int)q.size()) {
        auto cur = q[head++]; ++visited;
        if (visited >= ESCAPE_N) return true;   
        for (int d = 0; d < 4; ++d) {
            int ni = cur.first + dirs[d][0], nj = cur.second + dirs[d][1];
            if (tileBlocked(ni, nj)) continue;
            long long k = (long long)ni * 100003 + nj;
            if (vis.count(k)) continue;
            vis.insert(k); q.push_back({ni, nj});
        }
    }
    
    return false;
}



namespace {
std::mutex g_buildPosMutex;
std::map<const UsrAI*, std::map<int,int>> g_buildPosFrame;

bool buildPosBlocked(const UsrAI* self, std::set<int>& tried, int key, int frame) {
    std::lock_guard<std::mutex> lock(g_buildPosMutex);
    auto &m = g_buildPosFrame[self];
    auto it = m.find(key);
    if (!tried.count(key)) {
        if (it != m.end()) m.erase(it);
        return false;
    }
    if (it == m.end()) {
        tried.erase(key);
        return false;
    }
    if (frame - it->second > BUILD_POS_BLACKLIST_FRAMES) {
        tried.erase(key);
        m.erase(it);
        return false;
    }
    return true;
}

void markBuildPos(const UsrAI* self, std::set<int>& tried, int key, int frame) {
    std::lock_guard<std::mutex> lock(g_buildPosMutex);
    tried.insert(key);
    g_buildPosFrame[self][key] = frame;
}
}

bool UsrAI::findBuildSiteTowardCenter(int &x, int &y, int size, int minR, int maxR) {
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return false;
    int cx = center->BlockDR, cy = center->BlockUR;
    
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
                if (std::abs(dx) != r && std::abs(dy) != r) continue;   
                int nx = cx + dx, ny = cy + dy;
                if (nx < 0 || ny < 0 || nx >= MAP_L || ny >= MAP_U) continue;
                int key = nx * 1000 + ny;
                if (buildPosBlocked(this, triedBuildPositions, key, frame)) continue;
                if (!isPositionFree(nx, ny, size)) continue;
                
                double len = std::sqrt((double)(dx * dx + dy * dy));
                double align = (len > 1e-6) ? (dx * gx + dy * gy) / len : 0.0;
                double score = align * 100.0 + (double)(r - minR);     
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

    
    for (int r = 8; r < 50; ++r) {
        for (int dx = -r; dx <= r; ++dx) {
            for (int dy = -r; dy <= r; ++dy) {
                if (std::abs(dx) != r && std::abs(dy) != r) continue;
                int nx = cx + dx, ny = cy + dy;
                int key = nx * 1000 + ny;
                if (buildPosBlocked(this, triedBuildPositions, key, frame)) continue;
                if (!isPositionFree(nx, ny, size)) continue;
                
                if (avoidFarmAdjacent && isFarmAdjacent(nx, ny)) continue;
                x = nx; y = ny;
                return true;
            }
        }
    }

    
    return false;
}

bool UsrAI::findDefenseBuildSite(int &x, int &y, int size) {




    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return findBuildSite(x, y, size);
    int cx = center->BlockDR, cy = center->BlockUR;

    
    std::vector<std::pair<int,int>> existingTowers;
    for (auto &b : info.buildings)
        if (b.Type == BUILDING_ARROWTOWER)
            existingTowers.push_back({b.BlockDR, b.BlockUR});

    
    double gx = MAP_L * 0.5 - cx, gy = MAP_U * 0.5 - cy;
    double glen = std::sqrt(gx * gx + gy * gy);
    if (glen < 1e-6) { gx = 1.0; gy = 0.0; glen = 1.0; }
    gx /= glen; gy /= glen;
    if (!existingTowers.empty()) { gx = -gx; gy = -gy; }   

    
    int bestX = -1, bestY = -1;
    double bestScore = -1e18;
    int triedCount = 0, blockedCount = 0;
    for (int r = 4; r <= 12; ++r) {
        for (int dx = -r; dx <= r; ++dx) {
            for (int dy = -r; dy <= r; ++dy) {
                if (std::max(std::abs(dx), std::abs(dy)) != r) continue;   
                int nx = cx + dx, ny = cy + dy;
                if (nx < 0 || ny < 0 || nx >= MAP_L - size || ny >= MAP_U - size) continue;
                int key = nx * 1000 + ny;
                ++triedCount;
                if (buildPosBlocked(this, triedBuildPositions, key, frame)) { ++blockedCount; continue; }
                if (!isPositionFree(nx, ny, size)) { ++blockedCount; continue; }

                double len = std::sqrt((double)(dx * dx + dy * dy));
                double align = (len > 1e-6) ? (dx * gx + dy * gy) / len : 0.0;
                
                double score = align * 100.0 - (double)r * 0.5;
                if (score > bestScore) { bestScore = score; bestX = nx; bestY = ny; }
            }
        }
    }
    if (bestX < 0) {
        
        if (frame % 50 == 0) {   
            DebugText(QString("TowerSite FAIL (no free site in r=4~12) tried=%1 blocked=%2 blacklist_cleared=%3 existingTowers=%4")
                .arg(triedCount).arg(blockedCount).arg(0).arg((int)existingTowers.size()));
        }
        return false;
    }
    x = bestX; y = bestY;
    return true;
}

bool UsrAI::findGranarySite(int &x, int &y) {
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return false;
    double BL = (double)BLOCKSIDELENGTH;
    double tcDR = (center->BlockDR + 1) * BL;
    double tcUR = (center->BlockUR + 1) * BL;

    
    std::vector<std::pair<double,double>> existingGranaries;
    for (auto &b : info.buildings) {
        if (b.Type == BUILDING_GRANARY && b.Percent == 100) {
            existingGranaries.push_back({(b.BlockDR + 1.0) * BL, (b.BlockUR + 1.0) * BL});
        }
    }
    bool hasGranary = !existingGranaries.empty();

    
    
    
    int bestScore = -1;
    int bestBX = 0, bestBY = 0;
    for (auto &r : info.resources) {
        if (r.Cnt <= 0) continue;
        bool isBush = (r.Type == RESOURCE_BUSH);
        bool isGazelle = (r.Type == RESOURCE_GAZELLE);
        if (!isBush && !isGazelle) continue;
        
        if (isGazelle && !hasGranary) continue;
        
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

        
        if (hasGranary && isGazelle) cluster *= 2;

        
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

    
    int offsets[4][2] = {{1,0}, {-1,0}, {0,1}, {0,-1}};
    for (int d = 0; d < 4; d++) {
        int nx = bestBX + offsets[d][0] * 3;
        int ny = bestBY + offsets[d][1] * 3;
        if (buildPosBlocked(this, triedBuildPositions, nx * 1000 + ny, frame)) continue;
        if (isPositionFree(nx, ny, 3)) {
            x = nx; y = ny;
            return true;
        }
    }
    
    for (int r = 4; r < 10; r++) {
        for (int dx = -r; dx <= r; dx++) {
            for (int dy = -r; dy <= r; dy++) {
                if (std::abs(dx) != r && std::abs(dy) != r) continue;
                int nx = bestBX + dx, ny = bestBY + dy;
                if (nx < 0 || ny < 0) continue;
                if (buildPosBlocked(this, triedBuildPositions, nx * 1000 + ny, frame)) continue;
                if (isPositionFree(nx, ny, 3)) {
                    x = nx; y = ny;
                    return true;
                }
            }
        }
    }
    return false;
}





bool UsrAI::findRemoteBushCluster(int &bx, int &by, int &outCnt) {
    bx = by = -1; outCnt = 0;
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return false;
    double BL = (double)BLOCKSIDELENGTH;
    double tcDR = (center->BlockDR + 1) * BL;
    double tcUR = (center->BlockUR + 1) * BL;

    
    std::vector<std::pair<double,double>> exist;
    for (auto &b : info.buildings)
        if (b.Type == BUILDING_GRANARY)
            exist.push_back({(b.BlockDR + 1.0) * BL, (b.BlockUR + 1.0) * BL});

    int best = 0, bestX = -1, bestY = -1;
    for (auto &r : info.resources) {
        if (r.Type != RESOURCE_BUSH || r.Cnt <= 0) continue;
        if (calDistance(tcDR, tcUR, r.DR, r.UR) < SECOND_GRANARY_TC_MIN_DIST * BL) continue;   
        bool nearExist = false;
        for (auto &e : exist) {
            if (calDistance(r.DR, r.UR, e.first, e.second) < 12 * BL) { nearExist = true; break; }
        }
        if (nearExist) continue;                                                               
        int cluster = 0;
        for (auto &r2 : info.resources)
            if (r2.Type == RESOURCE_BUSH && r2.Cnt > 0 &&
                calDistance(r.DR, r.UR, r2.DR, r2.UR) < BUSH_CLUSTER_RADIUS * BL) cluster++;
        if (cluster > best) { best = cluster; bestX = r.BlockDR; bestY = r.BlockUR; }
    }
    if (best < MIN_BUSH_FOR_SECOND_GRANARY) return false;                                      
    bx = bestX; by = bestY; outCnt = best;
    return true;
}


bool UsrAI::findHouseSite(int &x, int &y) {
    return findBuildSiteTowardCenter(x, y, 2, 12, 45);
}


bool UsrAI::findMarketSite(int &x, int &y) {
    return findBuildSiteTowardCenter(x, y, 3, 12, 40);
}



bool UsrAI::isFarmAdjacent(int blockDR, int blockUR) {
    for (auto &b : info.buildings) {
        if (b.Type != BUILDING_FARM) continue;
        bool separatedX = (blockDR - 1 > b.BlockDR + 2) || (blockDR + 3 < b.BlockDR);
        bool separatedY = (blockUR - 1 > b.BlockUR + 2) || (blockUR + 3 < b.BlockUR);
        if (!separatedX && !separatedY) return true;   
    }
    return false;
}






bool UsrAI::findFarmSiteBest(int &x, int &y) {
    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return false;




    std::vector<std::pair<int, int> > anchors;
    std::vector<int> anchorTypes;          
    anchors.push_back(std::make_pair(center->BlockDR, center->BlockUR));
    anchorTypes.push_back(BUILDING_CENTER);
    for (auto &b : info.buildings) {
        if (b.Percent < 100) continue;                       
        if (b.Type != BUILDING_GRANARY) continue;            
        anchors.push_back(std::make_pair(b.BlockDR, b.BlockUR));
        anchorTypes.push_back(b.Type);
    }
    
    
    
    
    
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

    
    
    
    double bestD2 = 1e18;                    
    int bx = -1, by = -1;
    int bestBase = -1;                       
    
    
    auto consider = [&](int nx, int ny, bool useBlack, int base) {
        if (nx < 0 || ny < 0) return;
        if (useBlack && buildPosBlocked(this, triedBuildPositions, nx * 1000 + ny, frame)) return;
        if (!isPositionFree(nx, ny, 3)) return;
        if (isFarmAdjacent(nx, ny)) return;
        double fcx = nx + 1.0, fcy = ny + 1.0;
        double abx = anchors[base].first + 1.0, aby = anchors[base].second + 1.0;
        double d2 = dist2(fcx, fcy, abx, aby);
        if (d2 < bestD2) { bestD2 = d2; bx = nx; by = ny; bestBase = base; }
    };




    auto ringOf = [&](int ax, int ay, int r, bool useBlack, int base) {
        const int n = 2 * r + 1;
        for (int side = 0; side < 4; ++side) {
            for (int k = 0; k < n; ++k) {
                int nx, ny;
                if (side == 0)      { nx = ax - r + k; ny = ay + r; }       
                else if (side == 1) { nx = ax - r + k; ny = ay - r; }       
                else if (side == 2) { nx = ax - r;     ny = ay - r + k; }   
                else                { nx = ax + r;     ny = ay - r + k; }   
                consider(nx, ny, useBlack, base);
            }
        }
    };

    
    for (int pass = 0; pass < 2 && bx < 0; ++pass) {
        const bool useBlack = (pass == 0);
        
        for (int r = FARM_ANCHOR_R_MIN; r <= FARM_ANCHOR_R_MAX; ++r) {
            if ((double)r * (double)r > bestD2) break;
            ringOf(anchors[0].first, anchors[0].second, r, useBlack, 0);
        }
        if (bx >= 0) break;                  



        for (int ai = 1; ai < NA; ++ai) {
            for (int r = FARM_ANCHOR_R_MIN; r <= FARM_ANCHOR_R_MAX; ++r)
                ringOf(anchors[ai].first, anchors[ai].second, r, useBlack, ai);
        }
    }
    if (bx < 0) return false;
    
    {
        int bbx = anchors[bestBase].first, bby = anchors[bestBase].second;
        int rr  = std::max(std::abs(bx - bbx), std::abs(by - bby));
        int tcR = std::max(std::abs(bx - anchors[0].first), std::abs(by - anchors[0].second));
        
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
    
    if (buildingType == BUILDING_FARM) {
        int farmCount = 0;
        for (auto &b : info.buildings)
            if (b.Type == BUILDING_FARM) farmCount++;
        for (auto &kv : pendingBuildIns)
            if (kv.second.second == BUILDING_FARM) farmCount++;
        if (farmCount >= MAX_FARMS) return false;
    }

    
    tagFarmer* f = nullptr;
    if (preferNearBuilder && prefX >= 0 && prefY >= 0)
        f = findIdleFarmerNear((prefX + 1) * (double)BLOCKSIDELENGTH, (prefY + 1) * (double)BLOCKSIDELENGTH);
    if (!f) f = findIdleFarmer();
    if (!f) f = findAnyFarmer();
    if (!f) return false;

    int x, y;
    bool placed = false;
    
    if (prefX >= 0 && prefY >= 0) {
        int offs[][2] = {{0,0},{3,0},{-3,0},{0,3},{0,-3},{6,0},{-6,0},{0,6},{0,-6},
                         {-3,-3},{3,3},{-3,3},{3,-3}};
        for (auto &o : offs) {
            int nx = prefX + o[0], ny = prefY + o[1];
            if (nx < 0 || ny < 0) continue;
            if (isPositionFree(nx, ny, size)) { x = nx; y = ny; placed = true; break; }
        }
        
        if (!placed && noFallback) return false;
    }
    
    if (!placed && buildingType == BUILDING_GRANARY)
        placed = findGranarySite(x, y);
    
    if (!placed && buildingType == BUILDING_MARKET)
        placed = findMarketSite(x, y);
    
    if (!placed && buildingType == BUILDING_HOME)
        placed = findHouseSite(x, y);
    if (!placed && buildingType == BUILDING_FARM) {
        
        
        
        
        
        placed = findFarmSiteBest(x, y);
        if (!placed) {
            
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
    
    if (!placed && (buildingType == BUILDING_ARMYCAMP || buildingType == BUILDING_RANGE ||
                    buildingType == BUILDING_STABLE))
        placed = findBuildSiteTowardCenter(x, y, size, 12, 45);
    
    
    if (!placed && buildingType != BUILDING_FARM)
        placed = findBuildSite(x, y, size, false);
    if (!placed) return false;

    buildingFarmerType[f->SN] = buildingType;
    builderDispatchFrame[f->SN] = frame;   
    int buildInsId = HumanBuild(f->SN, buildingType, x, y);
    pendingBuildIns[buildInsId] = {f->SN, buildingType};
    pendingBuildInsFrame[buildInsId] = frame;
    lastBuildIssueFrame[buildingType] = frame;
    
    
    
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

    
    int key = x * 1000 + y;
    markBuildPos(this, triedBuildPositions, key, frame);

    buildCooldown = 5;   
    
    DebugText(QString("[BUILD-ISSUE f=%1] type=%2 size=%3 村民SN=%4 at=(%5,%6) wood=%7").arg(frame).arg(buildingType).arg(size).arg(f->SN).arg(x).arg(y).arg((int)info.Wood));
    return true;
}


void UsrAI::handleBuildResults() {
    
    if (pendingBuildIns.size() > 64) { pendingBuildIns.clear(); pendingBuildInsFrame.clear(); }

    for (auto it = pendingBuildIns.begin(); it != pendingBuildIns.end(); ) {
        int insId = it->first;
        int farmerSN = it->second.first;

        
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
            
            pendingBuildInsFrame.erase(insId);
            it = pendingBuildIns.erase(it);
            continue;
        }

        
        buildingFarmerType.erase(farmerSN);

        
        if (ret == ACTION_INVALID_HUMANBUILD_DIFFERENTHIGH ||
            ret == ACTION_INVALID_HUMANBUILD_OVERBORDER ||
            ret == ACTION_INVALID_HUMANBUILD_UNEXPLORE ||
            ret == ACTION_INVALID_HUMANBUILD_OVERLAP ||
            ret == ACTION_INVALID_POSITION_NOT_FIT) {
            buildCooldown = 0;   
        }
        pendingBuildInsFrame.erase(insId);
        it = pendingBuildIns.erase(it);
    }

    
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




void UsrAI::detectStuckGatherers() {
    
    for (auto it = stuckResourceUntil.begin(); it != stuckResourceUntil.end(); ) {
        if (it->second <= frame) it = stuckResourceUntil.erase(it);
        else ++it;
    }

    auto center = findBuilding(BUILDING_CENTER);
    if (!center) return;

    for (auto &f : info.farmers) {
        
        if (buildingFarmerType.count(f.SN)) {
            gatherStuckFrame.erase(f.SN);
            continue;
        }
        
        if (f.Resource > 0 || f.NowState == HUMAN_STATE_IDLE) {
            gatherStuckFrame.erase(f.SN);
            continue;
        }
        
        if (gatherStuckFrame.find(f.SN) == gatherStuckFrame.end()) {
            gatherStuckFrame[f.SN] = frame;
        } else if (frame - gatherStuckFrame[f.SN] > STUCK_GATHER_TIMEOUT) {
            int targetSN = f.WorkObjectSN;
            
            if (targetSN <= 0 && villLastTreeSN.count(f.SN)) targetSN = villLastTreeSN[f.SN];
            if (targetSN > 0) stuckResourceUntil[targetSN] = frame + STUCK_BLACKLIST_FRAMES;
            HumanAction(f.SN, center->SN);  
            gatherStuckFrame.erase(f.SN);
            DebugText(QString("[STUCK f=%1] 村民SN=%2 寻路卡死, 目标资源SN=%3 已拉黑").arg(frame).arg(f.SN).arg(targetSN));
        }
    }
}






bool UsrAI::gazelleDropoffReady(tagResource* r) {
    if (!r) return true;
    if (info.Wood < BUILD_STOCK_WOOD) return true;                         
    if (frame >= GAZELLE_STOCK_GATE_DEADLINE) return true;                 
    if (frame >= GAZELLE_STOCK_WINDOW_END) return true;                    
    if (storageNearGazelleBuilt == 1) return true;                         
    const double BL = (double)BLOCKSIDELENGTH;
    for (auto &b : info.buildings) {
        if (b.Type != BUILDING_STOCK) continue;
        if (b.Percent < 100 && deadBuildings.count(b.SN)) continue;        
        double bDR = (b.BlockDR + 1) * BL, bUR = (b.BlockUR + 1) * BL;
        if (calDistance(r->DR, r->UR, bDR, bUR) < GAZELLE_HUNT_RANGE * BL) return true;   
    }
    return false;
}

bool UsrAI::tryAssignFood(tagFarmer* f) {
    if (!f) return false;

    
    
    
    
    const bool postBronze = (info.civilizationStage >= CIVILIZATION_BRONZEAGE);
    const bool foodStop = (info.Meat >= (postBronze ? FOOD_CAP_STOP : FOOD_CAP_STOP_PREBRONZE));
    if (foodStop) return false;

    
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

    
    
    std::vector<std::pair<double,double>> builtGranaries2;
    for (auto &b : info.buildings)
        if (b.Type == BUILDING_GRANARY && b.Percent == 100)
            builtGranaries2.push_back({(b.BlockDR + 1.0) * BL, (b.BlockUR + 1.0) * BL});
    tagResource* bestBush = nullptr;
    double bestBDist = 1e12;
    for (auto &r : info.resources) {
        if (r.Type != RESOURCE_BUSH || r.Cnt <= 0) continue;
        if (stuckResourceUntil.count(r.SN)) continue;  
        if (calDistance(tcDR, tcUR, r.DR, r.UR) > 30 * BL) {
            bool nearGranary = false;
            for (auto &gd : builtGranaries2)
                if (calDistance(r.DR, r.UR, gd.first, gd.second) <= BUSH_NEAR_GRANARY_DIST * BL) {
                    nearGranary = true; break;
                }
            if (!nearGranary) continue;
        }
        int realCount = countFarmersOnTarget(r.SN);
        if (realCount + frameBushCount[r.SN] >= 2) continue;  
        double d = dist2(r.DR, r.UR, f->DR, f->UR);
        if (d < bestBDist) { bestBDist = d; bestBush = &r; }
    }
    if (bestBush) {
        HumanAction(f->SN, bestBush->SN);
        frameBushCount[bestBush->SN]++;  
        return true;
    }

    
    
    if (!isWarTime) {
        tagResource* bestEle = nullptr;
        double bestEDist = 1e12;
        for (auto &r : info.resources) {
            if (r.Type != RESOURCE_ELEPHANT || r.Cnt <= 0) continue;
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > 30 * BL) continue;
            if (stuckResourceUntil.count(r.SN)) continue;
            int realCount = countFarmersOnTarget(r.SN);
            if (realCount < ELEPHANT_HUNT_MIN) continue;      
            if (realCount >= ELEPHANT_HUNT_GROUP) continue;   
            double d = calDistance(f->DR, f->UR, r.DR, r.UR);
            if (d < bestEDist) { bestEDist = d; bestEle = &r; }
        }
        if (bestEle) {
            HumanAction(f->SN, bestEle->SN);
            frameFoodTargets.insert(bestEle->SN);
            return true;
        }
    }

    
    for (auto &b : info.buildings) {
        if (b.Type != BUILDING_FARM || b.Percent < 100) continue;
        if (frameFoodTargets.count(b.SN)) continue;  
        int realCount = countFarmersOnTarget(b.SN);
        if (realCount >= 1) continue;
        HumanAction(f->SN, b.SN);
        frameFoodTargets.insert(b.SN);  
        return true;
    }

    
    if (!huntingGroup.count(f->SN)) {
        
        tagResource* bestGazelle = nullptr;
        double bestGDist = 1e12;
        for (auto &r : info.resources) {
            if (r.Type != RESOURCE_GAZELLE || r.Cnt <= 0) continue;
            if (calDistance(tcDR, tcUR, r.DR, r.UR) > GAZELLE_HUNT_RANGE * BL) continue;
            if (stuckResourceUntil.count(r.SN)) continue;  
            int realCount = countFarmersOnTarget(r.SN);
            if (realCount + frameGazelleCount[r.SN] >= 2) continue;  
            double d = dist2(r.DR, r.UR, f->DR, f->UR);
            if (d < bestGDist) { bestGDist = d; bestGazelle = &r; }
        }
        
        if (bestGazelle && gazelleDropoffReady(bestGazelle)) {
            HumanAction(f->SN, bestGazelle->SN);
            huntingGroup.insert(f->SN);
            frameGazelleCount[bestGazelle->SN]++;
            return true;
        }
    }

    return false;
}


