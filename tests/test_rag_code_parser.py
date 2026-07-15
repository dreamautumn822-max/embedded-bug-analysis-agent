from pathlib import Path

from app.rag.code_parser import load_c_function_documents


def test_parser_keeps_leading_comment_and_absolute_lines(tmp_path: Path):
    source = tmp_path / "bridge_state.c"
    source.write_text(
        '#include "bridge.h"\n\n'
        "/* Bridge must be ready before DHCP starts. */\n"
        "int restart_after_ready(const char *name) {\n"
        "    if (is_ready(name)) {\n"
        "        return restart_dhcp();\n"
        "    }\n"
        "    return -1;\n"
        "}\n\n"
        "void mark_reload(void) { set_reload(1); }\n",
        encoding="utf-8",
    )

    documents = load_c_function_documents(source)

    assert [doc.metadata["symbol"] for doc in documents] == [
        "restart_after_ready",
        "mark_reload",
    ]
    first = documents[0]
    assert first.metadata["start_line"] == 3
    assert first.metadata["end_line"] == 9
    assert "Bridge must be ready" in first.page_content
    assert first.metadata["parse_has_error"] is False


def test_parser_falls_back_to_file_chunk_when_no_function_exists(tmp_path: Path):
    source = tmp_path / "constants.c"
    source.write_text("#define DHCP_RETRY_MAX 3\n", encoding="utf-8")

    documents = load_c_function_documents(source)

    assert len(documents) == 1
    assert documents[0].metadata["symbol"] == "source_file"
    assert documents[0].metadata["chunk_id"] == "code::constants.c::source_file"


def test_parser_extracts_calls_and_preprocessor_context(tmp_path: Path):
    source = tmp_path / "feature.c"
    source.write_text(
        "#ifdef CONFIG_DHCP_FAST_RELOAD\n"
        "int reload_dhcp(void) {\n"
        "    bridge_wait_ready();\n"
        "    return restart_dhcp_server();\n"
        "}\n"
        "#endif\n",
        encoding="utf-8",
    )

    document = load_c_function_documents(source)[0]

    assert document.metadata["calls_json"] == (
        '["bridge_wait_ready", "restart_dhcp_server"]'
    )
    assert document.metadata["preprocessor_context"] == (
        "#ifdef CONFIG_DHCP_FAST_RELOAD"
    )
    assert "CONFIG_DHCP_FAST_RELOAD" in document.page_content
