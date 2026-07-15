import re
import unicodedata
from dataclasses import dataclass

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document


_LATIN_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[._:/-][a-z0-9]+)*")
_CJK_SEQUENCE_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")


@dataclass
class RankedDocument:
    document: Document
    score: float
    rank: int


@dataclass
class FusedCandidate:
    document: Document
    vector_score: float | None = None
    vector_rank: int | None = None
    bm25_score: float | None = None
    bm25_rank: int | None = None
    fusion_score: float = 0.0
    rerank_score: float = 0.0

    @property
    def chunk_id(self) -> str:
        return str(self.document.metadata.get("chunk_id", "unknown"))


def tokenize_for_retrieval(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).lower()
    tokens = _LATIN_TOKEN_PATTERN.findall(normalized)
    identifier_parts = []
    for token in tokens:
        identifier_parts.extend(
            part for part in re.split(r"[._:/-]+", token) if part != token
        )
    tokens.extend(identifier_parts)

    for sequence in _CJK_SEQUENCE_PATTERN.findall(normalized):
        if len(sequence) <= 4:
            tokens.append(sequence)
        if len(sequence) == 1:
            tokens.append(sequence)
            continue
        for size in (2, 3):
            tokens.extend(
                sequence[index : index + size]
                for index in range(len(sequence) - size + 1)
            )

    return tokens


def bm25_search(
    query: str,
    documents: list[Document],
    *,
    k: int,
) -> list[RankedDocument]:
    if k < 1:
        raise ValueError("k must be >= 1")
    if not documents:
        return []

    retriever = BM25Retriever.from_documents(
        documents,
        preprocess_func=tokenize_for_retrieval,
        k=min(k, len(documents)),
    )
    query_tokens = tokenize_for_retrieval(query)
    if not query_tokens:
        return []

    scores = retriever.vectorizer.get_scores(query_tokens)
    query_token_set = set(query_tokens)
    overlaps = [
        len(query_token_set & set(tokenize_for_retrieval(document.page_content)))
        for document in retriever.docs
    ]
    ranked_indices = sorted(
        range(len(retriever.docs)),
        key=lambda index: (float(scores[index]), overlaps[index], -index),
        reverse=True,
    )

    results: list[RankedDocument] = []
    for index in ranked_indices:
        if overlaps[index] == 0 and float(scores[index]) <= 0:
            continue
        results.append(
            RankedDocument(
                document=retriever.docs[index],
                score=float(scores[index]),
                rank=len(results) + 1,
            )
        )
        if len(results) >= k:
            break
    return results


def reciprocal_rank_fusion(
    vector_results: list[RankedDocument],
    bm25_results: list[RankedDocument],
    *,
    rrf_k: int,
    vector_weight: float,
    bm25_weight: float,
) -> list[FusedCandidate]:
    if rrf_k < 1:
        raise ValueError("rrf_k must be >= 1")

    candidates: dict[str, FusedCandidate] = {}
    for item in vector_results:
        candidate = candidates.setdefault(
            _chunk_id(item.document),
            FusedCandidate(document=item.document),
        )
        candidate.vector_score = item.score
        candidate.vector_rank = item.rank
        candidate.fusion_score += vector_weight / (rrf_k + item.rank)

    for item in bm25_results:
        candidate = candidates.setdefault(
            _chunk_id(item.document),
            FusedCandidate(document=item.document),
        )
        candidate.bm25_score = item.score
        candidate.bm25_rank = item.rank
        candidate.fusion_score += bm25_weight / (rrf_k + item.rank)

    return sorted(
        candidates.values(),
        key=lambda candidate: (-candidate.fusion_score, candidate.chunk_id),
    )


def _chunk_id(document: Document) -> str:
    return str(document.metadata.get("chunk_id", "unknown"))
