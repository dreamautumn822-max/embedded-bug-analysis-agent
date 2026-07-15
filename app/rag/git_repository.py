import json
from pathlib import Path
import subprocess

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.code_parser import load_c_function_documents
from app.rag.splitter import count_approx_tokens


SOURCE_SUFFIXES = {".c", ".h"}
CONFIG_NAMES = {"Kconfig", "Makefile", "CMakeLists.txt", ".config"}
CONFIG_SUFFIXES = {".mk", ".cmake", ".conf"}
EXCLUDED_DIRECTORIES = {
    ".git",
    ".venv",
    "build",
    "dist",
    "node_modules",
    "out",
    "run",
    "third_party",
    "vendor",
}


def load_repository_code_documents(
    repository_path: Path,
    *,
    chunk_size: int,
    chunk_overlap: int,
    git_history_enabled: bool,
    git_max_commits: int,
    git_diff_max_chars: int,
) -> list[Document]:
    if not repository_path.exists():
        return []

    revision = repository_revision(repository_path)
    documents: list[Document] = []
    for source_path in discover_repository_files(repository_path, SOURCE_SUFFIXES):
        documents.extend(
            load_c_function_documents(
                source_path,
                repository_root=repository_path,
                repository_revision=revision,
            )
        )
    documents = enrich_call_graph(documents)
    documents.extend(
        load_build_config_documents(
            repository_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            repository_revision=revision,
        )
    )
    if git_history_enabled:
        documents.extend(
            load_commit_diff_documents(
                repository_path,
                max_commits=git_max_commits,
                max_diff_chars=git_diff_max_chars,
            )
        )
    return documents


def discover_repository_files(
    repository_path: Path,
    suffixes: set[str],
) -> list[Path]:
    return sorted(
        path
        for path in repository_path.rglob("*")
        if path.is_file()
        and path.suffix in suffixes
        and not any(part in EXCLUDED_DIRECTORIES for part in path.parts)
    )


def enrich_call_graph(documents: list[Document]) -> list[Document]:
    symbols = {
        str(document.metadata.get("symbol"))
        for document in documents
        if document.metadata.get("code_kind") == "function"
    }
    callers: dict[str, set[str]] = {symbol: set() for symbol in symbols}
    for document in documents:
        caller = str(document.metadata.get("symbol", ""))
        for callee in _json_list(document.metadata.get("calls_json")):
            if callee in callers:
                callers[callee].add(caller)

    enriched: list[Document] = []
    for document in documents:
        metadata = dict(document.metadata)
        symbol = str(metadata.get("symbol", ""))
        callees = _json_list(metadata.get("calls_json"))
        incoming = sorted(callers.get(symbol, set()))
        metadata["callers_json"] = json.dumps(incoming, ensure_ascii=False)
        if metadata.get("code_kind") == "function":
            graph_line = (
                f"call graph callers {' '.join(incoming)} "
                f"callees {' '.join(callees)}"
            )
            lines = document.page_content.splitlines()
            content = "\n".join([lines[0], graph_line, *lines[1:]])
            metadata["search_header_lines"] = 2
        else:
            content = document.page_content
        enriched.append(Document(page_content=content, metadata=metadata))
    return enriched


def load_build_config_documents(
    repository_path: Path,
    *,
    chunk_size: int,
    chunk_overlap: int,
    repository_revision: str,
) -> list[Document]:
    paths = sorted(
        path
        for path in repository_path.rglob("*")
        if path.is_file()
        and (path.name in CONFIG_NAMES or path.suffix in CONFIG_SUFFIXES)
        and not any(part in EXCLUDED_DIRECTORIES for part in path.parts)
    )
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=count_approx_tokens,
        separators=["\n\n", "\n", " ", ""],
    )
    documents: list[Document] = []
    for path in paths:
        source = path.relative_to(repository_path).as_posix()
        raw = path.read_text(encoding="utf-8", errors="replace")
        chunks = splitter.split_text(raw) or [raw]
        for index, chunk in enumerate(chunks):
            header = f"build config file {source} repository revision {repository_revision}"
            documents.append(
                Document(
                    page_content=f"{header}\n{chunk.strip()}",
                    metadata={
                        "source_type": "code",
                        "source": source,
                        "chunk_id": f"code::{source}::config::{index:03d}",
                        "parent_id": source,
                        "section": "build_config",
                        "section_path": f"{source} > build_config",
                        "symbol": "build_config",
                        "path": source,
                        "start_line": 1,
                        "end_line": max(1, len(raw.splitlines())),
                        "parser": "text_config",
                        "parse_has_error": False,
                        "code_kind": "build_config",
                        "calls_json": "[]",
                        "callers_json": "[]",
                        "preprocessor_context": "",
                        "repository_revision": repository_revision,
                        "search_header_lines": 1,
                    },
                )
            )
    return documents


def load_commit_diff_documents(
    repository_path: Path,
    *,
    max_commits: int,
    max_diff_chars: int,
) -> list[Document]:
    if not _is_repository_root(repository_path):
        return []
    log_output = _run_git(
        repository_path,
        [
            "log",
            "-n",
            str(max_commits),
            "--date=iso-strict",
            "--pretty=format:%H%x1f%aI%x1f%s%x1e",
        ],
    )
    documents: list[Document] = []
    for record in log_output.split("\x1e"):
        record = record.strip()
        if not record:
            continue
        commit_sha, commit_date, subject = record.split("\x1f", maxsplit=2)
        changed_files = _changed_files(repository_path, commit_sha)
        if not changed_files:
            continue
        diff = _run_git(
            repository_path,
            [
                "show",
                "--format=",
                "--no-ext-diff",
                "--no-color",
                "--unified=3",
                commit_sha,
                "--",
                "*.c",
                "*.h",
                "*.mk",
                "*.cmake",
                "Kconfig",
                "Makefile",
                "CMakeLists.txt",
            ],
        )
        if not diff.strip():
            continue
        if len(diff) > max_diff_chars:
            diff = f"{diff[:max_diff_chars].rstrip()}\n... diff truncated ..."
        short_sha = commit_sha[:12]
        source = f"git/{short_sha}"
        content = "\n".join(
            [
                f"git commit {commit_sha}",
                f"subject {subject}",
                f"date {commit_date}",
                f"changed files {' '.join(changed_files)}",
                diff.strip(),
            ]
        )
        documents.append(
            Document(
                page_content=content,
                metadata={
                    "source_type": "code",
                    "source": source,
                    "chunk_id": f"code::git_commit::{commit_sha}",
                    "parent_id": commit_sha,
                    "section": f"commit:{short_sha}",
                    "section_path": f"git history > {short_sha}",
                    "symbol": f"commit:{short_sha}",
                    "path": f"git:{commit_sha}",
                    "start_line": 1,
                    "end_line": max(1, len(diff.splitlines())),
                    "parser": "git_diff",
                    "parse_has_error": False,
                    "code_kind": "commit_diff",
                    "calls_json": "[]",
                    "callers_json": "[]",
                    "preprocessor_context": "",
                    "repository_revision": commit_sha,
                    "commit_sha": commit_sha,
                    "commit_subject": subject,
                    "commit_date": commit_date,
                    "changed_files_json": json.dumps(
                        changed_files,
                        ensure_ascii=False,
                    ),
                    "search_header_lines": 4,
                },
            )
        )
    return documents


def repository_revision(repository_path: Path) -> str:
    if not _is_repository_root(repository_path):
        return "working-tree"
    return _run_git(repository_path, ["rev-parse", "HEAD"]).strip()


def _changed_files(repository_path: Path, commit_sha: str) -> list[str]:
    output = _run_git(
        repository_path,
        [
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit_sha,
        ],
    )
    return [
        path
        for path in output.splitlines()
        if Path(path).suffix in SOURCE_SUFFIXES | CONFIG_SUFFIXES
        or Path(path).name in CONFIG_NAMES
    ]


def _is_repository_root(path: Path) -> bool:
    return (path / ".git").exists()


def _run_git(repository_path: Path, arguments: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository_path), *arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout


def _json_list(value: object) -> list[str]:
    if not isinstance(value, str):
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []
