"""Load .env from repo root."""

from __future__ import annotations

import os
from pathlib import Path

from .paths import PKG_ROOT, REPO_ROOT


def load_env() -> None:
    for env_path in (REPO_ROOT / ".env", PKG_ROOT / ".env", Path.cwd() / ".env"):
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
