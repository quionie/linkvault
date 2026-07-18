"""Core application logic for LinkVault.

This module ties the pieces together — fetching, summarizing, storing, and
searching — without knowing anything about the terminal. The CLI layer
(``cli.py``) calls into these functions and handles presentation. Keeping the
logic here means the tool could grow a web UI or API later without a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import database as db
from .config import Config, get_config
from .fetcher import fetch_url
from .models import Item, ItemType
from .summarizer import analyze, embed_query
from .utils import content_hash, cosine_similarity, derive_title, is_url, truncate


@dataclass
class SaveResult:
    """Outcome of a save operation.

    Attributes:
        item: The stored (or pre-existing) item.
        created: ``True`` if a new row was inserted, ``False`` if a duplicate
            already existed.
        used_ai: Whether AI summarization/tagging ran for this save.
        warning: Optional non-fatal message (e.g. content couldn't be fetched).
    """

    item: Item
    created: bool
    used_ai: bool
    warning: str | None = None


@dataclass
class SearchHit:
    """A single search result paired with its relevance score."""

    item: Item
    score: float
    matched_on: str  # "keyword", "semantic", or "hybrid"


def save(text: str, config: Config | None = None) -> SaveResult:
    """Save a URL, snippet, or note into the vault.

    The input is classified automatically:
      * A bare http(s) URL is fetched and its article text extracted.
      * Anything else is stored as a text snippet / note.

    Content is then summarized, tagged, and embedded (best-effort), and the
    item is de-duplicated against previously saved content.
    """
    config = config or get_config()
    db.init_db(config)

    text = text.strip()
    if not text:
        raise ValueError("Nothing to save — input was empty.")

    if is_url(text):
        item, warning = _build_link_item(text, config)
    else:
        item, warning = _build_text_item(text, config)

    # De-duplicate: if we've already saved this exact source, don't re-add it.
    if item.content_hash:
        existing = db.find_by_hash(item.content_hash, config)
        if existing is not None:
            return SaveResult(item=existing, created=False, used_ai=False, warning=warning)

    stored = db.add_item(item, config)
    return SaveResult(
        item=stored,
        created=True,
        used_ai=bool(item.embedding) or bool(item.summary and item.tags),
        warning=warning,
    )


def _build_link_item(url: str, config: Config) -> tuple[Item, str | None]:
    """Fetch a URL, analyze it, and build an :class:`Item`."""
    result = fetch_url(url, config)
    warning: str | None = None

    if result.ok:
        insight = analyze(result.text, config)
        content = truncate(result.text, config.max_content_chars)
        title = result.title or derive_title(result.text)
        summary = insight.summary
        tags = insight.tags
        embedding = insight.embedding
    else:
        # Couldn't extract content — still save the bare link so it's not lost.
        warning = result.error or "Could not fetch content."
        content = ""
        title = result.title or url
        summary = ""
        tags = []
        embedding = []

    item = Item(
        item_type=ItemType.LINK,
        url=result.url,
        title=title,
        content=content,
        summary=summary,
        tags=tags,
        embedding=embedding,
        content_hash=content_hash("link", result.url),
    )
    return item, warning


def _build_text_item(text: str, config: Config) -> tuple[Item, str | None]:
    """Analyze a raw text snippet and build an :class:`Item`."""
    insight = analyze(text, config)
    # Short inputs are notes; longer pasted blocks are text snippets.
    item_type = ItemType.NOTE if len(text) < 280 else ItemType.TEXT

    item = Item(
        item_type=item_type,
        url=None,
        title=derive_title(text),
        content=truncate(text, config.max_content_chars),
        summary=insight.summary,
        tags=insight.tags,
        embedding=insight.embedding,
        content_hash=content_hash(item_type.value, text),
    )
    return item, None


def search(
    query: str, limit: int = 10, config: Config | None = None
) -> list[SearchHit]:
    """Search the vault using a hybrid of keyword and semantic matching.

    Keyword matches (substring hits in title/summary/content) are always
    included. When embeddings are available, semantically similar items are
    blended in and the combined set is ranked by a single relevance score.
    """
    config = config or get_config()
    db.init_db(config)

    query = query.strip()
    if not query:
        return []

    scores: dict[int, SearchHit] = {}

    # --- Keyword pass --------------------------------------------------------
    for item in db.keyword_search(query, limit=limit * 3, config=config):
        if item.id is None:
            continue
        score = _keyword_score(item, query)
        scores[item.id] = SearchHit(item=item, score=score, matched_on="keyword")

    # --- Semantic pass -------------------------------------------------------
    query_vec = embed_query(query, config)
    if query_vec:
        for item in db.all_with_embeddings(config):
            if item.id is None:
                continue
            sim = cosine_similarity(query_vec, item.embedding)
            if sim < 0.35:  # Ignore weak semantic matches to reduce noise.
                continue
            if item.id in scores:
                # Item hit both passes — combine and mark as a hybrid match.
                existing = scores[item.id]
                existing.score = max(existing.score, 0.5) + sim
                existing.matched_on = "hybrid"
            else:
                scores[item.id] = SearchHit(item=item, score=sim, matched_on="semantic")

    hits = sorted(scores.values(), key=lambda h: h.score, reverse=True)
    return hits[:limit]


def _keyword_score(item: Item, query: str) -> float:
    """Weight keyword matches: title hits count more than body hits."""
    q = query.lower()
    score = 0.5  # Base score for being returned by the SQL search at all.
    if q in item.title.lower():
        score += 1.0
    if q in item.summary.lower():
        score += 0.5
    return score


def recent(limit: int = 10, config: Config | None = None) -> list[Item]:
    """Return the most recently saved items."""
    config = config or get_config()
    db.init_db(config)
    return db.list_recent(limit=limit, config=config)


def get(item_id: int, config: Config | None = None) -> Item | None:
    """Fetch a single item by id."""
    config = config or get_config()
    db.init_db(config)
    return db.get_item(item_id, config)


def delete(item_id: int, config: Config | None = None) -> bool:
    """Delete an item by id. Returns ``True`` if it existed."""
    config = config or get_config()
    db.init_db(config)
    return db.delete_item(item_id, config)


def stats(config: Config | None = None) -> int:
    """Return the number of items currently stored."""
    config = config or get_config()
    db.init_db(config)
    return db.count_items(config)
