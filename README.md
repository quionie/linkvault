<h1 align="center">🔗 LinkVault</h1>

<p align="center">
  <strong>A local-first, AI-powered clipboard & link saver for your terminal.</strong><br>
  Save links, text, and notes → LinkVault fetches, summarizes, tags, and stores them in a
  searchable local database. Everything stays on your machine.
</p>

<p align="center">
  <a href="#-features">Features</a> ·
  <a href="#-installation">Installation</a> ·
  <a href="#-quick-start">Quick Start</a> ·
  <a href="#-usage">Usage</a> ·
  <a href="#-how-it-works">How It Works</a> ·
  <a href="#-configuration">Configuration</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="Local-first" src="https://img.shields.io/badge/local--first-100%25-orange">
</p>

---

## ✨ Why LinkVault?

You copy dozens of links and snippets a day and forget most of them. Bookmarking tools
are cloud-locked, cluttered, and never actually help you *find* things again.

**LinkVault** is different:

- 🔒 **Private by design** — no accounts, no cloud, no telemetry. Your vault is a single
  SQLite file on your disk.
- 🧠 **AI that runs on your laptop** — summaries, tags, and semantic search powered by a
  local [Ollama](https://ollama.com) model. Nothing is sent anywhere.
- 🔎 **Actually findable** — hybrid keyword **+** semantic search means you can search by
  what you *meant*, not just the exact words you saved.
- ⚡ **Works offline, always** — no Ollama? LinkVault falls back to fast heuristics so
  `save` never fails.

---

## 🚀 Features

| Command | What it does |
| ------- | ------------ |
| `linkvault init` | Set up your config file and database |
| `linkvault save <url \| text>` | Fetch (if a URL), summarize, tag, and store an item |
| `linkvault search <query>` | Hybrid keyword + semantic search across your vault |
| `linkvault list [--limit N]` | Show your most recently saved items |
| `linkvault show <id>` | View a single item in full |
| `linkvault delete <id>` | Remove an item |
| `linkvault info` | Show config, item count, and AI status |

Under the hood:

- 📰 **Smart article extraction** with [Trafilatura](https://trafilatura.readthedocs.io/) —
  strips nav, ads, and boilerplate to keep just the content.
- 🏷️ **Auto-tagging** — every item gets topical tags for easy filtering.
- 🧬 **Semantic embeddings** stored alongside each item for meaning-based search.
- 🎨 **Beautiful terminal output** with [Rich](https://rich.readthedocs.io/).
- 🧯 **Graceful degradation** — offline heuristics keep everything working without a GPU.

---

## 📦 Installation

LinkVault needs **Python 3.11+**.

```bash
# 1. Clone the repo
git clone https://github.com/quionie/linkvault.git
cd linkvault

# 2. (Recommended) create a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install it (editable, so you can hack on it)
pip install -e .
```

That's it — the `linkvault` command is now on your path.

### Optional: enable local AI

LinkVault's summaries, tags, and semantic search are powered by
[Ollama](https://ollama.com). Install it, then pull the two default models:

```bash
ollama pull llama3.2          # summaries & tagging
ollama pull nomic-embed-text  # semantic search embeddings
```

> **No Ollama?** No problem. LinkVault still saves everything and falls back to a
> heuristic summary + keyword search. You can add Ollama any time.

---

## ⚡ Quick Start

```bash
# One-time setup
linkvault init

# Save a link — it gets fetched, summarized, and tagged automatically
linkvault save "https://en.wikipedia.org/wiki/Zettelkasten"

# Save a quick note
linkvault save "Idea: a CLI that turns my scattered bookmarks into a knowledge base"

# Find it later — by keyword OR meaning
linkvault search "note taking method"

# Browse what you've saved
linkvault list --limit 20
```

---

## 📖 Usage

### Save a link

```console
$ linkvault save "https://example.com/great-article"
╭───────────────────────────── Saved ──────────────────────────────╮
│ The Great Article                                                 │
│ https://example.com/great-article                                 │
│                                                                   │
│ A concise 2-3 sentence summary of what the article actually says. │
│                                                                   │
│ #productivity #writing #tools                                     │
│                                                                   │
│ #1 · link · just now                                              │
╰───────────────────────────────────────────────────────────────────╯
```

### Search your vault

```console
$ linkvault search "how to focus"
              Results for "how to focus"
┏━━━┳━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ # ┃ Type ┃ Title          ┃ Summary              ┃ Match  ┃
┡━━━╇━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ 4 │ link │ Deep Work      │ Cal Newport argues…  │ hybrid │
│ 7 │ note │ Focus ritual   │ Morning routine to…  │ keyword│
└───┴──────┴────────────────┴──────────────────────┴────────┘
```

`Match` tells you *how* an item was found: `keyword`, `semantic`, or `hybrid`
(both). Semantic hits surface items that don't contain your exact words but mean
the same thing.

### List recent items

```console
$ linkvault list -n 5
```

### Show one item in full

```console
$ linkvault show 4
```

### Delete an item

```console
$ linkvault delete 4
```

---

## 🧠 How It Works

```
                 ┌──────────────┐
  save <input> ─▶│  is it a URL? │
                 └──────┬───────┘
                        │ yes            no
              ┌─────────▼─────────┐   ┌──────────────┐
              │ fetch + extract   │   │ store as     │
              │ (httpx +          │   │ text / note  │
              │  trafilatura)     │   └──────┬───────┘
              └─────────┬─────────┘          │
                        └──────────┬─────────┘
                                   ▼
                        ┌────────────────────┐
                        │ analyze (Ollama):  │
                        │  • summary         │
                        │  • tags            │
                        │  • embedding       │
                        └─────────┬──────────┘
                                  ▼
                        ┌────────────────────┐
                        │ SQLite (SQLModel)  │
                        └────────────────────┘
```

Search runs two passes and blends the results:

1. **Keyword** — case-insensitive substring match on title, summary, and content.
2. **Semantic** — cosine similarity between your query's embedding and each item's
   stored embedding.

Items found by both are boosted and labelled `hybrid`.

### Project layout

```
linkvault/
├── linkvault/
│   ├── __init__.py
│   ├── cli.py          # Typer commands + Rich output (presentation only)
│   ├── core.py         # Orchestration: save / search / list logic
│   ├── database.py     # SQLite setup + CRUD via SQLModel
│   ├── models.py       # The Item data model
│   ├── summarizer.py   # Ollama client + graceful offline fallbacks
│   ├── fetcher.py      # URL fetching + article extraction
│   ├── config.py       # Config loading + persistence
│   └── utils.py        # Shared helpers (URL detection, cosine sim, etc.)
├── tests/
├── pyproject.toml
├── requirements.txt
├── README.md
├── LICENSE
└── .gitignore
```

The layers are deliberately separated: `cli.py` never touches the database, and
`core.py` never touches the terminal. That makes it easy to add a web UI or API
later without rewriting the logic.

---

## ⚙️ Configuration

Config lives at `~/.config/linkvault/config.json` (created by `linkvault init`).
Every value can also be overridden with an environment variable:

| Setting | Env var | Default |
| ------- | ------- | ------- |
| Data directory | `LINKVAULT_HOME` | `~/.config/linkvault` |
| Use AI | `LINKVAULT_USE_AI` | `true` |
| Ollama host | `LINKVAULT_OLLAMA_HOST` | `http://localhost:11434` |
| Chat model | `LINKVAULT_MODEL` | `llama3.2` |
| Embedding model | `LINKVAULT_EMBED_MODEL` | `nomic-embed-text` |

**Run fully offline (no AI):**

```bash
LINKVAULT_USE_AI=false linkvault save "some text to store"
```

Your data is just a SQLite file at `~/.config/linkvault/linkvault.db` — back it up,
sync it, or inspect it with any SQLite browser.

---

## 🛠️ Development

```bash
pip install -e ".[dev]"   # install with dev tools
pytest                     # run the tests
ruff check .               # lint
```

Tests use an isolated temporary database, so they never touch your real vault.

---

## 🗺️ Roadmap

- [ ] `linkvault open <id>` — open a saved link in the browser
- [ ] Image & file capture (OCR + description)
- [ ] Clipboard watch mode (auto-save on copy)
- [ ] Export to Markdown / JSON
- [ ] Tag-based filtering (`linkvault list --tag python`)

---

## 📄 License

[MIT](LICENSE) © 2026 Quionie. Built to be forked, hacked, and made your own.
