"""Agent node functions.

Each node takes the LangGraph `state` and returns a partial-state dict to merge.
Nodes share an `Agent` instance that holds the config, LLM client, and a logger.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from prforge.agent import prompts
from prforge.llm import LLMClient, Message
from prforge.tools import codebase, editor, github, sandbox
from prforge.utils import parse_json_list, truncate


class Agent:
    """Holds shared dependencies and implements each graph node."""

    def __init__(self, cfg, llm: LLMClient, log) -> None:
        self.cfg = cfg
        self.llm = llm
        self.log = log

    # ---- nodes -----------------------------------------------------------

    def fetch_issue(self, state: dict) -> dict:
        owner, repo, number = github.parse_issue_url(state["issue_url"])
        self.log(f"Fetching issue {owner}/{repo}#{number} ...")
        issue = github.fetch_issue(owner, repo, number)
        self.log(f"  title: {issue.title}")
        return {
            "owner": owner, "repo": repo, "issue_number": number,
            "issue_title": issue.title, "issue_body": issue.body,
            "repo_url": f"https://github.com/{owner}/{repo}.git",
            "iterations": 0,
        }

    def clone_and_map(self, state: dict) -> dict:
        workdir = str(self.cfg.workdir_root / f"{state['owner']}_{state['repo']}_{state['issue_number']}")
        Path(workdir).parent.mkdir(parents=True, exist_ok=True)
        if not Path(workdir).exists():
            self.log(f"Cloning {state['owner']}/{state['repo']} ...")
            if not codebase.clone_repo(state["repo_url"], workdir):
                return {"error": "git clone failed"}
        else:
            self.log("Reusing existing clone.")
        github.set_git_identity(workdir)
        self.log("Building repo map ...")
        repo_map = codebase.build_repo_map(workdir)
        test_cmd = codebase.detect_test_command(workdir)
        self.log(f"  test command: {test_cmd or 'none detected'}")
        return {"workdir": workdir, "repo_map": repo_map, "test_command": test_cmd}

    def localize(self, state: dict) -> dict:
        self.log("Localizing relevant files ...")
        resp = self.llm.complete(
            prompts.LOCALIZE_SYSTEM,
            [Message("user", prompts.localize_prompt(
                state["issue_title"], state["issue_body"], state["repo_map"]))],
        )
        files = parse_json_list(resp)
        # de-duplicate, keep order, only existing files
        seen, kept = set(), []
        for f in files:
            if f in seen:
                continue
            if (Path(state["workdir"]) / f).is_file():
                kept.append(f)
                seen.add(f)
        if not kept:
            # fallback: nothing parsed; let plan work from the map only
            kept = []
        self.log(f"  relevant files: {kept or '(none — will plan from map)'}")
        contents = {f: codebase.read_file(state["workdir"], f) for f in kept}
        return {"relevant_files": kept, "file_contents": contents}

    def plan(self, state: dict) -> dict:
        self.log("Planning fix ...")
        resp = self.llm.complete(
            prompts.PLAN_SYSTEM,
            [Message("user", prompts.plan_prompt(
                state["issue_number"], state["issue_title"], state["issue_body"],
                state["repo_map"], state.get("file_contents", {})))],
        )
        self.log("  plan ready.")
        return {"plan": resp}

    def edit(self, state: dict) -> dict:
        it = state.get("iterations", 0) + 1
        self.log(f"Generating edits (iteration {it}) ...")
        test_out = state.get("test_output") if it > 1 else None
        resp = self.llm.complete(
            prompts.EDIT_SYSTEM,
            [Message("user", prompts.edit_prompt(
                state["plan"], state.get("file_contents", {}), test_out))],
        )
        edits = editor.parse_edits(resp)
        self.log(f"  parsed {len(edits)} edit block(s).")
        applied, errors = editor.apply_edits(edits, state["workdir"])
        self.log(f"  applied {applied}, errors: {len(errors)}")
        # refresh file contents for the next iteration
        new_contents = dict(state.get("file_contents", {}))
        for e in edits:
            try:
                new_contents[e.filename] = codebase.read_file(state["workdir"], e.filename)
            except FileNotFoundError:
                pass
        return {
            "iterations": it, "edits_applied": applied, "edit_errors": errors,
            "file_contents": new_contents,
        }

    def test(self, state: dict) -> dict:
        cmd = state.get("test_command")
        if not cmd:
            self.log("No test command detected — skipping tests.")
            return {"test_pass": True, "test_output": ""}
        self.log(f"Running tests: {cmd}")
        result = sandbox.run_tests(state["workdir"], cmd, self.cfg.sandbox_image)
        tag = "sandbox" if result.ran_in_sandbox else "LOCAL (no sandbox image)"
        self.log(f"  tests {'passed' if result.ok else 'FAILED'} [{tag}]")
        return {"test_pass": result.ok, "test_output": truncate(result.output, 8000)}

    def review(self, state: dict) -> dict:
        diff = codebase.git_diff(state["workdir"])
        self.log(f"Diff ready ({len(diff)} chars). Asking for approval ...")
        approved = self.cfg.approval_callback(self.cfg, {**state, "diff": diff})
        return {"diff": diff, "approved": bool(approved)}

    def push_and_pr(self, state: dict) -> dict:
        if self.cfg.dry_run:
            self.log("DRY RUN — not pushing or opening a PR.")
            return {"pr_url": ""}
        branch = f"prforge/issue-{state['issue_number']}"
        self.log(f"Creating branch {branch} ...")
        github.create_branch(state["workdir"], branch)
        github.commit_all(state["workdir"], f"fix: resolve #{state['issue_number']}\n\n{truncate(state.get('plan',''),1000)}")
        self.log("Pushing ...")
        if not github.push(state["workdir"], branch):
            return {"error": "git push failed (check remote/auth)"}
        self.log("Opening PR ...")
        resp = self.llm.complete(
            prompts.PR_SYSTEM,
            [Message("user", prompts.pr_prompt(
                state["issue_number"], state["issue_title"],
                state.get("plan", ""), state.get("diff", "")))],
        )
        title, body = _split_pr(resp, state["issue_number"])
        pr_url = github.create_pr(state["owner"], state["repo"], title, body, head=branch)
        self.log(f"PR opened: {pr_url or '(failed)'}")
        return {"pr_url": pr_url}

    # ---- routers ---------------------------------------------------------

    def route_after_test(self, state: dict) -> str:
        if state.get("test_pass") or state.get("iterations", 0) >= self.cfg.max_iterations:
            return "review"
        return "edit"

    def route_after_review(self, state: dict) -> str:
        return "push_and_pr" if state.get("approved") else "__end__"


def _split_pr(resp: str, issue_number: int) -> tuple[str, str]:
    title, body = f"Fix #{issue_number}", f"Closes #{issue_number}"
    lines = resp.strip().splitlines()
    if lines and lines[0].upper().startswith("TITLE:"):
        title = lines[0].split(":", 1)[1].strip()
        rest = "\n".join(lines[1:])
        if "BODY:" in rest:
            body = rest.split("BODY:", 1)[1].strip()
        else:
            body = rest.strip()
    if f"#{issue_number}" not in body:
        body = f"{body}\n\nCloses #{issue_number}"
    return title, body
