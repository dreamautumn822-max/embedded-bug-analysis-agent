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
    document_count = len(store.get(include=[]).get("ids", []))
    print(
        f"Indexed {document_count} documents into {settings.persist_dir} "
        f"(collection={collection_name(settings)}, provider={settings.embedding_provider})"
    )
