from app.graph.nodes import generate_hypotheses_node
from app.llm.schemas import LLMHypothesis, LLMRootCauseResult


def _state():
    return {
        "device_model": "AX3000 Router",
        "firmware_version": "v2.1.8",
        "symptom": "升级后 DHCP 客户端偶发获取不到 IP",
        "logs": "dhcpd: lease allocation failed",
        "stack_trace": None,
        "module_hint": "network_dhcp",
        "extracted_info": {"keywords": ["dhcp"]},
        "bug_type": "network_dhcp",
        "parsed_logs": {
            "error_patterns": ["lease allocation failed"],
            "events": ["interface reload"],
            "evidence": ["dhcpd: lease allocation failed"],
        },
        "related_bugs": [{"bug_id": "BUG-018", "root_cause": "DHCP starts too early"}],
        "related_docs": [{"source": "dhcp.md", "snippet": "# DHCP 模块说明"}],
        "related_code": [{"file": "netifd_reload.c", "line": 3, "snippet": "restart_dhcp_server();"}],
        "hypotheses": [],
        "evidence": [],
        "fix_suggestions": [],
        "final_report": "",
    }


def test_generate_hypotheses_node_uses_llm_when_ready(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")

    def fake_generate_root_cause_with_llm(**kwargs):
        return LLMRootCauseResult(
            hypotheses=[
                LLMHypothesis(
                    title="LLM 判断 DHCP 与 bridge ready 时序异常",
                    description="LLM 基于日志和 BUG-018 判断 DHCP 启动过早。",
                    confidence=0.88,
                )
            ],
            fix_suggestions=["LLM 建议等待 br-lan forwarding 后再启动 DHCP。"],
        )

    monkeypatch.setattr(
        "app.graph.nodes.generate_root_cause_with_llm",
        fake_generate_root_cause_with_llm,
    )

    result = generate_hypotheses_node(_state())

    assert result["hypotheses"][0]["title"].startswith("LLM 判断")
    assert result["fix_suggestions"] == ["LLM 建议等待 br-lan forwarding 后再启动 DHCP。"]


def test_generate_hypotheses_node_falls_back_when_llm_fails(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")

    def fake_generate_root_cause_with_llm(**kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(
        "app.graph.nodes.generate_root_cause_with_llm",
        fake_generate_root_cause_with_llm,
    )

    result = generate_hypotheses_node(_state())

    assert result["hypotheses"][0]["title"] == "DHCP 服务启动早于 LAN bridge ready"
    assert "在 br-lan 进入 forwarding/ready 状态后再启动 DHCP server" in result["fix_suggestions"]
