"""Shared solve runner used by the CLI `solve` and `batch` commands."""

from __future__ import annotations

from typing import Callable

from prforge.agent.graph import build_graph
from prforge.agent.nodes import Agent
from prforge.config import Config
from prforge.llm import LLMClient


def run_solve(
    issue_url: str,
    cfg: Config,
    llm: LLMClient,
    log: Callable[[str], None] = print,
    dry_run: bool = True,
) -> dict:
    """Run the full agent graph on one issue URL. Returns the final state.

    The caller is responsible for setting `cfg.approval_callback` beforehand
    (interactive gate, auto-approve, or eval-style auto-approve).
    """
    cfg.dry_run = dry_run
    agent = Agent(cfg, llm, log)
    graph = build_graph(agent)
    return graph.invoke({"issue_url": issue_url})
