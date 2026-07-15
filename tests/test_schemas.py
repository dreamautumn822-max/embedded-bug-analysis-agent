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
        generation_mode="rule",
    )

    assert response.bug_type == "network_dhcp"
    assert response.confidence == 0.82
    assert response.root_causes[0].startswith("DHCP")
