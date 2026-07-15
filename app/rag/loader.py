from pathlib import Path

from langchain_core.documents import Document

from app.rag.splitter import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    split_markdown_document,
)


def load_markdown_docs(docs_dir: Path) -> list[Document]:
    documents: list[Document] = []
    for path in sorted(docs_dir.glob("*.md")):
        documents.append(
            Document(
                page_content=path.read_text(encoding="utf-8"),
                metadata={"source": path.name, "source_type": "doc"},
            )
        )
    return documents


def load_markdown_chunks(
    docs_dir: Path,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    chunks: list[Document] = []
    for document in load_markdown_docs(docs_dir):
        chunks.extend(
            split_markdown_document(
                document,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )
    return chunks
