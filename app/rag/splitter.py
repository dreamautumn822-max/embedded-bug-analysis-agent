from collections import Counter
import re

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


DEFAULT_CHUNK_SIZE = 300
DEFAULT_CHUNK_OVERLAP = 50
SPLITTER_VERSION = "markdown-header-local-token-v1"

_HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]
_HEADER_KEYS = tuple(key for _, key in _HEADERS_TO_SPLIT_ON)
_TOKEN_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]|[a-zA-Z0-9_./:-]+|[^\s]")
_SEPARATORS = [
    "\n\n",
    "\n",
    "。",
    "！",
    "？",
    ";",
    "；",
    "，",
    ",",
    " ",
    "",
]


def split_markdown_document(
    document: Document,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    _validate_chunk_settings(chunk_size, chunk_overlap)

    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )
    sections = header_splitter.split_text(document.page_content)
    if not sections:
        sections = [Document(page_content=document.page_content, metadata={})]

    token_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=count_approx_tokens,
        separators=_SEPARATORS,
    )

    source = str(document.metadata.get("source", "unknown"))
    path_occurrences: Counter[str] = Counter()
    chunks: list[Document] = []

    for section in sections:
        section_metadata = {**document.metadata, **section.metadata}
        section_path = _section_path(section_metadata)
        path_occurrences[section_path] += 1
        occurrence = path_occurrences[section_path]
        occurrence_suffix = "" if occurrence == 1 else f" [{occurrence}]"
        parent_id = f"{source}::{section_path}{occurrence_suffix}"

        parent = Document(
            page_content=section.page_content,
            metadata={
                **section_metadata,
                "source": source,
                "section": _deepest_section(section_metadata),
                "section_path": section_path,
                "parent_id": parent_id,
                "splitter_version": SPLITTER_VERSION,
            },
        )
        section_chunks = token_splitter.split_documents([parent])

        for chunk_index, chunk in enumerate(section_chunks):
            chunk_id = f"{parent_id}::{chunk_index:03d}"
            chunks.append(
                Document(
                    page_content=chunk.page_content.strip(),
                    metadata={
                        **chunk.metadata,
                        "chunk_id": chunk_id,
                        "chunk_index": chunk_index,
                        "chunk_count": len(section_chunks),
                    },
                )
            )

    return chunks


def count_approx_tokens(text: str) -> int:
    """Count stable local text units without requiring a model tokenizer download."""
    return len(_TOKEN_PATTERN.findall(text))


def _section_path(metadata: dict) -> str:
    headings = [str(metadata[key]).strip() for key in _HEADER_KEYS if metadata.get(key)]
    return " > ".join(headings) if headings else "document"


def _deepest_section(metadata: dict) -> str:
    for key in reversed(_HEADER_KEYS):
        if metadata.get(key):
            return str(metadata[key]).strip()
    return "document"


def _validate_chunk_settings(chunk_size: int, chunk_overlap: int) -> None:
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be >= 0")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
