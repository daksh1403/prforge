"""Aider-style SEARCH/REPLACE edit parsing and application.

The LLM emits blocks of the form:

    path/to/file.py
    <<<<<<< SEARCH
    exact original lines
    =======
    new lines
    >>>>>>> REPLACE

We parse those, then apply each as an exact string replacement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SEARCH_RE = re.compile(
    r"(?P<filename>[^\n<>|]+?)\n<<<<<<< SEARCH\n(?P<search>.*?)\n=======\n(?P<replace>.*?)\n>>>>>>> REPLACE",
    re.DOTALL,
)


@dataclass
class Edit:
    filename: str
    search: str
    replace: str


class EditError(RuntimeError):
    pass


def parse_edits(text: str) -> list[Edit]:
    """Parse all SEARCH/REPLACE blocks from an LLM response."""
    edits: list[Edit] = []
    for m in SEARCH_RE.finditer(text):
        filename = m.group("filename").strip().strip("`").strip()
        edits.append(Edit(filename=filename, search=m.group("search"), replace=m.group("replace")))
    return edits


def apply_edit(file_path: str | Path, search: str, replace: str) -> bool:
    """Apply one edit. Returns True if applied, raises EditError if search not found."""
    p = Path(file_path)
    if not p.exists():
        raise EditError(f"File not found: {p}")
    content = p.read_text(encoding="utf-8")
    if search not in content:
        # try with normalized line endings
        if search.replace("\r\n", "\n") in content.replace("\r\n", "\n"):
            content = content.replace("\r\n", "\n")
        else:
            raise EditError(
                f"SEARCH block not found in {p.name}. "
                f"Make sure the SEARCH text matches the file exactly."
            )
    if content.count(search) > 1:
        raise EditError(f"SEARCH block is ambiguous in {p.name} (matches {content.count(search)} times).")
    new_content = content.replace(search, replace, 1)
    p.write_text(new_content, encoding="utf-8")
    return True


def apply_edits(edits: list[Edit], workdir: str) -> tuple[int, list[str]]:
    """Apply a list of edits. Returns (applied_count, errors)."""
    applied = 0
    errors: list[str] = []
    for edit in edits:
        target = Path(workdir) / edit.filename
        try:
            apply_edit(target, edit.search, edit.replace)
            applied += 1
        except EditError as e:
            errors.append(str(e))
    return applied, errors
