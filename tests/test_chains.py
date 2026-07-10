from app.chains.extract_chain import extract_bug_info
from app.chains.report_chain import generate_report
from app.chains.root_cause_chain import generate_root_cause_hypotheses


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
    assert hypotheses[0]["description"].startswith("netifd reload")
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
