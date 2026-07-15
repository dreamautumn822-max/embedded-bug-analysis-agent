from pathlib import Path

from app.rag.corpus import (
    load_bug_documents,
    load_code_documents,
    load_knowledge_chunks,
)


def test_bug_documents_use_stable_structured_metadata():
    documents = load_bug_documents(Path("data/bugs/bug_history.json"))

    assert len(documents) == 5
    first = documents[0]
    assert first.metadata["source_type"] == "bug"
    assert first.metadata["source"] == "BUG-018"
    assert first.metadata["chunk_id"] == "bug::BUG-018"
    assert "DHCP service starts before bridge interface is ready" in first.page_content


def test_code_documents_use_function_level_ast_chunks():
    documents = load_code_documents(Path("data/codebase"))

    netifd = next(
        doc for doc in documents
        if doc.metadata["source"] == "netifd_reload.c"
        and doc.metadata["symbol"] == "lan_reload_handler"
    )
    assert len(documents) == 8
    assert netifd.metadata["source_type"] == "code"
    assert netifd.metadata["chunk_id"] == "code::netifd_reload.c::lan_reload_handler"
    assert netifd.metadata["start_line"] == 3
    assert netifd.metadata["end_line"] == 6
    assert netifd.metadata["parser"] == "tree_sitter_c"
    assert netifd.page_content.startswith(
        "source file netifd_reload.c netifd reload function symbol"
    )
    assert "restart_dhcp_server" in netifd.page_content


def test_knowledge_loader_can_filter_source_types():
    documents = load_knowledge_chunks(
        docs_dir=Path("data/docs"),
        bug_history_path=Path("data/bugs/bug_history.json"),
        codebase_dir=Path("data/codebase"),
        chunk_size=300,
        chunk_overlap=50,
        source_types={"bug", "code"},
    )

    assert {doc.metadata["source_type"] for doc in documents} == {"bug", "code"}
    assert len(documents) == 13
