# 项目文档入口

本文档目录用于系统学习当前 Bug 分析 Agent 项目。

建议先阅读详细设计文档，再对照 PlantUML 架构图和源码理解实现。

## 详细设计文档

- [嵌入式网通设备 Bug 分析 Agent 设计与实现详解](architecture/design-and-implementation.md)
- [真实故障 Case 接入与评估规范](evaluation/real-case-intake.md)
- [生产化扩展与运行手册](production/productionization.md)

这份文档是主文档，包含：

- 项目目标和应用场景。
- 项目目录结构。
- 总体架构分层。
- LangGraph 状态流设计。
- 从前端点击到后端生成报告的完整流程。
- LLM 接入方式。
- RAG 和本地知识源设计。
- 评估指标和评估脚本。
- 测试体系。
- 推荐源码阅读路线。
- 常用启动、测试、评估命令。

## 面试学习文档

- [AI Agent 应用岗位八股文学习手册](interview/ai-agent-application-interview-guide.md)

这份文档用于准备 AI Agent 应用开发岗位面试，包含：

- LLM 基础。
- Prompt 工程。
- RAG。
- 向量数据库。
- Agent 基础。
- 工具调用。
- LangChain / LangGraph。
- 结构化输出。
- fallback。
- 评估体系。
- 可观测性。
- 安全。
- 工程化。
- 高频面试题和项目表达模板。

## PlantUML 架构图

- [系统组件结构图](architecture/system-components.puml)
- [LangGraph 状态流图](architecture/langgraph-state-flow.puml)
- [API 调用时序图](architecture/api-sequence.puml)
- [LLM 调用与规则兜底流程图](architecture/llm-fallback-flow.puml)
- [评估流程图](architecture/evaluation-flow.puml)
- [运行部署图](architecture/runtime-deployment.puml)
- [生产化运行部署图](architecture/production-runtime.puml)
- [后台任务与复核时序图](architecture/queued-analysis-sequence.puml)
- [Git 代码索引流程图](architecture/git-code-index-flow.puml)
- [真实 Case 接入流程图](architecture/real-case-intake-flow.puml)

## 推荐阅读顺序

1. 阅读 `architecture/design-and-implementation.md` 的第 1 到 3 章，先理解项目做什么、由哪些模块组成。
2. 打开 `architecture/system-components.puml`，对照总体架构。
3. 阅读第 4 到 5 章，理解 LangGraph 状态流和每个节点的职责。
4. 打开 `architecture/langgraph-state-flow.puml` 和 `architecture/api-sequence.puml`，把流程串起来。
5. 阅读第 6 到 8 章，理解 LLM、RAG、评估闭环。
6. 最后按照第 11 章的源码阅读路线，对照代码逐个模块学习。
