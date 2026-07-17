"""SWE-bench-style evaluation harness.

Runs the agent over a set of instances and reports the resolve rate: the
fraction of instances whose tests pass after the agent's patch is applied.

Supports two kinds of instance:
  * LOCAL  — a path to a repo on disk (issue given inline).
  * SWE-bench — a remote repo + base_commit + problem_statement + gold
    test_patch + FAIL_TO_PASS / PASS_TO_PASS tests. The runner checks out the
    base_commit, lets the agent write a fix, applies the gold test_patch, then
    runs the gold tests.

Instance format (JSONL, one JSON object per line):

    {"id": "multiply-fix",
     "repo": "./testrepo",
     "issue_title": "multiply returns sum",
     "issue_body": "multiply() returns a+b; should return a*b.",
     "verify_command": "python -m pytest -q",
     "agent_test_command": "python -m pytest -q"}

    {"id": "django__django-11099",
     "repo": "https://github.com/django/django.git",
     "issue_title": "django__django-11099",
     "issue_body": "<problem_statement>",
     "is_local": false,
     "base_commit": "<sha>",
     "test_patch": "<unified diff>",
     "fail_to_pass": ["tests/..."],
     "pass_to_pass": ["tests/..."],
     "agent_test_command": null}
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from prforge.agent.graph import build_graph
from prforge.agent.nodes import Agent
from prforge.config import Config
from prforge.llm import LLMClient
from prforge.tools import codebase, github, sandbox
from prforge.tools.github import Issue
from prforge.utils import run


@dataclass
class EvalInstance:
    id: str
    repo: str
    issue_title: str
    issue_body: str
    verify_command: str = "python -m pytest -q"
    issue_number: int = 1
    is_local: bool = True
    # SWE-bench fields (optional)
    base_commit: str | None = None
    test_patch: str | None = None
    fail_to_pass: list[str] = field(default_factory=list)
    pass_to_pass: list[str] = field(default_factory=list)
    agent_test_command: str | None = None  # None = skip the agent's internal tests

    @classmethod
    def from_dict(cls, d: dict) -> "EvalInstance":
        repo = d["repo"]
        return cls(
            id=d["id"],
            repo=repo,
            issue_title=d.get("issue_title", d.get("title", d["id"])),
            issue_body=d.get("issue_body", d.get("body", d.get("problem_statement", ""))),
            verify_command=d.get("verify_command", "python -m pytest -q"),
            issue_number=d.get("issue_number", 1),
            is_local=d.get("is_local", not str(repo).startswith("http")),
            base_commit=d.get("base_commit"),
            test_patch=d.get("test_patch"),
            fail_to_pass=list(d.get("fail_to_pass", [])),
            pass_to_pass=list(d.get("pass_to_pass", [])),
            agent_test_command=d.get("agent_test_command"),
        )


def load_instances(path: str | Path) -> list[EvalInstance]:
    """Load JSONL instances. Blank lines and # comments are skipped."""
    p = Path(path)
    out: list[EvalInstance] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(EvalInstance.from_dict(json.loads(line)))
    return out


def _checkout_commit(repo_url: str, dest: str, commit: str) -> bool:
    """Fast shallow fetch of a specific commit (works on GitHub)."""
    run(["git", "init", dest])
    run(["git", "-C", dest, "remote", "add", "origin", repo_url])
    res = run(["git", "-C", dest, "fetch", "--depth", "1", "origin", commit])
    if not res.ok:
        return False
    return run(["git", "-C", dest, "checkout", "FETCH_HEAD"]).ok


def _prepare_repo(inst: EvalInstance, dest: str) -> bool:
    if inst.is_local:
        shutil.copytree(inst.repo, dest, dirs_exist_ok=True)
        return True
    if inst.base_commit:
        return _checkout_commit(inst.repo, dest, inst.base_commit)
    return codebase.clone_repo(inst.repo, dest)


def _apply_test_patch(workdir: str, patch: str) -> bool:
    patch_file = Path(workdir) / "_prforge_test_patch.diff"
    patch_file.write_text(patch, encoding="utf-8")
    res = run(["git", "-C", workdir, "apply", str(patch_file)])
    return res.ok


def _verify_command(inst: EvalInstance) -> str:
    if inst.fail_to_pass:
        tests = list(inst.fail_to_pass) + list(inst.pass_to_pass)
        return f"python -m pytest {' '.join(tests)} -q"
    return inst.verify_command


def run_instance(inst: EvalInstance, cfg: Config, llm: LLMClient, log=print) -> dict:
    """Run the agent on one instance and verify the result."""
    owner, repo = "eval", inst.id
    workdir = str(cfg.workdir_root / f"{owner}_{repo}_{inst.issue_number}")
    shutil.rmtree(workdir, ignore_errors=True)

    orig_fetch = github.fetch_issue
    orig_clone = codebase.clone_repo
    orig_detect = codebase.detect_test_command
    github.fetch_issue = lambda o, r, n: Issue(
        owner, repo, n, inst.issue_title, inst.issue_body, "open", [], "")
    codebase.clone_repo = lambda url, dest, depth=1: _prepare_repo(inst, dest)
    codebase.detect_test_command = lambda workdir: inst.agent_test_command

    cfg.dry_run = True
    cfg.approval_callback = lambda c, s: True

    try:
        agent = Agent(cfg, llm, log)
        graph = build_graph(agent)
        final = graph.invoke(
            {"issue_url": f"https://github.com/{owner}/{repo}/issues/{inst.issue_number}"}
        )
    finally:
        github.fetch_issue = orig_fetch
        codebase.clone_repo = orig_clone
        codebase.detect_test_command = orig_detect

    # Apply the gold test_patch (if any), then run the gold tests.
    patch_applied = True
    if inst.test_patch:
        patch_applied = _apply_test_patch(workdir, inst.test_patch)
        if not patch_applied:
            log(f"  ! test_patch did not apply cleanly")
    verify = sandbox.run_tests(workdir, _verify_command(inst), cfg.sandbox_image)
    return {
        "id": inst.id,
        "resolved": bool(verify.ok) and patch_applied,
        "iterations": final.get("iterations", 0),
        "edits_applied": final.get("edits_applied", 0),
        "test_pass_in_loop": final.get("test_pass"),
        "error": final.get("error"),
        "verify_tail": verify.output[-400:],
    }


def run_eval(
    instances: list[EvalInstance],
    cfg: Config,
    llm_factory: Callable[[Config], LLMClient],
    log=print,
) -> dict:
    """Run the agent over all instances and return a summary."""
    results: list[dict] = []
    for i, inst in enumerate(instances, 1):
        log(f"[{i}/{len(instances)}] {inst.id} ...")
        llm = llm_factory(cfg)
        try:
            results.append(run_instance(inst, cfg, llm, log))
        except Exception as e:  # pragma: no cover - defensive
            results.append({"id": inst.id, "resolved": False, "error": str(e),
                            "iterations": 0, "edits_applied": 0})
    resolved = sum(1 for r in results if r["resolved"])
    return {
        "resolved": resolved,
        "total": len(results),
        "resolve_rate": round(resolved / len(results), 3) if results else 0.0,
        "results": results,
    }


def make_selftest_repo(dest: str) -> str:
    """Create a tiny buggy repo for the --self-test mode."""
    root = Path(dest)
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    (root / "buggy.py").write_text("def multiply(a, b):\n    return a + b\n")
    (root / "test_buggy.py").write_text(
        "from buggy import multiply\n\n\ndef test_multiply():\n    assert multiply(3, 4) == 12\n"
    )
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    return str(root)


class _FakeLLM(LLMClient):
    """Deterministic LLM for --self-test (no API key needed)."""

    def complete(self, system: str, messages) -> str:
        if "triaging" in system:
            return '["buggy.py"]'
        if "step-by-step plan" in system:
            return "Change multiply to return a * b instead of a + b."
        if "SEARCH/REPLACE" in system:
            return (
                "buggy.py\n<<<<<<< SEARCH\ndef multiply(a, b):\n    return a + b\n"
                "=======\ndef multiply(a, b):\n    return a * b\n>>>>>>> REPLACE"
            )
        if "pull request" in system:
            return "TITLE: Fix multiply\nBODY:\n- multiply now returns the product\n\nCloses #1"
        return ""


def self_test(cfg: Config, log=print) -> dict:
    """Run the eval harness on a built-in buggy repo with a fake LLM."""
    repo = make_selftest_repo(str(cfg.workdir_root / "_selftest_repo"))
    inst = EvalInstance(
        id="selftest-multiply",
        repo=repo,
        issue_title="multiply() returns the sum instead of the product",
        issue_body="The multiply function in buggy.py returns a+b. It should return a*b.",
        verify_command=f"{sys.executable} -m pytest -q",
        agent_test_command=f"{sys.executable} -m pytest -q",
    )
    return run_eval([inst], cfg, lambda c: _FakeLLM(), log=log)
