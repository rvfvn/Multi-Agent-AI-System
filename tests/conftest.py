"""Shared fixtures; browser and external-service tests require explicit opt-in."""

import json
import socket
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
import requests
import uvicorn

ROOT = Path(__file__).resolve().parents[1]


def pytest_addoption(parser):
    parser.addoption(
        "--run-browser", action="store_true", help="Run tests requiring Chromium."
    )
    parser.addoption(
        "--run-live",
        action="store_true",
        help="Run real retrieval/Groq tests; may download models and use API quota.",
    )
    parser.addoption(
        "--live-timeout",
        type=float,
        default=180.0,
        help="Polling budget for live tasks after model warmup.",
    )


def pytest_collection_modifyitems(config, items):
    for item in items:
        parts = item.path.relative_to(ROOT / "tests").parts
        if "live" in parts and not config.getoption("--run-live"):
            item.add_marker(pytest.mark.skip(reason="Requires --run-live"))
        if (
            "browser" in parts or item.path.name == "test_end_to_end.py"
        ) and not config.getoption("--run-browser"):
            item.add_marker(pytest.mark.skip(reason="Requires --run-browser"))


@pytest.fixture(autouse=True)
def isolate_specialist_and_block_external_models(request, monkeypatch):
    from specialist import agent, answer, rag

    with agent.task_lock:
        agent.tasks.clear()
    answer.get_rag.cache_clear()
    answer.get_groq_client.cache_clear()
    live = "live" in request.node.path.relative_to(ROOT / "tests").parts
    if not live:

        def forbidden(*args, **kwargs):
            pytest.fail(
                "Offline test attempted to load a real model or Groq client; inject a fake."
            )

        monkeypatch.setattr(rag, "SentenceTransformer", forbidden)
        monkeypatch.setattr(rag, "CrossEncoder", forbidden)
        monkeypatch.setattr(answer, "Groq", forbidden)
        monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    yield
    with agent.task_lock:
        agent.tasks.clear()
    # Tests can replace get_rag/get_groq_client with mocks; clear original cached functions after restoration.
    monkeypatch.undo()
    answer.get_rag.cache_clear()
    answer.get_groq_client.cache_clear()


@pytest.fixture
def support_result():
    return {
        "category": "Network",
        "resolution": "Reconnect the device.",
        "sources": ["network.md"],
    }


@pytest.fixture
def envelope(support_result):
    def make(status="submitted", task_id="task-1", **overrides):
        data = {
            "task_id": task_id,
            "status": status,
            "result": support_result.copy() if status == "completed" else None,
            "error": "No relevant information." if status == "failed" else None,
        }
        data.update(overrides)
        return data

    return make


@pytest.fixture
def http_response():
    def make(data=None, status=200, raw=None):
        response = requests.Response()
        response.status_code = status
        response._content = raw if raw is not None else json.dumps(data).encode()
        response.url = "http://127.0.0.1:8000/tasks"
        return response

    return make


@pytest.fixture
def clock(monkeypatch):
    from requester import a2a_client

    class Clock:
        now = 0.0

        def __init__(self):
            self.sleeps = []

        def monotonic(self):
            return self.now

        def advance(self, seconds):
            self.now += seconds

        def sleep(self, seconds):
            self.sleeps.append(seconds)
            self.advance(seconds)

    fake = Clock()
    # Replace this module's time reference, not the global time module used by servers.
    monkeypatch.setattr(
        a2a_client, "time", SimpleNamespace(monotonic=fake.monotonic, sleep=fake.sleep)
    )
    return fake


@pytest.fixture
def fake_models():
    embeddings = Mock()

    def encode(texts, convert_to_numpy=True):
        return np.array(
            [
                [
                    float("network" in text.lower()),
                    float("account" in text.lower()),
                    1.0,
                ]
                for text in texts
            ],
            dtype=np.float32,
        )

    embeddings.encode.side_effect = encode
    reranker = Mock()
    reranker.predict.side_effect = lambda pairs: np.arange(len(pairs), dtype=float)
    return embeddings, reranker


@pytest.fixture
def small_kb(tmp_path):
    (tmp_path / "network.md").write_text(
        "Network support: reconnect Wi-Fi.", encoding="utf-8"
    )
    (tmp_path / "account.md").write_text(
        "Account support: verify identity before password reset.", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def server_factory():
    """Bind an available loopback port and run real HTTP, with bounded teardown."""
    servers = []

    def start(app):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=host,
                port=port,
                log_level="error",
                timeout_graceful_shutdown=2,
            )
        )
        thread = threading.Thread(
            target=server.run, kwargs={"sockets": [sock]}, daemon=True
        )
        servers.append((server, thread, sock))
        thread.start()
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not server.started:
            pytest.fail("Local test server did not start within five seconds.")
        return f"http://{host}:{port}"

    yield start
    for server, thread, sock in reversed(servers):
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        assert not thread.is_alive(), "Local test server failed to shut down"
