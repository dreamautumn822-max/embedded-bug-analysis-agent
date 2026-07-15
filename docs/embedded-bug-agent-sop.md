# 嵌入式网通设备 Bug 分析 Agent 使用 SOP

## 1. 适用范围

本文档用于指导本项目的本地启动、API 调用、Streamlit 页面演示、评估脚本运行和常见问题排查。

项目能力：

- 输入设备型号、固件版本、问题现象、设备日志、可选调用栈
- 自动分析 Bug 类型
- 解析系统日志
- 检索历史 Bug
- 检索模块文档证据
- 检索模拟 C 代码
- 按 C 函数 AST 定位源码行
- 对低置信度任务执行暂停、人工复核和恢复
- 暴露 Prometheus 运行指标
- 生成根因分析、证据链和修复建议

适合演示场景：

- AI Agent 应用岗位项目展示
- LangChain/LangGraph 学习
- 嵌入式网通设备 Bug 分析流程说明

---

## 2. 项目结构速览

```text
app/
  main.py                         FastAPI 入口
  graph/bug_analysis_graph.py      LangGraph 工作流
  graph/review_workflow.py         SQLite 人工复核任务服务
  graph/nodes.py                   各分析节点
  chains/                          规则型分析链
  tools/                           日志、历史 Bug、代码检索工具
  rag/                             文档/AST 切分、混合检索、RRF 与重排
  evaluation/                      评估 case 数据契约
  observability/                   Prometheus 指标
data/
  bugs/bug_history.json            历史 Bug 数据
  bugs/eval_cases.json             评估数据集
  codebase/                        模拟 C 代码
  docs/                            模块文档
scripts/
  ingest_docs.py                   构建本地 Chroma 文档索引
  evaluate.py                      运行评估
  evaluate_retrieval.py            运行检索消融评估
  validate_eval_dataset.py         校验 case 来源、标注和脱敏
ui/
  streamlit_app.py                 Streamlit 演示页面
tests/
  test_*.py                        自动化测试
```

---

## 3. 环境准备

### 3.1 进入项目目录

```bash
cd embedded-bug-analysis-agent
```

### 3.2 创建并激活虚拟环境

如果 `.venv` 已存在，可以直接激活：

```bash
source .venv/bin/activate
```

如果是首次运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3.3 准备环境变量文件

```bash
cp .env.example .env
```

当前项目默认走本地确定性规则链，生成阶段不需要模型 API Key；示例配置使用 FastEmbed + `BAAI/bge-small-zh-v1.5` 生成本地语义向量。首次运行会下载模型，缓存位于 `.cache/embeddings/`。

---

## 4. 构建统一知识索引

运行：

```bash
python scripts/ingest_docs.py
```

预期输出：

```text
Indexed 33 chunks into ... (provider=fastembed, ...)
```

说明：

- 索引包含模块文档 chunk、历史 Bug 条目和 C 函数 chunk 三类来源
- FastEmbed 在本机 CPU 推理，不需要 Embedding API Key
- 索引会写入 `.chroma/`
- `.chroma/` 已被 `.gitignore` 忽略
- API 首次分析也会自动同步索引，手动执行脚本用于提前构建和检查索引

成功输出会包含文档数量、索引目录、collection 名称和 Embedding provider。

---

## 5. 启动 API 服务

### 5.1 启动 FastAPI

```bash
uvicorn app.main:app --reload
```

默认地址：

```text
http://127.0.0.1:8000
```

### 5.2 检查服务健康状态

另开一个终端，进入项目目录并执行：

```bash
curl -s http://127.0.0.1:8000/health
```

预期输出：

```json
{"status":"ok"}
```

查看当前检索运行配置：

```bash
curl -s http://127.0.0.1:8000/health/details
```

```json
{"status":"ok"}
```

### 5.3 打开 API 文档

浏览器访问：

```text
http://127.0.0.1:8000/docs
```

查看 Prometheus 指标：

```bash
curl -s http://127.0.0.1:8000/metrics | grep '^bug_agent_'
```

---

## 6. 调用 Bug 分析 API

### 6.1 使用 curl 调用

```bash
curl -s -X POST http://127.0.0.1:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "device_model": "AX3000 Router",
    "firmware_version": "v2.1.8",
    "symptom": "升级后 DHCP 客户端偶发获取不到 IP",
    "logs": "2026-06-25 14:03:11 netifd: interface lan reload\n2026-06-25 14:03:12 kernel: br-lan port state changed to blocking\n2026-06-25 14:03:12 dhcpd: lease allocation failed",
    "stack_trace": null,
    "module_hint": null
  }'
```

### 6.2 预期返回字段

```json
{
  "bug_type": "network_dhcp",
  "summary": "DHCP 服务启动早于 LAN bridge ready",
  "root_causes": [
    "netifd reload 触发 bridge 重建后，DHCP server 在 br-lan forwarding 前启动，导致地址租约分配失败。"
  ],
  "hypotheses": [
    {
      "title": "DHCP 服务启动早于 LAN bridge ready",
      "description": "...",
      "confidence": 0.95,
      "evidence_ids": ["doc:dhcp.md::...::000", "bug:BUG-018"]
    }
  ],
  "evidence": [
    "log: ...",
    "doc: dhcp.md - ...",
    "bug: BUG-018 - ...",
    "code: netifd_reload.c:..."
  ],
  "evidence_details": [
    {
      "evidence_id": "doc:dhcp.md::...::000",
      "evidence_type": "doc",
      "source": "dhcp.md",
      "section": "启动依赖与时序",
      "retrieval_method": "hybrid_rrf_rerank",
      "rerank_method": "local_feature"
    }
  ],
  "fix_suggestions": [
    "在 br-lan 进入 forwarding/ready 状态后再启动 DHCP server"
  ],
  "confidence": 0.95,
  "generation_mode": "rule",
  "trace_events": [],
  "fallback_reasons": [],
  "review_required": false,
  "review_status": "not_required",
  "review_reasons": []
}
```

### 6.3 结果怎么看

- `bug_type`：Agent 判断的 Bug 类型
- `summary`：最核心的根因摘要
- `root_causes`：根因解释
- `evidence`：证据链，包含日志、文档、历史 Bug、代码片段
- `hypotheses` / `evidence_details`：根因到稳定证据 ID 的结构化引用，以及向量、BM25、RRF、rerank 元数据
- `fix_suggestions`：修复建议
- `confidence`：规则链路给出的置信度
- `generation_mode`：根因由 LLM 还是规则链生成
- `trace_events` / `fallback_reasons`：节点耗时、状态和降级原因
- `review_*`：低置信度或证据不足时的人工复核状态

### 6.4 启动并恢复持久化人工复核

以下输入会进入低置信度分支：

```bash
curl -s -X POST http://127.0.0.1:8000/analyses \
  -H 'Content-Type: application/json' \
  -d '{
    "device_model":"Unknown Gateway",
    "firmware_version":"v0.0.1",
    "symptom":"设备出现无法识别的随机异常",
    "logs":"daemon: unexplained status code 777"
  }'
```

响应中的 `status` 为 `pending_review`。保存 `analysis_id` 后查询：

```bash
curl -s http://127.0.0.1:8000/analyses/<analysis_id>
```

提交通过或驳回决定：

```bash
curl -s -X POST http://127.0.0.1:8000/analyses/<analysis_id>/review \
  -H 'Content-Type: application/json' \
  -d '{
    "approved":false,
    "reviewer":"qa-owner",
    "comment":"证据不足，补充复现日志"
  }'
```

恢复成功后 `status=completed`，`review_status=approved|rejected`。重复审批返回 HTTP 409；不存在的任务返回 404。SQLite 默认位于 `run/bug_analysis_checkpoints.sqlite`，重启 API 后仍可查询未完成 thread。

---

## 7. 使用 Streamlit 页面

### 7.1 先启动 API

终端 1：

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

### 7.2 启动页面

终端 2：

```bash
source .venv/bin/activate
streamlit run ui/streamlit_app.py
```

启动成功后，终端会输出类似：

```text
Local URL: http://localhost:8501
```

浏览器打开该地址。

### 7.3 页面使用步骤

1. 保持默认设备型号、版本、问题现象和日志
2. 可选填写 `Stack Trace`
3. 保持“启用人工复核断点”开启并点击 `分析 Bug`
4. 高置信度任务直接展示结果；低置信度任务填写复核人和意见后通过或驳回

页面会展示：

- Confidence
- Bug Type
- Summary
- Root Causes
- Evidence
- Fix Suggestions

### 7.4 修改 API 地址

默认页面请求：

```text
http://127.0.0.1:8000/analyze
```

如果 API 端口或地址不同，可通过环境变量覆盖：

```bash
BUG_AGENT_API_URL=http://127.0.0.1:9000/analyze streamlit run ui/streamlit_app.py
```

使用人工复核功能时同时设置基础地址：

```bash
BUG_AGENT_API_URL=http://127.0.0.1:9000/analyze \
BUG_AGENT_API_BASE_URL=http://127.0.0.1:9000 \
streamlit run ui/streamlit_app.py
```

---

## 8. 运行评估

先校验评估集：

```bash
python scripts/validate_eval_dataset.py
```

```bash
python scripts/evaluate.py --disable-llm
python scripts/evaluate_retrieval.py --top-k 3 --compare
python scripts/evaluate_retrieval.py --top-k 3 --compare-embeddings
```

指标含义：

- `classification_accuracy`：Bug 类型分类准确率
- `parser_coverage`：日志解析是否覆盖关键结构
- `evidence_coverage`：最终报告是否生成证据链
- `citation_validity`：根因引用的证据 ID 是否有效
- `retrieval_provenance_coverage`：检索证据是否保留来源元数据
- `review_routing_accuracy`：待人工复核路由是否符合标注
- `Recall@K / MRR / nDCG@K`：检索召回和排序质量

仓库内 5 条端到端 case 和 20 条检索 case 均为演示基线，不代表生产效果。真实数据必须按 `docs/evaluation/real-case-intake.md` 脱敏、双人标注和裁决，并运行：

```bash
python scripts/validate_eval_dataset.py \
  --cases /secure/path/real_cases.json \
  --require-production
```

---

## 9. 运行测试

### 9.1 运行全部测试

```bash
pytest -q
```

测试数量会随功能增加，以命令退出码为准，不在 SOP 中固定总数。

### 9.2 运行指定测试

API 测试：

```bash
pytest tests/test_api.py -v
```

LangGraph 工作流测试：

```bash
pytest tests/test_graph_workflow.py -v
```

评估数据测试：

```bash
pytest tests/test_eval_dataset.py -v
```

---

## 10. 标准演示流程

适合面试或项目汇报时使用。

### 10.1 讲项目定位

可以这样介绍：

> 这是一个面向路由器、光猫等嵌入式网通设备的软件 Bug 分析 Agent。它不是普通问答，而是把日志解析、历史缺陷检索、模块文档检索、代码检索和根因分析串成一个 LangGraph 状态流。

### 10.2 展示 API

```bash
uvicorn app.main:app --reload
```

打开：

```text
http://127.0.0.1:8000/docs
```

执行 `/analyze`，展示返回的：

- `bug_type`
- `summary`
- `evidence`
- `fix_suggestions`

### 10.3 展示 UI

```bash
streamlit run ui/streamlit_app.py
```

点击 `分析 Bug`，展示证据链：

```text
log: ...
doc: dhcp.md ...
bug: BUG-018 ...
code: netifd_reload.c ...
```

### 10.4 展示评估

```bash
python scripts/evaluate.py
```

重点讲当前演示集覆盖 DHCP、PPPoE、Wi-Fi、TR-069 和未知故障复核路径；展示具体指标时必须说明它们来自小规模合成样例，不能表述成线上准确率。

---

## 11. 常见问题排查

### 11.1 `ModuleNotFoundError: No module named 'app'`

优先确认是否在项目根目录：

```bash
pwd
```

应为：

```text
.../embedded-bug-analysis-agent
```

如果从其他目录运行，可以设置：

```bash
export PYTHONPATH="$(pwd)"
```

### 11.2 `streamlit` 或 `uvicorn` 命令不存在

先激活虚拟环境：

```bash
source .venv/bin/activate
```

或者直接使用：

```bash
.venv/bin/uvicorn app.main:app --reload
.venv/bin/streamlit run ui/streamlit_app.py
```

### 11.3 Streamlit 页面提示 API 调用失败

确认 API 服务正在运行：

```bash
curl -s http://127.0.0.1:8000/health
```

如果返回为空或连接失败，重新启动：

```bash
uvicorn app.main:app --reload
```

### 11.4 端口被占用

API 换端口：

```bash
uvicorn app.main:app --port 9000
```

Streamlit 指定 API 地址：

```bash
BUG_AGENT_API_URL=http://127.0.0.1:9000/analyze streamlit run ui/streamlit_app.py
```

### 11.5 混合检索或重排异常

先单独重建并检查索引：

```bash
python scripts/ingest_docs.py
python scripts/evaluate_retrieval.py --top-k 3 --compare
```

使用远程语义 Embedding 时，确认 `EMBEDDING_PROVIDER=openai`，并检查 `EMBEDDING_BASE_URL`、`EMBEDDING_API_KEY` 和 `EMBEDDING_MODEL`。默认混合检索中，向量或 BM25 单路失败时会继续使用另一条链路；FlashRank 或 CrossEncoder 失败时回退本地特征重排；两路召回都不可用时才由文档节点回退到关键词检索。

启用轻量多语言 FlashRank：

```bash
RAG_RERANK_PROVIDER=flashrank
RAG_RERANK_MODEL=ms-marco-MultiBERT-L-12
python scripts/warmup_reranker.py --provider flashrank
```

启用 Sentence Transformers CrossEncoder 前需要执行：

```bash
pip install -r requirements-rerank.txt
```

### 11.6 人工复核任务无法恢复

检查 SQLite 文件和目录权限：

```bash
ls -l run/bug_analysis_checkpoints.sqlite
curl -s http://127.0.0.1:8000/analyses/<analysis_id>
```

确认启动和恢复使用同一个 `LANGGRAPH_CHECKPOINT_PATH`。不要在有待复核任务时删除 `run/`；多 API 副本不能共享本地 SQLite，应改用共享 checkpointer。

---

## 12. 停止服务

FastAPI 和 Streamlit 都用 `Ctrl+C` 停止。

如果需要确认没有残留服务：

```bash
ps -ef | grep -E 'uvicorn|streamlit'
```

---

## 13. Docker Compose 运行

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
docker compose logs -f api
docker compose logs -f worker
```

基础 Compose 会启动 API、UI、Redis 和 RQ Worker。需要观测平台时使用 Overlay：

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.observability.yml \
  up --build -d
```

后台任务接口、API Key、真实 Case 导入、Git 仓库挂载和 Grafana/Tempo 验收步骤见 `docs/production/productionization.md`。

停止并保留索引、模型缓存、checkpoint 和 Redis 任务：

```bash
docker compose down
```

连同具名 volume 一起删除只用于彻底重建环境：

```bash
docker compose down -v
```
