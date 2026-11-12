# STP 转换伪干涉过滤层 v1.0

2026-09-17 定向复核补充：旧标签加体积匹配已发现三处错配，STABLE_SOURCE_LABEL_VOLUME_VERIFIED 不再作为可靠来源。标签只生成候选，必须同时通过空间特征检查；重复几何竞争时拒绝配对。旧覆盖率保存为历史审计，当前覆盖率按安全来源重新计算。相关 36 个 Solid 已全部在保留的单 Body 缓存中建立唯一空间对应。

独立模块不修改几何、不调用 CATIA、不依赖 AI。输入精确 OCCT 公共体积、距离、Solid 有效性、已验证来源及接口证据。原始相交事实保持不变，统一结果在 Word 报告输入前重新裁决。

|分类|裁决|必要证据|
|---|---|---|
|TRUE_PENETRATION 真实穿模|FAIL|有效的两个单 Solid、精确重叠、不同已验证来源、非设计重叠已确认|
|NORMAL_PIPE_CONNECTION 正常管路连接|PASS|已验证接口 ID，全部重叠限定在该接口，无冲突的穿模证据|
|CONTACT_OR_COPLANAR 接触或共面|NOT_EVALUATED|公共体积为零、距离在接触容差内；仍需设计关系|
|SAME_SOURCE_FRAGMENTATION 同源转换碎裂|NOT_EVALUATED|同一文档同一已验证 Body；并不证明原始几何无缺陷|
|MICRO_CONVERSION_ARTIFACT 微小转换伪影候选|NOT_EVALUATED|有效精确公共体积在微小阈值内；仅为怀疑，不证明是转换噪声|
|UNDETERMINED 无法确定|NOT_EVALUATED|有效性、来源、设计意图不足、非有限数或相互矛盾证据|
|CLEAR 无相交|PASS|有效精确 Solid、公共体积为零且超出接触容差|

默认微小体积阈值 1e-6 mm³、接触容差 1e-5 mm 是算法复核阈值，不是工程验收标准。微小真实穿模也可能进入待评估，因此待评估必须人工或进一步精确复核，不能视为检验通过。当前没有通过体积比例、共轴外观或近邻关系自动放行。

来源链通过几何复核的 Body 映射建立；无映射方法时拒绝形成来源键。OCCT STEP 清单逐 Solid 记录局部 Face ID；旧清单缺 Face 时明确 faces_complete=false，不补造已验证关系。Face ID 只在该次转换中有效，不代表源 CATIA Face 编号。批次 Solid 的父 ID 带批次限定，局部 Face ID 与父 Solid 组合解析。

验收：运行项目 tests/test_step_interference_filter.py。使用真实 OCCT 方块和空心圆管验证分类。主流程在 build_large_single_part_result 中过滤；补充 Body 救援映射后再次过滤。重复运行保持旧状态审计和原始相交证据。缓存检查点仅缓存几何事实，不缓存过滤结论。

现阶段局限：非设计重叠确认与接口确认由外部可追溯复核提供；不自动重建 STP 管路语义。轻量 Solid 清单有效性未知时保持待评估，需要后续按候选对补充 OCCT 有效性检查。过滤层已经接入统一结果边界；直接读取原始 analysis.findings 的消费者必须明确其为未经裁决的几何事实。
# v1.1 来源证据与微小穿模优先级

已确认的不允许重叠在不同且已验证来源的有效精确实体间发生时，任何正相交体积均判 TRUE_PENETRATION / FAIL；微小体积规则不能覆盖该证据。未通过六方向内部采样不构成消除相交的依据。

原始 STEP 实体绑定已验证且经精确内核读取后复现正相交体积时，使用 source_overlap_evidence 保留来源证据。无工程意图依据时仍为 UNDETERMINED / NOT_EVALUATED，不因体积小而宣称转换伪影。该证据不代表原始与导出几何完全一致，也不能签发 PASS。
