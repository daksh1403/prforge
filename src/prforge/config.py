"""Configuration loaded from environment variables / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from prforge.utils import load_dotenv


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


@dataclass
class Config:
    """Runtime configuration for a PRForge run."""

    llm_provider: str  # anthropic | openai | ollama
    model: str
    anthropic_api_key: str | None
    openai_api_key: str | None
    ollama_base_url: str
    max_iterations: int
    sandbox_image: str
    workdir_root: Path
    dry_run: bool = True
    auto_approve: bool = False
    # Called by the review node to ask a human whether to push.
    approval_callback: Callable[["Config", dict], bool] = field(default=None, repr=False)

    @classmethod
    def from_env(cls, **overrides) -> "Config":
        load_dotenv()
        cfg = cls(
            llm_provider=_env("PRFORGE_LLM_PROVIDER", "anthropic").lower(),
            model=_env("PRFORGE_MODEL", "claude-sonnet-4-5-20250929"),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            ollama_base_url=_env("PRFORGE_OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            max_iterations=int(_env("PRFORGE_MAX_ITERATIONS", "3")),
            sandbox_image=_env("PRFORGE_SANDBOX_IMAGE", "prforge-sandbox:latest"),
            workdir_root=Path(_env("PRFORGE_WORKDIR_ROOT", "./workdir")).resolve(),
            auto_approve=_env("PRFORGE_AUTO_APPROVE", "false").lower() in ("1", "true", "yes"),
        )
        for k, v in overrides.items():
            setattr(cfg, k, v)
        return cfg

    def validate(self) -> list[str]:
        """Return a list of human-readable problems (empty == ok)."""
        problems: list[str] = []
        if self.llm_provider not in ("anthropic", "openai", "ollama"):
            problems.append(f"Unknown PRFORGE_LLM_PROVIDER={self.llm_provider!r}")
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            problems.append("ANTHROPIC_API_KEY is not set.")
        if self.llm_provider == "openai" and not self.openai_api_key:
            problems.append("OPENAI_API_KEY is not set.")
        if self.max_iterations < 1:
            problems.append("PRFORGE_MAX_ITERATIONS must be >= 1.")
        return problems


def default_approval(cfg: "Config", state: dict) -> bool:
    """Non-interactive default: honour auto_approve, else refuse to push."""
    return cfg.auto_approve
