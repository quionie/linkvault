"""Shared pytest fixtures.

Every test runs against an isolated, throwaway config + database so the suite
never touches a real user vault and never needs Ollama running.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from linkvault.config import Config


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """A Config pointing at a temp dir, with AI disabled for determinism."""
    return Config(home=tmp_path, use_ai=False)
