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
  evidence.py                 结构化证据构建与根因引用绑定
  schemas/bug.py              API 请求/响应 Pydantic schema
  graph/
    bug_analysis_graph.py     LangGraph 工作流定义
    checkpoint.py             SQLite checkpointer 构建
    review_workflow.py        持久化任务启动、查询和恢复
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
    splitter.py               标题感知的文档切分与稳定 chunk ID
    vector_store.py           Chroma / Embedding 构建
    ranking.py                BM25、分词和 RRF 排名融合
    reranker.py               本地特征、FlashRank 与 CrossEncoder 重排
    retriever.py              混合检索编排和降级
    code_parser.py            tree-sitter C 函数级切分
    evaluation.py             Recall、MRR、nDCG 等排序指标
  evaluation/
    case_schema.py            真实/合成评估 case 数据契约
  observability/
    metrics.py                Prometheus 指标定义
  tools/
    log_parser.py             日志解析工具
    bug_history_search.py     历史 Bug 检索
    code_search.py            代码线索检索

data/
  bugs/
    bug_history.json          历史 Bug 样例库
    eval_cases.json           评估集
    real_eval_cases.example.json 真实脱敏 case 模板
  docs/                       模块文档
  rag/
    retrieval_eval_cases.json 检索评估集
  codebase/                   模拟 C 代码

ui/
  streamlit_app.py            前端页面

scripts/
  ingest_docs.py              构建本地 Chroma 索引
  evaluate.py                 自动化评估脚本
  evaluate_retrieval.py       chunk 检索排序评估脚本
  validate_eval_dataset.py    评估来源、标注和脱敏校验

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
- `app/rag/splitter.py`
- `app/rag/vector_store.py`
- `app/rag/retriever.py`

职责：

- 从日志中提取模块、错误模式、事件和证据行。
- 从 `bug_history.json` 检索相似历史 Bug。
- 从 `data/codebase` 检索相关 C 代码片段。
- 从 `data/docs` 加载模块文档，按 Markdown 标题和长度切成 chunk。
- 将 chunk 同步到 Chroma，并执行向量相似度检索。

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

- 使用有来源标记的 case 评估 Agent 效果；仓库内样例明确标记为 synthetic。
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
- generation_mode
- fallback_reasons
- trace_events
- review_required
- review_status
- review_reasons
- interactive_review
- review_decision

输出字段：
- hypotheses
- evidence
- evidence_details
- fix_suggestions
- final_report
```

每个节点只负责更新一部分字段。

好处：

- 流程清晰。
- 每一步可测试。
- 出错时能定位是哪一步问题。
- 后续可增加新节点，比如外部工单查询、设备状态查询和人工复核。

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

实现方式：历史记录先由 `app/rag/corpus.py` 转成 `source_type=bug` 的 LangChain `Document`，再复用 Chroma + BM25 + RRF + rerank 统一检索协议。只有双路检索失败或无结果时才调用 `search_bug_history()` 关键词工具，并记录结构化 fallback 原因。

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

实现方式：`app/rag/code_parser.py` 使用 tree-sitter-c 构建语法树，提取 `function_definition`，递归解析 declarator 得到函数名，并把紧邻函数的注释一起放入 chunk。每个 `Document` 携带 `symbol/start_line/end_line/parser`，chunk ID 为 `code::<文件名>::<函数名>`。文件名、函数名拆词和函数正文共同参与混合检索；返回时在函数 chunk 内定位最佳行，再加上 `start_line` 换算为原文件绝对行号。没有函数定义或无法提取函数时保留文件级兜底 chunk。

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
- 先按 Markdown 标题层级切分章节，再按 `RAG_CHUNK_SIZE` 和 `RAG_CHUNK_OVERLAP` 做二次切分。
- 为每个 chunk 记录来源、章节路径、父级 ID、序号和稳定 chunk ID。
- 自动把新增或变更 chunk 写入 Chroma，并删除已经失效的索引记录。
- Chroma 向量检索和 BM25 各召回 `RAG_CANDIDATE_K` 个候选 chunk。
- 向量分低于 `RAG_SCORE_THRESHOLD` 的候选会被过滤。
- 使用加权 Reciprocal Rank Fusion（RRF）按名次融合并按 chunk ID 去重。
- 使用本地特征、FlashRank 或 Sentence Transformers CrossEncoder 对融合候选重排，返回最终 `RAG_TOP_K`。
- 任一召回路径失败时保留另一条路径；模型重排失败时降级到本地特征重排；两路都不可用时由图节点回退到 chunk 关键词匹配。
- `fastembed` provider 默认使用 `BAAI/bge-small-zh-v1.5` 生成 512 维中文语义向量；`local` Hash provider 仅作为测试和词法回退。

输出：

- `related_docs`

例如 DHCP case 会召回：

- `dhcp.md`
- `upgrade.md`

每条结果包含：

- `source`：文档文件名。
- `section` / `section_path`：chunk 所在章节及完整标题路径。
- `chunk_id` / `parent_id`：稳定证据标识和父章节标识。
- `content`：交给 LLM 的命中 chunk 内容。
- `snippet`：证据总线展示的首个正文段落。
- `vector_score` / `vector_rank`：向量召回分数和名次。
- `bm25_score` / `bm25_rank`：BM25 分数和名次。
- `fusion_score`：RRF 融合分。
- `rerank_score` / `rank`：重排分和最终名次。
- `retrieval_method` / `rerank_method`：实际执行的召回和重排策略。

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
- evidence_details（包含可引用的稳定 evidence_id）

要求模型只返回 JSON：

```json
{
  "hypotheses": [
    {
      "title": "string",
      "description": "string",
      "confidence": 0.0,
      "evidence_ids": ["doc:dhcp.md::...::000"]
    }
  ],
  "fix_suggestions": ["string"]
}
```

然后使用：

```python
LLMRootCauseResult.model_validate(payload)
```

校验模型输出。Prompt 明确要求 `evidence_ids` 只能引用给定证据清单中的 ID；报告节点还会过滤不存在的 ID，避免模型伪造文档、Bug 或代码来源。

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

节点会写入 `generation_mode=llm|rule`。发生 fallback 时只记录错误类型和稳定错误码，不把 API Key、完整请求或供应商响应写入 trace。

### Step 10：判断是否需要人工复核

`assess_review_node()` 会检查 Bug 类型、第一根因置信度和证据类型数量。Bug 类型未知、置信度低于 `AGENT_REVIEW_CONFIDENCE_THRESHOLD`（默认 `0.70`），或有效证据类型少于两类时，LangGraph 条件边进入 `queue_human_review`。

同步 `/analyze` 保持兼容，只把状态标记为 `pending` 后生成报告。持久化 `/analyses` 会设置 `interactive_review=true`，节点调用 `interrupt(payload)`；SQLite checkpointer 在 `LANGGRAPH_CHECKPOINT_PATH` 保存 thread，接口返回 `analysis_id` 和复核载荷。审批接口使用相同 `thread_id` 调用 `Command(resume=decision)`，节点恢复后写入 `approved/rejected`、复核人和意见，再继续报告节点。LangGraph 恢复时只重放中断节点，已经完成的日志解析和三路检索不会重跑。

### Step 11：生成证据链和最终报告

节点：

```python
generate_report_node()
```

它会先构造 `evidence_details`，为日志、文档 chunk、历史 Bug 和代码线索生成稳定 ID，并把根因假设绑定到有效证据；同时保留兼容旧前端的 `evidence` 字符串：

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

复核任务恢复后，报告末尾会记录通过或驳回、复核人和意见。API 最终返回的是结构化 JSON，不直接返回 `final_report`，完整 state 则持久化在 checkpoint 中。

### Step 12：FastAPI 返回响应

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
    hypotheses=result["hypotheses"],
    evidence=result["evidence"],
    evidence_details=result["evidence_details"],
    fix_suggestions=result["fix_suggestions"],
    confidence=top_hypothesis["confidence"],
    generation_mode=result["generation_mode"],
    trace_events=result["trace_events"],
    fallback_reasons=result["fallback_reasons"],
    review_required=result["review_required"],
)
```

### Step 13：前端展示结果

前端展示：

- confidence
- bug_type
- summary
- root_causes
- evidence bus
- fix_suggestions
- generation mode、人工复核原因
- 可折叠的节点执行轨迹和 fallback 原因
- 低置信度任务的复核人、复核意见以及通过/驳回操作

前端优先使用 `evidence_details.evidence_type` 分组。DOC 卡片会展示来源文件、章节和相似度，CODE 多条结果仍折叠显示；当后端是旧版本、没有 `evidence_details` 时，才回退到字符串前缀解析：

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

本项目的 RAG 不是单一向量库问答，而是多来源证据组合。`load_knowledge_chunks()` 把 DOC、BUG、CODE 统一为 `source_type/source/chunk_id/parent_id` 元数据协议，并写入同一个按配置隔离的 Chroma collection。三个图节点保留不同 query 构造方式，但底层都调用 `retrieve_knowledge_source()`。

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
  -> Markdown 标题层级切分
  -> 长度上限与 overlap 切分
  -> 带稳定 ID 和章节元数据的 chunk
  -> [Chroma 向量召回 || BM25 关键词召回]
  -> 加权 RRF 融合与 chunk ID 去重
  -> 本地特征、FlashRank 或 CrossEncoder 重排
  -> 最终 Top-K
  -> related_docs
  -> 注入 LLM 根因分析 Prompt
```

`split_markdown_document()` 先用 `MarkdownHeaderTextSplitter` 保留标题语义，再用 `RecursiveCharacterTextSplitter` 控制 chunk 大小。默认 `chunk_size=300`、`chunk_overlap=50`，这里使用可离线复现的近似文本单元计数，而不是绑定某个在线模型的 tokenizer。

`build_vector_store()` 创建以余弦距离为度量的 Chroma collection。collection 名称包含 Embedding provider、模型、知识目录、切分版本和切分参数的配置摘要，切换模型或切分策略时不会误用旧向量。`sync_vector_store()` 使用“来源 + chunk ID + 内容哈希”生成索引 ID，因此重复启动不会重复写入，chunk 修改和删除也会同步反映到索引。

示例 `.env` 默认使用 FastEmbed 的 `BAAI/bge-small-zh-v1.5`，在 CPU 上生成 512 维真实语义向量。模型适配器先从本地缓存读取，缓存缺失时使用 FastEmbed 官方 Qdrant 镜像，避免隐式下载阻塞。LocalHash 只用于无需下载的自动化测试和消融基线。

BM25 使用 LangChain `BM25Retriever` 与 `rank-bm25`，适合错误码、函数名、配置键和日志原文等精确匹配。RRF 不直接比较两类不可比的原始分数，而是按 `weight / (RRF_K + rank)` 融合名次。默认本地 reranker 综合查询覆盖率、技术标识符、章节标题、BM25 分和向量分；`flashrank` 使用多语言 ONNX CrossEncoder 在 CPU 上联合打分；`cross_encoder` 使用 Sentence Transformers 加载指定模型。任一模型重排异常都会回退到本地特征重排。

`HybridDocumentRetriever` 实现 LangChain `BaseRetriever`，把上述完整流程封装为标准 `.invoke(query) -> list[Document]` 接口。LangGraph 节点使用结构化字典以保留详细分数，其他 LangChain Chain 则可直接复用 Retriever 接口。

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

切分与检索链路：

```text
C 文件 -> tree-sitter 语法树 -> function_definition
  -> 函数名、紧邻注释、起止行元数据
  -> 函数级 LangChain Document
  -> Chroma 向量 + BM25 + RRF + rerank
  -> 函数内最佳行定位 -> 原文件绝对行号
```

## 8. 评估体系

对应图：

- `docs/architecture/evaluation-flow.puml`

文件：

- `scripts/evaluate.py`
- `data/bugs/eval_cases.json`
- `scripts/evaluate_retrieval.py`
- `data/rag/retrieval_eval_cases.json`

评估 case 包含：

```json
{
  "case_id": "EVAL-001",
  "case_origin": "synthetic",
  "split": "test",
  "label_status": "reviewed",
  "annotator_count": 1,
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

### 8.6 证据引用、检索来源和复核路由

- `citation_validity`：根因假设引用的 evidence ID 是否都存在于本次证据集合。
- `retrieval_provenance_coverage`：DOC、BUG、CODE 证据是否携带 `retrieval_method`。
- `review_routing_accuracy`：低置信度或证据不足 case 是否进入待复核分支。

### 8.7 chunk 检索排序评估

每条检索 case 包含用户查询和人工标注的 `relevant_chunk_ids`。脚本执行真实 Chroma 检索后，计算：

- `Recall@K`：相关 chunk 中有多少进入前 K。
- `Precision@K`：前 K 结果中有多少是相关 chunk。
- `Hit Rate@K`：前 K 是否至少命中一个相关 chunk。
- `MRR`：第一个相关 chunk 排名的倒数。
- `nDCG@K`：综合考虑多个相关 chunk 的命中数量与排序位置。

命令：

```bash
python scripts/evaluate_retrieval.py --top-k 5
python scripts/evaluate_retrieval.py --load-env --top-k 5
python scripts/evaluate_retrieval.py --top-k 3 --compare
python scripts/evaluate_retrieval.py --top-k 3 --compare-embeddings
```

第一条命令使用默认混合检索建立可复现基线；第二条命令加载 `.env`；第三条执行向量、BM25、混合 RRF、混合 RRF+rerank 消融；第四条直接对比 LocalHash 与 BGE 中文语义向量。内置 20 条 case 包含困难负例和语义改写，指标只能证明当前演示链路，不代表生产效果。

### 8.8 真实 case 数据治理

`app/evaluation/case_schema.py` 使用 Pydantic 校验 case 来源、split、标注状态和字段完整性。`production_anonymized` case 必须满足：

- 工单 ID 只保留 `sha256:<64 hex>` 不可逆哈希。
- 至少两名标注人并完成裁决。
- 脱敏动作包含人工复核。
- 不残留真实 MAC、邮箱和非文档网段 IPv4。
- 同一工单哈希不能重复，避免跨 split 泄漏。

完整流程见 `docs/evaluation/real-case-intake.md`。校验命令：

```bash
python scripts/validate_eval_dataset.py
python scripts/validate_eval_dataset.py --cases /secure/path/cases.json --require-production
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

### 9.7 AST、checkpoint 和指标测试

- `tests/test_rag_code_parser.py`：函数名、注释和绝对行号切分。
- `tests/test_review_workflow.py`：SQLite 暂停、查询、恢复和防重复审批。
- `tests/test_metrics.py`：Prometheus 指标族、节点和 fallback 标签。
- `tests/test_evaluation_case_schema.py`：生产 case 标注门槛和敏感信息扫描。

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
- BM25 召回、加权 RRF 融合和本地特征重排。
- 可选 FlashRank / Sentence Transformers CrossEncoder 模型重排。
- LocalHash / FastEmbed 中文 BGE / OpenAI-compatible Embedding 切换。
- 文档、历史 Bug、代码统一混合检索协议。
- 向量与 BM25 单路降级、模型重排降级和关键词 fallback。
- 代码线索检索。
- tree-sitter C 函数级切分和绝对行号定位。
- Git 仓库递归索引、直接调用关系、条件编译上下文、构建配置和 Commit Diff 证据。
- OpenAI-compatible LLM 接入。
- Pydantic 结构化输出校验。
- LLM fallback 到规则链。
- 节点级自定义 trace 和结构化 fallback 原因。
- 低置信度人工复核条件分支。
- SQLite checkpointer、`interrupt()` 和 `Command(resume=...)` 持久化复核。
- Redis/RQ 持久化任务、幂等、重试、超时、取消和队列内人工复核。
- API Key 摘要认证、租户任务隔离和 checkpoint 所有权校验。
- Prometheus HTTP、节点、检索、LLM、fallback、分析、复核和队列指标。
- Grafana 仪表盘、Tempo Trace、Trace Context 跨队列传播和 Prometheus 告警规则。
- 真实 case Pydantic 数据契约、带盐工单摘要、稳定编号脱敏、双人标注和独立仲裁导入脚本。
- API/UI/Redis/Worker Docker Compose、可观测 Overlay 和 GitHub Actions CI。
- 自动化测试。
- 评估指标。

仍可继续增强：

- 在受控环境接入脱敏线上 case，并据此调优查询改写和领域 reranker。
- 使用授权的真实固件仓库和脱敏线上 case 建立生产基线。
- 把直接调用图升级为支持函数指针、动态注册和 `compile_commands.json` 的完整符号图。
- 将单机 SQLite checkpoint 迁移到支持多主机、多副本的 PostgreSQL。
- 接入集中日志、企业告警 Webhook、预算和模型成本统计。
- 为每个租户拆分 Chroma collection、代码挂载和文档目录，并增加细粒度审批角色与限流。

## 13. 常用命令

### 启动后端

```bash
cd embedded-bug-analysis-agent
set -a
source .env
set +a
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 9000
```

### 启动前端

```bash
cd embedded-bug-analysis-agent
set -a
source .env
set +a
BUG_AGENT_API_URL=http://127.0.0.1:9000/analyze \
BUG_AGENT_API_BASE_URL=http://127.0.0.1:9000 \
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

### 查看运行指标

```bash
curl -s http://127.0.0.1:9000/metrics
```

### 校验评估数据

```bash
.venv/bin/python scripts/validate_eval_dataset.py
```

### 跑规则链评估

```bash
.venv/bin/python scripts/evaluate.py --disable-llm
```

### 跑真实 LLM 评估

```bash
.venv/bin/python scripts/evaluate.py --load-env --repeat 1
```
