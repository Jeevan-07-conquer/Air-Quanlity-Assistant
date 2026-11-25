"""Minimal zero-dependency .env file loader (never overwrites existing environment variables)."""

import os
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_env_file(env_path: Optional[Path] = None) -> None:
    """Populate os.environ defaults from a local .env file if it exists."""
    target = env_path or (PROJECT_ROOT / ".env")
    if not target.is_file():
        return

    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]

        os.environ.setdefault(key, value)
