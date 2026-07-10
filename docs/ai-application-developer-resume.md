# AI 应用开发工程师简历

> 说明：请将姓名、电话、邮箱、学校、公司名、时间等占位符替换为你的真实信息。项目描述已按当前代码实现整理，未虚构“已接入真实大模型 API”。

## 个人信息

- 姓名：XXX
- 手机：XXX
- 邮箱：XXX
- 求职方向：AI 应用开发工程师 / LLM 应用开发工程师 / Agent 应用开发工程师
- 当前身份：嵌入式开发工程师
- 工作年限：X 年
- 所在城市：XXX
- GitHub / 作品地址：XXX

## 个人优势

具备嵌入式网通设备故障检测项目经验，熟悉路由器、光猫等设备的软件缺陷定位流程，了解 DHCP、PPPoE、Wi-Fi、TR-069、固件升级等常见故障场景。正在向 AI 应用开发方向转型，已独立完成基于 LangGraph / RAG 的嵌入式网通设备 Bug 分析 Agent 项目，能够将 LLM 应用框架、检索增强、状态流编排、后端 API、前端演示页面和评估脚本结合起来，构建可运行、可解释、可测试的 AI 应用原型。

## 技术技能

### AI 应用开发

- 熟悉 RAG 基本流程：知识源整理、文档切分、Embedding、向量检索、证据注入、结构化输出。
- 熟悉 Agent 应用设计思路：任务拆解、工具调用、状态管理、证据链输出、异常兜底。
- 熟悉 LangChain / LangGraph 基础使用，能够基于 LangGraph 构建多节点状态流。
- 了解 Prompt Engineering、结构化输出、幻觉控制、RAG 评估、Agent 可观测性等 AI 应用工程问题。
- 了解 OpenAI / DeepSeek / Qwen 等模型 API 接入方式，具备将本地规则链替换为真实 LLM 调用的设计能力。

### 后端与工程化

- 熟悉 Python，能够使用 FastAPI 构建后端接口，使用 Pydantic 做请求和响应数据校验。
- 熟悉 Streamlit，可快速构建 AI 应用演示页面。
- 熟悉 pytest，能够为日志解析、API、状态流、前端 helper 等模块编写单元测试。
- 熟悉 Git、Linux 常用命令、虚拟环境、依赖管理和基础服务启动排查。

### 嵌入式与网通领域

- 熟悉嵌入式软件开发和故障定位流程，具备设备日志分析、异常复现、模块定位经验。
- 熟悉网通设备常见业务模块：DHCP、PPPoE、Wi-Fi、LAN/WAN、固件升级、配置迁移等。
- 能够从设备日志、版本差异、历史缺陷和代码线索中分析潜在根因。

## 工作经历

### XXX 公司 - 嵌入式开发工程师

时间：20XX.XX - 至今

工作内容：

- 参与路由器 / 光猫等网通设备故障检测相关项目，负责设备异常场景分析、日志排查和问题定位。
- 根据设备运行日志、模块状态和版本差异，分析 DHCP、PPPoE、Wi-Fi、升级回归等典型问题。
- 配合测试和研发定位软件缺陷，整理复现路径、日志证据和修复建议。
- 参与嵌入式软件模块开发和问题修复，熟悉 Linux 环境下的调试、编译和基础排障流程。

工作成果：

- 积累了网通设备真实故障分析经验，为后续构建 AI Bug 分析 Agent 提供了业务基础。
- 能够将嵌入式故障分析流程抽象为“日志解析 -> 历史问题匹配 -> 模块定位 -> 根因分析 -> 修复建议”的结构化流程。

## 项目经历

### 项目一：嵌入式网通设备 Bug 分析 Agent

项目时间：2026.06 - 2026.07

项目角色：独立开发

技术栈：

Python、FastAPI、Streamlit、LangGraph、LangChain Document、Chroma、pytest、Pydantic

项目背景：

在路由器、光猫等嵌入式网通设备研发过程中，DHCP 获取不到 IP、PPPoE 拨号失败、Wi-Fi 客户端断连、固件升级后配置异常等问题通常需要结合设备日志、历史 Bug、模块文档和代码线索进行分析。传统排障依赖人工经验，信息分散，分析过程不易复用。

项目描述：

基于 LangGraph 构建嵌入式网通设备 Bug 分析 Agent。系统支持输入设备型号、固件版本、问题现象和设备日志，自动执行日志解析、历史 Bug 检索、模块文档检索、代码线索检索、根因假设生成和修复建议输出，最终生成带证据链的结构化 Bug 分析报告。

核心功能：

- 支持输入设备型号、固件版本、问题现象、设备日志、可选堆栈和模块提示。
- 使用 LangGraph 将 Bug 分析流程拆分为多个节点，包括故障信息提取、日志解析、历史 Bug 检索、文档检索、代码检索、根因生成和报告输出。
- 构建本地知识源，包含模块说明文档、历史缺陷样例和模拟 C 代码片段。
- 输出结构化分析结果，包括 bug_type、summary、root_causes、evidence、fix_suggestions、confidence。
- 前端使用 Streamlit 构建“现场调试台”风格页面，将证据按 LOG、DOC、BUG、CODE 分组展示，便于复查分析依据。
- 提供 FastAPI `/analyze` 接口和 `/health` 健康检查接口，便于前端和外部系统调用。
- 编写 pytest 测试用例覆盖 schema、API、日志解析、Graph 节点、RAG 数据、前端 helper 等模块。
- 编写评估脚本，覆盖 DHCP、PPPoE、Wi-Fi 三类典型场景，输出分类准确率、日志解析覆盖率和证据覆盖率。

技术亮点：

- 使用 LangGraph 状态流替代单次 Prompt 调用，将复杂 Bug 分析流程拆成可观察、可测试的节点。
- 使用 RAG 思路将模块文档、历史 Bug 和代码线索作为证据来源，降低无依据生成风险。
- 将嵌入式网通设备真实排障流程抽象为 AI Agent 工作流，区别于普通知识库问答或 ChatBot。
- 前端证据总线按 LOG、DOC、BUG、CODE 展示，使根因分析结果具备可解释性和可追溯性。
- 当前版本使用本地规则链和检索流程验证架构，后续可平滑接入 OpenAI、DeepSeek 或 Qwen 等真实 LLM。

项目成果：

- 完成从后端 API、Agent 工作流、知识检索、前端页面到测试评估的完整 AI 应用原型。
- 首版评估集覆盖 DHCP、PPPoE、Wi-Fi 三类高频网通设备故障。
- 当前规则链路在首版评估集中实现 bug_type 分类准确率、日志解析覆盖率、证据覆盖率均为 100%。
- 项目具备面试演示能力，可通过 Streamlit 页面展示输入故障日志后生成根因、证据链和修复建议。

面试可讲重点：

- 该项目不是普通聊天机器人，而是面向嵌入式网通设备 Bug 分析的 Agent 应用。
- LangGraph 用于编排状态流，RAG 用于补充私有知识和证据来源。
- 项目强调可解释性：每个结论都尽量关联日志、文档、历史 Bug 或代码线索。
- 当前项目未虚构真实模型能力，下一步计划接入真实 LLM 做根因报告生成和自然语言总结。

### 项目二：OpenClaw 数字员工任务调度平台

项目时间：20XX.XX - 20XX.XX

项目角色：核心开发 / 系统集成

项目背景：

团队需要将 AI 数字员工接入研发和测试流程，使用户可以通过飞书与 OpenClaw Agent 对话，由 Agent 调用 MCP 工具下发任务，再由分布式 worker 在不同 Linux / Windows 主机上执行自动化脚本、测试任务、提测流程和版本发布流程。

项目描述：

基于 OpenClaw + TaskManager 构建数字员工任务调度平台。系统支持多个飞书 channel 接入同一个 OpenClaw Agent，Agent 通过 MCP 调用 `tm_adapter` 暴露的任务管理工具，adapter 根据 worker 的 role、os、容量、负载和 meta 信息将任务路由到分布式 worker 执行。worker 通过 WebSocket 反向连接 adapter，降低跨网段和防火墙部署成本。

核心功能：

- 支持多飞书 Bot / channel 接入，OpenClaw 根据用户 @ 的 Bot 使用对应凭证回复消息。
- 实现 `tm_adapter` 作为 OpenClaw 唯一 MCP server，统一暴露任务创建、状态查询、历史记录、worker 查询等工具。
- 实现分布式 `tm_worker`，支持 Linux / Windows 主机反向连接 adapter 并执行下发任务。
- 设计基于 `role + os + capacity + load + meta` 的任务路由策略，支持按设备 serial、系统类型、角色和资源属性选择 worker。
- 使用 Redis 维护在线 worker、活跃任务和调度状态，使用 PostgreSQL 持久化历史任务。
- 支持数字员工注册表 `digital_employees.json`，管理 ATV 数字员工、烧录数字员工、版本控制数字员工、OpenWrt 发布数字员工等角色。
- 支持任务 lifecycle hook 和飞书通知，将任务开始、完成、失败等状态同步给用户。
- 编写部署和验证文档，支持 adapter、worker、OpenClaw 容器、Redis/PostgreSQL 的一体化部署和端到端测试。

技术亮点：

- 使用 MCP 将 OpenClaw Agent 与内部任务系统解耦，Agent 通过标准工具创建和查询任务。
- 采用 worker 反向 WebSocket 连接，适合跨网段、跨防火墙的分布式执行环境。
- 使用 Redis + PostgreSQL 分层存储任务状态，兼顾实时调度和历史追溯。
- 通过数字员工注册表和 skill 同步机制，使不同角色数字员工共享同一套任务调度底座。
- 支持多 worker 场景验证，包括注册可见、OS 路由、负载均衡和 PENDING 超时。

项目成果：

- 完成 OpenClaw、MCP Adapter、分布式 worker、飞书 channel、Redis/PostgreSQL、部署脚本的集成闭环。
- 支持 ATV 测试、烧录、版本控制、OpenWrt 提测发布等多个数字员工角色。
- 实现从飞书对话到 Agent 工具调用、任务分发、worker 执行、状态回传和历史记录的完整链路。
- 平台可扩展新的数字员工角色、worker 类型和业务脚本，适合作为企业内部 AI 数字员工执行底座。

## 教育经历

### XXX 大学 - XXX 专业

时间：20XX.XX - 20XX.XX

学历：本科 / 硕士

相关课程：

- 数据结构
- 操作系统
- 计算机网络
- Linux 程序设计
- 嵌入式系统
- Python 编程

## 证书与学习

- LangChain / LangGraph：学习并完成基于 Agent 状态流的项目实践。
- RAG 应用开发：理解文档切分、向量检索、证据注入、评估指标等核心流程。
- FastAPI / Streamlit：完成 AI 应用后端接口和前端演示页面开发。
- pytest：为 AI 应用核心流程编写自动化测试。

## 个人评价

我具备嵌入式网通设备故障分析经验，也具备 AI 应用开发的项目实践能力。相比只会调用大模型 API，我更关注如何把 LLM、RAG 和 Agent 融入真实业务流程，并通过状态流、结构化输出、证据链、测试和评估保证系统可解释、可维护、可迭代。希望在 AI 应用开发岗位中，继续深耕企业级 Agent、RAG 和行业知识库应用落地。

## 简历短版项目描述

**嵌入式网通设备 Bug 分析 Agent**

基于 LangGraph / RAG 构建面向路由器、光猫等网通设备的软件缺陷分析 Agent。系统支持输入设备型号、固件版本、问题现象和日志，自动执行日志解析、历史 Bug 检索、模块文档检索、代码线索检索和根因报告生成，输出 Bug 类型、根因假设、证据链和修复建议。前端使用 Streamlit 构建现场调试台页面，后端使用 FastAPI 提供结构化分析接口。项目首版评估集覆盖 DHCP、PPPoE、Wi-Fi 三类场景，规则链路在评估集中实现分类准确率、日志解析覆盖率和证据覆盖率 100%。

**OpenClaw 数字员工任务调度平台**

基于 OpenClaw / MCP / FastAPI / WebSocket 构建企业内部 AI 数字员工执行平台。系统支持用户通过飞书与 Agent 对话，Agent 调用 MCP 工具创建任务，adapter 根据 worker 的 role、os、容量、负载和 meta 信息将任务路由到分布式 Linux / Windows worker 执行，并通过 Redis 维护活跃状态、PostgreSQL 持久化历史任务。平台支持 ATV 测试、烧录、版本控制、OpenWrt 提测发布等数字员工角色，实现从对话入口、工具调用、任务分发、worker 执行、状态通知到历史追溯的完整闭环。

## 简历投递建议

- 如果投递“AI 应用开发工程师”：突出 FastAPI、LangGraph、RAG、Agent、项目完整度。
- 如果投递“LLM 应用开发工程师”：突出 RAG、结构化输出、幻觉控制、真实模型接入计划。
- 如果投递“Agent 开发工程师”：突出 LangGraph 状态流、节点拆分、工具检索、证据链。
- 如果投递“嵌入式 + AI”相关岗位：突出网通设备业务背景和 AI 故障分析场景。
