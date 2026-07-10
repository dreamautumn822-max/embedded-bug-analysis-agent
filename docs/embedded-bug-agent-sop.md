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
  graph/nodes.py                   各分析节点
  chains/                          规则型分析链
  tools/                           日志、历史 Bug、代码检索工具
  rag/                             文档加载与 Chroma 向量库
data/
  bugs/bug_history.json            历史 Bug 数据
  bugs/eval_cases.json             评估数据集
  codebase/                        模拟 C 代码
  docs/                            模块文档
  logs/                            样例日志
scripts/
  ingest_docs.py                   构建本地 Chroma 文档索引
  evaluate.py                      运行评估
ui/
  streamlit_app.py                 Streamlit 演示页面
tests/
  test_*.py                        自动化测试
```

---

## 3. 环境准备

### 3.1 进入项目目录

```bash
cd /home/sdmc/AgentProject
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

当前项目默认走本地 deterministic workflow 和 fake embeddings，演示不需要 OpenAI API Key。

---

## 4. 构建模块文档索引

运行：

```bash
python scripts/ingest_docs.py
```

预期输出：

```text
Indexed documents into .chroma
```

说明：

- 该脚本默认使用 fake embeddings
- 不需要 OpenAI API Key
- 索引会写入 `.chroma/`
- `.chroma/` 已被 `.gitignore` 忽略

如果看到 Chroma telemetry warning，只要最后输出 `Indexed documents into .chroma`，就不影响本地演示。

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

### 5.3 打开 API 文档

浏览器访问：

```text
http://127.0.0.1:8000/docs
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
  "evidence": [
    "log: ...",
    "doc: dhcp.md - ...",
    "bug: BUG-018 - ...",
    "code: netifd_reload.c:..."
  ],
  "fix_suggestions": [
    "在 br-lan 进入 forwarding/ready 状态后再启动 DHCP server"
  ],
  "confidence": 0.95
}
```

### 6.3 结果怎么看

- `bug_type`：Agent 判断的 Bug 类型
- `summary`：最核心的根因摘要
- `root_causes`：根因解释
- `evidence`：证据链，包含日志、文档、历史 Bug、代码片段
- `fix_suggestions`：修复建议
- `confidence`：规则链路给出的置信度

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
3. 点击 `分析 Bug`
4. 查看右侧结果

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

---

## 8. 运行评估

```bash
python scripts/evaluate.py
```

预期输出：

```text
EVAL-001: predicted=network_dhcp, expected=network_dhcp, passed=True, parser_ok=True, evidence_ok=True
EVAL-002: predicted=network_pppoe, expected=network_pppoe, passed=True, parser_ok=True, evidence_ok=True
EVAL-003: predicted=wifi_disconnect, expected=wifi_disconnect, passed=True, parser_ok=True, evidence_ok=True
case_count=3
classification_accuracy=1.00
parser_coverage=1.00
evidence_coverage=1.00
```

指标含义：

- `classification_accuracy`：Bug 类型分类准确率
- `parser_coverage`：日志解析是否覆盖关键结构
- `evidence_coverage`：最终报告是否生成证据链

---

## 9. 运行测试

### 9.1 运行全部测试

```bash
pytest -q
```

当前预期：

```text
19 passed
```

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

重点讲：

- 目前首版覆盖 DHCP、PPPoE、Wi-Fi 三类问题
- 分类准确率 100%
- 日志解析覆盖率 100%
- 证据链覆盖率 100%

---

## 11. 常见问题排查

### 11.1 `ModuleNotFoundError: No module named 'app'`

优先确认是否在项目根目录：

```bash
pwd
```

应为：

```text
/home/sdmc/AgentProject
```

如果从其他目录运行，可以设置：

```bash
export PYTHONPATH=/home/sdmc/AgentProject
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

### 11.5 Chroma telemetry warning

如果运行 `scripts/ingest_docs.py` 时看到类似 telemetry warning，但最后输出：

```text
Indexed documents into .chroma
```

可以忽略。

---

## 12. 停止服务

FastAPI 和 Streamlit 都用 `Ctrl+C` 停止。

如果需要确认没有残留服务：

```bash
ps -ef | grep -E 'uvicorn|streamlit'
```

---

## 13. 简历表述参考

```text
基于 LangChain/LangGraph 构建嵌入式网通设备 Bug 分析 Agent，面向路由器、光猫等设备的软件缺陷分析场景，支持缺陷描述、设备日志、历史 Bug、模块文档和模拟 C 代码的联合分析；通过 LangGraph 编排日志解析、历史缺陷检索、代码检索、文档证据检索、根因假设生成和报告输出流程，生成带证据链的结构化 Bug 分析报告。
```

可量化描述：

```text
构建 DHCP、PPPoE、Wi-Fi 三类首版评估样例，分类准确率、日志解析覆盖率、证据链覆盖率均达到 100%。
```
