import re
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field, model_validator


BugType = Literal[
    "network_dhcp",
    "network_pppoe",
    "wifi_disconnect",
    "management_tr069",
    "upgrade_regression",
    "unknown",
]
SanitizationAction = Literal[
    "mac_address",
    "ip_address",
    "email",
    "serial_number",
    "account",
    "hostname",
    "manual_review",
]

_TICKET_HASH_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
_MAC_PATTERN = re.compile(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b")
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_IPV4_PATTERN = re.compile(
    r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1?\d?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\d.])"
)
_DOCUMENTATION_NETWORKS = (
    "192.0.2.",
    "198.51.100.",
    "203.0.113.",
)


class EvaluationCase(BaseModel):
    case_id: str = Field(min_length=1, max_length=100)
    case_origin: Literal["synthetic", "production_anonymized"]
    split: Literal["train", "dev", "test"]
    label_status: Literal["draft", "reviewed", "adjudicated"]
    annotator_count: int = Field(ge=1, le=20)
    source_ticket_hash: str | None = None
    sanitization_actions: list[SanitizationAction] = Field(default_factory=list)
    device_model: str = Field(min_length=1)
    firmware_version: str = Field(min_length=1)
    symptom: str = Field(min_length=1)
    logs: str = Field(min_length=1)
    stack_trace: str | None = None
    module_hint: str | None = None
    expected_bug_type: BugType
    expected_root_cause_keywords: list[str] = Field(min_length=1)
    expected_evidence_terms: list[str] = Field(default_factory=list)
    expected_review_required: bool

    @model_validator(mode="after")
    def validate_production_case(self) -> "EvaluationCase":
        if self.case_origin == "synthetic":
            if self.source_ticket_hash is not None:
                raise ValueError("Synthetic cases must not contain source_ticket_hash")
            return self

        if not self.source_ticket_hash or not _TICKET_HASH_PATTERN.fullmatch(
            self.source_ticket_hash
        ):
            raise ValueError(
                "Production cases require source_ticket_hash in sha256:<64 hex> format"
            )
        digest = self.source_ticket_hash.removeprefix("sha256:")
        if len(set(digest)) == 1:
            raise ValueError("Production case source_ticket_hash is still a placeholder")
        if self.label_status != "adjudicated" or self.annotator_count < 2:
            raise ValueError(
                "Production cases require two annotators and adjudicated labels"
            )
        if "manual_review" not in self.sanitization_actions:
            raise ValueError("Production cases require a manual sanitization review")

        sensitive_text = "\n".join(
            filter(
                None,
                (
                    self.device_model,
                    self.symptom,
                    self.logs,
                    self.stack_trace,
                    self.module_hint,
                ),
            )
        )
        findings = find_sensitive_tokens(sensitive_text)
        if findings:
            raise ValueError(
                "Production case still contains sensitive token types: "
                + ", ".join(sorted(findings))
            )
        return self


def validate_evaluation_cases(
    payload: object,
    *,
    require_production: bool = False,
) -> list[EvaluationCase]:
    if not isinstance(payload, list) or not payload:
        raise ValueError("Evaluation dataset must be a non-empty JSON array")

    cases = [EvaluationCase.model_validate(item) for item in payload]
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Evaluation dataset contains duplicate case_id values")

    production_cases = [
        case for case in cases if case.case_origin == "production_anonymized"
    ]
    if require_production and not production_cases:
        raise ValueError("Dataset does not contain production_anonymized cases")

    hashes = [case.source_ticket_hash for case in production_cases]
    if len(hashes) != len(set(hashes)):
        raise ValueError(
            "The same source ticket appears more than once; this can leak across splits"
        )
    return cases


def find_sensitive_tokens(text: str) -> set[str]:
    findings: set[str] = set()
    if _MAC_PATTERN.search(text):
        findings.add("mac_address")
    if _EMAIL_PATTERN.search(text):
        findings.add("email")
    for match in _IPV4_PATTERN.finditer(text):
        address = match.group(0)
        if not address.startswith(_DOCUMENTATION_NETWORKS):
            findings.add("ip_address")
    return findings


def dataset_summary(cases: Sequence[EvaluationCase]) -> dict[str, object]:
    def counts(field: str) -> dict[str, int]:
        values: dict[str, int] = {}
        for case in cases:
            value = str(getattr(case, field))
            values[value] = values.get(value, 0) + 1
        return dict(sorted(values.items()))

    return {
        "case_count": len(cases),
        "origin_counts": counts("case_origin"),
        "split_counts": counts("split"),
        "label_status_counts": counts("label_status"),
        "bug_type_counts": counts("expected_bug_type"),
    }
