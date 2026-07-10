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
