import json
from pathlib import Path

from app.rag.loader import load_markdown_chunks


DATASET_PATH = Path("data/rag/retrieval_eval_cases.json")


def test_retrieval_eval_dataset_references_existing_chunks():
    cases = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    chunks = load_markdown_chunks(Path("data/docs"))
    chunk_ids = {chunk.metadata["chunk_id"] for chunk in chunks}

    assert len(cases) >= 10
    assert len({case["case_id"] for case in cases}) == len(cases)
    for case in cases:
        assert case["query"].strip()
        assert case["relevant_chunk_ids"]
        assert set(case["relevant_chunk_ids"]) <= chunk_ids
