# 项目截图与报告

涉及 CATIA 截图、干涉双视图或报告配图时，使用 `.agents/skills/catia-native-dual-view/SKILL.md`。

统一要求：两图等大；整体图显示完整模型后全部适应；局部图隐藏干涉对以外的对象后对干涉对全部适应。默认同方向。该用户确认要求优先于旧资料中的邻域整体图、大局部小整体和强制不同方向要求。

几何检查继续使用 catia-spatial-inspection-report，模型操作使用可用的 catia-model-understanding。截图技能不改变几何判定，不扩大模型修改或保存授权。

需要从已打开 STP/CATPart 清点并重建原位检查装配，继而完成原生 DMU/GSD/SPA 检查、双视图截图到竖版 A4 Word 报告的整套流程时，使用 `.agents/skills/catia-native-inspection-word/SKILL.md`；它统筹上述技能，不替代各自的判定与操作约束。

# CATIA 日常自然语言操作

结构树/BOM 导出、版本差异、模型来源、特征/相同件搜索、测量汇总、临时定位显示、批量格式导出和属性预检，按 `docs/CATIA_DAILY_OPERATIONS.md` 路由到对应 `.agents/skills/catia-*/SKILL.md`。这些是代理流程技能，不表示完整跨版本匹配、来源接收链或精确同形算法已实现；执行前核对实际工具与覆盖范围。
