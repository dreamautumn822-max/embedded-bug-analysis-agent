def generate_report(
    bug_type: str,
    hypotheses: list[dict],
    evidence: list[str],
    fix_suggestions: list[str],
) -> str:
    lines = [
        f"Bug 类型：{bug_type}",
        "",
        "根因假设：",
    ]

    for index, hypothesis in enumerate(hypotheses, start=1):
        lines.append(f"{index}. {hypothesis['title']}，置信度 {hypothesis['confidence']:.2f}")

    lines.extend(["", "证据链："])
    for index, item in enumerate(evidence, start=1):
        lines.append(f"{index}. {item}")

    lines.extend(["", "修复建议："])
    for index, item in enumerate(fix_suggestions, start=1):
        lines.append(f"{index}. {item}")

    return "\n".join(lines)
