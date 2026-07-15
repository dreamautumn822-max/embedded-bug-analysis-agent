from collections.abc import Iterator
import json
from pathlib import Path
import re

from langchain_core.documents import Document
from tree_sitter import Language, Node, Parser
import tree_sitter_c


PARSER_NAME = "tree_sitter_c"
_C_LANGUAGE = Language(tree_sitter_c.language())


def load_c_function_documents(
    source_path: Path,
    *,
    repository_root: Path | None = None,
    repository_revision: str | None = None,
) -> list[Document]:
    source = source_path.read_bytes()
    tree = Parser(_C_LANGUAGE).parse(source)
    source_name = _source_name(source_path, repository_root)
    function_nodes = [
        node for node in _walk_named_nodes(tree.root_node)
        if node.type == "function_definition"
    ]
    if not function_nodes:
        return [
            _file_fallback_document(
                source_path,
                source_name,
                source,
                tree.root_node.has_error,
                repository_revision,
            )
        ]

    documents: list[Document] = []
    duplicate_counts: dict[str, int] = {}
    for node in function_nodes:
        symbol = _function_symbol(node, source)
        duplicate_counts[symbol] = duplicate_counts.get(symbol, 0) + 1
        occurrence = duplicate_counts[symbol]
        chunk_suffix = symbol if occurrence == 1 else f"{symbol}::{occurrence:03d}"
        start_byte, start_line = _include_leading_comments(node, source)
        end_line = node.end_point.row + 1
        calls = _called_symbols(node, source)
        preprocessor_context = _preprocessor_context(node, source)
        raw_content = source[start_byte : node.end_byte].decode(
            "utf-8",
            errors="replace",
        )
        search_header = _search_header(
            source_name,
            symbol,
            calls=calls,
            preprocessor_context=preprocessor_context,
        )
        documents.append(
            Document(
                page_content=f"{search_header}\n{raw_content}",
                metadata={
                    "source_type": "code",
                    "source": source_name,
                    "chunk_id": f"code::{source_name}::{chunk_suffix}",
                    "parent_id": source_name,
                    "section": symbol,
                    "section_path": f"{source_name} > {symbol}",
                    "symbol": symbol,
                    "path": source_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "parser": PARSER_NAME,
                    "parse_has_error": tree.root_node.has_error,
                    "code_kind": "function",
                    "calls_json": json.dumps(calls, ensure_ascii=False),
                    "callers_json": "[]",
                    "preprocessor_context": preprocessor_context,
                    "repository_revision": repository_revision or "",
                    "search_header_lines": 1,
                },
            )
        )
    return documents


def _walk_named_nodes(root: Node) -> Iterator[Node]:
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.named_children))


def _function_symbol(function_node: Node, source: bytes) -> str:
    declarator = function_node.child_by_field_name("declarator")
    identifier = _declarator_identifier(declarator)
    if identifier is None:
        return f"anonymous_line_{function_node.start_point.row + 1}"
    return source[identifier.start_byte : identifier.end_byte].decode(
        "utf-8",
        errors="replace",
    )


def _declarator_identifier(node: Node | None) -> Node | None:
    if node is None:
        return None
    if node.type in {"identifier", "field_identifier"}:
        return node

    nested = node.child_by_field_name("declarator")
    if nested is not None:
        identifier = _declarator_identifier(nested)
        if identifier is not None:
            return identifier

    for child in node.named_children:
        identifier = _declarator_identifier(child)
        if identifier is not None:
            return identifier
    return None


def _include_leading_comments(function_node: Node, source: bytes) -> tuple[int, int]:
    start_byte = function_node.start_byte
    start_line = function_node.start_point.row + 1
    previous = function_node.prev_named_sibling
    while previous is not None and previous.type == "comment":
        gap = source[previous.end_byte:start_byte]
        if gap.strip() or gap.count(b"\n") > 2:
            break
        start_byte = previous.start_byte
        start_line = previous.start_point.row + 1
        previous = previous.prev_named_sibling
    return start_byte, start_line


def _called_symbols(function_node: Node, source: bytes) -> list[str]:
    body = function_node.child_by_field_name("body")
    if body is None:
        return []

    calls: set[str] = set()
    for node in _walk_named_nodes(body):
        if node.type != "call_expression":
            continue
        callee = node.child_by_field_name("function")
        if callee is None:
            continue
        value = source[callee.start_byte : callee.end_byte].decode(
            "utf-8",
            errors="replace",
        )
        identifiers = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", value)
        if identifiers:
            calls.add(identifiers[-1])
    return sorted(calls)


def _preprocessor_context(function_node: Node, source: bytes) -> str:
    directives: list[str] = []
    current = function_node.parent
    while current is not None:
        if current.type in {"preproc_if", "preproc_ifdef", "preproc_elif"}:
            first_line = source[current.start_byte : current.end_byte].splitlines()[0]
            directives.append(first_line.decode("utf-8", errors="replace").strip())
        current = current.parent
    return " | ".join(reversed(directives))


def _source_name(source_path: Path, repository_root: Path | None) -> str:
    if repository_root is None:
        return source_path.name
    try:
        return source_path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        return source_path.name


def _search_header(
    source_name: str,
    symbol: str,
    *,
    calls: list[str] | None = None,
    preprocessor_context: str = "",
) -> str:
    source_path = Path(source_name)
    file_terms = " ".join(
        part for part in source_path.stem.replace("-", "_").split("_") if part
    )
    symbol_terms = " ".join(part for part in symbol.split("_") if part)
    return (
        f"source file {source_name} {file_terms} "
        f"function symbol {symbol} {symbol_terms} "
        f"calls {' '.join(calls or [])} preprocessor {preprocessor_context}"
    )


def _file_fallback_document(
    source_path: Path,
    source_name: str,
    source: bytes,
    parse_has_error: bool,
    repository_revision: str | None,
) -> Document:
    raw_content = source.decode("utf-8", errors="replace")
    end_line = max(1, len(raw_content.splitlines()))
    return Document(
        page_content=f"{_search_header(source_name, 'source_file')}\n{raw_content}",
        metadata={
            "source_type": "code",
            "source": source_name,
            "chunk_id": f"code::{source_name}::source_file",
            "parent_id": source_name,
            "section": "source_file",
            "section_path": source_name,
            "symbol": "source_file",
            "path": source_name,
            "start_line": 1,
            "end_line": end_line,
            "parser": PARSER_NAME,
            "parse_has_error": parse_has_error,
            "code_kind": "source_file",
            "calls_json": "[]",
            "callers_json": "[]",
            "preprocessor_context": "",
            "repository_revision": repository_revision or "",
            "search_header_lines": 1,
        },
    )
