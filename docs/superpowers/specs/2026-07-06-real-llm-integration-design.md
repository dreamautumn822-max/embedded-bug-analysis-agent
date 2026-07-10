# Real LLM Integration Design

## Goal

Add a configurable real LLM path to the embedded networking bug analysis Agent while preserving the current deterministic rule path as fallback.

## Scope

This change covers:

- OpenAI-compatible chat API configuration.
- Pydantic schema validation for LLM output.
- LLM-driven root cause and fix suggestion generation.
- Automatic fallback to the existing rule chain when LLM is disabled, misconfigured, unavailable, or returns invalid output.
- Tests for enabled, disabled, invalid-output, and fallback paths.
- README and environment documentation.

This change does not cover:

- Replacing the existing local fake embedding path.
- Adding streaming UI output.
- Adding model-cost tracking.
- Expanding the evaluation dataset.

## Configuration

The project will use these environment variables:

- `LLM_ENABLED`: `true` or `false`. Defaults to `false`.
- `LLM_BASE_URL`: OpenAI-compatible API base URL.
- `LLM_API_KEY`: API key.
- `LLM_MODEL`: model name.
- `LLM_TIMEOUT_SECONDS`: request timeout. Defaults to `30`.
- `LLM_TEMPERATURE`: generation temperature. Defaults to `0.2`.

When `LLM_ENABLED` is false or required model settings are missing, the system uses the existing local rule chain.

## Data Flow

```text
LangGraph state
  -> parse logs / search bugs / retrieve docs / search code
  -> generate_hypotheses_node
       -> if LLM enabled:
             build evidence context
             call OpenAI-compatible model
             validate JSON with Pydantic
             return hypotheses + fix_suggestions
          else:
             return rule-chain hypotheses + fix_suggestions
  -> generate_report_node
```

## LLM Output Schema

The model must return JSON matching:

```json
{
  "hypotheses": [
    {
      "title": "string",
      "description": "string",
      "confidence": 0.0
    }
  ],
  "fix_suggestions": ["string"]
}
```

Validation rules:

- At least one hypothesis.
- `title` and `description` must be non-empty.
- `confidence` must be between `0` and `1`.
- At least one fix suggestion.

## Fallback

Fallback must be automatic and silent from the API caller perspective. The API response shape stays unchanged.

Fallback triggers:

- LLM disabled.
- Missing `LLM_API_KEY`, `LLM_BASE_URL`, or `LLM_MODEL`.
- Network/API exception.
- Invalid JSON.
- JSON fails Pydantic validation.

## Testing

Add tests for:

- Config parsing defaults.
- Missing config disables LLM path.
- Valid OpenAI-compatible JSON is parsed into hypotheses and fix suggestions.
- Invalid LLM output raises a controlled error in the LLM client.
- `generate_hypotheses_node` uses LLM result when enabled.
- `generate_hypotheses_node` falls back to rule chain when LLM fails.
- Existing API and graph workflow tests continue to pass with LLM disabled by default.
