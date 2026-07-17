"""Small shared helpers."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CmdResult:
    ok: bool
    stdout: str
    stderr: str
    returncode: int


def run(cmd: list[str], cwd: str | Path | None = None, timeout: int = 120) -> CmdResult:
    """Run a command, capturing output. Never raises on non-zero exit."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CmdResult(
            ok=proc.returncode == 0,
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )
    except FileNotFoundError:
        return CmdResult(False, "", f"command not found: {cmd[0]}", 127)
    except subprocess.TimeoutExpired:
        return CmdResult(False, "", f"timed out after {timeout}s", 124)


def load_dotenv(path: str | Path = ".env") -> None:
    """Tiny .env loader (no python-dotenv dependency)."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def strip_fences(text: str) -> str:
    """Strip a single wrapping ```lang ... ``` fence if present."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def parse_json_list(text: str) -> list[str]:
    """Best-effort parse of a JSON array of strings from an LLM response."""
    text = strip_fences(text)
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except json.JSONDecodeError:
        pass
    return []


def truncate(text: str, limit: int = 12000) -> str:
    """Truncate to a char limit with a marker."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated {len(text) - limit} chars]"


def format_files(file_contents: dict[str, str]) -> str:
    """Render a {path: content} dict as a readable block for prompts."""
    if not file_contents:
        return "(no files loaded)"
    parts: list[str] = []
    for path, content in file_contents.items():
        parts.append(f"----- FILE: {path} -----\n{content}")
    return "\n\n".join(parts)
