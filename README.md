# 嵌入式网通设备 Bug 分析 Agent

基于 LangChain/LangGraph 的嵌入式网通设备 Bug 分析项目。输入缺陷描述、设备日志和版本信息后，Agent 会检索历史 Bug、模块文档和模拟 C 代码，输出根因假设、证据链和修复建议。

## First Demo Scenario

DHCP 客户端升级后偶发获取不到 IP：

- `netifd` reload 触发 LAN bridge 重建
- DHCP server 早于 bridge ready 启动
- 日志出现 `lease allocation failed`
- 历史 Bug 中存在 bridge 初始化竞态案例

## Run

完成实现任务后运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/ingest_docs.py
uvicorn app.main:app --reload
```

`scripts/ingest_docs.py` 默认使用本地 fake embeddings 构建 Chroma 索引，便于无 API key 演示。

## Real LLM Generation

默认情况下项目使用本地规则链生成根因和修复建议，便于无 API key 演示。

如需接入真实大模型，可在 `.env` 中启用 OpenAI-compatible API：

```bash
LLM_ENABLED=true
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=<your-api-key>
LLM_MODEL=deepseek-chat
LLM_TIMEOUT_SECONDS=30
LLM_TEMPERATURE=0.2
```

Qwen DashScope compatible mode 示例：

```bash
LLM_ENABLED=true
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=<your-api-key>
LLM_MODEL=qwen-plus
```

OpenAI 示例：

```bash
LLM_ENABLED=true
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=<your-api-key>
LLM_MODEL=gpt-4o-mini
```

LLM 输出会经过 Pydantic schema 校验，要求返回 `hypotheses` 和 `fix_suggestions`。如果 LLM 未启用、配置缺失、接口异常或输出格式非法，系统会自动回退到本地规则链，API 响应结构保持不变。

## API Demo

```bash
uvicorn app.main:app --reload
```

Open API docs: `http://127.0.0.1:8000/docs`

## Streamlit Demo

Start API first, then run:

```bash
streamlit run ui/streamlit_app.py
```

## Evaluation

```bash
python scripts/evaluate.py
```

当前首版评估集覆盖 DHCP、PPPoE、Wi-Fi 三类场景，输出：

- `classification_accuracy`：Bug 类型识别准确率
- `parser_coverage`：日志解析覆盖率
- `root_cause_hit_rate`：根因关键词命中率
- `evidence_coverage`：期望证据项覆盖率
- `output_stability`：多次运行时输出稳定性

默认不加载 `.env`，适合快速验证本地规则链：

```bash
python scripts/evaluate.py --disable-llm
```

评估真实 LLM 输出时加载 `.env`，可用 `--repeat` 多次运行观察稳定性：

```bash
python scripts/evaluate.py --load-env --repeat 2
```

## 简历项目描述

**项目名：** 基于 LangChain/LangGraph 的嵌入式网通设备 Bug 分析 Agent

**项目描述：** 面向路由器、光猫等嵌入式网通设备的软件缺陷分析场景，构建 Bug 分析 Agent。系统支持输入缺陷描述、设备日志和版本信息，自动检索历史缺陷、模块文档和模拟 C 代码，输出根因假设、证据链和修复建议。

**技术亮点：**

- 使用 LangGraph 编排 Bug 信息抽取、日志解析、历史缺陷检索、代码检索、根因假设生成和报告输出状态流
- 使用 LangChain Document/Chroma 组织模块文档向量化能力，并在 LangGraph 工作流中检索模块文档证据
- 支持 OpenAI-compatible LLM 接入，使用 Pydantic 校验结构化输出，并保留规则链 fallback
- 构建 DHCP、PPPoE、Wi-Fi、TR-069、升级回归等网通设备样例数据
- 输出带证据链的结构化 Bug 分析报告，降低无依据模型回答风险

**可量化结果：**

- 构建 3 条首版评估样例，覆盖 DHCP、PPPoE、Wi-Fi 三类高频问题
- 首版规则链路分类准确率、日志解析覆盖率、证据链覆盖率均达到 100%
