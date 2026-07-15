import os
import sqlite3
from functools import lru_cache
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from app.paths import PROJECT_ROOT


DEFAULT_CHECKPOINT_PATH = PROJECT_ROOT / "run" / "bug_analysis_checkpoints.sqlite"


def checkpoint_path_from_env() -> Path:
    path = Path(
        os.getenv("LANGGRAPH_CHECKPOINT_PATH", str(DEFAULT_CHECKPOINT_PATH))
    ).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def get_sqlite_checkpointer(path: Path | str | None = None) -> SqliteSaver:
    resolved = Path(path).resolve() if path is not None else checkpoint_path_from_env()
    return _cached_sqlite_checkpointer(str(resolved))


@lru_cache(maxsize=8)
def _cached_sqlite_checkpointer(path: str) -> SqliteSaver:
    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        database_path,
        timeout=30,
        check_same_thread=False,
    )
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=30000")
    checkpointer = SqliteSaver(connection)
    checkpointer.setup()
    return checkpointer
