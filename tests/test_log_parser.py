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
    assert result["evidence"][0].startswith("2026-06-25")


def test_parse_syslog_excludes_unmatched_lines_from_evidence():
    logs = """
2026-06-25 14:03:10 system: heartbeat ok
2026-06-25 14:03:11 netifd: interface lan reload
2026-06-25 14:03:12 dhcpd: lease allocation failed
"""

    result = parse_syslog(logs)

    assert result["modules"] == ["dhcpd", "netifd", "system"]
    assert result["evidence"] == [
        "2026-06-25 14:03:11 netifd: interface lan reload",
        "2026-06-25 14:03:12 dhcpd: lease allocation failed",
    ]
