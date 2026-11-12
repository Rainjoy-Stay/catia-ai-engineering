# CATIA 日常自然语言操作技能

新增日期：2026-11-12。本目录技能是代理操作流程，当前未新增 CATIA MCP 端点、自动按钮或几何算法，也未连接真实模型验收。运行依赖目标环境实际注册的工具、CATIA 版本和许可。

## 能力入口

| 日常工作 | 技能 | 可直接说的话 | 当前实现边界 |
| --- | --- | --- | --- |
| 结构树/BOM 导出 | [catia-tree-export](../.agents/skills/catia-tree-export/SKILL.md) | 导出当前整机树，带层级、路径、件号、版本和描述 | 有结构/实例/件号读取基础；版本和描述须补读；表格转换由代理执行 |
| 两版差异清单 | [catia-revision-diff](../.agents/skills/catia-revision-diff/SKILL.md) | 对比两版，区分增删、属性变化和安装位置变化 | 现有 compare 仅判断捕获结构变化；完整跨版本匹配及几何差异尚无通用实现 |
| 来源与接收链 | [catia-model-provenance](../.agents/skills/catia-model-provenance/SKILL.md) | 整理来源、接收凭证和转换链，缺证据的标出来 | 文件/引用事实可采集；供应商和接收链需授权外部记录，不靠模型外观推断 |
| 搜索/相同件 | [catia-search-duplicates](../.agents/skills/catia-search-duplicates/SKILL.md) | 搜索所有支架，按体积面积找疑似重复件 | 有名称搜索、特征/参数和整件惯性工具；批量签名及精确同形未集成为独立服务 |
| 测量汇总 | [catia-measurement-summary](../.agents/skills/catia-measurement-summary/SKILL.md) | 汇总体积面积质量和重心，缺材料的单列 | 原生测量工具按对象可用；质量取决于密度；汇总须核对单位、范围、位姿 |
| 定位与显示 | [catia-display-review](../.agents/skills/catia-display-review/SKILL.md) | 定位这个件，临时隔离后恢复 | 有选择与显隐；颜色、透明度和相机完整恢复须具备读取/恢复工具 |
| 批量格式导出 | [catia-batch-export](../.agents/skills/catia-batch-export/SKILL.md) | 导出这些零件的 STEP，附文件校验清单 | 单文档导出已存在；批量编排、转换许可和重导入核验需现场验证 |
| 属性与交付预检 | [catia-metadata-audit](../.agents/skills/catia-metadata-audit/SKILL.md) | 对照 BOM 检查缺项和版本，先别改 | 有参数和结构读取；版本/描述/材料覆盖及 PLM 权限取决于工具；写回限已支持字段 |

## 共同执行约定

1. 从请求解析任务、准确文档/子树、输入版本、输出格式和路径。默认只读、当前文档可读范围、新输出目录；需要比较两版而只提供一版时继续采集独立基线，并请求缺失版本，不能用当前模型复制品冒充另一版。
2. 实际操作前发现可用结构化工具，获取文档信息及 manifest/理解快照；记录名称、类型、完整路径（未保存则 SESSION）、Saved、snapshot_id、范围、方法、单位和坐标系。定义与实例分开；同名必须解析路径，不以枚举编号当跨版本身份。
3. 可优先查找的工具名包括 catia_list_documents、catia_get_active_document_info、catia_get_model_manifest、catia_get_part_geometry_inventory、catia_search_elements、catia_get_feature_details、catia_get_parameters、catia_get_inertia、catia_measure_distance、catia_select_elements、catia_set_visibility、catia_export。工具名只作为发现线索，使用前读取实际输入输出约定；部署包和会话可能不同。不要凭说明虚构已注册调用。
4. 独立理解入口为 tools/understand_model.py；MCP 源码为 model_understanding_workbench/mcp_tools.py。当前覆盖结构、件号、定义/实例、位姿与快照查询；不含版本、描述、原生拓扑、质量、相同件、来源链和跨版映射。CLI 是同一读取器的本地入口，源码存在不代表 MCP 已部署。
5. 当前可用的 catia-model-understanding 处理模型操作；若不可用，最低流程为准确绑定文档、只读捕获、逐项留证、记录失败与覆盖率，不替换为普通桌面点击或任意 COM 写入。需要新增工具时记录所需读取/写入接口及验收条件；无工具时明确部分完成。
6. 大模型去重读取定义、按预算分块并报告截断；数量至少含 expected、read、failed、omitted。未读取不是空集合，未测量不是零值。UNKNOWN、NOT_READ、UNSUPPORTED、READ_FAILED、AMBIGUOUS、NOT_EVALUATED 分别保留，不混成成功。
7. CSV/JSON 是默认可移植交付；CSV 以 UTF-8 BOM、标准引号转义输出，防止文本单元格被 Excel 解释为公式。对外部文本中（忽略前导空白后）以 =、+、-、@ 或控制字符开头的值进行文本保护，同时在 JSON 保留原值；实际数值列保留类型。用户要 xlsx 时使用可用表格技能生成真正工作簿。
8. 读取和导出不触发源文档 Save、SaveAs、Update、重链接、几何修复或重命名。临时选择/显隐在任务结束恢复原状态；不能证明可恢复时缩小变化。允许用户明确要求保留显示。导出文件写新目录，避免碰撞和覆盖。
9. 结果证据至少包含对象路径、快照、原值、读取方法/状态和适用范围。文件系统事实、模型声明、测量事实与工程解释分别记录。来源/版本/工程标准缺证据时不得臆测；量化签名不作持久身份和可替换性证明。
10. 交付写明已完成、未完成、失败对象、数据覆盖及模型是否保存。任务有授权的必要操作继续完成，不重复索要已有授权；技能不会扩大到对外发送、批量替换、删除或保存模型。

## 输出记录建议

公共 envelope：schema_version、task、captured_at（带时区）、source_documents、snapshot_ids、scope、coverage、units、coordinate_frame、methods、limitations、artifacts。

清单行：object_id（快照内）、occurrence_path、definition_reference、evidence_ref、read_status、values。字段本身缺失时另外记录 field_status，不用空字符串同时表达空值和未读取。

差异行：before_ref、after_ref、match_basis、match_status、change_types、field、old_value、new_value、tolerance、evaluation_status。ADDED/REMOVED 需另一版完整范围支持；歧义候选不可强行进入增删数量。

签名行：definition_ref、closure_status、volume_mm3、area_mm2、method、tolerances、candidate_peer、verification_status。开放曲面分组另列，不混合闭合实体。

来源边：from_artifact、to_artifact、event_type、event_time、record_ref、verification_status。接收或转换边没有凭据时保持 UNVERIFIED。

## 自检场景与预期

- 同件三实例：树清单三行，定义测量一次，数量三；不能把根装配和三个实例重复累加。
- 同名兄弟、兄弟重排：路径保留索引；跨版索引不作身份，无法匹配时 AMBIGUOUS。
- 一版未加载引用：不能把另一版对应项直接报新增/删除。
- 同体积同面积的不同几何：仅为签名候选，无精确形状证据不得报完全相同。
- 零体积开放壳或缺密度：不进入有效实体体积/质量汇总，不填 0 伪装测量成功。
- 未保存内存模型：磁盘 SHA-256 只绑定磁盘文件，不证明当前内存几何。
- 缺接收登记：报告文件事实和接收链缺口，不编造供应商或接收时间。
- 显示状态不能读取：只做可恢复的定位，不能全隐藏后用“全部显示”冒充恢复。
- 名称以公式符号开头：CSV 保护，JSON 保留原名；不得直接作为输出文件路径。
- 用户只要求预检：产生问题清单，不写参数、不保存。

这些是人工检查的行为要求，并非真实 CATIA 自动化测试通过记录。技能格式、链接验证结果另见 daily-skills-validation.json。
