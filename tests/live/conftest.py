"""Live fixtures are only executed after explicit opt-in."""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv


@pytest.fixture(scope="session")
def live_rag():
    from specialist.rag import RAGSystem

    return RAGSystem()


@pytest.fixture
def live_service(live_rag, monkeypatch, server_factory):
    from specialist import answer
    from specialist.server import app

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if not os.getenv("GROQ_API_KEY"):
        pytest.fail(
            "Live end-to-end tests require GROQ_API_KEY in .env or the environment."
        )
    monkeypatch.setattr(answer, "get_rag", lambda: live_rag)
    return server_factory(app)
