from unittest.mock import Mock

import numpy as np
import pytest

from specialist.rag import RAGSystem


@pytest.fixture
def rag(small_kb, fake_models):
    return RAGSystem(small_kb, embedding_model=fake_models[0], reranker=fake_models[1])


@pytest.mark.parametrize("kind", ["missing", "file", "empty", "blank"])
def test_unusable_kb_rejected_before_model_loading(kind, tmp_path):
    path = tmp_path
    if kind == "missing":
        path = tmp_path / "missing"
    elif kind == "file":
        path = tmp_path / "not-directory.md"
        path.write_text("text")
    elif kind == "blank":
        (tmp_path / "blank.md").write_text(" \n ")
    # Global test guard fails if real model initialization is attempted.
    with pytest.raises(ValueError, match="Knowledge"):
        RAGSystem(path)


def test_chunking_preserves_sources_and_content(tmp_path, fake_models):
    text = "\n".join(
        f"Network procedure step {i}: reconnect and verify." for i in range(60)
    )
    (tmp_path / "network.md").write_text(text)
    (tmp_path / "ignore.txt").write_text("Not a Markdown document")
    rag = RAGSystem(tmp_path, embedding_model=fake_models[0], reranker=fake_models[1])
    assert rag.documents == [{"source": "network.md", "content": text}]
    assert len(rag.chunks) > 1
    assert all(
        c["source"] == "network.md"
        and c["content"] in text
        and len(c["content"]) <= 500
        for c in rag.chunks
    )
    assert rag.index.ntotal == len(rag.chunks)


def test_real_faiss_caps_candidates_and_preserves_result_contract(rag):
    result = rag.retrieve(" network ", top_k=50)
    assert len(result) == 2
    assert {r["source"] for r in result} == {"network.md", "account.md"}
    assert all(
        set(r) == {"source", "content", "score"} and isinstance(r["score"], float)
        for r in result
    )
    assert result[0]["score"] >= result[1]["score"]
    rag.embedding_model.encode.assert_called_with(["network"], convert_to_numpy=True)


@pytest.mark.parametrize("query", [None, 5, "", "   "])
def test_invalid_query_does_not_embed(query, rag):
    rag.embedding_model.reset_mock()
    with pytest.raises(ValueError, match="Query"):
        rag.retrieve(query)
    rag.embedding_model.encode.assert_not_called()


@pytest.mark.parametrize("top_k", [0, -1, True, False, 2.5, "2"])
def test_invalid_top_k(top_k, rag):
    with pytest.raises(ValueError, match="top_k"):
        rag.retrieve("network", top_k=top_k)


def test_reranking_changes_initial_order(rag):
    rag.index = Mock()
    rag.index.search.return_value = (np.array([[0, 1]]), np.array([[0, 1]]))
    rag.reranker.predict.side_effect = None
    rag.reranker.predict.return_value = [0.1, 0.9]
    result = rag.retrieve("question")
    assert [r["source"] for r in result] == [
        rag.chunks[1]["source"],
        rag.chunks[0]["source"],
    ]
    assert [pair[1] for pair in rag.reranker.predict.call_args.args[0]] == [
        c["content"] for c in rag.chunks
    ]


@pytest.mark.parametrize("indices", [[-1, 99], [-5, -1]])
def test_invalid_indices_skip_reranking(indices, rag):
    rag.index = Mock()
    rag.index.search.return_value = (np.zeros((1, 2)), np.array([indices]))
    assert rag.retrieve("question") == []
    rag.reranker.predict.assert_not_called()


def test_mixed_valid_and_invalid_indices(rag):
    rag.index = Mock()
    rag.index.search.return_value = (np.zeros((1, 2)), np.array([[-1, 0]]))
    result = rag.retrieve("question")
    assert len(result) == 1 and result[0]["source"] == rag.chunks[0]["source"]


def test_retrieval_model_failure_propagates(rag):
    rag.embedding_model.encode.side_effect = RuntimeError("embedding failed")
    with pytest.raises(RuntimeError, match="embedding failed"):
        rag.retrieve("question")
