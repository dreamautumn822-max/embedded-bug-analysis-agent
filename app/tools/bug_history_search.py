import json
import re
from pathlib import Path


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_./-]+")


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(text)}


def search_bug_history(query: str, bug_history_path: Path, limit: int = 3) -> list[dict]:
    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    bugs = json.loads(bug_history_path.read_text(encoding="utf-8"))
    scored: list[dict] = []

    for bug in bugs:
        searchable = " ".join(
            [
                bug["title"],
                bug["module"],
                bug["symptom"],
                bug["root_cause"],
                bug["fix"],
                " ".join(bug["keywords"]),
            ]
        )
        overlap = query_tokens & _tokens(searchable)
        score = len(overlap)
        if score > 0:
            enriched = dict(bug)
            enriched["score"] = score
            enriched["matched_terms"] = sorted(overlap)
            scored.append(enriched)

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]
