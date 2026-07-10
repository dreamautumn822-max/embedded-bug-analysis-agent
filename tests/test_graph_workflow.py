from app.graph.bug_analysis_graph import analyze_bug


def test_bug_analysis_workflow_returns_dhcp_report():
    logs = "\n".join(
        [
            "2026-06-25 14:03:11 netifd: interface lan reload",
            "2026-06-25 14:03:12 kernel: br-lan port state changed to blocking",
            "2026-06-25 14:03:12 dhcpd: lease allocation failed",
            "2026-06-25 14:03:14 kernel: br-lan port state changed to forwarding",
        ]
    )

    result = analyze_bug(
        device_model="AX3000 Router",
        firmware_version="v2.1.8",
        symptom="升级后 DHCP 客户端偶发获取不到 IP",
        logs=logs,
    )

    assert result["bug_type"] == "network_dhcp"
    assert result["hypotheses"][0]["confidence"] >= 0.75
    assert "修复建议" in result["final_report"]
    assert "lease allocation failed" in result["parsed_logs"]["error_patterns"]
    assert any(item.startswith("log: ") for item in result["evidence"])
    assert any(item.startswith("doc: dhcp.md") for item in result["evidence"])
    assert any("BUG-018" in item for item in result["evidence"])
    assert any("netifd_reload.c" in item for item in result["evidence"])
    assert "证据链" in result["final_report"]
