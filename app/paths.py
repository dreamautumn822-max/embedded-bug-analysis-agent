from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
BUG_HISTORY_PATH = DATA_DIR / "bugs" / "bug_history.json"
CODEBASE_DIR = DATA_DIR / "codebase"
DOCS_DIR = DATA_DIR / "docs"
