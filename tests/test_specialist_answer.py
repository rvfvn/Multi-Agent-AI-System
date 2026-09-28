import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from groq import APIConnectionError
from pydantic import ValidationError

from specialist import answer
from specialist.models import LLMAnswer, SpecialistResult


@pytest.fixture
def generation(monkeypatch):
    sources = ["network.md", "hardware.md", "software.md", "security.md"]
    documents = [{"source": s, "content": f"FULL DOCUMENT {s}"} for s in sources]
    matches = [
        {"source": s, "content": f"CHUNK {s}", "score": 4 - i}
        for i, s in enumerate(
            ["network.md", "network.md", "hardware.md", "software.md", "security.md"]
        )
    ]
    rag = SimpleNamespace(
        chunks=list(range(12)), documents=documents, retrieve=Mock(return_value=matches)
    )
    client = Mock()
    monkeypatch.setattr(answer, "get_rag", Mock(return_value=rag))
    monkeypatch.setattr(answer, "get_groq_client", Mock(return_value=client))

    def set_content(content):
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    data = {
        "supported": True,
        "category": " network ",
        "resolution": " Reconnect. ",
        "sources": [" network.md ", "network.md"],
    }
    set_content(json.dumps(data))
    return rag, client, data, set_content


def test_context_selection_and_valid_result(generation):
    rag, client, _, _ = generation
    result = answer.answer_support_question("Wi-Fi issue")
    assert result.model_dump() == {
        "category": "Network",
        "resolution": "Reconnect.",
        "sources": ["network.md"],
    }
    rag.retrieve.assert_called_once_with("Wi-Fi issue", top_k=8)
    prompt = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "Wi-Fi issue" in prompt
    for source in ["network.md", "hardware.md", "software.md"]:
        assert f"FULL DOCUMENT {source}" in prompt
    assert "FULL DOCUMENT security.md" not in prompt
    assert prompt.count("SOURCE: network.md") == 1


@pytest.mark.parametrize("content", ["not JSON", "[]", "{}", "null"])
def test_malformed_json(generation, content):
    generation[3](content)
    with pytest.raises(ValueError, match="malformed"):
        answer.answer_support_question("question")


@pytest.mark.parametrize(
    "changes",
    [
        {"supported": "true"},
        {"supported": 1},
        {"category": 8},
        {"resolution": []},
        {"sources": "network.md"},
        {"sources": [3]},
        {"unexpected": "field"},
    ],
)
def test_wrong_llm_types(generation, changes):
    _, _, data, set_content = generation
    set_content(json.dumps({**data, **changes}))
    with pytest.raises(ValueError, match="malformed"):
        answer.answer_support_question("question")


@pytest.mark.parametrize("field", ["supported", "category", "resolution", "sources"])
def test_missing_llm_field(field, generation):
    data = generation[2].copy()
    del data[field]
    generation[3](json.dumps(data))
    with pytest.raises(ValueError, match="malformed"):
        answer.answer_support_question("question")


@pytest.mark.parametrize("content", [None, "", "   "])
def test_empty_content(content, generation):
    generation[3](content)
    with pytest.raises(ValueError, match="empty"):
        answer.answer_support_question("question")


def test_no_choices(generation):
    generation[1].chat.completions.create.return_value = SimpleNamespace(choices=[])
    with pytest.raises(ValueError, match="empty"):
        answer.answer_support_question("question")


def test_unsupported_answer(generation):
    generation[3](
        json.dumps(
            {"supported": False, "category": "", "resolution": "", "sources": []}
        )
    )
    with pytest.raises(ValueError, match="No sufficiently relevant"):
        answer.answer_support_question("unrelated question")


@pytest.mark.parametrize(
    "changes",
    [
        {"category": "Other"},
        {"category": " "},
        {"resolution": " "},
        {"sources": []},
        {"sources": [" "]},
    ],
)
def test_unusable_supported_answer(changes, generation):
    generation[3](json.dumps({**generation[2], **changes}))
    with pytest.raises(ValueError, match="usable"):
        answer.answer_support_question("question")


@pytest.mark.parametrize("source", ["invented.md", "security.md"])
def test_sources_must_be_selected_context(source, generation):
    generation[3](json.dumps({**generation[2], "sources": [source]}))
    with pytest.raises(ValueError, match="sources"):
        answer.answer_support_question("question")


@pytest.mark.parametrize(
    "category",
    ["Account Access", "Network", "Hardware", "Software", "Email", "Security"],
)
def test_all_specialist_categories_are_valid(category):
    result = SpecialistResult(
        category=f" {category.lower()} ",
        resolution=" guidance ",
        sources=[" ref.md ", "ref.md"],
    )
    assert result.category == category
    assert result.resolution == "guidance" and result.sources == ["ref.md"]


@pytest.mark.parametrize(
    "changes",
    [
        {"category": "Other"},
        {"resolution": " "},
        {"sources": [" "]},
        {"sources": [1]},
        {"sources": []},
    ],
)
def test_result_model_rejects_invalid_values(changes, support_result):
    with pytest.raises(ValidationError):
        SpecialistResult(**{**support_result, **changes})


def test_raw_model_allows_unsupported_empty_fields():
    assert (
        LLMAnswer(supported=False, category="", resolution="", sources=[]).supported
        is False
    )


@pytest.mark.parametrize("empty_chunks", [True, False])
def test_empty_retrieval_does_not_call_groq(empty_chunks, generation):
    rag, client, _, _ = generation
    if empty_chunks:
        rag.chunks = []
    else:
        rag.retrieve.return_value = []
    with pytest.raises(ValueError):
        answer.answer_support_question("question")
    client.chat.completions.create.assert_not_called()


def test_retrieval_failure_does_not_call_groq(generation):
    generation[0].retrieve.side_effect = RuntimeError("retrieval failed")
    with pytest.raises(RuntimeError, match="retrieval failed"):
        answer.answer_support_question("question")
    generation[1].chat.completions.create.assert_not_called()


def test_groq_failure_propagates(generation):
    generation[1].chat.completions.create.side_effect = APIConnectionError(
        request=httpx.Request("POST", "https://example.invalid")
    )
    with pytest.raises(APIConnectionError):
        answer.answer_support_question("question")


def test_missing_api_key_fails_before_client_creation(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        answer.get_groq_client()
