from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.embeddings import FakeEmbeddings
from langchain_openai import OpenAIEmbeddings

from app.rag.loader import load_markdown_docs


def build_embeddings(use_fake: bool = False):
    if use_fake:
        return FakeEmbeddings(size=1536)
    return OpenAIEmbeddings()


def build_vector_store(
    docs_dir: Path,
    persist_dir: Path,
    use_fake_embeddings: bool = False,
) -> Chroma:
    docs = load_markdown_docs(docs_dir)
    embeddings = build_embeddings(use_fake=use_fake_embeddings)
    return Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=str(persist_dir),
        collection_name="embedded_bug_docs",
    )
