import hashlib
import hmac
import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.evaluation.case_schema import (
    BugType,
    EvaluationCase,
    SanitizationAction,
    validate_evaluation_cases,
)


_MAC_PATTERN = re.compile(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b")
_IPV4_PATTERN = re.compile(
    r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1?\d?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\d.])"
)
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SERIAL_PATTERN = re.compile(
    r"(?i)(\b(?:serial(?:_number)?|sn)\s*[:=]\s*)[A-Za-z0-9._-]{4,}"
    r"|((?:设备)?序列号\s*[:：=]\s*)[^\s,;，；]{4,}"
)
_ACCOUNT_PATTERN = re.compile(
    r"(?i)(\b(?:account|username|user)\s*[:=]\s*)[^\s,;]+"
    r"|(账号\s*[:：=]\s*)[^\s,;，；]+"
)
_HOSTNAME_PATTERN = re.compile(
    r"(?i)(\bhostname\s*[:=]\s*)[A-Za-z0-9._-]+"
    r"|(主机名\s*[:：=]\s*)[^\s,;，；]+"
)


class CaseLabel(BaseModel):
    annotator_ref: str = Field(min_length=1, max_length=100)
    expected_bug_type: BugType
    expected_root_cause_keywords: list[str] = Field(min_length=1)
    expected_evidence_terms: list[str] = Field(default_factory=list)
    expected_review_required: bool


class AdjudicatedLabel(BaseModel):
    adjudicator_ref: str = Field(min_length=1, max_length=100)
    expected_bug_type: BugType
    expected_root_cause_keywords: list[str] = Field(min_length=1)
    expected_evidence_terms: list[str] = Field(default_factory=list)
    expected_review_required: bool


class RawProductionCase(BaseModel):
    source_ticket_id: str = Field(min_length=1, max_length=200)
    split: Literal["train", "dev", "test"] = "test"
    device_model: str = Field(min_length=1)
    firmware_version: str = Field(min_length=1)
    symptom: str = Field(min_length=1)
    logs: str = Field(min_length=1)
    stack_trace: str | None = None
    module_hint: str | None = None
    annotations: list[CaseLabel] = Field(min_length=2)
    adjudication: AdjudicatedLabel
    manual_review_confirmed: bool

    @model_validator(mode="after")
    def validate_annotation_process(self) -> "RawProductionCase":
        annotators = [annotation.annotator_ref for annotation in self.annotations]
        if len(annotators) != len(set(annotators)):
            raise ValueError("Production case annotators must be distinct")
        if self.adjudication.adjudicator_ref in set(annotators):
            raise ValueError("The adjudicator must not be one of the annotators")
        if not self.manual_review_confirmed:
            raise ValueError("Production case requires manual sanitization confirmation")
        return self


def import_production_cases(payload: object, *, hash_salt: str) -> list[EvaluationCase]:
    if len(hash_salt) < 16:
        raise ValueError("Case hash salt must contain at least 16 characters")
    if not isinstance(payload, list) or not payload:
        raise ValueError("Raw production dataset must be a non-empty JSON array")

    cases = [
        build_anonymized_case(RawProductionCase.model_validate(item), hash_salt=hash_salt)
        for item in payload
    ]
    return validate_evaluation_cases(
        [case.model_dump(mode="json") for case in cases],
        require_production=True,
    )


def build_anonymized_case(
    raw_case: RawProductionCase,
    *,
    hash_salt: str,
) -> EvaluationCase:
    digest = hmac.new(
        hash_salt.encode("utf-8"),
        raw_case.source_ticket_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    sanitization_actions: set[SanitizationAction] = {"manual_review"}
    sanitizer = CaseSanitizer()

    sanitized_fields: dict[str, str | None] = {}
    for field_name in (
        "device_model",
        "firmware_version",
        "symptom",
        "logs",
        "stack_trace",
        "module_hint",
    ):
        value = getattr(raw_case, field_name)
        if value is None:
            sanitized_fields[field_name] = None
            continue
        sanitized, actions = sanitizer.sanitize(value)
        sanitized_fields[field_name] = sanitized
        sanitization_actions.update(actions)

    label = raw_case.adjudication
    return EvaluationCase.model_validate(
        {
            "case_id": f"prod-{digest[:16]}",
            "case_origin": "production_anonymized",
            "split": raw_case.split,
            "label_status": "adjudicated",
            "annotator_count": len(raw_case.annotations),
            "source_ticket_hash": f"sha256:{digest}",
            "sanitization_actions": sorted(sanitization_actions),
            **sanitized_fields,
            "expected_bug_type": label.expected_bug_type,
            "expected_root_cause_keywords": label.expected_root_cause_keywords,
            "expected_evidence_terms": label.expected_evidence_terms,
            "expected_review_required": label.expected_review_required,
        }
    )


def sanitize_case_text(text: str) -> tuple[str, set[SanitizationAction]]:
    return CaseSanitizer().sanitize(text)


class CaseSanitizer:
    _LABELS = {
        "mac_address": "MAC",
        "ip_address": "IP",
        "email": "EMAIL",
        "serial_number": "DEVICE_SN",
        "account": "ACCOUNT",
        "hostname": "HOST",
    }

    def __init__(self) -> None:
        self._mappings: dict[SanitizationAction, dict[str, str]] = {}
        self._actions: set[SanitizationAction] = set()

    def sanitize(self, text: str) -> tuple[str, set[SanitizationAction]]:
        sanitized = text
        simple_patterns: tuple[tuple[re.Pattern[str], SanitizationAction], ...] = (
            (_MAC_PATTERN, "mac_address"),
            (_IPV4_PATTERN, "ip_address"),
            (_EMAIL_PATTERN, "email"),
        )
        for pattern, action in simple_patterns:
            sanitized = pattern.sub(
                lambda match, action=action: self._placeholder(
                    action,
                    match.group(0),
                ),
                sanitized,
            )

        keyed_patterns: tuple[tuple[re.Pattern[str], SanitizationAction], ...] = (
            (_SERIAL_PATTERN, "serial_number"),
            (_ACCOUNT_PATTERN, "account"),
            (_HOSTNAME_PATTERN, "hostname"),
        )
        for pattern, action in keyed_patterns:
            sanitized = pattern.sub(
                lambda match, action=action: self._replace_keyed(match, action),
                sanitized,
            )
        return sanitized, set(self._actions)

    def _replace_keyed(
        self,
        match: re.Match[str],
        action: SanitizationAction,
    ) -> str:
        prefix = next((group for group in match.groups() if group), "")
        sensitive_value = match.group(0)[len(prefix) :]
        return f"{prefix}{self._placeholder(action, sensitive_value)}"

    def _placeholder(self, action: SanitizationAction, value: str) -> str:
        mapping = self._mappings.setdefault(action, {})
        if value not in mapping:
            label = self._LABELS[action]
            mapping[value] = f"<{label}_{len(mapping) + 1}>"
        self._actions.add(action)
        return mapping[value]
