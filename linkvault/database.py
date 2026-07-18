"""Database setup and operations for LinkVault.

Thin wrapper around SQLModel/SQLAlchemy. Everything is a local SQLite file, so
there is no connection pool to worry about and no server to run. The functions
here are deliberately small and composable — the interesting logic lives in
``core.py``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, desc, or_, select

from .config import Config, get_config
from .models import Item

# Cache one engine per database URL. Creating an engine is cheap but not free,
# and reusing it keeps SQLite's file handle stable across a single process.
_engines: dict[str, Engine] = {}


def get_engine(config: Config | None = None) -> Engine:
    """Return a cached SQLAlchemy engine for the configured database."""
    config = config or get_config()
    url = config.db_url
    if url not in _engines:
        config.ensure_dirs()
        # ``check_same_thread=False`` keeps SQLite usable if a caller ever hops
        # threads; the CLI is single-threaded, so this is just future-proofing.
        _engines[url] = create_engine(
            url,
            connect_args={"check_same_thread": False},
        )
    return _engines[url]


def init_db(config: Config | None = None) -> None:
    """Create the database file and all tables if they do not exist."""
    engine = get_engine(config)
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session(config: Config | None = None) -> Iterator[Session]:
    """Yield a database session, committing on success and closing on exit."""
    engine = get_engine(config)
    # ``expire_on_commit=False`` keeps loaded attributes accessible after the
    # session closes, so callers can safely read returned Item objects.
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# -- CRUD helpers ------------------------------------------------------------


def add_item(item: Item, config: Config | None = None) -> Item:
    """Persist a new item and return it with its assigned id populated."""
    with get_session(config) as session:
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


def get_item(item_id: int, config: Config | None = None) -> Item | None:
    """Fetch a single item by primary key, or ``None`` if it does not exist."""
    with get_session(config) as session:
        return session.get(Item, item_id)


def delete_item(item_id: int, config: Config | None = None) -> bool:
    """Delete an item by id. Returns ``True`` if a row was removed."""
    with get_session(config) as session:
        item = session.get(Item, item_id)
        if item is None:
            return False
        session.delete(item)
        return True


def find_by_hash(content_hash: str, config: Config | None = None) -> Item | None:
    """Return the first existing item with a matching content hash, if any."""
    with get_session(config) as session:
        statement = select(Item).where(Item.content_hash == content_hash)
        return session.exec(statement).first()


def list_recent(limit: int = 10, config: Config | None = None) -> list[Item]:
    """Return the ``limit`` most recently saved items, newest first."""
    with get_session(config) as session:
        statement = select(Item).order_by(desc(Item.created_at)).limit(limit)
        return list(session.exec(statement).all())


def keyword_search(
    query: str, limit: int = 50, config: Config | None = None
) -> list[Item]:
    """Case-insensitive substring search across title, summary, and content."""
    pattern = f"%{query.lower()}%"
    with get_session(config) as session:
        statement = (
            select(Item)
            .where(
                or_(
                    Item.title.ilike(pattern),      # type: ignore[attr-defined]
                    Item.summary.ilike(pattern),    # type: ignore[attr-defined]
                    Item.content.ilike(pattern),    # type: ignore[attr-defined]
                )
            )
            .order_by(desc(Item.created_at))
            .limit(limit)
        )
        return list(session.exec(statement).all())


def all_with_embeddings(config: Config | None = None) -> list[Item]:
    """Return every item that has a stored embedding, for semantic search."""
    with get_session(config) as session:
        # SQLite can't easily filter empty JSON arrays, so filter in Python.
        statement = select(Item)
        return [i for i in session.exec(statement).all() if i.embedding]


def count_items(config: Config | None = None) -> int:
    """Return the total number of items in the vault."""
    with get_session(config) as session:
        return len(session.exec(select(Item.id)).all())
