"""GitHub operations via the `gh` CLI (reuses your existing auth).

Falls back to the public REST API (unauthenticated, rate-limited) for reads
when `gh` is unavailable.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Any

from prforge.utils import run

ISSUE_URL_RE = re.compile(
    r"github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/(?:issues|pull)/(?P<number>\d+)"
)


@dataclass
class Issue:
    owner: str
    repo: str
    number: int
    title: str
    body: str
    state: str
    labels: list[str]
    url: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}#{self.number}"


def parse_issue_url(url: str) -> tuple[str, str, int]:
    """Return (owner, repo, number) from a GitHub issue URL."""
    m = ISSUE_URL_RE.search(url.strip())
    if not m:
        raise ValueError(f"Could not parse GitHub issue URL: {url!r}")
    return m["owner"], m["repo"], int(m["number"])


def _gh_available() -> bool:
    return run(["gh", "--version"]).ok


def fetch_issue(owner: str, repo: str, number: int) -> Issue:
    """Fetch an issue. Uses `gh` if available, else the public API."""
    url = f"https://github.com/{owner}/{repo}/issues/{number}"
    if _gh_available():
        res = run(
            ["gh", "issue", "view", str(number), "-R", f"{owner}/{repo}", "--json",
             "title,body,state,labels,url"]
        )
        if res.ok:
            data = json.loads(res.stdout)
            return Issue(
                owner=owner, repo=repo, number=number,
                title=data.get("title", "").strip(),
                body=data.get("body", "") or "",
                state=data.get("state", "open"),
                labels=[l["name"] if isinstance(l, dict) else str(l) for l in data.get("labels", [])],
                url=data.get("url", url),
            )
    # Fallback: unauthenticated public API
    res = run(["curl", "-fsSL", f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"])
    if res.ok:
        data = json.loads(res.stdout)
        return Issue(
            owner=owner, repo=repo, number=number,
            title=data.get("title", "").strip(),
            body=data.get("body", "") or "",
            state=data.get("state", "open"),
            labels=[l.get("name", "") for l in data.get("labels", [])],
            url=data.get("html_url", url),
        )
    raise RuntimeError(f"Could not fetch issue {owner}/{repo}#{number}: {res.stderr or res.stdout}")


def create_branch(workdir: str, branch: str, base: str = "main") -> bool:
    res = run(["git", "checkout", "-b", branch, base], cwd=workdir)
    if not res.ok:
        # base branch may not be 'main'
        res = run(["git", "checkout", "-b", branch], cwd=workdir)
    return res.ok


def commit_all(workdir: str, message: str) -> bool:
    run(["git", "add", "-A"], cwd=workdir)
    res = run(["git", "commit", "-m", message], cwd=workdir)
    return res.ok


def push(workdir: str, branch: str, remote: str = "origin") -> bool:
    res = run(["git", "push", "-u", remote, branch], cwd=workdir)
    return res.ok


def create_pr(owner: str, repo: str, title: str, body: str, head: str, base: str = "main") -> str:
    """Open a PR via `gh`. Returns the PR URL (or empty string on failure)."""
    res = run(
        ["gh", "pr", "create", "-R", f"{owner}/{repo}", "--title", title,
         "--body", body, "--head", head, "--base", base]
    )
    if res.ok:
        # gh prints the PR URL on the last line
        for line in reversed(res.stdout.strip().splitlines()):
            if line.startswith("http"):
                return line.strip()
    return ""


def set_git_identity(workdir: str, name: str = "prforge-bot", email: str = "prforge@users.noreply.github.com") -> None:
    run(["git", "config", "user.name", name], cwd=workdir)
    run(["git", "config", "user.email", email], cwd=workdir)
