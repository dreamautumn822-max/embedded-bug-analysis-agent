from pathlib import Path

from app.rag.loader import load_markdown_docs


def test_load_markdown_docs_reads_domain_docs():
    docs = load_markdown_docs(Path("data/docs"))

    assert len(docs) == 5
    assert any(doc.metadata["source"] == "dhcp.md" for doc in docs)
    assert any("DHCP server" in doc.page_content for doc in docs)
