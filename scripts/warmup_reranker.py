import argparse
import sys
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.config import RAGSettings
from app.rag.reranker import warmup_model_reranker


DEFAULT_MODELS = {
    "flashrank": "ms-marco-MultiBERT-L-12",
    "cross_encoder": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
}


def main() -> None:
    args = _parse_args()
    if args.load_env:
        load_dotenv(PROJECT_ROOT / ".env", override=True)

    settings = RAGSettings.from_env()
    model_name = args.model or (
        settings.rerank_model
        if settings.rerank_provider == args.provider
        else DEFAULT_MODELS[args.provider]
    )
    cache_dir = args.cache_dir or settings.rerank_cache_dir
    max_length = args.max_length or settings.rerank_max_length

    started_at = perf_counter()
    warmup_model_reranker(
        provider=args.provider,
        model_name=model_name,
        cache_dir=cache_dir,
        max_length=max_length,
    )
    elapsed_seconds = perf_counter() - started_at
    print(
        f"Reranker ready: provider={args.provider}, model={model_name}, "
        f"cache_dir={cache_dir}, elapsed_seconds={elapsed_seconds:.2f}"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and initialize the configured model reranker."
    )
    parser.add_argument(
        "--provider",
        choices=("flashrank", "cross_encoder"),
        default="flashrank",
    )
    parser.add_argument("--model")
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--max-length", type=int)
    parser.add_argument("--load-env", action="store_true")
    args = parser.parse_args()
    if args.max_length is not None and args.max_length < 1:
        raise SystemExit("--max-length must be >= 1")
    return args


if __name__ == "__main__":
    main()
