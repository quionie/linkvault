"""Tests for the pure helpers in linkvault.utils."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from linkvault.utils import (
    content_hash,
    cosine_similarity,
    derive_title,
    first_sentences,
    format_relative,
    is_url,
    truncate,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("https://example.com", True),
        ("http://example.com/path?q=1", True),
        ("https://sub.domain.co/a/b", True),
        ("just some text", False),
        ("ftp://example.com", False),
        ("example.com", False),  # no scheme
        ("https://example.com with trailing words", False),
        ("", False),
    ],
)
def test_is_url(text: str, expected: bool) -> None:
    assert is_url(text) is expected


def test_content_hash_is_stable_and_distinct() -> None:
    assert content_hash("a", "b") == content_hash("a", "b")
    assert content_hash("a", "b") != content_hash("b", "a")


def test_truncate() -> None:
    assert truncate("hello world", 20) == "hello world"
    assert truncate("hello world", 8).endswith("…")
    assert len(truncate("hello world", 8)) <= 8


def test_first_sentences() -> None:
    text = "One. Two. Three. Four."
    assert first_sentences(text, 2) == "One. Two."


def test_derive_title() -> None:
    assert derive_title("A neat idea. More detail here.") == "A neat idea."
    assert derive_title("") == "Untitled"


def test_cosine_similarity() -> None:
    assert cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    # Mismatched / empty vectors return 0 rather than raising.
    assert cosine_similarity([], [1, 2]) == 0.0
    assert cosine_similarity([1, 2, 3], [1, 2]) == 0.0


def test_format_relative() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert format_relative(now, now=now) == "just now"
    assert format_relative(now - timedelta(hours=3), now=now) == "3h ago"
    assert format_relative(now - timedelta(days=2), now=now) == "2d ago"
