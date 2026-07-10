import re


MODULE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ([^:]+): (.+)")

ERROR_KEYWORDS = {
    "lease allocation failed": "lease allocation failed",
    "auth failed": "auth failed",
    "station disconnected": "station disconnected",
    "inform failed": "inform failed",
    "segfault": "segfault",
}

EVENT_KEYWORDS = {
    "interface lan reload": "interface reload",
    "br-lan port state changed": "bridge state change",
    "channel switch": "channel switch",
    "wan link up": "wan link up",
    "wan link down": "wan link down",
    "retry timer stopped": "retry timer stopped",
}


def parse_syslog(logs: str) -> dict[str, list[str]]:
    modules = set()
    error_patterns = []
    events = []
    evidence = []

    for line in logs.splitlines():
        line = line.strip()
        if not line:
            continue

        match = MODULE_PATTERN.match(line)
        if not match:
            continue

        modules.add(match.group(1))

        lowered = line.lower()
        matched_evidence = False
        for keyword, label in ERROR_KEYWORDS.items():
            if keyword in lowered and label not in error_patterns:
                error_patterns.append(label)
                matched_evidence = True

        for keyword, label in EVENT_KEYWORDS.items():
            if keyword in lowered and label not in events:
                events.append(label)
                matched_evidence = True

        if matched_evidence:
            _append_once(evidence, line)

    return {
        "modules": sorted(modules),
        "error_patterns": error_patterns,
        "events": events,
        "evidence": evidence,
    }


def _append_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)
