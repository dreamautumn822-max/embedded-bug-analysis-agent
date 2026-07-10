# Embedded Bug Agent Frontend Console Design

## Subject

The interface is a field debugging console for embedded networking bug analysis. The primary users are embedded, networking, QA, and support engineers investigating router and ONU failures from symptoms and device logs.

## Single Job

Help the user paste a failure scene, run analysis, and read the root cause evidence chain without leaving the page.

## Chosen Direction

Direction A: field debugging console.

The page should borrow from serial terminals, board bring-up benches, and network diagnostics panels without becoming a generic dark dashboard. The input side stays efficient and form-like. The result side reads as a structured incident board: bug type, confidence, root cause, evidence, and fix actions.

## Token System

- Console shell: `#182022`
- Panel metal: `#263033`
- Work surface: `#F2F5F1`
- Signal green: `#6DA36F`
- Trace amber: `#D6B45A`
- Fault coral: `#C76E5A`
- Bus blue: `#7AA8A8`

Typography:

- Display: system sans with condensed, heavy weights for the header.
- Utility/data: monospace for labels, timestamps, device fields, and evidence snippets.
- Body: system sans for Chinese readability.

## Layout

```text
┌──────────────────────────────────────────────────────────┐
│ status rail: API endpoint / model / firmware / module     │
├───────────────────────────┬──────────────────────────────┤
│ failure scene input       │ root cause board              │
│ device + firmware         │ confidence + bug type         │
│ symptom                   │ summary                       │
│ logs                      │ evidence grouped by source    │
│ optional trace/module     │ fix actions                   │
└───────────────────────────┴──────────────────────────────┘
```

## Signature Element

Use an evidence bus: grouped evidence blocks labeled `LOG`, `DOC`, `BUG`, and `CODE`. This makes the LangGraph/RAG output visible as a debugging trail instead of a flat markdown list.

## Implementation Notes

- Keep Streamlit and existing API contract.
- Extract small helper functions for payload building and evidence grouping so tests can cover the behavior.
- Do not add new frontend dependencies.
- Avoid landing-page copy; the first screen remains the usable analyzer.
