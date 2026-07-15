import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.config import (
    RAGSettings,
    SUPPORTED_RERANK_PROVIDERS,
    SUPPORTED_RETRIEVAL_MODES,
)
from app.rag.evaluation import aggregate_ranking_metrics, evaluate_ranking
from app.rag.retriever import clear_vector_store_cache, retrieve_related_documents


DEFAULT_CASES_PATH = PROJECT_ROOT / "data" / "rag" / "retrieval_eval_cases.json"


def run_retrieval_evaluation(
    cases: list[dict],
    *,
    settings: RAGSettings,
    top_k: int,
) -> dict:
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if not cases:
        raise ValueError("cases must not be empty")

    eval_settings = replace(
        settings,
        top_k=top_k,
        candidate_k=max(settings.candidate_k, top_k),
    )
    case_results: list[dict] = []

    clear_vector_store_cache()
    try:
        for case in cases:
            started_at = perf_counter()
            retrieved = retrieve_related_documents(case["query"], settings=eval_settings)
            latency_ms = (perf_counter() - started_at) * 1000
            retrieved_ids = [item["chunk_id"] for item in retrieved]
            metrics = evaluate_ranking(
                retrieved_ids,
                case["relevant_chunk_ids"],
                k=top_k,
            )
            case_results.append(
                {
                    "case_id": case["case_id"],
                    "query": case["query"],
                    "retrieved_ids": retrieved_ids,
                    "retrieval_methods": sorted(
                        {item["retrieval_method"] for item in retrieved}
                    ),
                    "rerank_methods": sorted(
                        {item["rerank_method"] for item in retrieved}
                    ),
                    "latency_ms": latency_ms,
                    **metrics,
                }
            )
    finally:
        clear_vector_store_cache()

    latencies = sorted(result["latency_ms"] for result in case_results)
    p95_index = max(0, int(len(latencies) * 0.95 + 0.9999) - 1)
    return {
        "case_count": len(case_results),
        "top_k": top_k,
        "retrieval_mode": eval_settings.retrieval_mode,
        "rerank_provider": eval_settings.rerank_provider,
        "embedding_provider": eval_settings.embedding_provider,
        "embedding_model": eval_settings.embedding_model,
        "metrics": aggregate_ranking_metrics(case_results),
        "average_latency_ms": sum(latencies) / len(latencies),
        "p95_latency_ms": latencies[p95_index],
        "cases": case_results,
    }


def main() -> None:
    args = _parse_args()
    if args.load_env:
        load_dotenv(PROJECT_ROOT / ".env", override=True)

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if not cases:
        raise SystemExit("No retrieval evaluation cases found.")

    settings = RAGSettings.from_env()
    if args.retrieval_mode:
        settings = replace(settings, retrieval_mode=args.retrieval_mode)
    if args.rerank_provider:
        settings = replace(settings, rerank_provider=args.rerank_provider)

    if args.compare:
        _print_comparison(cases, settings=settings, top_k=args.top_k)
        return
    if args.compare_embeddings:
        _print_embedding_comparison(cases, settings=settings, top_k=args.top_k)
        return

    report = run_retrieval_evaluation(cases, settings=settings, top_k=args.top_k)
    _print_report(report, verbose=True)


def _print_report(report: dict, *, verbose: bool) -> None:
    if verbose:
        for case in report["cases"]:
            print(
                f"{case['case_id']}: "
                f"recall@{report['top_k']}={case['recall_at_k']:.2f}, "
                f"mrr={case['mrr']:.2f}, "
                f"ndcg@{report['top_k']}={case['ndcg_at_k']:.2f}, "
                f"latency_ms={case['latency_ms']:.1f}, "
                f"retrieved={case['retrieved_ids']}"
            )

    print("summary:")
    print(f"retrieval_mode={report['retrieval_mode']}")
    print(f"rerank_provider={report['rerank_provider']}")
    print(f"case_count={report['case_count']}")
    print(f"top_k={report['top_k']}")
    for name, value in report["metrics"].items():
        print(f"{name}={value:.4f}")
    print(f"average_latency_ms={report['average_latency_ms']:.2f}")
    print(f"p95_latency_ms={report['p95_latency_ms']:.2f}")


def _print_comparison(
    cases: list[dict],
    *,
    settings: RAGSettings,
    top_k: int,
) -> None:
    rerank_provider = (
        settings.rerank_provider if settings.rerank_provider != "none" else "local"
    )
    pipelines = [
        ("vector", replace(settings, retrieval_mode="vector", rerank_provider="none")),
        ("bm25", replace(settings, retrieval_mode="bm25", rerank_provider="none")),
        (
            "hybrid_rrf",
            replace(settings, retrieval_mode="hybrid", rerank_provider="none"),
        ),
        (
            f"hybrid_{rerank_provider}",
            replace(
                settings,
                retrieval_mode="hybrid",
                rerank_provider=rerank_provider,
            ),
        ),
    ]

    print(
        "pipeline\trecall@k\tprecision@k\thit_rate@k\tmrr\tndcg@k\tavg_ms\tp95_ms"
    )
    for name, pipeline_settings in pipelines:
        report = run_retrieval_evaluation(
            cases,
            settings=pipeline_settings,
            top_k=top_k,
        )
        metrics = report["metrics"]
        print(
            f"{name}\t{metrics['recall_at_k']:.4f}\t"
            f"{metrics['precision_at_k']:.4f}\t"
            f"{metrics['hit_rate_at_k']:.4f}\t{metrics['mrr']:.4f}\t"
            f"{metrics['ndcg_at_k']:.4f}\t"
            f"{report['average_latency_ms']:.2f}\t{report['p95_latency_ms']:.2f}"
        )


def _print_embedding_comparison(
    cases: list[dict],
    *,
    settings: RAGSettings,
    top_k: int,
) -> None:
    providers = [
        (
            "local_hash_vector",
            replace(
                settings,
                embedding_provider="local",
                embedding_model="local-hashing-v1",
                retrieval_mode="vector",
                rerank_provider="none",
            ),
        ),
        (
            "bge_zh_vector",
            replace(
                settings,
                embedding_provider="fastembed",
                embedding_model="BAAI/bge-small-zh-v1.5",
                retrieval_mode="vector",
                rerank_provider="none",
            ),
        ),
    ]
    print("embedding\trecall@k\thit_rate@k\tmrr\tndcg@k\tavg_ms\tp95_ms")
    for name, provider_settings in providers:
        report = run_retrieval_evaluation(
            cases,
            settings=provider_settings,
            top_k=top_k,
        )
        metrics = report["metrics"]
        print(
            f"{name}\t{metrics['recall_at_k']:.4f}\t"
            f"{metrics['hit_rate_at_k']:.4f}\t{metrics['mrr']:.4f}\t"
            f"{metrics['ndcg_at_k']:.4f}\t"
            f"{report['average_latency_ms']:.2f}\t{report['p95_latency_ms']:.2f}"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate RAG chunk retrieval ranking.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--load-env", action="store_true")
    parser.add_argument(
        "--retrieval-mode",
        choices=sorted(SUPPORTED_RETRIEVAL_MODES),
    )
    parser.add_argument(
        "--rerank-provider",
        choices=sorted(SUPPORTED_RERANK_PROVIDERS),
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare vector, BM25, hybrid RRF, and hybrid rerank pipelines.",
    )
    parser.add_argument(
        "--compare-embeddings",
        action="store_true",
        help="Compare LocalHash and local BGE semantic vector retrieval.",
    )
    args = parser.parse_args()
    if args.top_k < 1:
        raise SystemExit("--top-k must be >= 1")
    return args


if __name__ == "__main__":
    main()
