"""SQLModel data models for LinkVault.

A single table, ``item``, backs the whole tool. Each saved link, snippet, or
note becomes one row. Tags and the semantic-search embedding are stored as JSON
columns so the schema stays flat and easy to query.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class ItemType(StrEnum):
    """The kind of thing that was saved."""

    LINK = "link"   # A URL whose content was fetched and extracted.
    TEXT = "text"   # A pasted snippet of text.
    NOTE = "note"   # A short user-authored note.


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp (avoids the deprecated ``utcnow``)."""
    return datetime.now(UTC)


class Item(SQLModel, table=True):
    """A single saved item in the vault.

    Attributes:
        id: Auto-incrementing primary key.
        item_type: Whether this row is a link, text snippet, or note.
        url: Source URL, if the item originated from a link.
        title: Human-readable title (page title for links, else derived).
        content: Extracted/cleaned text content, truncated to a sane length.
        summary: AI (or heuristic) summary of the content.
        tags: List of short topical tags for filtering and discovery.
        embedding: Vector embedding of the content, used for semantic search.
            Stored as a list of floats; empty when embeddings are unavailable.
        content_hash: Hash of the source, used to detect duplicates.
        created_at: When the item was saved (UTC).
    """

    id: int | None = Field(default=None, primary_key=True)
    item_type: ItemType = Field(default=ItemType.NOTE, index=True)

    url: str | None = Field(default=None, index=True)
    title: str = Field(default="Untitled", index=True)
    content: str = Field(default="")
    summary: str = Field(default="")

    # JSON-backed columns. ``sa_column`` lets us store native Python lists.
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    embedding: list[float] = Field(default_factory=list, sa_column=Column(JSON))

    content_hash: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)

    def tag_string(self) -> str:
        """Return tags as a comma-separated string for compact display."""
        return ", ".join(self.tags)
