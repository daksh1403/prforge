"""Batch mode: solve multiple issues from a file and summarise."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from prforge.config import Config
from prforge.llm import LLMClient
from prforge.runner import run_solve


def load_issue_urls(path: str | Path) -> list[str]:
    """Read a file of GitHub issue URLs (one per line; # comments ignored)."""
    p = Path(path)
    out: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def run_batch(
    issue_urls: list[str],
    cfg: Config,
    llm_factory: Callable[[Config], LLMClient],
    log: Callable[[str], None] = print,
    dry_run: bool = True,
) -> dict:
    """Solve each issue (dry-run by default) and return a summary."""
    # Batch never blocks on the interactive gate.
    cfg.approval_callback = lambda c, s: True
    results: list[dict] = []
    for i, url in enumerate(issue_urls, 1):
        log(f"[{i}/{len(issue_urls)}] {url}")
        llm = llm_factory(cfg)
        try:
            final = run_solve(url, cfg, llm, log=log, dry_run=dry_run)
            results.append({
                "url": url,
                "ok": not final.get("error"),
                "iterations": final.get("iterations", 0),
                "edits_applied": final.get("edits_applied", 0),
                "test_pass": final.get("test_pass"),
                "error": final.get("error"),
            })
        except Exception as e:  # pragma: no cover - defensive
            results.append({"url": url, "ok": False, "error": str(e), "iterations": 0})
    succeeded = sum(1 for r in results if r["ok"])
    return {"succeeded": succeeded, "total": len(results), "results": results}
