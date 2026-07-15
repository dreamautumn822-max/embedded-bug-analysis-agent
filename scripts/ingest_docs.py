from pathlib import Path
import sys

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.config import RAGSettings
from app.rag.vector_store import build_vector_store, collection_name


if __name__ == "__main__":
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    settings = RAGSettings.from_env()
    store = build_vector_store(settings=settings)
    chunk_count = len(store.get(include=[]).get("ids", []))
    print(
        f"Indexed {chunk_count} chunks into {settings.persist_dir} "
        f"(collection={collection_name(settings)}, "
        f"provider={settings.embedding_provider}, "
        f"chunk_size={settings.chunk_size}, overlap={settings.chunk_overlap})"
    )
