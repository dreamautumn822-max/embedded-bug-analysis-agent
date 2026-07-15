from ui.streamlit_app import (
    api_base_url,
    api_headers,
    api_timeout_seconds,
    build_evidence_grid_html,
    build_payload,
    group_evidence,
    group_evidence_details,
    render_result,
)


def test_build_payload_keeps_required_fields_and_normalizes_optional_fields():
    payload = build_payload(
        device_model="AX3000-GW",
        firmware_version="v2.1.7",
        symptom="DHCP clients cannot get IP",
        logs="dhcpd: lease allocation failed",
        stack_trace="",
        module_hint=" network_dhcp ",
    )

    assert payload == {
        "device_model": "AX3000-GW",
        "firmware_version": "v2.1.7",
        "symptom": "DHCP clients cannot get IP",
        "logs": "dhcpd: lease allocation failed",
        "stack_trace": None,
        "module_hint": "network_dhcp",
    }


def test_api_timeout_defaults_to_llm_friendly_value(monkeypatch):
    monkeypatch.delenv("BUG_AGENT_API_TIMEOUT_SECONDS", raising=False)

    assert api_timeout_seconds() == 90


def test_api_timeout_can_be_configured(monkeypatch):
    monkeypatch.setenv("BUG_AGENT_API_TIMEOUT_SECONDS", "120")

    assert api_timeout_seconds() == 120


def test_api_base_url_is_derived_from_analyze_endpoint(monkeypatch):
    monkeypatch.delenv("BUG_AGENT_API_BASE_URL", raising=False)

    assert api_base_url() == "http://127.0.0.1:8000"


def test_api_base_url_can_be_configured(monkeypatch):
    monkeypatch.setenv("BUG_AGENT_API_BASE_URL", "http://api:9000/")

    assert api_base_url() == "http://api:9000"


def test_api_headers_only_include_configured_key(monkeypatch):
    monkeypatch.delenv("BUG_AGENT_API_KEY", raising=False)
    assert api_headers() == {}

    monkeypatch.setenv("BUG_AGENT_API_KEY", "secret-key")
    assert api_headers() == {"X-API-Key": "secret-key"}


def test_group_evidence_splits_agent_sources():
    grouped = group_evidence(
        [
            "log: dhcpd: lease allocation failed",
            "doc: dhcp.md - bridge readiness",
            "bug: BUG-018 - DHCP starts too early",
            "code: netifd_reload.c: restart_dhcp_server",
            "manual triage note",
        ]
    )

    assert grouped["logs"] == ["dhcpd: lease allocation failed"]
    assert grouped["docs"] == ["dhcp.md - bridge readiness"]
    assert grouped["bugs"] == ["BUG-018 - DHCP starts too early"]
    assert grouped["code"] == ["netifd_reload.c: restart_dhcp_server"]
    assert grouped["other"] == ["manual triage note"]


def test_group_evidence_details_uses_structured_metadata():
    grouped = group_evidence_details(
        [
            {
                "evidence_type": "doc",
                "source": "dhcp.md",
                "section": "启动依赖与时序",
                "score": 0.307,
                "retrieval_method": "hybrid_rrf_rerank",
                "rerank_method": "local_feature",
                "content": "DHCP server 必须等待 bridge ready。",
            },
            {
                "evidence_type": "code",
                "source": "netifd_reload.c:3",
                "content": "restart_bridge before restart_dhcp_server",
            },
        ]
    )

    assert grouped["docs"] == [
        "dhcp.md / 启动依赖与时序 / 重排分 0.307 / "
        "向量+BM25+RRF+本地特征重排 - "
        "DHCP server 必须等待 bridge ready。"
    ]
    assert grouped["code"] == [
        "netifd_reload.c:3 - restart_bridge before restart_dhcp_server"
    ]


def test_structured_document_without_reranker_uses_relevance_label():
    grouped = group_evidence_details(
        [
            {
                "evidence_type": "doc",
                "source": "dhcp.md",
                "score": 0.42,
                "content": "DHCP evidence",
            }
        ]
    )

    assert grouped["docs"] == ["dhcp.md / 相关度 0.420 - DHCP evidence"]


def test_code_evidence_includes_ast_symbol_when_available():
    grouped = group_evidence_details(
        [
            {
                "evidence_type": "code",
                "source": "netifd_reload.c:3",
                "symbol": "lan_reload_handler",
                "content": "restart_dhcp_server();",
            }
        ]
    )

    assert grouped["code"] == [
        "netifd_reload.c:3 / lan_reload_handler - restart_dhcp_server();"
    ]


def test_code_evidence_includes_commit_and_call_graph_metadata():
    grouped = group_evidence_details(
        [
            {
                "evidence_type": "code",
                "source": "git/abc123:1",
                "symbol": "commit:abc123",
                "code_kind": "commit_diff",
                "commit_sha": "abc1234567890",
                "commit_subject": "fix DHCP restart ordering",
                "content": "+restart_dhcp_server();",
            },
            {
                "evidence_type": "code",
                "source": "dhcp.c:3",
                "symbol": "restart_dhcp",
                "callers": ["lan_reload_handler"],
                "calls": ["bridge_wait_ready"],
                "content": "restart_dhcp();",
            },
        ]
    )

    assert "提交 abc123456789" in grouped["code"][0]
    assert "fix DHCP restart ordering" in grouped["code"][0]
    assert "上游 lan_reload_handler" in grouped["code"][1]
    assert "调用 bridge_wait_ready" in grouped["code"][1]


def test_code_evidence_renders_as_one_collapsible_card():
    html = build_evidence_grid_html(
        {
            "logs": [],
            "docs": [],
            "bugs": [],
            "code": [
                "netifd_reload.c:3 - restart_bridge then restart_dhcp_server",
                "dhcp_server.c:1 - migration keys",
            ],
            "other": [],
        }
    )

    assert html.count('class="evidence-card code"') == 1
    assert "<details" in html
    assert "2 条代码线索" in html
    assert "netifd_reload.c:3" in html
    assert "dhcp_server.c:1" in html


def test_evidence_grid_html_does_not_emit_markdown_indented_blocks():
    html = build_evidence_grid_html(
        {
            "logs": ["dhcpd: lease allocation failed"],
            "docs": ["dhcp.md - # DHCP 模块说明"],
            "bugs": ["BUG-018 - DHCP starts before bridge ready"],
            "code": [
                'dhcp_server.c:3 - #include "dhcp_server.h"',
                "netifd_reload.c:5 - restart_dhcp_server();",
            ],
            "other": [],
        }
    )

    assert not any(
        line.startswith("    ") and line.lstrip().startswith("<")
        for line in html.splitlines()
    )
    assert html.startswith('<div class="evidence-grid">')


def test_result_html_keeps_closing_tags_inside_raw_html_block(monkeypatch):
    rendered = []
    monkeypatch.setattr("ui.streamlit_app.render_html", rendered.append)
    monkeypatch.setattr("ui.streamlit_app.render_evidence_grid", lambda grouped: None)
    monkeypatch.setattr("ui.streamlit_app.st.markdown", lambda value: None)

    render_result(
        {
            "bug_type": "network_dhcp",
            "summary": "DHCP 启动时序异常",
            "root_causes": ["DHCP 启动早于网桥就绪"],
            "fix_suggestions": [],
            "confidence": 0.85,
            "generation_mode": "rule",
            "review_required": False,
            "trace_events": [],
            "evidence": [],
        }
    )

    diagnosis = rendered[0]
    assert '<div class="field-note" hidden></div>' in diagnosis
    assert '<div class="summary-title">DHCP 启动时序异常</div><div' in diagnosis
