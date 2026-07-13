# 嵌入式网通设备 Bug 分析 Agent 设计与实现详解

本文档用于深入理解当前项目的完整实现。阅读顺序建议：

1. 先看 `docs/architecture/*.puml` 图。
2. 再读本文档的架构和流程说明。
3. 最后对照具体代码文件逐个阅读。

## 1. 项目目标

本项目是一个面向嵌入式网通设备的软件缺陷分析 Agent。

它解决的问题是：

> 当路由器、光猫、网关、Mesh AP 等设备出现 DHCP 获取不到 IP、PPPoE 拨号失败、Wi-Fi 掉线等问题时，系统根据设备信息、故障现象和日志，自动检索历史 Bug、模块文档和代码线索，生成根因假设、证据链和修复建议。

项目不是普通 ChatBot，而是一个完整 AI 应用原型，包含：

- FastAPI 后端接口。
- Streamlit 前端页面。
- LangGraph 状态流。
- 本地 RAG / 检索数据。
- OpenAI-compatible LLM 接入。
- Pydantic 输出校验。
- 规则链 fallback。
- 自动化测试。
- 评估脚本。
- SOP 和简历/面试文档。

## 2. 项目目录结构

核心目录如下：

```text
app/
  main.py                     FastAPI 入口
  schemas/bug.py              API 请求/响应 Pydantic schema
  graph/
    bug_analysis_graph.py     LangGraph 工作流定义
    nodes.py                  每个图节点的实现
    state.py                  LangGraph 状态结构
  chains/
    extract_chain.py          本地规则：Bug 信息提取
    root_cause_chain.py       本地规则：根因假设生成
    report_chain.py           本地规则：报告文本生成
  llm/
    config.py                 LLM 环境变量配置
    client.py                 OpenAI-compatible LLM 调用
    schemas.py                LLM 输出 Pydantic schema
  rag/
    config.py                 RAG 与 Embedding 配置
    loader.py                 Markdown 文档加载
    vector_store.py           Chroma / Embedding 构建
    retriever.py              文档 retriever
  tools/
    log_parser.py             日志解析工具
    bug_history_search.py     历史 Bug 检索
    code_search.py            代码线索检索

data/
  bugs/
    bug_history.json          历史 Bug 样例库
    eval_cases.json           评估集
  docs/                       模块文档
  codebase/                   模拟 C 代码
  logs/                       样例日志

ui/
  streamlit_app.py            前端页面

scripts/
  ingest_docs.py              构建本地 Chroma 索引
  evaluate.py                 自动化评估脚本

tests/                        单元测试与集成测试
docs/architecture/            架构图和本文档
```

## 3. 总体架构

对应图：

- `docs/architecture/system-components.puml`
- `docs/architecture/runtime-deployment.puml`

系统分为 6 层：

### 3.1 前端层

文件：

- `ui/streamlit_app.py`

职责：

- 提供“现场调试台”风格页面。
- 让用户输入设备型号、固件版本、问题现象、设备日志、可选堆栈和模块提示。
- 调用后端 `/analyze`。
- 展示根因诊断板。
- 按 `LOG / DOC / BUG / CODE` 展示证据总线。

重要函数：

- `build_payload()`：组装 API 请求体。
- `group_evidence()`：按证据前缀分组。
- `build_evidence_grid_html()`：生成证据总线 HTML。
- `api_timeout_seconds()`：读取前端 API 调用超时，默认 90 秒。

为什么要把 timeout 调大：

真实 LLM 请求可能需要 20 到 30 秒，原本 30 秒超时容易导致页面调用失败，所以现在默认前端等待 90 秒。

### 3.2 API 层

文件：

- `app/main.py`
- `app/schemas/bug.py`

职责：

- 提供 `/health` 健康检查。
- 提供 `/analyze` 分析接口。
- 使用 Pydantic 校验输入和输出。

请求 schema：

```python
class BugAnalyzeRequest(BaseModel):
    device_model: str = Field(min_length=1)
    firmware_version: str = Field(min_length=1)
    symptom: str = Field(min_length=1)
    logs: str = Field(min_length=1)
    stack_trace: str | None = None
    module_hint: str | None = None
```

响应 schema：

```python
class BugAnalyzeResponse(BaseModel):
    bug_type: str
    summary: str
    root_causes: list[str]
    evidence: list[str]
    fix_suggestions: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
```

这里的 Pydantic 作用是：

- 保证必填字段不为空。
- 保证响应结构稳定。
- 保证 `confidence` 在 0 到 1 之间。

### 3.3 LangGraph 编排层

文件：

- `app/graph/bug_analysis_graph.py`
- `app/graph/nodes.py`
- `app/graph/state.py`

职责：

- 把 Bug 分析拆成多个节点。
- 每个节点读写同一个 `BugAnalysisState`。
- 保证流程可观察、可测试、可扩展。

当前图结构：

```text
extract_bug_info
  -> parse_logs
  -> search_bug_history
  -> search_codebase
  -> retrieve_related_docs
  -> generate_hypotheses
  -> generate_report
  -> END
```

对应图：

- `docs/architecture/langgraph-state-flow.puml`

### 3.4 本地工具和检索层

文件：

- `app/tools/log_parser.py`
- `app/tools/bug_history_search.py`
- `app/tools/code_search.py`
- `app/rag/config.py`
- `app/rag/loader.py`
- `app/rag/vector_store.py`
- `app/rag/retriever.py`

职责：

- 从日志中提取模块、错误模式、事件和证据行。
- 从 `bug_history.json` 检索相似历史 Bug。
- 从 `data/codebase` 检索相关 C 代码片段。
- 从 `data/docs` 加载模块文档。
- 将模块文档同步到 Chroma，并执行向量相似度检索。

`retrieve_related_docs_node()` 已接入 Chroma。默认的 `LocalHashEmbeddings` 使用确定性词法特征，不需要 API Key；配置 `EMBEDDING_PROVIDER=openai` 后可改用 OpenAI-compatible 语义 Embedding。索引或查询异常、召回结果低于阈值时，节点自动回退到 token overlap 检索，避免文档检索故障中断整条分析链。

### 3.5 LLM 层

文件：

- `app/llm/config.py`
- `app/llm/client.py`
- `app/llm/schemas.py`

职责：

- 从环境变量读取 LLM 配置。
- 构造根因分析 Prompt。
- 调用 OpenAI-compatible chat completions API。
- 解析模型 JSON。
- 使用 Pydantic 校验模型输出。
- 输出不合法时抛出受控异常，由 LangGraph 节点 fallback。

当前对接格式是：

```python
client.chat.completions.create(
    model=settings.model,
    messages=[
        {"role": "system", "content": "..."},
        {"role": "user", "content": prompt},
    ],
    temperature=settings.temperature,
    timeout=settings.timeout_seconds,
)
```

也就是说当前是 OpenAI-compatible 格式，不是 Anthropic Messages API 格式。

### 3.6 评估层

文件：

- `scripts/evaluate.py`
- `data/bugs/eval_cases.json`

职责：

- 使用历史 case 评估 Agent 效果。
- 支持规则链评估和真实 LLM 评估。
- 输出分类准确率、日志解析覆盖率、根因命中率、证据覆盖率和稳定性。

运行方式：

```bash
python scripts/evaluate.py --disable-llm
python scripts/evaluate.py --load-env --repeat 1
python scripts/evaluate.py --load-env --repeat 2
```

## 4. 核心数据结构：BugAnalysisState

文件：

- `app/graph/state.py`

`BugAnalysisState` 是 LangGraph 流程里的共享状态。

它大致包含：

```text
输入字段：
- device_model
- firmware_version
- symptom
- logs
- stack_trace
- module_hint

中间字段：
- extracted_info
- bug_type
- parsed_logs
- related_docs
- related_bugs
- related_code

输出字段：
- hypotheses
- evidence
- fix_suggestions
- final_report
```

每个节点只负责更新一部分字段。

好处：

- 流程清晰。
- 每一步可测试。
- 出错时能定位是哪一步问题。
- 后续可增加新节点，比如 rerank、外部工单查询、设备状态查询。

## 5. 从用户点击到生成结果的完整流程

对应图：

- `docs/architecture/api-sequence.puml`

完整链路如下：

### Step 1：用户填写前端表单

前端文件：

- `ui/streamlit_app.py`

用户填写：

- 设备型号。
- 固件版本。
- 问题现象。
- 现场日志。
- 可选堆栈。
- 可选模块提示。

点击“分析 Bug”后，前端调用：

```python
requests.post(API_URL, json=payload, timeout=api_timeout_seconds())
```

### Step 2：FastAPI 接收请求

文件：

- `app/main.py`

接口：

```python
@app.post("/analyze", response_model=BugAnalyzeResponse)
def analyze(request: BugAnalyzeRequest) -> BugAnalyzeResponse:
    result = analyze_bug(...)
```

FastAPI 会自动用 `BugAnalyzeRequest` 校验请求。

如果缺少 `device_model`、`firmware_version`、`symptom` 或 `logs`，接口会直接返回 422 参数错误。

### Step 3：构建初始 LangGraph state

文件：

- `app/graph/bug_analysis_graph.py`

函数：

```python
analyze_bug(...)
```

它会构造初始 state：

```python
initial_state = {
    "device_model": device_model,
    "firmware_version": firmware_version,
    "symptom": symptom,
    "logs": logs,
    ...
}
```

然后执行：

```python
app = build_bug_analysis_graph()
return app.invoke(initial_state)
```

### Step 4：提取 Bug 信息

节点：

```python
extract_bug_info_node()
```

调用：

```python
extract_bug_info(symptom, logs, module_hint)
```

输出：

- `extracted_info`
- `bug_type`

当前规则会根据关键词判断：

- DHCP 相关 -> `network_dhcp`
- PPPoE 相关 -> `network_pppoe`
- Wi-Fi 相关 -> `wifi_disconnect`
- 其他 -> `unknown`

### Step 5：解析日志

节点：

```python
parse_logs_node()
```

调用：

```python
parse_syslog(state["logs"])
```

输出：

- `modules`
- `error_patterns`
- `events`
- `evidence`

例如 DHCP case 会提取：

```text
error_patterns:
- lease allocation failed

events:
- interface reload

evidence:
- netifd: interface lan reload
- dhcpd: lease allocation failed
```

### Step 6：检索历史 Bug

节点：

```python
search_bug_history_node()
```

查询内容来自：

- 用户现象。
- `extracted_info.keywords`。
- `parsed_logs.error_patterns`。

数据源：

- `data/bugs/bug_history.json`

输出：

- `related_bugs`

例如 DHCP case 会召回：

- `BUG-018`
- `BUG-052`

### Step 7：检索代码线索

节点：

```python
search_codebase_node()
```

查询内容来自：

- 用户现象。
- 关键词。
- 日志事件。

数据源：

- `data/codebase/*.c`

输出：

- `related_code`

例如 DHCP case 会召回：

- `netifd_reload.c`
- `dhcp_server.c`

### Step 8：检索模块文档

节点：

```python
retrieve_related_docs_node()
```

数据源：

- `data/docs/*.md`

当前实现：

- 把故障现象、抽取关键词、错误模式和关键事件拼成检索 query。
- 加载 Markdown，并按来源和内容哈希生成稳定文档 ID。
- 自动把新增或变更文档写入 Chroma，并删除已经失效的索引记录。
- 使用配置的 Embedding 生成查询向量，按余弦相似度召回 Top-K 文档。
- 过滤低于 `RAG_SCORE_THRESHOLD` 的结果。
- Chroma 或远程 Embedding 失败、结果为空时，回退到本地 token overlap 检索。

输出：

- `related_docs`

例如 DHCP case 会召回：

- `dhcp.md`
- `upgrade.md`

每条结果包含：

- `source`：文档文件名。
- `content`：交给 LLM 的完整文档内容。
- `snippet`：证据总线展示的首个正文段落。
- `score`：向量相关度分数。
- `retrieval_method`：`chroma_vector` 或 `keyword_fallback`。

### Step 9：生成根因假设和修复建议

节点：

```python
generate_hypotheses_node()
```

这是项目最核心的 AI 节点。

逻辑：

```text
读取 LLMSettings
  -> 如果 LLM 配置 ready
       -> 调用真实 LLM
       -> Pydantic 校验输出
       -> 成功则使用 LLM 输出
       -> 失败则 fallback
  -> 如果 LLM 未启用或配置不完整
       -> 使用本地规则链
```

对应图：

- `docs/architecture/llm-fallback-flow.puml`

#### LLM 路径

文件：

- `app/llm/client.py`

函数：

```python
generate_root_cause_with_llm()
```

它会构造 Prompt，包含：

- bug_type
- symptom
- parsed_logs
- related_bugs
- related_docs
- related_code

要求模型只返回 JSON：

```json
{
  "hypotheses": [
    {
      "title": "string",
      "description": "string",
      "confidence": 0.0
    }
  ],
  "fix_suggestions": ["string"]
}
```

然后使用：

```python
LLMRootCauseResult.model_validate(payload)
```

校验模型输出。

#### 规则链 fallback

文件：

- `app/chains/root_cause_chain.py`

函数：

```python
generate_root_cause_hypotheses()
```

它根据 bug_type、日志模式、历史 Bug 和代码线索生成确定性根因。

例如 DHCP：

```text
DHCP 服务启动早于 LAN bridge ready
```

fallback 触发条件：

- `LLM_ENABLED=false`
- 缺少 base_url / api_key / model
- LLM 网络异常
- LLM 返回空内容
- LLM 返回非法 JSON
- LLM JSON 不符合 Pydantic schema

### Step 10：生成证据链和最终报告

节点：

```python
generate_report_node()
```

它会构造 `evidence`：

```text
log: ...
doc: ...
bug: ...
code: ...
```

然后调用：

```python
generate_report()
```

生成 `final_report` 文本。

API 最终返回的是结构化 JSON，不直接返回 `final_report`。

### Step 11：FastAPI 返回响应

`app/main.py` 从最终 state 中取第一条 hypothesis：

```python
top_hypothesis = result["hypotheses"][0]
```

构造响应：

```python
BugAnalyzeResponse(
    bug_type=result["bug_type"],
    summary=top_hypothesis["title"],
    root_causes=[top_hypothesis["description"]],
    evidence=result["evidence"],
    fix_suggestions=result["fix_suggestions"],
    confidence=top_hypothesis["confidence"],
)
```

### Step 12：前端展示结果

前端展示：

- confidence
- bug_type
- summary
- root_causes
- evidence bus
- fix_suggestions

证据分组逻辑：

```python
if item.startswith("log: "):
    grouped["logs"].append(...)
elif item.startswith("doc: "):
    grouped["docs"].append(...)
elif item.startswith("bug: "):
    grouped["bugs"].append(...)
elif item.startswith("code: "):
    grouped["code"].append(...)
```

多条 CODE 证据会折叠在一个 CODE 卡片里，避免页面显得重复。

## 6. LLM 配置和运行方式

配置文件：

- `.env`
- `.env.example`

当前使用 OpenAI-compatible 格式。

示例：

```bash
LLM_ENABLED=true
LLM_BASE_URL=http://10.10.120.244:4000/v1
LLM_API_KEY=<your-api-key>
LLM_MODEL=3rd-MiniMax-M3
LLM_TIMEOUT_SECONDS=30
LLM_TEMPERATURE=0.2
```

启动服务时要显式加载 `.env`：

```bash
set -a
source .env
set +a
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 9000
```

前端：

```bash
set -a
source .env
set +a
BUG_AGENT_API_URL=http://127.0.0.1:9000/analyze \
BUG_AGENT_API_TIMEOUT_SECONDS=90 \
.venv/bin/streamlit run ui/streamlit_app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.headless true \
  --browser.gatherUsageStats false
```

为什么前端 timeout 是 90 秒：

- LLM 请求可能耗时 20 到 30 秒。
- 多数网络波动下 30 秒容易误判失败。
- 后端 LLM 自身仍由 `LLM_TIMEOUT_SECONDS` 控制。

## 7. RAG 和知识源设计

本项目的 RAG 不是单一向量库问答，而是多来源证据组合。

### 7.1 历史 Bug

文件：

- `data/bugs/bug_history.json`

包含：

- bug_id
- title
- module
- symptom
- root_cause
- fix
- keywords
- related_files

作用：

- 匹配相似历史缺陷。
- 给根因分析提供历史案例依据。
- 给前端证据总线提供 BUG 证据。

### 7.2 模块文档

目录：

- `data/docs/`

包含：

- `dhcp.md`
- `pppoe.md`
- `wifi.md`
- `tr069.md`
- `upgrade.md`

作用：

- 提供模块机制说明。
- 给 LLM 上下文增加领域知识。
- 给前端证据总线提供 DOC 证据。

检索链路：

```text
Markdown 文档
  -> LangChain Document
  -> LocalHashEmbeddings 或 OpenAI-compatible Embedding
  -> Chroma 持久化索引
  -> 查询向量相似度 Top-K
  -> 分数阈值过滤
  -> related_docs
  -> 注入 LLM 根因分析 Prompt
```

`build_vector_store()` 创建以余弦距离为度量的 Chroma collection。collection 名称包含 Embedding provider、模型、地址和知识目录的配置摘要，切换模型时不会误用旧向量。`sync_vector_store()` 使用“来源 + 内容哈希”生成稳定 ID，因此重复启动不会重复写入，文档修改和删除也会同步反映到索引。

默认的本地 Hash Embedding 保障离线可运行和测试结果稳定，但只擅长字面相关性。生产环境应使用真实语义 Embedding，并通过评估集调整 `RAG_TOP_K` 和 `RAG_SCORE_THRESHOLD`。

### 7.3 代码线索

目录：

- `data/codebase/`

包含模拟 C 代码：

- `netifd_reload.c`
- `dhcp_server.c`
- `pppoe_client.c`
- `wifi_manager.c`
- `tr069_report.c`

作用：

- 让 Agent 不只是“查文档”，还能关联代码位置。
- 给根因分析提供更接近研发排障的证据。
- 给前端证据总线提供 CODE 证据。

## 8. 评估体系

对应图：

- `docs/architecture/evaluation-flow.puml`

文件：

- `scripts/evaluate.py`
- `data/bugs/eval_cases.json`

评估 case 包含：

```json
{
  "case_id": "EVAL-001",
  "device_model": "...",
  "firmware_version": "...",
  "symptom": "...",
  "logs": "...",
  "expected_bug_type": "network_dhcp",
  "expected_root_cause_keywords": ["DHCP", "bridge", "ready"],
  "expected_evidence_terms": ["lease allocation failed", "BUG-018", "dhcp.md"]
}
```

### 8.1 classification_accuracy

Bug 类型是否判断正确。

例如：

```text
expected=network_dhcp
predicted=network_dhcp
```

则 classification_ok 为 true。

### 8.2 parser_coverage

日志解析是否提取到：

- modules
- error_patterns
- events
- evidence

### 8.3 root_cause_hit_rate

根因输出是否包含期望关键词。

例如 DHCP case 期望：

```text
DHCP
bridge
ready
```

如果模型输出提到 `DHCP server restarted before bridge interface is ready`，则命中。

### 8.4 evidence_coverage

证据链是否包含期望证据项。

例如：

```text
lease allocation failed
BUG-018
dhcp.md
```

### 8.5 output_stability

同一 case 多次运行时：

- bug_type 是否一致。
- classification 是否正确。
- root cause 是否命中。

命令：

```bash
python scripts/evaluate.py --load-env --repeat 2
```

## 9. 测试体系

目录：

- `tests/`

主要测试类型：

### 9.1 API 测试

文件：

- `tests/test_api.py`

验证 `/analyze` 能返回结构化报告。

### 9.2 Schema 测试

文件：

- `tests/test_schemas.py`
- `tests/test_llm_schemas.py`

验证 API schema 和 LLM 输出 schema。

### 9.3 Graph 节点测试

文件：

- `tests/test_graph_nodes.py`
- `tests/test_graph_workflow.py`
- `tests/test_llm_graph_node.py`

验证 LangGraph 节点和 LLM fallback。

### 9.4 工具测试

文件：

- `tests/test_log_parser.py`
- `tests/test_bug_history_search.py`
- `tests/test_code_search.py`
- `tests/test_rag_loader.py`

验证日志解析、Bug 检索、代码检索和文档加载。

### 9.5 前端 helper 测试

文件：

- `tests/test_streamlit_ui_helpers.py`

验证：

- payload 组装。
- 证据分组。
- CODE 证据折叠。
- 前端 API timeout。

### 9.6 评估测试

文件：

- `tests/test_eval_dataset.py`
- `tests/test_evaluate_metrics.py`

验证评估集完整性和指标计算。

运行全部测试：

```bash
.venv/bin/pytest -q
```

## 10. PlantUML 文件说明

目录：

- `docs/architecture/`

文件：

```text
system-components.puml       系统组件图
langgraph-state-flow.puml    LangGraph 状态流图
api-sequence.puml            API 调用时序图
llm-fallback-flow.puml       LLM fallback 流程图
evaluation-flow.puml         评估流程图
runtime-deployment.puml      本地运行部署图
```

渲染示例：

```bash
plantuml docs/architecture/*.puml
```

如果没有本地 PlantUML，也可以把 `.puml` 内容复制到在线 PlantUML 渲染器。

## 11. 推荐学习路线

如果你要深入理解该项目，建议按以下顺序：

### 第一步：理解 API 输入输出

阅读：

- `app/schemas/bug.py`
- `app/main.py`

目标：

- 明白用户传什么。
- 明白接口返回什么。
- 明白 Pydantic 做了什么校验。

### 第二步：理解 LangGraph 主流程

阅读：

- `app/graph/bug_analysis_graph.py`
- `app/graph/state.py`

目标：

- 明白有哪些节点。
- 明白 state 如何在节点之间传递。

### 第三步：逐个读节点

阅读：

- `app/graph/nodes.py`

目标：

- 理解每个节点读哪些字段。
- 理解每个节点写哪些字段。
- 理解检索 query 如何构造。

### 第四步：理解工具层

阅读：

- `app/tools/log_parser.py`
- `app/tools/bug_history_search.py`
- `app/tools/code_search.py`
- `app/rag/loader.py`

目标：

- 明白日志如何解析。
- 明白历史 Bug 如何匹配。
- 明白代码线索如何找。
- 明白模块文档如何加载。

### 第五步：理解 LLM 接入

阅读：

- `app/llm/config.py`
- `app/llm/client.py`
- `app/llm/schemas.py`
- `tests/test_llm_client.py`

目标：

- 明白环境变量如何控制 LLM。
- 明白 Prompt 如何构造。
- 明白模型输出如何校验。
- 明白 fallback 为什么可靠。

### 第六步：理解前端展示

阅读：

- `ui/streamlit_app.py`
- `tests/test_streamlit_ui_helpers.py`

目标：

- 明白页面如何调用 API。
- 明白证据总线如何分组。
- 明白为什么 CODE 证据折叠。

### 第七步：理解评估闭环

阅读：

- `data/bugs/eval_cases.json`
- `scripts/evaluate.py`
- `tests/test_evaluate_metrics.py`

目标：

- 明白如何证明 Agent 分析效果。
- 明白规则链评估和 LLM 评估怎么跑。

## 12. 当前项目能力边界

已经实现：

- API 和 UI。
- LangGraph 状态流。
- 本地日志解析。
- 历史 Bug 检索。
- 模块文档检索。
- Chroma 持久化向量召回与自动增量同步。
- 本地词法 Embedding / OpenAI-compatible 语义 Embedding 切换。
- 向量检索异常时关键词 fallback。
- 代码线索检索。
- OpenAI-compatible LLM 接入。
- Pydantic 结构化输出校验。
- LLM fallback 到规则链。
- 自动化测试。
- 评估指标。

仍可继续增强：

- 增加 hybrid search：向量检索 + 关键词检索。
- 增加 rerank。
- 增加 LangSmith / 自定义 trace。
- 将 LLM fallback 原因写入 state，便于前端展示。
- 增加更多 eval cases。
- 支持 Anthropic Messages API。
- 支持 Docker 部署。

## 13. 常用命令

### 启动后端

```bash
cd /home/sdmc/AgentProject
set -a
source .env
set +a
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 9000
```

### 启动前端

```bash
cd /home/sdmc/AgentProject
set -a
source .env
set +a
BUG_AGENT_API_URL=http://127.0.0.1:9000/analyze \
BUG_AGENT_API_TIMEOUT_SECONDS=90 \
.venv/bin/streamlit run ui/streamlit_app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.headless true \
  --browser.gatherUsageStats false
```

### API 调用

```bash
curl -X POST http://127.0.0.1:9000/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "device_model": "AX3000 Router",
    "firmware_version": "v2.1.8",
    "symptom": "升级后 DHCP 客户端偶发获取不到 IP",
    "logs": "2026-06-25 14:03:11 netifd: interface lan reload\n2026-06-25 14:03:12 dhcpd: lease allocation failed"
  }'
```

### 跑测试

```bash
.venv/bin/pytest -q
```

### 跑规则链评估

```bash
.venv/bin/python scripts/evaluate.py --disable-llm
```

### 跑真实 LLM 评估

```bash
.venv/bin/python scripts/evaluate.py --load-env --repeat 1
```
