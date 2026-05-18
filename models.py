"""Shared data structures for Perplexify CLI and HTTP mode."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

MODEL_CHOICES: tuple[str, ...] = ("sonar", "sonar-pro", "gpt", "claude")
MODE_CHOICES: tuple[str, ...] = ("ask", "search", "chat")


@dataclass
class PerplexifySource:
    """Normalized source shape for terminal, JSON, and HTTP output."""

    title: str
    url: str
    snippet: str = ""
    host: str = ""

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "PerplexifySource":
        url = str(raw.get("url") or raw.get("link") or "").strip()
        title = str(raw.get("name") or raw.get("title") or raw.get("host") or url).strip()
        snippet = str(raw.get("snippet") or raw.get("description") or "").strip()
        host = str(raw.get("host") or "").strip()
        return cls(title=title or url, url=url, snippet=snippet, host=host)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class PerplexifyResult:
    """Stable public response contract for Perplexify integrations."""

    ok: bool
    mode: str
    query: str
    answer: str = ""
    sources: list[PerplexifySource] = field(default_factory=list)
    model_requested: str | None = None
    model_used: str | None = None
    status: str = "unknown"
    elapsed_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sources"] = [source.to_dict() for source in self.sources]
        return data
