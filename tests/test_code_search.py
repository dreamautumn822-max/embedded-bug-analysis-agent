from pathlib import Path

from app.tools.code_search import _tokens, search_codebase


def test_search_codebase_finds_lan_reload_handler():
    results = search_codebase(
        query="restart dhcp server bridge ready",
        codebase_dir=Path("data/codebase"),
        limit=3,
    )

    assert any(result["file"] == "netifd_reload.c" for result in results)
    netifd_result = next(result for result in results if result["file"] == "netifd_reload.c")
    assert "restart_dhcp_server" in netifd_result["snippet"]


def test_search_codebase_finds_wifi_channel_switch():
    results = search_codebase(
        query="wifi channel switch station disconnected",
        codebase_dir=Path("data/codebase"),
        limit=3,
    )

    assert results[0]["file"] == "wifi_manager.c"
    source_line = Path("data/codebase", results[0]["file"]).read_text(encoding="utf-8").splitlines()[
        results[0]["line"] - 1
    ]
    assert source_line.strip()


def test_tokens_split_snake_case_identifiers():
    assert {"restart", "dhcp", "server"} <= _tokens("restart_dhcp_server")
    assert {"channel", "switch"} <= _tokens("on_channel_switch_start")
