from pathlib import Path

from app.tools.bug_history_search import search_bug_history


def test_search_bug_history_returns_dhcp_bug():
    results = search_bug_history(
        query="dhcp lease allocation failed after netifd reload",
        bug_history_path=Path("data/bugs/bug_history.json"),
        limit=2,
    )

    assert results[0]["bug_id"] == "BUG-018"
    assert results[0]["score"] > 0
    assert "DHCP service starts before bridge" in results[0]["root_cause"]


def test_search_bug_history_returns_empty_for_unrelated_query():
    results = search_bug_history(
        query="bluetooth pairing battery issue",
        bug_history_path=Path("data/bugs/bug_history.json"),
        limit=2,
    )

    assert results == []
