"""Codebase navigation: clone, repo map, read/grep."""

from __future__ import annotations

import subprocess
from pathlib import Path

from prforge.utils import run

# Directories and extensions to ignore when building a repo map.
IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    ".eggs", ".tox", ".idea", ".vscode", "site-packages",
}
CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".h", ".cpp", ".cc",
    ".hpp", ".rs", ".go", ".rb", ".php", ".cs", ".kt", ".swift", ".scala",
    ".sh", ".bash", ".yml", ".yaml", ".toml", ".json", ".md", ".txt", ".cfg",
    ".ini", ".sql", ".html", ".css", ".scss",
}
MAX_FILE_BYTES = 25_000


def clone_repo(url: str, dest: str, depth: int = 1) -> bool:
    """Shallow-clone a repo into dest."""
    res = run(["git", "clone", "--depth", str(depth), url, dest])
    return res.ok


def build_repo_map(workdir: str, max_files: int = 400) -> str:
    """Build a compact repo map: file tree with line counts for code files."""
    root = Path(workdir)
    lines: list[str] = []
    count = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        if path.suffix.lower() not in CODE_EXTS:
            continue
        try:
            n = sum(1 for _ in path.open(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        lines.append(f"{rel} ({n}L)")
        count += 1
        if count >= max_files:
            lines.append("... [repo map truncated]")
            break
    return "\n".join(lines) if lines else "(empty repo map)"


def read_file(workdir: str, rel_path: str) -> str:
    """Read a file relative to workdir, capped to MAX_FILE_BYTES."""
    p = Path(workdir) / rel_path
    if not p.is_file():
        raise FileNotFoundError(rel_path)
    data = p.read_text(encoding="utf-8", errors="ignore")
    if len(data) > MAX_FILE_BYTES:
        data = data[:MAX_FILE_BYTES] + f"\n... [truncated, {len(data)} bytes total]"
    return data


def list_files(workdir: str, pattern: str = "**/*") -> list[str]:
    root = Path(workdir)
    out: list[str] = []
    for path in sorted(root.glob(pattern)):
        if not path.is_file():
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        out.append(path.relative_to(root).as_posix())
    return out


def grep(workdir: str, pattern: str, extra: list[str] | None = None) -> str:
    """Run ripgrep if available, else fall back to git grep / grep -r."""
    cmd = ["rg", "-n", "--", pattern]
    if extra:
        cmd = ["rg", "-n", *extra, "--", pattern]
    res = run(cmd, cwd=workdir)
    if res.ok:
        return res.stdout[:MAX_FILE_BYTES]
    # fallback to git grep
    res = run(["git", "grep", "-n", pattern], cwd=workdir)
    if res.ok:
        return res.stdout[:MAX_FILE_BYTES]
    return ""


def git_diff(workdir: str) -> str:
    """Return the unstaged + staged diff (the agent's changes)."""
    res = run(["git", "diff", "HEAD"], cwd=workdir)
    return res.stdout if res.ok else ""


def detect_test_command(workdir: str) -> str | None:
    """Guess the repo's test command from common markers."""
    root = Path(workdir)
    if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists() and "pytest" in (root / "pyproject.toml").read_text(errors="ignore"):
        return "pytest -q"
    if (root / "package.json").exists():
        return "npm test"
    if (root / "Cargo.toml").exists():
        return "cargo test"
    if (root / "go.mod").exists():
        return "go test ./..."
    if (root / "pom.xml").exists():
        return "mvn -q test"
    return None
