import json
from pathlib import Path
import subprocess

from app.rag.git_repository import load_repository_code_documents


def _git(repository: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "firmware"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.email", "test@example.invalid")
    _git(repository, "config", "user.name", "Test User")
    (repository / "Kconfig").write_text(
        "config DHCP_FAST_RELOAD\n    bool \"Fast DHCP reload\"\n",
        encoding="utf-8",
    )
    (repository / "dhcp.c").write_text(
        "int bridge_wait_ready(void) { return 1; }\n"
        "int restart_dhcp(void) {\n"
        "    bridge_wait_ready();\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )
    _git(repository, "add", "Kconfig", "dhcp.c")
    _git(repository, "commit", "-m", "fix dhcp restart ordering")
    return repository


def test_repository_loader_builds_call_graph_and_config_chunks(tmp_path: Path):
    documents = load_repository_code_documents(
        _repository(tmp_path),
        chunk_size=300,
        chunk_overlap=50,
        git_history_enabled=False,
        git_max_commits=10,
        git_diff_max_chars=4000,
    )

    restart = next(doc for doc in documents if doc.metadata["symbol"] == "restart_dhcp")
    bridge = next(
        doc for doc in documents if doc.metadata["symbol"] == "bridge_wait_ready"
    )
    config = next(doc for doc in documents if doc.metadata["code_kind"] == "build_config")
    assert json.loads(restart.metadata["calls_json"]) == ["bridge_wait_ready"]
    assert json.loads(bridge.metadata["callers_json"]) == ["restart_dhcp"]
    assert "callers restart_dhcp" in bridge.page_content
    assert config.metadata["source"] == "Kconfig"


def test_repository_loader_indexes_commit_diff(tmp_path: Path):
    documents = load_repository_code_documents(
        _repository(tmp_path),
        chunk_size=300,
        chunk_overlap=50,
        git_history_enabled=True,
        git_max_commits=10,
        git_diff_max_chars=4000,
    )

    commit = next(doc for doc in documents if doc.metadata["code_kind"] == "commit_diff")
    assert commit.metadata["commit_subject"] == "fix dhcp restart ordering"
    assert "dhcp.c" in json.loads(commit.metadata["changed_files_json"])
    assert "+int restart_dhcp" in commit.page_content
