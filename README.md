# CATIA AI Engineering

面向 CATIA V5 的模型理解、管路与空间几何检查、代理执行及证据报告项目。

本仓库是从开发工作区整理的源码快照（2026-11-12），不包含供应商模型、派生装配、真实案例截图、报告、公司运行环境或离线二进制依赖。原工作区和原有 Git 暂存状态未修改。

## 能力与状态

| 模块 | 当前能力 | 验证边界 |
| --- | --- | --- |
| 检查基线 | 空间框检查、几何/规则/报告模块、CATIA MCP | 来源为 2026-10-12 发布基线；R30 公司内网全流程仍待现场验收 |
| 原生检查工作流 | STP 清点、原位重建检查装配、DMU/GSD/SPA、双视图及报告 | 保留案例脚本；存在固定路径/对象编号，不能直接用于任意模型 |
| 只读模型理解 | 产品结构、定义/实例区分、递归刚体位姿、快照与证据查询 | 合成数据和模拟 COM 验证；完整原生拓扑与工程用途识别尚未实现 |
| AI 编排 | MCP 工具、工作流技能、可替换语言模型适配 | AI 负责解释与编排；几何结论由确定性检查与原生工具提供 |

以上能力尚未统一为已完成验收的一键产品。研究、案例与规划代码不等同于生产功能。

## 目录

- `inspection/`：检查软件源码，保留原包的 project/scripts/vendor 相对结构；不含 runtime。
- `model_understanding_workbench/`：独立只读模型理解模块和测试。
- `tools/`：模型理解 CLI、独立 MCP 启动与验证入口。
- `workflows/`：原生检查与原位重建案例脚本，仅供开发参考。
- `.agents/skills/`：可追溯代理工作流说明。
- `docs/`：整理说明、历史需求、报告要求和源文件清单。

## 快速验证：不连接 CATIA

使用 Python 3.12，在仓库根目录执行：

```powershell
python -m unittest discover -s model_understanding_workbench/tests -v
```

如需验证 MCP 协议，安装依赖后执行：

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-understanding.txt
.venv/Scripts/python.exe tools/validate_understanding.py --output output/understanding-validation-001 --protocol
```

输出目录每次必须不存在。离线测试不代表真实 CATIA 或发动机模型验收。

## CATIA 模型理解入口

Windows、有效 CATIA V5 许可和已运行且注册到 COM 的 CATIA 为前提。先打开待检查模型，再运行：

```powershell
.venv/Scripts/python.exe tools/understand_model.py capture --output output/capture-001
.venv/Scripts/python.exe tools/start_understanding_mcp.py
```

此独立理解入口不负责打开、更新或保存模型。详细数据覆盖和引用限制见 [模块说明](model_understanding_workbench/README.md)。原模块文档中的离线 runtime 路径属于来源工作区，本源码仓库改用自建虚拟环境。

检查软件的安装与限制见 [运行说明](docs/SETUP.md)。

## 执行边界

检查以只读为默认；不自动修复或保存供应商源模型。创建派生检查装配或运行建模实验前，应单独确认操作范围。未知数据输出 UNKNOWN / NOT_EVALUATED，不按通过处理。工程规则须有批准依据，示例阈值不构成航空符合性认证。

截图要求以根目录 AGENTS.md 和现行截图技能为准：两图等大；整体完整模型全部适应；局部仅干涉对全部适应；默认同方向。历史文档中冲突的截图规范仅保留作历史记录。

## 来源与许可

检查基线和案例代码的来源见 `docs/source-manifest.json`；该清单记录整理前源文件校验和，后续文档与配置调整见整理说明。第三方 CATIA MCP 衍生代码保留上游 MIT 许可，见 [第三方说明](THIRD_PARTY_NOTICES.md)。本项目其余代码未额外授予开源许可，拟公开分发前需确认权属及许可证。

## 日常自然语言操作技能

新增 8 个日常操作技能：结构树/BOM 导出、版本差异、来源溯源、特征搜索与相同件候选、测量汇总、定位及显示恢复、批量导出、属性与交付预检。自然语言示例、工具基础和未实现边界见 [日常技能目录](docs/CATIA_DAILY_OPERATIONS.md)。这些是代理工作流，未新增 MCP 端点；完整跨版本匹配、精确同形和接收链确认仍依赖额外工具或证据。

## 本地版本维护

2026-11-12 已验证本地完整包的依赖、149 个 MCP 工具、550 项离线回归、6035 个发布文件哈希及 UI 启动；模型理解另有 32 项测试与协议验证。真实 CATIA 当前不可附着，实机验收仍未完成。旧版清理仅针对已完整归档校验的冗余展开副本，在用 MCP 和被引用版本保留。详见 [维护记录](docs/LOCAL_MAINTENANCE.md)。GitHub 不包含完整运行时，local-launchers 仅适用于记录的本地布局。
