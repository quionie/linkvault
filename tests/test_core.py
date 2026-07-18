"""End-to-end tests for the core save/search/list flow.

These run with AI disabled (heuristic mode), so they exercise the real database
path without needing Ollama.
"""

from __future__ import annotations

from linkvault import core
from linkvault.config import Config
from linkvault.models import ItemType


def test_save_note_and_list(config: Config) -> None:
    result = core.save("A quick note about local-first software", config=config)
    assert result.created is True
    assert result.item.id is not None
    assert result.item.item_type == ItemType.NOTE
    # Heuristic summary should be populated even without AI.
    assert result.item.summary

    items = core.recent(limit=10, config=config)
    assert len(items) == 1
    assert items[0].title.startswith("A quick note")


def test_save_deduplicates(config: Config) -> None:
    first = core.save("exactly the same text", config=config)
    second = core.save("exactly the same text", config=config)
    assert first.created is True
    assert second.created is False
    assert first.item.id == second.item.id
    assert core.stats(config=config) == 1


def test_empty_input_raises(config: Config) -> None:
    try:
        core.save("   ", config=config)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for empty input")


def test_keyword_search_finds_item(config: Config) -> None:
    core.save("Notes on the Zettelkasten method for knowledge management", config=config)
    core.save("Grocery list: eggs, milk, bread", config=config)

    hits = core.search("zettelkasten", limit=10, config=config)
    assert len(hits) == 1
    assert "Zettelkasten" in hits[0].item.title
    assert hits[0].matched_on in {"keyword", "hybrid"}


def test_delete(config: Config) -> None:
    result = core.save("delete me please", config=config)
    item_id = result.item.id
    assert item_id is not None
    assert core.delete(item_id, config=config) is True
    assert core.delete(item_id, config=config) is False
    assert core.get(item_id, config=config) is None
