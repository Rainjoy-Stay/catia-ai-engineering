# 运行与验收

## 只读理解模块

Python 3.12；核心合成测试仅依赖标准库。真实读取需要 Windows/pywin32，MCP 服务需要 mcp。安装 requirements-understanding.txt 后从仓库根目录调用 tools 中入口。

## 检查基线

inspection 保留原包的相对目录。原离线包包含定制运行时、依赖与 .pth 设置，本仓库没有这些二进制文件，因此不能承诺原 cmd 启动器直接运行。

开发环境需将 inspection/project、inspection/scripts 与 inspection/vendor/catia-v5-mcp-server 加入 PYTHONPATH。完整第三方依赖版本参考 dependency-versions.source.json；它是来源环境清单，并非已经在全新环境验证的可移植锁文件。需要根据实际入口安装 OCCT、NumPy、报告及 UI 依赖，并重新验收。

不要直接执行 workflows 中案例脚本：先参数化固定路径、对象编号和输出位置，核对当前文档及模型修改范围。部分工具包含建模、保存和删除能力；这些能力的存在不构成执行授权。

## 验证层级

1. 标准库合成测试：快照、对象身份、位姿和模拟 COM。
2. MCP 协议测试：注册与错误行为，不连接 CATIA。
3. Windows CATIA 实机：引用归属、坐标变换、几何与原生接口。
4. R30 内网：许可、依赖、性能、数据边界及报告全链路验收。

前两项不能替代后两项。此次整理不进行真实模型操作。
