import argparse
import getpass
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.security.auth import hash_api_key


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hash a Bug Agent API key for environment configuration.",
    )
    parser.add_argument("--key", help="Prefer interactive input to avoid shell history")
    args = parser.parse_args()
    api_key = args.key or getpass.getpass("API key: ")
    if len(api_key) < 16:
        print("API keys must contain at least 16 characters", file=sys.stderr)
        return 1
    print(hash_api_key(api_key))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
