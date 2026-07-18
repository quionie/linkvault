# LinkVault

A local-first, command-line link and note saver with optional local AI. You
pass it a URL, a snippet of text, or a note; it fetches and extracts article
content (for URLs), summarizes and tags the item, and stores it in a local
SQLite database that you can search by keyword or by meaning.

Everything runs on your machine. There are no accounts, no network calls except
the pages you explicitly save and a local Ollama server if you enable AI, and no
telemetry.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

## Requirements

- Python 3.11 or newer
- (Optional) [Ollama](https://ollama.com) for AI summaries, tags, and semantic
  search. Without it, LinkVault falls back to heuristic summaries and keyword
  search, so every command still works.

## Installation

```bash
git clone https://github.com/quionie/linkvault.git
cd linkvault
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
```

This puts the `linkvault` command on your path.

To enable local AI, install Ollama and pull the two default models:

```bash
ollama pull llama3.2          # summarization and tagging
ollama pull nomic-embed-text  # embeddings for semantic search
```

## Usage

```
linkvault init                    Create the config file and database
linkvault save <url | text>       Fetch (if a URL), summarize, tag, and store
linkvault search <query>          Keyword + semantic search
linkvault list [--limit N]        Show recent items (default 10)
linkvault show <id>               Show a single item in full
linkvault delete <id>             Remove an item
linkvault info                    Show config and vault status
```

### Examples

```bash
linkvault init

# Save a URL. The page is fetched, the main content extracted, then summarized.
linkvault save "https://en.wikipedia.org/wiki/Zettelkasten"

# Save a note. Short inputs are stored as notes; longer text as snippets.
linkvault save "Idea: turn scattered bookmarks into a searchable knowledge base"

# Search. Results are labelled by how they matched.
linkvault search "note taking method"

# Browse recent items.
linkvault list --limit 20
```

Search runs two passes and merges them:

- **Keyword** — case-insensitive substring match on title, summary, and content.
- **Semantic** — cosine similarity between the query embedding and each item's
  stored embedding. Only runs when Ollama is available.

Items found by both passes are ranked higher and labelled `hybrid`. Semantic
matching is what lets a search for "how to focus" surface an item titled "Deep
Work" that never contains those words.

## Configuration

Configuration lives at `~/.config/linkvault/config.json`, created by
`linkvault init`. Every value can be overridden with an environment variable:

| Setting          | Environment variable      | Default                  |
| ---------------- | ------------------------- | ------------------------ |
| Data directory   | `LINKVAULT_HOME`          | `~/.config/linkvault`    |
| Use AI           | `LINKVAULT_USE_AI`        | `true`                   |
| Ollama host      | `LINKVAULT_OLLAMA_HOST`   | `http://localhost:11434` |
| Chat model       | `LINKVAULT_MODEL`         | `llama3.2`               |
| Embedding model  | `LINKVAULT_EMBED_MODEL`   | `nomic-embed-text`       |

Run without AI at any time:

```bash
LINKVAULT_USE_AI=false linkvault save "some text to store"
```

The database is a single SQLite file at `~/.config/linkvault/linkvault.db`. Back
it up, sync it, or inspect it with any SQLite client.

## Architecture

The code is organized so that presentation, orchestration, and storage stay
separate. `cli.py` never touches the database, and `core.py` never touches the
terminal, which keeps the logic reusable if a web UI or API is added later.

```
linkvault/
  __init__.py
  cli.py          Typer commands and Rich output (presentation)
  core.py         Orchestration: save, search, and list logic
  database.py     SQLite setup and CRUD via SQLModel
  models.py       The Item data model
  summarizer.py   Ollama client with offline fallbacks
  fetcher.py      URL fetching and article extraction (Trafilatura)
  config.py       Configuration loading and persistence
  utils.py        Shared helpers (URL detection, cosine similarity, ...)
tests/
```

The save pipeline: input is classified as a URL or text. URLs are fetched with
`httpx` and reduced to their main content with Trafilatura. The content is then
summarized, tagged, and embedded (best-effort, degrading to heuristics if Ollama
is unavailable), de-duplicated against existing items by content hash, and
written to SQLite.

## Development

```bash
pip install -e ".[dev]"
pytest                     # run the test suite
ruff check .               # lint
```

Tests run against an isolated temporary database with AI disabled, so they never
touch a real vault and do not require Ollama.

## Roadmap

- `linkvault open <id>` to open a saved link in the browser
- Image and file capture
- Clipboard watch mode to save on copy
- Export to Markdown and JSON
- Tag-based filtering (`linkvault list --tag python`)

## License

MIT. See [LICENSE](LICENSE).
