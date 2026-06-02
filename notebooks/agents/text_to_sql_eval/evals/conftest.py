from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parent.parent
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(PKG_ROOT))

from agent.env import load_env
from agent.build_agent import make_llm
from evals.runner import run_question


@pytest.fixture(scope="session", autouse=True)
def _env():
    load_env()


@pytest.fixture(scope="session")
def llm():
    return make_llm()


@pytest.fixture
def run(llm):
    def sync_run(question: str):
        return asyncio.run(run_question(llm, question))

    return sync_run
