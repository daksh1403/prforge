"""Tests for the dashboard API (uses FastAPI TestClient)."""

import sys
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import prforge.dashboard_server as ds
from prforge.llm import LLMClient
from prforge.tools import codebase, github
from prforge.tools.github import Issue


class _FakeLLM(LLMClient):
    def complete(self, system, messages):
        if "triaging" in system:
            return '["buggy.py"]'
        if "step-by-step plan" in system:
            return "Change multiply to return a * b."
        if "SEARCH/REPLACE" in system:
            return ("buggy.py\n<<<<<<< SEARCH\ndef multiply(a, b):\n    return a + b\n"
                    "=======\ndef multiply(a, b):\n    return a * b\n>>>>>>> REPLACE")
        if "pull request" in system:
            return "TITLE: fix\nBODY:\n- fixed\n\nCloses #1"
        return ""


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    # isolate the runs file + workdir
    monkeypatch.setattr(ds, "RUNS_FILE", tmp_path / "runs.json")
    monkeypatch.setattr(ds, "llm_factory", lambda cfg: _FakeLLM())
    # patch network nodes to a local buggy repo
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "buggy.py").write_text("def multiply(a, b):\n    return a + b\n")
    (repo / "test_buggy.py").write_text(
        "from buggy import multiply\n\n\ndef test_multiply():\n    assert multiply(3, 4) == 12\n"
    )
    (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    import shutil, subprocess
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    import shutil
    monkeypatch.setattr(github, "fetch_issue", lambda o, r, n: Issue(
        o, r, n, "multiply returns sum", "should return a*b", "open", [], ""))
    monkeypatch.setattr(codebase, "clone_repo", lambda url, dest, depth=1: (shutil.copytree(repo, dest, dirs_exist_ok=True), True)[1])
    monkeypatch.setattr(codebase, "detect_test_command", lambda workdir: f"{sys.executable} -m pytest -q")
    from prforge.config import Config
    monkeypatch.setattr(Config, "from_env", classmethod(lambda cls, **kw: cls.__new__(cls)))
    # build a minimal cfg
    cfg = Config.from_env()
    cfg.workdir_root = tmp_path / "work"
    cfg.workdir_root.mkdir(parents=True, exist_ok=True)
    cfg.dry_run = True
    cfg.sandbox_image = "prforge-sandbox:latest"
    cfg.approval_callback = lambda c, s: True
    monkeypatch.setattr(Config, "from_env", classmethod(lambda cls, **kw: cfg))
    return TestClient(ds.app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_solve_and_list_and_approve(client):
    r = client.post("/api/solve", json={"issue_url": "https://github.com/o/r/issues/1", "dry_run": True})
    assert r.status_code == 200
    run = r.json()
    assert run["status"] == "done"
    assert run["edits_applied"] == 1
    run_id = run["id"]

    r = client.get("/api/runs")
    assert r.status_code == 200
    assert len(r.json()["runs"]) == 1

    r = client.get(f"/api/runs/{run_id}")
    assert r.status_code == 200
    assert "return a * b" in r.json()["diff"]

    r = client.post(f"/api/runs/{run_id}/approve")
    assert r.status_code == 200
    assert r.json()["approved"] is True


def test_get_run_404(client):
    r = client.get("/api/runs/does-not-exist")
    assert r.status_code == 404
