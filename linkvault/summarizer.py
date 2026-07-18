"""AI summarization, tagging, and embeddings via Ollama.

LinkVault is local-first: by default it talks to a locally running `Ollama
<https://ollama.com>`_ server for summaries, tags, and semantic-search
embeddings. Nothing leaves your machine.

Crucially, every function here degrades gracefully. If Ollama isn't running,
the model isn't pulled, or a call times out, LinkVault falls back to fast
heuristics so ``save`` never fails just because the LLM is unavailable.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import httpx

from .config import Config, get_config
from .utils import clean_whitespace, first_sentences, truncate

# How much text to send to the model. Keeps prompts fast and within context.
_MAX_INPUT_CHARS = 6_000


@dataclass
class Insight:
    """The result of analyzing a piece of content.

    Attributes:
        summary: A concise summary of the content.
        tags: A short list of topical tags.
        embedding: Vector embedding for semantic search (empty if unavailable).
        used_ai: Whether an LLM produced this result (vs. the fallback path).
    """

    summary: str = ""
    tags: list[str] = field(default_factory=list)
    embedding: list[float] = field(default_factory=list)
    used_ai: bool = False


class OllamaClient:
    """Minimal HTTP client for the Ollama REST API."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or get_config()

    def is_available(self) -> bool:
        """Return ``True`` if the Ollama server responds to a quick ping."""
        try:
            resp = httpx.get(f"{self.config.ollama_host}/api/tags", timeout=3.0)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def generate(self, prompt: str) -> str:
        """Run a single-shot completion and return the raw text response."""
        resp = httpx.post(
            f"{self.config.ollama_host}/api/generate",
            json={
                "model": self.config.ollama_model,
                "prompt": prompt,
                "stream": False,
                # Low temperature keeps summaries factual and tags stable.
                "options": {"temperature": 0.2},
            },
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()

    def embed(self, text: str) -> list[float]:
        """Return an embedding vector for ``text`` (empty list on failure)."""
        resp = httpx.post(
            f"{self.config.ollama_host}/api/embeddings",
            json={"model": self.config.embed_model, "prompt": text},
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        return list(resp.json().get("embedding", []))


_SUMMARY_PROMPT = """\
You are a concise research assistant. Read the content below and respond with a
single JSON object — no markdown, no code fences, no commentary — of the form:

{{"summary": "<2-3 sentence summary>", "tags": ["tag1", "tag2", "tag3"]}}

Rules:
- The summary must be factual, self-contained, and under 60 words.
- Provide 3 to 6 lowercase tags: short topical keywords, no "#", no spaces
  (use hyphens if needed).

CONTENT:
{content}
"""


def analyze(text: str, config: Config | None = None) -> Insight:
    """Summarize, tag, and embed ``text``.

    Tries Ollama first when AI is enabled and reachable; otherwise returns a
    heuristic summary with no tags/embedding. Either way the caller gets a
    usable :class:`Insight` and never has to handle an exception.
    """
    config = config or get_config()
    text = clean_whitespace(text)
    if not text:
        return Insight()

    if config.use_ai:
        client = OllamaClient(config)
        if client.is_available():
            ai = _analyze_with_ai(text, client)
            if ai is not None:
                return ai

    # Fallback: cheap, offline, always works.
    return Insight(summary=first_sentences(text, 3), tags=[], used_ai=False)


def _analyze_with_ai(text: str, client: OllamaClient) -> Insight | None:
    """Attempt full AI analysis; return ``None`` if anything goes wrong."""
    snippet = truncate(text, _MAX_INPUT_CHARS)
    try:
        raw = client.generate(_SUMMARY_PROMPT.format(content=snippet))
        summary, tags = _parse_summary_response(raw)

        # Embedding failure shouldn't discard a good summary — try separately.
        try:
            embedding = client.embed(snippet)
        except httpx.HTTPError:
            embedding = []

        # If the model returned nothing useful, fall back to heuristics.
        if not summary:
            summary = first_sentences(text, 3)

        return Insight(summary=summary, tags=tags, embedding=embedding, used_ai=True)
    except httpx.HTTPError:
        return None


def _parse_summary_response(raw: str) -> tuple[str, list[str]]:
    """Parse the model's JSON reply, tolerating stray prose or code fences."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        # No JSON at all — treat the whole thing as a plain-text summary.
        return clean_whitespace(raw), []

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return clean_whitespace(raw), []

    summary = clean_whitespace(str(data.get("summary", "")))
    raw_tags = data.get("tags", [])
    tags = _normalize_tags(raw_tags)
    return summary, tags


def _normalize_tags(raw_tags: object) -> list[str]:
    """Coerce model output into a clean, de-duplicated list of tags."""
    if isinstance(raw_tags, str):
        raw_tags = re.split(r"[,\s]+", raw_tags)
    if not isinstance(raw_tags, (list, tuple)):
        return []

    seen: set[str] = set()
    tags: list[str] = []
    for tag in raw_tags:
        cleaned = re.sub(r"[^a-z0-9\-]", "", str(tag).lower().strip())
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            tags.append(cleaned)
    return tags[:6]


def embed_query(text: str, config: Config | None = None) -> list[float]:
    """Embed a search query for semantic comparison (empty list on failure)."""
    config = config or get_config()
    if not config.use_ai:
        return []
    client = OllamaClient(config)
    if not client.is_available():
        return []
    try:
        return client.embed(clean_whitespace(text))
    except httpx.HTTPError:
        return []
