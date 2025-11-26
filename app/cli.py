"""
Timepoint Flash CLI Tool

Batteries-included command-line interface for generating and viewing
photorealistic historical scenes.

Usage:
    tp generate "query"  - Generate a timepoint
    tp list              - List all timepoints
    tp serve             - Start server with gallery
    tp demo              - Quick demo mode
"""
import click
import httpx
import time
import sys
import webbrowser
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import print as rprint
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

console = Console()

# API Configuration
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

# Demo queries that always look good
DEMO_QUERIES = [
    "Medieval marketplace in London, winter 1250",
    "Ancient Rome forum, summer 50 BCE",
    "American Revolutionary War, Valley Forge 1777",
]


def validate_environment():
    """Validate that all required dependencies are installed."""
    missing_packages = []

    try:
        import fastapi
    except ImportError:
        missing_packages.append("fastapi")

    try:
        import uvicorn
    except ImportError:
        missing_packages.append("uvicorn")

    try:
        import sqlalchemy
    except ImportError:
        missing_packages.append("sqlalchemy")

    if missing_packages:
        console.print("[red]✗ Missing required packages[/red]")
        console.print(f"\nMissing: {', '.join(missing_packages)}")
        console.print("\nPlease run the setup script:")
        console.print("[yellow]./setup.sh[/yellow]")
        console.print("\nOr install dependencies manually:")
        console.print("[yellow]uv sync[/yellow]  # or: pip install -e .")
        sys.exit(1)


def check_api_key():
    """Check if OpenRouter API key is configured."""
    if not OPENROUTER_KEY or OPENROUTER_KEY == "your_key_here":
        console.print("[red]✗ OPENROUTER_API_KEY not configured[/red]")
        console.print("\nPlease add your OpenRouter API key to .env:")
        console.print("[yellow]echo \"OPENROUTER_API_KEY=your_key_here\" >> .env[/yellow]")
        console.print("\nGet your key at: https://openrouter.ai/keys")
        console.print("\nOr run setup script to configure interactively:")
        console.print("[yellow]./setup.sh[/yellow]")
        sys.exit(1)


def check_server(start_if_needed=False):
    """Check if API server is running."""
    try:
        response = httpx.get(f"{API_BASE}/health", timeout=2.0)
        return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        if start_if_needed:
            console.print("[yellow]⚠ Server not running, starting it...[/yellow]")
            start_server(background=True)
            time.sleep(2)  # Wait for server to start
            return check_server(start_if_needed=False)
        return False


def start_server(background=False, port=8000):
    """Start the FastAPI server."""
    import subprocess

    cmd = [sys.executable, "-m", "uvicorn", "app.main:app", f"--port={port}"]

    if background:
        # Start in background
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
    else:
        # Run in foreground
        subprocess.run(cmd)


@click.group()
@click.version_option(version="1.0.0", prog_name="Timepoint Flash")
def main():
    """
    🎬 TIMEPOINT FLASH - Photorealistic Time Travel CLI

    Generate and view AI-powered historical scenes with just an OpenRouter API key.
    """
    pass


@main.command()
@click.argument("query")
@click.option("--email", default="cli@timepoint.local", help="Email for tracking")
@click.option("--wait", is_flag=True, help="Wait for generation to complete")
def generate(query: str, email: str, wait: bool):
    """
    Generate a timepoint from a historical query.

    Example:
        tp generate "Medieval marketplace, London 1250"
    """
    check_api_key()

    if not check_server(start_if_needed=True):
        console.print("[red]✗ Could not connect to API server[/red]")
        sys.exit(1)

    console.print(Panel(
        f"[bold cyan]{query}[/bold cyan]",
        title="🎬 Generating Timepoint",
        border_style="cyan"
    ))

    try:
        # Create timepoint
        response = httpx.post(
            f"{API_BASE}/api/timepoint/create",
            json={"query": query, "email": email},
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()

        session_id = data.get("session_id")
        slug = data.get("slug")

        console.print(f"\n[green]✓[/green] Generation started!")
        console.print(f"Session ID: [cyan]{session_id}[/cyan]")

        if wait:
            console.print("\n[yellow]⏳ Waiting for generation to complete...[/yellow]")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Generating...", total=None)

                # Poll for completion
                max_attempts = 60  # 10 minutes max
                for attempt in range(max_attempts):
                    time.sleep(10)

                    try:
                        # Check feed for our timepoint
                        feed_response = httpx.get(f"{API_BASE}/api/feed?limit=20")
                        feed_data = feed_response.json()

                        for tp in feed_data.get("timepoints", []):
                            if tp.get("input_query") == query:
                                progress.update(task, description="[green]Complete![/green]")
                                console.print(f"\n[green]✓ Timepoint generated successfully![/green]")
                                console.print(f"View at: [cyan]{API_BASE}/view/{tp.get('slug')}[/cyan]")
                                return
                    except Exception:
                        pass

                    progress.update(task, description=f"Still generating... ({attempt * 10}s)")

                console.print("\n[yellow]⚠ Generation taking longer than expected[/yellow]")
                console.print("Check the gallery to see if it completed")
        else:
            console.print(f"\n[dim]Use --wait to wait for completion[/dim]")
            console.print(f"Or view progress at: [cyan]{API_BASE}/generate[/cyan]")

    except httpx.HTTPError as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        sys.exit(1)


@main.command()
@click.option("--limit", default=20, help="Number of timepoints to show")
def list(limit: int):
    """
    List all generated timepoints.

    Example:
        tp list --limit 10
    """
    if not check_server(start_if_needed=True):
        console.print("[red]✗ Could not connect to API server[/red]")
        sys.exit(1)

    try:
        response = httpx.get(f"{API_BASE}/api/feed?limit={limit}")
        response.raise_for_status()
        data = response.json()

        timepoints = data.get("timepoints", [])
        total = data.get("total", 0)

        if not timepoints:
            console.print("[yellow]No timepoints found. Generate one with:[/yellow]")
            console.print("[cyan]tp generate \"your query here\"[/cyan]")
            return

        table = Table(title=f"📚 Timepoints ({total} total)", show_header=True, header_style="bold cyan")
        table.add_column("Slug", style="cyan")
        table.add_column("Year", justify="right")
        table.add_column("Season")
        table.add_column("Query", style="dim")

        for tp in timepoints:
            table.add_row(
                tp.get("slug", ""),
                str(tp.get("year", "")),
                tp.get("season", ""),
                tp.get("input_query", "")[:50] + "..." if len(tp.get("input_query", "")) > 50 else tp.get("input_query", "")
            )

        console.print(table)
        console.print(f"\n[dim]View in gallery: [cyan]{API_BASE}[/cyan][/dim]")

    except httpx.HTTPError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        sys.exit(1)


@main.command()
@click.option("--port", default=8000, help="Port to run server on")
@click.option("--open-browser", is_flag=True, help="Auto-open browser")
@click.option("--gallery", is_flag=True, default=True, help="Enable gallery UI")
def serve(port: int, open_browser: bool, gallery: bool):
    """
    Start the Timepoint Flash server with gallery.

    Example:
        tp serve --port 8000 --open-browser
    """
    console.print(Panel(
        f"[bold green]Starting Timepoint Flash Server[/bold green]\n\n"
        f"Gallery: [cyan]http://localhost:{port}[/cyan]\n"
        f"API Docs: [cyan]http://localhost:{port}/api/docs[/cyan]\n\n"
        f"[dim]Press Ctrl+C to stop[/dim]",
        border_style="green"
    ))

    if open_browser:
        # Wait a moment for server to start, then open browser
        import threading
        def open_after_delay():
            time.sleep(2)
            webbrowser.open(f"http://localhost:{port}")
        threading.Thread(target=open_after_delay, daemon=True).start()

    start_server(background=False, port=port)


@main.command()
@click.option("--port", default=8000, help="Port to run server on")
def demo(port: int):
    """
    Quick demo mode - generates 3 sample timepoints and opens gallery.

    Perfect for first-time users to see Timepoint Flash in action!

    Example:
        tp demo
    """
    # Validate environment first
    validate_environment()
    check_api_key()

    console.print(Panel(
        "[bold cyan]🎬 TIMEPOINT FLASH - Demo Mode[/bold cyan]\n\n"
        "[dim]Generating 3 stunning historical scenes...[/dim]",
        border_style="cyan"
    ))

    # Start server
    if not check_server(start_if_needed=True):
        console.print("[red]✗ Could not start server[/red]")
        sys.exit(1)

    time.sleep(2)  # Let server fully start

    # Check if we already have demo timepoints
    try:
        response = httpx.get(f"{API_BASE}/api/feed?limit=10")
        existing = response.json().get("timepoints", [])

        demo_queries_set = set(DEMO_QUERIES)
        existing_queries = {tp.get("input_query") for tp in existing}

        missing_demos = [q for q in DEMO_QUERIES if q not in existing_queries]

        if not missing_demos:
            console.print("\n[green]✓ Demo timepoints already exist![/green]")
        else:
            console.print(f"\n[yellow]Generating {len(missing_demos)} demo timepoint(s)...[/yellow]\n")

            for i, query in enumerate(missing_demos, 1):
                console.print(f"[{i}/{len(missing_demos)}] [cyan]{query}[/cyan]")

                try:
                    response = httpx.post(
                        f"{API_BASE}/api/timepoint/create",
                        json={"query": query, "email": "demo@timepoint.local"},
                        timeout=30.0
                    )
                    response.raise_for_status()
                    console.print(f"  [green]✓[/green] Started generation\n")
                except Exception as e:
                    console.print(f"  [red]✗[/red] Error: {e}\n")

            console.print("\n[yellow]⏳ Generation in progress (takes ~1-2 minutes each)...[/yellow]")
            console.print("[dim]You can watch the progress in the gallery![/dim]\n")

    except Exception as e:
        console.print(f"[red]✗ Error checking existing demos: {e}[/red]")

    # Open gallery
    gallery_url = f"http://localhost:{port}"
    console.print(Panel(
        f"[bold green]Opening gallery in browser...[/bold green]\n\n"
        f"[cyan]{gallery_url}[/cyan]\n\n"
        f"[dim]The server will keep running. Press Ctrl+C to stop.[/dim]",
        border_style="green"
    ))

    webbrowser.open(gallery_url)

    # Keep server running
    console.print("\n[dim]Server is running. View the gallery in your browser.[/dim]")
    console.print("[dim]Press Ctrl+C to stop the server.[/dim]\n")

    try:
        start_server(background=False, port=port)
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Server stopped.[/yellow]")


if __name__ == "__main__":
    main()
