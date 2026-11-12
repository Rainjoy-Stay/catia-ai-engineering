# CATIA 模型理解开发入口 v0.1

这是从检查项目扩展出的独立只读理解基线。开发目录与历史发布包分离，运行时复用 `release_build/CATIA_Offline_20261012/runtime/python.exe`；未改旧检查入口或当前 MCP 配置。

当前实现：CATPart/CATProduct 结构读取、零件定义与安装实例区分、递归刚体位姿、读取覆盖率、快照级对象 ID、证据查询。模型对象、源文件及 CATIA 选择均不修改。仅附着正在运行且已注册到 COM 的 CATIA。

尚未实现：原生面边邻接、面级持久引用、完整曲面清点、尺寸测量、接触和功能识别、自然语言问答前端、跨版本几何对应。HybridBody 当前只读取顶层数量，参数和约束未读取。结构读取完成不表示几何或工程语义已理解。

## 运行

在项目根目录执行，输出路径每轮使用新目录：

```powershell
& 'release_build/CATIA_Offline_20261012/runtime/python.exe' -X utf8 tools/understand_model.py capture --output output/model_understanding_run_001
```

入口不打开模型、不切换文档、不执行更新和保存。CATIA 未连接或源状态变化时写失败诊断，不生成成功快照。Saved 状态只能作为辅助状态检查，不能证明任意几何内容完全不变。

```powershell
& 'release_build/CATIA_Offline_20261012/runtime/python.exe' -X utf8 tools/understand_model.py query output/model_understanding_run_001/snapshot.json 'Bolt'
& 'release_build/CATIA_Offline_20261012/runtime/python.exe' -X utf8 tools/understand_model.py describe output/model_understanding_run_001/snapshot.json OCC_0_1
& 'release_build/CATIA_Offline_20261012/runtime/python.exe' -X utf8 tools/understand_model.py point output/model_understanding_run_001/snapshot.json OCC_0_1 0 0 0
```

`point` 只执行坐标变换，不是几何测量。根坐标系由根产品定义；未知实例位姿及其后代世界位姿返回 UNKNOWN。名称或零件号重复时返回候选，不自动选择。

结构相同的两个观察不能证明几何没变化。`compare` 明确只比较已捕获数据；几何变化检测仍不可用。每个对象 ID 必须与 snapshot_id 一起使用，不能跨快照直接绑定或将枚举编号当作 CATIA 持久引用。

## 独立 MCP 服务

```powershell
& 'release_build/CATIA_Offline_20261012/runtime/python.exe' -X utf8 tools/start_understanding_mcp.py
```

服务提供 `catia_understanding_capture`、`catia_understanding_query_snapshot`、`catia_understanding_describe_snapshot` 和 `catia_understanding_point_snapshot`。没有自动注册到 Codex；需要接入时将此模块加入维护中的 CATIA MCP 或配置该独立服务。该目录提供可测试工具实现，不宣称当前会话已加载新工具。

工具查询必须携带采集返回的 snapshot_id。失败重采集清空旧快照；查询历史快照明确返回 `CAPTURED_SNAPSHOT_NOT_LIVE_STATE`。离线 CLI 与 MCP 共用同一读取和查询实现。

## 验证

```powershell
& 'release_build/CATIA_Offline_20261012/runtime/python.exe' -X utf8 tools/validate_understanding.py --output output/model_understanding_validation_001 --protocol
```

输出单元测试日志、合成观察/快照、查询示例和机器可读验证结果。测试模型完全为手写合成数据及模拟 COM，不是发动机实机验收。真实 CATIA 的 GetComponents 封送、单位、实例引用归属和深层装配坐标应在实机单独验证。

## 后续验收

先用小型真实 CATProduct 核对一件多实例、多层旋转和平移、无法读取的组件与源状态，再处理原生 B-Rep 和可解析引用。用实际接口数据和几何内核补充证据后，才扩展机匣、盘、轴、叶片、轴承、密封与管路系统语义。
