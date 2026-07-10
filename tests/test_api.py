from fastapi.testclient import TestClient

from app.main import app


def test_analyze_endpoint_returns_dhcp_report():
    client = TestClient(app)
    logs = "\n".join(
        [
            "2026-06-25 14:03:11 netifd: interface lan reload",
            "2026-06-25 14:03:12 kernel: br-lan port state changed to blocking",
            "2026-06-25 14:03:12 dhcpd: lease allocation failed",
            "2026-06-25 14:03:14 kernel: br-lan port state changed to forwarding",
        ]
    )

    response = client.post(
        "/analyze",
        json={
            "device_model": "AX3000 Router",
            "firmware_version": "v2.1.8",
            "symptom": "升级后 DHCP 客户端偶发获取不到 IP",
            "logs": logs,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["bug_type"] == "network_dhcp"
    assert "DHCP" in data["summary"]
    assert data["confidence"] >= 0.75
    assert any("BUG-018" in item or item.startswith("log: ") for item in data["evidence"])
