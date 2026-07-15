# 生产化扩展与运行手册

本文说明真实 Case、Git 代码知识库、可观测性和后台任务四个扩展的设计、配置、执行流程与验收方法。

## 1. 总体架构

```text
Streamlit / API Client
        |
        | X-API-Key + Idempotency-Key
        v
FastAPI API
  |-- API Key 摘要认证 -> tenant_id
  |-- 同步 /analyze 与 /analyses
  |-- 后台 /v1/jobs
  |-- /metrics
        |
        +---- Redis ---- RQ Worker ---- LangGraph
                              |            |
                              |            +-- SQLite WAL checkpoint
                              |            +-- Chroma + BM25 + Rerank
                              |            +-- OpenAI-compatible LLM
                              |
                              +-- 任务结果、重试、取消、超时

Prometheus <- API metrics
Grafana    <- Prometheus + Tempo
Tempo      <- API / Worker OTLP Trace
Alertmanager <- Prometheus alerts
```

后台任务与同步接口共用同一条 LangGraph，不维护两套业务逻辑。队列只负责执行调度、生命周期和租户所有权。

## 2. 真实故障 Case

### 2.1 原始数据边界

原始工单必须位于公司批准的受控存储，不进入本仓库。仓库只提供格式示例：

```text
docs/evaluation/real-case-import.example.json
```

每条原始记录要求：

- 稳定的内部工单 ID；
- 设备、固件、现象、日志和可选堆栈；
- 至少两名不同标注者；
- 与标注者不同的仲裁者；
- 仲裁后的 Bug 类型、根因关键词、证据词和复核标签；
- `manual_review_confirmed=true`。

### 2.2 导入

生成至少 16 位随机盐，只放在密码管理系统或运行环境：

```bash
export BUG_AGENT_CASE_HASH_SALT='<random-secret>'
python scripts/import_real_cases.py \
  --input /secure/raw/cases.json \
  --output run/private_eval/real_eval_cases.json
```

导入器执行：

1. 用 HMAC-SHA256 把原工单 ID 转换为不可逆摘要。
2. 在单个 Case 内稳定替换 MAC、IPv4、邮箱、序列号、账号和主机名。
3. 同一敏感值映射到相同编号，不同值映射到不同编号。
4. 丢弃标注者和仲裁者身份，只保留 `annotator_count`。
5. 生成 `production_anonymized`、`adjudicated` Case。
6. 再次执行敏感字段扫描、重复 ID 和跨 Split 工单泄漏检查。

默认输出目录 `run/private_eval/` 已被 Git 忽略。脚本会拒绝把生产 Case 写入仓库内的其他目录。

### 2.3 验收

```bash
python scripts/validate_eval_dataset.py \
  --cases run/private_eval/real_eval_cases.json \
  --require-production

python scripts/evaluate.py \
  --cases run/private_eval/real_eval_cases.json \
  --disable-llm

python scripts/evaluate.py \
  --cases run/private_eval/real_eval_cases.json \
  --load-env --repeat 3
```

生产报告必须把 synthetic 与 production_anonymized 指标分开，不得用五条合成 Case 的结果声明生产准确率。

## 3. Git 代码知识库

### 3.1 数据来源

系统读取已经检出的本地 Git 仓库，不保存远程仓库凭据，也不自动执行 `git pull`。支持：

- 递归扫描 `.c`、`.h`；
- tree-sitter 函数级 AST 切分；
- 函数直接调用和反向调用者；
- `#if`、`#ifdef` 和 `#elif` 条件编译上下文；
- Kconfig、Makefile、CMake、`.mk` 和 `.conf`；
- 最近 N 个相关 Commit Diff；
- Commit SHA、主题、时间和变更文件，不索引作者信息。

函数指针、动态注册、跨语言调用和编译器展开后的调用关系不在当前解析范围内。

### 3.2 本地索引

```bash
export CODEBASE_DIR=/secure/repos/firmware
export RAG_GIT_HISTORY_ENABLED=true
export RAG_GIT_MAX_COMMITS=20
export RAG_GIT_DIFF_MAX_CHARS=12000

python scripts/index_git_repository.py \
  --repo /secure/repos/firmware \
  --max-commits 20
```

代码、配置和 Diff 最终仍是 `source_type=code` 的 LangChain `Document`，因此自动复用：

```text
BGE 向量召回
  + BM25 标识符召回
  -> RRF 融合
  -> Rerank
  -> EvidenceDetail
  -> LLM / 规则根因
```

响应中的代码证据可能包含：

- `code_kind=function|source_file|build_config|commit_diff`；
- `symbol/start_line/end_line`；
- `calls/callers`；
- `preprocessor_context`；
- `repository_revision`；
- `commit_sha/commit_subject/changed_files`。

### 3.3 Docker 挂载

`.env`：

```bash
CODE_REPOSITORY_PATH=/secure/repos/firmware
RAG_GIT_HISTORY_ENABLED=true
```

Compose 以只读方式挂载到 `/workspace/repository`。仓库内容不会写入镜像或 Docker volume。

`rag-init` 和 `metrics-init` 是长驻就绪 Sidecar。前者在 API/Worker 启动前预热模型并创建索引，后者在整栈启动时清理一次 Prometheus 多进程目录；重复执行 `docker compose up -d` 不会再次在线写 Chroma 或删除活动指标文件。知识源变化时先停止 API/Worker，重启 `rag-init`，再启动业务进程。

## 4. 后台任务、超时与取消

### 4.1 任务状态

```text
queued
  -> running
      -> completed
      -> pending_review -> queued(review) -> running -> completed
      -> failed
      -> timed_out
  -> cancel_requested -> cancelled
  -> cancelled
```

Redis 保存领域任务记录，RQ 保存执行队列和 Worker 状态。任务记录包含租户、输入、当前 RQ Job、尝试次数、复核载荷和最终报告，并按 TTL 自动过期。

### 4.2 入队

```bash
curl -X POST http://127.0.0.1:8000/v1/jobs \
  -H 'X-API-Key: <key>' \
  -H 'Idempotency-Key: <stable-request-id>' \
  -H 'Content-Type: application/json' \
  -d @request.json
```

同一租户使用相同 `Idempotency-Key` 和相同请求时返回原任务。相同 Key 对应不同请求时返回 `409`，防止静默覆盖。

### 4.3 查询、取消和复核

```bash
curl -H 'X-API-Key: <key>' \
  http://127.0.0.1:8000/v1/jobs/<job_id>

curl -X DELETE -H 'X-API-Key: <key>' \
  http://127.0.0.1:8000/v1/jobs/<job_id>

curl -X POST http://127.0.0.1:8000/v1/jobs/<job_id>/review \
  -H 'X-API-Key: <key>' \
  -H 'Content-Type: application/json' \
  -d '{"approved":true,"reviewer":"owner","comment":"confirmed"}'
```

排队任务通过 RQ cancel 直接取消；运行中任务向 Worker 发送 stop command，并先进入 `cancel_requested`。RQ 超时异常在查询时归一化为 `timed_out`。

### 4.4 重试和 TTL

| 环境变量 | 作用 | 默认值 |
| --- | --- | ---: |
| `JOB_TIMEOUT_SECONDS` | 默认执行超时 | 120 秒 |
| `JOB_MAX_TIMEOUT_SECONDS` | API 允许的最大超时 | 900 秒 |
| `JOB_MAX_RETRIES` | 失败后的最大重试次数 | 1 |
| `JOB_RESULT_TTL_SECONDS` | 成功任务保留时间 | 86400 秒 |
| `JOB_FAILURE_TTL_SECONDS` | 失败任务保留时间 | 86400 秒 |
| `JOB_IDEMPOTENCY_TTL_SECONDS` | 幂等映射保留时间 | 86400 秒 |

## 5. API Key 与租户隔离

### 5.1 创建摘要

```bash
python scripts/hash_api_key.py
```

配置示例：

```bash
API_AUTH_ENABLED=true
BUG_AGENT_API_KEY_HASHES_JSON={"team-a":"sha256:<digest-a>","team-b":"sha256:<digest-b>"}
```

服务端只比较 SHA-256 摘要。`tenant_id` 来自匹配的配置项，不接受客户端自报租户。

### 5.2 隔离范围

已经隔离：

- Redis 任务查询、取消和审批；
- LangGraph checkpoint 查询和恢复；
- 幂等键命名空间。

尚未隔离：

- Chroma collection；
- 模块文档、历史 Bug 和代码仓库；
- Prometheus 指标。

需要严格知识库隔离时，应按租户配置独立 collection、代码挂载和知识目录，而不是只依赖 API 层过滤。

## 6. 指标、Trace 和告警

启动完整观测栈：

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.observability.yml \
  up --build -d
```

主要指标：

| 指标 | 含义 |
| --- | --- |
| `bug_agent_http_requests_total` | HTTP 方法、路由和状态码 |
| `bug_agent_http_request_duration_seconds` | HTTP 延迟直方图 |
| `bug_agent_node_runs_total` | LangGraph 节点成功、fallback、异常和中断 |
| `bug_agent_retrieval_duration_seconds` | 各知识源检索延迟 |
| `bug_agent_llm_requests_total` | LLM 成功、请求错误和非法输出 |
| `bug_agent_llm_tokens_total` | Provider 返回的输入和输出 Token |
| `bug_agent_queue_depth` | RQ 队列深度 |
| `bug_agent_queue_jobs_current` | Redis 中各状态任务数量 |

Trace 不记录 Prompt、日志正文或 API Key，只记录节点名、状态、结果数量、模型名和 Token 数。API 入队时注入 W3C Trace Context，Worker 提取后继续同一条 Trace。

默认告警：

- API 一分钟不可抓取；
- HTTP p95 连续五分钟高于 20 秒；
- fallback 比例连续十分钟高于 20%；
- LLM 请求错误或非法输出比例高于 20%；
- 队列深度连续五分钟高于 20。

Alertmanager 默认接收器不外发通知。生产环境需要增加飞书、邮件或值班平台 Webhook。

## 7. 压测

```bash
python -m pip install -r requirements-loadtest.txt
BUG_AGENT_LOADTEST_API_KEY=<raw-key> \
locust -f loadtests/locustfile.py \
  --headless --host http://127.0.0.1:8000 \
  --users 10 --spawn-rate 2 --run-time 5m \
  --csv run/loadtest/bug-agent
```

压测必须同时记录 API p95、队列等待、任务完成率、超时率、fallback、Worker CPU/内存和模型加载时间。不要只看入队接口延迟。

## 8. 验收清单

```bash
pytest -q
python -m compileall -q app scripts tests ui loadtests
python scripts/validate_eval_dataset.py
docker compose config -q
docker compose -f docker-compose.yml -f docker-compose.observability.yml config -q
```

人工验收：

1. 使用租户 A 创建任务，租户 B 查询应返回 404。
2. 相同幂等键和请求返回相同 Job ID。
3. 修改请求后复用幂等键应返回 409。
4. 排队任务可以取消，运行任务先进入 `cancel_requested`。
5. 低置信度任务进入 `pending_review`，审批后恢复原 checkpoint。
6. Grafana 能看到请求、fallback、队列和检索面板。
7. Tempo 能看到 HTTP -> Queue -> LangGraph Node -> RAG/LLM Span。
8. 真实 Case 校验必须带 `--require-production` 且不在 Git 工作区出现。
9. `API_AUTH_ENABLED=true`，且 Grafana、Redis、模型服务和 Case 盐均使用外部 Secret 注入。

## 9. 后续生产升级

- 多主机部署时把 SQLite checkpointer 迁移到 PostgreSQL。
- 多租户严格隔离时拆分 Chroma、代码仓库和文档目录。
- 使用 Vault、KMS 或容器 Secret 管理 API Key、模型密钥和 Case 盐。
- 为 Redis 配置 TLS、ACL、备份和最大内存淘汰策略。
- 把 Alertmanager 接入企业值班系统，并为严重告警建立处理手册。
- 根据真实 Case 和目标硬件压测结果确定 Worker 数量、超时和发布门槛。
