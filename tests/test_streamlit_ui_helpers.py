from ui.streamlit_app import (
    api_timeout_seconds,
    build_evidence_grid_html,
    build_payload,
    group_evidence,
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
