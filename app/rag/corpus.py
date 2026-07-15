import json
from pathlib import Path

from langchain_core.documents import Document

from app.rag.git_repository import load_repository_code_documents
from app.rag.loader import load_markdown_chunks


SUPPORTED_SOURCE_TYPES = {"doc", "bug", "code"}
CORPUS_VERSION = "multi-source-v4-git-callgraph"


def load_knowledge_chunks(
    *,
    docs_dir: Path,
    bug_history_path: Path | None,
    codebase_dir: Path | None,
    chunk_size: int,
    chunk_overlap: int,
    source_types: set[str] | None = None,
    git_history_enabled: bool = False,
    git_max_commits: int = 20,
    git_diff_max_chars: int = 12000,
) -> list[Document]:
    selected = SUPPORTED_SOURCE_TYPES if source_types is None else source_types
    unsupported = selected - SUPPORTED_SOURCE_TYPES
    if unsupported:
        raise ValueError(f"Unsupported source types: {sorted(unsupported)}")

    documents: list[Document] = []
    if "doc" in selected:
        documents.extend(
            load_markdown_chunks(
                docs_dir,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )
    if "bug" in selected and bug_history_path is not None:
        documents.extend(load_bug_documents(bug_history_path))
    if "code" in selected and codebase_dir is not None:
        documents.extend(
            load_code_documents(
                codebase_dir,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                git_history_enabled=git_history_enabled,
                git_max_commits=git_max_commits,
                git_diff_max_chars=git_diff_max_chars,
            )
        )
    return documents


def load_bug_documents(path: Path) -> list[Document]:
    if not path.exists():
        return []

    records = json.loads(path.read_text(encoding="utf-8"))
    documents: list[Document] = []
    for bug in records:
        bug_id = str(bug["bug_id"])
        keywords = [str(item) for item in bug.get("keywords", [])]
        related_files = [str(item) for item in bug.get("related_files", [])]
        content = "\n".join(
            [
                f"历史 Bug: {bug_id}",
                f"标题: {bug.get('title', '')}",
                f"模块: {bug.get('module', '')}",
                f"现象: {bug.get('symptom', '')}",
                f"根因: {bug.get('root_cause', '')}",
                f"修复: {bug.get('fix', '')}",
                f"关键词: {' '.join(keywords)}",
                f"相关文件: {' '.join(related_files)}",
            ]
        )
        documents.append(
            Document(
                page_content=content,
                metadata={
                    "source_type": "bug",
                    "source": bug_id,
                    "chunk_id": f"bug::{bug_id}",
                    "parent_id": bug_id,
                    "section": str(bug.get("module", "unknown")),
                    "section_path": str(bug.get("module", "unknown")),
                    "bug_id": bug_id,
                    "title": str(bug.get("title", "")),
                    "module": str(bug.get("module", "")),
                    "symptom": str(bug.get("symptom", "")),
                    "root_cause": str(bug.get("root_cause", "")),
                    "fix": str(bug.get("fix", "")),
                    "keywords_json": json.dumps(keywords, ensure_ascii=False),
                    "related_files_json": json.dumps(
                        related_files,
                        ensure_ascii=False,
                    ),
                },
            )
        )
    return documents


def load_code_documents(
    codebase_dir: Path,
    *,
    chunk_size: int = 300,
    chunk_overlap: int = 50,
    git_history_enabled: bool = False,
    git_max_commits: int = 20,
    git_diff_max_chars: int = 12000,
) -> list[Document]:
    return load_repository_code_documents(
        codebase_dir,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        git_history_enabled=git_history_enabled,
        git_max_commits=git_max_commits,
        git_diff_max_chars=git_diff_max_chars,
    )
