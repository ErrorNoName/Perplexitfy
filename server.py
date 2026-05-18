"""Local HTTP bridge for Perplexify."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from config import ensure_import_paths, load_cookie
from engine import run_query
from models import MODEL_CHOICES


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    model: str | None = None
    context: str = ""


class ChatRequest(QueryRequest):
    history: list[dict[str, str]] = Field(default_factory=list)


def create_app() -> FastAPI:
    ensure_import_paths()
    app = FastAPI(
        title="Perplexify CLI Local Bridge",
        version="1.0.0",
        description="Local HTTP wrapper around the Perplexify reverse-web stack.",
    )

    @app.get("/health")
    async def health() -> dict[str, object]:
        cookie = load_cookie()
        return {
            "ok": bool(cookie.cookie),
            "service": "perplexify",
            "cookie_configured": bool(cookie.cookie),
            "cookie_source": cookie.source,
        }

    @app.get("/models")
    async def models() -> dict[str, object]:
        return {
            "ok": True,
            "models": list(MODEL_CHOICES),
            "note": "Model values are reverse-web preferences; Perplexity reports the effective model_used.",
        }

    @app.post("/ask")
    async def ask(payload: QueryRequest) -> dict[str, object]:
        return await _run_endpoint(payload, mode="ask")

    @app.post("/search")
    async def search(payload: QueryRequest) -> dict[str, object]:
        return await _run_endpoint(payload, mode="search")

    @app.post("/chat")
    async def chat(payload: ChatRequest) -> dict[str, object]:
        context = payload.context or _history_to_context(payload.history)
        result = await run_query(
            payload.query,
            mode="chat",
            model=payload.model,
            context=context,
        )
        return result.to_dict()

    return app


async def _run_endpoint(payload: QueryRequest, *, mode: Literal["ask", "search"]) -> dict[str, object]:
    result = await run_query(
        payload.query,
        mode=mode,
        model=payload.model,
        context=payload.context,
    )
    return result.to_dict()


def _history_to_context(history: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for item in history[-8:]:
        role = str(item.get("role") or "user")
        content = str(item.get("content") or "")
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def run_server(*, host: str = "127.0.0.1", port: int = 8787, reload: bool = False) -> None:
    import uvicorn

    target = "server:create_app"
    uvicorn.run(target, factory=True, host=host, port=port, reload=reload)


app = create_app()
