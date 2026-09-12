# Aoe-project
帝国时代课程设计

---
## 📖 项目简介

本项目是针对《帝国时代1》复刻版博弈系统（NewAOE v3.x）的AI控制程序。通过实现`UsrAI`类，编写策略代码来控制游戏进程，完成从石器时代发展到铜器时代、抵御敌方进攻并最终转化敌方武器工程厂的游戏目标。

### 游戏目标
1. **发展**：从工具时代演进到铜器时代
2. **防御**：抵御敌方第1、2、3波进攻（第1波约4分钟，第2波约9分钟，第3波约14分钟）
3. **反攻**：最终攻入敌方基地，用祭司英雄将敌方**武器工程厂**转化为己方
4. **时限**：30分钟内完成目标，否则失败

---

## 🎮 游戏机制

### 资源系统
| 资源 | 初始量 | 采集方式 |
|------|--------|----------|
| 食物 | 500 | 浆果、狩猎、农场 |
| 木材 | 200 | 伐木 |
| 石头 | 300 | 开采石矿 |
| 黄金 | 0 | 开采金矿 |

### 时代演进
- **工具时代**（初始）→ **铜器时代**（需800食物 + 2个工具时代建筑）
- 铜器时代解锁高级兵种和科技

### 核心单位
| 单位 | 作用 |
|------|------|
| **村民** | 采集资源、建造建筑 |
| **祭司** | 感化敌方单位/建筑（12格距离），治疗友军 |
| **阔剑兵** | 铜器时代近战主力 |
| **复合弓兵** | 铜器时代远程主力 |

---

## 🚀 快速开始

### 环境要求
- C++17 编译器
- Qt 5.9+
- 游戏本体（NewAOE v3.x）

### 编译运行
```bash
# 克隆仓库
git clone https://github.com/yourusername/newaoe-ai.git
cd newaoe-ai

# 使用 Qt Creator 打开项目文件
# 或使用命令行
qmake
make
```

### 目录结构
```
newaoe-ai/
├── UsrAI.h          # AI接口头文件
├── UsrAI.cpp        # AI策略实现
├── config.json      # 游戏配置文件
└── maps/            # 地图文件目录
    └── map*.njust   # 地图数据
```

---

## 🧠 AI策略架构

### 状态机设计
```cpp
enum State {
    EARLY_ECONOMY,   // 早期经济发展
    UPGRADING,       // 升级铜器时代
    DEFENSE_PREP,    // 防御准备
    DEFENSE_WAVE1,   // 第一波防守
    DEFENSE_WAVE2,   // 第二波防守
    DEFENSE_WAVE3,   // 第三波防守
    COUNTERATTACK    // 反攻
};
```

### 核心策略模块
| 模块 | 功能 |
|------|------|
| `manageEconomy` | 村民生产、资源分配、建筑规划 |
| `manageMilitary` | 兵种训练、作战指挥 |
| `managePriest` | 祭司感化、治疗、安全保护 |
| `manageHunting` | 动物引诱与狩猎 |

### 关键策略
- **前期**：优先食物采集，快速升级铜器
- **中期**：发展经济，训练混编部队（阔剑+复合弓）
- **后期**：祭司感化高价值目标，完成胜利

---

## 📊 游戏配置

`config.json` 关键参数：
```json
{
  "INITIAL_WOOD": 200,
  "INITIAL_MEAT": 500,
  "INITIAL_STONE": 300,
  "GAME_LOSE_SEC": 1500,
  "HOUSE_HUMAN_NUM": 4
}
```

---

## 🛠️ 开发与调试

### 调试输出
使用 `DebugText()` 在右侧调试面板输出信息：
```cpp
DebugText(QString("Frame: %1, Food: %2").arg(frame).arg(info.Meat));
```

### 常用命令
```bash
# 指定地图
./newAOE --map map1.njust

# 指定旋转角度
./newAOE --rotate 90

# 开启全局视野（调试）
./newAOE --GlobalVision true
```

---

## 📝 代码规范

- **头文件**：声明类结构，使用 `#pragma once` 或头文件守卫
- **源文件**：实现具体逻辑，保持函数简洁
- **注释**：关键逻辑添加中文注释
- **常量**：使用 `#define` 或 `constexpr` 定义常量

---

---

## 🕓 版本演进历史

本仓库 `main` 分支共 **163 个提交**，其中 **162 个是 `UsrAI` 的逐版本快照**（每个提交对应一次策略改动），最后 1 个提交为工程当前状态（含全部引擎源码、脚本与文档）。

- 完整版本清单（编号 / 日期 / 标签 / 源码 md5 / 行数）：[`VERSIONS.md`](VERSIONS.md)
- 与课程设计报告《1.7 版本记录》一节对应。

### 常用命令

```bash
# 列出全部版本提交
git log --oneline -- UsrAI.cpp

# 导出某个历史版本的源码
git show <commit>:UsrAI.cpp > UsrAI.cpp

# 回退到某个版本
git checkout <commit> -- UsrAI.cpp UsrAI.h

# 对比两个版本
git diff <commitA> <commitB> -- UsrAI.cpp
```

> **关于本地 `UsrAI.cpp.bak_<日期>_<标签>` 快照文件**：它们的内容已完整保存在提交历史中，因此已在 `.gitignore` 中排除，不再重复入库。本地备份习惯可照旧保留。

### 行尾约定

仓库通过 `.gitattributes`（`* -text`）关闭了 git 的全部行尾转换，保证字节级保真：

| 文件 | 行尾 | 说明 |
|---|---|---|
| `UsrAI.cpp` 等 `.cpp` | 纯 LF | 与构建工具链约定一致 |
| `UsrAI.h` 等 `.h` | 纯 CRLF | 与构建工具链约定一致 |
| `config.json` | 纯 LF | |

> ⚠ 不要移除 `* -text`：否则 git 会将 `.h` 的 CRLF 静默归一为 LF，破坏本地构建前提。

---

## 🙏 致谢

- 原游戏《帝国时代1》（Microsoft，1997）
- NewAOE 项目提供的游戏框架和AI接口

---

## 📮 联系方式

- 项目维护者：金威杨
- 邮箱：3429973898@qq.com
- 项目地址：https://github.com/52Vertin0/Aoe-project
