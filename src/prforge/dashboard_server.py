"""Web dashboard backend (FastAPI).

Stores runs in a JSON file and exposes:
    GET  /api/runs            list runs
    GET  /api/runs/{id}       run detail (diff, status)
    POST /api/solve           {issue_url, dry_run} -> run the agent, store result
    POST /api/runs/{id}/approve   mark a run approved

Run with:  prforge dashboard
Requires:  pip install 'prforge[dashboard]'
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from prforge.config import Config
from prforge.llm import LLMClient
from prforge.runner import run_solve

RUNS_FILE = Path("./dashboard/runs.json")
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "dashboard" / "frontend" / "dist"

# Overridable in tests; defaults to the configured LLM.
llm_factory: Callable[[Config], LLMClient] = None  # set in _default_llm_factory


class SolveRequest(BaseModel):
    issue_url: str
    dry_run: bool = True


def _default_llm_factory(cfg: Config) -> LLMClient:
    from prforge.llm import get_llm
    return get_llm(cfg)


llm_factory = _default_llm_factory


def _load_runs() -> list[dict]:
    if RUNS_FILE.exists():
        return json.loads(RUNS_FILE.read_text(encoding="utf-8"))
    return []


def _save_runs(runs: list[dict]) -> None:
    RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNS_FILE.write_text(json.dumps(runs, indent=2), encoding="utf-8")


def _new_run(issue_url: str, dry_run: bool) -> dict:
    return {
        "id": uuid.uuid4().hex[:8],
        "issue_url": issue_url,
        "dry_run": dry_run,
        "status": "running",
        "approved": False,
        "created_at": time.time(),
    }


app = FastAPI(title="PRForge Dashboard", version="0.1.0")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "prforge-dashboard"}


@app.get("/api/runs")
def list_runs() -> dict:
    return {"runs": _load_runs()}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    for r in _load_runs():
        if r["id"] == run_id:
            return r
    raise HTTPException(status_code=404, detail="run not found")


@app.post("/api/solve")
def solve(req: SolveRequest) -> dict:
    cfg = Config.from_env()
    cfg.approval_callback = lambda c, s: True  # dashboard records approval separately
    run = _new_run(req.issue_url, req.dry_run)
    try:
        final = run_solve(req.issue_url, cfg, llm_factory(cfg), log=lambda m: None, dry_run=req.dry_run)
        run.update({
            "status": "error" if final.get("error") else "done",
            "iterations": final.get("iterations", 0),
            "edits_applied": final.get("edits_applied", 0),
            "test_pass": final.get("test_pass"),
            "diff": final.get("diff", ""),
            "pr_url": final.get("pr_url", ""),
            "error": final.get("error"),
        })
    except Exception as e:  # pragma: no cover - defensive
        run.update({"status": "error", "error": str(e)})
    runs = _load_runs()
    runs.append(run)
    _save_runs(runs)
    return run


@app.post("/api/runs/{run_id}/approve")
def approve(run_id: str) -> dict:
    runs = _load_runs()
    for r in runs:
        if r["id"] == run_id:
            r["approved"] = True
            _save_runs(runs)
            return r
    raise HTTPException(status_code=404, detail="run not found")


# Serve the built React frontend if present.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


def run_dashboard(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Entry point for `prforge dashboard`."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)
