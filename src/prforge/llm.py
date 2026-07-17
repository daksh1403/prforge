"""LLM provider abstraction.

A single `complete(system, messages) -> str` interface backed by Anthropic,
OpenAI, or a local Ollama instance (via its OpenAI-compatible endpoint).
Provider SDKs are imported lazily so the package imports without them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prforge.config import Config


class LLMError(RuntimeError):
    """Raised when an LLM call fails or a provider is misconfigured."""


@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: str


class LLMClient:
    """Base class. Subclasses implement `complete`."""

    def complete(self, system: str, messages: list[Message]) -> str:  # pragma: no cover
        raise NotImplementedError


class AnthropicClient(LLMClient):
    def __init__(self, cfg: "Config") -> None:
        try:
            import anthropic  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise LLMError("Install the anthropic extra: pip install 'prforge[anthropic]'") from e
        if not cfg.anthropic_api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set.")
        self._client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
        self._model = cfg.model

    def complete(self, system: str, messages: list[Message]) -> str:
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=8192,
                system=system,
                messages=[{"role": m.role, "content": m.content} for m in messages],
            )
            return "".join(block.text for block in resp.content if hasattr(block, "text"))
        except Exception as e:  # pragma: no cover
            raise LLMError(f"Anthropic call failed: {e}") from e


class OpenAICompatClient(LLMClient):
    """Works for OpenAI and for Ollama (OpenAI-compatible /v1 endpoint)."""

    def __init__(self, cfg: "Config", base_url: str | None = None) -> None:
        try:
            import openai  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise LLMError("Install the openai extra: pip install 'prforge[openai]'") from e
        if cfg.llm_provider == "openai" and not cfg.openai_api_key:
            raise LLMError("OPENAI_API_KEY is not set.")
        self._client = openai.OpenAI(
            api_key=cfg.openai_api_key or "ollama",
            base_url=base_url,
        )
        self._model = cfg.model

    def complete(self, system: str, messages: list[Message]) -> str:
        try:
            full = [{"role": "system", "content": system}] + [
                {"role": m.role, "content": m.content} for m in messages
            ]
            resp = self._client.chat.completions.create(model=self._model, messages=full, max_tokens=8192)
            return resp.choices[0].message.content or ""
        except Exception as e:  # pragma: no cover
            raise LLMError(f"OpenAI-compatible call failed: {e}") from e


def get_llm(cfg: "Config") -> LLMClient:
    """Factory: build the configured LLM client."""
    if cfg.llm_provider == "anthropic":
        return AnthropicClient(cfg)
    if cfg.llm_provider == "openai":
        return OpenAICompatClient(cfg)
    if cfg.llm_provider == "ollama":
        return OpenAICompatClient(cfg, base_url=cfg.ollama_base_url)
    raise LLMError(f"Unknown provider: {cfg.llm_provider!r}")
