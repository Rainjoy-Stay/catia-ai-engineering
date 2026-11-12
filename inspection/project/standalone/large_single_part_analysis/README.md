# 大型单 CATPart 精确检查


## 报告截图代码说明（2026-10-10）

本节为当前截图代码说明；本文旧黄/红配色、全图像素扫描或中央默认框的描述，在新报告创建中以本节修订为准。其他业务要求、历史事实和既有报告结果保持原义。

涉及当前模型配图或报告创建时，先读[原始代码与修订入口](../../tools/report_capture_reference_20260920/README.md)。三段原始代码解释相关邻域整体取景、双方隔离局部取景及高亮标注；正式通用截图和罗盘排除修订代码也保存在同目录，可随本项目使用。

对象A/B采用UI橙色RGB(255,161,56)与青色RGB(31,214,224)，背景约20%不透明、取景目的与既有布局不变。明确排除罗盘、树、工具栏和坐标轴，只检测目标屏幕ROI；缺可靠像素或掩膜影响目标则待复核，不补中央框。高亮框不是精确干涉边界，原始脚本固定Body编号、旧颜色阈值与统一黄色恢复不可直接沿用。

独立核心模块，面向导入 STEP/IGES 后形成的多 Body 大型 CATPart。调用方提供 OCCT 精确 B-Rep manifest 和后端；模块自身不连接 CATIA、不导出文件、不修改模型，也不使用网格裁决。

流程：过滤独立 Solid → 精确 AABB 的 Sweep-and-Prune 粗筛 → 仅对候选计算 OCCT 最小距离和公共体积 → 输出内部穿模、接触、低净距、无干涉及覆盖门禁。开放 Shell、Surface 和无效 B-Rep 单列为 REVIEW，不能混入 Solid 公共体积结论。

`INTERNAL_SOLID_INTERFERENCE` 由正公共体积确认；零距离但无公共体积为 `SOLID_CONTACT`；候选截断或精确计算异常会使 `coverage_complete=false`。所有输出固定包含 `mesh_used=false` 和 `source_modified=false`。

该目录保持为可独立测试的核心；主项目适配层负责从 CATIA 原文件或临时只读 STEP 导出取得 OCCT manifest，并将结果转换为统一 finding、JSON 和 Word。

现已由主项目完成适配：`--large-single-part-source`直接读取原始STEP/IGES；`--large-single-part-active`通过CATIA `ExportData`创建临时STEP，再由隔离子进程执行OCCT。入口实时转发载入、粗筛和精确候选进度，按规则限制总运行时间；成功、异常或超时都会终止子进程并清理临时目录。失败仍生成结构化ERROR报告。流程还会校验源Saved状态、Body数量及导出Solid数量，数量不一致时关闭完整性门禁。活动CATPart分支在生成Word前自动按报告中的精确Body映射定位待复核项，采集前视和等轴测证据图并写入finding；活动文档名称不一致时立即停止截图，禁止把其他模型的画面写入报告。

一键入口会同时启动CATIA弹窗守卫。守卫只自动确认文本和按钮均精确匹配的“重复文档标识”信息框；保存、覆盖、删除、更新诊断以及所有未知弹窗一律不点击，并把处置记录写入本次运行目录的`catia-dialogs.jsonl`和结构化审计字段。
