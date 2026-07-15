from pathlib import Path

import pytest

from app.rag.loader import load_markdown_chunks, load_markdown_docs
from app.rag.splitter import count_approx_tokens


def test_load_markdown_docs_reads_domain_docs():
    docs = load_markdown_docs(Path("data/docs"))

    assert len(docs) == 5
    assert any(doc.metadata["source"] == "dhcp.md" for doc in docs)
    assert any("DHCP server" in doc.page_content for doc in docs)


def test_load_markdown_chunks_preserves_sections_and_stable_ids(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "network.md").write_text(
        "# 网络模块\n\n## DHCP 启动\n\n"
        + "DHCP 必须等待 bridge ready。" * 12
        + "\n\n## Wi-Fi 信道\n\n信道切换期间不能清理 station table。",
        encoding="utf-8",
    )

    first = load_markdown_chunks(docs_dir, chunk_size=35, chunk_overlap=5)
    repeated = load_markdown_chunks(docs_dir, chunk_size=35, chunk_overlap=5)

    assert len(first) > 2
    assert [chunk.metadata["chunk_id"] for chunk in first] == [
        chunk.metadata["chunk_id"] for chunk in repeated
    ]
    assert len({chunk.metadata["chunk_id"] for chunk in first}) == len(first)
    assert all(chunk.metadata["source"] == "network.md" for chunk in first)
    assert all(chunk.metadata["parent_id"] for chunk in first)
    assert all(chunk.metadata["section_path"] for chunk in first)
    assert all(chunk.metadata["chunk_count"] >= 1 for chunk in first)
    assert any(chunk.metadata["section"] == "DHCP 启动" for chunk in first)
    assert any(chunk.metadata["section"] == "Wi-Fi 信道" for chunk in first)
    assert all(count_approx_tokens(chunk.page_content) <= 35 for chunk in first)


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap"),
    [(0, 0), (10, -1), (10, 10), (10, 11)],
)
def test_load_markdown_chunks_rejects_invalid_sizes(
    tmp_path: Path,
    chunk_size: int,
    chunk_overlap: int,
):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "doc.md").write_text("# Doc\n\ncontent", encoding="utf-8")

    with pytest.raises(ValueError):
        load_markdown_chunks(
            docs_dir,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
