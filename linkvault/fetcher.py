"""Web content fetching and extraction.

Given a URL, download the page and pull out the main article text and title,
stripping navigation, ads, and boilerplate. Uses ``trafilatura`` for extraction
(fast, dependency-light, and surprisingly good) with ``httpx`` handling the
actual HTTP request so we control timeouts and user-agent.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import trafilatura

from .config import Config, get_config
from .utils import clean_whitespace

# A polite, real-looking user agent. Many sites reject the default Python one.
_USER_AGENT = (
    "Mozilla/5.0 (compatible; LinkVault/0.1; +https://github.com/quionie/linkvault)"
)


@dataclass
class FetchResult:
    """The outcome of fetching and extracting a URL.

    Attributes:
        url: The (possibly redirected) final URL.
        title: Extracted page title, or a fallback derived from the URL.
        text: Cleaned main-content text. Empty if extraction found nothing.
        ok: Whether the fetch + extraction produced usable text.
        error: Human-readable reason when ``ok`` is ``False``.
    """

    url: str
    title: str = ""
    text: str = ""
    ok: bool = False
    error: str | None = None


def fetch_url(url: str, config: Config | None = None) -> FetchResult:
    """Fetch ``url`` and extract its main content.

    Never raises for ordinary network problems — failures are reported via the
    ``ok``/``error`` fields so the caller can degrade gracefully (e.g. still
    save the bare URL with a placeholder title).
    """
    config = config or get_config()

    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=config.request_timeout,
            headers={"User-Agent": _USER_AGENT},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return FetchResult(url=url, title=_fallback_title(url), error=str(exc))

    final_url = str(response.url)
    html = response.text

    # Extract the main body text. ``include_comments=False`` keeps it clean.
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    )

    title = _extract_title(html, final_url)

    if not text:
        return FetchResult(
            url=final_url,
            title=title,
            error="Could not extract readable content from the page.",
        )

    return FetchResult(
        url=final_url,
        title=title,
        text=clean_whitespace(text),
        ok=True,
    )


def _extract_title(html: str, url: str) -> str:
    """Pull a title from page metadata, falling back to the URL."""
    try:
        metadata = trafilatura.extract_metadata(html)
        if metadata and metadata.title:
            return clean_whitespace(metadata.title)
    except Exception:
        # Metadata extraction is best-effort; never let it break a save.
        pass
    return _fallback_title(url)


def _fallback_title(url: str) -> str:
    """Derive a readable title from a URL when no page title is available."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.netloc.removeprefix("www.")
    path = parsed.path.strip("/")
    if path:
        # Turn "posts/my-cool-article" into "my cool article".
        slug = path.split("/")[-1].replace("-", " ").replace("_", " ")
        if slug:
            return f"{slug} — {host}".strip()
    return host or url
