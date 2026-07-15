import json
import re
from time import perf_counter
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from app.llm.config import LLMSettings
from app.llm.schemas import LLMRootCauseResult
from app.observability.metrics import observe_llm
from app.observability.tracing import start_span


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
    evidence_details: list[dict] | None = None,
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
            '{"hypotheses":[{"title":"string","description":"string","confidence":0.0,"evidence_ids":["string"]}],"fix_suggestions":["string"]}',
            "evidence_ids 只能引用下方可引用证据中的 evidence_id。",
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
            _format_records(related_docs, ["source", "content", "snippet", "score"]),
            "",
            "代码线索:",
            _format_code_records(related_code),
            "",
            "可引用证据:",
            _format_records(
                evidence_details or [],
                ["evidence_id", "evidence_type", "source", "content"],
            ),
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
    evidence_details: list[dict] | None = None,
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
        evidence_details=evidence_details,
    )

    started_at = perf_counter()
    with start_span(
        "llm.root_cause",
        {
            "gen_ai.system": "openai-compatible",
            "gen_ai.request.model": settings.model,
        },
    ) as span:
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
        except Exception as exc:  # pragma: no cover - provider exceptions vary
            span.set_attribute("gen_ai.response.status", "error")
            observe_llm(
                model=settings.model,
                status="error",
                duration_seconds=perf_counter() - started_at,
            )
            raise LLMGenerationError(f"LLM request failed: {exc}") from exc

        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        content = response.choices[0].message.content
        try:
            if not content:
                raise LLMGenerationError("LLM returned empty content")
            result = parse_llm_json(content)
        except LLMGenerationError:
            span.set_attribute("gen_ai.response.status", "invalid_output")
            observe_llm(
                model=settings.model,
                status="invalid_output",
                duration_seconds=perf_counter() - started_at,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            raise

        span.set_attribute("gen_ai.response.status", "success")
        span.set_attribute("gen_ai.usage.input_tokens", prompt_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", completion_tokens)
        observe_llm(
            model=settings.model,
            status="success",
            duration_seconds=perf_counter() - started_at,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return result


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
