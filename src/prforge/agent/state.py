"""LangGraph state definition."""

from __future__ import annotations

from typing import TypedDict


class RunState(TypedDict, total=False):
    # input
    issue_url: str
    # fetched
    owner: str
    repo: str
    issue_number: int
    issue_title: str
    issue_body: str
    repo_url: str
    # workspace
    workdir: str
    repo_map: str
    relevant_files: list[str]
    file_contents: dict[str, str]
    test_command: str | None
    # agent reasoning
    plan: str
    iterations: int
    # results
    edits_applied: int
    edit_errors: list[str]
    test_output: str
    test_pass: bool
    diff: str
    # gate + output
    approved: bool
    pr_url: str
    error: str
