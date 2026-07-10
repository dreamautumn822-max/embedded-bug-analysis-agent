import os
from html import escape

import requests
import streamlit as st


API_URL = os.getenv("BUG_AGENT_API_URL", "http://127.0.0.1:8000/analyze")

DEFAULT_LOGS = """2026-06-25 09:12:03 netifd: Interface 'lan' is now down
2026-06-25 09:12:04 netifd: bridge 'br-lan' reload triggered by firmware upgrade
2026-06-25 09:12:05 dhcpd: DHCPDISCOVER from 48:2c:a0:11:22:33 via br-lan
2026-06-25 09:12:05 dhcpd: lease allocation failed: bridge br-lan not ready
2026-06-25 09:12:07 netifd: Interface 'lan' is now up
2026-06-25 09:12:09 dhcpd: no free leases for subnet 192.168.1.0/24"""

PAGE_CSS = """
<style>
:root {
  --console-shell: #182022;
  --panel-metal: #263033;
  --work-surface: #f2f5f1;
  --signal-green: #6da36f;
  --trace-amber: #d6b45a;
  --fault-coral: #c76e5a;
  --bus-blue: #7aa8a8;
  --ink: #1d2629;
  --muted: #6a7779;
}

.stApp {
  background:
    linear-gradient(90deg, rgba(24, 32, 34, .04) 1px, transparent 1px),
    linear-gradient(180deg, rgba(24, 32, 34, .04) 1px, transparent 1px),
    var(--work-surface);
  background-size: 28px 28px;
  color: var(--ink);
}

.block-container {
  max-width: 1320px;
  padding-top: 2.1rem;
  padding-bottom: 3rem;
}

h1, h2, h3, label {
  letter-spacing: 0;
}

div[data-testid="stForm"] {
  background: rgba(255, 255, 255, .78);
  border: 1px solid rgba(38, 48, 51, .16);
  border-left: 6px solid var(--signal-green);
  border-radius: 8px;
  padding: 1rem 1rem 1.1rem;
  box-shadow: 0 18px 40px rgba(24, 32, 34, .09);
}

div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
  border-radius: 6px;
  border: 1px solid rgba(38, 48, 51, .22);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color: var(--ink);
}

div[data-testid="stTextArea"] textarea {
  line-height: 1.45;
}

.stButton > button {
  border-radius: 6px;
  border: 1px solid #466e48;
  background: var(--signal-green);
  color: #fff;
  font-weight: 750;
  min-height: 2.7rem;
}

.stButton > button:hover {
  border-color: #315533;
  background: #5c935f;
  color: #fff;
}

.console-hero {
  background: var(--console-shell);
  color: #eaf2e2;
  border-radius: 8px;
  border: 1px solid rgba(109, 163, 111, .45);
  box-shadow: 0 22px 50px rgba(24, 32, 34, .22);
  padding: 1.45rem 1.55rem;
  margin-bottom: 1.25rem;
  position: relative;
  overflow: hidden;
}

.console-hero:before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, rgba(122, 168, 168, .14) 1px, transparent 1px),
    linear-gradient(180deg, rgba(122, 168, 168, .09) 1px, transparent 1px);
  background-size: 36px 36px;
  pointer-events: none;
}

.console-hero > * {
  position: relative;
}

.console-kicker,
.status-label,
.evidence-label,
.field-note {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  letter-spacing: .02em;
}

.console-kicker {
  color: #9ab2a0;
  font-size: .78rem;
  text-transform: uppercase;
  margin-bottom: .55rem;
}

.console-title {
  font-size: clamp(2rem, 4vw, 4.4rem);
  line-height: .98;
  font-weight: 900;
  max-width: 760px;
  margin: 0;
}

.console-copy {
  max-width: 760px;
  margin-top: .85rem;
  color: #cfd9cf;
  font-size: 1rem;
  line-height: 1.65;
}

.status-rail {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: .65rem;
  margin-top: 1.2rem;
}

.status-cell,
.result-card,
.empty-board {
  border-radius: 8px;
  border: 1px solid rgba(38, 48, 51, .15);
  background: rgba(255, 255, 255, .82);
}

.status-cell {
  background: rgba(38, 48, 51, .9);
  color: #e9f1e6;
  padding: .72rem .82rem;
  border-color: rgba(122, 168, 168, .28);
}

.status-label {
  color: #9ab2a0;
  font-size: .68rem;
  text-transform: uppercase;
}

.status-value {
  margin-top: .22rem;
  font-size: .88rem;
  overflow-wrap: anywhere;
}

.section-title {
  display: flex;
  align-items: center;
  gap: .55rem;
  color: var(--ink);
  margin: .2rem 0 .85rem;
}

.section-title:before {
  content: "";
  width: .72rem;
  height: .72rem;
  background: var(--trace-amber);
  border: 2px solid var(--console-shell);
  box-shadow: 4px 4px 0 var(--bus-blue);
}

.field-note {
  color: var(--muted);
  font-size: .74rem;
  margin: -.35rem 0 .7rem;
}

.result-card,
.empty-board {
  padding: 1rem 1.05rem;
  box-shadow: 0 18px 40px rgba(24, 32, 34, .08);
}

.diagnosis-head {
  display: grid;
  grid-template-columns: 150px 1fr;
  gap: .85rem;
  align-items: stretch;
}

.confidence-dial {
  background: var(--console-shell);
  color: #eaf2e2;
  border-radius: 8px;
  padding: .95rem;
  border: 1px solid rgba(109, 163, 111, .5);
}

.confidence-number {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color: var(--trace-amber);
  font-size: 2.25rem;
  font-weight: 900;
  line-height: 1;
}

.bug-chip {
  display: inline-block;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: rgba(199, 110, 90, .16);
  color: #8c3f30;
  border: 1px solid rgba(199, 110, 90, .34);
  border-radius: 999px;
  padding: .24rem .55rem;
  font-size: .76rem;
  margin-bottom: .65rem;
}

.summary-title {
  font-size: 1.24rem;
  font-weight: 850;
  line-height: 1.35;
}

.evidence-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: .75rem;
  margin-top: .85rem;
}

.evidence-card {
  border-radius: 8px;
  border: 1px solid rgba(38, 48, 51, .14);
  background: #fff;
  overflow: hidden;
}

.evidence-label {
  padding: .48rem .65rem;
  color: #122022;
  font-size: .7rem;
  font-weight: 850;
}

.evidence-card.log .evidence-label { background: rgba(214, 180, 90, .7); }
.evidence-card.doc .evidence-label { background: rgba(122, 168, 168, .6); }
.evidence-card.bug .evidence-label { background: rgba(199, 110, 90, .55); }
.evidence-card.code .evidence-label { background: rgba(109, 163, 111, .58); }
.evidence-card.other .evidence-label { background: rgba(38, 48, 51, .18); }

.evidence-item {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: .78rem;
  line-height: 1.48;
  padding: .62rem .65rem;
  border-top: 1px solid rgba(38, 48, 51, .09);
  overflow-wrap: anywhere;
}

.code-fold {
  border-top: 1px solid rgba(38, 48, 51, .09);
}

.code-fold summary {
  cursor: pointer;
  list-style: none;
  padding: .68rem .65rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: .78rem;
  font-weight: 850;
  color: #1e3b2b;
  background: rgba(109, 163, 111, .09);
}

.code-fold summary::-webkit-details-marker {
  display: none;
}

.code-fold summary:before {
  content: "+";
  display: inline-flex;
  width: 1.1rem;
  height: 1.1rem;
  align-items: center;
  justify-content: center;
  margin-right: .45rem;
  border-radius: 4px;
  background: var(--signal-green);
  color: #fff;
}

.code-fold[open] summary:before {
  content: "-";
}

.code-line {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: .76rem;
  line-height: 1.48;
  padding: .62rem .65rem;
  border-top: 1px dashed rgba(38, 48, 51, .16);
  background: #fff;
  overflow-wrap: anywhere;
}

.fix-list {
  display: grid;
  gap: .55rem;
  margin-top: .75rem;
}

.fix-item {
  border-left: 4px solid var(--signal-green);
  background: rgba(109, 163, 111, .1);
  border-radius: 6px;
  padding: .68rem .8rem;
  line-height: 1.55;
}

.empty-board {
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  background:
    linear-gradient(90deg, rgba(38, 48, 51, .06) 1px, transparent 1px),
    linear-gradient(180deg, rgba(38, 48, 51, .06) 1px, transparent 1px),
    rgba(255, 255, 255, .78);
  background-size: 28px 28px;
}

.empty-board strong {
  display: block;
  font-size: 1.3rem;
  margin-bottom: .45rem;
}

@media (max-width: 900px) {
  .status-rail,
  .diagnosis-head,
  .evidence-grid {
    grid-template-columns: 1fr;
  }
}
</style>
"""


def _optional_text(value: str) -> str | None:
    value = value.strip()
    return value or None


def api_timeout_seconds() -> int:
    return int(os.getenv("BUG_AGENT_API_TIMEOUT_SECONDS", "90"))


def build_payload(
    *,
    device_model: str,
    firmware_version: str,
    symptom: str,
    logs: str,
    stack_trace: str,
    module_hint: str,
) -> dict[str, str | None]:
    return {
        "device_model": device_model.strip(),
        "firmware_version": firmware_version.strip(),
        "symptom": symptom.strip(),
        "logs": logs.strip(),
        "stack_trace": _optional_text(stack_trace),
        "module_hint": _optional_text(module_hint),
    }


def group_evidence(evidence: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {
        "logs": [],
        "docs": [],
        "bugs": [],
        "code": [],
        "other": [],
    }
    prefixes = {
        "log: ": "logs",
        "doc: ": "docs",
        "bug: ": "bugs",
        "code: ": "code",
    }

    for item in evidence:
        for prefix, group in prefixes.items():
            if item.startswith(prefix):
                grouped[group].append(item.removeprefix(prefix))
                break
        else:
            grouped["other"].append(item)

    return grouped


def render_html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def render_header() -> None:
    render_html(
        f"""
        <div class="console-hero">
          <div class="console-kicker">embedded network bug analysis console</div>
          <h1 class="console-title">故障现场到根因证据链</h1>
          <div class="console-copy">
            输入设备型号、固件版本、问题现象和现场日志，Agent 会把日志、模块文档、历史 Bug 和代码片段串成一份可复查的分析报告。
          </div>
          <div class="status-rail">
            <div class="status-cell">
              <div class="status-label">api endpoint</div>
              <div class="status-value">{escape(API_URL)}</div>
            </div>
            <div class="status-cell">
              <div class="status-label">target</div>
              <div class="status-value">Router / ONU / Gateway</div>
            </div>
            <div class="status-cell">
              <div class="status-label">analysis path</div>
              <div class="status-value">Log -> RAG -> Hypothesis</div>
            </div>
            <div class="status-cell">
              <div class="status-label">default module</div>
              <div class="status-value">network_dhcp</div>
            </div>
          </div>
        </div>
        """
    )


def render_result(result: dict) -> None:
    confidence = float(result.get("confidence", 0) or 0)
    confidence_percent = round(confidence * 100)
    bug_type = escape(str(result.get("bug_type", "-")))
    summary = escape(str(result.get("summary", "-")))
    root_causes = [escape(str(item)) for item in result.get("root_causes", [])]
    fix_suggestions = [escape(str(item)) for item in result.get("fix_suggestions", [])]
    grouped_evidence = group_evidence([str(item) for item in result.get("evidence", [])])

    root_cause_markup = "".join(
        f'<div class="fix-item">{item}</div>' for item in root_causes
    ) or '<div class="fix-item">未返回根因描述。</div>'

    render_html(
        f"""
        <div class="section-title"><h3>根因诊断板</h3></div>
        <div class="result-card">
          <div class="diagnosis-head">
            <div class="confidence-dial">
              <div class="status-label">confidence</div>
              <div class="confidence-number">{confidence_percent}%</div>
            </div>
            <div>
              <div class="bug-chip">{bug_type}</div>
              <div class="summary-title">{summary}</div>
            </div>
          </div>
          <div class="fix-list">{root_cause_markup}</div>
        </div>
        """
    )

    st.markdown("")
    render_html('<div class="section-title"><h3>证据总线</h3></div>')
    render_evidence_grid(grouped_evidence)

    st.markdown("")
    render_html('<div class="section-title"><h3>修复动作</h3></div>')
    fix_markup = "".join(
        f'<div class="fix-item">{item}</div>' for item in fix_suggestions
    ) or '<div class="fix-item">未返回修复建议。</div>'
    render_html(f'<div class="result-card"><div class="fix-list">{fix_markup}</div></div>')


def render_evidence_grid(grouped_evidence: dict[str, list[str]]) -> None:
    render_html(build_evidence_grid_html(grouped_evidence))


def build_evidence_grid_html(grouped_evidence: dict[str, list[str]]) -> str:
    labels = {
        "logs": ("log", "LOG / 现场日志"),
        "docs": ("doc", "DOC / 模块文档"),
        "bugs": ("bug", "BUG / 历史缺陷"),
        "code": ("code", "CODE / 代码线索"),
        "other": ("other", "OTHER / 其他证据"),
    }
    cards = []

    for key, items in grouped_evidence.items():
        if not items:
            continue
        card_class, label = labels[key]
        if key == "code" and len(items) > 1:
            code_lines = "".join(
                f'<div class="code-line">{escape(str(item))}</div>' for item in items
            )
            body = (
                '<details class="code-fold">'
                f"<summary>{len(items)} 条代码线索</summary>"
                f"{code_lines}"
                "</details>"
            )
        else:
            body = "".join(
                f'<div class="evidence-item">{escape(str(item))}</div>' for item in items
            )
        cards.append(
            f'<div class="evidence-card {card_class}">'
            f'<div class="evidence-label">{label}</div>'
            f"{body}"
            "</div>"
        )

    if not cards:
        cards.append(
            '<div class="evidence-card other">'
            '<div class="evidence-label">EMPTY</div>'
            '<div class="evidence-item">未返回证据。</div>'
            "</div>"
        )

    return f'<div class="evidence-grid">{"".join(cards)}</div>'


def render_empty_board() -> None:
    render_html(
        """
        <div class="section-title"><h3>根因诊断板</h3></div>
        <div class="empty-board">
          <div>
            <strong>等待一组故障现场</strong>
            <div class="field-note">填写左侧信息后点击“分析 Bug”，这里会生成根因、证据和修复动作。</div>
          </div>
        </div>
        """
    )


def main() -> None:
    st.set_page_config(
        page_title="嵌入式网通设备 Bug 分析 Agent",
        layout="wide",
    )
    render_html(PAGE_CSS)
    render_header()

    left, right = st.columns([0.92, 1.28], gap="large")

    with left:
        render_html('<div class="section-title"><h3>故障现场输入</h3></div>')
        render_html('<div class="field-note">字段保持贴近真实工单：设备、版本、现象、日志、可选堆栈和模块提示。</div>')

        with st.form("bug_analysis_form"):
            device_model = st.text_input("设备型号", value="AX3000-GW")
            firmware_version = st.text_input("固件版本", value="v2.1.7")
            symptom = st.text_area(
                "问题现象",
                value="固件升级后，LAN 侧客户端偶发无法通过 DHCP 获取 IP，需要重启网关才能恢复。",
                height=110,
            )
            logs = st.text_area("现场日志", value=DEFAULT_LOGS, height=265)
            stack_trace = st.text_area("堆栈信息（可选）", value="", height=95)
            module_hint = st.text_input("模块提示（可选）", value="network_dhcp")
            submitted = st.form_submit_button("分析 Bug", type="primary", use_container_width=True)

    if submitted:
        payload = build_payload(
            device_model=device_model,
            firmware_version=firmware_version,
            symptom=symptom,
            logs=logs,
            stack_trace=stack_trace,
            module_hint=module_hint,
        )

        try:
            with st.spinner("正在分析日志、检索历史 Bug 和模块文档..."):
                response = requests.post(API_URL, json=payload, timeout=api_timeout_seconds())
                response.raise_for_status()
                st.session_state["analysis_result"] = response.json()
        except requests.RequestException as exc:
            st.session_state.pop("analysis_result", None)
            st.error(f"调用分析 API 失败：{exc}")

    with right:
        result = st.session_state.get("analysis_result")
        if result:
            render_result(result)
        else:
            render_empty_board()


if __name__ == "__main__":
    main()
