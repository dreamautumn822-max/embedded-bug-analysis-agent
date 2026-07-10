# Real LLM Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable OpenAI-compatible LLM generation to the Bug Analysis Agent with Pydantic validation and rule-chain fallback.

**Architecture:** Create a small `app/llm/` module that owns configuration, schema, prompt construction, OpenAI-compatible chat calls, and output validation. Keep LangGraph node orchestration intact by letting `generate_hypotheses_node` try the LLM path and fall back to the existing deterministic chain.

**Tech Stack:** Python, Pydantic, OpenAI-compatible chat completions via `openai`, LangGraph, pytest, FastAPI, Streamlit.

---

## File Map

- Create `app/llm/__init__.py`: package marker.
- Create `app/llm/config.py`: environment parsing and enabled/misconfigured checks.
- Create `app/llm/schemas.py`: Pydantic schemas for model output.
- Create `app/llm/client.py`: OpenAI-compatible client wrapper, prompt builder, JSON parsing.
- Modify `app/graph/nodes.py`: use LLM generation in `generate_hypotheses_node` with fallback.
- Modify `.env.example`: document LLM environment variables.
- Modify `README.md`: add LLM setup and fallback behavior.
- Add `tests/test_llm_config.py`: config behavior.
- Add `tests/test_llm_client.py`: parsing and mocked client behavior.
- Add `tests/test_llm_graph_node.py`: LangGraph node LLM/fallback behavior.

## Tasks

### Task 1: LLM Config

- [ ] Write failing tests for default disabled config and enabled config.
- [ ] Implement `LLMSettings.from_env()`.
- [ ] Verify config tests pass.

### Task 2: LLM Schemas

- [ ] Write failing tests for valid and invalid LLM output.
- [ ] Implement `LLMHypothesis` and `LLMRootCauseResult`.
- [ ] Verify schema tests pass.

### Task 3: LLM Client

- [ ] Write failing tests for JSON parsing, markdown-code-fence JSON parsing, invalid JSON, and mocked chat completion.
- [ ] Implement prompt builder and `generate_root_cause_with_llm()`.
- [ ] Verify client tests pass.

### Task 4: Graph Node Integration

- [ ] Write failing tests proving `generate_hypotheses_node` uses LLM when enabled and falls back on LLM error.
- [ ] Modify `app/graph/nodes.py` to call LLM first and rule chain second.
- [ ] Verify graph node tests pass.

### Task 5: Docs and Environment

- [ ] Update `.env.example` with LLM variables.
- [ ] Update `README.md` with DeepSeek/Qwen/OpenAI-compatible setup examples and fallback explanation.
- [ ] Run full test suite.

## Verification

Run:

```bash
.venv/bin/pytest -q
.venv/bin/python scripts/evaluate.py
```

Expected:

- All tests pass.
- Evaluation still works with `LLM_ENABLED=false`.
