import hashlib


def build_evidence_details(state: dict) -> list[dict]:
    details: list[dict] = []

    for item in state.get("parsed_logs", {}).get("evidence", [])[:3]:
        details.append(
            {
                "evidence_id": f"log:{_short_hash(item)}",
                "evidence_type": "log",
                "source": "runtime_log",
                "content": item,
                "score": None,
                "rank": len(details) + 1,
            }
        )

    for rank, doc in enumerate(state.get("related_docs", [])[:2], start=1):
        source = str(doc.get("source", "unknown"))
        chunk_id = str(doc.get("chunk_id") or f"{source}::document::000")
        details.append(
            {
                "evidence_id": str(doc.get("evidence_id") or f"doc:{chunk_id}"),
                "evidence_type": "doc",
                "source": source,
                "content": doc.get("snippet") or doc.get("content", ""),
                "score": doc.get("score"),
                "rank": int(doc.get("rank", rank)),
                "section": str(doc.get("section", "document")),
                "chunk_id": chunk_id,
                "retrieval_method": doc.get("retrieval_method"),
                "rerank_method": doc.get("rerank_method"),
                "vector_score": doc.get("vector_score"),
                "vector_rank": doc.get("vector_rank"),
                "bm25_score": doc.get("bm25_score"),
                "bm25_rank": doc.get("bm25_rank"),
                "fusion_score": doc.get("fusion_score"),
                "rerank_score": doc.get("rerank_score"),
            }
        )

    for rank, bug in enumerate(state.get("related_bugs", [])[:2], start=1):
        bug_id = str(bug.get("bug_id", "unknown"))
        details.append(
            {
                "evidence_id": str(bug.get("evidence_id") or f"bug:{bug_id}"),
                "evidence_type": "bug",
                "source": bug_id,
                "content": bug.get("root_cause") or bug.get("symptom", ""),
                "score": bug.get("score"),
                "rank": int(bug.get("rank", rank)),
                **_retrieval_metadata(bug),
            }
        )

    for rank, code in enumerate(state.get("related_code", [])[:2], start=1):
        file_name = str(code.get("file", "unknown"))
        line = str(code.get("line", "?"))
        details.append(
            {
                "evidence_id": str(
                    code.get("evidence_id") or f"code:{file_name}:{line}"
                ),
                "evidence_type": "code",
                "source": f"{file_name}:{line}",
                "content": code.get("snippet", ""),
                "score": code.get("score"),
                "rank": int(code.get("rank", rank)),
                "section": code.get("symbol") or code.get("section"),
                "chunk_id": code.get("chunk_id"),
                "symbol": code.get("symbol"),
                "start_line": code.get("start_line"),
                "end_line": code.get("end_line"),
                "code_kind": code.get("code_kind"),
                "calls": code.get("calls", []),
                "callers": code.get("callers", []),
                "preprocessor_context": code.get("preprocessor_context"),
                "repository_revision": code.get("repository_revision"),
                "commit_sha": code.get("commit_sha"),
                "commit_subject": code.get("commit_subject"),
                "commit_date": code.get("commit_date"),
                "changed_files": code.get("changed_files", []),
                **_retrieval_metadata(code),
            }
        )

    return _deduplicate(details)


def format_evidence(detail: dict) -> str:
    evidence_type = detail["evidence_type"]
    source = detail["source"]
    content = detail["content"]
    if evidence_type == "log":
        return f"log: {content}"
    if evidence_type == "doc":
        section = detail.get("section", "document")
        return f"doc: {source} [{section}] - {content}"
    if evidence_type == "bug":
        return f"bug: {source} - {content}"
    if evidence_type == "code":
        return f"code: {source} - {content}"
    return f"other: {source} - {content}"


def bind_hypothesis_evidence(
    hypotheses: list[dict],
    evidence_details: list[dict],
) -> list[dict]:
    valid_ids = {detail["evidence_id"] for detail in evidence_details}
    default_ids = _representative_evidence_ids(evidence_details)
    bound: list[dict] = []

    for hypothesis in hypotheses:
        requested = hypothesis.get("evidence_ids", [])
        evidence_ids = [item for item in requested if item in valid_ids]
        bound.append(
            {
                **hypothesis,
                "evidence_ids": evidence_ids or default_ids,
            }
        )

    return bound


def _representative_evidence_ids(evidence_details: list[dict]) -> list[str]:
    selected: list[str] = []
    seen_types: set[str] = set()
    for detail in evidence_details:
        evidence_type = detail["evidence_type"]
        if evidence_type in seen_types:
            continue
        seen_types.add(evidence_type)
        selected.append(detail["evidence_id"])
    return selected


def _deduplicate(details: list[dict]) -> list[dict]:
    deduplicated: list[dict] = []
    seen: set[str] = set()
    for detail in details:
        evidence_id = detail["evidence_id"]
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        deduplicated.append(detail)
    return deduplicated


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _retrieval_metadata(item: dict) -> dict:
    keys = (
        "retrieval_method",
        "rerank_method",
        "vector_score",
        "vector_rank",
        "bm25_score",
        "bm25_rank",
        "fusion_score",
        "rerank_score",
    )
    return {key: item.get(key) for key in keys}
