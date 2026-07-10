from pathlib import Path

from langchain_core.documents import Document


def load_markdown_docs(docs_dir: Path) -> list[Document]:
    documents: list[Document] = []
    for path in sorted(docs_dir.glob("*.md")):
        documents.append(
            Document(
                page_content=path.read_text(encoding="utf-8"),
                metadata={"source": path.name},
            )
        )
    return documents
