import argparse
from collections import Counter
from dataclasses import replace
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.config import RAGSettings
from app.rag.corpus import load_code_documents
from app.rag.vector_store import build_vector_store, collection_name


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Index a checked-out C/C++-style Git repository for bug analysis.",
    )
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--max-commits", type=int, default=20)
    parser.add_argument("--without-history", action="store_true")
    args = parser.parse_args()

    repository = args.repo.expanduser().resolve()
    if not repository.is_dir():
        print(f"Repository directory does not exist: {repository}", file=sys.stderr)
        return 1
    if args.max_commits < 1:
        print("--max-commits must be >= 1", file=sys.stderr)
        return 1

    settings = replace(
        RAGSettings.from_env(),
        codebase_dir=repository,
        git_history_enabled=not args.without_history,
        git_max_commits=args.max_commits,
    )
    documents = load_code_documents(
        repository,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        git_history_enabled=settings.git_history_enabled,
        git_max_commits=settings.git_max_commits,
        git_diff_max_chars=settings.git_diff_max_chars,
    )
    build_vector_store(settings=settings)

    kinds = Counter(str(document.metadata.get("code_kind")) for document in documents)
    print(f"repository={repository}")
    print(f"collection={collection_name(settings)}")
    print(f"indexed_code_chunks={len(documents)}")
    for kind, count in sorted(kinds.items()):
        print(f"{kind}={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
