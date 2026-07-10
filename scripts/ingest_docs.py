from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.paths import DOCS_DIR
from app.rag.vector_store import build_vector_store


if __name__ == "__main__":
    build_vector_store(
        docs_dir=DOCS_DIR,
        persist_dir=PROJECT_ROOT / ".chroma",
        use_fake_embeddings=True,
    )
    print("Indexed documents into .chroma")
