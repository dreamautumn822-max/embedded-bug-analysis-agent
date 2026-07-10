from pathlib import Path

from langchain_chroma import Chroma

from app.rag.vector_store import build_embeddings


def create_doc_retriever(persist_dir: Path, use_fake_embeddings: bool = False):
    embeddings = build_embeddings(use_fake=use_fake_embeddings)
    store = Chroma(
        persist_directory=str(persist_dir),
        embedding_function=embeddings,
        collection_name="embedded_bug_docs",
    )
    return store.as_retriever(search_kwargs={"k": 3})
