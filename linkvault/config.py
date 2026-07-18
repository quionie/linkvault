"""Configuration for LinkVault.

Configuration is stored as a small JSON file in the user's config directory
(``~/.config/linkvault/config.json`` by default, overridable via the
``LINKVAULT_HOME`` environment variable). Every setting can also be overridden
through an environment variable, which makes the tool easy to script and test.

The design goal here is *zero surprises*: sensible defaults that work offline,
one file to edit, and no hidden global state beyond a cached singleton.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path


def _default_home() -> Path:
    """Return the base directory where LinkVault keeps its data.

    Order of precedence:
      1. ``LINKVAULT_HOME`` environment variable (explicit override).
      2. ``$XDG_CONFIG_HOME/linkvault`` if ``XDG_CONFIG_HOME`` is set.
      3. ``~/.config/linkvault`` (the conventional default on Linux/macOS).
    """
    if env_home := os.environ.get("LINKVAULT_HOME"):
        return Path(env_home).expanduser()

    if xdg := os.environ.get("XDG_CONFIG_HOME"):
        return Path(xdg).expanduser() / "linkvault"

    return Path.home() / ".config" / "linkvault"


@dataclass
class Config:
    """Runtime configuration for LinkVault.

    Attributes:
        home: Base directory for all LinkVault data (config + database).
        db_path: Absolute path to the SQLite database file.
        use_ai: When ``True``, use Ollama for summaries, tags, and embeddings.
            When ``False`` (or when Ollama is unreachable) LinkVault falls back
            to fast, dependency-free heuristics so the tool always works.
        ollama_host: Base URL of the local Ollama server.
        ollama_model: Chat model used for summarization and tagging.
        embed_model: Model used to generate embeddings for semantic search.
        request_timeout: Timeout (seconds) for network calls (fetch + Ollama).
        max_content_chars: Upper bound on stored content length, to keep the
            database lean. The full text is still summarized before truncation.
    """

    home: Path = field(default_factory=_default_home)
    db_path: Path | None = None
    use_ai: bool = True
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    embed_model: str = "nomic-embed-text"
    request_timeout: float = 60.0
    max_content_chars: int = 20_000

    def __post_init__(self) -> None:
        # Normalize paths and apply environment overrides. Environment variables
        # always win so the tool can be reconfigured without editing the file.
        self.home = Path(self.home).expanduser()
        if self.db_path is None:
            self.db_path = self.home / "linkvault.db"
        self.db_path = Path(self.db_path).expanduser()

        self.use_ai = _env_bool("LINKVAULT_USE_AI", self.use_ai)
        self.ollama_host = os.environ.get("LINKVAULT_OLLAMA_HOST", self.ollama_host)
        self.ollama_model = os.environ.get("LINKVAULT_MODEL", self.ollama_model)
        self.embed_model = os.environ.get("LINKVAULT_EMBED_MODEL", self.embed_model)

    # -- persistence ---------------------------------------------------------

    @property
    def config_path(self) -> Path:
        """Path to the JSON config file on disk."""
        return self.home / "config.json"

    @property
    def db_url(self) -> str:
        """SQLAlchemy connection URL for the SQLite database."""
        return f"sqlite:///{self.db_path}"

    def ensure_dirs(self) -> None:
        """Create the config/data directory if it does not yet exist."""
        self.home.mkdir(parents=True, exist_ok=True)

    def save(self) -> Path:
        """Persist the current configuration to ``config.json``."""
        self.ensure_dirs()
        data = asdict(self)
        # Paths are not JSON-serializable; store them as strings.
        data["home"] = str(self.home)
        data["db_path"] = str(self.db_path)
        self.config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return self.config_path

    @classmethod
    def load(cls) -> Config:
        """Load configuration from disk, falling back to defaults.

        Unknown keys in the file are ignored so that upgrading LinkVault never
        crashes on an older config, and environment overrides are re-applied in
        ``__post_init__`` regardless of what the file contains.
        """
        home = _default_home()
        path = home / "config.json"
        if not path.exists():
            return cls()

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # A corrupt config should never brick the CLI — fall back cleanly.
            return cls()

        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in raw.items() if k in known}
        return cls(**filtered)


def _env_bool(name: str, default: bool) -> bool:
    """Interpret an environment variable as a boolean flag."""
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return the cached, process-wide configuration instance."""
    return Config.load()


def reset_config_cache() -> None:
    """Clear the cached config (useful in tests and after ``init``)."""
    get_config.cache_clear()
