"""PRForge command-line interface.

Commands:
    solve   <issue-url>   full agent loop (dry-run by default)
    fetch   <issue-url>   fetch + print an issue (no LLM)
    map     <repo-url>    clone + print a repo map (no LLM)
    diff    <issue-url>   show the diff in a solve workdir
    eval    [instances]   run the eval harness (--self-test needs no key)
    batch   <file>        solve many issue URLs from a file
    mcp                   run as an MCP server (expose tools to other agents)
    dashboard             run the web dashboard (FastAPI + React)
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from prforge import __version__
from prforge.config import Config
from prforge.llm import get_llm
from prforge.runner import run_solve
from prforge.tools import codebase, github

app = typer.Typer(
    name="prforge",
    help="Agentic PR bot: read a GitHub issue, write a fix, run tests, open a reviewed PR.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def _banner() -> None:
    console.print(Panel.fit(
        f"[bold cyan]PRForge[/bold cyan] [dim]v{__version__}[/dim] — agentic PR bot for GSoC",
        border_style="cyan",
    ))


def _interactive_approval(cfg: Config, state: dict) -> bool:
    diff = state.get("diff", "")
    if diff:
        console.print(Syntax(diff, "diff", theme="ansi_dark", word_wrap=True))
    else:
        console.print("[yellow]No diff produced (the agent made no changes).[/yellow]")
    return typer.confirm("Approve and open a PR with these changes?", default=False)


def _build_cfg(**overrides) -> Config:
    cfg = Config.from_env(**overrides)
    problems = cfg.validate()
    if problems:
        for p in problems:
            console.print(f"[red]✗[/red] {p}")
        raise typer.Exit(1)
    return cfg


@app.callback(invoke_without_command=True)
def _root(version: bool = typer.Option(False, "--version", "-V", help="Show version and exit.")):
    if version:
        console.print(f"prforge {__version__}")
        raise typer.Exit()


@app.command()
def solve(
    issue_url: str = typer.Argument(..., help="GitHub issue URL."),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Dry run: do not push or open a PR."),
    yes: bool = typer.Option(False, "--yes", help="Skip the interactive approval gate."),
    provider: str = typer.Option(None, "--provider", help="Override LLM provider."),
    model: str = typer.Option(None, "--model", help="Override LLM model."),
):
    """Solve a GitHub issue end-to-end and (optionally) open a PR."""
    _banner()
    cfg = _build_cfg(**({"llm_provider": provider} if provider else {}),
                     **({"model": model} if model else {}))
    cfg.approval_callback = (lambda c, s: True) if (yes or cfg.auto_approve) else _interactive_approval

    def log(msg: str) -> None:
        console.print(f"[dim]•[/dim] {msg}")

    console.print(f"[green]→[/green] Solving [bold]{issue_url}[/bold]")
    final = run_solve(issue_url, cfg, get_llm(cfg), log=log, dry_run=dry_run)

    if final.get("error"):
        console.print(f"[red]✗ Error:[/red] {final['error']}")
        raise typer.Exit(1)
    console.print(Panel.fit(
        f"[bold green]Done.[/bold green]\n"
        f"Iterations: {final.get('iterations', 0)}  |  Edits: {final.get('edits_applied', 0)}  |  "
        f"Tests: {'pass' if final.get('test_pass') else 'fail/none'}\n"
        f"PR: {final.get('pr_url') or '(dry run — no PR)'}",
        title="Result", border_style="green",
    ))


@app.command()
def fetch(issue_url: str = typer.Argument(..., help="GitHub issue URL.")):
    """Fetch and print a GitHub issue (no LLM needed)."""
    _banner()
    owner, repo, number = github.parse_issue_url(issue_url)
    issue = github.fetch_issue(owner, repo, number)
    console.print(Panel.fit(
        f"[bold]{issue.title}[/bold]\n[dim]{issue.slug}[/dim] · {issue.state} · "
        f"{', '.join(issue.labels) or 'no labels'}", title="Issue"))
    console.print(issue.body or "(no body)")


@app.command()
def map(repo_url: str = typer.Argument(..., help="Git URL to clone and map.")):
    """Clone a repo and print its repo map (no LLM needed)."""
    _banner()
    name = repo_url.rstrip("/").split("/")[-1].removesuffix(".git")
    workdir = str(Path("./workdir") / name)
    if not Path(workdir).exists():
        console.print(f"[green]→[/green] Cloning {name} ...")
        if not codebase.clone_repo(repo_url, workdir):
            console.print("[red]✗ clone failed[/red]")
            raise typer.Exit(1)
    console.print(Panel(codebase.build_repo_map(workdir), title=f"Repo map — {name}", border_style="cyan"))


@app.command()
def diff(issue_url: str = typer.Argument(..., help="GitHub issue URL (names the workdir).")):
    """Show the current diff in the cloned workdir for an issue."""
    _banner()
    owner, repo, number = github.parse_issue_url(issue_url)
    workdir = str(Path("./workdir") / f"{owner}_{repo}_{number}")
    if not Path(workdir).exists():
        console.print(f"[red]✗ no workdir at {workdir}. Run `prforge solve` first.[/red]")
        raise typer.Exit(1)
    d = codebase.git_diff(workdir)
    console.print(Syntax(d or "(no changes)", "diff", theme="ansi_dark", word_wrap=True))


@app.command()
def eval(
    instances: str = typer.Argument(None, help="Path to instances.jsonl"),
    self_test: bool = typer.Option(False, "--self-test", help="Run built-in eval with a fake LLM (no API key)."),
    provider: str = typer.Option(None, "--provider", help="Override LLM provider."),
    model: str = typer.Option(None, "--model", help="Override LLM model."),
):
    """Run the SWE-bench-style eval harness and print the resolve rate."""
    _banner()
    cfg = _build_cfg(**({"llm_provider": provider} if provider else {}),
                    **({"model": model} if model else {}))

    def log(msg: str) -> None:
        console.print(f"[dim]•[/dim] {msg}")

    if self_test:
        from prforge.eval.runner import self_test as _self_test
        result = _self_test(cfg, log=log)
    else:
        if not instances:
            console.print("[red]✗ Provide an instances file or use --self-test.[/red]")
            raise typer.Exit(1)
        from prforge.eval.runner import load_instances, run_eval
        insts = load_instances(instances)
        result = run_eval(insts, cfg, lambda c: get_llm(c), log=log)

    table = Table(title="Eval results", border_style="cyan")
    table.add_column("Instance")
    table.add_column("Resolved", justify="center")
    table.add_column("Iters", justify="right")
    table.add_column("Edits", justify="right")
    for r in result["results"]:
        table.add_row(
            r["id"],
            "[green]✓[/green]" if r["resolved"] else "[red]✗[/red]",
            str(r.get("iterations", "-")),
            str(r.get("edits_applied", "-")),
        )
    console.print(table)
    console.print(Panel.fit(
        f"[bold]Resolve rate: {result['resolved']}/{result['total']} "
        f"({result['resolve_rate'] * 100:.1f}%)[/bold]",
        border_style="green",
    ))


@app.command()
def batch(
    file: str = typer.Argument(..., help="File of GitHub issue URLs (one per line)."),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Dry run: do not push."),
    provider: str = typer.Option(None, "--provider", help="Override LLM provider."),
    model: str = typer.Option(None, "--model", help="Override LLM model."),
):
    """Solve many issues from a file and print a summary."""
    _banner()
    cfg = _build_cfg(**({"llm_provider": provider} if provider else {}),
                    **({"model": model} if model else {}))

    def log(msg: str) -> None:
        console.print(f"[dim]•[/dim] {msg}")

    from prforge.batch import load_issue_urls, run_batch
    urls = load_issue_urls(file)
    if not urls:
        console.print("[yellow]No issue URLs found in file.[/yellow]")
        raise typer.Exit(1)
    result = run_batch(urls, cfg, lambda c: get_llm(c), log=log, dry_run=dry_run)

    table = Table(title="Batch results", border_style="cyan")
    table.add_column("Issue")
    table.add_column("Status", justify="center")
    table.add_column("Edits", justify="right")
    for r in result["results"]:
        table.add_row(
            r["url"].split("/")[-1] or r["url"],
            "[green]ok[/green]" if r["ok"] else "[red]error[/red]",
            str(r.get("edits_applied", "-")),
        )
    console.print(table)
    console.print(f"[bold]Succeeded: {result['succeeded']}/{result['total']}[/bold]")


@app.command()
def mcp():
    """Run PRForge as an MCP server (expose tools to other agents)."""
    from prforge.mcp_server import run_mcp_server
    run_mcp_server()


@app.command()
def dashboard(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
):
    """Run the web dashboard (FastAPI backend + React frontend)."""
    from prforge.dashboard_server import run_dashboard
    run_dashboard(host=host, port=port)


if __name__ == "__main__":
    app()
