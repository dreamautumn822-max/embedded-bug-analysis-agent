# 嵌入式网通设备 Bug 分析 Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个基于 LangChain/LangGraph 的嵌入式网通设备 Bug 分析 Agent，输入缺陷描述、日志、版本信息和可选调用栈后，自动检索历史 Bug、模块文档、模拟 C 代码，并输出根因分析、证据链、影响范围和修复建议。

**Architecture:** 项目采用 FastAPI + LangGraph + LangChain RAG 的结构。LangGraph 负责编排 Bug 信息抽取、类型分类、文档检索、历史缺陷检索、日志解析、代码检索、根因假设生成、证据校验和报告生成；LangChain 负责模型调用、Prompt、向量检索和工具封装；本地模拟数据保存在 `data/`，向量库保存在 `.chroma/`。

**Tech Stack:** Python 3.11、FastAPI、Pydantic、LangChain、LangGraph、langchain-openai、langchain-community、Chroma、pytest、Streamlit。

---

## Scope

第一版只做 Bug 分析和修复建议，不自动修改代码、不连接真实设备、不接入公司内部系统。

项目展示重点：

- 嵌入式网通领域 Bug 分析场景
- RAG 检索模块文档和历史缺陷
- Agent 工具调用：日志解析、历史 Bug 搜索、代码搜索
- LangGraph 状态流编排
- 证据链输出，避免无来源结论
- 可演示 UI 和 API

---

## File Structure

实现完成后项目结构如下：

```text
embedded-bug-agent/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── bug.py
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── nodes.py
│   │   └── bug_analysis_graph.py
│   ├── chains/
│   │   ├── __init__.py
│   │   ├── extract_chain.py
│   │   ├── root_cause_chain.py
│   │   └── report_chain.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── log_parser.py
│   │   ├── bug_history_search.py
│   │   └── code_search.py
│   └── rag/
│       ├── __init__.py
│       ├── loader.py
│       ├── vector_store.py
│       └── retriever.py
├── data/
│   ├── bugs/
│   │   └── bug_history.json
│   ├── codebase/
│   │   ├── dhcp_server.c
│   │   ├── netifd_reload.c
│   │   ├── pppoe_client.c
│   │   ├── tr069_report.c
│   │   └── wifi_manager.c
│   ├── docs/
│   │   ├── dhcp.md
│   │   ├── pppoe.md
│   │   ├── tr069.md
│   │   ├── upgrade.md
│   │   └── wifi.md
│   └── logs/
│       ├── dhcp_lease_failed.log
│       ├── pppoe_auth_failed.log
│       └── wifi_disconnect.log
├── scripts/
│   └── ingest_docs.py
├── tests/
│   ├── test_log_parser.py
│   ├── test_bug_history_search.py
│   ├── test_code_search.py
│   ├── test_graph_nodes.py
│   └── test_api.py
├── ui/
│   └── streamlit_app.py
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

Responsibilities:

- `app/schemas/bug.py`: API 输入输出数据结构。
- `app/tools/log_parser.py`: 从设备日志中提取错误模式、模块名、时间线和关键证据。
- `app/tools/bug_history_search.py`: 从本地历史缺陷 JSON 中检索相似 Bug。
- `app/tools/code_search.py`: 对模拟 C 代码库做关键词检索，返回文件名、行号和代码片段。
- `app/rag/*`: 加载模块文档、构建向量库、创建 retriever。
- `app/chains/*`: 封装模型调用。无 API key 时提供 deterministic fallback，保证测试可跑。
- `app/graph/*`: 定义 LangGraph 状态、节点函数和状态流。
- `app/main.py`: 提供 `/analyze` API。
- `ui/streamlit_app.py`: 演示输入、Agent 步骤和分析报告。

---

## Task 1: Project Bootstrap

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `README.md`
- Create: package directories under `app/`

- [ ] **Step 1: Create dependency file**

Create `requirements.txt`:

```text
fastapi==0.115.6
uvicorn[standard]==0.32.1
pydantic==2.10.3
python-dotenv==1.0.1
langchain==0.3.12
langgraph==0.2.60
langchain-openai==0.2.12
langchain-community==0.3.12
langchain-chroma==0.1.4
chromadb==0.5.23
streamlit==1.41.1
pytest==8.3.4
httpx==0.28.1
```

- [ ] **Step 2: Create environment example**

Create `.env.example`:

```text
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
CHROMA_DIR=.chroma
DOCS_DIR=data/docs
BUG_HISTORY_PATH=data/bugs/bug_history.json
CODEBASE_DIR=data/codebase
```

- [ ] **Step 3: Create `.gitignore`**

Create `.gitignore`:

```text
.env
.venv/
__pycache__/
.pytest_cache/
.chroma/
*.pyc
```

- [ ] **Step 4: Create package directories**

Run:

```bash
mkdir -p app/schemas app/graph app/chains app/tools app/rag data/bugs data/codebase data/docs data/logs scripts tests ui
touch app/__init__.py app/schemas/__init__.py app/graph/__init__.py app/chains/__init__.py app/tools/__init__.py app/rag/__init__.py
```

Expected: directories and package marker files exist.

- [ ] **Step 5: Create initial README**

Create `README.md`:

```markdown
# 嵌入式网通设备 Bug 分析 Agent

基于 LangChain/LangGraph 的嵌入式网通设备 Bug 分析项目。输入缺陷描述、设备日志和版本信息后，Agent 会检索历史 Bug、模块文档和模拟 C 代码，输出根因假设、证据链和修复建议。

## First Demo Scenario

DHCP 客户端升级后偶发获取不到 IP：

- `netifd` reload 触发 LAN bridge 重建
- DHCP server 早于 bridge ready 启动
- 日志出现 `lease allocation failed`
- 历史 Bug 中存在 bridge 初始化竞态案例

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/ingest_docs.py
uvicorn app.main:app --reload
```
```

- [ ] **Step 6: Install dependencies**

Run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: packages install successfully.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .env.example .gitignore README.md app scripts tests ui data
git commit -m "chore: bootstrap embedded bug agent project"
```

---

## Task 2: Define Bug Schemas

**Files:**
- Create: `app/schemas/bug.py`
- Test: `tests/test_schemas.py`

- [ ] **Step 1: Write failing schema test**

Create `tests/test_schemas.py`:

```python
from app.schemas.bug import BugAnalyzeRequest, BugAnalyzeResponse


def test_bug_analyze_request_defaults():
    request = BugAnalyzeRequest(
        device_model="AX3000 Router",
        firmware_version="v2.1.8",
        symptom="升级后 DHCP 客户端偶发获取不到 IP",
        logs="dhcpd: lease allocation failed",
    )

    assert request.device_model == "AX3000 Router"
    assert request.firmware_version == "v2.1.8"
    assert request.stack_trace is None
    assert request.module_hint is None


def test_bug_analyze_response_shape():
    response = BugAnalyzeResponse(
        bug_type="network_dhcp",
        summary="DHCP 服务启动时序异常",
        root_causes=["DHCP server starts before bridge is ready"],
        evidence=["log: dhcpd lease allocation failed"],
        fix_suggestions=["wait bridge ready before restarting DHCP server"],
        confidence=0.82,
    )

    assert response.bug_type == "network_dhcp"
    assert response.confidence == 0.82
    assert response.root_causes[0].startswith("DHCP")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_schemas.py -v
```

Expected: FAIL with `ModuleNotFoundError` or missing classes.

- [ ] **Step 3: Implement schemas**

Create `app/schemas/bug.py`:

```python
from pydantic import BaseModel, Field


class BugAnalyzeRequest(BaseModel):
    device_model: str = Field(min_length=1)
    firmware_version: str = Field(min_length=1)
    symptom: str = Field(min_length=1)
    logs: str = Field(min_length=1)
    stack_trace: str | None = None
    module_hint: str | None = None


class BugAnalyzeResponse(BaseModel):
    bug_type: str
    summary: str
    root_causes: list[str]
    evidence: list[str]
    fix_suggestions: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_schemas.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/schemas/bug.py tests/test_schemas.py
git commit -m "feat: define bug analysis schemas"
```

---

## Task 3: Add Sample Domain Data

**Files:**
- Create: `data/bugs/bug_history.json`
- Create: `data/docs/dhcp.md`
- Create: `data/docs/pppoe.md`
- Create: `data/docs/wifi.md`
- Create: `data/docs/tr069.md`
- Create: `data/docs/upgrade.md`
- Create: `data/codebase/*.c`
- Create: `data/logs/*.log`

- [ ] **Step 1: Create historical Bug data**

Create `data/bugs/bug_history.json`:

```json
[
  {
    "bug_id": "BUG-018",
    "title": "LAN bridge reload causes DHCP lease failure",
    "module": "dhcp/netifd",
    "symptom": "client cannot obtain IP after firmware upgrade",
    "root_cause": "DHCP service starts before bridge interface is ready",
    "fix": "wait for bridge ready event before restarting DHCP server",
    "keywords": ["dhcp", "lease allocation failed", "netifd", "bridge", "upgrade"],
    "related_files": ["netifd_reload.c", "dhcp_server.c"]
  },
  {
    "bug_id": "BUG-027",
    "title": "PPPoE authentication retry stops after link flap",
    "module": "wan/pppoe",
    "symptom": "PPPoE cannot reconnect after WAN link recovers",
    "root_cause": "retry timer is not restarted when link state changes from down to up",
    "fix": "restart PPPoE authentication timer on WAN link up event",
    "keywords": ["pppoe", "auth failed", "wan", "retry", "link flap"],
    "related_files": ["pppoe_client.c"]
  },
  {
    "bug_id": "BUG-033",
    "title": "Wi-Fi clients disconnect during channel switch",
    "module": "wifi",
    "symptom": "clients disconnect when auto channel selection runs",
    "root_cause": "channel switch event clears station table before reassociation window",
    "fix": "delay station cleanup until channel switch completion event",
    "keywords": ["wifi", "disconnect", "channel switch", "station table"],
    "related_files": ["wifi_manager.c"]
  },
  {
    "bug_id": "BUG-041",
    "title": "TR-069 inform fails after DNS update",
    "module": "management/tr069",
    "symptom": "ACS inform fails after DNS configuration change",
    "root_cause": "TR-069 client keeps stale resolver cache after DNS reload",
    "fix": "clear resolver cache before next inform request",
    "keywords": ["tr069", "acs", "dns", "inform", "resolver"],
    "related_files": ["tr069_report.c"]
  },
  {
    "bug_id": "BUG-052",
    "title": "Configuration migration loses DHCP address pool",
    "module": "upgrade/config",
    "symptom": "LAN clients cannot obtain IP after firmware upgrade",
    "root_cause": "old DHCP pool key is not mapped to new config schema",
    "fix": "add migration rule for lan.dhcp.pool_start and lan.dhcp.pool_end",
    "keywords": ["upgrade", "dhcp", "migration", "address pool", "config"],
    "related_files": ["dhcp_server.c"]
  }
]
```

- [ ] **Step 2: Create module docs**

Create `data/docs/dhcp.md`:

```markdown
# DHCP 模块说明

DHCP server 依赖 LAN bridge 处于 ready 状态。`netifd reload` 会触发 LAN bridge 重建，bridge 未 ready 时启动 DHCP server 可能出现 `lease allocation failed`。

排查 DHCP 获取失败时，需要检查：

- 是否出现 `dhcpd: lease allocation failed`
- 是否在同一时间窗口出现 `netifd: interface lan reload`
- 是否出现 `kernel: br-lan port state changed`
- DHCP 地址池是否为空
- bridge ready 事件是否早于 DHCP server restart
```

Create `data/docs/pppoe.md`:

```markdown
# PPPoE 模块说明

PPPoE 拨号失败常见原因包括账号认证失败、WAN link flap、认证重试定时器未启动、MTU 配置错误。

出现 `pppoe: auth failed` 时，需要结合 WAN 口 link 状态和 retry timer 日志判断是账号问题还是状态机问题。
```

Create `data/docs/wifi.md`:

```markdown
# Wi-Fi 模块说明

Wi-Fi 掉线问题常见于自动信道切换、DFS 检测、弱信号、驱动重启和 station table 清理。

如果日志中同时出现 `channel switch` 和 `station disconnected`，优先检查信道切换完成事件前是否清理了 station table。
```

Create `data/docs/tr069.md`:

```markdown
# TR-069 模块说明

TR-069 inform 失败通常与 ACS 地址解析、DNS 缓存、认证参数、WAN 可达性有关。

DNS 配置更新后，TR-069 client 应清理 resolver cache，否则可能继续访问旧 ACS 地址。
```

Create `data/docs/upgrade.md`:

```markdown
# 固件升级与配置迁移说明

固件升级后出现网络异常时，需要检查配置迁移规则。旧版本配置 key 如果没有映射到新 schema，可能导致 DHCP 地址池、WAN 账号、Wi-Fi 参数丢失。
```

- [ ] **Step 3: Create simulated C codebase**

Create `data/codebase/netifd_reload.c`:

```c
#include "network.h"

void lan_reload_handler(void) {
    restart_bridge("br-lan");
    restart_dhcp_server();
}

int is_bridge_ready(const char *ifname) {
    return query_link_state(ifname) == LINK_READY;
}
```

Create `data/codebase/dhcp_server.c`:

```c
#include "dhcp_server.h"

int restart_dhcp_server(void) {
    if (dhcp_pool_empty()) {
        log_error("dhcpd: lease allocation failed");
        return -1;
    }
    return dhcpd_restart();
}
```

Create `data/codebase/pppoe_client.c`:

```c
#include "pppoe_client.h"

void on_wan_link_up(void) {
    set_pppoe_state(PPPOE_STATE_READY);
}

void on_pppoe_auth_failed(void) {
    log_error("pppoe: auth failed");
    stop_retry_timer();
}
```

Create `data/codebase/wifi_manager.c`:

```c
#include "wifi_manager.h"

void on_channel_switch_start(void) {
    clear_station_table();
    log_info("wifi: channel switch started");
}

void on_station_disconnect(const char *mac) {
    log_info("wifi: station disconnected");
}
```

Create `data/codebase/tr069_report.c`:

```c
#include "tr069_report.h"

int send_periodic_inform(void) {
    const char *acs_host = resolver_cache_get("acs.example.net");
    return http_post_inform(acs_host);
}
```

- [ ] **Step 4: Create sample logs**

Create `data/logs/dhcp_lease_failed.log`:

```text
2026-06-25 14:03:11 netifd: interface lan reload
2026-06-25 14:03:12 kernel: br-lan port state changed to blocking
2026-06-25 14:03:12 dhcpd: lease allocation failed
2026-06-25 14:03:14 kernel: br-lan port state changed to forwarding
```

Create `data/logs/pppoe_auth_failed.log`:

```text
2026-06-25 08:22:01 netifd: wan link down
2026-06-25 08:22:04 netifd: wan link up
2026-06-25 08:22:05 pppoe: auth failed
2026-06-25 08:22:05 pppoe: retry timer stopped
```

Create `data/logs/wifi_disconnect.log`:

```text
2026-06-25 20:15:31 wifi: channel switch started
2026-06-25 20:15:31 wifi: station disconnected mac=10:22:33:44:55:66
2026-06-25 20:15:33 wifi: channel switch completed
```

- [ ] **Step 5: Commit**

```bash
git add data
git commit -m "testdata: add embedded networking bug samples"
```

---

## Task 4: Implement Log Parser Tool

**Files:**
- Create: `app/tools/log_parser.py`
- Test: `tests/test_log_parser.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_log_parser.py`:

```python
from app.tools.log_parser import parse_syslog


def test_parse_dhcp_log_extracts_patterns():
    logs = """
2026-06-25 14:03:11 netifd: interface lan reload
2026-06-25 14:03:12 kernel: br-lan port state changed to blocking
2026-06-25 14:03:12 dhcpd: lease allocation failed
2026-06-25 14:03:14 kernel: br-lan port state changed to forwarding
"""

    result = parse_syslog(logs)

    assert result["modules"] == ["dhcpd", "kernel", "netifd"]
    assert "lease allocation failed" in result["error_patterns"]
    assert "interface reload" in result["events"]
    assert result["evidence"][0].startswith("2026-06-25")


def test_parse_wifi_log_extracts_disconnect():
    logs = """
2026-06-25 20:15:31 wifi: channel switch started
2026-06-25 20:15:31 wifi: station disconnected mac=10:22:33:44:55:66
2026-06-25 20:15:33 wifi: channel switch completed
"""

    result = parse_syslog(logs)

    assert result["modules"] == ["wifi"]
    assert "station disconnected" in result["error_patterns"]
    assert "channel switch" in result["events"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_log_parser.py -v
```

Expected: FAIL because `app.tools.log_parser` does not exist.

- [ ] **Step 3: Implement log parser**

Create `app/tools/log_parser.py`:

```python
import re


MODULE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ([^:]+): (.+)")

ERROR_KEYWORDS = {
    "lease allocation failed": "lease allocation failed",
    "auth failed": "auth failed",
    "station disconnected": "station disconnected",
    "inform failed": "inform failed",
    "segfault": "segfault",
}

EVENT_KEYWORDS = {
    "interface lan reload": "interface reload",
    "br-lan port state changed": "bridge state change",
    "channel switch": "channel switch",
    "wan link up": "wan link up",
    "wan link down": "wan link down",
    "retry timer stopped": "retry timer stopped",
}


def parse_syslog(logs: str) -> dict:
    modules: set[str] = set()
    error_patterns: list[str] = []
    events: list[str] = []
    evidence: list[str] = []

    for raw_line in logs.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = MODULE_PATTERN.match(line)
        if match:
            modules.add(match.group(1))

        lowered = line.lower()
        for keyword, label in ERROR_KEYWORDS.items():
            if keyword in lowered and label not in error_patterns:
                error_patterns.append(label)
                evidence.append(line)

        for keyword, label in EVENT_KEYWORDS.items():
            if keyword in lowered and label not in events:
                events.append(label)
                evidence.append(line)

    return {
        "modules": sorted(modules),
        "error_patterns": error_patterns,
        "events": events,
        "evidence": evidence,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_log_parser.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/tools/log_parser.py tests/test_log_parser.py
git commit -m "feat: add syslog parser tool"
```

---

## Task 5: Implement Historical Bug Search Tool

**Files:**
- Create: `app/tools/bug_history_search.py`
- Test: `tests/test_bug_history_search.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_bug_history_search.py`:

```python
from pathlib import Path

from app.tools.bug_history_search import search_bug_history


def test_search_bug_history_returns_dhcp_bug():
    results = search_bug_history(
        query="dhcp lease allocation failed after netifd reload",
        bug_history_path=Path("data/bugs/bug_history.json"),
        limit=2,
    )

    assert results[0]["bug_id"] == "BUG-018"
    assert results[0]["score"] > 0
    assert "DHCP service starts before bridge" in results[0]["root_cause"]


def test_search_bug_history_returns_empty_for_unrelated_query():
    results = search_bug_history(
        query="bluetooth pairing battery issue",
        bug_history_path=Path("data/bugs/bug_history.json"),
        limit=2,
    )

    assert results == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_bug_history_search.py -v
```

Expected: FAIL because search function does not exist.

- [ ] **Step 3: Implement keyword search**

Create `app/tools/bug_history_search.py`:

```python
import json
import re
from pathlib import Path


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_./-]+")


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(text)}


def search_bug_history(query: str, bug_history_path: Path, limit: int = 3) -> list[dict]:
    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    bugs = json.loads(bug_history_path.read_text(encoding="utf-8"))
    scored: list[dict] = []

    for bug in bugs:
        searchable = " ".join(
            [
                bug["title"],
                bug["module"],
                bug["symptom"],
                bug["root_cause"],
                bug["fix"],
                " ".join(bug["keywords"]),
            ]
        )
        overlap = query_tokens & _tokens(searchable)
        score = len(overlap)
        if score > 0:
            enriched = dict(bug)
            enriched["score"] = score
            enriched["matched_terms"] = sorted(overlap)
            scored.append(enriched)

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_bug_history_search.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/tools/bug_history_search.py tests/test_bug_history_search.py
git commit -m "feat: add historical bug search tool"
```

---

## Task 6: Implement Code Search Tool

**Files:**
- Create: `app/tools/code_search.py`
- Test: `tests/test_code_search.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_code_search.py`:

```python
from pathlib import Path

from app.tools.code_search import search_codebase


def test_search_codebase_finds_lan_reload_handler():
    results = search_codebase(
        query="restart dhcp server bridge ready",
        codebase_dir=Path("data/codebase"),
        limit=3,
    )

    assert any(result["file"] == "netifd_reload.c" for result in results)
    assert any("restart_dhcp_server" in result["snippet"] for result in results)


def test_search_codebase_finds_wifi_channel_switch():
    results = search_codebase(
        query="wifi channel switch station disconnected",
        codebase_dir=Path("data/codebase"),
        limit=3,
    )

    assert results[0]["file"] == "wifi_manager.c"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_code_search.py -v
```

Expected: FAIL because `search_codebase` does not exist.

- [ ] **Step 3: Implement code search**

Create `app/tools/code_search.py`:

```python
import re
from pathlib import Path


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+")


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(text)}


def _snippet(lines: list[str], index: int, radius: int = 2) -> str:
    start = max(index - radius, 0)
    end = min(index + radius + 1, len(lines))
    return "".join(lines[start:end]).strip()


def search_codebase(query: str, codebase_dir: Path, limit: int = 5) -> list[dict]:
    query_tokens = _tokens(query)
    results: list[dict] = []

    for path in sorted(codebase_dir.glob("*.c")):
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        file_text = "".join(lines)
        file_tokens = _tokens(file_text)
        file_score = len(query_tokens & file_tokens)

        for index, line in enumerate(lines):
            line_tokens = _tokens(line)
            line_score = len(query_tokens & line_tokens)
            if line_score > 0 or file_score >= 2:
                results.append(
                    {
                        "file": path.name,
                        "line": index + 1,
                        "score": line_score + file_score,
                        "snippet": _snippet(lines, index),
                    }
                )
                break

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_code_search.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/tools/code_search.py tests/test_code_search.py
git commit -m "feat: add C codebase search tool"
```

---

## Task 7: Implement RAG Loader and Retriever

**Files:**
- Create: `app/rag/loader.py`
- Create: `app/rag/vector_store.py`
- Create: `app/rag/retriever.py`
- Create: `scripts/ingest_docs.py`
- Test: `tests/test_rag_loader.py`

- [ ] **Step 1: Write failing loader test**

Create `tests/test_rag_loader.py`:

```python
from pathlib import Path

from app.rag.loader import load_markdown_docs


def test_load_markdown_docs_reads_domain_docs():
    docs = load_markdown_docs(Path("data/docs"))

    assert len(docs) == 5
    assert any(doc.metadata["source"] == "dhcp.md" for doc in docs)
    assert any("DHCP server" in doc.page_content for doc in docs)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_rag_loader.py -v
```

Expected: FAIL because loader does not exist.

- [ ] **Step 3: Implement loader**

Create `app/rag/loader.py`:

```python
from pathlib import Path

from langchain_core.documents import Document


def load_markdown_docs(docs_dir: Path) -> list[Document]:
    documents: list[Document] = []
    for path in sorted(docs_dir.glob("*.md")):
        documents.append(
            Document(
                page_content=path.read_text(encoding="utf-8"),
                metadata={"source": path.name},
            )
        )
    return documents
```

- [ ] **Step 4: Implement vector store**

Create `app/rag/vector_store.py`:

```python
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.embeddings import FakeEmbeddings
from langchain_openai import OpenAIEmbeddings

from app.rag.loader import load_markdown_docs


def build_embeddings(use_fake: bool = False):
    if use_fake:
        return FakeEmbeddings(size=1536)
    return OpenAIEmbeddings()


def build_vector_store(docs_dir: Path, persist_dir: Path, use_fake_embeddings: bool = False) -> Chroma:
    docs = load_markdown_docs(docs_dir)
    embeddings = build_embeddings(use_fake=use_fake_embeddings)
    return Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=str(persist_dir),
        collection_name="embedded_bug_docs",
    )
```

- [ ] **Step 5: Implement retriever factory**

Create `app/rag/retriever.py`:

```python
from pathlib import Path

from langchain_chroma import Chroma

from app.rag.vector_store import build_embeddings


def create_doc_retriever(persist_dir: Path, use_fake_embeddings: bool = False):
    embeddings = build_embeddings(use_fake=use_fake_embeddings)
    store = Chroma(
        persist_directory=str(persist_dir),
        embedding_function=embeddings,
        collection_name="embedded_bug_docs",
    )
    return store.as_retriever(search_kwargs={"k": 3})
```

- [ ] **Step 6: Implement ingestion script**

Create `scripts/ingest_docs.py`:

```python
from pathlib import Path

from app.rag.vector_store import build_vector_store


if __name__ == "__main__":
    build_vector_store(
        docs_dir=Path("data/docs"),
        persist_dir=Path(".chroma"),
        use_fake_embeddings=False,
    )
    print("Indexed documents into .chroma")
```

- [ ] **Step 7: Run loader test**

Run:

```bash
pytest tests/test_rag_loader.py -v
```

Expected: PASS.

- [ ] **Step 8: Run ingestion with fake embeddings in a smoke command**

Run:

```bash
python -c "from pathlib import Path; from app.rag.vector_store import build_vector_store; build_vector_store(Path('data/docs'), Path('/tmp/embedded-bug-agent-chroma'), use_fake_embeddings=True); print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 9: Commit**

```bash
git add app/rag scripts/ingest_docs.py tests/test_rag_loader.py
git commit -m "feat: add document ingestion and retriever"
```

---

## Task 8: Implement Deterministic Chains

**Files:**
- Create: `app/chains/extract_chain.py`
- Create: `app/chains/root_cause_chain.py`
- Create: `app/chains/report_chain.py`
- Test: `tests/test_chains.py`

This task creates deterministic chain functions first. Later, LLM-backed versions can be swapped in without changing graph node interfaces.

- [ ] **Step 1: Write failing chain tests**

Create `tests/test_chains.py`:

```python
from app.chains.extract_chain import extract_bug_info
from app.chains.root_cause_chain import generate_root_cause_hypotheses
from app.chains.report_chain import generate_report


def test_extract_bug_info_classifies_dhcp():
    info = extract_bug_info(
        symptom="升级后 DHCP 客户端偶发获取不到 IP",
        logs="dhcpd: lease allocation failed\nnetifd: interface lan reload",
        module_hint=None,
    )

    assert info["bug_type"] == "network_dhcp"
    assert "dhcp" in info["keywords"]


def test_generate_root_cause_hypotheses_for_dhcp():
    hypotheses = generate_root_cause_hypotheses(
        bug_type="network_dhcp",
        parsed_logs={"error_patterns": ["lease allocation failed"], "events": ["interface reload"]},
        related_bugs=[{"bug_id": "BUG-018", "root_cause": "DHCP service starts before bridge interface is ready"}],
        related_code=[{"file": "netifd_reload.c", "snippet": "restart_bridge(); restart_dhcp_server();"}],
    )

    assert hypotheses[0]["title"] == "DHCP 服务启动早于 LAN bridge ready"
    assert hypotheses[0]["confidence"] >= 0.75


def test_generate_report_contains_evidence():
    report = generate_report(
        bug_type="network_dhcp",
        hypotheses=[{"title": "DHCP 服务启动早于 LAN bridge ready", "confidence": 0.82}],
        evidence=["log: dhcpd lease allocation failed", "bug: BUG-018"],
        fix_suggestions=["等待 bridge ready 后再启动 DHCP server"],
    )

    assert "Bug 类型：network_dhcp" in report
    assert "DHCP 服务启动早于 LAN bridge ready" in report
    assert "log: dhcpd lease allocation failed" in report
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_chains.py -v
```

Expected: FAIL because chain modules do not exist.

- [ ] **Step 3: Implement extract chain**

Create `app/chains/extract_chain.py`:

```python
def extract_bug_info(symptom: str, logs: str, module_hint: str | None) -> dict:
    combined = f"{symptom}\n{logs}\n{module_hint or ''}".lower()

    if "dhcp" in combined or "lease allocation failed" in combined:
        return {"bug_type": "network_dhcp", "keywords": ["dhcp", "lease", "netifd", "bridge"]}
    if "pppoe" in combined or "auth failed" in combined:
        return {"bug_type": "network_pppoe", "keywords": ["pppoe", "auth", "wan", "retry"]}
    if "wifi" in combined or "station disconnected" in combined:
        return {"bug_type": "wifi_disconnect", "keywords": ["wifi", "channel", "station", "disconnect"]}
    if "tr069" in combined or "acs" in combined:
        return {"bug_type": "management_tr069", "keywords": ["tr069", "acs", "dns", "inform"]}
    if "upgrade" in combined or "升级" in combined:
        return {"bug_type": "upgrade_regression", "keywords": ["upgrade", "migration", "config"]}

    return {"bug_type": "unknown", "keywords": []}
```

- [ ] **Step 4: Implement root cause chain**

Create `app/chains/root_cause_chain.py`:

```python
def generate_root_cause_hypotheses(
    bug_type: str,
    parsed_logs: dict,
    related_bugs: list[dict],
    related_code: list[dict],
) -> list[dict]:
    if bug_type == "network_dhcp":
        confidence = 0.55
        if "lease allocation failed" in parsed_logs.get("error_patterns", []):
            confidence += 0.15
        if "interface reload" in parsed_logs.get("events", []):
            confidence += 0.10
        if any(bug.get("bug_id") == "BUG-018" for bug in related_bugs):
            confidence += 0.08
        if any("restart_dhcp_server" in code.get("snippet", "") for code in related_code):
            confidence += 0.07

        return [
            {
                "title": "DHCP 服务启动早于 LAN bridge ready",
                "description": "netifd reload 触发 bridge 重建后，DHCP server 在 br-lan forwarding 前启动，导致地址租约分配失败。",
                "confidence": min(round(confidence, 2), 0.95),
            }
        ]

    if bug_type == "network_pppoe":
        return [
            {
                "title": "PPPoE link up 后认证重试定时器未恢复",
                "description": "WAN link flap 后 PPPoE 状态机进入 ready，但 retry timer 未重新启动，导致认证失败后无法继续拨号。",
                "confidence": 0.76,
            }
        ]

    if bug_type == "wifi_disconnect":
        return [
            {
                "title": "信道切换期间过早清理 station table",
                "description": "auto channel switch 开始时清理 station table，客户端在重关联窗口前被断开。",
                "confidence": 0.78,
            }
        ]

    return [
        {
            "title": "需要补充日志和模块信息",
            "description": "当前输入不足以稳定判断根因，需要补充完整 syslog、版本差异和相关模块名。",
            "confidence": 0.35,
        }
    ]
```

- [ ] **Step 5: Implement report chain**

Create `app/chains/report_chain.py`:

```python
def generate_report(
    bug_type: str,
    hypotheses: list[dict],
    evidence: list[str],
    fix_suggestions: list[str],
) -> str:
    lines = [
        f"Bug 类型：{bug_type}",
        "",
        "根因假设：",
    ]

    for index, hypothesis in enumerate(hypotheses, start=1):
        lines.append(f"{index}. {hypothesis['title']}，置信度 {hypothesis['confidence']:.2f}")

    lines.extend(["", "证据链："])
    for index, item in enumerate(evidence, start=1):
        lines.append(f"{index}. {item}")

    lines.extend(["", "修复建议："])
    for index, item in enumerate(fix_suggestions, start=1):
        lines.append(f"{index}. {item}")

    return "\n".join(lines)
```

- [ ] **Step 6: Run chain tests**

Run:

```bash
pytest tests/test_chains.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/chains tests/test_chains.py
git commit -m "feat: add deterministic bug analysis chains"
```

---

## Task 9: Implement LangGraph State and Nodes

**Files:**
- Create: `app/graph/state.py`
- Create: `app/graph/nodes.py`
- Test: `tests/test_graph_nodes.py`

- [ ] **Step 1: Write failing node tests**

Create `tests/test_graph_nodes.py`:

```python
from app.graph.nodes import (
    extract_bug_info_node,
    parse_logs_node,
    search_bug_history_node,
    search_codebase_node,
    generate_hypotheses_node,
    generate_report_node,
)


def test_graph_nodes_produce_report_for_dhcp():
    state = {
        "device_model": "AX3000 Router",
        "firmware_version": "v2.1.8",
        "symptom": "升级后 DHCP 客户端偶发获取不到 IP",
        "logs": "netifd: interface lan reload\ndhcpd: lease allocation failed",
        "stack_trace": None,
        "module_hint": None,
        "extracted_info": {},
        "bug_type": "",
        "related_docs": [],
        "related_bugs": [],
        "related_code": [],
        "parsed_logs": {},
        "hypotheses": [],
        "evidence": [],
        "fix_suggestions": [],
        "final_report": "",
    }

    state.update(extract_bug_info_node(state))
    state.update(parse_logs_node(state))
    state.update(search_bug_history_node(state))
    state.update(search_codebase_node(state))
    state.update(generate_hypotheses_node(state))
    state.update(generate_report_node(state))

    assert state["bug_type"] == "network_dhcp"
    assert state["related_bugs"][0]["bug_id"] == "BUG-018"
    assert "Bug 类型：network_dhcp" in state["final_report"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_graph_nodes.py -v
```

Expected: FAIL because graph modules do not exist.

- [ ] **Step 3: Implement state type**

Create `app/graph/state.py`:

```python
from typing import TypedDict


class BugAnalysisState(TypedDict):
    device_model: str
    firmware_version: str
    symptom: str
    logs: str
    stack_trace: str | None
    module_hint: str | None
    extracted_info: dict
    bug_type: str
    related_docs: list[dict]
    related_bugs: list[dict]
    related_code: list[dict]
    parsed_logs: dict
    hypotheses: list[dict]
    evidence: list[str]
    fix_suggestions: list[str]
    final_report: str
```

- [ ] **Step 4: Implement graph nodes**

Create `app/graph/nodes.py`:

```python
from pathlib import Path

from app.chains.extract_chain import extract_bug_info
from app.chains.report_chain import generate_report
from app.chains.root_cause_chain import generate_root_cause_hypotheses
from app.graph.state import BugAnalysisState
from app.tools.bug_history_search import search_bug_history
from app.tools.code_search import search_codebase
from app.tools.log_parser import parse_syslog


BUG_HISTORY_PATH = Path("data/bugs/bug_history.json")
CODEBASE_DIR = Path("data/codebase")


def extract_bug_info_node(state: BugAnalysisState) -> dict:
    extracted = extract_bug_info(
        symptom=state["symptom"],
        logs=state["logs"],
        module_hint=state["module_hint"],
    )
    return {"extracted_info": extracted, "bug_type": extracted["bug_type"]}


def parse_logs_node(state: BugAnalysisState) -> dict:
    parsed = parse_syslog(state["logs"])
    return {"parsed_logs": parsed}


def search_bug_history_node(state: BugAnalysisState) -> dict:
    query = " ".join(
        [
            state["symptom"],
            " ".join(state["extracted_info"].get("keywords", [])),
            " ".join(state["parsed_logs"].get("error_patterns", [])),
        ]
    )
    return {"related_bugs": search_bug_history(query, BUG_HISTORY_PATH, limit=3)}


def search_codebase_node(state: BugAnalysisState) -> dict:
    query = " ".join(
        [
            state["symptom"],
            " ".join(state["extracted_info"].get("keywords", [])),
            " ".join(state["parsed_logs"].get("events", [])),
        ]
    )
    return {"related_code": search_codebase(query, CODEBASE_DIR, limit=3)}


def generate_hypotheses_node(state: BugAnalysisState) -> dict:
    hypotheses = generate_root_cause_hypotheses(
        bug_type=state["bug_type"],
        parsed_logs=state["parsed_logs"],
        related_bugs=state["related_bugs"],
        related_code=state["related_code"],
    )

    fix_suggestions = []
    if state["bug_type"] == "network_dhcp":
        fix_suggestions = [
            "在 br-lan 进入 forwarding/ready 状态后再启动 DHCP server",
            "为 DHCP server restart 增加 bridge 状态检查和有限重试",
            "补充升级后 LAN DHCP 获取地址回归测试",
        ]
    elif state["bug_type"] == "network_pppoe":
        fix_suggestions = [
            "WAN link up 事件中重新启动 PPPoE retry timer",
            "增加 link flap 后 PPPoE 状态机回归测试",
        ]
    elif state["bug_type"] == "wifi_disconnect":
        fix_suggestions = [
            "延迟 station table 清理直到 channel switch completed",
            "增加自动信道切换期间客户端保持连接测试",
        ]
    else:
        fix_suggestions = ["补充完整日志、版本差异和模块信息后重新分析"]

    return {"hypotheses": hypotheses, "fix_suggestions": fix_suggestions}


def generate_report_node(state: BugAnalysisState) -> dict:
    evidence: list[str] = []
    evidence.extend([f"log: {item}" for item in state["parsed_logs"].get("evidence", [])[:3]])
    evidence.extend([f"bug: {bug['bug_id']} - {bug['root_cause']}" for bug in state["related_bugs"][:2]])
    evidence.extend([f"code: {code['file']}:{code['line']} - {code['snippet']}" for code in state["related_code"][:2]])

    report = generate_report(
        bug_type=state["bug_type"],
        hypotheses=state["hypotheses"],
        evidence=evidence,
        fix_suggestions=state["fix_suggestions"],
    )
    return {"evidence": evidence, "final_report": report}
```

- [ ] **Step 5: Run node tests**

Run:

```bash
pytest tests/test_graph_nodes.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/graph/state.py app/graph/nodes.py tests/test_graph_nodes.py
git commit -m "feat: add bug analysis graph nodes"
```

---

## Task 10: Build LangGraph Workflow

**Files:**
- Create: `app/graph/bug_analysis_graph.py`
- Test: `tests/test_graph_workflow.py`

- [ ] **Step 1: Write failing workflow test**

Create `tests/test_graph_workflow.py`:

```python
from app.graph.bug_analysis_graph import analyze_bug


def test_analyze_bug_workflow_returns_final_report():
    result = analyze_bug(
        device_model="AX3000 Router",
        firmware_version="v2.1.8",
        symptom="升级后 DHCP 客户端偶发获取不到 IP",
        logs="netifd: interface lan reload\ndhcpd: lease allocation failed",
        stack_trace=None,
        module_hint=None,
    )

    assert result["bug_type"] == "network_dhcp"
    assert result["hypotheses"][0]["confidence"] >= 0.75
    assert "修复建议" in result["final_report"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_graph_workflow.py -v
```

Expected: FAIL because workflow module does not exist.

- [ ] **Step 3: Implement workflow**

Create `app/graph/bug_analysis_graph.py`:

```python
from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    extract_bug_info_node,
    generate_hypotheses_node,
    generate_report_node,
    parse_logs_node,
    search_bug_history_node,
    search_codebase_node,
)
from app.graph.state import BugAnalysisState


def build_bug_analysis_graph():
    graph = StateGraph(BugAnalysisState)

    graph.add_node("extract_bug_info", extract_bug_info_node)
    graph.add_node("parse_logs", parse_logs_node)
    graph.add_node("search_bug_history", search_bug_history_node)
    graph.add_node("search_codebase", search_codebase_node)
    graph.add_node("generate_hypotheses", generate_hypotheses_node)
    graph.add_node("generate_report", generate_report_node)

    graph.set_entry_point("extract_bug_info")
    graph.add_edge("extract_bug_info", "parse_logs")
    graph.add_edge("parse_logs", "search_bug_history")
    graph.add_edge("search_bug_history", "search_codebase")
    graph.add_edge("search_codebase", "generate_hypotheses")
    graph.add_edge("generate_hypotheses", "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile()


def analyze_bug(
    device_model: str,
    firmware_version: str,
    symptom: str,
    logs: str,
    stack_trace: str | None,
    module_hint: str | None,
) -> BugAnalysisState:
    app = build_bug_analysis_graph()
    initial_state: BugAnalysisState = {
        "device_model": device_model,
        "firmware_version": firmware_version,
        "symptom": symptom,
        "logs": logs,
        "stack_trace": stack_trace,
        "module_hint": module_hint,
        "extracted_info": {},
        "bug_type": "",
        "related_docs": [],
        "related_bugs": [],
        "related_code": [],
        "parsed_logs": {},
        "hypotheses": [],
        "evidence": [],
        "fix_suggestions": [],
        "final_report": "",
    }
    return app.invoke(initial_state)
```

- [ ] **Step 4: Run workflow test**

Run:

```bash
pytest tests/test_graph_workflow.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/graph/bug_analysis_graph.py tests/test_graph_workflow.py
git commit -m "feat: build LangGraph bug analysis workflow"
```

---

## Task 11: Add FastAPI Endpoint

**Files:**
- Create: `app/main.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing API test**

Create `tests/test_api.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_analyze_endpoint_returns_bug_report():
    client = TestClient(app)
    response = client.post(
        "/analyze",
        json={
            "device_model": "AX3000 Router",
            "firmware_version": "v2.1.8",
            "symptom": "升级后 DHCP 客户端偶发获取不到 IP",
            "logs": "netifd: interface lan reload\ndhcpd: lease allocation failed",
            "stack_trace": None,
            "module_hint": None,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["bug_type"] == "network_dhcp"
    assert "DHCP" in data["summary"]
    assert data["confidence"] >= 0.75
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_api.py -v
```

Expected: FAIL because `app.main` does not exist.

- [ ] **Step 3: Implement API**

Create `app/main.py`:

```python
from fastapi import FastAPI

from app.graph.bug_analysis_graph import analyze_bug
from app.schemas.bug import BugAnalyzeRequest, BugAnalyzeResponse


app = FastAPI(title="Embedded Bug Analysis Agent")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze", response_model=BugAnalyzeResponse)
def analyze(request: BugAnalyzeRequest) -> BugAnalyzeResponse:
    result = analyze_bug(
        device_model=request.device_model,
        firmware_version=request.firmware_version,
        symptom=request.symptom,
        logs=request.logs,
        stack_trace=request.stack_trace,
        module_hint=request.module_hint,
    )
    top_hypothesis = result["hypotheses"][0]

    return BugAnalyzeResponse(
        bug_type=result["bug_type"],
        summary=top_hypothesis["title"],
        root_causes=[item["description"] for item in result["hypotheses"]],
        evidence=result["evidence"],
        fix_suggestions=result["fix_suggestions"],
        confidence=top_hypothesis["confidence"],
    )
```

- [ ] **Step 4: Run API test**

Run:

```bash
pytest tests/test_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Run local API smoke test**

Run:

```bash
uvicorn app.main:app --reload
```

In another shell:

```bash
curl -s http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_api.py
git commit -m "feat: expose bug analysis API"
```

---

## Task 12: Add Streamlit Demo UI

**Files:**
- Create: `ui/streamlit_app.py`
- Modify: `README.md`

- [ ] **Step 1: Create Streamlit app**

Create `ui/streamlit_app.py`:

```python
import requests
import streamlit as st


DEFAULT_LOGS = """2026-06-25 14:03:11 netifd: interface lan reload
2026-06-25 14:03:12 kernel: br-lan port state changed to blocking
2026-06-25 14:03:12 dhcpd: lease allocation failed
2026-06-25 14:03:14 kernel: br-lan port state changed to forwarding"""


st.set_page_config(page_title="嵌入式网通 Bug 分析 Agent", layout="wide")
st.title("嵌入式网通设备 Bug 分析 Agent")

left, right = st.columns([1, 1])

with left:
    device_model = st.text_input("设备型号", value="AX3000 Router")
    firmware_version = st.text_input("固件版本", value="v2.1.8")
    symptom = st.text_area("问题现象", value="升级后 DHCP 客户端偶发获取不到 IP", height=100)
    logs = st.text_area("设备日志", value=DEFAULT_LOGS, height=220)
    module_hint = st.text_input("模块提示", value="")
    submitted = st.button("分析 Bug")

with right:
    st.subheader("分析结果")
    if submitted:
        payload = {
            "device_model": device_model,
            "firmware_version": firmware_version,
            "symptom": symptom,
            "logs": logs,
            "stack_trace": None,
            "module_hint": module_hint or None,
        }
        response = requests.post("http://127.0.0.1:8000/analyze", json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        st.metric("Bug 类型", data["bug_type"])
        st.metric("置信度", f"{data['confidence']:.2f}")
        st.markdown("### 根因摘要")
        st.write(data["summary"])
        st.markdown("### 证据链")
        for item in data["evidence"]:
            st.write(f"- {item}")
        st.markdown("### 修复建议")
        for item in data["fix_suggestions"]:
            st.write(f"- {item}")
```

- [ ] **Step 2: Update README run instructions**

Modify `README.md` to include:

```markdown
## API Demo

```bash
uvicorn app.main:app --reload
```

Open API docs:

```text
http://127.0.0.1:8000/docs
```

## Streamlit Demo

Start API first, then run:

```bash
streamlit run ui/streamlit_app.py
```
```

- [ ] **Step 3: Run UI smoke test**

Run:

```bash
streamlit run ui/streamlit_app.py
```

Expected: Streamlit starts and prints a local URL.

- [ ] **Step 4: Commit**

```bash
git add ui/streamlit_app.py README.md
git commit -m "feat: add Streamlit demo UI"
```

---

## Task 13: Add Evaluation Script

**Files:**
- Create: `tests/test_eval_dataset.py`
- Create: `data/bugs/eval_cases.json`
- Create: `scripts/evaluate.py`

- [ ] **Step 1: Create evaluation cases**

Create `data/bugs/eval_cases.json`:

```json
[
  {
    "case_id": "EVAL-001",
    "device_model": "AX3000 Router",
    "firmware_version": "v2.1.8",
    "symptom": "升级后 DHCP 客户端偶发获取不到 IP",
    "logs": "netifd: interface lan reload\ndhcpd: lease allocation failed",
    "expected_bug_type": "network_dhcp"
  },
  {
    "case_id": "EVAL-002",
    "device_model": "GPON ONU",
    "firmware_version": "v1.9.3",
    "symptom": "WAN 断开恢复后 PPPoE 无法重新拨号",
    "logs": "netifd: wan link up\npppoe: auth failed\npppoe: retry timer stopped",
    "expected_bug_type": "network_pppoe"
  },
  {
    "case_id": "EVAL-003",
    "device_model": "Home Gateway",
    "firmware_version": "v3.0.1",
    "symptom": "自动信道切换时 Wi-Fi 客户端掉线",
    "logs": "wifi: channel switch started\nwifi: station disconnected\nwifi: channel switch completed",
    "expected_bug_type": "wifi_disconnect"
  }
]
```

- [ ] **Step 2: Write evaluation dataset test**

Create `tests/test_eval_dataset.py`:

```python
import json
from pathlib import Path


def test_eval_cases_have_required_fields():
    cases = json.loads(Path("data/bugs/eval_cases.json").read_text(encoding="utf-8"))

    assert len(cases) == 3
    for case in cases:
        assert case["case_id"]
        assert case["device_model"]
        assert case["firmware_version"]
        assert case["symptom"]
        assert case["logs"]
        assert case["expected_bug_type"]
```

- [ ] **Step 3: Create evaluation script**

Create `scripts/evaluate.py`:

```python
import json
from pathlib import Path

from app.graph.bug_analysis_graph import analyze_bug


def main() -> None:
    cases = json.loads(Path("data/bugs/eval_cases.json").read_text(encoding="utf-8"))
    correct = 0

    for case in cases:
        result = analyze_bug(
            device_model=case["device_model"],
            firmware_version=case["firmware_version"],
            symptom=case["symptom"],
            logs=case["logs"],
            stack_trace=None,
            module_hint=None,
        )
        predicted = result["bug_type"]
        expected = case["expected_bug_type"]
        passed = predicted == expected
        correct += int(passed)
        print(f"{case['case_id']}: predicted={predicted}, expected={expected}, passed={passed}")

    accuracy = correct / len(cases)
    print(f"classification_accuracy={accuracy:.2f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run evaluation tests**

Run:

```bash
pytest tests/test_eval_dataset.py -v
```

Expected: PASS.

- [ ] **Step 5: Run evaluation script**

Run:

```bash
python scripts/evaluate.py
```

Expected:

```text
EVAL-001: predicted=network_dhcp, expected=network_dhcp, passed=True
EVAL-002: predicted=network_pppoe, expected=network_pppoe, passed=True
EVAL-003: predicted=wifi_disconnect, expected=wifi_disconnect, passed=True
classification_accuracy=1.00
```

- [ ] **Step 6: Commit**

```bash
git add data/bugs/eval_cases.json scripts/evaluate.py tests/test_eval_dataset.py
git commit -m "feat: add evaluation dataset and script"
```

---

## Task 14: Final Verification and Resume Material

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run complete test suite**

Run:

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Run evaluation**

Run:

```bash
python scripts/evaluate.py
```

Expected: `classification_accuracy=1.00`.

- [ ] **Step 3: Update README with project highlights**

Append to `README.md`:

```markdown
## 简历项目描述

**项目名：** 基于 LangChain/LangGraph 的嵌入式网通设备 Bug 分析 Agent

**项目描述：** 面向路由器、光猫等嵌入式网通设备的软件缺陷分析场景，构建 Bug 分析 Agent。系统支持输入缺陷描述、设备日志和版本信息，自动检索历史缺陷、模块文档和模拟 C 代码，输出根因假设、证据链、影响范围和修复建议。

**技术亮点：**

- 使用 LangGraph 编排 Bug 信息抽取、日志解析、历史缺陷检索、代码检索、根因假设生成和报告输出状态流
- 使用 LangChain 组织 RAG 检索和工具调用接口
- 构建 DHCP、PPPoE、Wi-Fi、TR-069、升级回归等网通设备样例数据
- 输出带证据链的结构化 Bug 分析报告，降低无依据模型回答风险

**可量化结果：**

- 构建 3 条首版评估样例，覆盖 DHCP、PPPoE、Wi-Fi 三类高频问题
- 首版规则链路分类准确率达到 100%，后续可扩展到 20+ 样例做稳定性评估
```

- [ ] **Step 4: Commit final docs**

```bash
git add README.md
git commit -m "docs: add resume-ready project summary"
```

---

## Future Enhancements

These are intentionally outside the first implementation:

- 接入真实 LLM，让 `extract_chain`、`root_cause_chain`、`report_chain` 使用 ChatOpenAI。
- 接入 LangSmith，展示每次 Bug 分析的 trace。
- 增加 Git commit 检索工具，分析版本回归。
- 增加 crash dump parser，支持段错误调用栈分析。
- 增加 human-in-the-loop 节点，在 Agent 输出高风险修复动作前请求确认。
- 将 evaluation 数据扩展到 20 条以上。

---

## Execution Handoff

Plan complete. Recommended execution mode:

1. **Subagent-Driven (recommended)** - 每个任务使用独立上下文执行，任务完成后 review，再进入下一项。
2. **Inline Execution** - 在当前会话按任务顺序执行，每个阶段跑测试并提交。

If implementing manually, follow task order exactly. The first runnable milestone is Task 10, where LangGraph workflow can produce a complete DHCP Bug analysis report from local data.
