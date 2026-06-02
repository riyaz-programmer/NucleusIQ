"""Load .env from repo root."""

from __future__ import annotations

import os
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PKG_ROOT.parents[2]


def load_env() -> None:
    for env_path in (REPO_ROOT / ".env", PKG_ROOT / ".env", Path.cwd() / ".env"):
        if not env_path.is_file():
            continue
        try:
            from dotenv import load_dotenv

            load_dotenv(env_path)
            return
        except ImportError:
            pass
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
