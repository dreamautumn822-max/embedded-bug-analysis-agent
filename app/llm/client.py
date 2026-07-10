import json
import re
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from app.llm.config import LLMSettings
from app.llm.schemas import LLMRootCauseResult


class LLMGenerationError(RuntimeError):
    """Raised when LLM output cannot be used by the Agent."""


def build_root_cause_prompt(
    *,
    bug_type: str,
    symptom: str,
    parsed_logs: dict,
    related_bugs: list[dict],
    related_docs: list[dict],
    related_code: list[dict],
) -> str:
    log_patterns = parsed_logs.get("error_patterns", [])
    log_events = parsed_logs.get("events", [])
    log_evidence = parsed_logs.get("evidence", [])

    return "\n".join(
        [
            "你是嵌入式网通设备故障分析助手。",
            "请只基于给定日志、历史 Bug、模块文档和代码线索分析根因。",
            "如果证据不足，请降低 confidence 并给出需要补充的信息。",
            "必须返回 JSON，不要输出 Markdown，不要输出额外解释。",
            "",
            "JSON schema:",
            '{"hypotheses":[{"title":"string","description":"string","confidence":0.0}],"fix_suggestions":["string"]}',
            "",
            f"Bug 类型: {bug_type}",
            f"问题现象: {symptom}",
            "",
            "日志错误模式:",
            _format_list(log_patterns),
            "日志事件:",
            _format_list(log_events),
            "日志证据:",
            _format_list(log_evidence),
            "",
            "历史 Bug:",
            _format_records(related_bugs, ["bug_id", "symptom", "root_cause", "fix"]),
            "",
            "模块文档:",
            _format_records(related_docs, ["source", "snippet", "score"]),
            "",
            "代码线索:",
            _format_code_records(related_code),
        ]
    )


def generate_root_cause_with_llm(
    *,
    settings: LLMSettings,
    bug_type: str,
    symptom: str,
    parsed_logs: dict,
    related_bugs: list[dict],
    related_docs: list[dict],
    related_code: list[dict],
    client: Any | None = None,
) -> LLMRootCauseResult:
    if not settings.is_ready:
        raise LLMGenerationError("LLM is not ready")

    client = client or OpenAI(api_key=settings.api_key, base_url=settings.base_url)
    prompt = build_root_cause_prompt(
        bug_type=bug_type,
        symptom=symptom,
        parsed_logs=parsed_logs,
        related_bugs=related_bugs,
        related_docs=related_docs,
        related_code=related_code,
    )

    try:
        response = client.chat.completions.create(
            model=settings.model,
            messages=[
                {
                    "role": "system",
                    "content": "你是严谨的嵌入式网通设备 Bug 分析专家，只输出可解析 JSON。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=settings.temperature,
            timeout=settings.timeout_seconds,
        )
    except Exception as exc:  # pragma: no cover - exact SDK exceptions vary by provider
        raise LLMGenerationError(f"LLM request failed: {exc}") from exc

    content = response.choices[0].message.content
    if not content:
        raise LLMGenerationError("LLM returned empty content")
    return parse_llm_json(content)


def parse_llm_json(content: str) -> LLMRootCauseResult:
    raw = _strip_code_fence(content.strip())
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMGenerationError(f"LLM returned invalid JSON: {exc}") from exc

    try:
        return LLMRootCauseResult.model_validate(payload)
    except ValidationError as exc:
        raise LLMGenerationError(f"LLM output failed validation: {exc}") from exc


def _strip_code_fence(content: str) -> str:
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", content, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return content


def _format_list(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def _format_records(records: list[dict], keys: list[str]) -> str:
    if not records:
        return "- none"
    lines = []
    for record in records:
        parts = [f"{key}={record[key]}" for key in keys if key in record and record[key]]
        lines.append(f"- {'; '.join(parts)}")
    return "\n".join(lines)


def _format_code_records(records: list[dict]) -> str:
    if not records:
        return "- none"
    lines = []
    for record in records:
        file_name = record.get("file", "unknown")
        line = record.get("line", "?")
        snippet = record.get("snippet", "")
        lines.append(f"- {file_name}:{line} - {snippet}")
    return "\n".join(lines)
