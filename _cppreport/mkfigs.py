# -*- coding: utf-8 -*-
"""生成 C++ 课程设计报告用的三张图：类图 / 总体流程图 / 状态机图"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

FONT = lambda s: dict(fontproperties=__import__("matplotlib.font_manager", fromlist=["FontProperties"]).FontProperties(fname=r"C:\Windows\Fonts\simhei.ttf"), fontsize=s)
OUT = r"C:\new-aoe3.0.7g\_cppreport"

C_AI, C_AI_E = "#e8f0fb", "#2f5d9e"
C_ENG, C_ENG_E = "#eef7ee", "#2f7d4f"
C_DATA, C_DATA_E = "#fdf3e3", "#b07d28"
C_FLOW, C_FLOW_E = "#eaf3fb", "#2f5d9e"
C_LLM, C_LLM_E = "#f2eefb", "#6b4fa8"
C_RED, C_RED_E = "#fdeaea", "#a83232"


def box(ax, x, y, w, h, title, lines=(), fc="#fff", ec="#333", ts=8.5, ls=7.0, lh=2.45, pad=0.3):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=%.2f" % pad,
                                linewidth=1.3, edgecolor=ec, facecolor=fc, zorder=2))
    ax.text(x + w / 2, y + h - 0.85, title, ha="center", va="top", color="#12203a", zorder=3, **FONT(ts))
    step = ls * 0.205
    yy = y + h - 0.85 - ts * 0.46
    for ln in lines:
        ax.text(x + 0.9, yy, ln, ha="left", va="top", color="#22304a", zorder=3, **FONT(ls))
        yy -= step


def arr(ax, p1, p2, color="#2f5d9e", lw=1.4, ls="-", rad=0.0, style="-|>"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=13, linewidth=lw,
                                 color=color, linestyle=ls,
                                 connectionstyle="arc3,rad=%.2f" % rad, zorder=1))


# ============================== 图1：类图 ==============================
fig, ax = plt.subplots(figsize=(13.4, 9.6), dpi=160)
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
ax.text(4, 95.5, "AI 框架层 / 策略实现层", ha="left", va="center", color=C_AI_E, **FONT(9.5))
ax.text(55, 95.5, "引擎实体层", ha="left", va="center", color=C_ENG_E, **FONT(9.5))
ax.text(4, 2.0, "说明：实线箭头 = 公有继承（箭头指向基类）；虚线 = 关联 / 依赖。", ha="left", va="center", color="#555555", **FONT(8))

box(ax, 5, 87.5, 42, 5.6, "QThread    （Qt 线程基类）", (), "#f4f4f4", "#888888")
box(ax, 5, 64.0, 42, 21.0, "AI : QThread      （ai.h / AI.cpp，课题给定）",
    ["+ HumanMove(SN, DR, UR)         移动",
     "+ HumanAction(SN, obSN)         动作 / 攻击",
     "+ HumanBuild(SN, type, bx, by)  建造",
     "+ BuildingAction(SN, action)    建筑动作",
     "+ PinPointStrike(SN, DR, UR)    定点打击",
     "+ CommitInstruction()           帧末统一提交",
     "# InsPerFrame : vector<instruction>   指令队列",
     "- processData() = 0    - clearInsRet() = 0"], C_AI, C_AI_E)
box(ax, 5, 41.5, 42, 20.0, "UsrAICore : AI     （加固层，抽象、不可实例化）",
    ["+ refreshSnapshot()     请求主线程取快照",
     "+ event(QEvent*)        主线程执行 getInfo()",
     "+ commitInstruction()   提交前逐条指针体检",
     "+ logEnvOnce / logSnapBeat / checkDirtySnapshot",
     "- infoPtr : shared_ptr<tagInfo>    零拷贝快照",
     "# frame : int                       当前帧号",
     "· 三点加固：快照获取 / 线程生命周期 / 帧末提交",
     "· 做成基类：引擎硬编码 new UsrAI()，派生则永不构造"],
    C_AI, C_AI_E)
box(ax, 5, 12.0, 42, 27.0, "UsrAI : UsrAICore   （策略本体，本人完成）",
    ["+ processData() / processFrame()   帧主体",
     "+ updateState()        阶段状态机",
     "+ manageEconomy()      经济与资源配比",
     "+ manageBuildings()    建筑选址与建造",
     "+ managePriest()       祭司决策（核心）",
     "+ manageMilitary()     军事生产与集结",
     "+ manageCounterAttack()  反攻推进",
     "+ manageTechUpgrade() / manageHunting()",
     "- state : State        阶段枚举",
     "- 大量跨帧状态表（std::map / std::set）",
     "· 五个指令接口同名隐藏，转发前用 g_Object.find() 只读校验"],
    C_AI, C_AI_E)
arr(ax, (26, 85.0), (26, 87.4), C_AI_E)
arr(ax, (26, 61.5), (26, 63.9), C_AI_E)
arr(ax, (26, 39.0), (26, 41.4), C_AI_E)

box(ax, 55, 88.0, 42, 5.6, "Coordinate   （坐标基类：块坐标 / 细节坐标）", (), C_ENG, C_ENG_E)
box(ax, 55, 78.5, 20, 6.9, "MoveObject", ["+ 位置 / 移动 / 寻路"], C_ENG, C_ENG_E)
box(ax, 77, 78.5, 20, 6.9, "BloodHaver", ["+ Blood / MaxBlood"], C_ENG, C_ENG_E)
box(ax, 55, 68.5, 42, 6.9, "Human   : MoveObject + BloodHaver",
    ["+ SN / Sort / NowState（状态机）  + DR, UR"], C_ENG, C_ENG_E)
box(ax, 55, 58.5, 20, 6.9, "Farmer : Human", ["村民：采集 / 建造 / 交付"], C_ENG, C_ENG_E)
box(ax, 77, 58.5, 20, 6.9, "Army : Human", ["军队：近战 / 远程 / 祭司 / 投石车"], C_ENG, C_ENG_E, ts=8.0)
box(ax, 55, 48.5, 20, 6.9, "Building : Coordinate", ["+ Type / Project / Blood"], C_ENG, C_ENG_E, ts=8.0)
box(ax, 77, 48.5, 20, 6.9, "Resource", ["+ Type（金 / 木 / 石 / 树…）"], C_ENG, C_ENG_E)
box(ax, 55, 38.5, 42, 6.9, "Animal : MoveObject + Resource + BloodHaver",
    ["瞪羚 / 大象：可移动，又可被猎杀为食物"], C_ENG, C_ENG_E)
box(ax, 55, 29.5, 42, 6.4, "Missile 投射物    ｜    Block 地图区块", (), C_ENG, C_ENG_E)
box(ax, 55, 18.5, 42, 8.4, "管理层：Core 主控 ｜ Map 地图 ｜ Player 玩家",
    ["GameWidget / MainWidget / SelectWidget  （Qt 界面）"], C_ENG, C_ENG_E)
box(ax, 55, 5.5, 42, 10.5, "AI 与引擎之间的数据结构",
    ["tagInfo    一帧完整快照（村民 / 军队 / 敌方 / 资源存量）",
     "instruction / ins   待执行指令（含 self、obj 裸指针）",
     "tagObj → tagHuman → tagFarmer / tagArmy",
     "tagObj → tagBuilding / tagResource"], C_DATA, C_DATA_E, ts=8.5, ls=7.0)

arr(ax, (65, 85.4), (65, 87.9), C_ENG_E)
arr(ax, (87, 85.4), (87, 87.9), C_ENG_E)
arr(ax, (65, 75.4), (65, 78.4), C_ENG_E)
arr(ax, (87, 75.4), (87, 78.4), C_ENG_E)
arr(ax, (65, 65.4), (65, 68.4), C_ENG_E)
arr(ax, (87, 65.4), (87, 68.4), C_ENG_E)
arr(ax, (87, 45.4), (87, 48.4), C_ENG_E, ls="--")

ax.text(48.0, 30.0, "读取快照\n下发指令", ha="center", va="center", color="#a83232", **FONT(8.2))
arr(ax, (47.3, 27.0), (54.6, 12.0), "#a83232", 1.3, "--", rad=-0.28)
plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
fig.savefig(OUT + r"\fig1_class.png", facecolor="white")
plt.close(fig)
print("fig1 ok")

# ============================== 图2：总体流程图 ==============================
fig, ax = plt.subplots(figsize=(11.6, 14.0), dpi=160)
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

MAIN_X, MAIN_W = 24, 40
CX = MAIN_X + MAIN_W / 2
steps = [
    ("引擎每帧调用 processData()", "#f4f4f4", "#888888"),
    ("processFrame()   业务主体", C_FLOW, C_FLOW_E),
    ("refreshSnapshot()   主线程代取快照（零拷贝）", C_FLOW, C_FLOW_E),
    ("checkDefeat()   祭司阵亡 / 主城被毁 → 判负", C_FLOW, C_FLOW_E),
    ("managePriest()   探路 / 祭司：感化 > 逃跑 > 治疗 > 待命", C_FLOW, C_FLOW_E),
    ("updateState()   阶段状态机切换", C_FLOW, C_FLOW_E),
    ("manageCarriedResources()   交付携带资源", C_FLOW, C_FLOW_E),
    ("manageHunting()   打猎 / 组队猎象", C_FLOW, C_FLOW_E),
    ("manageEconomy()   村民生产 · 配比 · 建造 · 科技", C_FLOW, C_FLOW_E),
    ("manageMilitary()   生产 · 回城待命 · 集结", C_FLOW, C_FLOW_E),
    ("manageCounterAttack()   〔仅反攻阶段〕推进 · 拆建筑 · 祭司护卫", C_LLM, C_LLM_E),
    ("doDebugOutput()   输出本帧调试信息", C_FLOW, C_FLOW_E),
    ("commitInstruction()   帧末唯一提交点：逐条体检 self / obj 指针后并入队", C_RED, C_RED_E),
]
H = 4.9
for i, (t, fc, ec) in enumerate(steps):
    y = 93.0 - i * 6.75
    ax.add_patch(FancyBboxPatch((MAIN_X, y), MAIN_W, H, boxstyle="round,pad=0.28",
                                linewidth=1.3, edgecolor=ec, facecolor=fc, zorder=2))
    ax.text(CX, y + H / 2, t, ha="center", va="center", color="#12203a", zorder=3, **FONT(8.0))
for i in range(len(steps) - 1):
    y1 = 93.0 - i * 6.75
    y2 = 93.0 - (i + 1) * 6.75 + H
    arr(ax, (CX, y1), (CX, y2), C_FLOW_E, 1.5)

ax.text(66.5, 93.0 - 2 * 6.75 + H / 2, "失败 → 本帧直接 return", ha="left", va="center", color="#a83232", **FONT(8.0))
ax.add_patch(FancyBboxPatch((70, 93.0 - 8 * 6.75), 27, 6.4, boxstyle="round,pad=0.28",
                            linewidth=1.2, edgecolor=C_LLM_E, facecolor=C_LLM, zorder=2))
ax.text(83.5, 93.0 - 8 * 6.75 + 3.2, "manageBuildings()  选址（可达性预检）\nmanageTechUpgrade()  铜器 / 科技升级",
        ha="center", va="center", color="#12203a", zorder=3, **FONT(7.6))
arr(ax, (MAIN_X + MAIN_W, 93.0 - 8 * 6.75 + 3.2), (70, 93.0 - 8 * 6.75 + 3.2), C_LLM_E, 1.2)

ax.add_patch(FancyBboxPatch((70, 93.0 - 12 * 6.75), 27, 4.6, boxstyle="round,pad=0.28",
                            linewidth=1.2, edgecolor="#888888", facecolor="#f4f4f4", zorder=2))
ax.text(83.5, 93.0 - 12 * 6.75 + 2.3, "clearInsRet()  清空引擎侧指令返回缓冲",
        ha="center", va="center", color="#12203a", zorder=3, **FONT(7.6))
arr(ax, (MAIN_X + MAIN_W, 93.0 - 12 * 6.75 + 2.3), (70, 93.0 - 12 * 6.75 + 2.3), "#888888", 1.2)
ax.text(50, 2.4, "指令由引擎在下一帧执行；拿不到快照则不执行本帧任何决策。",
        ha="center", va="center", color="#a83232", **FONT(8.2))
plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
fig.savefig(OUT + r"\fig2_flow.png", facecolor="white")
plt.close(fig)
print("fig2 ok")

# ============================== 图3：状态机 ==============================
fig, ax = plt.subplots(figsize=(13.0, 8.0), dpi=160)
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

W, H = 21.0, 10.0
xs = [4, 27.5, 51, 74.5]
def st(x, y, name, desc, fc=C_ENG, ec=C_ENG_E):
    ax.add_patch(FancyBboxPatch((x, y), W, H, boxstyle="round,pad=0.3", linewidth=1.3,
                                edgecolor=ec, facecolor=fc, zorder=2))
    ax.text(x + W / 2, y + H - 1.0, name, ha="center", va="top", color="#12203a", zorder=3, **FONT(8.6))
    ax.text(x + W / 2, y + 3.4, desc, ha="center", va="center", color="#22304a", zorder=3, **FONT(7.4))

R1, R2, R3 = 82, 58, 30
st(xs[0], R1, "INIT", "开局")
st(xs[1], R1, "EARLY_ECONOMY", "攒食物 800\n补前置建筑")
st(xs[2], R1, "UPGRADING", "引擎确认施工\n否则重试 / 兜底")
st(xs[3], R1, "DEFENSE_PREP", "波次间准备")
st(xs[3], R2, "DEFENSE_WAVE1", "帧 ≥ 5000\n清空敌人或超时")
st(xs[2], R2, "DEFENSE_WAVE2", "帧 ≥ 13500\n清空敌人或超时")
st(xs[1], R2, "DEFENSE_WAVE3", "帧 ≥ 21000\n清空敌人或超时")
st(xs[0], R2, "COUNTERATTACK", "敌尽 或 帧 > 33000\n强制反攻")
st(xs[0], R3, "VICTORY", "祭司感化敌方\n攻城武器厂", C_RED, "#2f7d4f")
st(xs[1], R3, "DEFEAT", "祭司阵亡 / 主城被毁\n/ 30 分钟超时", C_RED, C_RED_E)

for i in range(3):
    arr(ax, (xs[i] + W, R1 + H / 2), (xs[i + 1], R1 + H / 2))
arr(ax, (xs[3] + W / 2, R1), (xs[3] + W / 2, R2 + H))
arr(ax, (xs[3], R2 + H / 2), (xs[2] + W, R2 + H / 2), "#2f7d4f")
arr(ax, (xs[2], R2 + H / 2), (xs[1] + W, R2 + H / 2), "#2f7d4f")
arr(ax, (xs[1], R2 + H / 2), (xs[0] + W, R2 + H / 2), "#2f7d4f")
arr(ax, (xs[0] + W / 2, R2), (xs[0] + W / 2, R3 + H), "#2f7d4f")
arr(ax, (xs[0] + W, R3 + H / 2), (xs[1], R3 + H / 2), C_RED_E)
ax.text(50, 16.0, "任一时点触发失败条件（祭司阵亡 / 主城被毁 / 超时）即刻进入 DEFEAT",
        ha="center", va="center", color="#a83232", **FONT(8.4))
ax.text(50, 71.5, "↑ 波次推进：波内敌人清空或超时 → 进入下一波；第三波结束阈值与强制反攻同源",
        ha="center", va="center", color="#2f7d4f", **FONT(8.2))
plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
fig.savefig(OUT + r"\fig3_fsm.png", facecolor="white")
plt.close(fig)
print("fig3 ok")
