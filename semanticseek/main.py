#!/usr/bin/env python3
"""
SemanticSeek — Natural language file search powered by local embeddings.
"""

import sys
import os
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import box
from typing import Optional
from pathlib import Path

from semanticseek import indexer, searcher, store

app = typer.Typer(
    name="semanticseek",
    help="🔍 Semantic file search — find documents by meaning, not keywords.",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


def print_banner():
    banner = Text()
    banner.append("  ███████╗███████╗███╗   ███╗ █████╗ ███╗   ██╗████████╗██╗ ██████╗\n", style="bold cyan")
    banner.append("  ██╔════╝██╔════╝████╗ ████║██╔══██╗████╗  ██║╚══██╔══╝██║██╔════╝\n", style="bold cyan")
    banner.append("  ███████╗█████╗  ██╔████╔██║███████║██╔██╗ ██║   ██║   ██║██║     \n", style="bold blue")
    banner.append("  ╚════██║██╔══╝  ██║╚██╔╝██║██╔══██║██║╚██╗██║   ██║   ██║██║     \n", style="bold blue")
    banner.append("  ███████║███████╗██║ ╚═╝ ██║██║  ██║██║ ╚████║   ██║   ██║╚██████╗\n", style="bold magenta")
    banner.append("  ╚══════╝╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝ ╚═════╝\n", style="bold magenta")
    banner.append("  ╔═══════════════════════════════════════════════════════════════╗\n", style="dim")
    banner.append("  ║  Natural language search · Local embeddings · Zero GPU needed ║\n", style="dim")
    banner.append("  ╚═══════════════════════════════════════════════════════════════╝\n", style="dim")
    console.print(banner)


@app.command()
def index(
    path: str = typer.Argument(..., help="Folder to index"),
    db: str = typer.Option("~/.semanticseek/db", help="Path to vector database"),
    force: bool = typer.Option(False, "--force", "-f", help="Re-index already indexed files"),
):
    """
    [bold cyan]Index[/bold cyan] a folder of documents (.txt, .md, .pdf) for semantic search.
    """
    print_banner()
    folder = Path(path).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        console.print(f"[bold red]✗[/bold red] Path does not exist or is not a directory: {folder}")
        raise typer.Exit(1)

    db_path = Path(db).expanduser().resolve()
    db_path.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]📂 Indexing:[/bold] [cyan]{folder}[/cyan]")
    console.print(f"[bold]💾 Database:[/bold] [cyan]{db_path}[/cyan]\n")

    collection = store.get_collection(str(db_path))
    files = indexer.discover_files(folder)

    if not files:
        console.print("[yellow]⚠ No supported files found (.txt, .md, .pdf)[/yellow]")
        raise typer.Exit(0)

    console.print(f"[bold]Found {len(files)} file(s)[/bold]\n")

    model = None
    indexed = 0
    skipped = 0

    with Progress(
        SpinnerColumn(spinner_name="dots", style="cyan"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30, style="cyan", complete_style="bold cyan"),
        TaskProgressColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("[cyan]Loading embedding model...", total=len(files))

        # Lazy load model — shown once
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        progress.update(task, description="[cyan]Indexing files...")

        for file in files:
            rel = file.relative_to(folder)
            progress.update(task, description=f"[cyan]{rel}")

            if not force and store.is_indexed(collection, str(file)):
                skipped += 1
                progress.advance(task)
                continue

            chunks = indexer.extract_chunks(file)
            if chunks:
                embeddings = model.encode([c["text"] for c in chunks], show_progress_bar=False).tolist()
                store.upsert_chunks(collection, str(file), chunks, embeddings)
                indexed += 1
            else:
                skipped += 1

            progress.advance(task)

    console.print()
    console.print(Panel(
        f"[bold green]✔ Done![/bold green]\n\n"
        f"  Indexed  : [bold cyan]{indexed}[/bold cyan] file(s)\n"
        f"  Skipped  : [dim]{skipped}[/dim] (already up to date, use --force to re-index)\n\n"
        f"  Run [bold]semanticseek search \"your query\"[/bold] to start searching.",
        title="[bold]Index Complete[/bold]",
        border_style="cyan",
        padding=(1, 2),
    ))


@app.command()
def search(
    query: str = typer.Argument(..., help="Natural language search query"),
    db: str = typer.Option("~/.semanticseek/db", help="Path to vector database"),
    top: int = typer.Option(5, "--top", "-n", help="Number of results to return"),
    show_snippet: bool = typer.Option(True, "--snippet/--no-snippet", help="Show text snippet"),
):
    """
    [bold cyan]Search[/bold cyan] your indexed documents using natural language.
    """
    print_banner()
    db_path = Path(db).expanduser().resolve()

    if not db_path.exists():
        console.print("[bold red]✗[/bold red] No index found. Run [bold]semanticseek index <folder>[/bold] first.")
        raise typer.Exit(1)

    collection = store.get_collection(str(db_path))

    with console.status("[cyan]Loading model & searching...", spinner="dots"):
        results = searcher.search(collection, query, top_k=top)

    if not results:
        console.print(Panel(
            "[yellow]No results found.[/yellow]\n\nTry a different query or re-index with [bold]semanticseek index <folder>[/bold]",
            border_style="yellow",
        ))
        raise typer.Exit(0)

    console.print(f"\n[bold]Query:[/bold] [italic cyan]\"{query}\"[/italic cyan]")
    console.print(f"[dim]Top {len(results)} result(s)\n[/dim]")

    table = Table(
        box=box.ROUNDED,
        border_style="cyan",
        show_header=True,
        header_style="bold cyan",
        padding=(0, 1),
        expand=True,
    )
    table.add_column("#", style="bold dim", width=3, justify="right")
    table.add_column("File", style="bold white", no_wrap=False)
    table.add_column("Score", style="bold green", width=7, justify="center")
    if show_snippet:
        table.add_column("Snippet", style="dim", no_wrap=False)

    for i, r in enumerate(results, 1):
        score_pct = f"{r['score']*100:.1f}%"
        file_path = Path(r["file"])
        display_path = str(file_path)

        # Try to make path shorter for display
        try:
            display_path = str(file_path.relative_to(Path.home()))
            display_path = "~/" + display_path
        except ValueError:
            pass

        snippet = ""
        if show_snippet:
            raw = r.get("snippet", "")
            # Trim and clean
            snippet = " ".join(raw.split())[:180]
            if len(raw.strip()) > 180:
                snippet += "…"

        if show_snippet:
            table.add_row(str(i), display_path, score_pct, snippet)
        else:
            table.add_row(str(i), display_path, score_pct)

    console.print(table)
    console.print()


@app.command()
def status(
    db: str = typer.Option("~/.semanticseek/db", help="Path to vector database"),
):
    """
    [bold cyan]Show[/bold cyan] index stats — how many files and chunks are indexed.
    """
    print_banner()
    db_path = Path(db).expanduser().resolve()

    if not db_path.exists():
        console.print("[bold red]✗[/bold red] No index found. Run [bold]semanticseek index <folder>[/bold] first.")
        raise typer.Exit(1)

    collection = store.get_collection(str(db_path))
    stats = store.get_stats(collection)

    console.print(Panel(
        f"  [bold]Total chunks indexed:[/bold] [cyan]{stats['total_chunks']}[/cyan]\n"
        f"  [bold]Unique files:[/bold]         [cyan]{stats['unique_files']}[/cyan]\n"
        f"  [bold]Database path:[/bold]         [dim]{db_path}[/dim]",
        title="[bold]SemanticSeek Index Status[/bold]",
        border_style="cyan",
        padding=(1, 2),
    ))


@app.command()
def clear(
    db: str = typer.Option("~/.semanticseek/db", help="Path to vector database"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """
    [bold red]Clear[/bold red] the entire index database.
    """
    db_path = Path(db).expanduser().resolve()
    if not yes:
        confirm = typer.confirm(f"⚠  This will delete the index at {db_path}. Continue?")
        if not confirm:
            raise typer.Exit(0)

    import shutil
    if db_path.exists():
        shutil.rmtree(db_path)
        console.print("[bold green]✔[/bold green] Index cleared.")
    else:
        console.print("[yellow]No index found.[/yellow]")


def main():
    app()


if __name__ == "__main__":
    main()
