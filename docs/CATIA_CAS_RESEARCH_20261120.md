# CATIA V5 AI 辅助造型技术调研

2026 年 11 月 20 日 · 技术路线建议，待实机验证

## 建议

四项能力都纳入设计。采用统一的造型任务描述和评审记录，连接三维概念生成、直接生成与重建曲面、CATIA 局部改型、检查与交付。先做实机基准和共用的检查能力，同时把概念生成和直接生成作为独立对照。首轮以授权的非敏感样件为输入。

造型意图可以用轮廓、特征线、截面、体量和高光表达。工程条件单独指定，例如锁定轮廓、邻接面的连续性和干涉包络。AI 提出候选操作及幅度，几何求解器负责建面和约束，设计师确认视觉效果及交付结果。

## 能力与候选方案

| 能力 | 候选与已公开证据 | 本项目采用方式与缺口 |
|---|---|---|
| 草图、参考图或文字 → 概念三维 | Alias Form Explorer 从文字或画布生成概念网格。其 SubD 流程可用标志曲线引导重拓扑。Microsoft TRELLIS.2 以图像为输入，示例导出 GLB，官方代码仅在 Linux 测试并要求至少 24 GB NVIDIA 显存。 | 用 Alias 作商用对照，核实账号资格、使用方式和素材数据政策。TRELLIS.2 作本地部署候选，使用独立 GPU 环境。本机 RTX 4060 Laptop 只有 8188 MiB 显存，官方配置无法直接满足。统一比较无贴图轮廓、尺度和多视图一致性。 |
| 概念或扫描 → 曲面重建 | Alias 的 SubD/NURBS 工具可重构和继续编辑曲面。Open CASCADE 的 GeomPlate 支持曲线、点和不同阶的几何约束，需进一步检查逼近为 B 样条后的误差。 | 先让设计师确认特征线和面片布局，再比较 Alias 重建、受约束拟合后 STEP 导入、CATIA 原生 GSD 重建。分别评估外形保真、面片数量、接缝质量、输入参考能否编辑。 |
| 文本或点云 → 直接生成 CAD | BrepGen 展示了自由曲面 B-rep 生成。NURBGen 从文字输出控制点、节点、次数与权重等数据。ParaCAD 预印本以点云为条件生成参数曲面，再恢复边与顶点。 | 同批盲测，记录可用输出比例、失败模式、CATIA 导入情况，以及复修耗时。NURBGen 的代码、权重商业使用条件与 ParaCAD 的可运行分发状态待核，评估阶段采用合成数据。 |
| 现有 CATPart → 局部改型 | ICEM Surf 提供控制点编辑、匹配和即时诊断。V5 GSD Automation 支持多截面建面，文档还列有带相切支撑面的导引接口。 | 对有历史的 CATPart 优先改引用到的截面和引导线。对无历史的导入面，比较保留边界后局部重建和外部约束拟合。每个变体在独立文档内生成，核对相邻面、接缝及下游特征。 |
| 检查 → 工程交付 | Alias 的 Class-A 指南同时检查连接连续性、反射线、曲率、工程配合和公差。CATIA Generative Drafting 可建立与三维数据关联的图纸视图。 | 先做 CAD 有效性与 CATIA 更新，随后测量几何质量，再做视觉评审。满足项目要求后试做关联视图，改一次模型以验证图纸更新。 |

各行依据依次见 [Alias Form Explorer](https://help.autodesk.com/cloudhelp/2026/ENU/Alias-WhatsNew/files/wn-whatsnewinalias2026/wn-alias-form-explorer-2026-1.html)、[Canvas to Mesh](https://blogs.autodesk.com/design-studio/2026/03/24/canvas-to-mesh-accelerating-automotive-concept-development/)、[Alias SubD 曲线引导](https://help.autodesk.com/cloudhelp/2026/ENU/Alias-WhatsNew/files/wn-whatsnewinalias2026/wn-alias-subdiv-modeling-2026-1.html)、[TRELLIS.2](https://github.com/microsoft/TRELLIS.2)、[Alias 曲面重建](https://help.autodesk.com/cloudhelp/2027/ENU/Alias-WhatsNew/files/wn-whatsnewinalias2027/2027-Updates-and-Enhancements/wn-alias-modeling-overview-2027.html)、[OCCT GeomPlate](https://dev.opencascade.org/doc/refman/html/class_geom_plate___build_plate_surface.html)、[BrepGen](https://www.research.autodesk.com/publications/brepgen/)、[NURBGen](https://arxiv.org/abs/2511.06194)、[ParaCAD](https://arxiv.org/abs/2607.17093)、[ICEM Surf](https://www.3ds.com/products/catia/icem-surf)、[V5 Automation Loft 接口文档镜像](https://catia-v5-help.anarkia333data.center/online/interfaces/CATGSMIDLItf/interface_HybridShapeLoft_20035.htm)、[Class-A 建模](https://help.autodesk.com/cloudhelp/2026/CHS/Alias-Getting-Started/files/theory-builders/GUID-64611955-D2CC-44F2-98F0-D4F1FE931D8B.html)、[CATIA Generative Drafting](https://3dswym.3dexperience.3ds.com/wiki/catia-user-community/catia-generative-drafting-2-gdr_zMnLy9wbSG6u6Euasa7Phg)。

## 本地接口核查

- 项目 GSD MCP 源码包含坐标点、样条、Sweep、Loft、Fill、Join、Split。当前 Loft 接收截面、导引线、闭合点和方向。Fill 接收边界。两者当前公开参数没有逐边相邻支撑面和连续性配置。
- 上一轮盖板脚本只验证了合成截面的操作计划和模拟 MCP 执行。先前实机附着返回 COM 错误，本轮本机进程检查也未见 CNEXT。CATIA 许可、导入映射、精确曲面延续和图纸关联仍待实机确认。
- 3DEXPERIENCE CATIA LEO 公告列出的侧重点包括机械参数、线框和实体特征。以 V5 当前接口和许可证作为本项目的工程基线。[Dassault CATIA LEO 公告](https://3dswym.3dexperience.3ds.com/wiki/3dexperience-platform-user-s-community/catia-what-s-new-generative-experience-virtual-companions_jelSnBkWSD-zApRp2L49fg)

## 交接数据

任务记录应包含源文件和版本、单位、坐标系、指定对象、锁定区域、特征线、期望视觉变化、接缝连续性目标和验收方式。候选需要关联输入、模型或算法版本、几何输出、可编辑特征及检查记录。

- 概念交付为网格及造型参考线，供评审和重建。
- 曲面交付为可交换的 STEP/B-rep，导入后检查偏差、修剪边和接缝。导入历史通常仅体现交换所得的几何。
- 原生交付为带可编辑截面、导引线或造型参数的 CATPart。按交付要求同时验证依赖特征、图纸视图和尺寸引用。

## 首轮对照试验

选一块有明显特征线、相邻面、锁定边界和下游引用的双曲率外观件。首轮可用授权的脱敏外观件或公开可复用样件，记录使用权限和基准版本。准备两到三张带基准视角的参考图、带真实比例的参考线、基准 CATPart 和已知的人工改型结果。复用同一案例贯通全流程。

1. **概念对照**。同一造型简报分别用人工基线、Alias 和可用的本地模型生成三维候选。固定观察视角、光照和比例，比较轮廓关键点、特征线位置和设计师认可的方案数。
2. **曲面对照**。将同一选定方案分别走特征曲线重建、直接生成和人工基线。记录可导入率、有效几何率、面片布局、关键截面偏差、边界偏差和人工返修时间。对齐采用明确基准，保留采样位置和未覆盖区。
3. **改型对照**。用“抬高肩线并收紧侧面高光，保留分缝位置”这样的任务，对有特征历史版和 STEP 回导版分别测试。记录特征线是否达到目标、接缝是否符合要求、失败如何恢复。成功候选由设计师再调整一次。
4. **交付对照**。在指定接缝核对位置偏差、法向夹角及项目要求的曲率连续性，用反射线和曲率图补充面内质量评审。更新下游特征及一张关联 CATDrawing。采用真实项目公差及设计师评审，记录几何通过率、二次编辑成功率和从输入到可交付的总工时。

首轮把第一处真实双曲率接缝及其变更后的关联更新作为 CATIA 实机验收基准。外部生成模块可同步测试。以选中方案的返修工时和二次编辑能力决定各模块进入日常设计的顺序。当前报告依据公开资料和本地源码，暂无同样件实测数据、采购报价或 GPU 运行基线。
