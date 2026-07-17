"""MCP server mode.

Exposes PRForge's capabilities as MCP tools so other agents (Claude Desktop,
Cursor, etc.) can call them:

    fetch_issue(url)            -> issue text
    solve_issue(url, dry_run)   -> run the agent, return diff + status
    get_diff(url)               -> current diff in the workdir

Run with:  prforge mcp
Requires the `mcp` package:  pip install 'prforge[mcp]'
"""

from __future__ import annotations

from pathlib import Path

from prforge.config import Config
from prforge.llm import get_llm
from prforge.runner import run_solve
from prforge.tools import codebase, github


def _make_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "The `mcp` package is required. Install with: pip install 'prforge[mcp]'"
        ) from e

    mcp = FastMCP("prforge")

    @mcp.tool()
    def fetch_issue(url: str) -> str:
        """Fetch a GitHub issue's title, state, labels, and body."""
        owner, repo, number = github.parse_issue_url(url)
        issue = github.fetch_issue(owner, repo, number)
        labels = ", ".join(issue.labels) or "none"
        return f"{issue.title}\n{issue.slug} · {issue.state} · {labels}\n\n{issue.body}"

    @mcp.tool()
    def solve_issue(url: str, dry_run: bool = True) -> str:
        """Run the PRForge agent on a GitHub issue. Returns a status summary and diff.

        Args:
            url: GitHub issue URL.
            dry_run: If True (default), do not push or open a PR.
        """
        cfg = Config.from_env()
        cfg.approval_callback = lambda c, s: True  # non-interactive in MCP mode
        llm = get_llm(cfg)
        final = run_solve(url, cfg, llm, log=lambda m: None, dry_run=dry_run)
        diff = final.get("diff", "")
        return (
            f"iterations={final.get('iterations', 0)} "
            f"edits={final.get('edits_applied', 0)} "
            f"tests={'pass' if final.get('test_pass') else 'fail/none'} "
            f"pr={final.get('pr_url') or '(none)'}\n\n--- diff ---\n{diff}"
        )

    @mcp.tool()
    def get_diff(url: str) -> str:
        """Return the current git diff in the workdir for a solved issue."""
        owner, repo, number = github.parse_issue_url(url)
        workdir = str(Path("./workdir") / f"{owner}_{repo}_{number}")
        if not Path(workdir).exists():
            return f"no workdir found at {workdir}"
        return codebase.git_diff(workdir) or "(no changes)"

    return mcp


def run_mcp_server() -> None:
    """Entry point for `prforge mcp`."""
    mcp = _make_server()
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    run_mcp_server()
