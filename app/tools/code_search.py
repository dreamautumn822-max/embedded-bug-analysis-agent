import re
from pathlib import Path


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+")


def _tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in TOKEN_PATTERN.findall(text):
        lowered = token.lower()
        tokens.add(lowered)
        tokens.update(part for part in lowered.split("_") if part)
    return tokens


def _snippet(lines: list[str], line_index: int, radius: int = 2) -> str:
    start = max(0, line_index - radius)
    end = min(len(lines), line_index + radius + 1)
    return "\n".join(lines[start:end])


def search_codebase(query: str, codebase_dir: Path, limit: int = 5) -> list[dict]:
    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    scored: list[dict] = []
    for source_path in sorted(codebase_dir.glob("*.c")):
        content = source_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        file_matches = query_tokens & _tokens(content)
        file_score = len(file_matches)
        if file_score == 0:
            continue

        best_line_index = 0
        best_line_score = -1
        best_line_matches: set[str] = set()
        for index, line in enumerate(lines):
            line_matches = query_tokens & _tokens(line)
            line_score = len(line_matches)
            if line_score > best_line_score:
                best_line_index = index
                best_line_matches = line_matches
                best_line_score = line_score

        line_score = len(best_line_matches)
        scored.append(
            {
                "file": source_path.name,
                "path": str(source_path),
                "line": best_line_index + 1,
                "score": line_score + file_score,
                "matched_terms": sorted(file_matches),
                "snippet": _snippet(lines, best_line_index),
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]
