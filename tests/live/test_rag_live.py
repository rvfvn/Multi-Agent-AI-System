import pytest


@pytest.mark.parametrize(
    ("question", "expected_sources"),
    [
        (
            "I forgot my password and cannot log in.",
            {"account_access.md", "password_reset.md"},
        ),
        ("My laptop will not connect to Wi-Fi.", {"network.md"}),
        ("My keyboard stopped working.", {"hardware.md"}),
        ("I cannot install approved software.", {"software.md"}),
        ("My company email is not synchronizing.", {"email.md"}),
        ("I suspect my account was compromised.", {"security.md"}),
    ],
)
def test_relevant_source_in_top_five(question, expected_sources, live_rag):
    matches = live_rag.retrieve(question, top_k=5)
    assert expected_sources.intersection(match["source"] for match in matches), matches
    assert all(match["content"].strip() for match in matches)
    assert [match["score"] for match in matches] == sorted(
        (m["score"] for m in matches), reverse=True
    )
