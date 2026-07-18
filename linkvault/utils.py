"""Small, dependency-light helpers shared across LinkVault.

Kept intentionally pure and side-effect-free (aside from the shared Rich
console) so the rest of the codebase can lean on these without surprises.
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import UTC, datetime
from urllib.parse import urlparse

from rich.console import Console

# One shared console for the whole app keeps output styling consistent.
console = Console()

# A pragmatic URL matcher: requires an http(s) scheme and a host.
_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)


def is_url(text: str) -> bool:
    """Return ``True`` if ``text`` looks like a single http(s) URL."""
    text = text.strip()
    if not _URL_RE.match(text):
        return False
    parsed = urlparse(text)
    return bool(parsed.scheme in {"http", "https"} and parsed.netloc)


def content_hash(*parts: str) -> str:
    """Return a stable short hash of the given parts, for de-duplication."""
    digest = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def truncate(text: str, limit: int, suffix: str = "…") -> str:
    """Truncate ``text`` to ``limit`` characters, adding an ellipsis if cut."""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - len(suffix))].rstrip() + suffix


def clean_whitespace(text: str) -> str:
    """Collapse runs of whitespace to single spaces and strip the ends."""
    return re.sub(r"\s+", " ", text).strip()


def first_sentences(text: str, count: int = 3) -> str:
    """Return roughly the first ``count`` sentences of ``text``.

    Used as the offline fallback summary when no LLM is available. It's a
    heuristic, not a parser — good enough to be useful, cheap enough to be free.
    """
    text = clean_whitespace(text)
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:count]).strip()


def derive_title(text: str, limit: int = 60) -> str:
    """Derive a readable title from a block of text (its first line/phrase)."""
    text = clean_whitespace(text)
    if not text:
        return "Untitled"
    # Prefer the first sentence; fall back to a truncated prefix.
    first = re.split(r"(?<=[.!?])\s+", text)[0]
    return truncate(first, limit)


def format_relative(dt: datetime, *, now: datetime | None = None) -> str:
    """Format a timestamp as a compact relative age like ``3h ago``."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    now = now or datetime.now(UTC)
    seconds = max(0, int((now - dt).total_seconds()))

    # Each step is (divisor, resulting-unit): divide the running value by the
    # divisor and adopt the new unit until the value no longer fits.
    steps = (
        (60, "m"),   # seconds → minutes
        (60, "h"),   # minutes → hours
        (24, "d"),   # hours   → days
        (7, "w"),    # days    → weeks
        (4, "mo"),   # weeks   → months
        (12, "y"),   # months  → years
    )
    value = seconds
    unit = "s"
    for size, next_unit in steps:
        if value < size:
            break
        value //= size
        unit = next_unit
    if unit == "s":
        return "just now"
    return f"{value}{unit} ago"


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return the cosine similarity of two equal-length vectors in ``[-1, 1]``.

    Returns ``0.0`` for empty or mismatched vectors rather than raising, so
    callers can rank freely without guarding every comparison.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
