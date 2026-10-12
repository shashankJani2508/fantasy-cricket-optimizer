"""Read secrets from the environment, falling back to the project's .env file (never hardcoded)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def env(name):
    if os.environ.get(name):
        return os.environ[name]
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf8").splitlines():
            if line.strip().startswith(name + "="):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v
    return None
