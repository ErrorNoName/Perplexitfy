"""Standalone Perplexity reverse client for exported Perplexify folders.

This module is intentionally self-contained so the Go TUI can run from a
portable Perplexify directory without importing ``scraping_lab`` or Footix.
It uses the cookie-based reverse SSE endpoint. The richer Footix Browser Bridge
is still used when the package is launched inside Footix.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

PPLX_AUTH_SESSION = "https://www.perplexity.ai/api/auth/session"
PPLX_ASK_ENDPOINT = "https://www.perplexity.ai/rest/sse/perplexity_ask"
PPLX_RATE_LIMIT = "https://www.perplexity.ai/rest/rate-limit/all"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

ENV_PATH = Path(__file__).resolve().parent / ".env"


@dataclass
class PerplexityResponse:
    answer: str = ""
    web_results: list[dict[str, Any]] = field(default_factory=list)
    backend_uuid: str | None = None
    model_used: str | None = None
    status: str = "unknown"
    raw_events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.answer)


class PerplexityClient:
    def __init__(self, cookie: str | None = None, model: str | None = None) -> None:
        self._cookie = cookie or _load_env_value("PPLX_COOKIE")
        self._model = model or _load_env_value("PPLX_MODEL", "sonar")
        self._backend_uuid: str | None = None
        self._session: Any = None

    def _get_session(self) -> Any:
        if self._session is not None:
            return self._session
        try:
            from curl_cffi.requests import Session

            self._session = Session(impersonate="chrome")
        except ImportError:
            import httpx

            self._session = httpx.Client(http2=True, follow_redirects=True)
        return self._session

    def _headers(self, *, accept: str = "text/event-stream") -> dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Content-Type": "application/json",
            "Origin": "https://www.perplexity.ai",
            "Referer": "https://www.perplexity.ai/",
            "Cookie": f"__Secure-next-auth.session-token={self._cookie}",
        }

    def validate_session(self) -> dict[str, Any]:
        if not self._cookie:
            return {"error": "PPLX_COOKIE not set"}
        try:
            resp = self._get_session().get(
                PPLX_AUTH_SESSION,
                headers=self._headers(accept="application/json"),
            )
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            return resp.json() if callable(getattr(resp, "json", None)) else json.loads(resp.text)
        except Exception as exc:
            return {"error": str(exc)}

    def get_rate_limits(self) -> dict[str, Any]:
        if not self._cookie:
            return {"error": "PPLX_COOKIE not set"}
        try:
            resp = self._get_session().get(
                PPLX_RATE_LIMIT,
                headers=self._headers(accept="application/json"),
            )
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            return resp.json() if callable(getattr(resp, "json", None)) else json.loads(resp.text)
        except Exception as exc:
            return {"error": str(exc)}

    def ask(
        self,
        query: str,
        *,
        model: str | None = None,
        search_focus: str = "internet",
        mode: str = "concise",
        timeout: float = 60.0,
    ) -> PerplexityResponse:
        if not self._cookie:
            return PerplexityResponse(error="PPLX_COOKIE not set")

        body = {
            "version": "2.18",
            "source": "default",
            "model_preference": model or self._model,
            "mode": mode,
            "is_pro_search": True,
            "visitor_id": str(uuid4()),
            "frontend_uuid": str(uuid4()),
            "search_focus": search_focus,
            "query_str": query,
            "backend_uuid": self._backend_uuid,
        }
        result = PerplexityResponse()
        try:
            resp = self._get_session().post(
                PPLX_ASK_ENDPOINT,
                headers=self._headers(),
                json=body,
                timeout=timeout,
            )
            if resp.status_code != 200:
                return PerplexityResponse(error=f"HTTP {resp.status_code}: {resp.text[:300]}")
            raw_body = (resp.text if hasattr(resp, "text") else resp.content.decode("utf-8", errors="replace"))
            raw_body = raw_body.replace("\r\n", "\n").replace("\r", "\n")
            for line in raw_body.split("\n"):
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                raw_json = line[5:].strip()
                if not raw_json.startswith("{"):
                    continue
                try:
                    evt = json.loads(raw_json)
                except json.JSONDecodeError:
                    continue
                result.raw_events.append(evt)
                if evt.get("backend_uuid"):
                    result.backend_uuid = evt["backend_uuid"]
                    self._backend_uuid = evt["backend_uuid"]
                if evt.get("display_model"):
                    result.model_used = evt["display_model"]
                if evt.get("answer"):
                    result.answer = evt["answer"]
                if isinstance(evt.get("web_results"), list):
                    result.web_results = evt["web_results"]
                if evt.get("text_completed") or evt.get("final_sse_message"):
                    result.status = "completed"
            if not result.answer:
                result.answer = _extract_answer_from_blocks(result.raw_events)
            if not result.web_results:
                result.web_results = _extract_sources(result.raw_events)
            if result.answer and result.status == "unknown":
                result.status = "partial"
            if not result.model_used:
                result.model_used = "perplexity-reverse-sse"
        except Exception as exc:
            result.error = str(exc)
        return result

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None


async def ask_perplexity_async(query: str, **kwargs: Any) -> PerplexityResponse:
    client = PerplexityClient()
    try:
        return await asyncio.to_thread(client.ask, query, **kwargs)
    finally:
        client.close()


def _load_env_value(key: str, default: str = "") -> str:
    if os.getenv(key):
        return os.getenv(key, "")
    if ENV_PATH.is_file():
        for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            k, _, value = stripped.partition("=")
            if k.strip() == key:
                return value.strip()
    return default


def _extract_answer_from_blocks(events: list[dict[str, Any]]) -> str:
    chunks: list[tuple[int, str]] = []
    seen: set[int] = set()
    for evt in events:
        for block in evt.get("blocks", []):
            usage = block.get("intended_usage", "")
            markdown = block.get("markdown_block")
            if "ask_text" not in usage or not markdown:
                continue
            offset = int(markdown.get("chunk_starting_offset", len(chunks)))
            if offset in seen:
                continue
            seen.add(offset)
            chunks.append((offset, "".join(str(c) for c in markdown.get("chunks", []))))
    chunks.sort(key=lambda item: item[0])
    return "".join(text for _, text in chunks)


def _extract_sources(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for evt in events:
        if isinstance(evt.get("web_results"), list) and len(evt["web_results"]) > len(sources):
            sources = evt["web_results"]
        for block in evt.get("blocks", []):
            plan = block.get("plan_block")
            if not plan:
                continue
            for step in plan.get("steps", []):
                step_sources = step.get("search_results", [])
                if len(step_sources) > len(sources):
                    sources = step_sources
    return sources
