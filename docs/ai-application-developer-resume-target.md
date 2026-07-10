# AI 应用开发工程师简历（项目完成版模板）

> 使用前提：本版本按“项目已完成真实 LLM 接入、混合检索和评估优化”的目标状态撰写。正式投递前，请确保对应能力已经在项目中实现并可演示。

## 个人信息

- 姓名：XXX
- 手机：XXX
- 邮箱：XXX
- 求职方向：AI 应用开发工程师 / LLM 应用开发工程师 / Agent 应用开发工程师
- 当前岗位：嵌入式开发工程师
- 工作年限：X 年
- 所在城市：XXX
- GitHub / 项目地址：XXX

## 个人优势

具备嵌入式网通设备故障检测项目经验，熟悉路由器、光猫等设备的软件缺陷定位流程，了解 DHCP、PPPoE、Wi-Fi、TR-069、固件升级与配置迁移等常见问题场景。具备 AI 应用开发项目实践，能够基于 LangGraph、RAG、LLM API、FastAPI 和 Streamlit 构建面向真实业务场景的 Agent 应用。擅长将设备日志、历史缺陷、模块文档和代码线索组织成可检索、可追溯的知识体系，并通过结构化输出、证据链和评估脚本提升 AI 分析结果的可靠性。

## 技术技能

### AI / LLM 应用开发

  - 熟悉 LLM 应用开发基本流程，了解 Prompt 设计、上下文构造、结构化输出和结果校验。
  - 熟悉 RAG 基本流程，包括文档清洗、切分、Embedding、向量检索、上下文拼接和答案生成。
  - 熟悉 Agent 应用设计思路，了解任务拆解、工具调用、状态管理、异常兜底和执行链路追踪。
  - 熟悉 LangChain / LangGraph 基础用法，能够基于状态流编排多步骤 AI 应用流程。
  - 了解 OpenAI-compatible API 接入方式，能够对接 DeepSeek、Qwen、OpenAI 等大模型服务。
  - 了解 AI 应用常见工程问题，包括模型调用超时、输出格式不稳定、幻觉控制、日志记录和成本控
  制。

### 后端与工程化

- 熟悉 Python、FastAPI、Pydantic，能够设计结构化 AI 服务接口。
- 熟悉 Streamlit，可构建 AI 应用演示页面和内部工具前端。
- 熟悉 pytest，能够为 Agent 节点、API、RAG 检索、日志解析、前端 helper 编写测试。
- 熟悉 Linux、Git、虚拟环境、服务启动、日志排查和基础部署流程。

### 嵌入式与网通领域

- 熟悉网通设备故障分析流程，具备设备日志阅读、模块定位、版本差异分析和问题复现经验。
- 熟悉 DHCP、PPPoE、Wi-Fi、LAN/WAN、TR-069、固件升级等模块常见故障模式。
- 能够将嵌入式排障经验抽象为 AI Agent 的任务流、工具流和证据链。

## 工作经历

### XXX 公司 - 嵌入式开发工程师

时间：20XX.XX - 至今

- 参与路由器 / 光猫等网通设备故障检测项目，负责设备异常场景分析、日志排查和问题定位。
- 分析 DHCP 获取不到 IP、PPPoE 拨号失败、Wi-Fi 断连、固件升级回归等场景下的设备日志和模块状态。
- 协助测试和研发定位软件缺陷，整理复现路径、日志证据、影响范围和修复建议。
- 将实际排障流程沉淀为 AI Bug 分析 Agent 项目的业务流程和样例数据。

## 项目经历

### 项目一：嵌入式网通设备 Bug 分析 Agent

项目时间：2026.06 - 2026.07

项目角色：独立开发

技术栈：

Python、FastAPI、Streamlit、LangGraph、LangChain、Chroma、DeepSeek / Qwen / OpenAI-compatible API、Pydantic、pytest

项目背景：

路由器、光猫等嵌入式网通设备出现故障时，研发通常需要结合设备日志、历史 Bug、模块文档、版本信息和代码线索进行分析。传统排障依赖人工经验，信息分散，定位效率低。该项目将网通设备故障分析流程抽象为 AI Agent，通过 RAG 和 LLM 生成带证据链的根因分析报告。

项目描述：

基于 LangGraph 构建嵌入式网通设备 Bug 分析 Agent。系统输入设备型号、固件版本、问题现象、设备日志和可选堆栈后，自动执行日志解析、Bug 类型识别、历史缺陷检索、模块文档检索、代码线索检索、LLM 根因推理和修复建议生成，最终输出结构化 Bug 分析报告。前端通过 Streamlit 展示“故障现场输入区”和“证据总线”，后端通过 FastAPI 提供 `/analyze` 分析接口。

核心功能：

- 支持 DHCP、PPPoE、Wi-Fi、TR-069、固件升级等网通设备高频故障场景分析。
- 使用 LangGraph 编排多节点 Agent 状态流，包括信息抽取、日志解析、历史 Bug 检索、文档检索、代码检索、根因推理和报告生成。
- 接入真实 LLM API，根据检索到的日志、文档、历史缺陷和代码片段生成根因假设、修复建议和摘要说明。
- 使用 RAG 构建私有知识检索能力，将模块文档、历史 Bug 和代码片段作为模型上下文证据。
- 使用结构化输出约束 LLM 返回 `bug_type`、`summary`、`root_causes`、`evidence`、`fix_suggestions`、`confidence` 等字段。
- 对模型输出进行 Pydantic 校验和异常兜底，避免格式漂移影响前端和接口调用。
- 前端使用 Streamlit 构建现场调试台页面，将证据按 LOG、DOC、BUG、CODE 分组展示，增强可解释性。
- 编写 pytest 测试覆盖 API、Schema、日志解析、LangGraph 节点、RAG 检索、前端证据渲染等核心模块。
- 构建评估脚本，对 bug_type 分类、日志解析覆盖、证据召回和根因命中进行自动化评估。

技术亮点：

- 使用 LangGraph 状态流管理复杂 Agent 执行过程，使每个节点的输入、输出和中间状态可观察、可调试、可测试。
- 将嵌入式排障流程产品化为 AI Agent，而不是简单知识库问答，体现业务建模和工程落地能力。
- 通过 RAG + 证据链约束模型回答，降低 LLM 在专业故障分析场景中的幻觉风险。
- 结合日志规则解析和 LLM 推理：规则层提取关键错误模式，LLM 层负责综合证据生成自然语言根因分析。
- 使用结构化输出和后处理校验，保证 AI 分析结果可被 API、前端和评估脚本稳定消费。

项目成果：

- 完成从知识源、RAG 检索、Agent 状态流、LLM 生成、API 服务、前端页面到评估脚本的完整 AI 应用闭环。
- 支持 DHCP、PPPoE、Wi-Fi 三类首批高频问题演示，并可扩展到 TR-069、升级回归、LAN/WAN 异常等场景。
- 在首版评估集中，bug_type 分类准确率、日志解析覆盖率和证据覆盖率达到 100%。
- 项目可通过 Streamlit 页面演示：输入故障日志后自动生成根因、证据链和修复建议。

### 项目二：OpenClaw 数字员工任务调度平台

项目时间：20XX.XX - 20XX.XX

项目角色：核心开发 / 系统集成

技术栈：

Python、FastAPI、WebSocket、MCP、OpenClaw、Redis、PostgreSQL、Docker、systemd、Feishu Bot、Linux / Windows Worker

项目背景：

团队需要将 AI 数字员工接入真实研发和测试流程，使用户可以通过飞书与 OpenClaw Agent 对话，由 Agent 调用 MCP 工具下发任务，再由分布式 worker 在不同 Linux / Windows 主机上执行自动化脚本、测试任务、提测流程和版本发布流程。

项目描述：

设计并实现 OpenClaw + TaskManager 的数字员工任务调度平台。系统支持多个飞书 channel 接入同一个 OpenClaw Agent，Agent 通过 MCP 调用 `tm_adapter` 暴露的任务管理工具，adapter 根据 worker 的 role、os、容量、负载和 meta 信息将任务路由到分布式 worker 执行。worker 通过 WebSocket 反向连接 adapter，无需开放入站端口，适合跨网段、跨防火墙部署。平台支持数字员工注册、技能同步、任务状态管理、历史任务持久化、飞书通知和多 worker 调度。

核心功能：

- 支持多飞书 Bot / channel 接入，OpenClaw 根据用户 @ 的 Bot 使用对应凭证回复消息。
- 实现 `tm_adapter` 作为 OpenClaw 唯一 MCP server，统一暴露任务创建、状态查询、历史记录、worker 查询等工具。
- 实现分布式 `tm_worker`，支持 Linux / Windows 主机反向连接 adapter 并执行下发任务。
- 设计基于 `role + os + capacity + load + meta` 的任务路由策略，支持按设备 serial、系统类型、角色和资源属性选择 worker。
- 使用 Redis 维护在线 worker、活跃任务和调度状态，使用 PostgreSQL 持久化历史任务。
- 支持数字员工注册表 `digital_employees.json`，管理 ATV 数字员工、烧录数字员工、版本控制数字员工、OpenWrt 发布数字员工等角色。
- 支持将数字员工 skill 同步到 OpenClaw 容器，使 Agent 可根据数字员工角色发现和调用对应能力。
- 支持任务 lifecycle hook 和飞书通知，将任务开始、完成、失败等状态同步给用户。
- 提供一键部署脚本，集成 Docker、Redis、PostgreSQL、OpenClaw 容器、egress 白名单、systemd 服务和 adapter 启停。

技术亮点：

- 用 MCP 将 OpenClaw Agent 与企业内部任务系统解耦，Agent 只需要调用标准工具，不直接感知 worker 部署细节。
- 采用 worker 反向 WebSocket 连接，降低跨网段部署和防火墙配置成本。
- 将任务路由与设备调度分离，adapter 负责 worker 粗粒度选择，设备级执行由 worker 自身根据 meta 决策。
- 使用 Redis + PostgreSQL 分层存储任务状态，兼顾实时调度和历史追溯。
- 通过数字员工注册表和 skill 同步机制，使不同角色数字员工可以共享同一套调度底座。
- 支持多 worker 场景验证，包括注册可见、OS 路由、负载均衡、PENDING 超时等自动化测试。

项目成果：

- 完成 OpenClaw、MCP Adapter、分布式 worker、飞书 channel、Redis/PostgreSQL、部署脚本的集成闭环。
- 支持 ATV 测试、烧录、版本控制、OpenWrt 提测发布等多个数字员工角色。
- 实现从飞书对话到 Agent 工具调用、任务分发、worker 执行、状态回传和历史记录的完整链路。
- 平台可扩展新的数字员工角色、worker 类型和业务脚本，适合作为企业内部 AI 数字员工执行底座。

## 教育经历

### XXX 大学 - XXX 专业

时间：20XX.XX - 20XX.XX

学历：本科 / 硕士

相关课程：数据结构、操作系统、计算机网络、Linux 程序设计、嵌入式系统、Python 编程

## 个人评价

我具备嵌入式网通设备故障分析经验，也具备 AI 应用开发项目实践。相比单纯调用大模型 API，我更关注如何将 LLM、RAG、Agent 状态流、结构化输出、测试评估和真实业务流程结合起来，构建可解释、可维护、可演示的 AI 应用。希望在 AI 应用开发岗位中继续深耕企业级 Agent、RAG 和行业知识库应用落地。

## 简历短版项目描述

**嵌入式网通设备 Bug 分析 Agent**

基于 LangGraph / RAG / LLM API 构建面向路由器、光猫等网通设备的软件缺陷分析 Agent。系统支持输入设备型号、固件版本、故障现象和设备日志，自动执行日志解析、历史 Bug 检索、模块文档检索、代码线索检索和 LLM 根因报告生成，输出 Bug 类型、根因假设、证据链、修复建议和置信度。前端使用 Streamlit 构建现场调试台页面，后端使用 FastAPI 提供结构化分析接口，并通过 pytest 和评估脚本覆盖核心流程。项目首版评估集覆盖 DHCP、PPPoE、Wi-Fi 三类场景，分类准确率、日志解析覆盖率和证据覆盖率达到 100%。

**OpenClaw 数字员工任务调度平台**

基于 OpenClaw / MCP / FastAPI / WebSocket 构建企业内部 AI 数字员工执行平台。系统支持用户通过飞书与 Agent 对话，Agent 调用 MCP 工具创建任务，adapter 根据 worker 的 role、os、容量、负载和 meta 信息将任务路由到分布式 Linux / Windows worker 执行，并通过 Redis 维护活跃状态、PostgreSQL 持久化历史任务。平台支持 ATV 测试、烧录、版本控制、OpenWrt 提测发布等数字员工角色，实现从对话入口、工具调用、任务分发、worker 执行、状态通知到历史追溯的完整闭环。
