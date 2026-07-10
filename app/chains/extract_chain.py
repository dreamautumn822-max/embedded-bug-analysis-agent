def extract_bug_info(symptom: str, logs: str, module_hint: str | None) -> dict:
    combined = f"{symptom}\n{logs}\n{module_hint or ''}".lower()

    if "dhcp" in combined or "lease allocation failed" in combined:
        return {"bug_type": "network_dhcp", "keywords": ["dhcp", "lease", "netifd", "bridge"]}
    if "pppoe" in combined or "auth failed" in combined:
        return {"bug_type": "network_pppoe", "keywords": ["pppoe", "auth", "wan", "retry"]}
    if "wifi" in combined or "station disconnected" in combined:
        return {"bug_type": "wifi_disconnect", "keywords": ["wifi", "channel", "station", "disconnect"]}
    if "tr069" in combined or "acs" in combined:
        return {"bug_type": "management_tr069", "keywords": ["tr069", "acs", "dns", "inform"]}
    if "upgrade" in combined or "升级" in combined:
        return {"bug_type": "upgrade_regression", "keywords": ["upgrade", "migration", "config"]}

    return {"bug_type": "unknown", "keywords": []}
