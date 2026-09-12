| 项目 | 配置 |
| --- | --- |
| 操作系统 | Windows 10 / 11（64 位） |
| 集成开发环境 | Qt Creator 5.9.2 |
| 编译器 | MinGW 32 位 g++ 5.3.0（`mingw530_32`） |
| 构建系统 | qmake（`newAOE.pro`）+ `mingw32-make`，Release 构建 |
| 语言标准 | C++11（`std::shared_ptr`、`std::chrono`、lambda、STL 容器） |
| 依赖库 | Qt 5.9.2（Core / Gui / Widgets / Multimedia） |
| 辅助脚本 | Python 3.13（跑局编排与数据统计） |

**开发中遇到的两个环境问题（已解决）**

1．**g++ 静默失败。** 若 `PATH` 中缺少 32 位 MinGW 的 `bin` 目录，`g++ --version` 能正常输出版本号，但任何一次实际编译都会**零输出、直接以 exit=1 退出**。根因是编译器后端 `cc1plus` 找不到依赖的 32 位运行时 DLL。构建脚本因此固定把 `.../mingw530_32/bin` 前置到 `PATH`，并在每次编译后校验返回码与产物时间戳。

2．**Qt Creator 中按 F5 立即崩溃。** 引擎全部使用**相对路径**读取资源（`config.json` 等），若工作目录不是工程根目录，就会因读不到配置而在启动阶段发生除零崩溃。正确做法是把 `config.json` 等资源复制到构建输出目录，而不是修改 `.pro.user`。
