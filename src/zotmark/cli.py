from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from zotmark.config import AppConfig, find_config_path, load_config, save_config
from zotmark.models import CategoryRule
from zotmark.sync_engine import SyncEngine
from zotmark.zotero_client import ZoteroClient

console = Console()


@click.group()
def cli() -> None:
    """Zotmark: Sync your Zotero library and PDF annotations into Markdown notes."""
    pass


@cli.command("init")
@click.option("--config-path", "-c", default="config.yaml", help="Path to write the config file.")
def init(config_path: str) -> None:
    """Interactively configure categories, folders, and templates to sync."""
    console.print(
        Panel.fit(
            "[bold cyan]Zotmark - Setup Wizard[/bold cyan]\n"
            "Configure which Zotero categories to import into your notes directory and with which templates.",
            border_style="cyan",
        )
    )

    client = ZoteroClient()
    api_live = client.check_api_available()
    if api_live:
        console.print("[green]✔ Connected to Zotero Desktop API (port 23119)[/green]")
    else:
        console.print(
            "[yellow]! Zotero Desktop API not responding. Using local SQLite database fallback.[/yellow]"
        )

    # 1. Ask Notes Directory Path
    default_notes_path = (
        "/home/xenologos/Koofr/obsidian"
        if Path("/home/xenologos/Koofr/obsidian").exists()
        else "~/Notes"
    )
    notes_input = Prompt.ask(
        "Enter path to your Markdown notes directory",
        default=default_notes_path,
    )
    notes_path = Path(notes_input).expanduser().resolve()
    if not notes_path.exists():
        console.print(f"[yellow]Note: Directory '{notes_path}' does not exist yet.[/yellow]")

    # 2. Ask Default Output Folder
    default_dir = Prompt.ask(
        "Default folder for literature notes (relative to notes directory)",
        default="Literature",
    )

    # 3. Ask File Name Format
    filename_format = Prompt.ask(
        "File naming pattern (e.g. '{{ citekey }}' or '@{{ citekey }}')",
        default="{{ citekey }}",
    )

    # 4. Discover Collections & Item Types
    collections = client.get_collections()
    item_types = client.get_item_types()

    categories: list[CategoryRule] = []

    # Copy default templates locally if they don't exist yet
    templates_dir = Path.cwd() / "templates"
    src_templates = Path(__file__).resolve().parent.parent.parent / "templates"
    if src_templates.exists() and not templates_dir.exists():
        shutil.copytree(src_templates, templates_dir)
        console.print(f"[green]✔ Created local editable templates directory at {templates_dir}[/green]")

    console.print("\n[bold]Configuring Categories to Import:[/bold]")

    # Configure Collections
    if collections:
        console.print("\n[bold cyan]Found Collections in Zotero:[/bold cyan]")
        for coll in collections:
            include = Confirm.ask(
                f"  Sync collection '[bold]{coll.name}[/bold]' ({coll.num_items} items)?",
                default=True,
            )
            if include:
                out_folder = Prompt.ask(
                    f"    Target folder for '{coll.name}'",
                    default=f"{default_dir}/{coll.name.replace(' ', '_')}",
                )
                template_file = Prompt.ask(
                    f"    Template for '{coll.name}'",
                    default="templates/paper.md.j2",
                )
                categories.append(
                    CategoryRule(
                        name=f"Collection: {coll.name}",
                        match_collection=coll.name,
                        output_dir=out_folder,
                        template=template_file,
                        enabled=True,
                    )
                )

    # Configure Item Types (e.g., Books vs Journal Articles)
    console.print("\n[bold cyan]Found Item Types in Zotero:[/bold cyan]")
    if "book" in item_types:
        include_books = Confirm.ask(
            f"  Sync [bold]Books[/bold] ({item_types['book']} items) to a dedicated folder/template?",
            default=True,
        )
        if include_books:
            book_folder = Prompt.ask("    Folder for Books", default="Books")
            categories.append(
                CategoryRule(
                    name="Books",
                    match_item_type="book",
                    output_dir=book_folder,
                    template="templates/book.md.j2",
                    enabled=True,
                )
            )

    # Journal Articles & Preprints
    article_count = item_types.get("journalArticle", 0) + item_types.get("preprint", 0) + item_types.get("conferencePaper", 0)
    include_articles = Confirm.ask(
        f"  Sync [bold]Journal Articles & Preprints[/bold] ({article_count} items)?",
        default=True,
    )
    if include_articles:
        categories.append(
            CategoryRule(
                name="Journal Articles & Preprints",
                match_item_type=["journalArticle", "preprint", "conferencePaper"],
                output_dir=default_dir,
                template="templates/paper.md.j2",
                enabled=True,
            )
        )

    # Default fallback rule
    include_fallback = Confirm.ask(
        "  Include generic fallback rule for any other items?",
        default=True,
    )
    if include_fallback:
        categories.append(
            CategoryRule(
                name="All Other Items",
                output_dir=default_dir,
                template="templates/default.md.j2",
                enabled=True,
            )
        )

    config = AppConfig(
        notes_path=str(notes_path),
        default_output_dir=default_dir,
        file_name_format=filename_format,
        categories=categories,
    )

    saved_path = save_config(config, config_path)
    console.print(f"\n[bold green]✔ Configuration saved to {saved_path}[/bold green]")
    console.print("You can view or edit this file anytime, or run: [bold cyan]zotmark run[/bold cyan]")


@cli.command("list")
@click.option("--config-path", "-c", default=None, help="Path to config file.")
def list_categories(config_path: str | None) -> None:
    """List available Zotero categories and configured sync rules."""
    client = ZoteroClient()
    collections = client.get_collections()
    item_types = client.get_item_types()

    table = Table(title="Zotero Library Summary", box=box.ROUNDED)
    table.add_column("Type / Collection", style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_column("Key / ID", style="dim")

    for c in collections:
        table.add_row(f"📁 Collection: {c.name}", str(c.num_items), c.key)

    for t_name, count in item_types.items():
        table.add_row(f"📄 Type: {t_name}", str(count), "-")

    console.print(table)

    try:
        cfg = load_config(config_path)
        rule_table = Table(title="Configured Sync Rules", box=box.ROUNDED)
        rule_table.add_column("Rule Name", style="bold")
        rule_table.add_column("Filter", style="cyan")
        rule_table.add_column("Output Directory", style="yellow")
        rule_table.add_column("Template", style="magenta")
        rule_table.add_column("Enabled", justify="center")

        for r in cfg.categories:
            filt = []
            if r.match_collection:
                filt.append(f"coll='{r.match_collection}'")
            if r.match_item_type:
                filt.append(f"type={r.match_item_type}")
            rule_table.add_row(
                r.name,
                ", ".join(filt) if filt else "all",
                r.output_dir,
                r.template,
                "[green]yes[/green]" if r.enabled else "[red]no[/red]",
            )
        console.print(rule_table)
        console.print(
            "\n[dim]Tip: You can use any collection name or item type from above in your rules.[/dim]\n"
            "[dim]To edit your configuration file directly with all inline guides, run: [bold cyan]zotmark edit[/bold cyan][/dim]"
        )
    except Exception:
        console.print("[dim]No config.yaml found yet. Run 'zotmark init' to configure rules.[/dim]")


@cli.command("edit")
@click.option("--config-path", "-c", default=None, help="Path to config file.")
def edit_config(config_path: str | None) -> None:
    """Open config.yaml in your default text editor."""
    path = find_config_path(config_path)
    if not path.exists():
        console.print(f"[yellow]Config file not found at {path}. Generating standard config...[/yellow]")
        save_config(AppConfig(), path)

    console.print(f"[cyan]Opening config file:[/cyan] [bold]{path}[/bold]")
    click.edit(filename=str(path))


@cli.command("run")
@click.option("--dry-run", is_flag=True, help="Preview notes without writing to disk.")
@click.option("--force", is_flag=True, help="Overwrite notes even if unchanged.")
@click.option("--recent", "-n", type=int, default=None, help="Sync only N most recent items.")
@click.option("--key", "-k", type=str, default=None, help="Sync a specific item key.")
@click.option("--config-path", "-c", default=None, help="Path to config file.")
def run_sync(
    dry_run: bool,
    force: bool,
    recent: int | None,
    key: str | None,
    config_path: str | None,
) -> None:
    """Run synchronization of Zotero entries into Markdown notes."""
    try:
        config = load_config(config_path)
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return

    client = ZoteroClient(
        api_base_url=config.zotero_api_url,
        db_path=config.zotero_db_path,
    )
    engine = SyncEngine(config=config, client=client)

    mode_label = "[yellow](DRY RUN)[/yellow] " if dry_run else ""
    console.print(f"\n[bold]{mode_label}Starting Zotero to Markdown Sync...[/bold]")

    keys = [key] if key else None
    with console.status("[cyan]Fetching items from Zotero...[/cyan]"):
        items = client.get_items(limit=recent, keys=keys)

    console.print(f"Loaded [bold green]{len(items)}[/bold green] items from Zotero.")

    with console.status(f"[cyan]{mode_label}Rendering and syncing notes...[/cyan]"):
        stats = engine.sync_items(items=items, dry_run=dry_run, force=force)

    # Print Results Table
    result_table = Table(title=f"{mode_label}Sync Summary", box=box.ROUNDED)
    result_table.add_column("Status", style="bold")
    result_table.add_column("Count", justify="right")

    result_table.add_row("[green]Created[/green]", str(len(stats.created)))
    result_table.add_row("[yellow]Updated[/yellow]", str(len(stats.updated)))
    result_table.add_row("[dim]Skipped / Up-to-date[/dim]", str(stats.skipped))
    if stats.errors:
        result_table.add_row("[red]Errors[/red]", str(len(stats.errors)))

    console.print(result_table)

    if stats.created:
        console.print(f"\n[bold green]Sample Created Notes (showing first 5):[/bold green]")
        for p in stats.created[:5]:
            console.print(f"  + {p.name}")

    if stats.updated:
        console.print(f"\n[bold yellow]Sample Updated Notes (showing first 5):[/bold yellow]")
        for p in stats.updated[:5]:
            console.print(f"  ~ {p.name}")

    if stats.errors:
        console.print("\n[bold red]Errors encountered:[/bold red]")
        for item_key, err in stats.errors:
            console.print(f"  - Item {item_key}: {err}")


@cli.command("watch")
@click.option("--interval", "-i", type=int, default=300, help="Check interval in seconds (default: 300).")
@click.option("--config-path", "-c", default=None, help="Path to config file.")
def watch(interval: int, config_path: str | None) -> None:
    """Continuously watch Zotero and sync newly added/modified items."""
    console.print(f"[bold cyan]Watching Zotero for updates (checking every {interval}s)...[/bold cyan]")
    console.print("Press [bold red]Ctrl+C[/bold red] to stop.\n")

    try:
        config = load_config(config_path)
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return

    client = ZoteroClient(api_base_url=config.zotero_api_url, db_path=config.zotero_db_path)
    engine = SyncEngine(config=config, client=client)

    while True:
        try:
            items = client.get_items(limit=25)
            stats = engine.sync_items(items=items)
            if stats.created or stats.updated:
                t = time.strftime("%H:%M:%S")
                console.print(
                    f"[{t}] Synced: [green]+{len(stats.created)} created[/green], "
                    f"[yellow]~{len(stats.updated)} updated[/yellow]"
                )
        except Exception as e:
            console.print(f"[red]Watch error: {e}[/red]")

        time.sleep(interval)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
