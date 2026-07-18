"""LinkVault command-line interface.

Built with Typer + Rich. This layer is purely about presentation and argument
parsing — all real work is delegated to :mod:`linkvault.core`. Commands:

    linkvault init                 Set up config + database
    linkvault save <url|text>      Fetch, summarize, tag, and store an item
    linkvault search <query>       Hybrid keyword + semantic search
    linkvault list [--limit N]     Show recent items
    linkvault show <id>            Show a single item in full
    linkvault delete <id>          Remove an item
    linkvault info                 Show config + vault status
"""

from __future__ import annotations

import typer
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__, core
from . import database as db
from .config import get_config, reset_config_cache
from .models import Item
from .summarizer import OllamaClient
from .utils import console, format_relative, truncate

app = typer.Typer(
    name="linkvault",
    help="Local-first, AI-powered clipboard & link saver. Everything stays on your machine.",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Type colors keep the output scannable at a glance.
_TYPE_STYLES = {
    "link": "cyan",
    "text": "magenta",
    "note": "yellow",
}


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"LinkVault [bold cyan]v{__version__}[/]")
        raise typer.Exit()


@app.callback()
def main(
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """LinkVault — save anything, find it later."""


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@app.command()
def init() -> None:
    """Set up the configuration file and database."""
    config = get_config()
    config.ensure_dirs()
    path = config.save()
    db.init_db(config)
    reset_config_cache()

    body = Text()
    body.append("Config:   ", style="bold")
    body.append(f"{path}\n")
    body.append("Database: ", style="bold")
    body.append(f"{config.db_path}\n")
    body.append("AI:       ", style="bold")
    if config.use_ai:
        available = OllamaClient(config).is_available()
        status = (
            "[green]ready[/]" if available
            else "[yellow]enabled, but Ollama not reachable[/]"
        )
        body.append_text(
            Text.from_markup(
                f"{status} ({config.ollama_model} via {config.ollama_host})"
            )
        )
    else:
        body.append("disabled (heuristic mode)", style="dim")

    console.print(Panel(body, title="[bold green]LinkVault ready[/]", border_style="green"))

    if config.use_ai and not OllamaClient(config).is_available():
        console.print(
            "\n[dim]Tip: install Ollama (https://ollama.com) and run "
            f"[bold]ollama pull {config.ollama_model}[/] + "
            f"[bold]ollama pull {config.embed_model}[/] for AI summaries and "
            "semantic search. LinkVault works without it, too.[/]"
        )


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------


@app.command()
def save(
    text: str = typer.Argument(..., help="A URL, a snippet of text, or a quick note."),
) -> None:
    """Fetch (if a URL), summarize, tag, and save an item to the vault."""
    with console.status("[cyan]Saving…[/] fetching, summarizing, and embedding"):
        try:
            result = core.save(text)
        except ValueError as exc:
            console.print(f"[red]✗[/] {exc}")
            raise typer.Exit(code=1) from exc

    item = result.item
    if not result.created:
        console.print(
            f"[yellow]•[/] Already saved as [bold]#{item.id}[/] — "
            f"[dim]{truncate(item.title, 60)}[/]"
        )
        return

    if result.warning:
        console.print(f"[yellow]![/] {result.warning} [dim]Saved the link anyway.[/]")

    console.print(_item_panel(item, title="Saved"))


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


@app.command()
def search(
    query: str = typer.Argument(..., help="What to search for."),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results to show."),
) -> None:
    """Search saved items by keyword and meaning (semantic)."""
    with console.status(f"[cyan]Searching[/] for “{query}”…"):
        hits = core.search(query, limit=limit)

    if not hits:
        console.print(f"[yellow]No matches for[/] “{query}”.")
        return

    table = Table(title=f"Results for “{query}”", title_style="bold", expand=True)
    table.add_column("#", justify="right", style="dim", no_wrap=True)
    table.add_column("Type", no_wrap=True)
    table.add_column("Title", style="bold", ratio=2)
    table.add_column("Summary", ratio=3)
    table.add_column("Match", no_wrap=True, style="dim")

    for hit in hits:
        item = hit.item
        table.add_row(
            str(item.id),
            _type_label(item),
            truncate(item.title, 50),
            truncate(item.summary or item.content or "—", 90),
            hit.matched_on,
        )
    console.print(table)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@app.command(name="list")
def list_items(
    limit: int = typer.Option(10, "--limit", "-n", help="How many items to show."),
) -> None:
    """Show recently saved items, newest first."""
    items = core.recent(limit=limit)
    if not items:
        console.print(
            "[dim]Your vault is empty. Save something with[/] "
            "[bold]linkvault save <url>[/]."
        )
        return

    table = Table(title="Recent items", title_style="bold", expand=True)
    table.add_column("#", justify="right", style="dim", no_wrap=True)
    table.add_column("Type", no_wrap=True)
    table.add_column("Title", style="bold", ratio=2)
    table.add_column("Tags", style="green", ratio=1)
    table.add_column("Saved", no_wrap=True, style="dim")

    for item in items:
        table.add_row(
            str(item.id),
            _type_label(item),
            truncate(item.title, 55),
            truncate(item.tag_string() or "—", 30),
            format_relative(item.created_at),
        )
    console.print(table)


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


@app.command()
def show(item_id: int = typer.Argument(..., help="The item id (from list/search).")) -> None:
    """Show a single item in full."""
    item = core.get(item_id)
    if item is None:
        console.print(f"[red]✗[/] No item with id [bold]#{item_id}[/].")
        raise typer.Exit(code=1)
    console.print(_item_panel(item, title=f"Item #{item.id}", full=True))


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@app.command()
def delete(item_id: int = typer.Argument(..., help="The item id to remove.")) -> None:
    """Delete an item from the vault."""
    if core.delete(item_id):
        console.print(f"[green]✓[/] Deleted item [bold]#{item_id}[/].")
    else:
        console.print(f"[red]✗[/] No item with id [bold]#{item_id}[/].")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------


@app.command()
def info() -> None:
    """Show configuration and vault status."""
    config = get_config()
    count = core.stats()
    ai_ready = config.use_ai and OllamaClient(config).is_available()

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Version", __version__)
    table.add_row("Database", str(config.db_path))
    table.add_row("Items stored", str(count))
    table.add_row("AI enabled", "yes" if config.use_ai else "no")
    table.add_row("Ollama", "[green]reachable[/]" if ai_ready else "[yellow]not reachable[/]")
    table.add_row("Chat model", config.ollama_model)
    table.add_row("Embed model", config.embed_model)
    console.print(Panel(table, title="[bold cyan]LinkVault[/]", border_style="cyan"))


# ---------------------------------------------------------------------------
# presentation helpers
# ---------------------------------------------------------------------------


def _type_label(item: Item) -> Text:
    """Return a colored label for an item's type."""
    style = _TYPE_STYLES.get(item.item_type.value, "white")
    return Text(item.item_type.value, style=style)


def _item_panel(item: Item, *, title: str, full: bool = False) -> Panel:
    """Render an item as a Rich panel."""
    body = Text()
    body.append(item.title + "\n", style="bold")

    if item.url:
        body.append(item.url + "\n", style="cyan underline")

    if item.summary:
        body.append("\n")
        body.append(item.summary + "\n", style="")

    if item.tags:
        body.append("\n")
        body.append(" ".join(f"#{t}" for t in item.tags), style="green")
        body.append("\n")

    if full and item.content:
        body.append("\n")
        preview = item.content if full else truncate(item.content, 500)
        body.append(preview + "\n", style="dim")

    meta = Text(
        f"#{item.id} · {item.item_type.value} · {format_relative(item.created_at)}",
        style="dim",
    )
    body.append("\n")
    body.append_text(meta)

    border = _TYPE_STYLES.get(item.item_type.value, "cyan")
    return Panel(body, title=f"[bold green]{title}[/]", border_style=border)


if __name__ == "__main__":  # pragma: no cover
    app()
