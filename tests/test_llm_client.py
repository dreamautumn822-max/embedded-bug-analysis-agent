import pytest

from app.llm.client import (
    LLMGenerationError,
    build_root_cause_prompt,
    generate_root_cause_with_llm,
    parse_llm_json,
)
from app.llm.config import LLMSettings


class FakeCompletions:
    def __init__(self, content: str):
        self.content = content
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        message = type("Message", (), {"content": self.content})()
        choice = type("Choice", (), {"message": message})()
        return type("Response", (), {"choices": [choice]})()


class FakeClient:
    def __init__(self, content: str):
        self.chat = type("Chat", (), {"completions": FakeCompletions(content)})()


VALID_JSON = """
{
  "hypotheses": [
    {
      "title": "DHCP starts before bridge ready",
      "description": "DHCP server restarts while br-lan is still blocking.",
      "confidence": 0.91
    }
  ],
  "fix_suggestions": ["Wait for br-lan forwarding before restarting DHCP."]
}
"""


def test_parse_llm_json_accepts_plain_json():
    result = parse_llm_json(VALID_JSON)

    assert result.hypotheses[0].title == "DHCP starts before bridge ready"
    assert result.fix_suggestions[0].startswith("Wait for br-lan")


def test_parse_llm_json_accepts_markdown_code_fence():
    result = parse_llm_json(f"```json\n{VALID_JSON}\n```")

    assert result.hypotheses[0].confidence == 0.91


def test_parse_llm_json_rejects_invalid_payload():
    with pytest.raises(LLMGenerationError):
        parse_llm_json("not json")


def test_build_root_cause_prompt_includes_evidence_context():
    prompt = build_root_cause_prompt(
        bug_type="network_dhcp",
        symptom="DHCP clients cannot get IP",
        parsed_logs={"error_patterns": ["lease allocation failed"]},
        related_bugs=[{"bug_id": "BUG-018", "root_cause": "DHCP starts too early"}],
        related_docs=[
            {
                "source": "dhcp.md",
                "content": "DHCP server 必须等待 bridge ready 后启动。",
                "snippet": "DHCP 模块说明",
            }
        ],
        related_code=[{"file": "netifd_reload.c", "line": 3, "snippet": "restart_dhcp_server();"}],
    )

    assert "network_dhcp" in prompt
    assert "lease allocation failed" in prompt
    assert "BUG-018" in prompt
    assert "bridge ready 后启动" in prompt
    assert "netifd_reload.c:3" in prompt


def test_generate_root_cause_with_llm_calls_openai_compatible_client():
    fake_client = FakeClient(VALID_JSON)
    settings = LLMSettings(
        enabled=True,
        base_url="https://api.deepseek.com",
        api_key="test-key",
        model="deepseek-chat",
        timeout_seconds=7,
        temperature=0.1,
    )

    result = generate_root_cause_with_llm(
        settings=settings,
        bug_type="network_dhcp",
        symptom="DHCP clients cannot get IP",
        parsed_logs={"error_patterns": ["lease allocation failed"]},
        related_bugs=[],
        related_docs=[],
        related_code=[],
        client=fake_client,
    )

    kwargs = fake_client.chat.completions.kwargs
    assert kwargs["model"] == "deepseek-chat"
    assert kwargs["temperature"] == 0.1
    assert kwargs["timeout"] == 7
    assert result.hypotheses[0].description.startswith("DHCP server")
